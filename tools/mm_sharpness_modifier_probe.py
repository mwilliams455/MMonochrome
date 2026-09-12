#!/usr/bin/env python3
"""Close original M Monochrom sharpness modifier-code arithmetic.

Evidence-only probe for the canonical decrypted M Monochrom 1.022 firmware.
It reports derived integer metadata from PROCESS/LUTS and BF561 static data; no
firmware binary payload is emitted.
"""
from __future__ import annotations

import argparse
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as trace  # noqa: E402
import mm_lutbank_geometry_probe as geom  # noqa: E402

MATRIX_START = 0x410
MATRIX_ROWS = 5
MATRIX_STRIDE_WORDS = 19
MATRIX_ISO_WORDS = 16
MATRIX_END = MATRIX_START + MATRIX_ROWS * MATRIX_STRIDE_WORDS * 4
BANK_START = 0x58C
CORE_A_DESC_BASE = 0xFEB001E8
CORE_B_DESC_BASE = 0xFEB030B0
MAX_CODE = 12


def u32(b: bytes, off: int) -> int:
    return struct.unpack_from("<I", b, off)[0]


def read_segmented_ldr(blocks: list[dict], addr: int, size: int) -> tuple[bytes, list[dict]]:
    """Reconstruct an address range even when it straddles LDR blocks.

    parse_ldr already materializes zero-fill records as zero byte payloads, so
    this preserves the firmware load image exactly. Later records win only if
    an address overlaps, matching sequential loader semantics.
    """
    mem: dict[int, int] = {}
    provenance: dict[int, int] = {}
    for bi, b in enumerate(blocks):
        lo = int(b["addr"])
        for j, value in enumerate(b["payload"]):
            a = lo + j
            if addr <= a < addr + size:
                mem[a] = value
                provenance[a] = bi
    missing = [a for a in range(addr, addr + size) if a not in mem]
    if missing:
        raise KeyError(f"LDR range has holes: {hex(missing[0])}..{hex(missing[-1])}")
    raw = bytes(mem[a] for a in range(addr, addr + size))
    runs = []
    start = addr
    last_bi = provenance[addr]
    for a in range(addr + 1, addr + size + 1):
        bi = provenance.get(a)
        if a == addr + size or bi != last_bi:
            b = blocks[last_bi]
            runs.append({
                "block_index": last_bi,
                "block_addr": hex(int(b["addr"])),
                "block_size": len(b["payload"]),
                "flags": hex(int(b["flags"])),
                "range_start": hex(start),
                "range_end": hex(a),
                "range_bytes": a - start,
                "zero_fill_flag": bool(int(b["flags"]) & 1),
            })
            start = a
            last_bi = bi
    return raw, runs


