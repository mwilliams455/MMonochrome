#!/usr/bin/env python3
"""Extract every fixed-map occurrence of selected BF561 symbols.

The Leica bf0 map can legitimately contain repeated/truncated symbol names.
This helper preserves every matching record in map order and extracts the exact
LDR overlay bytes for each one, producing address/size/SHA-256 anchors plus
optionally raw local function slices.  It makes no claim about which occurrence
is active beyond the map region supplied by the caller.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from pathlib import Path


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def map_records(path: Path) -> list[dict]:
    data = path.read_bytes()
    if len(data) % 32:
        raise ValueError(f"{path}: map size {len(data)} is not a multiple of 32")
    out=[]
    for off in range(0,len(data),32):
        rec=data[off:off+32]
        name=rec[:24].split(b"\0",1)[0].decode("ascii","ignore").rstrip("'")
        addr,size=struct.unpack_from("<II",rec,24)
        if name:
            out.append({"name":name,"addr":addr,"size":size,"map_off":off})
    return out


def ldr_blocks(path: Path) -> list[dict]:
    data=path.read_bytes(); off=4; out=[]
    while off+10 <= len(data):
        addr,count,flags=struct.unpack_from("<IIH",data,off); off += 10
        if flags & 1:
            payload=bytes(count)
        else:
            end=off+count
            if end > len(data):
                raise RuntimeError(f"{path}: LDR block 0x{addr:08x}+{count} overruns file")
            payload=data[off:end]; off=end
        out.append({"addr":addr,"data":payload,"flags":flags})
        if flags & 0x8000:
            break
    if not out:
        raise RuntimeError(f"{path}: no LDR blocks parsed")
    return out


def read_overlay(blocks: list[dict], addr: int, size: int) -> bytes:
    out=bytearray(size); hit=bytearray(size)
    for b in blocks:
        base=b["addr"]; data=b["data"]
        start=max(addr,base); end=min(addr+size,base+len(data))
        if end > start:
            out[start-addr:end-addr]=data[start-base:end-base]
            hit[start-addr:end-addr]=b"\x01"*(end-start)
    if not all(hit):
        miss=next(i for i,v in enumerate(hit) if not v)
        raise RuntimeError(f"missing overlay byte at 0x{addr+miss:08x}")
    return bytes(out)


def safe_name(name: str) -> str:
    return ''.join(c if c.isalnum() or c in '._-' else '_' for c in name)


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--ldr",required=True,type=Path)
    ap.add_argument("--map",required=True,type=Path)
    ap.add_argument("--symbol",required=True,action="append")
    ap.add_argument("--out-dir",type=Path)
    ap.add_argument("--strict",action="store_true")
    args=ap.parse_args()
    rows=map_records(args.map); blocks=ldr_blocks(args.ldr)
    if args.out_dir: args.out_dir.mkdir(parents=True,exist_ok=True)
    result={"schema":"mmonochrom.bfin_symbol_occurrences.v1","map":str(args.map),"ldr":str(args.ldr),"symbols":{},"problems":[]}
    for symbol in args.symbol:
        matches=[r for r in rows if r["name"]==symbol]
        items=[]
        if not matches:
            result["problems"].append(f"symbol not found: {symbol}")
        for i,r in enumerate(matches):
            try:
                code=read_overlay(blocks,r["addr"],r["size"])
            except RuntimeError as exc:
                result["problems"].append(f"{symbol}[{i}]: {exc}")
                continue
            filename=f"{safe_name(symbol)}__{i}__0x{r['addr']:08x}.bin"
            if args.out_dir:
                (args.out_dir/filename).write_bytes(code)
            items.append({
                "occurrence":i,"address":f"0x{r['addr']:08x}","size":r["size"],
                "map_offset":f"0x{r['map_off']:x}","sha256":sha256(code),"filename":filename,
            })
        result["symbols"][symbol]=items
    result["verified"]=not result["problems"]
    print(json.dumps(result,indent=2))
    if args.strict and result["problems"]:
        raise SystemExit(2)

if __name__ == "__main__":
    main()
