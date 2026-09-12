#!/usr/bin/env python3
"""Hash-bound structural verifier for the canonical Monochrom scalar buffers.

This closes a narrower question than the sensor producer itself: which buffer
holds the primary scalar plane inside ``Run`` and how does that plane cross the
16-bit -> 8-bit boundary?

The verifier binds exact canonical function bytes to GNU Blackfin disassembly
and proves only directly visible structure:

* InitL1MemoryProcessing creates the L1 working-buffer pointer quartet at
  context offsets +0x34/+0x38/+0x3c/+0x40 from two L1 pool bases.
* L3L1_Get selector 0 takes the L3 source pointer at context +0x00 and the L1
  destination pointer at context +0x34 and calls the 16-bit window DMA helper.
* Run performs that selector-0 load before the processing-bit dispatch.
* Process_Shading reads/writes the +0x34 primary 16-bit plane and uses +0x38
  and, in its alternate mode, +0x3c as auxiliary planes.
* Run passes +0x34 as Process_Contrast's 16-bit source and +0x3c as its 8-bit
  destination in the canonical mode-0 arrangement.
* Run then passes +0x3c as Process_Y source and +0x34 as Process_Y destination.

This does NOT identify who filled the L3 pointer stored at context +0x00 before
Run. That producer remains the next upstream forensic target.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

EXPECTED = {
    "InitL1MemoryProcessing": (266, "6a2787ed9e1c1ddc22270f73bfb47bcde691ab917a8485298df3b405a80c6092"),
    "L3L1_Get": (196, "fa32b81e5dac1e453497b0583512ef1dc9b0a464a533c76c9546ae499b60eff9"),
    "Process_Shading": (318, "592888ff7254f649495fb0a016f2d32ff3fc7eb06d29a8214e5e12459cb28897"),
    "Process_Contrast": (508, "790659b15a6655d60a750542c69f98eb22c66b300cdb8ad9e4077174aec6a47d"),
    "Process_Y": (292, "f0694943391ab9b5c2cd75119d7bba5ff817fd5bbbaa2c6598a198cc97d7e22a"),
    "Run": (2444, "9a7aef3a340f4617b547accff61ed72ddb8b466cd5d01f0758542e0756fd58f0"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(path: Path) -> list[str]:
    return [line.lower().replace("0x0x", "0x") for line in path.read_text(errors="replace").splitlines()]


def addr_lines(path: Path) -> dict[int, str]:
    out = {}
    for line in normalize(path):
        m = re.match(r"^\s*([0-9a-f]+):", line)
        if m:
            out[int(m.group(1), 16)] = line
    return out


def check_hash(name: str, path: Path, problems: list[str]) -> dict:
    size, expected_hash = EXPECTED[name]
    data = path.read_bytes()
    got_hash = hashlib.sha256(data).hexdigest()
    if len(data) != size:
        problems.append(f"{name}: size {len(data)} != {size}")
    if got_hash != expected_hash:
        problems.append(f"{name}: SHA-256 drift {got_hash}")
    return {"size": len(data), "sha256": got_hash}


def require_contains(lines: list[str], needles: list[str], label: str, problems: list[str]) -> None:
    for needle in needles:
        if not any(needle.lower() in line for line in lines):
            problems.append(f"{label}: missing {needle!r}")


def require_at(lines: dict[int, str], addr: int, needles: list[str], label: str, problems: list[str]) -> None:
    line = lines.get(addr, "")
    for needle in needles:
        if needle.lower() not in line:
            problems.append(f"{label} @0x{addr:08x}: expected {needle!r}; got {line!r}")


def main() -> None:
    ap = argparse.ArgumentParser()
    for stem in ("init", "get", "shading", "contrast", "y", "run"):
        ap.add_argument(f"--{stem}-bin", required=True, type=Path)
        ap.add_argument(f"--{stem}-dis", required=True, type=Path)
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    files = {
        "InitL1MemoryProcessing": (args.init_bin, args.init_dis),
        "L3L1_Get": (args.get_bin, args.get_dis),
        "Process_Shading": (args.shading_bin, args.shading_dis),
        "Process_Contrast": (args.contrast_bin, args.contrast_dis),
        "Process_Y": (args.y_bin, args.y_dis),
        "Run": (args.run_bin, args.run_dis),
    }
    problems: list[str] = []
    anchors = {name: check_hash(name, pair[0], problems) for name, pair in files.items()}

    init = normalize(args.init_dis)
    get = normalize(args.get_dis)
    shading = normalize(args.shading_dis)
    contrast = normalize(args.contrast_dis)
    y = normalize(args.y_dis)
    run = normalize(args.run_dis)
    run_addr = addr_lines(args.run_dis)

    require_contains(init, [
        "r0 = [p2 + 0x14]", "r5 = [p2 + 0x18]",
        "[p2 + 0x34] = r0", "[p2 + 0x38] = r4",
        "[p2 + 0x3c] = r5", "[p2 + 0x40] = r1",
    ], "InitL1MemoryProcessing L1 pointer quartet", problems)

    # Selector mapping in L3L1_Get: selector 0 keeps P2=context; selector 1
    # chooses context+8; other selector chooses context+4. Destination is
    # context+0x34 + selector*4. R0=[P2] and R1=[P0] become the DMA endpoints.
    require_contains(get, [
        "cc = r1 == 0x0", "p5 = r1", "p2 = p0", "p2 += 0x8",
        "p1 += 0x4", "if !cc p2 = p1", "r0 = [p2]",
        "p0 += 0x34", "p0 = p0 + (p5 << 0x2)", "r1 = [p0]",
        "call 0xffa02d72",
    ], "L3L1_Get selector/DMA mapping", problems)

    require_contains(shading, [
        "p3 = [p0 + 0x38]", "p5 = [p0 + 0x34]", "p2 = [p0 + 0x3c]",
        "r0 = w[p5++]", "w[p1++] = r0", "0x3fff",
    ], "Process_Shading primary/auxiliary planes", problems)

    # Contrast mode 0 visibly reads 16-bit samples from P5 and writes bytes to
    # P4. The caller setup below identifies those as +0x34 and +0x3c.
    require_contains(contrast, [
        "r0 = w[p5++] (z)", "r0 >>>= 0x3", "r0 = b[p1] (x)", "b[p4++] = r0",
    ], "Process_Contrast 16-to-8 mode-0 loop", problems)

    # Process_Y's entry binds destination P0=R1 and source P2=R0, while its
    # core traffic is byte-domain.
    require_contains(y, ["p0 = r1", "p2 = r0", "r0 = b[p3++]", "b[p0++] = r0"],
                     "Process_Y source/destination byte-domain binding", problems)

    # Canonical Run: primary selector-0 input load.
    require_at(run_addr, 0xFFA01AB6, ["r0 = rot r4 by 0x0"], "Run primary context arg", problems)
    require_at(run_addr, 0xFFA01AC2, ["r1 = r1 - r1"], "Run selector zero", problems)
    require_at(run_addr, 0xFFA01ACC, ["call", "0xffa122d2"], "Run L3L1_Get", problems)

    # Contrast caller setup: +0x34 primary source -> caller stack +0x14;
    # +0x3c byte-output plane -> caller stack +0x18; then Process_Contrast.
    require_at(run_addr, 0xFFA01C90, ["r3 = [p5 + 0x34]"], "Run Contrast primary", problems)
    require_at(run_addr, 0xFFA01C92, ["[sp + 0x14] = r3"], "Run Contrast primary arg", problems)
    require_at(run_addr, 0xFFA01C94, ["r1 = [p5 + 0x3c]"], "Run Contrast output", problems)
    require_at(run_addr, 0xFFA01C9E, ["[sp + 0x18] = r1"], "Run Contrast output arg", problems)
    require_at(run_addr, 0xFFA01CAE, ["call", "0xffa00b30"], "Run Process_Contrast", problems)

    # Process_Y gets R0=+0x3c source and R1=+0x34 destination.
    require_at(run_addr, 0xFFA01C3A, ["r1 = [p5 + 0x34]"], "Run Process_Y destination", problems)
    require_at(run_addr, 0xFFA01C3C, ["r0 = [p5 + 0x3c]"], "Run Process_Y source", problems)
    require_at(run_addr, 0xFFA01C44, ["call", "0xffa028e8"], "Run Process_Y", problems)

    out = {
        "schema": "mmonochrom.source1e.buffer_lineage.v1",
        "scope": "exact_hash_bound_internal_buffer_lineage_not_upstream_sensor_producer",
        "anchors": anchors,
        "verified_path": [
            "context+0x00 L3 primary source pointer",
            "L3L1_Get(selector=0)",
            "context+0x34 L1 primary 16-bit scalar plane",
            "Process_Shading (when enabled)",
            "Process_Contrast mode 0: uint16 -> curve -> uint8",
            "context+0x3c L1 8-bit output plane",
            "Process_Y: +0x3c source -> +0x34 destination (when enabled)",
        ],
        "auxiliary_planes": {
            "context+0x38": "Process_Shading auxiliary coefficient plane",
            "context+0x3c_before_contrast": "alternate Shading auxiliary plane; later reused as Contrast byte output",
        },
        "closed_question": (
            "The primary scalar plane entering Run is loaded from the L3 pointer stored at context+0x00 "
            "into the L1 pointer at context+0x34. It remains 16-bit through Shading and crosses to 8-bit "
            "inside Contrast mode 0."
        ),
        "remaining_question": (
            "Which pre-Run producer writes the 14-bit scalar image into the L3 buffer whose pointer is stored "
            "at context+0x00?"
        ),
        "problems": problems,
        "verified": not problems,
    }
    print(json.dumps(out, indent=2))
    if args.strict and problems:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
