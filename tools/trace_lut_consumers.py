#!/usr/bin/env python3
"""Trace two high-value M Monochrom BF561 LUT consumer helpers.

This is deliberately a *small verified decoder*, not a general Blackfin
Disassembler.  It decodes only the opcodes used by Leica M Monochrom 1.022
`SetLutL3` and `LoadISODataL1`, then emits symbolic semantics that can be
checked against the firmware on every run.

No Leica firmware bytes are distributed with this repository.  Point the tool
at locally extracted BF561 `bf0` / `bf0.map` files.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path
from typing import Dict, List, Tuple


def map_records(path: Path) -> List[dict]:
    b = path.read_bytes()
    out = []
    for off in range(0, len(b) - 31, 32):
        rec = b[off : off + 32]
        name = rec[:24].split(b"\0", 1)[0].decode("ascii", "ignore").rstrip("'")
        if not name:
            continue
        addr, size = struct.unpack_from("<II", rec, 24)
        out.append({"name": name, "addr": addr, "size": size, "map_off": off})
    return out


def ldr_blocks(path: Path) -> List[dict]:
    b = path.read_bytes()
    off = 4
    out = []
    while off + 10 <= len(b):
        addr, count, flags = struct.unpack_from("<IIH", b, off)
        off += 10
        if flags & 1:
            data = bytes(count)
        else:
            data = b[off : off + count]
            off += count
        out.append({"addr": addr, "data": data, "flags": flags})
        if flags & 0x8000:
            break
    return out


def read_overlay(blocks: List[dict], addr: int, size: int) -> bytes:
    out = bytearray(size)
    hit = bytearray(size)
    for blk in blocks:
        ba = blk["addr"]
        data = blk["data"]
        start = max(addr, ba)
        end = min(addr + size, ba + len(data))
        if end > start:
            out[start - addr : end - addr] = data[start - ba : end - ba]
            hit[start - addr : end - addr] = b"\1" * (end - start)
    if not all(hit):
        raise RuntimeError(f"function 0x{addr:08x}+{size} is not fully covered by LDR blocks")
    return bytes(out)


def function_bytes(name: str, records: List[dict], blocks: List[dict]) -> Tuple[dict, bytes]:
    matches = [r for r in records if r["name"] == name]
    if not matches:
        raise KeyError(f"symbol not found: {name}")
    # The map can contain a second core copy.  Use the first/high-memory instance,
    # matching the established M9 forensic convention.
    rec = matches[0]
    return rec, read_overlay(blocks, rec["addr"], rec["size"])


def regmv(h: int) -> str:
    src, dst = h & 7, (h >> 3) & 7
    gs, gd = (h >> 6) & 7, (h >> 9) & 7
    groups = {0: "R", 1: "P"}
    if gs not in groups or gd not in groups:
        raise ValueError(f"unsupported RegMv groups {gs}->{gd}")
    return f"{groups[gd]}{dst}={groups[gs]}{src}"


def ldstii(h: int) -> Tuple[str, int, int, int, int, int]:
    reg, ptr = h & 7, (h >> 3) & 7
    off, op, w = (h >> 6) & 0xF, (h >> 10) & 3, (h >> 12) & 1
    if op != 0:
        raise ValueError(f"unsupported LDSTii op={op}")
    if not w:
        return (f"R{reg}=[P{ptr}+{off*4}]", reg, ptr, off * 4, op, w)
    return (f"[P{ptr}+{off*4}]=R{reg}", reg, ptr, off * 4, op, w)


def alu2(h: int) -> str:
    dst, src, opc = h & 7, (h >> 3) & 7, (h >> 6) & 0xF
    if opc == 3:
        return f"R{dst}=R{dst}*R{src}"
    raise ValueError(f"unsupported ALU2 opcode {opc}")


def comp3(h: int) -> str:
    src0, src1 = h & 7, (h >> 3) & 7
    dst, opc = (h >> 6) & 7, (h >> 9) & 7
    if opc == 0:
        return f"R{dst}=R{src0}+R{src1}"
    if opc == 7:
        return f"P{dst}=P{src0}+(P{src1}<<2)"
    if opc == 5:
        return f"P{dst}=P{src0}+P{src1}"
    raise ValueError(f"unsupported COMP3 opcode {opc}")


def dsp32alu_add(hi: int, lo: int) -> str:
    s, x = (lo >> 13) & 1, (lo >> 12) & 1
    aop = (lo >> 14) & 3
    src0, src1 = (lo >> 3) & 7, lo & 7
    dst0 = (lo >> 9) & 7
    hl, aopcde = (hi >> 5) & 1, hi & 0x1F
    # Leica's SetLutL3 uses the normal 32-bit register add encoding.
    if (s, x, aop, hl, aopcde) != (0, 0, 0, 0, 4):
        raise ValueError(
            f"unsupported DSP32ALU fields s={s} x={x} aop={aop} HL={hl} code={aopcde}"
        )
    return f"R{dst0}=R{src0}+R{src1}"


def ldimm_half(hi: int, lo: int) -> str:
    reg, grp = hi & 7, (hi >> 3) & 3
    s, h, z = (hi >> 5) & 1, (hi >> 6) & 1, (hi >> 7) & 1
    if (s, h, z) != (1, 0, 0):
        raise ValueError("only sign-extended whole-register LDIMM used here")
    val = lo if lo < 0x8000 else lo - 0x10000
    g = {0: "R", 1: "P"}.get(grp)
    if g is None:
        raise ValueError(f"unsupported LDIMM group {grp}")
    return f"{g}{reg}={val}"


def ldst(h: int) -> str:
    reg, ptr = h & 7, (h >> 3) & 7
    z, aop, w, sz = (h >> 6) & 1, (h >> 7) & 3, (h >> 9) & 1, (h >> 10) & 3
    if (aop, w, sz) != (2, 0, 0):
        raise ValueError("unsupported LDST form")
    if z:
        return f"P{reg}=[P{ptr}]"
    return f"R{reg}=[P{ptr}]"


def fp_restore(h: int) -> str:
    reg, off, w = h & 0xF, (h >> 4) & 0x1F, (h >> 9) & 1
    if w:
        raise ValueError("unexpected FP store")
    name = f"R{reg}" if reg < 8 else f"P{reg-8}"
    return f"{name}=[FP-{off*4}]"


def trace_set_lut(code: bytes) -> dict:
    # Exact instruction layout for M Monochrom 1.022 SetLutL3.  Keeping this
    # strict is intentional: firmware drift should fail visibly rather than
    # produce plausible but wrong semantics.
    pos = 0
    ops: List[str] = []
    while pos < len(code):
        h = struct.unpack_from("<H", code, pos)[0]
        if (h & 0xF000) == 0x3000:
            ops.append(regmv(h)); pos += 2
        elif (h & 0xE000) == 0xA000:
            ops.append(ldstii(h)[0]); pos += 2
        elif (h & 0xFC00) == 0x4000:
            ops.append(alu2(h)); pos += 2
        elif (h & 0xF7C0) == 0xC400:
            lo = struct.unpack_from("<H", code, pos + 2)[0]
            ops.append(dsp32alu_add(h, lo)); pos += 4
        elif (h & 0xF000) == 0x5000:
            ops.append(comp3(h)); pos += 2
        elif (h & 0xFC00) == 0xB000:  # only b308 in this function
            ops.append(ldstii(h)[0]); pos += 2
        elif h in (0x0000, 0x0010):
            ops.append("NOP" if h == 0 else "RTS"); pos += 2
        else:
            raise ValueError(f"unexpected SetLutL3 opcode 0x{h:04x} at +0x{pos:x}")

    expected = [
        "P1=R0",
        "R1=[P1+12]", "R0=[P1+44]", "R2=[P1+40]",
        "R0=R0*R1", "R2=R2*R1", "R3=[P1+8]", "R0=R0*R3", "R3=R3*R2",
        "R2=[P1+16]", "R2=R2*R0", "R2=R2+R3",
        "R0=[P1+32]", "NOP", "R0=R0*R1", "R0=R2+R0",
        "R1=[P1+36]", "NOP", "R0=R0+R1",
        "R2=[P1+28]", "NOP", "R1=[P1+24]", "R2=R1+R2",
        "R1=[P1+4]", "NOP", "R0=R0*R1", "R0=R2+R0", "[P1+48]=R0", "RTS",
    ]
    if ops != expected:
        raise AssertionError("SetLutL3 decode changed:\n" + "\n".join(ops))

    formula = "f24 + f28 + f4*(f36 + f12*(f32 + f8*(f40 + f16*f44)))"
    return {"ops": ops, "output_field": 48, "formula": formula}


def trace_iso(code: bytes) -> dict:
    if len(code) != 18:
        raise AssertionError(f"expected 18-byte LoadISODataL1, got {len(code)}")
    h = list(struct.unpack("<9H", code))
    ops = [
        regmv(h[0]),
        ldimm_half(h[1], h[2]),
        ldst(h[3]),
        comp3(h[4]),
        comp3(h[5]),
        ldst(h[6]),
        fp_restore(h[7]),
        "RTS" if h[8] == 0x0010 else f"0x{h[8]:04x}",
    ]
    expected = [
        "P1=R0", "P0=92", "P2=[P1]", "P0=P1+P0", "P0=P0+(P2<<2)",
        "R0=[P0]", "P0=[FP-32]", "RTS",
    ]
    if ops != expected:
        raise AssertionError("LoadISODataL1 decode changed:\n" + "\n".join(ops))
    return {
        "ops": ops,
        "semantics": "return *(uint32_t *)(descriptor + 0x5c + 4*descriptor->iso_slot)",
        "iso_slot_field": 0,
        "table_offset": 0x5C,
        "entry_size": 4,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ldr", required=True, type=Path)
    ap.add_argument("--map", required=True, dest="map_path", type=Path)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    records = map_records(args.map_path)
    blocks = ldr_blocks(args.ldr)
    out: Dict[str, dict] = {}
    for name, tracer in (("SetLutL3", trace_set_lut), ("LoadISODataL1", trace_iso)):
        rec, code = function_bytes(name, records, blocks)
        d = tracer(code)
        d.update({
            "address": f"0x{rec['addr']:08x}",
            "size": rec["size"],
            "sha256": hashlib.sha256(code).hexdigest(),
        })
        out[name] = d

    if args.json:
        print(json.dumps(out, indent=2))
        return
    for name, d in out.items():
        print(f"{name} @ {d['address']} size={d['size']} sha256={d['sha256']}")
        for op in d["ops"]:
            print("  ", op)
        if "formula" in d:
            print("  formula:", d["formula"])
        if "semantics" in d:
            print("  semantics:", d["semantics"])


if __name__ == "__main__":
    main()
