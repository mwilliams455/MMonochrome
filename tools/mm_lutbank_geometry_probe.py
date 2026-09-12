#!/usr/bin/env python3
"""Probe the original M Monochrom PROCESS/LUTS 16 x 2050-int16 bank.

This is evidence-only.  It intentionally distinguishes geometric/header evidence
from direct consumer proof.  The candidate range 0x58c..0x105cc is exactly
16 * 2050 * 2 bytes.  M9 firmware independently proves its Sharp source bank
uses 2050 signed-int16 values per ISO row, so this probe compares canonical
Monochrom and M9 row geometry and shape without assuming identical offsets.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import struct
from pathlib import Path
from typing import Iterable

MM_FW_SHA = "c9e14ee475408802c83774f37b19c85c57663d9840e8e4c2cfe80e14dec9a7ae"
M9_FW_SHA = "4f962bb7799ad9a6745ab36c2a3ba59757bfcbd205f50472ddf1b904a5756d20"
MM_LUTS_SIZE = 562_940
M9_LUTS_SIZE = 427_744
MM_BANK_START = 0x58C
MM_BANK_END = 0x105CC
MM_ISO_ROWS = 16
LUT_COUNT = 2050
ROW_BYTES = LUT_COUNT * 2
M9_BANK_START = 0xACF8
M9_ISO_ROWS = 13
MM_ISO_COUNT_OFF = 0x98
EXPECTED_MM_ISO = [320,400,500,640,800,1000,1250,1600,2000,2500,3200,4000,5000,6400,8000,10000]


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def parse_pwad(data: bytes) -> list[tuple[str, bytes]]:
    if data[:4] != b"PWAD":
        raise ValueError("not PWAD")
    count, directory = struct.unpack_from("<II", data, 4)
    out = []
    for i in range(count):
        off, size, raw = struct.unpack_from("<II8s", data, directory + 16*i)
        if off + size > len(data):
            raise ValueError("bad PWAD entry")
        name = raw.split(b"\0", 1)[0].decode("ascii", "replace")
        out.append((name, data[off:off+size]))
    return out


def walk(data: bytes, prefix: str = "") -> Iterable[tuple[str, bytes]]:
    for name, payload in parse_pwad(data):
        path = f"{prefix}/{name}" if prefix else name
        yield path, payload
        if payload[:4] == b"PWAD":
            yield from walk(payload, path)


def find_exact(data: bytes, path: str) -> bytes:
    for p, payload in walk(data):
        if p.upper() == path.upper():
            return payload
    raise KeyError(path)


def u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def i16_row(payload: bytes, off: int) -> list[int]:
    return list(struct.unpack_from("<" + "h"*LUT_COUNT, payload, off))


def pearson(a: list[int], b: list[int]) -> float | None:
    if len(a) != len(b) or not a:
        return None
    ma = sum(a)/len(a); mb = sum(b)/len(b)
    sa = sum((x-ma)*(x-ma) for x in a)
    sb = sum((y-mb)*(y-mb) for y in b)
    if sa <= 0 or sb <= 0:
        return None
    return sum((x-ma)*(y-mb) for x,y in zip(a,b)) / math.sqrt(sa*sb)


def row_stats(values: list[int], raw: bytes, slot: int, off: int) -> dict:
    absvals = [abs(v) for v in values]
    n = len(values)
    symmetry_pairs = min(n//2, 1024)
    odd_err = [abs(values[i] + values[-1-i]) for i in range(symmetry_pairs)]
    sign_changes = sum(1 for i in range(1,n) if (values[i] < 0) != (values[i-1] < 0) and values[i] != 0 and values[i-1] != 0)
    return {
        "iso_slot": slot,
        "offset": hex(off),
        "size": len(raw),
        "sha256": sha(raw),
        "min": min(values),
        "max": max(values),
        "max_abs": max(absvals),
        "mean": sum(values)/n,
        "median": statistics.median(values),
        "zero_count": sum(v == 0 for v in values),
        "nonzero_fraction": sum(v != 0 for v in values)/n,
        "negative_fraction": sum(v < 0 for v in values)/n,
        "positive_fraction": sum(v > 0 for v in values)/n,
        "sign_change_count": sign_changes,
        "first8": values[:8],
        "center8": values[n//2-4:n//2+4],
        "last8": values[-8:],
        "odd_symmetry_mae": (sum(odd_err)/len(odd_err)) if odd_err else None,
    }


def aligned_occurrences(payload: bytes, value: int, limit: int = 0x1000) -> list[str]:
    out=[]
    for off in range(0, min(limit, len(payload)-3), 4):
        if u32(payload, off) == value:
            out.append(hex(off))
    return out


def plausible_header_offsets(payload: bytes, limit: int = 0x600) -> list[dict]:
    out=[]
    for off in range(0, min(limit, len(payload)-3), 4):
        v=u32(payload,off)
        if 0 < v < len(payload) and (v % 4 == 0):
            out.append({"header_offset":hex(off),"value":hex(v)})
    return out


def distinct_groups(rows: list[dict]) -> list[dict]:
    groups={}
    for r in rows:
        groups.setdefault(r["sha256"], []).append(r["iso_slot"])
    return [{"sha256":h,"slots":slots} for h,slots in groups.items()]


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("mm_decrypted",type=Path)
    ap.add_argument("m9_decrypted",type=Path)
    ap.add_argument("--out",type=Path,default=Path("MM_LUTBANK_GEOMETRY_PROBE.json"))
    a=ap.parse_args()

    mmfw=a.mm_decrypted.read_bytes(); m9fw=a.m9_decrypted.read_bytes()
    if sha(mmfw)!=MM_FW_SHA: raise SystemExit(f"MM decrypted SHA mismatch: {sha(mmfw)}")
    if sha(m9fw)!=M9_FW_SHA: raise SystemExit(f"M9 decrypted SHA mismatch: {sha(m9fw)}")
    mm=find_exact(mmfw,"LUTS/PROCESS/LUTS")
    m9=find_exact(m9fw,"LUTS/PROCESS/LUTS")
    if len(mm)!=MM_LUTS_SIZE: raise SystemExit(f"MM PROCESS/LUTS size {len(mm)}")
    if len(m9)!=M9_LUTS_SIZE: raise SystemExit(f"M9 PROCESS/LUTS size {len(m9)}")

    mm_geom=MM_BANK_END-MM_BANK_START
    expected_geom=MM_ISO_ROWS*ROW_BYTES
    if mm_geom!=expected_geom:
        raise SystemExit(f"candidate geometry mismatch {mm_geom} != {expected_geom}")

    mm_rows=[]; mm_values=[]
    for slot in range(MM_ISO_ROWS):
        off=MM_BANK_START+slot*ROW_BYTES
        raw=mm[off:off+ROW_BYTES]
        vals=i16_row(mm,off)
        mm_values.append(vals); mm_rows.append(row_stats(vals,raw,slot,off))

    m9_rows=[]; m9_values=[]
    for slot in range(M9_ISO_ROWS):
        off=M9_BANK_START+slot*ROW_BYTES
        raw=m9[off:off+ROW_BYTES]
        vals=i16_row(m9,off)
        m9_values.append(vals); m9_rows.append(row_stats(vals,raw,slot,off))

    correlations=[]
    for i,vals in enumerate(mm_values):
        scores=[]
        for j,mvals in enumerate(m9_values):
            c=pearson(vals,mvals)
            scores.append({"m9_slot":j,"pearson":c})
        valid=[x for x in scores if x["pearson"] is not None]
        best=max(valid,key=lambda x:abs(x["pearson"])) if valid else None
        correlations.append({"mm_slot":i,"best_m9_match_by_abs_pearson":best,"all":scores})

    iso_count=u32(mm,MM_ISO_COUNT_OFF)
    iso_values=[u32(mm,MM_ISO_COUNT_OFF+4+4*i) for i in range(16)] if iso_count==16 else []

    report={
        "schema":"mmonochrom.lutbank.geometry1a.v1",
        "classification":"geometry_and_crosscamera_evidence_only_consumer_not_yet_proven",
        "firmware":{
            "mm_decrypted_sha256":sha(mmfw),"m9_decrypted_sha256":sha(m9fw),
            "mm_process_luts_size":len(mm),"mm_process_luts_sha256":sha(mm),
            "m9_process_luts_size":len(m9),"m9_process_luts_sha256":sha(m9),
        },
        "monochrom_iso_header":{
            "count_offset":hex(MM_ISO_COUNT_OFF),"count":iso_count,
            "values_if_count16":iso_values,"matches_expected_sequence":iso_values==EXPECTED_MM_ISO,
        },
        "candidate_bank":{
            "start":hex(MM_BANK_START),"end":hex(MM_BANK_END),"bytes":mm_geom,
            "iso_rows":MM_ISO_ROWS,"int16_count_per_row":LUT_COUNT,"row_bytes":ROW_BYTES,
            "exact_16x2050x2_geometry":mm_geom==expected_geom,
            "header_u32_0x10":hex(u32(mm,0x10)),
            "header_locations_pointing_to_bank_start":aligned_occurrences(mm,MM_BANK_START),
            "header_locations_pointing_to_bank_end":aligned_occurrences(mm,MM_BANK_END),
            "header_locations_equal_2050":aligned_occurrences(mm,LUT_COUNT),
            "header_locations_equal_16":aligned_occurrences(mm,MM_ISO_ROWS),
            "plausible_offset_fields_first_0x600":plausible_header_offsets(mm),
            "row_groups":distinct_groups(mm_rows),
            "rows":mm_rows,
        },
        "m9_proven_sharp_reference":{
            "bank_start":hex(M9_BANK_START),"iso_rows":M9_ISO_ROWS,"int16_count_per_row":LUT_COUNT,
            "row_bytes":ROW_BYTES,"header_u32_0x10":hex(u32(m9,0x10)),
            "count_u32_0x5f4":u32(m9,0x5f4),"row_groups":distinct_groups(m9_rows),"rows":m9_rows,
        },
        "crosscamera_shape_comparison":correlations,
        "evidence_statement":{
            "proven_here":[
                "Monochrom range 0x58c..0x105cc is exactly 16 rows x 2050 signed-int16 samples",
                "Monochrom ISO header contains 16 physical ISO slots from 320 through 10000 if canonical layout check passes",
                "M9 proven Sharp bank uses the same 2050-int16 row geometry with 13 ISO slots",
            ],
            "not_proven_here":[
                "that the Monochrom 0x58c bank is consumed by LoadAndModifySharpnessData",
                "that the bank is Sharpness rather than another ISO-indexed 2050-sample stage",
                "full photographic placement/order of Process_Sharpness",
            ],
            "next_proof":"disassemble Monochrom LoadLutDataL3 / LoadAndModifySharpnessData and map source pointer + count fields to this bank",
        },
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps({
        "out":str(a.out),
        "mm_header_u32_0x10":report["candidate_bank"]["header_u32_0x10"],
        "bank_start_refs":report["candidate_bank"]["header_locations_pointing_to_bank_start"],
        "count2050_refs":report["candidate_bank"]["header_locations_equal_2050"],
        "iso_count":iso_count,"iso_matches":iso_values==EXPECTED_MM_ISO,
        "mm_distinct_row_groups":len(report["candidate_bank"]["row_groups"]),
        "best_correlations":[x["best_m9_match_by_abs_pearson"] for x in correlations],
    },indent=2))


if __name__=="__main__":
    main()
