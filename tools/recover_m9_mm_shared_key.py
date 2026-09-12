#!/usr/bin/env python3
"""Recover and verify the shared Leica M9 / M Monochrom XOR stream.

The canonical M9 1.216 and original M Monochrom 1.022 updater ciphertexts use
the same 1021-byte repeating XOR stream and contain the same BODY plaintext at
different offsets.  Comparing those ciphertext regions yields a cycle of XOR
equations over every key byte.  The only remaining one-byte ambiguity is fixed
by requiring the decrypted outer M9 header to be ``PWAD``.

No firmware bytes or key bytes are stored in this repository.  The script is
intended for CI or local use with independently downloaded updater files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path

PERIOD = 1021
M9_BODY_OFFSET = 0x00451050
MM_BODY_OFFSET = 0x00119350
BODY_SIZE = 143_418

EXPECTED_M9_RAW_SHA256 = "c3d30d7124abe6a3674cf2095719c178454b8773b1454cb70cf54ae468024da4"
EXPECTED_MM_RAW_SHA256 = "53330385edfbfb9beeffa06645bffa2789e27dda614869107698919464f80ad8"
EXPECTED_KEY_SHA256 = "595c49ebabdaafcde7cc6cbd6aa7a37092d7c2ad4ca47d0d8bc57a04a5bed3a1"
EXPECTED_M9_DECRYPTED_SHA256 = "4f962bb7799ad9a6745ab36c2a3ba59757bfcbd205f50472ddf1b904a5756d20"
EXPECTED_MM_DECRYPTED_SHA256 = "c9e14ee475408802c83774f37b19c85c57663d9840e8e4c2cfe80e14dec9a7ae"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def decrypt(cipher: bytes, key: bytes) -> bytes:
    return bytes(value ^ key[i % len(key)] for i, value in enumerate(cipher))


def build_edges(m9: bytes, mm: bytes) -> tuple[list[int], int]:
    if len(m9) < M9_BODY_OFFSET + PERIOD:
        raise ValueError("M9 ciphertext is too short for BODY equations")
    if len(mm) < MM_BODY_OFFSET + PERIOD:
        raise ValueError("Monochrom ciphertext is too short for BODY equations")

    delta = (MM_BODY_OFFSET - M9_BODY_OFFSET) % PERIOD
    if math.gcd(delta, PERIOD) != 1:
        raise RuntimeError(f"BODY offset delta {delta} does not span key period")

    edge: list[int | None] = [None] * PERIOD
    for i in range(PERIOD):
        a = (M9_BODY_OFFSET + i) % PERIOD
        edge[a] = m9[M9_BODY_OFFSET + i] ^ mm[MM_BODY_OFFSET + i]
    if any(x is None for x in edge):
        raise RuntimeError("incomplete key equation graph")
    return [int(x) for x in edge], delta


def key_from_seed(edge: list[int], delta: int, seed: int) -> bytes:
    key: list[int | None] = [None] * PERIOD
    key[0] = seed
    cur = 0
    for _ in range(PERIOD - 1):
        nxt = (cur + delta) % PERIOD
        if key[nxt] is not None:
            raise RuntimeError("key equation cycle closed early")
        key[nxt] = int(key[cur]) ^ edge[cur]
        cur = nxt
    if (cur + delta) % PERIOD != 0:
        raise RuntimeError("key equation graph did not form one cycle")
    if (int(key[cur]) ^ edge[cur]) != seed:
        raise RuntimeError("inconsistent shared-BODY equations")
    return bytes(int(x) for x in key)


def recover_key(m9: bytes, mm: bytes) -> tuple[bytes, int, int]:
    edge, delta = build_edges(m9, mm)
    candidates: list[tuple[int, bytes]] = []
    for seed in range(256):
        key = key_from_seed(edge, delta, seed)
        if bytes(m9[i] ^ key[i % PERIOD] for i in range(4)) == b"PWAD":
            candidates.append((seed, key))
    if len(candidates) != 1:
        raise RuntimeError(f"expected one PWAD-compatible seed, got {len(candidates)}")
    seed, key = candidates[0]
    return key, delta, seed


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("m9_upd", type=Path)
    ap.add_argument("mm_upm", type=Path)
    ap.add_argument("--m9-out", type=Path)
    ap.add_argument("--mm-out", type=Path)
    ap.add_argument("--meta-out", type=Path)
    args = ap.parse_args()

    m9 = args.m9_upd.read_bytes()
    mm = args.mm_upm.read_bytes()
    raw_hashes = {"m9": sha256(m9), "mm": sha256(mm)}
    if raw_hashes["m9"] != EXPECTED_M9_RAW_SHA256:
        raise SystemExit(f"M9 raw SHA mismatch: {raw_hashes['m9']}")
    if raw_hashes["mm"] != EXPECTED_MM_RAW_SHA256:
        raise SystemExit(f"Monochrom raw SHA mismatch: {raw_hashes['mm']}")

    key, delta, seed = recover_key(m9, mm)
    if sha256(key) != EXPECTED_KEY_SHA256:
        raise SystemExit(f"recovered key SHA mismatch: {sha256(key)}")

    m9_plain = decrypt(m9, key)
    mm_plain = decrypt(mm, key)
    if m9_plain[:4] != b"PWAD" or mm_plain[:4] != b"PWAD":
        raise SystemExit("decryption did not produce PWAD headers")
    if sha256(m9_plain) != EXPECTED_M9_DECRYPTED_SHA256:
        raise SystemExit(f"M9 decrypted SHA mismatch: {sha256(m9_plain)}")
    if sha256(mm_plain) != EXPECTED_MM_DECRYPTED_SHA256:
        raise SystemExit(f"Monochrom decrypted SHA mismatch: {sha256(mm_plain)}")

    m9_body = m9_plain[M9_BODY_OFFSET : M9_BODY_OFFSET + BODY_SIZE]
    mm_body = mm_plain[MM_BODY_OFFSET : MM_BODY_OFFSET + BODY_SIZE]
    if len(m9_body) != BODY_SIZE or m9_body != mm_body:
        raise SystemExit("decrypted shared BODY verification failed")

    meta = {
        "schema": "mmonochrom.sharedbody_key_recovery.v1",
        "period": PERIOD,
        "offset_delta_mod_period": delta,
        "gcd_delta_period": math.gcd(delta, PERIOD),
        "pw_ad_seed": seed,
        "m9_raw_sha256": raw_hashes["m9"],
        "mm_raw_sha256": raw_hashes["mm"],
        "key_sha256": sha256(key),
        "m9_decrypted_sha256": sha256(m9_plain),
        "mm_decrypted_sha256": sha256(mm_plain),
        "shared_body_exact": True,
    }
    print(json.dumps(meta, indent=2))
    if args.m9_out:
        args.m9_out.write_bytes(m9_plain)
    if args.mm_out:
        args.mm_out.write_bytes(mm_plain)
    if args.meta_out:
        args.meta_out.write_text(json.dumps(meta, indent=2) + "\n")


if __name__ == "__main__":
    main()
