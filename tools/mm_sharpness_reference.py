#!/usr/bin/env python3
"""Firmware-derived Leica M Monochrom 1.022 sharpness host oracle.

This is a research/reference model, not Android production code. It implements
only behavior already closed from the canonical firmware:

* 16 ISO-specific 2050-int16 source LUT rows at PROCESS/LUTS + 0x58c.
* public Sharpening enum Off/Low/Standard/Medium high/High = selectors 0..4.
* selector x ISO modifier-code matrix at PROCESS/LUTS 0x410..0x58c.
* exact descriptor sequence 0,1,2,3,4,5,6,7,8,10,12,13,20.
* parity-reduced signed multiply/right-shift and coefficient clamp [-2048,2048].
* stage-wise separable [1,2,1]/4 Gaussian.
* centered nonlinear LUT mapping over residual [-1024,+1024].
* in-place unsigned 14-bit result clamp [0,16383].
* Sharp contributes +2 to the accumulated valid-border/inset state; pixels
  outside the resulting interior rectangle are untouched.

It consumes the canonical decrypted updater at runtime so firmware LUT bytes are
not committed to this repository.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
from dataclasses import dataclass
from typing import Sequence

import mm_lutbank_geometry_probe as geom

MM_DEC_SHA = geom.MM_FW_SHA
PROCESS_LUTS_PATH = "LUTS/PROCESS/LUTS"
BANK_START = geom.MM_BANK_START
ISO_VALUES = geom.EXPECTED_MM_ISO
ISO_ROWS = 16
LUT_LEN = 2050
LUT_CENTER = 1024
DETAIL_LIMIT = 1024
COEFF_LIMIT = 2048
PIXEL_MAX = 16383
SHARP_BORDER_INCREMENT = 2

MENU_TO_SELECTOR = {
    "off": 0,
    "low": 1,
    "standard": 2,
    "medium high": 3,
    "medium_high": 3,
    "medium-high": 3,
    "high": 4,
}

EXPECTED_MODIFIER_MATRIX = [
    [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
    [4,4,4,4,2,2,2,2,2,2,2,2,2,2,1,1],
    [8,8,8,8,4,4,4,4,4,4,4,4,3,3,2,2],
    [11,11,11,11,8,8,8,8,8,8,8,7,6,5,4,3],
    [12,12,12,12,11,11,11,11,11,11,11,10,9,8,7,6],
]

DESCRIPTORS = [0,1,2,3,4,5,6,7,8,10,12,13,20]


@dataclass(frozen=True)
class Selection:
    iso: int
    iso_slot: int
    menu: str
    selector: int
    modifier_code: int
    descriptor: int


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def clamp(v: int, lo: int, hi: int) -> int:
    return lo if v < lo else hi if v > hi else v


def load_process_luts(mm_decrypted: str | pathlib.Path) -> bytes:
    fw = pathlib.Path(mm_decrypted).read_bytes()
    digest = sha(fw)
    if digest != MM_DEC_SHA:
        raise ValueError(f"decrypted firmware SHA mismatch: {digest} != {MM_DEC_SHA}")
    payload = geom.find_exact(fw, PROCESS_LUTS_PATH)
    if len(payload) != geom.MM_LUTS_SIZE:
        raise ValueError(f"PROCESS/LUTS size mismatch: {len(payload)}")
    return payload


def extract_bank(process_luts: bytes) -> list[list[int]]:
    rows=[]
    for slot in range(ISO_ROWS):
        off=BANK_START + slot*LUT_LEN*2
        rows.append(list(struct.unpack_from("<"+"h"*LUT_LEN, process_luts, off)))
    return rows


def extract_modifier_matrix(process_luts: bytes) -> list[list[int]]:
    start=0x410; stride_words=19
    matrix=[]
    for selector in range(5):
        off=start + selector*stride_words*4
        vals=list(struct.unpack_from("<"+"I"*stride_words, process_luts, off))
        matrix.append([int(v) for v in vals[:16]])
    if matrix != EXPECTED_MODIFIER_MATRIX:
        raise ValueError(f"modifier matrix mismatch: {matrix}")
    return matrix


def select(iso: int, menu: str, matrix: Sequence[Sequence[int]]) -> Selection:
    try:
        slot=ISO_VALUES.index(int(iso))
    except ValueError as exc:
        raise ValueError(f"unsupported proven M Monochrom physical ISO: {iso}") from exc
    key=menu.strip().lower()
    try:
        selector=MENU_TO_SELECTOR[key]
    except KeyError as exc:
        raise ValueError(f"unknown M Monochrom Sharpening menu value: {menu!r}") from exc
    code=int(matrix[selector][slot])
    if not 0 <= code < len(DESCRIPTORS):
        raise ValueError(f"modifier code outside proven range: {code}")
    return Selection(int(iso),slot,key,selector,code,DESCRIPTORS[code])


def decode_descriptor(code: int) -> tuple[int,int]:
    """Return the exact multiplier/right-shift used by LoadAndModifySharpnessDa."""
    if not 0 <= code <= 12:
        raise ValueError(code)
    desc=int(DESCRIPTORS[code])
    if code == 0:
        return 0,0
    r2=desc
    r1=2
    if (r2 & 1) == 0:
        r1=1
        r2 >>= 1
    r0=r1 >> 1
    if (r2 & 1) == 0:
        r1=r0
        r2 >>= 1
    return r2,r1


def scale_lut(base: Sequence[int], code: int) -> list[int]:
    if len(base) != LUT_LEN:
        raise ValueError(f"base LUT length {len(base)} != {LUT_LEN}")
    if code == 0:
        raise ValueError("code 0 is disabled before LUT copy/modify in firmware")
    mult,shift=decode_descriptor(code)
    return [clamp((int(x)*mult) >> shift, -COEFF_LIMIT, COEFF_LIMIT) for x in base]


def lut_correction(detail: int, table: Sequence[int]) -> int:
    if len(table) != LUT_LEN:
        raise ValueError("working LUT length mismatch")
    clip_mag=-int(table[0])
    if detail < -DETAIL_LIMIT:
        return -clip_mag
    if detail > DETAIL_LIMIT:
        return clip_mag
    return int(table[LUT_CENTER+detail])


def apply_kernel(
    src: Sequence[Sequence[int]],
    table: Sequence[int],
    incoming_border: int=0,
) -> tuple[list[list[int]], int]:
    """Apply the exact closed UM_Gauss3LUT rectangle/arithmetic.

    The firmware routine receives the *updated* border after Process_Sharpness
    adds two. This API accepts the incoming accumulated border for convenience.
    """
    if incoming_border < 0:
        raise ValueError("incoming_border must be >= 0")
    h=len(src); w=len(src[0]) if h else 0
    if any(len(row)!=w for row in src):
        raise ValueError("source is not rectangular")
    if any(not (0 <= int(v) <= PIXEL_MAX) for row in src for v in row):
        raise ValueError("source must contain unsigned 14-bit samples")
    out=[[int(v) for v in row] for row in src]
    b=incoming_border + SHARP_BORDER_INCREMENT
    iw=w-2*b; ih=h-2*b
    if iw <= 0 or ih <= 0:
        return out,b

    # Horizontal scratch is full-pitch in firmware, but only the exact required
    # rectangle is initialized by this stage.
    scratch=[[0]*w for _ in range(h)]
    for y in range(b-1, h-b+1):
        for x in range(b, w-b):
            scratch[y][x]=(int(src[y][x-1]) + 2*int(src[y][x]) + int(src[y][x+1])) >> 2

    for y in range(b, h-b):
        for x in range(b, w-b):
            blur=(scratch[y-1][x] + 2*scratch[y][x] + scratch[y+1][x]) >> 2
            center=int(src[y][x])
            detail=center-blur
            corr=lut_correction(detail,table)
            out[y][x]=clamp(center+corr,0,PIXEL_MAX)
    return out,b


def apply_monochrom_sharpness(
    src: Sequence[Sequence[int]],
    bank: Sequence[Sequence[int]],
    matrix: Sequence[Sequence[int]],
    iso: int,
    menu: str="standard",
    incoming_border: int=0,
) -> tuple[list[list[int]], int, Selection]:
    sel=select(iso,menu,matrix)
    if sel.modifier_code == 0:
        # Firmware returns from Process_Sharpness before border increment.
        return [[int(v) for v in row] for row in src], incoming_border, sel
    table=scale_lut(bank[sel.iso_slot],sel.modifier_code)
    out,border=apply_kernel(src,table,incoming_border)
    return out,border,sel


def packed_u16(img: Sequence[Sequence[int]]) -> bytes:
    return b"".join(struct.pack("<H",int(v)) for row in img for v in row)


def synthetic_image(w: int=43,h: int=37) -> list[list[int]]:
    # Deterministic mix of gradients, high-frequency structure and clipping-near
    # values without relying on an external imaging library.
    out=[]
    for y in range(h):
        row=[]
        for x in range(w):
            v=(311*x + 197*y + 29*x*y + ((x^y)&7)*853 + ((x*3+y*5)%11)*487) & 0x3fff
            if (x+y)%19==0: v=16000
            if (x*7+y*3)%23==0: v=64
            row.append(v)
        out.append(row)
    return out


def self_test(mm_decrypted: str | pathlib.Path) -> dict:
    process_luts=load_process_luts(mm_decrypted)
    bank=extract_bank(process_luts)
    matrix=extract_modifier_matrix(process_luts)

    assert len(bank)==16 and all(len(r)==2050 for r in bank)
    assert matrix==EXPECTED_MODIFIER_MATRIX
    assert [decode_descriptor(i) for i in range(13)] == [
        (0,0),(1,2),(1,1),(3,2),(1,0),(5,2),(3,1),(7,2),(2,0),(5,1),(3,0),(13,2),(5,0)
    ]

    # Off is a true stage bypass: no border change and no pixels changed.
    src=synthetic_image()
    off,b0,s0=apply_monochrom_sharpness(src,bank,matrix,320,"off",incoming_border=3)
    assert off==src and b0==3 and s0.modifier_code==0

    # Constant input remains constant for every Standard ISO if the canonical
    # row maps zero residual to zero correction, which the firmware bank does.
    plane=[[4096]*29 for _ in range(27)]
    centers=[]
    for iso in ISO_VALUES:
        sel=select(iso,"standard",matrix)
        work=scale_lut(bank[sel.iso_slot],sel.modifier_code)
        centers.append(int(work[LUT_CENTER]))
        out,b,_=apply_monochrom_sharpness(plane,bank,matrix,iso,"standard",incoming_border=0)
        assert out==plane and b==2
    assert all(v==0 for v in centers)

    # Borders are copied through exactly and the stage contributes +2.
    standard,b,stdsel=apply_monochrom_sharpness(src,bank,matrix,800,"standard",incoming_border=1)
    assert b==3 and stdsel.modifier_code==4
    h=len(src);w=len(src[0])
    for y in range(h):
        for x in range(w):
            if y < b or y >= h-b or x < b or x >= w-b:
                assert standard[y][x]==src[y][x]

    vectors=[]
    for menu in ("off","low","standard","medium high","high"):
        for iso in ISO_VALUES:
            for incoming in (0,2):
                out,b,sel=apply_monochrom_sharpness(src,bank,matrix,iso,menu,incoming)
                vectors.append({
                    "menu":menu,"iso":iso,"incoming_border":incoming,
                    "out_border":b,"selector":sel.selector,"modifier_code":sel.modifier_code,
                    "descriptor":sel.descriptor,"sha256_u16le":sha(packed_u16(out)),
                    "changed_pixels":sum(int(out[y][x])!=int(src[y][x]) for y in range(len(src)) for x in range(len(src[0]))),
                })

    bank_raw=b"".join(struct.pack("<h",v) for row in bank for v in row)
    return {
        "schema":"mmonochrom.sharpness.reference-selftest1a.v1",
        "firmware_decrypted_sha256":MM_DEC_SHA,
        "process_luts_sha256":sha(process_luts),
        "sharpness_bank_sha256":sha(bank_raw),
        "iso_values":ISO_VALUES,
        "modifier_matrix":matrix,
        "descriptor_sequence":DESCRIPTORS,
        "standard_codes":EXPECTED_MODIFIER_MATRIX[2],
        "working_standard_center_coefficients":centers,
        "synthetic_source_sha256_u16le":sha(packed_u16(src)),
        "synthetic_shape":[len(src),len(src[0])],
        "vectors":vectors,
        "status":"pass",
    }


def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("mm_decrypted",type=pathlib.Path)
    ap.add_argument("--self-test",action="store_true")
    ap.add_argument("--out",type=pathlib.Path)
    args=ap.parse_args()
    if not args.self_test:
        ap.error("use --self-test")
    result=self_test(args.mm_decrypted)
    text=json.dumps(result,indent=2)+"\n"
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(text)
    print(text,end="")
    return 0


if __name__=="__main__":
    raise SystemExit(main())
