#!/usr/bin/env python3
"""Inspect the fixed-width BF561 symbol map embedded in Leica firmware."""
from __future__ import annotations

from pathlib import Path
import argparse
import struct

from pwad import get_lump


def records(data: bytes):
    if len(data) % 32:
        raise ValueError("map is not a multiple of 32 bytes")
    for offset in range(0, len(data), 32):
        rec = data[offset : offset + 32]
        name = rec[:24].split(b"\0", 1)[0].decode("ascii", "ignore").rstrip("'")
        addr, size = struct.unpack_from("<II", rec, 24)
        yield offset, name, addr, size


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("decrypted_firmware", type=Path)
    ap.add_argument("--map", choices=["bf0.map", "bf1.map"], default="bf0.map")
    ap.add_argument("--grep")
    args = ap.parse_args()

    root = args.decrypted_firmware.read_bytes()
    blob = get_lump(root, ["BF561", args.map]).data
    for off, name, addr, size in records(blob):
        if args.grep and args.grep.lower() not in name.lower():
            continue
        print(f"{off:06x} {addr:08x} {size:6d} {name}")


if __name__ == "__main__":
    main()
