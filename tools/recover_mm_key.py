#!/usr/bin/env python3
"""Recover the M Monochrom 1.022 XOR stream from an M9 decrypted reference.

The method deliberately does not require the historical M9 key file. It uses a
key-independent invariant for a repeating XOR stream and the byte-identical BODY
component shared by M9 1.216 and M Monochrom 1.022.
"""
from __future__ import annotations

from pathlib import Path
import argparse
import hashlib

from pwad import get_lump, parse_pwad

PERIOD = 1021
EXPECTED_KEY_SHA256 = "595c49ebabdaafcde7cc6cbd6aa7a37092d7c2ad4ca47d0d8bc57a04a5bed3a1"
EXPECTED_MM_SHA256 = "53330385edfbfb9beeffa06645bffa2789e27dda614869107698919464f80ad8"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def period_xor_signature(data: bytes, period: int, length: int) -> bytes:
    if len(data) < period + length:
        raise ValueError("not enough data for signature")
    return bytes(data[i] ^ data[i + period] for i in range(length))


def recover_key(cipher: bytes, known_plain: bytes, period: int = PERIOD) -> tuple[bytes, int]:
    # C[o+i] ^ C[o+i+period] = P[i] ^ P[i+period], so the repeating key cancels.
    sig_len = 128
    signature = period_xor_signature(known_plain, period, sig_len)
    cipher_delta = bytes(cipher[i] ^ cipher[i + period] for i in range(len(cipher) - period))

    hits: list[int] = []
    start = 0
    while True:
        hit = cipher_delta.find(signature, start)
        if hit < 0:
            break
        hits.append(hit)
        start = hit + 1
    if len(hits) != 1:
        raise RuntimeError(f"expected one BODY match, got {len(hits)}: {hits[:10]}")

    body_offset = hits[0]
    key = bytearray(period)
    for i in range(period):
        key[(body_offset + i) % period] = cipher[body_offset + i] ^ known_plain[i]
    return bytes(key), body_offset


def decrypt(cipher: bytes, key: bytes) -> bytes:
    return bytes(value ^ key[i % len(key)] for i, value in enumerate(cipher))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mm_upm", type=Path, help="Leica M Monochrom Mm-1_022.upm")
    ap.add_argument("m9_decrypted", type=Path, help="decrypted Leica M9 1.216 PWAD")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--key-out", type=Path)
    args = ap.parse_args()

    cipher = args.mm_upm.read_bytes()
    m9 = args.m9_decrypted.read_bytes()
    m9_body = get_lump(m9, ["BODY"]).data

    key, body_offset = recover_key(cipher, m9_body)
    plain = decrypt(cipher, key)

    lumps = parse_pwad(plain)
    mm_body = next(x for x in lumps if x.name == "BODY")
    if mm_body.data != m9_body:
        raise RuntimeError("decrypted Monochrom BODY does not match M9 BODY")

    print(f"input_sha256={sha256(cipher)}")
    print(f"body_offset=0x{body_offset:x}")
    print(f"key_sha256={sha256(key)}")
    print(f"decrypted_sha256={sha256(plain)}")
    print("lumps=" + ",".join(x.name for x in lumps))

    if sha256(cipher) == EXPECTED_MM_SHA256 and sha256(key) != EXPECTED_KEY_SHA256:
        raise RuntimeError("canonical 1.022 firmware produced an unexpected key")

    if args.out:
        args.out.write_bytes(plain)
    if args.key_out:
        args.key_out.write_bytes(key)


if __name__ == "__main__":
    main()
