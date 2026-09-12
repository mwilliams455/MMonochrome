#!/usr/bin/env python3
"""Verify M Monochrom vs M9 BF561 scalar/colour symbol topology.

This tool intentionally proves only map-level topology. It does not claim that
an absent named function cannot have equivalent arithmetic inlined elsewhere.
No Leica firmware bytes are distributed with this repository.
"""
from __future__ import annotations

import argparse
import json
import struct
from pathlib import Path
from typing import Dict, List


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

M9_COLOUR_PATH_REMOVED = [
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


def records(path: Path) -> List[dict]:
    data = path.read_bytes()
    if len(data) % 32:
        raise ValueError(f"{path}: map size {len(data)} is not a multiple of 32")
    out: List[dict] = []
    for off in range(0, len(data), 32):
        rec = data[off : off + 32]
        name = rec[:24].split(b"\0", 1)[0].decode("ascii", "ignore").rstrip("'")
        addr, size = struct.unpack_from("<II", rec, 24)
        if name:
            out.append({"name": name, "addr": addr, "size": size, "map_off": off})
    return out


def by_name(rows: List[dict]) -> Dict[str, List[dict]]:
    out: Dict[str, List[dict]] = {}
    for row in rows:
        out.setdefault(row["name"], []).append(row)
    return out


def locations(index: Dict[str, List[dict]], name: str) -> List[dict]:
    return [
        {
            "address": f"0x{r['addr']:08x}",
            "size": r["size"],
            "map_offset": f"0x{r['map_off']:x}",
        }
        for r in index.get(name, [])
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--mono-map", required=True, type=Path)
    ap.add_argument("--m9-map", type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    mono_rows = records(args.mono_map)
    mono = by_name(mono_rows)
    m9_rows = records(args.m9_map) if args.m9_map else []
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
    removed = {
        name: {
            "mono_present": name in mono,
            "mono_locations": locations(mono, name),
            "m9_present": (name in m9) if args.m9_map else None,
            "m9_locations": locations(m9, name) if args.m9_map else [],
        }
        for name in M9_COLOUR_PATH_REMOVED
    }

    out = {
        "schema": "mmonochrom.scalar_topology.v1",
        "scope": "symbol_map_topology_only_not_instruction_semantics",
        "mono_map": str(args.mono_map),
        "mono_size": args.mono_map.stat().st_size,
        "mono_record_count": len(mono_rows),
        "m9_map": str(args.m9_map) if args.m9_map else None,
        "m9_size": args.m9_map.stat().st_size if args.m9_map else None,
        "m9_record_count": len(m9_rows) if args.m9_map else None,
        "monochrom_scalar_spatial_family": retained,
        "m9_named_colour_path_expected_absent_from_monochrom": removed,
        "interpretation": (
            "Named M9 WB/ColorMatrix/FPGA-Y/YCbCr stages being absent while "
            "Process_Y/L3L1_Put8BitY/Shading/Contrast remain supports a scalar-first "
            "Monochrom trace target, but does not exclude equivalent inlined arithmetic."
        ),
    }

    problems: List[str] = []
    for name, item in retained.items():
        if not item["mono_present"]:
            problems.append(f"expected Monochrom scalar/spatial symbol missing: {name}")
    for name, item in removed.items():
        if item["mono_present"]:
            problems.append(f"M9 colour-path symbol unexpectedly present in Monochrom map: {name}")
    if args.m9_map:
        for name in M9_COLOUR_PATH_REMOVED:
            if name not in m9:
                problems.append(f"comparison M9 map does not contain expected symbol: {name}")

    out["strict_checks_passed"] = not problems
    out["problems"] = problems
    print(json.dumps(out, indent=2))

    if args.strict and problems:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
