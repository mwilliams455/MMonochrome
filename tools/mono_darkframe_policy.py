#!/usr/bin/env python3
"""First-generation Leica M Monochrom 1.022 BlackRef decision model.

Recovered from the canonical BF547 control firmware. This models only the
normal Leica decision to request a black-reference acquisition; it does not
perform image correction or emulate a mechanical shutter.
"""
from __future__ import annotations
import argparse,json

# BF547 table at runtime 0xDB93C, rows selected by temperature group,
# columns selected by ISO bucket. Firmware compares exposure_us/10 > value.
TABLE = (
    (100000, 50000, 25000, 12500, 6600),
    ( 50000, 25000,  6600,  3330,  800),
    ( 25000, 12500,  6600,  1660,  400),
    (  6600,  3330,  1660,   400,  100),
)

# Canonical firmware ISO code table used by the control path.
ISO_CODES = (
    64,80,100,125,160,200,250,320,400,500,640,800,1000,
    1250,1600,2000,2500,3200,4000,5000,6400,8000,10000,
    12800,16000,20000,
)

def iso_code_index(iso:int)->int:
    """Map a physical ISO to the closest exact firmware ISO code."""
    try:return ISO_CODES.index(int(iso))
    except ValueError:raise ValueError(f"ISO {iso} is not a canonical firmware slot")

def iso_bucket_from_code(code:int)->int:
    # Closed from BF547 0x3819C path.
    if code <= 7:return 0
    return min((code-7)//6,4)

def iso_bucket(iso:int)->int:
    return iso_bucket_from_code(iso_code_index(iso))

def temperature_group(temp_c:float)->int:
    # Normal path uses groups 1..3. Group 0 exists in the table but is not
    # selected by the normal temperature branch recovered from 0x3819C.
    if temp_c <= 19:return 1
    if temp_c <= 39:return 2
    return 3

def threshold_us(iso:int,temp_c:float)->int:
    return TABLE[temperature_group(temp_c)][iso_bucket(iso)]*10

def needs_black_ref(iso:int,exposure_us:int,temp_c:float)->bool:
    # Firmware uses a strict > comparison after unsigned exposure_us / 10.
    return (int(exposure_us)//10) > TABLE[temperature_group(temp_c)][iso_bucket(iso)]

def decision(iso:int,exposure_us:int,temp_c:float)->dict:
    code=iso_code_index(iso);bucket=iso_bucket_from_code(code);group=temperature_group(temp_c)
    t=TABLE[group][bucket]*10
    return {
        "firmware":"Leica M Monochrom 1.022",
        "iso":iso,"isoCode":code,"isoBucket":bucket,
        "temperatureC":temp_c,"temperatureGroup":group,
        "exposureUs":int(exposure_us),"thresholdUs":t,
        "blackRef":needs_black_ref(iso,exposure_us,temp_c),
        "comparison":"floor(exposure_us/10) > threshold_table[group][bucket]",
    }

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--iso",type=int,required=True)
    ap.add_argument("--exposure-us",type=int,required=True)
    ap.add_argument("--temperature-c",type=float,required=True)
    a=ap.parse_args()
    print(json.dumps(decision(a.iso,a.exposure_us,a.temperature_c),indent=2))

if __name__=="__main__":main()
