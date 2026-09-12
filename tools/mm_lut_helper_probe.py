#!/usr/bin/env python3
"""Extract original M Monochrom LUT helper used by UM_Gauss3LUT."""
from __future__ import annotations
import argparse,bisect,json,pathlib,re,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad
import mm_sharpness_consumer_trace as base

TARGETS=("LUT","UM_Gauss3LUT","Process_Sharpness")

def main():
    ap=argparse.ArgumentParser();ap.add_argument("mm_decrypted",type=pathlib.Path);ap.add_argument("--objdump",type=pathlib.Path,required=True);ap.add_argument("--outdir",type=pathlib.Path,required=True);a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if base.sha(fw)!=base.MM_DEC_SHA: raise SystemExit("firmware SHA mismatch")
    a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/"_binary_work";work.mkdir(exist_ok=True)
    bf=next(x for x in pwad.parse_pwad(fw) if x.name.upper()=="BF561"); ch={x.name.lower():x for x in pwad.parse_pwad(bf.data)}
    syms=base.parse_map(ch["bf0.map"].data);blocks=base.parse_ldr(ch["bf0"].data);lines=base.disassemble_blocks(blocks,a.objdump,work);addrs=[x[0] for x in lines]
    exact={}
    for s in syms: exact.setdefault(int(s["addr"]),[]).append(s["name"])
    starts=sorted(exact)
    def resolve(addr):
        if addr in exact:return {"exact":exact[addr]}
        i=bisect.bisect_right(starts,addr)-1
        if i<0:return None
        st=starts[i];return {"nearest_addr":hex(st),"nearest":exact[st],"offset":addr-st}
    pats=[re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b",re.I),re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\b.*?<([0-9a-fA-F]+)>",re.I)]
    funcs=[]
    for s in syms:
        if s["name"] not in TARGETS:continue
        lo=int(s["addr"]);hi=lo+int(s["size"]);i=bisect.bisect_left(addrs,lo);j=bisect.bisect_left(addrs,hi);fl=lines[i:j]
        transfers=[]
        for addr,line,src,ln in fl:
            target=None
            for p in pats:
                m=p.search(line)
                if m:target=int(m.group(1),16);break
            if target is not None:transfers.append({"site":hex(addr),"target":hex(target),"resolve":resolve(target),"text":line})
        funcs.append({"name":s["name"],"addr":hex(lo),"size":int(s["size"]),"disassembly":"\n".join(x[1] for x in fl),"transfers":transfers})
    lut=[x for x in funcs if x["name"]=="LUT"]
    if len(lut)<2:raise SystemExit(f"expected mirrored LUT symbols; got {len(lut)}")
    report={"schema":"mmonochrom.sharpness.luthelper1a.v1","firmware_decrypted_sha256":base.sha(fw),"classification":"focused_disassembly_evidence","functions":funcs}
    (a.outdir/"MM_LUT_HELPER_PROBE.json").write_text(json.dumps(report,indent=2)+"\n")
    with (a.outdir/"MM_LUT_HELPER_PROBE.txt").open("w") as f:
        for x in funcs:f.write(f"\n===== {x['name']} {x['addr']} size={x['size']} =====\n{x['disassembly']}\n-- transfers --\n{json.dumps(x['transfers'],indent=2)}\n")
    for p in work.iterdir():p.unlink()
    work.rmdir()
    print(json.dumps([{"name":x["name"],"addr":x["addr"],"size":x["size"]} for x in funcs],indent=2))
if __name__=="__main__":main()
