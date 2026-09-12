#!/usr/bin/env python3
"""Trace M Monochrom Process_Sharpness/UM_Gauss3LUT image geometry.

Outputs derived disassembly context only. The goal is to close the exact image
pointer, width/stride/height and border rectangle semantics before an Android
port is allowed.
"""
from __future__ import annotations

import argparse
import bisect
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as base  # noqa: E402

TARGET_NAMES = ("Run", "Process_Sharpness", "UM_Gauss3LUT", "LUT")


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("mm_decrypted",type=pathlib.Path)
    ap.add_argument("--objdump",type=pathlib.Path,required=True)
    ap.add_argument("--outdir",type=pathlib.Path,required=True)
    a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if base.sha(fw)!=base.MM_DEC_SHA:
        raise SystemExit(f"decrypted firmware SHA mismatch: {base.sha(fw)}")
    a.outdir.mkdir(parents=True,exist_ok=True)
    work=a.outdir/"_binary_work"; work.mkdir(exist_ok=True)

    bf=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=="BF561"),None)
    if bf is None:raise SystemExit("outer BF561 missing")
    children=pwad.parse_pwad(bf.data); cmap={x.name.lower():x for x in children}
    syms=base.parse_map(cmap["bf0.map"].data)
    blocks=base.parse_ldr(cmap["bf0"].data)
    lines=base.disassemble_blocks(blocks,a.objdump,work)
    addrs=[x[0] for x in lines]

    by_name={}
    for n in TARGET_NAMES:
        by_name[n]=[{"addr":int(s["addr"]),"size":int(s["size"])} for s in syms if s["name"]==n]

    starts=sorted((int(s["addr"]),s["name"],int(s["size"])) for s in syms)
    start_addrs=[x[0] for x in starts]
    def owner(addr:int):
        i=bisect.bisect_right(start_addrs,addr)-1
        if i<0:return None
        st,n,sz=starts[i]
        return {"name":n,"start":hex(st),"size":sz,"offset":addr-st,"inside":addr<st+max(1,sz)}

    transfer=[
        re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b",re.I),
        re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\b.*?<([0-9a-fA-F]+)>",re.I),
    ]
    target_starts={n:{x["addr"] for x in xs} for n,xs in by_name.items()}
    callsites=[]
    for idx,(addr,text,src,ln) in enumerate(lines):
        target=None
        for pat in transfer:
            m=pat.search(text)
            if m:
                target=int(m.group(1),16);break
        if target is None:continue
        hit=[n for n,aset in target_starts.items() if target in aset]
        if not hit:continue
        lo=max(0,idx-70); hi=min(len(lines),idx+30)
        callsites.append({
            "site":hex(addr),"owner":owner(addr),"target":hex(target),"target_names":hit,
            "context":[{"addr":hex(x[0]),"text":x[1],"owner":owner(x[0])} for x in lines[lo:hi]],
        })

    funcs={}
    for n,xs in by_name.items():
        funcs[n]=[]
        for x in xs:
            lo=x["addr"]; hi=lo+x["size"]
            i=bisect.bisect_left(addrs,lo);j=bisect.bisect_left(addrs,hi)
            funcs[n].append({"addr":hex(lo),"size":x["size"],"disassembly":"\n".join(y[1] for y in lines[i:j])})

    # Extract all FP/SP offset references in the two key functions so stack-passed
    # geometry arguments can be mapped mechanically.
    stack_refs={}
    for n in ("Process_Sharpness","UM_Gauss3LUT"):
        refs=[]
        for f in funcs[n]:
            for line in f["disassembly"].splitlines():
                if "[FP" in line or "[SP" in line:
                    refs.append(line)
        stack_refs[n]=refs

    report={
        "schema":"mmonochrom.sharpness.geometryprobe1a.v1",
        "firmware_decrypted_sha256":base.sha(fw),
        "classification":"derived_geometry_and_callsite_disassembly",
        "symbols":{n:[{"addr":hex(x["addr"]),"size":x["size"]} for x in xs] for n,xs in by_name.items()},
        "callsites":callsites,
        "functions":funcs,
        "stack_refs":stack_refs,
        "questions":[
            "Map Process_Sharpness caller stack stores to image pointer, width, stride and height.",
            "Map Process_Sharpness local argument reshuffle into UM_Gauss3LUT ABI.",
            "Prove first/last processed row/column and whether border samples are left unchanged.",
        ],
    }
    (a.outdir/"MM_SHARPNESS_GEOMETRY_PROBE.json").write_text(json.dumps(report,indent=2)+"\n")
    with (a.outdir/"MM_SHARPNESS_GEOMETRY_PROBE.txt").open("w") as f:
        for c in callsites:
            f.write(f"\n===== CALL {c['site']} owner={c['owner']} -> {c['target_names']} {c['target']} =====\n")
            for row in c["context"]:f.write(row["text"]+"\n")
        for n in ("Process_Sharpness","UM_Gauss3LUT"):
            for x in funcs[n]:f.write(f"\n===== {n} {x['addr']} size={x['size']} =====\n{x['disassembly']}\n")
    for p in work.iterdir():p.unlink()
    work.rmdir()
    print(json.dumps({"symbols":report["symbols"],"callsite_count":len(callsites),"callsite_summary":[{"site":x["site"],"owner":x["owner"],"target_names":x["target_names"]} for x in callsites]},indent=2))


if __name__=="__main__":main()
