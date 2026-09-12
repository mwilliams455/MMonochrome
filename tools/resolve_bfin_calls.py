#!/usr/bin/env python3
"""Resolve direct Blackfin CALL targets in GNU objdump text against a bf0.map.

This is a provenance helper, not a control-flow decompiler. It records only
explicit direct CALL instructions emitted by GNU objdump and resolves exact
addresses to fixed-width map records when possible. Indirect calls, jumps and
runtime processing-list semantics remain outside this tool's claim.

``--map-end`` optionally restricts eligible records to a byte prefix of the map.
This is required for canonical M9 bf0.map because its active M9 record prefix is
followed by an exact embedded M Monochrom map. Without the boundary, archival
Monochrom records can be mistaken for active M9 call targets.
"""
from __future__ import annotations

import argparse
import json
import re
import struct
from pathlib import Path
from typing import Dict, List

# GNU's Blackfin disassembler currently renders direct absolute calls as e.g.
# ``CALL 0x0xffa13990`` (a duplicated 0x prefix). Accept both that spelling
# and the conventional ``CALL 0xffa13990`` rather than silently reporting zero
# calls.
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
        if map_end < 0 or map_end > len(data):
            raise ValueError(f"--map-end 0x{map_end:x} is outside map size 0x{len(data):x}")
        if map_end % 32:
            raise ValueError(f"--map-end 0x{map_end:x} is not on a 32-byte record boundary")
        data = data[:map_end]
    out = []
    for off in range(0, len(data), 32):
        rec = data[off : off + 32]
        name = rec[:24].split(b"\0", 1)[0].decode("ascii", "ignore").rstrip("'")
        addr, size = struct.unpack_from("<II", rec, 24)
        if name:
            out.append({"name": name, "addr": addr, "size": size, "map_off": off})
    return out


def exact_address_index(rows: List[dict]) -> Dict[int, List[dict]]:
    out: Dict[int, List[dict]] = {}
    for row in rows:
        out.setdefault(row["addr"], []).append(row)
    return out


def containing(rows: List[dict], addr: int) -> List[dict]:
    return [r for r in rows if r["addr"] <= addr < r["addr"] + r["size"]]


def summarize_record(r: dict) -> dict:
    return {
        "name": r["name"],
        "address": f"0x{r['addr']:08x}",
        "size": r["size"],
        "map_offset": f"0x{r['map_off']:x}",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--map", required=True, type=Path)
    ap.add_argument(
        "--map-end",
        type=auto_int,
        help="optional exclusive byte offset limiting eligible map records (accepts 0x...)",
    )
    ap.add_argument("--disassembly", required=True, type=Path, action="append")
    args = ap.parse_args()

    rows = map_records(args.map, args.map_end)
    exact = exact_address_index(rows)
    output = {
        "schema": "mmonochrom.bfin_direct_calls.v3",
        "scope": "explicit_direct_CALL_only_no_indirect_or_runtime_order_claim",
        "map": str(args.map),
        "map_end": f"0x{args.map_end:x}" if args.map_end is not None else None,
        "eligible_map_record_count": len(rows),
        "files": {},
    }

    for path in args.disassembly:
        calls = []
        for line in path.read_text(errors="replace").splitlines():
            m = CALL_RE.match(line)
            if not m:
                continue
            site = int(m.group(1), 16)
            target = int(m.group(2), 16)
            exact_hits = exact.get(target, [])
            calls.append(
                {
                    "site": f"0x{site:08x}",
                    "target": f"0x{target:08x}",
                    "exact_map_records": [summarize_record(r) for r in exact_hits],
                    "containing_map_records": [
                        summarize_record(r) for r in containing(rows, target)
                    ] if not exact_hits else [],
                    "line": line.strip(),
                }
            )
        output["files"][path.name] = {
            "direct_call_count": len(calls),
            "calls": calls,
        }

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
