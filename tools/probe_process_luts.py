#!/usr/bin/env python3
"""Conservative structural probe for M Monochrom PROCESS/LUTS.

Reports structure without assigning photographic semantics until consumers are traced.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib
import struct
from collections import defaultdict

from pwad import get_lump


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mm_decrypted", type=Path)
    args = ap.parse_args()

    root = args.mm_decrypted.read_bytes()
    data = get_lump(root, ["LUTS", "PROCESS", "LUTS"]).data
    print(f"process_luts_size={len(data)}")
    print(f"process_luts_sha256={sha(data)}")

    version = struct.unpack_from("<I", data, 0)[0]
    offsets = list(struct.unpack_from("<18I", data, 4))
    print(f"header_word0={version}")
    print("header_offsets=" + ",".join(str(x) for x in offsets))

    iso_off = 0x98
    iso_count = struct.unpack_from("<I", data, iso_off)[0]
    iso = list(struct.unpack_from(f"<{iso_count}I", data, iso_off + 4))
    print(f"iso_count={iso_count}")
    print("iso=" + ",".join(map(str, iso)))

    pair_start, pair_end, pair_stride = 0x58C, 0x105CC, 2050
    pair_count = (pair_end - pair_start) // pair_stride
    print(f"iso_pair_region_count={pair_count}")
    print(f"iso_pair_region_stride={pair_stride}")

    curve_start, curve_count, curve_len = 0x10714, 60, 2048
    curves = [
        data[curve_start + i * curve_len : curve_start + (i + 1) * curve_len]
        for i in range(curve_count)
    ]
    groups: dict[str, list[int]] = defaultdict(list)
    for i, curve in enumerate(curves):
        groups[sha(curve)].append(i)
    print(f"curve_bank_count={curve_count}")
    print(f"curve_length={curve_len}")
    print(f"curve_unique={len(groups)}")
    for digest, indexes in groups.items():
        print(f"curve_repeat={','.join(map(str, indexes))}:{digest}")

    tail_start = 0x7F6FC
    tail = [
        data[tail_start + i * curve_len : tail_start + (i + 1) * curve_len]
        for i in range(20)
    ]
    unique_curve_bytes = set(curves)
    print(f"tail_curve_count={len(tail)}")
    print(f"tail_all_present_in_60_curve_bank={all(x in unique_curve_bytes for x in tail)}")


if __name__ == "__main__":
    main()
