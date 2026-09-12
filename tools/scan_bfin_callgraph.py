#!/usr/bin/env python3
"""Build a provenance-oriented direct-call graph for a Blackfin LDR/map pair.

Every fixed-width map record is sliced from the LDR overlay and independently
disassembled with GNU Blackfin objdump. Only explicit direct ``CALL``
instructions are recorded. The result can be filtered to one or more target
addresses to answer questions such as "which bf0 functions directly call Run?"
without inferring from symbol order.

This intentionally does not treat indirect calls/jumps as resolved and does not
claim that a map record is executed on every capture. Duplicate map records are
preserved in source metadata but identical address/size slices are disassembled
only once for efficiency.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List

CALL_RE = re.compile(
    r"^\s*([0-9a-fA-F]+):.*\bCALL\s+(?:0x)+(?:0x)?([0-9a-fA-F]+)\b",
    re.IGNORECASE,
)


def auto_int(value: str) -> int:
    return int(value, 0)


def map_records(path: Path, map_end: int | None = None) -> List[dict]:
    data = path.read_bytes()
    if len(data) % 32:
        raise ValueError(f"{path}: map size {len(data)} is not a multiple of 32")
    if map_end is not None:
        if not 0 <= map_end <= len(data) or map_end % 32:
            raise ValueError(f"invalid --map-end 0x{map_end:x} for map size 0x{len(data):x}")
        data = data[:map_end]
    rows = []
    for off in range(0, len(data), 32):
        rec = data[off : off + 32]
        name = rec[:24].split(b"\0", 1)[0].decode("ascii", "ignore").rstrip("'")
        addr, size = struct.unpack_from("<II", rec, 24)
        if name and size:
            rows.append({"name": name, "addr": addr, "size": size, "map_off": off})
    return rows


def ldr_blocks(path: Path) -> List[dict]:
    data = path.read_bytes()
    off = 4
    blocks = []
    while off + 10 <= len(data):
        addr, count, flags = struct.unpack_from("<IIH", data, off)
        off += 10
        if flags & 1:
            payload = bytes(count)
        else:
            end = off + count
            if end > len(data):
                raise RuntimeError(f"LDR block at 0x{addr:08x} overruns {path}")
            payload = data[off:end]
            off = end
        blocks.append({"addr": addr, "data": payload, "flags": flags})
        if flags & 0x8000:
            break
    if not blocks:
        raise RuntimeError(f"no LDR blocks parsed from {path}")
    return blocks


def read_overlay(blocks: List[dict], addr: int, size: int) -> bytes:
    out = bytearray(size)
    hit = bytearray(size)
    for block in blocks:
        base = block["addr"]
        data = block["data"]
        start = max(addr, base)
        end = min(addr + size, base + len(data))
        if end > start:
            out[start - addr : end - addr] = data[start - base : end - base]
            hit[start - addr : end - addr] = b"\x01" * (end - start)
    if not all(hit):
        missing = next(i for i, value in enumerate(hit) if not value)
        raise RuntimeError(f"overlay gap at 0x{addr + missing:08x} for 0x{addr:08x}+{size}")
    return bytes(out)


def brief(row: dict) -> dict:
    return {
        "name": row["name"],
        "address": f"0x{row['addr']:08x}",
        "size": row["size"],
        "map_offset": f"0x{row['map_off']:x}",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ldr", required=True, type=Path)
    ap.add_argument("--map", required=True, type=Path)
    ap.add_argument("--objdump", required=True, type=Path)
    ap.add_argument("--map-end", type=auto_int)
    ap.add_argument("--target", action="append", type=auto_int, dest="targets")
    ap.add_argument("--include-all-edges", action="store_true")
    args = ap.parse_args()

    rows = map_records(args.map, args.map_end)
    blocks = ldr_blocks(args.ldr)
    by_addr: Dict[int, List[dict]] = {}
    for row in rows:
        by_addr.setdefault(row["addr"], []).append(row)

    wanted = set(args.targets or [])
    edges = []
    problems = []
    seen_slices: set[tuple[int, int]] = set()

    with tempfile.TemporaryDirectory(prefix="bfin-callgraph-") as tmp:
        tmp_root = Path(tmp)
        for row in rows:
            key = (row["addr"], row["size"])
            if key in seen_slices:
                continue
            seen_slices.add(key)
            try:
                code = read_overlay(blocks, row["addr"], row["size"])
            except RuntimeError as exc:
                problems.append({"source": brief(row), "error": str(exc)})
                continue
            bin_path = tmp_root / f"f_{row['addr']:08x}_{row['size']:x}.bin"
            bin_path.write_bytes(code)
            proc = subprocess.run(
                [str(args.objdump), "-D", "-b", "binary", "-m", "bfin",
                 f"--adjust-vma=0x{row['addr']:x}", str(bin_path)],
                check=False,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            if proc.returncode:
                problems.append({
                    "source": brief(row),
                    "error": f"objdump rc={proc.returncode}: {proc.stderr[-500:]}",
                })
                continue
            for line in proc.stdout.splitlines():
                m = CALL_RE.match(line)
                if not m:
                    continue
                site = int(m.group(1), 16)
                target = int(m.group(2), 16)
                if wanted and target not in wanted and not args.include_all_edges:
                    continue
                edges.append({
                    "source_records": [brief(r) for r in by_addr.get(row["addr"], [row])],
                    "call_site": f"0x{site:08x}",
                    "target": f"0x{target:08x}",
                    "target_records": [brief(r) for r in by_addr.get(target, [])],
                    "line": line.strip(),
                })

    target_summary = {}
    for target in sorted(wanted):
        key = f"0x{target:08x}"
        target_summary[key] = [edge for edge in edges if edge["target"] == key]

    out = {
        "schema": "mmonochrom.bfin_callgraph.v1",
        "scope": "explicit_direct_CALL_edges_from_map_slices_only",
        "eligible_map_record_count": len(rows),
        "unique_disassembled_slice_count": len(seen_slices),
        "map_end": f"0x{args.map_end:x}" if args.map_end is not None else None,
        "requested_targets": [f"0x{x:08x}" for x in sorted(wanted)],
        "target_callers": target_summary,
        "edges": edges if args.include_all_edges or not wanted else [],
        "problem_count": len(problems),
        "problems": problems,
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
