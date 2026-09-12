#!/usr/bin/env python3
"""Synthetic regression tests for SOURCE1E forensic helpers.

No Leica firmware bytes are required. These tests exercise the infrastructure
that must be trustworthy *before* real firmware assets are fed into it:

- fixed-width 32-byte BF561 map record parsing;
- the legacy 299/300/299 name-set fingerprint helper;
- LDR block parsing and overlay byte extraction;
- exact function slicing / hashing primitives used by SOURCE1E.

The tests intentionally do not assert any Leica photographic semantics.
"""
from __future__ import annotations

import hashlib
import struct
import tempfile
import unittest
from pathlib import Path

import extract_source1e_targets as extract
import trace_scalar_topology as topology


def pack_record(name: str, addr: int, size: int) -> bytes:
    encoded = name.encode("ascii")
    if len(encoded) > 24:
        raise ValueError("synthetic symbol name too long")
    return encoded.ljust(24, b"\0") + struct.pack("<II", addr, size)


def pack_ldr_block(addr: int, payload: bytes, flags: int = 0x8000) -> bytes:
    # The project LDR reader expects a four-byte global header followed by
    # repeated <addr,count,flags> records and inline payload bytes when bit0 is
    # clear. 0x8000 marks the final block.
    return b"TEST" + struct.pack("<IIH", addr, len(payload), flags) + payload


class TopologyHelpersTest(unittest.TestCase):
    def test_fixed_record_parser_preserves_exact_fields(self) -> None:
        blob = b"".join(
            [
                pack_record("Process_Y", 0xFFA01000, 0x120),
                pack_record("L3L1_Put8BitY", 0xFEB11000, 0x80),
            ]
        )
        rows = topology.records_bytes(blob, "synthetic")
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "Process_Y")
        self.assertEqual(rows[0]["addr"], 0xFFA01000)
        self.assertEqual(rows[0]["size"], 0x120)
        self.assertEqual(rows[0]["map_off"], 0)
        self.assertEqual(rows[1]["map_off"], 32)

    def test_fixed_record_parser_rejects_non_multiple_of_32(self) -> None:
        with self.assertRaises(ValueError):
            topology.records_bytes(b"bad", "synthetic")

    def test_legacy_count_fingerprint_is_exact_not_fuzzy(self) -> None:
        common = {f"S{i:03d}" for i in range(299)}
        mono_names = set(common)
        m9_names = set(common) | {"M9_ONLY"}
        result = topology.name_comparison(mono_names, m9_names)
        self.assertEqual(result["counts"], topology.LEGACY_SYMBOL_COUNTS)
        self.assertTrue(result["matches_legacy_299_300_299"])

        mono_names.add("EXTRA_MONO")
        changed = topology.name_comparison(mono_names, m9_names)
        self.assertFalse(changed["matches_legacy_299_300_299"])

    def test_disputed_membership_is_reported_separately_from_counts(self) -> None:
        mono_names = {"A", "Process_FPGA_Y"}
        m9_names = {"A", "Process_FPGA_Y", "Process_WB"}
        result = topology.name_comparison(mono_names, m9_names)
        self.assertIn("Process_FPGA_Y", result["disputed_common"])
        self.assertIn("Process_WB", result["disputed_m9_present"])
        self.assertNotIn("Process_WB", result["disputed_mono_present"])


class ExtractorHelpersTest(unittest.TestCase):
    def test_ldr_block_round_trip_and_function_slice_hash(self) -> None:
        payload = bytes(range(64))
        addr = 0xFFA01000
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            ldr_path = root / "bf0.bin"
            map_path = root / "bf0.map"
            ldr_path.write_bytes(pack_ldr_block(addr, payload))
            map_path.write_bytes(pack_record("Process_Y", addr + 8, 24))

            blocks = extract.ldr_blocks(ldr_path)
            self.assertEqual(len(blocks), 1)
            self.assertEqual(blocks[0]["addr"], addr)
            self.assertEqual(blocks[0]["data"], payload)

            rows = extract.map_records(map_path)
            index = extract.index_by_name(rows)
            rec, code = extract.extract_one(index, blocks, "Process_Y")
            self.assertEqual(rec["addr"], addr + 8)
            self.assertEqual(code, payload[8:32])
            self.assertEqual(
                extract.sha256(code),
                hashlib.sha256(payload[8:32]).hexdigest(),
            )

    def test_read_overlay_can_join_adjacent_blocks(self) -> None:
        blocks = [
            {"addr": 0x1000, "data": b"abcd", "flags": 0},
            {"addr": 0x1004, "data": b"efgh", "flags": 0x8000},
        ]
        self.assertEqual(extract.read_overlay(blocks, 0x1002, 4), b"cdef")

    def test_read_overlay_fails_on_hole(self) -> None:
        blocks = [
            {"addr": 0x1000, "data": b"ab", "flags": 0},
            {"addr": 0x1004, "data": b"ef", "flags": 0x8000},
        ]
        with self.assertRaises(RuntimeError):
            extract.read_overlay(blocks, 0x1000, 6)


if __name__ == "__main__":
    unittest.main(verbosity=2)
