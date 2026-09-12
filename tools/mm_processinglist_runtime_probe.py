#!/usr/bin/env python3
"""Compare original M Monochrom and M9 BF561 processing-list runtime.

The Monochrom and M9 BF561 images expose the same named scheduling globals and
many homologous imaging functions, but their BF547 controller layouts differ.
This evidence-only probe therefore works from the canonical BF561 maps/overlays
for each camera, compares function bodies independently, and traces access to
`g_CurrentProcessingSetti` and `g_ProcessingList` without assuming BF547 offsets.

No firmware bytes are emitted; reports contain hashes, symbols, integer fields
and disassembly text only.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as tr  # noqa: E402
from recover_leica_m9_mm_shared_key import M9_DEC_SHA, MM_DEC_SHA  # noqa: E402

TARGETS = (
    "SPI_SetNextImage", "SPI_AppendSettings", "IM_SetCurrentJob",
    "Run", "SetProcess", "SetStructParameter", "Set",
    "LoadAndModifySharpnessDa", "Process_Shading", "Process_Blinker",
    "Process_Noise", "Process_Sharpness", "Process_Contrast", "Process_Y",
)
GLOBALS = ("g_CurrentProcessingSetti", "g_ProcessingList")
TRANSFER = re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b", re.I)
ADDR_LINE = re.compile(r"^\s*([0-9a-fA-F]+):")


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def component(root: bytes) -> tuple[bytes, bytes, bytes]:
    bf = next((x for x in pwad.parse_pwad(root) if x.name.upper() == "BF561"), None)
    if bf is None:
        raise RuntimeError("outer BF561 missing")
    cmap = {x.name.lower(): x for x in pwad.parse_pwad(bf.data)}
    for n in ("bf0", "bf0.map"):
        if n not in cmap:
            raise RuntimeError(f"BF561 missing {n}")
    return bf.data, cmap["bf0"].data, cmap["bf0.map"].data


def read_overlay(blocks: list[dict], addr: int, size: int) -> bytes:
    """Read initialized/BSS-overlay bytes over possibly adjacent LDR blocks."""
    out = bytearray()
    cur = addr
    end = addr + size
    while cur < end:
        hit = next((b for b in blocks if int(b["addr"]) <= cur < int(b["addr"]) + len(b["payload"])), None)
        if hit is None:
            raise KeyError(f"overlay gap at {cur:#x} reading {addr:#x}+{size:#x}")
        lo = int(hit["addr"]); payload = hit["payload"]
        take = min(end - cur, lo + len(payload) - cur)
        rel = cur - lo
        out += payload[rel:rel+take]
        cur += take
    return bytes(out)


def disassemble_blob(objdump: pathlib.Path, blob: bytes, vma: int, work: pathlib.Path, stem: str) -> str:
    p = work / f"{stem}.bin"
    p.write_bytes(blob)
    r = subprocess.run([str(objdump), "-D", "-b", "binary", "-m", "bfin", f"--adjust-vma={vma:#x}", str(p)], capture_output=True, text=True)
    p.unlink()
    if r.returncode:
        raise RuntimeError(r.stderr)
    return r.stdout


def normalize_disasm(text: str, base: int) -> str:
    """Normalize only displayed instruction addresses to offsets; operands stay exact."""
    out=[]
    for line in text.splitlines():
        m=ADDR_LINE.match(line)
        if m:
            a=int(m.group(1),16)
            line=line[:m.start(1)] + f"+{a-base:04x}" + line[m.end(1):]
        out.append(line)
    return "\n".join(out)


def find_reg_address_contexts(text: str, addr: int) -> list[dict]:
    """Find high/low register constructions for an absolute 32-bit address."""
    hi=(addr>>16)&0xffff; lo=addr&0xffff
    lines=text.splitlines(); out=[]
    hirx=re.compile(rf"\b([PR][0-7])\.H\s*=\s*0x{hi:x}\b",re.I)
    for i,line in enumerate(lines):
        m=hirx.search(line)
        if not m: continue
        reg=m.group(1).upper()
        for j in range(i+1,min(len(lines),i+18)):
            if re.search(rf"\b{reg}\.L\s*=\s*0x{lo:x}\b",lines[j],re.I):
                out.append({"reg":reg,"context":lines[max(0,i-12):min(len(lines),j+28)]})
                break
    return out


def analyse(label: str, fw: bytes, objdump: pathlib.Path, outdir: pathlib.Path) -> dict:
    _bf, ldr, mp = component(fw)
    syms=tr.parse_map(mp); blocks=tr.parse_ldr(ldr)
    work=outdir/f"_{label}_work"; work.mkdir(exist_ok=True)

    globals_out={}
    for name in GLOBALS:
        hits=[s for s in syms if s["name"]==name]
        globals_out[name]=[]
        for s in hits:
            addr=int(s["addr"]); size=int(s["size"])
            raw=read_overlay(blocks,addr,size)
            globals_out[name].append({
                "addr":hex(addr),"size":size,"initial_sha256":sha(raw),
                "initial_nonzero_bytes":sum(x!=0 for x in raw),
                "initial_u32_head":[int.from_bytes(raw[o:o+4],"little") for o in range(0,min(len(raw),64)-3,4)],
            })

    funcs={}
    for name in TARGETS:
        funcs[name]=[]
        for idx,s in enumerate(x for x in syms if x["name"]==name and int(x["size"])>0):
            addr=int(s["addr"]); size=int(s["size"])
            raw=read_overlay(blocks,addr,size)
            dis=disassemble_blob(objdump,raw,addr,work,f"{name}_{idx}_{addr:08x}")
            refs={}
            for g,entries in globals_out.items():
                refs[g]=[]
                for ge in entries:
                    refs[g]+=find_reg_address_contexts(dis,int(ge["addr"],16))
            calls=[]
            for line in dis.splitlines():
                m=TRANSFER.search(line)
                if m: calls.append({"target":hex(int(m.group(1),16)),"line":line})
            funcs[name].append({
                "addr":hex(addr),"size":size,"sha256":sha(raw),
                "normalized_disassembly_sha256":sha(normalize_disasm(dis,addr).encode()),
                "global_address_contexts":refs,"calls":calls,"disassembly":dis,
            })
    for p in work.iterdir(): p.unlink()
    work.rmdir()
    return {"firmware_sha256":sha(fw),"globals":globals_out,"functions":funcs}


def pair_functions(a: dict,b: dict) -> dict:
    out={}
    for name in TARGETS:
        aa=a["functions"].get(name,[]); bb=b["functions"].get(name,[])
        pairs=[]
        for i,x in enumerate(aa):
            best=None
            for j,y in enumerate(bb):
                score=(x["sha256"]==y["sha256"], x["normalized_disassembly_sha256"]==y["normalized_disassembly_sha256"], x["size"]==y["size"])
                if best is None or score>best[0]: best=(score,j,y)
            pairs.append({"a_index":i,"a_addr":x["addr"],"best_b_index":None if best is None else best[1],"b_addr":None if best is None else best[2]["addr"],"byte_identical":False if best is None else best[0][0],"normalized_disassembly_identical":False if best is None else best[0][1],"size_identical":False if best is None else best[0][2]})
        out[name]=pairs
    return out


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("m9_decrypted",type=pathlib.Path)
    ap.add_argument("mm_decrypted",type=pathlib.Path)
    ap.add_argument("--objdump",type=pathlib.Path,required=True)
    ap.add_argument("--outdir",type=pathlib.Path,required=True)
    a=ap.parse_args()
    m9=a.m9_decrypted.read_bytes(); mm=a.mm_decrypted.read_bytes()
    if sha(m9)!=M9_DEC_SHA: raise SystemExit(f"M9 decrypted SHA mismatch: {sha(m9)}")
    if sha(mm)!=MM_DEC_SHA: raise SystemExit(f"MM decrypted SHA mismatch: {sha(mm)}")
    a.outdir.mkdir(parents=True,exist_ok=True)
    m9r=analyse("m9",m9,a.objdump,a.outdir)
    mmr=analyse("mm",mm,a.objdump,a.outdir)
    pairs=pair_functions(m9r,mmr)
    report={
        "schema":"mmonochrom.processinglist.runtime-crosscamera1a.v1",
        "classification":"direct_BF561_symbol_function_and_global_comparison",
        "m9":m9r,"monochrom":mmr,"crosscamera_function_pairs":pairs,
        "questions":[
            "Are SPI job ingestion and processing-list functions byte-identical between M9 and M Monochrom?",
            "Which functions directly reference g_CurrentProcessingSetti/g_ProcessingList?",
            "Can independently closed M9 job-record semantics be transferred to Monochrom BF561 without transferring the differing BF547 controller layout?",
        ],
    }
    (a.outdir/"MM_PROCESSINGLIST_RUNTIME_PROBE.json").write_text(json.dumps(report,indent=2)+"\n")
    with (a.outdir/"MM_PROCESSINGLIST_RUNTIME_PROBE.txt").open("w") as f:
        f.write("M Monochrom / M9 BF561 processing-list runtime comparison\n\n")
        f.write("Globals:\n")
        for label,r in (("M9",m9r),("MM",mmr)):
            for g,entries in r["globals"].items():
                for x in entries: f.write(f"{label} {g} {x['addr']} size={x['size']} nonzero={x['initial_nonzero_bytes']} sha={x['initial_sha256']}\n")
        f.write("\nFunction comparison:\n")
        for n,ps in pairs.items():
            for p in ps: f.write(f"{n}: {json.dumps(p,sort_keys=True)}\n")
        for label,r in (("M9",m9r),("MM",mmr)):
            for n,items in r["functions"].items():
                for x in items:
                    f.write(f"\n===== {label} {n} {x['addr']} size={x['size']} sha={x['sha256']} =====\n")
                    for g,ctxs in x["global_address_contexts"].items():
                        if ctxs:
                            f.write(f"-- references {g} --\n")
                            for ctx in ctxs:
                                for line in ctx['context']: f.write(line+"\n")
                    f.write(x['disassembly']+"\n")
    compact={
        "globals":{"m9":m9r["globals"],"mm":mmr["globals"]},
        "pairs":pairs,
        "mm_direct_global_ref_functions":{
            n:[{"addr":x["addr"],"refs":{g:len(v) for g,v in x["global_address_contexts"].items()}} for x in items if any(x["global_address_contexts"].values())]
            for n,items in mmr["functions"].items()
        },
    }
    print(json.dumps(compact,indent=2))


if __name__=="__main__": main()
