#!/usr/bin/env python3
"""Hash-bound verifier for M Monochrom raw-buffer slot topology.

This verifier binds only facts directly recovered from canonical 1.022 bf0
routines.  It does not infer sensor spectral response or assign semantic names
like "input"/"output" to the two job-selected processing slots.

Verified facts:
- IM_GetRawBuffer(index) returns index * 0x01450000.
- IM_AppendItem synthesizes a 68-byte job record whose +0x28 slot is fixed to
  raw-buffer index 8, while +0x2c/+0x30 are selected by copied payload bytes
  +7/+8 using the same stride.
- PPI_Enable loads current_job+0x28 and writes it to the PPI/DMA address
  registers before enabling transfer.
- InitInterpolation reserves raw-buffer index 7 in processing_context+0x08.
- SetProcess maps job +0x2c/+0x30 into processing-context L3 slots +0/+4 and
  job +0x28 into context +0x0c/+0x10.

No firmware bytes are stored in the repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

STRIDE = 0x01450000
SLOT7 = 7 * STRIDE
SLOT8 = 8 * STRIDE

ANCHORS = {
    "IM_GetRawBuffer": (10, "4af476c48317292ec119d992692535e79d4128011b0d6aa7643234ed35afefe0"),
    "IM_AppendItem": (162, "57574b11407b7edf08cef55841a2bbfd2c4c79d926a073b02c0b0817cc28ede3"),
    "PPI_Enable": (122, "c1d30ec419d4bee521c59dc4b2314c50be5b555ab377125fa84298fe6034e7a7"),
    "InitInterpolation": (194, "d494d5c63c82501dbeccd453eb25b855a5193e57e24fc3d7f6d2e9d27b8b267c"),
    "SetProcess": (142, "de587b8cad7ddc71bdfb13784f5d56d5d0a0373c010108682d9ac964500067ca"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def norm_lines(path: Path) -> list[str]:
    return [line.lower().replace("0x0x", "0x") for line in path.read_text(errors="replace").splitlines()]


def require(condition: bool, msg: str, problems: list[str]) -> None:
    if not condition:
        problems.append(msg)


def contains(lines: list[str], *needles: str) -> bool:
    return any(all(n.lower() in line for n in needles) for line in lines)


def verify_anchor(name: str, binary: Path, problems: list[str]) -> None:
    size, sha = ANCHORS[name]
    data = binary.read_bytes()
    require(len(data) == size, f"{name}: size {len(data)} != {size}", problems)
    require(digest(binary) == sha, f"{name}: SHA-256 drift", problems)


def main() -> None:
    ap = argparse.ArgumentParser()
    for stem in ("getraw", "append", "ppi", "init", "setprocess"):
        ap.add_argument(f"--{stem}-bin", required=True, type=Path)
        ap.add_argument(f"--{stem}-dis", required=True, type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    problems: list[str] = []
    pairs = {
        "IM_GetRawBuffer": (args.getraw_bin, args.getraw_dis),
        "IM_AppendItem": (args.append_bin, args.append_dis),
        "PPI_Enable": (args.ppi_bin, args.ppi_dis),
        "InitInterpolation": (args.init_bin, args.init_dis),
        "SetProcess": (args.setprocess_bin, args.setprocess_dis),
    }
    lines = {}
    for name, (binary, dis) in pairs.items():
        verify_anchor(name, binary, problems)
        lines[name] = norm_lines(dis)

    g = lines["IM_GetRawBuffer"]
    require(contains(g, "r1.h = 0x145"), "IM_GetRawBuffer: 0x01450000 stride high half missing", problems)
    require(contains(g, "r0 *= r1"), "IM_GetRawBuffer: index*stride multiply missing", problems)

    a = lines["IM_AppendItem"]
    require(contains(a, "r2 = 0x25"), "IM_AppendItem: 37-byte payload copy length missing", problems)
    require(contains(a, "r1 = b[p4 + 0x7]"), "IM_AppendItem: payload byte +7 selector missing", problems)
    require(contains(a, "r0 = b[p4 + 0x8]"), "IM_AppendItem: payload byte +8 selector missing", problems)
    require(contains(a, "r6.h = 0x145"), "IM_AppendItem: raw-buffer stride constant missing", problems)
    require(contains(a, "r0 *= r6"), "IM_AppendItem: +8 selector stride multiply missing", problems)
    require(contains(a, "r1 *= r6"), "IM_AppendItem: +7 selector stride multiply missing", problems)
    require(contains(a, "r2.h = 0xa28"), "IM_AppendItem: fixed slot-8 address constant missing", problems)
    require(contains(a, "[p4 + 0x30] = r0"), "IM_AppendItem: job+0x30 store missing", problems)
    require(contains(a, "[p4 + 0x2c] = r1"), "IM_AppendItem: job+0x2c store missing", problems)
    require(contains(a, "[p4 + 0x28] = r2"), "IM_AppendItem: job+0x28 store missing", problems)

    p = lines["PPI_Enable"]
    require(contains(p, "call", "0xffa03fc8"), "PPI_Enable: IM_GetCurrentJob call missing", problems)
    require(contains(p, "r0 = [p1 + 0x28]"), "PPI_Enable: current_job+0x28 load missing", problems)
    require(contains(p, "p2 = 0x1c24") and contains(p, "p2.h = 0xffc0"),
            "PPI_Enable: PPI/DMA destination register 0xffc01c24 missing", problems)
    require(contains(p, "i0 = 0x1c04") and contains(p, "i0.h = 0xffc0"),
            "PPI_Enable: companion destination register 0xffc01c04 missing", problems)
    require(contains(p, "[p2] = r0"), "PPI_Enable: destination write to 0xffc01c24 missing", problems)
    require(contains(p, "[i0] = r0"), "PPI_Enable: destination write to 0xffc01c04 missing", problems)

    i = lines["InitInterpolation"]
    require(contains(i, "r0 = 0x7"), "InitInterpolation: raw-buffer slot 7 index missing", problems)
    require(contains(i, "call", "0xffa03fd4"), "InitInterpolation: IM_GetRawBuffer call missing", problems)
    require(contains(i, "[p5 + 0x8] = r0"), "InitInterpolation: context+0x08 slot-7 store missing", problems)

    s = lines["SetProcess"]
    require(contains(s, "r3 = [p0 + 0x2c]"), "SetProcess: job+0x2c load missing", problems)
    require(contains(s, "[p1] = r3"), "SetProcess: context+0x00 store missing", problems)
    require(contains(s, "r3 = [p0 + 0x30]"), "SetProcess: job+0x30 load missing", problems)
    require(contains(s, "[p1 + 0x4] = r3"), "SetProcess: context+0x04 store missing", problems)
    require(sum("r3 = [p0 + 0x28]" in line for line in s) >= 2,
            "SetProcess: repeated job+0x28 loads missing", problems)
    require(contains(s, "[p1 + 0xc] = r3"), "SetProcess: context+0x0c store missing", problems)
    require(contains(s, "[p1 + 0x10] = r3"), "SetProcess: context+0x10 store missing", problems)

    out = {
        "schema": "mmonochrom.source1e.raw_buffer_slots.v1",
        "scope": "hash_bound_buffer_slot_topology_not_sensor_spectral_semantics",
        "raw_buffer_stride_bytes": STRIDE,
        "raw_buffer_stride_hex": f"0x{STRIDE:08x}",
        "slot_7_address": f"0x{SLOT7:08x}",
        "slot_8_address": f"0x{SLOT8:08x}",
        "job_record": {
            "size_bytes": 68,
            "slot_capture_fixed": {"offset": "0x28", "index": 8, "address": f"0x{SLOT8:08x}"},
            "slot_selector_a": {"payload_byte_offset": 7, "job_offset": "0x2c", "formula": "byte7 * 0x01450000"},
            "slot_selector_b": {"payload_byte_offset": 8, "job_offset": "0x30", "formula": "byte8 * 0x01450000"},
        },
        "capture_dma": "PPI_Enable programs current_job+0x28 into the PPI/DMA destination registers",
        "processing_context": {
            "0x00": "job+0x2c",
            "0x04": "job+0x30",
            "0x08": "raw-buffer slot 7 (InitInterpolation)",
            "0x0c": "job+0x28",
            "0x10": "job+0x28",
        },
        "conclusion": (
            "Canonical Monochrom firmware uses a fixed-stride raw-buffer bank. The queued job descriptor "
            "does not carry an arbitrary external pixel pointer: it synthesizes buffer-slot addresses. "
            "PPI capture is explicitly directed to fixed slot 8, while processing tracks two job-selected "
            "slots plus reserved slot 7."
        ),
        "problems": problems,
        "verified": not problems,
    }
    print(json.dumps(out, indent=2))
    if args.strict and problems:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
