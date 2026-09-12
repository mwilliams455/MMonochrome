#!/usr/bin/env python3
"""Trace runtime ownership/writers of the M Monochrom sharpness descriptor table.

The sharpness row modifier loader indexes a 16-bit table at 0xfeb001e8 on one
core (mirrored address 0xfeb030b0). The raw LDR image at those RAM addresses is
not sufficient to assign runtime values, so this probe resolves symbols, LDR
block provenance, and all code sites that materialize the table addresses.
Output is derived text/JSON only.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as base  # noqa: E402

TARGETS = {
    "core_a": 0xFEB001E8,
    "core_b": 0xFEB030B0,
}
SPAN = 0x1A


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

    bf = next((x for x in pwad.parse_pwad(fw) if x.name.upper() == "BF561"), None)
    if bf is None:
        raise SystemExit("outer BF561 missing")
    children = pwad.parse_pwad(bf.data)
    cmap = {x.name.lower(): x for x in children}

    all_source_lines = []
    maps = {}
    block_info = {}
    for core in ("bf0", "bf1"):
        if core not in cmap or f"{core}.map" not in cmap:
            continue
        syms = base.parse_map(cmap[f"{core}.map"].data)
        maps[core] = syms
        blocks = base.parse_ldr(cmap[core].data)
        block_info[core] = blocks
        core_work = work / core
        core_work.mkdir(exist_ok=True)
        lines = base.disassemble_blocks(blocks, a.objdump, core_work)
        for row in lines:
            all_source_lines.append((core,) + row)

    all_source_lines.sort(key=lambda x: (x[0], x[1]))

    def symbol_context(syms: list[dict], addr: int) -> dict:
        covering = []
        for s in syms:
            lo = int(s["addr"]); hi = lo + max(1, int(s["size"]))
            if lo <= addr < hi:
                covering.append({"name": s["name"], "addr": hex(lo), "size": int(s["size"]), "offset": addr - lo})
        nearest = sorted(
            ({"distance": abs(int(s["addr"]) - addr), "name": s["name"], "addr": hex(int(s["addr"])), "size": int(s["size"])} for s in syms),
            key=lambda x: x["distance"],
        )[:12]
        return {"covering": covering, "nearest": nearest}

    def containing_blocks(blocks: list[dict], addr: int) -> dict:
        out = []
        for i, b in enumerate(blocks):
            lo = int(b["addr"]); hi = lo + len(b["payload"])
            if lo <= addr < hi or lo < addr + SPAN <= hi:
                rel = max(0, addr - lo)
                raw = b["payload"][rel:rel + SPAN]
                out.append({
                    "block_index": i,
                    "addr": hex(lo),
                    "size": len(b["payload"]),
                    "flags": hex(int(b["flags"])),
                    "target_offset": addr - lo,
                    "target_bytes_all_zero": bool(raw) and all(x == 0 for x in raw),
                })
        nearest = sorted(
            ({"distance": abs(int(b["addr"]) - addr), "block_index": i, "addr": hex(int(b["addr"])), "size": len(b["payload"]), "flags": hex(int(b["flags"]))} for i, b in enumerate(blocks)),
            key=lambda x: x["distance"],
        )[:8]
        return {"containing": out, "nearest": nearest}

    materializations = []
    for core in maps:
        lines = [(addr, text, src, ln) for c, addr, text, src, ln in all_source_lines if c == core]
        for idx, (addr, text, src, ln) in enumerate(lines):
            ml = re.search(r"\b(P[0-5])\.L\s*=\s*0x([0-9a-fA-F]+)", text)
            if not ml:
                continue
            reg = ml.group(1); low = int(ml.group(2), 16) & 0xFFFF
            for j in range(idx + 1, min(idx + 7, len(lines))):
                addr2, text2, src2, ln2 = lines[j]
                mh = re.search(rf"\b{re.escape(reg)}\.H\s*=\s*0x([0-9a-fA-F]+)", text2)
                if not mh:
                    continue
                high = int(mh.group(1), 16) & 0xFFFF
                full = (high << 16) | low
                for label, target in TARGETS.items():
                    if abs(full - target) <= 0x80:
                        lo = max(0, idx - 6); hi = min(len(lines), j + 12)
                        materializations.append({
                            "core_ldr": core,
                            "target_label": label,
                            "target": hex(target),
                            "materialized": hex(full),
                            "delta": full - target,
                            "register": reg,
                            "site": hex(addr),
                            "context": [x[1] for x in lines[lo:hi]],
                        })
                break

    target_report = {}
    for label, addr in TARGETS.items():
        target_report[label] = {
            "address": hex(addr),
            "span": SPAN,
            "maps": {core: symbol_context(syms, addr) for core, syms in maps.items()},
            "ldr_blocks": {core: containing_blocks(blocks, addr) for core, blocks in block_info.items()},
            "materializations": [x for x in materializations if x["target_label"] == label],
        }

    report = {
        "schema": "mmonochrom.sharpness.descriptortrace1a.v1",
        "firmware_decrypted_sha256": base.sha(fw),
        "classification": "runtime_descriptor_table_ownership_trace",
        "targets": target_report,
        "interpretation_guard": [
            "Do not treat LDR bytes at the target RAM address as final runtime descriptor values unless a static-init proof closes that mapping.",
            "The purpose of this probe is to identify the owning symbol and initialization/writer path before decoding modifier codes 1..12.",
        ],
    }
    (a.outdir / "MM_SHARPNESS_DESCRIPTOR_TRACE.json").write_text(json.dumps(report, indent=2) + "\n")
    with (a.outdir / "MM_SHARPNESS_DESCRIPTOR_TRACE.txt").open("w") as f:
        for label, info in target_report.items():
            f.write(f"\n===== {label} {info['address']} =====\n")
            f.write("\nSYMBOL CONTEXT\n" + json.dumps(info["maps"], indent=2) + "\n")
            f.write("\nLDR BLOCK CONTEXT\n" + json.dumps(info["ldr_blocks"], indent=2) + "\n")
            f.write("\nADDRESS MATERIALIZATIONS\n" + json.dumps(info["materializations"], indent=2) + "\n")

    for core_dir in work.iterdir():
        if core_dir.is_dir():
            for p in core_dir.iterdir():
                p.unlink()
            core_dir.rmdir()
    work.rmdir()
    print(json.dumps({
        "targets": {k: {"materializations": len(v["materializations"]), "covering_symbols": {c: len(x["covering"]) for c, x in v["maps"].items()}} for k, v in target_report.items()}
    }, indent=2))


if __name__ == "__main__":
    main()
