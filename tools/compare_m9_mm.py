#!/usr/bin/env python3
"""Cross-map decrypted Leica M9 1.216 and M Monochrom 1.022 PWADs."""
from __future__ import annotations

from pathlib import Path
import argparse
import struct

from pwad import get_lump, walk_pwad


def map_records(data: bytes):
    if len(data) % 32:
        raise ValueError("unexpected map size")
    rows = []
    for offset in range(0, len(data), 32):
        rec = data[offset : offset + 32]
        name = rec[:24].split(b"\0", 1)[0].decode("ascii", "ignore").rstrip("'")
        addr, size = struct.unpack_from("<II", rec, 24)
        rows.append((name, addr, size, rec))
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("m9_decrypted", type=Path)
    ap.add_argument("mm_decrypted", type=Path)
    args = ap.parse_args()

    m9 = args.m9_decrypted.read_bytes()
    mm = args.mm_decrypted.read_bytes()

    m9_top = {path: lump for path, lump in walk_pwad(m9)}
    mm_top = {path: lump for path, lump in walk_pwad(mm)}

    print("path,size_m9,size_mm,same_sha256")
    for path in sorted(set(m9_top) | set(mm_top)):
        a, b = m9_top.get(path), mm_top.get(path)
        print(
            f"{path},{a.size if a else ''},{b.size if b else ''},"
            f"{bool(a and b and a.sha256 == b.sha256)}"
        )

    m9_bf0_map = get_lump(m9, ["BF561", "bf0.map"]).data
    mm_bf0_map = get_lump(mm, ["BF561", "bf0.map"]).data
    suffix_at = m9_bf0_map.find(mm_bf0_map)
    print(f"bf0_map_mm_exact_substring_offset={suffix_at}")

    a = map_records(m9_bf0_map)
    b = map_records(mm_bf0_map)
    aset = {(n, addr, size) for n, addr, size, _ in a}
    bset = {(n, addr, size) for n, addr, size, _ in b}
    print(f"bf0_m9_records={len(a)}")
    print(f"bf0_mm_records={len(b)}")
    print(f"bf0_mm_records_present_exactly_in_m9={len(aset & bset)}")
    print("bf0_m9_only_symbols=" + ",".join(sorted({x[0] for x in a} - {x[0] for x in b})))


if __name__ == "__main__":
    main()
