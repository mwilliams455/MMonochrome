#!/usr/bin/env python3
"""Resolve indirect dispatch references to M Monochrom SPI_AppendSettings.

Evidence-only. The direct-caller probe established that SPI_AppendSettings is not
reached by a normal absolute CALL in the disassembled BF0 image. This probe
therefore searches the loaded BF0 LDR image for:

* literal function-pointer references to SPI_AppendSettings,
* nearby pointer-table entries resolved against BF0.map,
* split-immediate constructions of the target address in executable code, and
* SPI/settings symbols that can anchor dispatcher-table interpretation.

It emits derived addresses/symbol names only; no firmware payload bytes.
"""
from __future__ import annotations

import argparse, bisect, json, pathlib, re, struct, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as tr  # noqa: E402

TARGET = 0xFFA03E74
LOW16 = TARGET & 0xFFFF
HIGH16 = (TARGET >> 16) & 0xFFFF


def getbf(fw: bytes):
    bf = next((x for x in pwad.parse_pwad(fw) if x.name.upper() == "BF561"), None)
    if bf is None:
        raise RuntimeError("outer BF561 missing")
    c = {x.name.lower(): x for x in pwad.parse_pwad(bf.data)}
    return tr.parse_map(c["bf0.map"].data), tr.parse_ldr(c["bf0"].data)


def make_resolver(syms):
    arr = sorted((int(s["addr"]), int(s["size"]), s["name"]) for s in syms if int(s["size"]) > 0)
    starts = [x[0] for x in arr]
    exact = {}
    for s in syms:
        exact.setdefault(int(s["addr"]), []).append(s["name"])

    def resolve(addr: int):
        out = {}
        if addr in exact:
            out["exact"] = exact[addr]
        i = bisect.bisect_right(starts, addr) - 1
        if i >= 0:
            st, sz, name = arr[i]
            if st <= addr < st + sz:
                out["owner"] = {"name": name, "addr": hex(st), "size": sz, "offset": addr - st}
        return out or None
    return resolve


def block_for(blocks, addr: int):
    for b in blocks:
        lo = int(b["addr"]); hi = lo + len(b["payload"])
        if lo <= addr < hi:
            return b
    return None


def pointer_xrefs(blocks, resolve):
    needle = struct.pack("<I", TARGET)
    hits = []
    for bi, b in enumerate(blocks):
        data = b["payload"]
        pos = 0
        while True:
            pos = data.find(needle, pos)
            if pos < 0:
                break
            addr = int(b["addr"]) + pos
            # Interpret a +/-64-byte aligned neighborhood as little-endian u32s.
            first = max(0, (pos - 64) & ~3)
            last = min(len(data) - 3, ((pos + 68) + 3) & ~3)
            entries = []
            for off in range(first, last, 4):
                v = struct.unpack_from("<I", data, off)[0]
                r = resolve(v)
                if r is not None or v == TARGET:
                    entries.append({
                        "slot_addr": hex(int(b["addr"]) + off),
                        "relative_words": (off - pos) // 4,
                        "value": hex(v),
                        "resolve": r,
                    })
            hits.append({
                "block_index": bi,
                "xref_addr": hex(addr),
                "xref_resolve": resolve(addr),
                "target": hex(TARGET),
                "nearby_resolved_u32_entries": entries,
            })
            pos += 1
    return hits


def split_immediate_hits(dis, resolve):
    # Blackfin commonly materializes an absolute pointer as Rn.L/Pn.L then
    # Rn.H/Pn.H. Search a small instruction window rather than relying on exact
    # register spelling.
    low = f"0x{LOW16:x}"
    high = f"0x{HIGH16:x}"
    out = []
    texts = [x[1] for x in dis]
    for i, (addr, line, *_rest) in enumerate(dis):
        if low not in line.lower():
            continue
        j0 = max(0, i - 4); j1 = min(len(dis), i + 12)
        ctx = texts[j0:j1]
        if any(high in x.lower() for x in ctx):
            out.append({"addr": hex(addr), "resolve": resolve(addr), "context": ctx})
    return out


def symbol_inventory(syms):
    keep = []
    for s in syms:
        n = s["name"]
        nl = n.lower()
        if ("spi" in nl or "settings" in nl or "processing" in nl or
                "append" in nl or "dispatch" in nl or "message" in nl or
                "command" in nl):
            keep.append({"name": n, "addr": hex(int(s["addr"])), "size": int(s["size"])})
    return sorted(keep, key=lambda x: int(x["addr"], 16))


