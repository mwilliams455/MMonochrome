#!/usr/bin/env python3
"""Verify M Monochrom vs M9 BF561 scalar/colour symbol topology.

This is deliberately a fixed-record / byte-level provenance check, not a broad
string-token search and not an instruction decoder.  It exists because an early
handoff described several M9 colour-path names as shared "symbol-like tokens",
while the later canonical bf0.map comparison found those exact fixed-width
records absent from the Monochrom imaging map.

The stronger claim checked here is narrowly defined:

* Monochrom BF561/bf0.map is 13,440 bytes / 420 fixed-width records;
* every exact (name,address,size) Monochrom bf0 record exists in M9 bf0;
* the complete Monochrom bf0.map occurs byte-for-byte in M9 bf0.map at 0x3940;
* named M9 colour-path records are absent from Monochrom bf0 but present in M9.

This does not prove that equivalent arithmetic cannot be inlined elsewhere, and
it does not establish runtime photographic ordering.  No Leica firmware bytes
are distributed with this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Dict, List


EXPECTED_MONO_BF0_SIZE = 13_440
EXPECTED_MONO_BF0_RECORDS = 420
EXPECTED_MONO_IN_M9_BF0_OFFSET = 0x3940
EXPECTED_M9_BF0_SHA256 = "1efdcd44e8a0739494d9bd1923767b12f04dae5c0b60cb4b02e940aaa28777de"

MONO_RETAINED = [
    "Process_Y",
    "L3L1_Put8BitY",
    "Process_Shading",
    "Process_Contrast",
    "ExecuteContrast_11LUT8_7",
    "ExecuteContrast_11LUT8_2",
    "ExecuteContrast_11LUT8_3",
    "Process_Noise",
    "Process_Sharpness",
    "LoadLutArchiveL3",
    "LoadISODataL1",
    "CalculateNoiseParameter",
]

DISPUTED_M9_COLOUR_PATH = [
    "ExecuteColorMatrix_14FM1",
    "Process_WB",
    "Process_FPGA_Y",
    "Process_FPGA_YCrCb",
    "SetMatrixL3",
    "LoadLutDataL3",
    "L3L1_Put16BitRGB",
    "L3L1_Put3rgb",
    "L3L1_Put3yycrcb",
    "Process_DNGNoise",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def records_bytes(data: bytes, label: str) -> List[dict]:
    if len(data) % 32:
        raise ValueError(f"{label}: map size {len(data)} is not a multiple of 32")
    out: List[dict] = []
    for off in range(0, len(data), 32):
        rec = data[off : off + 32]
        name = rec[:24].split(b"\0", 1)[0].decode("ascii", "ignore").rstrip("'")
        addr, size = struct.unpack_from("<II", rec, 24)
        if name:
            out.append({"name": name, "addr": addr, "size": size, "map_off": off})
    return out


def records(path: Path) -> List[dict]:
    return records_bytes(path.read_bytes(), str(path))


def by_name(rows: List[dict]) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    for row in rows:
        out.setdefault(row["name"], []).append(row)
    return out


def exact_tuple_set(rows: List[dict]) -> set[tuple[str, int, int]]:
    return {(r["name"], r["addr"], r["size"]) for r in rows}


def locations(index: Dict[str, List[dict]], name: str) -> List[dict]:
    return [
        {
            "address": f"0x{r['addr']:08x}",
            "size": r["size"],
            "map_offset": f"0x{r['map_off']:x}",
        }
        for r in index.get(name, [])
    ]


def map_summary(path: Path | None) -> dict | None:
    if path is None:
        return None
    data = path.read_bytes()
    rows = records_bytes(data, str(path))
    return {
        "path": str(path),
        "size": len(data),
        "record_count": len(rows),
        "sha256": sha256(data),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mono-map", required=True, type=Path, help="Monochrom BF561/bf0.map")
    ap.add_argument("--m9-map", type=Path, help="M9 BF561/bf0.map")
    ap.add_argument("--mono-bf1-map", type=Path, help="optional Monochrom BF561/bf1.map")
    ap.add_argument("--m9-bf1-map", type=Path, help="optional M9 BF561/bf1.map")
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    mono_bytes = args.mono_map.read_bytes()
    mono_rows = records_bytes(mono_bytes, str(args.mono_map))
    mono = by_name(mono_rows)

    m9_bytes = args.m9_map.read_bytes() if args.m9_map else None
    m9_rows = records_bytes(m9_bytes, str(args.m9_map)) if m9_bytes is not None else []
    m9 = by_name(m9_rows)

    retained = {
        name: {
            "mono_present": name in mono,
            "mono_locations": locations(mono, name),
            "m9_present": (name in m9) if args.m9_map else None,
            "m9_locations": locations(m9, name) if args.m9_map else [],
        }
        for name in MONO_RETAINED
    }
    disputed = {
        name: {
            "mono_bf0_present": name in mono,
            "mono_bf0_locations": locations(mono, name),
            "m9_bf0_present": (name in m9) if args.m9_map else None,
            "m9_bf0_locations": locations(m9, name) if args.m9_map else [],
        }
        for name in DISPUTED_M9_COLOUR_PATH
    }

    embedded_offset = m9_bytes.find(mono_bytes) if m9_bytes is not None else None
    tuple_subset = (
        exact_tuple_set(mono_rows) <= exact_tuple_set(m9_rows)
        if args.m9_map
        else None
    )
    exact_tuple_intersection_count = (
        len(exact_tuple_set(mono_rows) & exact_tuple_set(m9_rows))
        if args.m9_map
        else None
    )

    bf1 = None
    if args.mono_bf1_map or args.m9_bf1_map:
        if not (args.mono_bf1_map and args.m9_bf1_map):
            raise ValueError("provide both --mono-bf1-map and --m9-bf1-map, or neither")
        mono_bf1_bytes = args.mono_bf1_map.read_bytes()
        m9_bf1_bytes = args.m9_bf1_map.read_bytes()
        mono_bf1_rows = records_bytes(mono_bf1_bytes, str(args.mono_bf1_map))
        m9_bf1_rows = records_bytes(m9_bf1_bytes, str(args.m9_bf1_map))
        mono_bf1 = by_name(mono_bf1_rows)
        m9_bf1 = by_name(m9_bf1_rows)
        bf1 = {
            "mono": map_summary(args.mono_bf1_map),
            "m9": map_summary(args.m9_bf1_map),
            "byte_identical": mono_bf1_bytes == m9_bf1_bytes,
            "disputed_symbol_presence": {
                name: {
                    "mono_bf1_present": name in mono_bf1,
                    "m9_bf1_present": name in m9_bf1,
                }
                for name in DISPUTED_M9_COLOUR_PATH
            },
            "purpose": (
                "diagnose whether an earlier broad token inventory may have observed "
                "names outside the Monochrom bf0 imaging map; presence here is not "
                "proof of runtime use by the Monochrom bf0 photographic overlay"
            ),
        }

    out = {
        "schema": "mmonochrom.scalar_topology.v2",
        "scope": "fixed_record_and_byte_topology_only_not_instruction_semantics_or_runtime_order",
        "evidence_precedence": (
            "exact fixed-width bf0 records and byte containment outrank broad symbol-like token searches"
        ),
        "mono_bf0": map_summary(args.mono_map),
        "m9_bf0": map_summary(args.m9_map),
        "canonical_checks": {
            "expected_mono_size": EXPECTED_MONO_BF0_SIZE,
            "expected_mono_record_count": EXPECTED_MONO_BF0_RECORDS,
            "expected_mono_in_m9_offset": f"0x{EXPECTED_MONO_IN_M9_BF0_OFFSET:x}",
            "observed_mono_in_m9_offset": (
                f"0x{embedded_offset:x}" if embedded_offset is not None and embedded_offset >= 0 else embedded_offset
            ),
            "all_mono_exact_tuples_present_in_m9": tuple_subset,
            "exact_tuple_intersection_count": exact_tuple_intersection_count,
            "expected_m9_bf0_sha256": EXPECTED_M9_BF0_SHA256,
        },
        "monochrom_scalar_spatial_family": retained,
        "disputed_m9_colour_path_names": disputed,
        "bf1_crosscheck": bf1,
        "interpretation": (
            "If the canonical byte/record checks pass, the named M9 WB/ColorMatrix/FPGA-Y/YCbCr "
            "records are superseded as Monochrom bf0 trace targets by stricter map evidence. "
            "Equivalent inlined arithmetic or activity in another processor/overlay remains open."
        ),
    }

    problems: List[str] = []
    if len(mono_bytes) != EXPECTED_MONO_BF0_SIZE:
        problems.append(
            f"Monochrom bf0.map size {len(mono_bytes)} != canonical {EXPECTED_MONO_BF0_SIZE}"
        )
    if len(mono_rows) != EXPECTED_MONO_BF0_RECORDS:
        problems.append(
            f"Monochrom bf0.map record count {len(mono_rows)} != canonical {EXPECTED_MONO_BF0_RECORDS}"
        )
    for name, item in retained.items():
        if not item["mono_present"]:
            problems.append(f"expected Monochrom scalar/spatial symbol missing: {name}")
    for name, item in disputed.items():
        if item["mono_bf0_present"]:
            problems.append(f"disputed M9 colour-path record unexpectedly present in Monochrom bf0: {name}")

    if args.m9_map:
        if sha256(m9_bytes) != EXPECTED_M9_BF0_SHA256:
            problems.append("comparison M9 bf0.map SHA-256 does not match canonical checkpoint")
        if embedded_offset != EXPECTED_MONO_IN_M9_BF0_OFFSET:
            problems.append(
                "Monochrom bf0.map is not embedded at canonical M9 offset "
                f"0x{EXPECTED_MONO_IN_M9_BF0_OFFSET:x}; observed {embedded_offset}"
            )
        if not tuple_subset:
            problems.append("not every Monochrom (name,address,size) record is present in M9 bf0")
        for name in DISPUTED_M9_COLOUR_PATH:
            if name not in m9:
                problems.append(f"comparison M9 bf0 does not contain expected disputed symbol: {name}")

    if bf1 is not None and not bf1["byte_identical"]:
        problems.append("Monochrom and M9 bf1.map are not byte-identical as canonical baseline reports")

    out["strict_checks_passed"] = not problems
    out["problems"] = problems
    print(json.dumps(out, indent=2))

    if args.strict and problems:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
