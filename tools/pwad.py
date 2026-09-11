#!/usr/bin/env python3
"""Minimal Leica/Doom-style PWAD reader used by the M9/M Monochrom firmware."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import struct
from typing import Iterable


@dataclass(frozen=True)
class Lump:
    name: str
    offset: int
    size: int
    data: bytes

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.data).hexdigest()

    @property
    def is_pwad(self) -> bool:
        return self.data[:4] == b"PWAD"


def parse_pwad(data: bytes) -> list[Lump]:
    if len(data) < 12 or data[:4] != b"PWAD":
        raise ValueError("not a PWAD payload")
    count, directory_offset = struct.unpack_from("<II", data, 4)
    if directory_offset + count * 16 > len(data):
        raise ValueError("PWAD directory exceeds payload")

    lumps: list[Lump] = []
    for i in range(count):
        offset, size, raw_name = struct.unpack_from(
            "<II8s", data, directory_offset + i * 16
        )
        if offset + size > len(data):
            raise ValueError(f"lump {i} exceeds payload")
        name = raw_name.split(b"\0", 1)[0].decode("ascii", "replace")
        lumps.append(Lump(name, offset, size, data[offset : offset + size]))
    return lumps


def get_lump(data: bytes, path: Iterable[str]) -> Lump:
    current = data
    found: Lump | None = None
    path = list(path)
    for part in path:
        found = next((x for x in parse_pwad(current) if x.name == part), None)
        if found is None:
            raise KeyError("/".join(path))
        current = found.data
    assert found is not None
    return found


def walk_pwad(data: bytes, prefix: str = ""):
    for lump in parse_pwad(data):
        path = f"{prefix}/{lump.name}" if prefix else lump.name
        yield path, lump
        if lump.is_pwad:
            yield from walk_pwad(lump.data, path)


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument("firmware", type=Path)
    args = ap.parse_args()

    data = args.firmware.read_bytes()
    for path, lump in walk_pwad(data):
        print(
            f"{path:40s} offset=0x{lump.offset:08x} size={lump.size:8d} "
            f"sha256={lump.sha256}"
        )


if __name__ == "__main__":
    main()
