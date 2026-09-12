#!/usr/bin/env python3
"""Hash-bound verifier for the Monochrom Run-context source provenance.

This closes one upstream step from the previously verified ``Run`` buffer
lineage.  It proves that ``StartInterpolation_Jolos`` passes its first argument
as the Run processing context, first asks ``SetProcess`` to populate that same
context, and that ``SetProcess`` copies the primary L3 source pointer from
``source_descriptor + 0x2c`` into ``context + 0x00``.

It does not identify who filled ``source_descriptor + 0x2c``.  That remains the
next producer-boundary target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

START_ADDR = 0xFFA0377C
START_SIZE = 118
START_SHA256 = "625e328d67af33b3d14705b3d2155367a8977c8c42c6769ac7db767c9fc92a53"
SET_ADDR = 0xFFA127D0
SET_SIZE = 142
SET_SHA256 = "de587b8cad7ddc71bdfb13784f5d56d5d0a0373c010108682d9ac964500067ca"
RUN_ADDR = 0xFFA01790


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines_by_addr(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        m = re.match(r"^\s*([0-9a-fA-F]+):", raw)
        if m:
            out[int(m.group(1), 16)] = raw.lower().replace("0x0x", "0x")
    return out


def require_at(lines: dict[int, str], addr: int, needles: list[str], label: str, problems: list[str]) -> None:
    line = lines.get(addr, "")
    for needle in needles:
        if needle.lower() not in line:
            problems.append(f"{label} @0x{addr:08x}: expected {needle!r}; got {line!r}")


def require_hash(path: Path, size: int, expected: str, label: str, problems: list[str]) -> dict:
    data = path.read_bytes()
    got = hashlib.sha256(data).hexdigest()
    if len(data) != size:
        problems.append(f"{label}: size {len(data)} != {size}")
    if got != expected:
        problems.append(f"{label}: SHA-256 drift {got}")
    return {"size": len(data), "sha256": got}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-bin", required=True, type=Path)
    ap.add_argument("--start-dis", required=True, type=Path)
    ap.add_argument("--set-bin", required=True, type=Path)
    ap.add_argument("--set-dis", required=True, type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    problems: list[str] = []
    anchors = {
        "StartInterpolation_Jolos": require_hash(
            args.start_bin, START_SIZE, START_SHA256, "StartInterpolation_Jolos", problems
        ),
        "SetProcess": require_hash(args.set_bin, SET_SIZE, SET_SHA256, "SetProcess", problems),
    }
    start = lines_by_addr(args.start_dis)
    setp = lines_by_addr(args.set_dis)

    # StartInterpolation ABI aliases: A=entry R0, B=entry R1, C=entry R2.
    # It preserves A in R7, B in R6, and uses C through P1/R0.
    require_at(start, 0xFFA03782, ["r7 = r0"], "preserve context A", problems)
    require_at(start, 0xFFA03784, ["r0 = r2"], "source descriptor C", problems)
    require_at(start, 0xFFA0378E, ["r6 = r1"], "preserve control B", problems)

    # SetProcess(C, A, B): R0 is still C, R1 becomes A, R2 becomes B.
    require_at(start, 0xFFA037A8, ["r1 = r7"], "SetProcess context argument", problems)
    require_at(start, 0xFFA037AA, ["r2 = r6"], "SetProcess control argument", problems)
    require_at(start, 0xFFA037AC, ["call", "0xffa127d0"], "SetProcess call", problems)

    # Run(B, A): the same A context populated above is passed in R1.
    require_at(start, 0xFFA037B0, ["r0 = r6"], "Run first/control argument", problems)
    require_at(start, 0xFFA037B2, ["r1 = r7"], "Run second/context argument", problems)
    require_at(start, 0xFFA037B4, ["call", f"0x{RUN_ADDR:08x}"], "Run call", problems)

    # SetProcess binds P1=context (A) and P0=source descriptor (C), then copies
    # descriptor image-buffer pointers into the context consumed by Run.
    require_at(setp, 0xFFA127D0, ["p1 = r1"], "SetProcess context binding", problems)
    require_at(setp, 0xFFA127F2, ["p0 = r0"], "SetProcess source binding", problems)
    require_at(setp, 0xFFA12820, ["r1 = rot r2 by 0x0", "r3 = [p0 + 0x2c]"],
               "load primary L3 source descriptor", problems)
    require_at(setp, 0xFFA12828, ["[p1] = r3"], "store context primary source", problems)
    require_at(setp, 0xFFA12830, ["r3 = [p0 + 0x30]"], "load secondary source", problems)
    require_at(setp, 0xFFA12832, ["[p1 + 0x4] = r3"], "store secondary source", problems)
    require_at(setp, 0xFFA12834, ["r3 = [p0 + 0x28]"], "load auxiliary source", problems)
    require_at(setp, 0xFFA12836, ["[p1 + 0xc] = r3"], "store auxiliary source", problems)
    require_at(setp, 0xFFA12838, ["r3 = [p0 + 0x28]"], "reload auxiliary source", problems)
    require_at(setp, 0xFFA1283A, ["[p1 + 0x10] = r3"], "store duplicated auxiliary source", problems)

    out = {
        "schema": "mmonochrom.source1e.context_source.v1",
        "scope": "hash_bound_Run_context_pointer_provenance_not_sensor_writer_identity",
        "anchors": anchors,
        "verified_argument_flow": {
            "StartInterpolation_entry": {
                "R0_A": "Run processing context",
                "R1_B": "Run first/control argument",
                "R2_C": "source descriptor",
            },
            "SetProcess_call": "SetProcess(C, A, B)",
            "Run_call": "Run(B, A)",
        },
        "verified_context_pointer_mapping": {
            "context+0x00": "source_descriptor+0x2c (primary L3 image pointer)",
            "context+0x04": "source_descriptor+0x30 (secondary image pointer)",
            "context+0x0c": "source_descriptor+0x28 (auxiliary pointer)",
            "context+0x10": "source_descriptor+0x28 (same auxiliary pointer)",
        },
        "closed_question": (
            "The L3 primary image pointer consumed by Run is not created inside Run. "
            "SetProcess copies it verbatim from source_descriptor+0x2c into context+0x00 "
            "immediately before StartInterpolation calls Run."
        ),
        "remaining_question": (
            "Which upstream function or hardware handoff writes the image buffer pointer into "
            "source_descriptor+0x2c, and what scalar samples are stored at that pointer?"
        ),
        "problems": problems,
        "verified": not problems,
    }
    print(json.dumps(out, indent=2))
    if args.strict and problems:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
