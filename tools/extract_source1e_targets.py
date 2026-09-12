#!/usr/bin/env python3
"""Extract exact BF561 SOURCE1E target functions from Leica LDR + map assets.

Purpose:
- establish reproducible function address/size/SHA-256 anchors before decoding;
- compare same-named M Monochrom and M9 routines byte-for-byte when both assets
  are supplied;
- optionally write local raw function slices for a narrow strict decoder.

The canonical M9 bf0.map contains the complete Monochrom bf0.map as an embedded
suffix.  With ``--m9-active-prefix`` this tool finds that exact byte boundary
and excludes the embedded Monochrom records from M9 function selection.  This
prevents archival Monochrom map records from being misidentified as active M9
routines.

This tool intentionally does not disassemble and does not infer pipeline order.
No Leica firmware bytes are stored in this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Dict, List, Tuple


DEFAULT_TARGETS = [
    "Process_Y", "L3L1_Put8BitY", "Process_Shading", "Process_Contrast",
    "Process_Noise", "Process_Sharpness", "Process_Blinker",
    "CalculateNoiseParameter", "LoadISODataL1", "LoadLutArchiveL3",
    "InitL1MemoryProcessing", "DMACopyWindow", "L3L1_Get",
    "L3L1_Put16Bit", "L3L1_Put8Bit", "IP_Start", "IP_FinishLines",
    "IP_Finished", "LoadBlemishL1", "CorrectionBlemishes",
    "CorrectionDualOutput", "SetProcess", "StartInterpolation_Jolos", "Run",
]


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def map_records_bytes(data: bytes, label: str) -> List[dict]:
    if len(data) % 32:
        raise ValueError(f"{label}: map size {len(data)} is not a multiple of 32")
    out = []
    for off in range(0, len(data), 32):
        rec = data[off : off + 32]
        name = rec[:24].split(b"\0", 1)[0].decode("ascii", "ignore").rstrip("'")
        addr, size = struct.unpack_from("<II", rec, 24)
        if name:
            out.append({"name": name, "addr": addr, "size": size, "map_off": off})
    return out


def map_records(path: Path) -> List[dict]:
    return map_records_bytes(path.read_bytes(), str(path))


def ldr_blocks(path: Path) -> List[dict]:
    data = path.read_bytes()
    off = 4
    out = []
    while off + 10 <= len(data):
        addr, count, flags = struct.unpack_from("<IIH", data, off)
        off += 10
        if flags & 1:
            payload = bytes(count)
        else:
            end = off + count
            if end > len(data):
                raise RuntimeError(f"{path}: LDR block at 0x{addr:08x} count={count} overruns file")
            payload = data[off:end]
            off = end
        out.append({"addr": addr, "data": payload, "flags": flags})
        if flags & 0x8000:
            break
    if not out:
        raise RuntimeError(f"{path}: no LDR blocks parsed")
    return out


def read_overlay(blocks: List[dict], addr: int, size: int) -> bytes:
    out = bytearray(size)
    hit = bytearray(size)
    for block in blocks:
        base = block["addr"]
        data = block["data"]
        start = max(addr, base)
        end = min(addr + size, base + len(data))
        if end > start:
            out[start - addr : end - addr] = data[start - base : end - base]
            hit[start - addr : end - addr] = b"\x01" * (end - start)
    if not all(hit):
        first_missing = next(i for i, value in enumerate(hit) if not value)
        raise RuntimeError(
            f"overlay bytes missing at 0x{addr + first_missing:08x} while reading 0x{addr:08x}+{size}"
        )
    return bytes(out)


def index_by_name(rows: List[dict]) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    for row in rows:
        out.setdefault(row["name"], []).append(row)
    return out


def choose_record(index: Dict[str, List[dict]], name: str) -> dict:
    matches = index.get(name, [])
    if not matches:
        raise KeyError(f"symbol not found: {name}")
    return matches[0]


def extract_one(index: Dict[str, List[dict]], blocks: List[dict], name: str) -> Tuple[dict, bytes]:
    rec = choose_record(index, name)
    code = read_overlay(blocks, rec["addr"], rec["size"])
    return rec, code


def brief(rec: dict, code: bytes) -> dict:
    return {
        "address": f"0x{rec['addr']:08x}", "size": rec["size"],
        "map_offset": f"0x{rec['map_off']:x}", "sha256": sha256(code),
        "first16": code[:16].hex(), "last16": code[-16:].hex() if code else "",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mono-ldr", required=True, type=Path)
    ap.add_argument("--mono-map", required=True, type=Path)
    ap.add_argument("--m9-ldr", type=Path)
    ap.add_argument("--m9-map", type=Path)
    ap.add_argument("--m9-active-prefix", action="store_true",
                    help="restrict M9 records to bytes before the exact embedded Monochrom map")
    ap.add_argument("--allow-missing-m9", action="store_true",
                    help="record active-M9 missing symbols without failing --strict")
    ap.add_argument("--target", action="append", dest="targets")
    ap.add_argument("--out-dir", type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    if bool(args.m9_ldr) != bool(args.m9_map):
        raise ValueError("provide both --m9-ldr and --m9-map, or neither")
    if args.m9_active_prefix and not args.m9_map:
        raise ValueError("--m9-active-prefix requires --m9-map")

    targets = args.targets or DEFAULT_TARGETS
    mono_map_bytes = args.mono_map.read_bytes()
    mono_rows = map_records_bytes(mono_map_bytes, str(args.mono_map))
    mono_index = index_by_name(mono_rows)
    mono_blocks = ldr_blocks(args.mono_ldr)

    m9_index = None
    m9_blocks = None
    m9_active_end = None
    if args.m9_ldr:
        m9_map_bytes = args.m9_map.read_bytes()
        m9_rows = map_records_bytes(m9_map_bytes, str(args.m9_map))
        if args.m9_active_prefix:
            m9_active_end = m9_map_bytes.find(mono_map_bytes)
            if m9_active_end < 0:
                raise RuntimeError("exact Monochrom map is not embedded in supplied M9 map")
            if m9_active_end % 32:
                raise RuntimeError(f"embedded Monochrom map begins off record boundary: 0x{m9_active_end:x}")
            m9_rows = [row for row in m9_rows if row["map_off"] < m9_active_end]
        m9_index = index_by_name(m9_rows)
        m9_blocks = ldr_blocks(args.m9_ldr)

    if args.out_dir:
        args.out_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "schema": "mmonochrom.source1e.function_anchors.v3",
        "scope": "exact_function_slices_before_instruction_decode",
        "mono_ldr_sha256": sha256(args.mono_ldr.read_bytes()),
        "mono_map_sha256": sha256(mono_map_bytes),
        "m9_ldr_sha256": sha256(args.m9_ldr.read_bytes()) if args.m9_ldr else None,
        "m9_map_sha256": sha256(args.m9_map.read_bytes()) if args.m9_map else None,
        "m9_active_prefix_enabled": bool(args.m9_active_prefix),
        "m9_active_map_end": f"0x{m9_active_end:x}" if m9_active_end is not None else None,
        "m9_embedded_monochrom_records_excluded": (
            len(mono_map_bytes) // 32 if m9_active_end is not None else 0
        ),
        "targets": {},
    }

    problems: List[str] = []
    missing_m9: List[str] = []
    for name in targets:
        item = {"name": name}
        try:
            mono_rec, mono_code = extract_one(mono_index, mono_blocks, name)
            item["monochrom"] = brief(mono_rec, mono_code)
            if args.out_dir:
                (args.out_dir / f"mm_{name}.bin").write_bytes(mono_code)
        except (KeyError, RuntimeError) as exc:
            item["monochrom_error"] = str(exc)
            problems.append(f"Monochrom {name}: {exc}")
            result["targets"][name] = item
            continue

        if m9_index is not None and m9_blocks is not None:
            try:
                m9_rec, m9_code = extract_one(m9_index, m9_blocks, name)
                item["m9"] = brief(m9_rec, m9_code)
                item["same_address"] = mono_rec["addr"] == m9_rec["addr"]
                item["same_size"] = mono_rec["size"] == m9_rec["size"]
                item["byte_identical"] = mono_code == m9_code
                if args.out_dir:
                    (args.out_dir / f"m9_{name}.bin").write_bytes(m9_code)
            except KeyError as exc:
                item["m9_error"] = str(exc)
                missing_m9.append(name)
                if not args.allow_missing_m9:
                    problems.append(f"M9 {name}: {exc}")
            except RuntimeError as exc:
                item["m9_error"] = str(exc)
                problems.append(f"M9 {name}: {exc}")

        result["targets"][name] = item

    result["missing_active_m9_targets"] = missing_m9
    result["problems"] = problems
    result["strict_checks_passed"] = not problems
    result["next_step"] = (
        "Trace the active Monochrom Run transfer path backwards from the 16-bit shading/contrast "
        "buffer. Treat M9 records in the embedded Monochrom suffix as archival provenance, not "
        "active M9 code targets."
    )
    print(json.dumps(result, indent=2))
    if args.strict and problems:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