def decode_descriptor(desc: int) -> dict:
    """Mirror LoadAndModifySharpnessDa's parity reductions exactly."""
    r2 = int(desc)
    r1 = 2
    if (r2 & 1) == 0:
        r1 = 1
        r2 >>= 1
    r0 = r1 >> 1
    if (r2 & 1) == 0:
        r1 = r0
        r2 >>= 1
    mult = r2
    shift = r1
    return {
        "descriptor": desc,
        "multiplier": mult,
        "right_shift": shift,
        "effective_scale_num": mult,
        "effective_scale_den": 1 << shift,
        "equals_descriptor_over_4": (mult * 4 == desc * (1 << shift)),
        "sample_equation": f"clamp_s16_2048((x * {mult}) >> {shift})",
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("mm_decrypted", type=pathlib.Path)
    ap.add_argument("--outdir", type=pathlib.Path, required=True)
    a = ap.parse_args()

    fw = a.mm_decrypted.read_bytes()
    if trace.sha(fw) != trace.MM_DEC_SHA:
        raise SystemExit(f"decrypted firmware SHA mismatch: {trace.sha(fw)}")

    luts = geom.find_exact(fw, "LUTS/PROCESS/LUTS")
    if MATRIX_END != BANK_START:
        raise SystemExit("matrix geometry constant mismatch")

    matrix = []
    for selector in range(MATRIX_ROWS):
        off = MATRIX_START + selector * MATRIX_STRIDE_WORDS * 4
        vals = [u32(luts, off + 4 * i) for i in range(MATRIX_STRIDE_WORDS)]
        matrix.append({
            "raw_selector": selector,
            "archive_offset": hex(off),
            "iso_codes": vals[:MATRIX_ISO_WORDS],
            "extra_words": vals[MATRIX_ISO_WORDS:],
            "all_codes_in_loader_range_0_to_12": all(0 <= v <= MAX_CODE for v in vals[:MATRIX_ISO_WORDS]),
        })

    iso_count = u32(luts, 0x98)
    iso_values = [u32(luts, 0x9C + 4 * i) for i in range(16)] if iso_count == 16 else []

    bf = next((x for x in pwad.parse_pwad(fw) if x.name.upper() == "BF561"), None)
    if bf is None:
        raise SystemExit("outer BF561 missing")
    children = pwad.parse_pwad(bf.data)
    cmap = {x.name.lower(): x for x in children}
    # Both mirrored LoadAndModifySharpnessDa implementations materialize their
    # descriptor-table addresses in the BF0 load image. The first word of each
    # table is the final two bytes of a zero-fill record and codes 1.. are in the
    # immediately following initialized block, so a segmented reconstruction is
    # required rather than reading one containing block.
    blocks = trace.parse_ldr(cmap["bf0"].data)

    def extract_desc(base_addr: int) -> dict:
        raw, runs = read_segmented_ldr(blocks, base_addr, 2 * (MAX_CODE + 1))
        vals = struct.unpack("<" + "h" * (MAX_CODE + 1), raw)
        return {
            "source_ldr": "bf0",
            "base": hex(base_addr),
            "provenance_runs": runs,
            "entries": [{"code": i, **decode_descriptor(int(v))} for i, v in enumerate(vals)],
        }

    core_a = extract_desc(CORE_A_DESC_BASE)
    core_b = extract_desc(CORE_B_DESC_BASE)
    core_a_vals = [x["descriptor"] for x in core_a["entries"]]
    core_b_vals = [x["descriptor"] for x in core_b["entries"]]

    report = {
        "schema": "mmonochrom.sharpness.modifierprobe1c.v1",
        "firmware_decrypted_sha256": trace.sha(fw),
        "classification": "firmware_derived_integer_modifier_semantics",
        "archive_matrix": {
            "start": hex(MATRIX_START), "end": hex(MATRIX_END),
            "ends_exactly_at_sharpness_bank_start": MATRIX_END == BANK_START,
            "rows": MATRIX_ROWS, "words_per_row": MATRIX_STRIDE_WORDS,
            "physical_iso_words_per_row": MATRIX_ISO_WORDS,
            "iso_count": iso_count, "iso_values": iso_values,
            "selector_rows": matrix,
        },
        "descriptor_tables": {
            "core_a": core_a, "core_b": core_b,
            "mirrored_values_identical": core_a_vals == core_b_vals,
        },
        "closed_equation": {
            "loader_valid_codes": "1..12; <=0 or >12 returns before copy/modify",
            "per_sample": "y = clamp(((x * multiplier(code)) >> shift(code)), -2048, +2048)",
            "descriptor_relation": "multiplier(code) / 2^shift(code) == descriptor(code) / 4",
            "note": "Parity reduction must be retained because integer rounding differs even when rational scale is descriptor/4.",
        },
    }

    if core_a_vals != core_b_vals:
        raise SystemExit(f"mirrored descriptor tables disagree: {core_a_vals} vs {core_b_vals}")
    if core_a_vals[0] != 0:
        raise SystemExit(f"descriptor code 0 expected zero-fill, got {core_a_vals[0]}")

    a.outdir.mkdir(parents=True, exist_ok=True)
    (a.outdir / "MM_SHARPNESS_MODIFIER_PROBE.json").write_text(json.dumps(report, indent=2) + "\n")
    with (a.outdir / "MM_SHARPNESS_MODIFIER_PROBE.txt").open("w") as f:
        f.write("M Monochrom sharpness modifier probe 1C\n\n")
        for row in matrix:
            f.write(f"selector {row['raw_selector']}: ISO codes {row['iso_codes']} extra {row['extra_words']}\n")
        f.write("\nDescriptor table provenance (core A):\n" + json.dumps(core_a["provenance_runs"], indent=2) + "\n")
        f.write("\nMirrored descriptors:\n")
        for x in core_a["entries"]:
            f.write(f"code {x['code']:2d}: desc={x['descriptor']:4d} mult={x['multiplier']:4d} >>{x['right_shift']} scale={x['effective_scale_num']}/{x['effective_scale_den']}\n")
        f.write("\nExact loader sample equation:\n")
        f.write("y = clamp(((x * multiplier(code)) >> shift(code)), -2048, +2048)\n")

    print(json.dumps({
        "matrix_meets_bank": MATRIX_END == BANK_START,
        "iso_count": iso_count,
        "core_mirror_identical": core_a_vals == core_b_vals,
        "descriptors": core_a_vals,
        "core_a_provenance": core_a["provenance_runs"],
        "core_b_provenance": core_b["provenance_runs"],
        "selector_iso_codes": [x["iso_codes"] for x in matrix],
    }, indent=2))


if __name__ == "__main__":
    main()
