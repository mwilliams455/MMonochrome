#!/usr/bin/env python3
"""Extract focused original M Monochrom UM_Gauss3LUT evidence.

The input is the canonical decrypted M Monochrom 1.022 updater. Output contains
only derived disassembly/symbol metadata, never firmware binary material.
"""
from __future__ import annotations

import argparse
import bisect
import json
import pathlib
import re
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as base  # noqa: E402

TARGETS = ("Process_Sharpness", "UM_Gauss3LUT", "LoadAndModifySharpnessDa")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mm_decrypted", type=pathlib.Path)
    ap.add_argument("--objdump", type=pathlib.Path, required=True)
    ap.add_argument("--outdir", type=pathlib.Path, required=True)
    a = ap.parse_args()

    fw = a.mm_decrypted.read_bytes()
    if base.sha(fw) != base.MM_DEC_SHA:
        raise SystemExit(f"decrypted firmware SHA mismatch: {base.sha(fw)}")

    a.outdir.mkdir(parents=True, exist_ok=True)
    work = a.outdir / "_binary_work"
    work.mkdir(exist_ok=True)

    bf = next((l for l in pwad.parse_pwad(fw) if l.name.upper() == "BF561"), None)
    if bf is None:
        raise SystemExit("outer BF561 missing")
    children = pwad.parse_pwad(bf.data)
    cmap = {l.name.lower(): l for l in children}
    ldr = cmap["bf0"].data
    mp = cmap["bf0.map"].data
    syms = base.parse_map(mp)
    blocks = base.parse_ldr(ldr)
    lines = base.disassemble_blocks(blocks, a.objdump, work)
    addrs = [x[0] for x in lines]

    exact: dict[int, list[str]] = {}
    for s in syms:
        exact.setdefault(int(s["addr"]), []).append(s["name"])
    starts = sorted(exact)

    def resolve(addr: int):
        if addr in exact:
            return {"exact": exact[addr]}
        i = bisect.bisect_right(starts, addr) - 1
        if i < 0:
            return None
        st = starts[i]
        return {"nearest_addr": hex(st), "nearest": exact[st], "offset": addr - st}

    def func_lines(s: dict):
        lo = int(s["addr"])
        hi = lo + int(s["size"])
        i = bisect.bisect_left(addrs, lo)
        j = bisect.bisect_left(addrs, hi)
        return lines[i:j]

    transfer_patterns = [
        re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b", re.I),
        re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\b.*?<([0-9a-fA-F]+)>", re.I),
    ]

    funcs = []
    for s in syms:
        if s["name"] not in TARGETS:
            continue
        fl = func_lines(s)
        transfers = []
        memory_ops = []
        immediates = []
        for addr, line, src, ln in fl:
            target = None
            for pat in transfer_patterns:
                m = pat.search(line)
                if m:
                    target = int(m.group(1), 16)
                    break
            if target is not None:
                transfers.append({
                    "site": hex(addr),
                    "target": hex(target),
                    "target_resolve": resolve(target),
                    "text": line,
                })
            if "[" in line and "]" in line:
                memory_ops.append({"addr": hex(addr), "text": line})
            # Record explicit immediate tokens to make Q-format / limits easy to audit.
            toks = re.findall(r"(?<![A-Za-z0-9_])(?:0x[0-9a-fA-F]+|\b\d+\b)", line)
            if toks:
                immediates.append({"addr": hex(addr), "tokens": toks, "text": line})
        funcs.append({
            "name": s["name"],
            "addr": hex(int(s["addr"])),
            "size": int(s["size"]),
            "disassembly": "\n".join(x[1] for x in fl),
            "transfers": transfers,
            "memory_ops": memory_ops,
            "immediate_lines": immediates,
        })

    gauss = [x for x in funcs if x["name"] == "UM_Gauss3LUT"]
    if len(gauss) < 2:
        raise SystemExit(f"expected mirrored UM_Gauss3LUT symbols, found {len(gauss)}")

    # Compare the two mirrored cores after normalizing absolute addresses. This does
    # not assert semantics, but helps distinguish real algorithm structure from
    # core-specific placement/call destinations.
    def normalize_dis(text: str) -> list[str]:
        out = []
        for line in text.splitlines():
            line = re.sub(r"^\s*[0-9a-fA-F]+:\s*", "", line)
            line = re.sub(r"0x0x[0-9a-fA-F]+|0x[0-9a-fA-F]+", "<ADDR>", line)
            line = re.sub(r"\s+", " ", line).strip()
            out.append(line)
        return out

    norm0 = normalize_dis(gauss[0]["disassembly"])
    norm1 = normalize_dis(gauss[1]["disassembly"])
    mirror_same = norm0 == norm1

    report = {
        "schema": "mmonochrom.sharpness.gauss3lut1a.v1",
        "firmware_decrypted_sha256": base.sha(fw),
        "classification": "focused_disassembly_evidence_no_android_pixel_change",
        "functions": funcs,
        "um_gauss3lut_instances": [
            {"addr": x["addr"], "size": x["size"], "transfer_count": len(x["transfers"])}
            for x in gauss
        ],
        "mirrored_core_normalized_instruction_text_identical": mirror_same,
        "questions": {
            "q1": "Does UM_Gauss3LUT treat the 2050-word source as two 1025-word halves?",
            "q2": "What are the image and LUT argument domains?",
            "q3": "What exact arithmetic is used for Gaussian/detail reconstruction?",
            "q4": "Which bounds, rounding and saturation operations must an Android port reproduce?",
        },
    }
    (a.outdir / "MM_GAUSS3LUT_PROBE.json").write_text(json.dumps(report, indent=2) + "\n")
    with (a.outdir / "MM_GAUSS3LUT_PROBE.txt").open("w") as f:
        for x in funcs:
            f.write(f"\n===== {x['name']} {x['addr']} size={x['size']} =====\n{x['disassembly']}\n")
            f.write("\n-- transfers --\n" + json.dumps(x["transfers"], indent=2) + "\n")
        f.write("\n===== SUMMARY =====\n")
        f.write(json.dumps({
            "um_gauss3lut_instances": report["um_gauss3lut_instances"],
            "mirrored_core_normalized_instruction_text_identical": mirror_same,
        }, indent=2) + "\n")

    for p in work.iterdir():
        p.unlink()
    work.rmdir()
    print(json.dumps({
        "functions": [{"name": x["name"], "addr": x["addr"], "size": x["size"]} for x in funcs],
        "mirror_same": mirror_same,
    }, indent=2))


if __name__ == "__main__":
    main()