def xref_neighbor_symbols(hits, resolve):
    # Expand pointer hits into candidate contiguous tables by walking up to 16
    # words in each direction while words keep resolving to mapped symbols.
    out = []
    for h in hits:
        addr = int(h["xref_addr"], 16)
        # This helper is intentionally populated later from the already emitted
        # nearby entries; it labels contiguous runs without re-emitting bytes.
        entries = sorted(h["nearby_resolved_u32_entries"], key=lambda x: int(x["slot_addr"], 16))
        runs = []
        cur = []
        last = None
        for e in entries:
            a = int(e["slot_addr"], 16)
            if last is None or a == last + 4:
                cur.append(e)
            else:
                if cur:
                    runs.append(cur)
                cur = [e]
            last = a
        if cur:
            runs.append(cur)
        out.append({
            "xref_addr": h["xref_addr"],
            "contiguous_resolved_runs": [r for r in runs if any(int(e["value"], 16) == TARGET for e in r)],
        })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mm_decrypted", type=pathlib.Path)
    ap.add_argument("--objdump", type=pathlib.Path, required=True)
    ap.add_argument("--outdir", type=pathlib.Path, required=True)
    a = ap.parse_args()

    fw = a.mm_decrypted.read_bytes()
    if tr.sha(fw) != tr.MM_DEC_SHA:
        raise SystemExit(f"MM decrypted SHA mismatch {tr.sha(fw)}")
    syms, blocks = getbf(fw)
    resolve = make_resolver(syms)
    a.outdir.mkdir(parents=True, exist_ok=True)
    work = a.outdir / "_work"; work.mkdir(exist_ok=True)
    dis = tr.disassemble_blocks(blocks, a.objdump, work)

    ptr = pointer_xrefs(blocks, resolve)
    imm = split_immediate_hits(dis, resolve)
    inv = symbol_inventory(syms)
    runs = xref_neighbor_symbols(ptr, resolve)

    report = {
        "schema": "mmonochrom.spi.dispatch-table1a.v1",
        "firmware_decrypted_sha256": tr.sha(fw),
        "target": {"name": "SPI_AppendSettings", "addr": hex(TARGET), "resolve": resolve(TARGET)},
        "literal_pointer_xrefs": ptr,
        "target_table_runs": runs,
        "split_immediate_code_hits": imm,
        "spi_settings_symbol_inventory": inv,
        "classification": (
            "literal_pointer_xref_is_strong_indirect_dispatch_evidence_when_nearby_words_resolve_to_handler_symbols; "
            "table index semantics remain unassigned until dispatcher consumer is traced"
        ),
        "next_questions": [
            "Does a literal xref sit in a contiguous table of SPI handler function pointers?",
            "Which code loads/indexes that table and from which command byte/word?",
            "What table index corresponds to SPI_AppendSettings?",
            "Can that command path be tied to the normal still-JPEG settings packet?",
        ],
    }
    (a.outdir / "MM_SPI_DISPATCH_TABLE_PROBE.json").write_text(json.dumps(report, indent=2) + "\n")
    with (a.outdir / "MM_SPI_DISPATCH_TABLE_PROBE.txt").open("w") as f:
        f.write("M Monochrom SPI indirect-dispatch/table probe\n\n")
        f.write("TARGET\n" + json.dumps(report["target"], indent=2) + "\n\n")
        f.write("LITERAL POINTER XREFS\n" + json.dumps(ptr, indent=2) + "\n\n")
        f.write("TARGET TABLE RUNS\n" + json.dumps(runs, indent=2) + "\n\n")
        f.write("SPLIT-IMMEDIATE CODE HITS\n" + json.dumps(imm, indent=2) + "\n\n")
        f.write("SPI/SETTINGS SYMBOL INVENTORY\n" + json.dumps(inv, indent=2) + "\n")
    print(json.dumps({
        "literal_pointer_xrefs": len(ptr),
        "target_table_runs": sum(len(x["contiguous_resolved_runs"]) for x in runs),
        "split_immediate_hits": len(imm),
        "inventory_symbols": len(inv),
    }, indent=2))

    for p in work.iterdir():
        p.unlink()
    work.rmdir()


if __name__ == "__main__":
    main()
