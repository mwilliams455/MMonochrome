#!/usr/bin/env python3
"""Trace original M Monochrom process scheduling and Sharp incoming-border state.

Evidence-only probe for the canonical decrypted M Monochrom 1.022 updater.
No firmware binary bytes are emitted. The report contains derived symbol names,
integer/static metadata and disassembly text needed to determine the active
processing mask/order and which stages can contribute to the accumulated border
before Process_Sharpness.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import pathlib
import re
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as base  # noqa: E402

KEY_FUNCS = (
    "Run", "SetProcess", "SetStructParameter", "Process_Blinker",
    "Process_Noise", "Process_Shading", "Process_Sharpness",
    "Process_Contrast", "Process_Y", "LoadAndModifySharpnessDa",
)

PROCESS_RE = re.compile(r"(?:process|processing|setting|current|sharp|noise|contrast|blinker|shading)", re.I)
TRANSFER_RE = re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\s+(?:0x)?([0-9a-fA-F]+)\b", re.I)
BITTST_RE = re.compile(r"BITTST\s*\([^,]+,\s*0x([0-9a-fA-F]+)\)", re.I)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def read_ldr(blocks: list[dict], addr: int, size: int) -> bytes | None:
    """Read an initialized static range from parsed LDR blocks.

    Zero-fill blocks are represented by parse_ldr as payload bytes when present;
    if no single block covers the requested range, return None rather than
    inventing data across discontinuities.
    """
    end = addr + size
    for b in blocks:
        lo = int(b["addr"])
        payload = b["payload"]
        hi = lo + len(payload)
        if lo <= addr and end <= hi:
            rel = addr - lo
            return payload[rel:rel + size]
    return None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mm_decrypted", type=pathlib.Path)
    ap.add_argument("--objdump", type=pathlib.Path, required=True)
    ap.add_argument("--outdir", type=pathlib.Path, required=True)
    a = ap.parse_args()

    fw = a.mm_decrypted.read_bytes()
    if base.sha(fw) != base.MM_DEC_SHA:
        raise SystemExit(f"decrypted firmware SHA mismatch: {base.sha(fw)}")

    bf = next((x for x in pwad.parse_pwad(fw) if x.name.upper() == "BF561"), None)
    if bf is None:
        raise SystemExit("outer BF561 missing")
    cmap = {x.name.lower(): x for x in pwad.parse_pwad(bf.data)}
    if "bf0" not in cmap or "bf0.map" not in cmap:
        raise SystemExit("BF561 bf0/bf0.map missing")

    syms = base.parse_map(cmap["bf0.map"].data)
    blocks = base.parse_ldr(cmap["bf0"].data)
    a.outdir.mkdir(parents=True, exist_ok=True)
    work = a.outdir / "_binary_work"
    work.mkdir(exist_ok=True)
    lines = base.disassemble_blocks(blocks, a.objdump, work)
    addrs = [x[0] for x in lines]

    ordered = sorted((int(s["addr"]), s["name"], int(s["size"])) for s in syms)
    starts = [x[0] for x in ordered]

    def owner(addr: int) -> dict | None:
        i = bisect.bisect_right(starts, addr) - 1
        if i < 0:
            return None
        st, name, size = ordered[i]
        return {"name": name, "start": hex(st), "size": size,
                "offset": addr - st, "inside": addr < st + max(1, size)}

    by_name: dict[str, list[dict]] = {}
    for n in KEY_FUNCS:
        by_name[n] = [
            {"addr": int(s["addr"]), "size": int(s["size"])}
            for s in syms if s["name"] == n
        ]

    funcs: dict[str, list[dict]] = {}
    for n, entries in by_name.items():
        funcs[n] = []
        for ent in entries:
            lo, hi = ent["addr"], ent["addr"] + ent["size"]
            i, j = bisect.bisect_left(addrs, lo), bisect.bisect_left(addrs, hi)
            text = "\n".join(x[1] for x in lines[i:j])
            funcs[n].append({"addr": hex(lo), "size": ent["size"], "disassembly": text})

    target_starts = {n: {x["addr"] for x in xs} for n, xs in by_name.items()}
    callsites = []
    for idx, (addr, text, _src, _ln) in enumerate(lines):
        m = TRANSFER_RE.search(text)
        if not m:
            continue
        target = int(m.group(1), 16)
        hit = [n for n, vals in target_starts.items() if target in vals]
        if not hit:
            continue
        own = owner(addr)
        lo, hi = max(0, idx - 32), min(len(lines), idx + 18)
        callsites.append({
            "site": hex(addr), "owner": own, "target": hex(target),
            "target_names": hit,
            "context": [x[1] for x in lines[lo:hi]],
        })

    # Decode the Run dispatcher mechanically: every BITTST(R5,bit) followed
    # within a short window by a branch into a block that contains one of the
    # named Process_* calls. We retain raw evidence rather than over-naming bits.
    run_dispatch = []
    for f in funcs.get("Run", []):
        rows = f["disassembly"].splitlines()
        for i, row in enumerate(rows):
            bm = BITTST_RE.search(row)
            if not bm or "R5" not in row:
                continue
            bit = int(bm.group(1), 16)
            context = rows[i:i+18]
            called = []
            for rr in context:
                tm = TRANSFER_RE.search(rr)
                if tm:
                    targ = int(tm.group(1), 16)
                    for n, vals in target_starts.items():
                        if targ in vals:
                            called.append(n)
            run_dispatch.append({"bit": bit, "site_line": row, "next_lines": context,
                                 "named_calls_in_window": sorted(set(called))})

    # Candidate process/settings globals and static contents. Emit at most the
    # first 64 initialized bytes as integer words/hex metadata, not firmware blobs.
    globals_out = []
    for s in syms:
        name = s["name"]
        size = int(s["size"])
        addr = int(s["addr"])
        if size <= 0 or not PROCESS_RE.search(name):
            continue
        raw = read_ldr(blocks, addr, min(size, 64))
        item = {"name": name, "addr": hex(addr), "size": size}
        if raw is not None:
            item["initialized_prefix_len"] = len(raw)
            item["initialized_prefix_sha256"] = sha(raw)
            item["u32_prefix"] = [struct.unpack_from("<I", raw, o)[0]
                                  for o in range(0, len(raw) - 3, 4)]
            item["nonzero_prefix_bytes"] = sum(x != 0 for x in raw)
        globals_out.append(item)
    globals_out.sort(key=lambda x: (x["addr"], x["name"]))

    # Highlight SetProcess callsites separately because they reveal where the
    # processing mask/list is selected outside Run.
    setprocess_sites = [x for x in callsites if "SetProcess" in x["target_names"]]
    run_sites = [x for x in callsites if "Run" in x["target_names"]]

    report = {
        "schema": "mmonochrom.process.scheduleprobe1a.v1",
        "firmware_decrypted_sha256": base.sha(fw),
        "classification": "derived_dispatch_and_border_provenance_evidence",
        "symbols": {n: [{"addr": hex(x["addr"]), "size": x["size"]} for x in xs]
                    for n, xs in by_name.items()},
        "run_dispatch_bit_windows": run_dispatch,
        "setprocess_callsites": setprocess_sites,
        "run_callsites": run_sites,
        "all_named_callsites": callsites,
        "process_related_symbols": globals_out,
        "functions": funcs,
        "questions": [
            "Which externally selected processing mask/list corresponds to normal M Monochrom JPEG Standard?",
            "Which enabled stages execute before Process_Sharpness and mutate the accumulated border pointer?",
            "What exact incoming border value reaches Sharp in that normal path?",
        ],
    }
    (a.outdir / "MM_PROCESS_SCHEDULE_PROBE.json").write_text(json.dumps(report, indent=2) + "\n")
    with (a.outdir / "MM_PROCESS_SCHEDULE_PROBE.txt").open("w") as f:
        f.write("M Monochrom process schedule probe\n\n")
        f.write("Run BITTST windows:\n")
        for x in run_dispatch:
            f.write(f"bit {x['bit']}: calls={x['named_calls_in_window']}\n")
            for line in x["next_lines"]:
                f.write("  " + line + "\n")
        f.write("\nSetProcess callsites:\n")
        for x in setprocess_sites:
            f.write(f"site={x['site']} owner={x['owner']}\n")
            for line in x["context"]:
                f.write(line + "\n")
        f.write("\nRun callsites:\n")
        for x in run_sites:
            f.write(f"site={x['site']} owner={x['owner']}\n")
            for line in x["context"]:
                f.write(line + "\n")
        f.write("\nProcess-related symbols:\n")
        for x in globals_out:
            f.write(json.dumps(x, sort_keys=True) + "\n")
        for n in ("SetProcess", "Run", "Process_Blinker", "Process_Noise", "Process_Sharpness"):
            for x in funcs.get(n, []):
                f.write(f"\n===== {n} {x['addr']} size={x['size']} =====\n{x['disassembly']}\n")

    for p in work.iterdir():
        p.unlink()
    work.rmdir()

    print(json.dumps({
        "setprocess_calls": [{"site": x["site"], "owner": x["owner"]} for x in setprocess_sites],
        "run_calls": [{"site": x["site"], "owner": x["owner"]} for x in run_sites],
        "dispatcher": [{"bit": x["bit"], "calls": x["named_calls_in_window"]} for x in run_dispatch],
        "process_related_symbol_names": [x["name"] for x in globals_out],
    }, indent=2))


if __name__ == "__main__":
    main()
