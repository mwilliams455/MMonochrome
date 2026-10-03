#!/usr/bin/env python3
"""Generate exact Leica M Monochrom 1.022 normal-ISO/sRGB Contrast curves.

No Leica firmware bytes are stored in the repository. This tool consumes the
hash-verified decrypted firmware in CI and emits build-local C++/Android assets.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, struct, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from pwad import get_lump

MM_DEC_SHA = "c9e14ee475408802c83774f37b19c85c57663d9840e8e4c2cfe80e14dec9a7ae"
PROCESS_SHA = "dea370ecbf043da03a4af8a7d126d930caf8364f2c806e96a15b2dcb78fcab96"
CURVE20_OFF = 0x7F6FC
CURVE_SIZE = 2048
STANDARD_SHA = "7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752"
LABELS = ["Low", "Medium low", "Standard", "Medium high", "High"]

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mm_decrypted", type=pathlib.Path)
    ap.add_argument("--cpp-out", type=pathlib.Path, required=True)
    ap.add_argument("--asset-out", type=pathlib.Path, required=True)
    ap.add_argument("--java-out", type=pathlib.Path, required=True)
    ap.add_argument("--report-out", type=pathlib.Path, required=True)
    a = ap.parse_args()

    fw = a.mm_decrypted.read_bytes()
    if sha(fw) != MM_DEC_SHA:
        raise SystemExit("M Monochrom decrypted firmware SHA mismatch")
    luts = get_lump(fw, ["LUTS", "PROCESS", "LUTS"]).data
    if sha(luts) != PROCESS_SHA:
        raise SystemExit("M Monochrom PROCESS/LUTS SHA mismatch")

    descriptor = struct.unpack_from("<6I", luts, 0x105CC)
    if descriptor != (60, 2048, 2, 5, 3, 2):
        raise SystemExit(f"unexpected contrast descriptor: {descriptor}")

    curves = [
        luts[CURVE20_OFF + i * CURVE_SIZE : CURVE20_OFF + (i + 1) * CURVE_SIZE]
        for i in range(5)
    ]
    if any(len(x) != CURVE_SIZE for x in curves):
        raise SystemExit("contrast curve bank truncated")
    if sha(curves[2]) != STANDARD_SHA:
        raise SystemExit("Standard curve02 identity mismatch")
    if len({sha(x) for x in curves}) != 5:
        raise SystemExit("five Leica Contrast curves are not unique")

    # Curves are monotone 8-bit transfer tables.
    for i, curve in enumerate(curves):
        if any(curve[j] > curve[j + 1] for j in range(CURVE_SIZE - 1)):
            raise SystemExit(f"curve{i:02d} is not monotone")

    bank = b"".join(curves)
    hashes = [sha(x) for x in curves]

    a.asset_out.parent.mkdir(parents=True, exist_ok=True)
    a.asset_out.write_bytes(bank)

    a.cpp_out.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "// GENERATED from hash-verified Leica M Monochrom 1.022 firmware; do not edit.",
        "#pragma once",
        "#include <cstdint>",
        "static constexpr int MM_MONO_CONTRAST_COUNT = 5;",
        "static constexpr int MM_MONO_CONTRAST_CURVE_SIZE = 2048;",
        "static constexpr uint8_t MM_MONO_CONTRAST_CURVES[5][2048] = {",
    ]
    for i, curve in enumerate(curves):
        lines.append(f"  {{ // {i}: {LABELS[i]}")
        for j in range(0, len(curve), 64):
            lines.append("    " + ",".join(str(v) for v in curve[j:j+64]) + ",")
        lines.append("  },")
    lines.append("};")
    a.cpp_out.write_text("\n".join(lines) + "\n")

    a.java_out.parent.mkdir(parents=True, exist_ok=True)
    hash_literals = ",".join('"' + x + '"' for x in hashes)
    label_literals = ",".join('"' + x + '"' for x in LABELS)
    a.java_out.write_text(
        "package com.particlesdevs.photoncamera.m9.render;\n\n"
        "/** Generated Leica M Monochrom 1.022 Contrast curve metadata. */\n"
        "public final class MonoContrastCurves1A {\n"
        "    public static final int DEFAULT = 2;\n"
        "    public static final String BANK_SHA256 = \"" + sha(bank) + "\";\n"
        "    public static final String[] SHA256 = new String[]{" + hash_literals + "};\n"
        "    public static final String[] LABELS = new String[]{" + label_literals + "};\n"
        "    private MonoContrastCurves1A() {}\n"
        "    public static int clamp(int value) { return value < 0 ? 0 : (value > 4 ? 4 : value); }\n"
        "}\n"
    )

    report = {
        "schema": "mmonochrome.contrast.curves1a.v1",
        "source": "Leica M Monochrom 1.022 PROCESS/LUTS",
        "firmwareDecryptedSha256": MM_DEC_SHA,
        "processLutsSha256": PROCESS_SHA,
        "descriptor": list(descriptor),
        "selector": "normal_ISO_sRGB_curve_index_equals_nContrast",
        "labels": LABELS,
        "curveSha256": hashes,
        "bankSha256": sha(bank),
        "standardCurveIndex": 2,
        "standardCurveSha256": STANDARD_SHA,
        "firmwareBytesCommitted": False,
    }
    a.report_out.parent.mkdir(parents=True, exist_ok=True)
    a.report_out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))

if __name__ == "__main__":
    main()
