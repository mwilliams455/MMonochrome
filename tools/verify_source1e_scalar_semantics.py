#!/usr/bin/env python3
"""Strict structural verifier for canonical M Monochrom SOURCE1E routines.

This is intentionally narrower than a disassembler.  GNU Blackfin objdump does
instruction decoding; this script binds that text to exact canonical function
SHA-256 anchors and asserts only the semantic facts needed for SOURCE1E:

* ``Process_Y`` moves 8-bit Y samples, contains no direct calls, supports the
  recovered resolution ratios, and packs raster input in 8x8 groups;
* native ``Process_Contrast`` mode 0 is the 16-bit scalar -> LUT -> 8-bit
  transition already recovered from firmware.

If function bytes or the expected instruction structure drift, verification
fails rather than silently generalising.  It does not claim caller order or
native CCD/FPGA producer semantics.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

PROCESS_Y_SHA256 = "f0694943391ab9b5c2cd75119d7bba5ff817fd5bbbaa2c6598a198cc97d7e22a"
PROCESS_Y_ADDR = 0xFFA028E8
PROCESS_Y_SIZE = 292

PROCESS_CONTRAST_SHA256 = "790659b15a6655d60a750542c69f98eb22c66b300cdb8ad9e4077174aec6a47d"
PROCESS_CONTRAST_ADDR = 0xFFA00B30
PROCESS_CONTRAST_SIZE = 508


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def insn_lines(path: Path) -> list[str]:
    out = []
    for raw in path.read_text(errors="replace").splitlines():
        m = re.match(r"^\s*[0-9a-fA-F]+:\s+(?:[0-9a-fA-F]{2}\s+)+(.+?)\s*$", raw)
        if m:
            out.append(m.group(1).strip())
    return out


def require(condition: bool, message: str, problems: list[str]) -> None:
    if not condition:
        problems.append(message)


def count_contains(lines: list[str], needle: str) -> int:
    return sum(needle in line for line in lines)


def verify_process_y(binary: Path, disasm: Path) -> dict:
    problems: list[str] = []
    data = binary.read_bytes()
    lines = insn_lines(disasm)
    require(len(data) == PROCESS_Y_SIZE, f"Process_Y size {len(data)} != {PROCESS_Y_SIZE}", problems)
    require(sha256(binary) == PROCESS_Y_SHA256, "Process_Y SHA-256 drift", problems)
    require(any("P0 = R1" in x for x in lines), "Process_Y destination pointer P0=R1 missing", problems)
    require(any("P2 = R0" in x for x in lines), "Process_Y source pointer P2=R0 missing", problems)
    require(count_contains(lines, "CALL ") == 0, "Process_Y unexpectedly contains direct CALL", problems)

    byte_loads = count_contains(lines, "R0 = B[P3++]") + count_contains(lines, "R0 = B[P3] (X)")
    byte_stores = count_contains(lines, "B[P0++] = R0")
    word_pixel_ops = sum("W[P3" in x or "W[P0" in x for x in lines)
    require(byte_loads == 8, f"Process_Y core byte-load count {byte_loads} != 8", problems)
    require(byte_stores == 8, f"Process_Y core byte-store count {byte_stores} != 8", problems)
    require(word_pixel_ops == 0, "Process_Y unexpectedly uses word pixel traffic on core source/destination", problems)

    for mode in (1, 2, 3):
        require(any(f"CC = R2 == 0x{mode:x}" in x for x in lines), f"Process_Y mode {mode} branch missing", problems)
    # Mode 4 is compared through R3=4 then R2==R3 rather than an immediate compare.
    require(any("R3 = 0x4" in x for x in lines), "Process_Y mode-4 constant missing", problems)
    require(any("CC = R2 == R3" in x for x in lines), "Process_Y mode-4 compare missing", problems)

    # Structural anchors for the four recovered dimension ratios.
    require(any("R1 = R0 << 0x2" in x for x in lines) and any("R1 = R1 - R0" in x for x in lines),
            "Process_Y 3/4 mode arithmetic missing", problems)
    require(count_contains(lines, ">>>= 0x1") >= 2, "Process_Y 1/2 mode arithmetic missing", problems)
    require(any("0x5556" in x for x in lines) and any("0x5555" in x for x in lines),
            "Process_Y signed divide-by-3 magic missing", problems)
    require(count_contains(lines, ">>>= 0x2") >= 2, "Process_Y 1/4 mode arithmetic missing", problems)

    # The common path reduces both dimensions by 8 and copies 8 byte samples per
    # inner loop while stepping the source by the raster row stride.  This is the
    # characteristic 8x8 Y-block packing stage.
    require(count_contains(lines, ">>>= 0x3") >= 2, "Process_Y /8 tile-count arithmetic missing", problems)
    require(any("P5 = 0x8" in x for x in lines), "Process_Y 8-row inner-loop constant missing", problems)
    require(any("P4 = P4 + P1" in x for x in lines), "Process_Y raster-row stride step missing", problems)
    require(any("P2 += 0x8" in x for x in lines), "Process_Y horizontal 8-pixel block step missing", problems)

    return {
        "function": "Process_Y",
        "address": f"0x{PROCESS_Y_ADDR:08x}",
        "size": len(data),
        "sha256": sha256(binary),
        "direct_call_count": count_contains(lines, "CALL "),
        "core_byte_load_count": byte_loads,
        "core_byte_store_count": byte_stores,
        "recovered_resolution_geometry": {
            "mode_1": "3/4 linear dimensions",
            "mode_2": "1/2 linear dimensions",
            "mode_3": "1/3 linear dimensions",
            "mode_4": "1/4 linear dimensions",
            "other": "unchanged before 8x8 block flooring",
        },
        "recovered_role": (
            "8-bit Y raster-to-8x8-block packing/resolution helper; not a 14-bit sensor-luminance generator"
        ),
        "problems": problems,
        "verified": not problems,
    }


def verify_contrast(binary: Path, disasm: Path) -> dict:
    problems: list[str] = []
    data = binary.read_bytes()
    lines = insn_lines(disasm)
    require(len(data) == PROCESS_CONTRAST_SIZE,
            f"Process_Contrast size {len(data)} != {PROCESS_CONTRAST_SIZE}", problems)
    require(sha256(binary) == PROCESS_CONTRAST_SHA256, "Process_Contrast SHA-256 drift", problems)

    ordered = [
        "R0 = W[P5++] (Z)",
        "R0 = R0 - R5",
        "R0 = MAX (R0, R4)",
        "R0 >>>= 0x3",
        "R0 = R2 + R0",
        "P1 = R0",
        "R0 = B[P1] (X)",
        "B[P4++] = R0",
    ]
    cursor = 0
    positions: list[int] = []
    for needle in ordered:
        hit = next((i for i in range(cursor, len(lines)) if needle in lines[i]), None)
        if hit is None:
            problems.append(f"Process_Contrast mode-0 instruction missing/out of order: {needle}")
            break
        positions.append(hit)
        cursor = hit + 1

    return {
        "function": "Process_Contrast",
        "address": f"0x{PROCESS_CONTRAST_ADDR:08x}",
        "size": len(data),
        "sha256": sha256(binary),
        "mode0_sequence_verified": len(positions) == len(ordered) and not problems,
        "recovered_role": (
            "native mode-0 16-bit scalar above pedestal -> 11-bit LUT index -> 8-bit Y transition"
        ),
        "mode0_semantics": "out8 = curve[max(uint16(sample14)-pedestal,0) >>> 3]",
        "problems": problems,
        "verified": not problems,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--process-y-bin", required=True, type=Path)
    ap.add_argument("--process-y-dis", required=True, type=Path)
    ap.add_argument("--contrast-bin", required=True, type=Path)
    ap.add_argument("--contrast-dis", required=True, type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    py = verify_process_y(args.process_y_bin, args.process_y_dis)
    contrast = verify_contrast(args.contrast_bin, args.contrast_dis)
    out = {
        "schema": "mmonochrom.source1e.scalar_semantics.v1",
        "scope": "exact_hash_bound_structural_semantics_not_caller_order_or_sensor_producer",
        "process_y": py,
        "process_contrast": contrast,
        "conclusion": (
            "Process_Y operates in the already-8-bit Y domain. The recovered native mode-0 "
            "Contrast loop is the 16-bit-to-8-bit transition. Therefore Process_Y is downstream "
            "of the unresolved 14-bit scalar producer problem and should not be used to infer "
            "Monochrom CCD spectral response."
        ),
        "verified": py["verified"] and contrast["verified"],
    }
    print(json.dumps(out, indent=2))
    if args.strict and not out["verified"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
