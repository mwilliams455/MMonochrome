#!/usr/bin/env python3
"""Hash-bound verifier for the canonical M Monochrom ``Run`` dispatcher.

The purpose is deliberately narrow: prove the order in which ``Run`` tests the
processing-enable bits and returns from each corresponding processing branch to
the next test.  This is stronger than symbol-order inference but still does not
claim that every branch is enabled for every capture or that a named function
fully describes its input producer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

RUN_SHA256 = "9a7aef3a340f4617b547accff61ed72ddb8b466cd5d01f0758542e0756fd58f0"
RUN_ADDR = 0xFFA01790
RUN_SIZE = 2444

EXPECTED = [
    {
        "bit": 1,
        "test": "0xffa01b2c",
        "branch": "0xffa01dfc",
        "call_site": "0xffa01e34",
        "call_target": "0xffa02718",
        "name": "Process_Shading",
        "resume": "0xffa01b38",
    },
    {
        "bit": 2,
        "test": "0xffa01b38",
        "branch": "0xffa01d98",
        "call_site": "0xffa01db4",
        "call_target": "0xffa007c0",
        "name": "Process_Blinker",
        "resume": "0xffa01b3c",
    },
    {
        "bit": 6,
        "test": "0xffa01b44",
        "branch": "0xffa01d22",
        "call_site": "0xffa01d46",
        "call_target": "0xffa015d8",
        "name": "Process_Noise",
        "resume": "0xffa01b4a",
    },
    {
        "bit": 7,
        "test": "0xffa01b4a",
        "branch": "0xffa01cb4",
        "call_site": "0xffa01cd4",
        "call_target": "0xffa0287c",
        "name": "Process_Sharpness",
        "resume": "0xffa01b4e",
    },
    {
        "bit": 8,
        "test": "0xffa01b4e",
        "branch": "0xffa01c8e",
        "call_site": "0xffa01cae",
        "call_target": "0xffa00b30",
        "name": "Process_Contrast",
        "resume": "0xffa01b52",
    },
    {
        "bit": 9,
        "test": "0xffa01b52",
        "branch": "0xffa01c2a",
        "call_site": "0xffa01c44",
        "call_target": "0xffa028e8",
        "name": "Process_Y",
        "resume": "0xffa01b56",
    },
]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(line: str) -> str:
    return line.lower().replace("0x0x", "0x")


def lines_by_addr(path: Path) -> dict[int, str]:
    out: dict[int, str] = {}
    for raw in path.read_text(errors="replace").splitlines():
        m = re.match(r"^\s*([0-9a-fA-F]+):", raw)
        if m:
            out[int(m.group(1), 16)] = normalize(raw)
    return out


def address(value: str) -> int:
    return int(value, 16)


def require_at(lines: dict[int, str], addr: str, needles: list[str], problems: list[str]) -> None:
    line = lines.get(address(addr), "")
    for needle in needles:
        if needle.lower() not in line:
            problems.append(f"{addr}: expected {needle!r}; got {line!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-bin", required=True, type=Path)
    ap.add_argument("--run-dis", required=True, type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    problems: list[str] = []
    data = args.run_bin.read_bytes()
    if len(data) != RUN_SIZE:
        problems.append(f"Run size {len(data)} != {RUN_SIZE}")
    if sha256(args.run_bin) != RUN_SHA256:
        problems.append(f"Run SHA-256 drift: {sha256(args.run_bin)}")

    lines = lines_by_addr(args.run_dis)
    recovered = []
    for item in EXPECTED:
        require_at(lines, item["test"], [f"bittst (r5, 0x{item['bit']:x})"], problems)
        # The conditional jump immediately after each BITTST selects its process branch.
        test_addr = address(item["test"])
        next_lines = [lines.get(test_addr + delta, "") for delta in (2, 4, 6)]
        if not any(item["branch"].lower() in line and "jump" in line for line in next_lines):
            problems.append(f"{item['test']}: branch to {item['branch']} not found immediately after bit test")
        require_at(
            lines,
            item["call_site"],
            ["call", item["call_target"]],
            problems,
        )

        # Search a short post-call window for the explicit return to the next
        # dispatch test or its immediate prelude.
        call_addr = address(item["call_site"])
        resume_found = False
        for addr in sorted(a for a in lines if call_addr < a <= call_addr + 0x100):
            line = lines[addr]
            if item["resume"].lower() in line and "jump" in line:
                resume_found = True
                break
        if not resume_found:
            problems.append(
                f"{item['name']}: no explicit post-call jump to next dispatch point {item['resume']}"
            )

        recovered.append(
            {
                "bit": item["bit"],
                "test_address": item["test"],
                "branch_address": item["branch"],
                "call_site": item["call_site"],
                "call_target": item["call_target"],
                "function": item["name"],
                "resume_address": item["resume"],
            }
        )

    out = {
        "schema": "mmonochrom.source1e.run_dispatch.v1",
        "scope": "hash_bound_Run_direct_control_flow_not_universal_capture_enablement",
        "run_address": f"0x{RUN_ADDR:08x}",
        "run_size": len(data),
        "run_sha256": sha256(args.run_bin),
        "dispatch": recovered,
        "recovered_enabled_stage_order": [x["function"] for x in recovered],
        "scalar_domain_implication": (
            "Within canonical Monochrom Run, an enabled Process_Shading stage is dispatched before "
            "Process_Contrast, and Process_Y is dispatched after Process_Contrast. Combined with the "
            "hash-bound function semantics, this places the 16-bit shading path upstream of the "
            "16-bit-to-8-bit contrast transition and the 8-bit Y block-packing path downstream."
        ),
        "problems": problems,
        "verified": not problems,
    }
    print(json.dumps(out, indent=2))
    if args.strict and problems:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
