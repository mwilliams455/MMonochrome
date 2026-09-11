#!/usr/bin/env python3
"""Verify the M Monochrom 1.022 contrast-curve selector and archive bank.

No Leica firmware bytes are embedded. Point this at a locally decrypted 1.022
PWAD. The verifier checks archive structure, the 60->20 curve collapse, and the
BF547 menu enum records that name the selector dimensions used by BF561.
"""
from __future__ import annotations

import argparse
import hashlib
import struct
from pathlib import Path

from pwad import get_lump

EXPECTED_PROCESS_SHA256 = "dea370ecbf043da03a4af8a7d126d930caf8364f2c806e96a15b2dcb78fcab96"
EXPECTED_BF547_SHA256 = "8f82e5eb08c4933d821ce3df903a14846e300f940fee353514d37cda2c70b621"

META_OFF = 0x105CC
CURVE60_OFF = 0x10714
CURVE20_OFF = 0x7F6FC
CURVE_SIZE = 2048

# BF547 file offsets. Its static RAM image is addressed at file+0x20000 here.
BF547_RAM_DELTA = 0x20000
CONTRAST_TABLE_OFF = 0xBE8CC
COLORSPACE_TABLE_OFF = 0xBF4CC
ISO_TABLE_PULL80_OFF = 0xBFA30
ISO_TABLE_PULL160_OFF = 0xBFA44
MENU_RECORD_STRIDE = 20


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def cstr(data: bytes, offset: int) -> str:
    if not 0 <= offset < len(data):
        raise AssertionError(f"string offset outside BF547: 0x{offset:x}")
    return data[offset:].split(b"\0", 1)[0].decode("ascii")


def menu_record(data: bytes, offset: int) -> tuple[str, int]:
    ptr, value = struct.unpack_from("<II", data, offset)
    if ptr < BF547_RAM_DELTA:
        raise AssertionError(f"unexpected menu string pointer 0x{ptr:x} at 0x{offset:x}")
    return cstr(data, ptr - BF547_RAM_DELTA), value


def verify_process_luts(data: bytes) -> dict:
    got_hash = sha256(data)
    if got_hash != EXPECTED_PROCESS_SHA256:
        raise AssertionError(f"unexpected PROCESS/LUTS sha256: {got_hash}")

    header = struct.unpack_from("<6I", data, META_OFF)
    expected_header = (60, 2048, 2, 5, 3, 2)
    if header != expected_header:
        raise AssertionError(f"unexpected curve descriptor header: {header}")

    bank60 = [
        data[CURVE60_OFF + i * CURVE_SIZE : CURVE60_OFF + (i + 1) * CURVE_SIZE]
        for i in range(60)
    ]
    if any(len(x) != CURVE_SIZE for x in bank60):
        raise AssertionError("60-curve bank truncated")

    # Saturation is represented in the generic 4-D selector, but the tone
    # payload is identical for all three saturation positions.
    for i in range(10):
        if not (bank60[i] == bank60[i + 10] == bank60[i + 20]):
            raise AssertionError(f"normal-ISO saturation replicas differ for curve {i}")
        if not (bank60[i + 30] == bank60[i + 40] == bank60[i + 50]):
            raise AssertionError(f"Pull160 saturation replicas differ for curve {i}")

    canonical = [
        data[CURVE20_OFF + i * CURVE_SIZE : CURVE20_OFF + (i + 1) * CURVE_SIZE]
        for i in range(20)
    ]
    expected_canonical = bank60[0:10] + bank60[30:40]
    if canonical != expected_canonical:
        raise AssertionError("canonical 20-curve bank does not match collapsed 60-bank")

    unique = len({hashlib.sha256(x).digest() for x in bank60})
    if unique != 20:
        raise AssertionError(f"expected 20 unique curves, got {unique}")

    return {
        "sha256": got_hash,
        "header": header,
        "unique_curves": unique,
        "curve60_offset": CURVE60_OFF,
        "curve20_offset": CURVE20_OFF,
    }


def verify_bf547(data: bytes) -> dict:
    got_hash = sha256(data)
    if got_hash != EXPECTED_BF547_SHA256:
        raise AssertionError(f"unexpected BF547 sha256: {got_hash}")

    contrast = [menu_record(data, CONTRAST_TABLE_OFF + i * MENU_RECORD_STRIDE) for i in range(5)]
    expected_contrast = [
        ("Low ", 0),
        ("Medium low ", 1),
        ("Standard", 2),
        ("Medium high ", 3),
        ("High ", 4),
    ]
    if contrast != expected_contrast:
        raise AssertionError(f"unexpected Contrast menu: {contrast!r}")

    colorspace = [menu_record(data, COLORSPACE_TABLE_OFF + i * MENU_RECORD_STRIDE) for i in range(2)]
    if colorspace != [("sRGB", 0), ("Adobe RGB", 1)]:
        raise AssertionError(f"unexpected color-space menu: {colorspace!r}")

    pull80 = menu_record(data, ISO_TABLE_PULL80_OFF)
    pull160 = menu_record(data, ISO_TABLE_PULL160_OFF)
    if pull80 != ("PULL 80", 1):
        raise AssertionError(f"unexpected Pull80 record: {pull80!r}")
    if pull160 != ("PULL 160", 4):
        raise AssertionError(f"unexpected Pull160 record: {pull160!r}")

    return {
        "sha256": got_hash,
        "contrast": contrast,
        "colorspace": colorspace,
        "pull80": pull80,
        "pull160": pull160,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("decrypted_firmware", type=Path)
    args = ap.parse_args()

    root = args.decrypted_firmware.read_bytes()
    process_luts = get_lump(root, ["LUTS", "PROCESS", "LUTS"]).data
    bf547 = get_lump(root, ["BF547"]).data

    p = verify_process_luts(process_luts)
    b = verify_bf547(bf547)

    print(f"PROCESS/LUTS sha256={p['sha256']}")
    print(f"descriptor@0x{META_OFF:x}={list(p['header'])}")
    print(f"60-bank@0x{CURVE60_OFF:x}: unique={p['unique_curves']} saturation replicas=exact")
    print(f"20-bank@0x{CURVE20_OFF:x}: exact collapse of [0..9]+[30..39]")
    print("Contrast menu:", ", ".join(f"{v}={name.strip()}" for name, v in b["contrast"]))
    print("Color space:", ", ".join(f"{v}={name}" for name, v in b["colorspace"]))
    print(f"special ISO record: {b['pull160'][0]} enum={b['pull160'][1]}")
    print()
    print("BF561 selector (from SetStructParameter + SetLutL3):")
    print("  curve60 = nContrast + 5*(nColorSpace + 2*(nSaturation + 3*isPull160))")
    print("  isPull160 = 1 iff nIso == 4")
    print("Because saturation replicas are exact, canonical tone selector collapses to:")
    print("  curve20 = nContrast + 5*nColorSpace + 10*isPull160")
    print("Normal ISO / sRGB / Standard => curve20 = 2")


if __name__ == "__main__":
    main()
