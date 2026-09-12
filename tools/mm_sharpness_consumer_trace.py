#!/usr/bin/env python3
"""Trace original M Monochrom BF561 sharpness-related consumers.

Input is the canonical *decrypted* M Monochrom 1.022 updater and a Blackfin
objdump. Output is derived text/JSON evidence only. No firmware bytes are
embedded in the report.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import pathlib
import re
import struct
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402

MM_DEC_SHA = "c9e14ee475408802c83774f37b19c85c57663d9840e8e4c2cfe80e14dec9a7ae"
FOCUS = (
    "Process_Sharpness", "LoadAndModifySharpnessDa",
    "Process_Noise", "Process_Shading", "Process_Contrast",
    "LoadISODataL1", "LoadLutArchiveL3", "CalculateNoiseParameter",
    "SetStructParameter", "SetProcess", "Set", "Run",
)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def parse_map(data: bytes) -> list[dict]:
    out=[]
    for off in range(0, len(data)-31, 32):
        rec=data[off:off+32]
        name=rec[:24].split(b"\0",1)[0].decode("ascii","ignore").rstrip("'")
        if not name:
            continue
        addr,size=struct.unpack_from("<II",rec,24)
        out.append({"name":name,"addr":addr,"size":size,"mapoff":off})
    return out


def parse_ldr(data: bytes) -> list[dict]:
    if len(data) < 4:
        raise ValueError("LDR too small")
    off=4; out=[]
    while off+10 <= len(data):
        header=off
        addr,count,flags=struct.unpack_from("<IIH",data,off); off += 10
        if flags & 1:
            payload=bytes(count)
        else:
            if off+count > len(data):
                raise ValueError(f"LDR block overrun at {header:#x}")
            payload=data[off:off+count]; off += count
        out.append({"addr":addr,"size":len(payload),"flags":flags,
                    "header_off":header,"payload":payload})
        if flags & 0x8000:
            break
    return out


def disassemble_blocks(blocks: list[dict], objdump: pathlib.Path, work: pathlib.Path) -> list[tuple[int,str,str,int]]:
    all_lines=[]
    for bi,b in enumerate(blocks):
        raw=work/f"block_{bi:03d}_{b['addr']:08x}.bin"
        raw.write_bytes(b["payload"])
        p=subprocess.run([str(objdump),"-D","-b","binary","-m","bfin",
                          f"--adjust-vma=0x{b['addr']:x}",str(raw)],
                         text=True,capture_output=True)
        if p.returncode:
            raise RuntimeError(f"objdump failed block {bi}: {p.stderr}")
        dis=work/f"block_{bi:03d}_{b['addr']:08x}.dis.txt"
        dis.write_text(p.stdout)
        for ln,line in enumerate(p.stdout.splitlines(),1):
            m=re.match(r"^\s*([0-9a-fA-F]+):",line)
            if m:
                all_lines.append((int(m.group(1),16),line,dis.name,ln))
    all_lines.sort(key=lambda x:x[0])
    return all_lines


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("mm_decrypted",type=pathlib.Path)
    ap.add_argument("--objdump",type=pathlib.Path,required=True)
    ap.add_argument("--outdir",type=pathlib.Path,required=True)
    a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if sha(fw)!=MM_DEC_SHA:
        raise SystemExit(f"decrypted firmware SHA mismatch: {sha(fw)}")
    a.outdir.mkdir(parents=True,exist_ok=True)
    work=a.outdir/"_binary_work"; work.mkdir(exist_ok=True)

    bf=next((l for l in pwad.parse_pwad(fw) if l.name.upper()=="BF561"),None)
    if bf is None:
        raise SystemExit("outer BF561 missing")
    children=pwad.parse_pwad(bf.data)
    cmap={l.name.lower():l for l in children}
    if "bf0" not in cmap or "bf0.map" not in cmap:
        raise SystemExit(f"BF561 children missing bf0/map: {sorted(cmap)}")
    ldr=cmap["bf0"].data; mp=cmap["bf0.map"].data
    syms=parse_map(mp); blocks=parse_ldr(ldr)
    lines=disassemble_blocks(blocks,a.objdump,work)
    addrs=[x[0] for x in lines]
    exact={}
    for s in syms:
        exact.setdefault(int(s["addr"]),[]).append(s["name"])
    starts=sorted(exact)

    def resolve(addr:int):
        if addr in exact:
            return {"exact":exact[addr]}
        i=bisect.bisect_right(starts,addr)-1
        if i<0:return None
        st=starts[i]
        return {"nearest_addr":hex(st),"nearest":exact[st],"offset":addr-st}

    def func_text(s:dict) -> str:
        lo=int(s["addr"]); hi=lo+int(s["size"])
        i=bisect.bisect_left(addrs,lo); j=bisect.bisect_left(addrs,hi)
        return "\n".join(x[1] for x in lines[i:j])

    funcs={}
    for name in FOCUS:
        funcs[name]=[]
        for s in syms:
            if s["name"]==name:
                funcs[name].append({"addr":hex(int(s["addr"])),"size":int(s["size"]),
                                    "disassembly":func_text(s)})

    # Binutils prints these targets as e.g. "CALL 0x0xffa0287c" in this target,
    # so accept an optional doubled 0x prefix as well as normal absolute hex.
    transfer_patterns=[
        re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b",re.I),
        re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\b.*?<([0-9a-fA-F]+)>",re.I),
    ]
    focus_ranges=[]
    for name in FOCUS:
        for s in syms:
            if s["name"]==name:
                focus_ranges.append((int(s["addr"]),int(s["addr"])+max(1,int(s["size"])),name))
    calls=[]
    for addr,line,src,ln in lines:
        target=None
        for pat in transfer_patterns:
            m=pat.search(line)
            if m:
                target=int(m.group(1),16); break
        if target is None: continue
        hit=[{"name":n,"start":hex(lo),"offset":target-lo} for lo,hi,n in focus_ranges if lo<=target<hi]
        if hit:
            calls.append({"site":hex(addr),"site_resolve":resolve(addr),"target":hex(target),
                          "target_resolve":resolve(target),"target_hit":hit,"text":line})

    offset_tokens=("0x5c","0x58","0x18","0x14","0x10","0xc","0x0c","0x30","0x34","0x38","0x3c","0x40",
                   "0x460","0x468","0x7c","0x84","0x818")
    field_hits=[]
    focus_words=("sharp","noise","iso","lutarchive","setstruct","setprocess")
    for addr,line,src,ln in lines:
        r=resolve(addr)
        names=[] if not r else (r.get("exact") or r.get("nearest") or [])
        if any(k in " ".join(names).lower() for k in focus_words) and any(tok in line.lower() for tok in offset_tokens):
            field_hits.append({"addr":hex(addr),"resolve":r,"text":line})

    geometry_hits=[]
    for addr,line,src,ln in lines:
        ll=line.lower()
        if any(tok in ll for tok in ("2050","0x802","4100","0x1004")):
            geometry_hits.append({"addr":hex(addr),"resolve":resolve(addr),"text":line})

    # Explicitly report all calls whose site is inside the two sharpness functions,
    # even if the destination is not a named function entry. This exposes internal
    # helper/secondary-entry relationships without assigning semantics by guess.
    sharp_ranges=[]
    for s in syms:
        if s["name"] in ("Process_Sharpness","LoadAndModifySharpnessDa"):
            sharp_ranges.append((int(s["addr"]),int(s["addr"])+max(1,int(s["size"])),s["name"]))
    sharp_calls=[]
    for addr,line,src,ln in lines:
        if not any(lo<=addr<hi for lo,hi,_ in sharp_ranges):
            continue
        target=None
        for pat in transfer_patterns:
            m=pat.search(line)
            if m:
                target=int(m.group(1),16); break
        if target is not None:
            sharp_calls.append({"site":hex(addr),"site_owner":[n for lo,hi,n in sharp_ranges if lo<=addr<hi],
                                "target":hex(target),"target_resolve":resolve(target),"text":line})

    manifest={"bf561_sha256":bf.sha256,"children":[{"name":l.name,"size":l.size,"sha256":l.sha256} for l in children],
              "bf0_symbol_count":len(syms),"bf0_block_count":len(blocks)}
    report={
        "schema":"mmonochrom.sharpness.consumertrace1c.v1",
        "firmware_decrypted_sha256":sha(fw),
        "bf561_manifest":manifest,
        "focus_symbols":[{"name":s["name"],"addr":hex(int(s["addr"])),"size":int(s["size"])} for s in syms if s["name"] in FOCUS],
        "functions":funcs,
        "calls_into_focus_functions":calls,
        "sharpness_owned_calls":sharp_calls,
        "descriptor_offset_hits":field_hits,
        "geometry_constant_hits":geometry_hits,
        "classification":"disassembly_evidence_only_semantics_require_manual_or_crosscamera_closure",
    }
    (a.outdir/"bf561_manifest.json").write_text(json.dumps(manifest,indent=2)+"\n")
    (a.outdir/"mm_sharpness_consumer_trace.json").write_text(json.dumps(report,indent=2)+"\n")
    with (a.outdir/"mm_sharpness_consumer_trace.txt").open("w") as f:
        for name,items in funcs.items():
            for item in items:
                f.write(f"\n===== {name} {item['addr']} size={item['size']} =====\n{item['disassembly']}\n")
        f.write("\n===== CALLS INTO FOCUS =====\n"+json.dumps(calls,indent=2)+"\n")
        f.write("\n===== SHARPNESS-OWNED CALLS =====\n"+json.dumps(sharp_calls,indent=2)+"\n")
        f.write("\n===== FIELD HITS =====\n"+json.dumps(field_hits,indent=2)+"\n")
        f.write("\n===== GEOMETRY CONSTANT HITS =====\n"+json.dumps(geometry_hits,indent=2)+"\n")
    for p in work.iterdir(): p.unlink()
    work.rmdir()
    print(json.dumps({"focus_counts":{k:len(v) for k,v in funcs.items()},"calls":len(calls),
                      "sharpness_owned_calls":len(sharp_calls),"field_hits":len(field_hits),
                      "geometry_hits":len(geometry_hits)},indent=2))


if __name__=="__main__":
    main()
