#!/usr/bin/env python3
"""Trace M Monochrom BF547 processing-mask source against canonical M9.

Evidence-only. The M9 work independently identified runtime 0xF2C38 as the
4-byte processing-mask template copied into an imaging job record. This probe
checks that exact structural hypothesis in the original M Monochrom 1.022
BF547, compares the static template and serializer neighborhood across cameras,
and discovers all matching address-construction contexts in disassembly.

No firmware bytes are written to the report; only hashes, integer words, bit
sets, equality flags and textual disassembly are retained.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import re
import subprocess
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import M9_DEC_SHA, MM_DEC_SHA  # noqa: E402

RAM = 0x20000
M9_TEMPLATE_RUNTIME = 0xF2C38
M9_SERIALIZER_START = 0x37020
M9_SERIALIZER_END = 0x370C0


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def find_component(root: bytes, name: str) -> bytes:
    want=name.upper(); hits=[]
    def rec(data: bytes, depth: int=0):
        if depth>4 or data[:4]!=b"PWAD": return
        for x in pwad.parse_pwad(data):
            if x.name.upper()==want: hits.append(x.data)
            if x.data[:4]==b"PWAD": rec(x.data,depth+1)
    rec(root)
    if len(hits)!=1: raise RuntimeError(f"{name} hits={len(hits)}")
    return hits[0]


def u32le(b: bytes, off: int) -> int:
    return int.from_bytes(b[off:off+4],"little")


def set_bits(v: int) -> list[int]:
    return [i for i in range(32) if v & (1<<i)]


def all_occurrences(b: bytes, needle: bytes) -> list[int]:
    out=[]; p=0
    while True:
        p=b.find(needle,p)
        if p<0: return out
        out.append(p); p+=1


def disasm(objdump: pathlib.Path, blob: bytes, vma: int, work: pathlib.Path, stem: str) -> list[str]:
    p=work/f"{stem}.bin"; p.write_bytes(blob)
    r=subprocess.run([str(objdump),"-D","-b","binary","-m","bfin",f"--adjust-vma={vma:#x}",str(p)],capture_output=True,text=True,check=True)
    p.unlink()
    return r.stdout.splitlines()


def addr_of(line: str) -> int | None:
    m=re.match(r"^\s*([0-9a-fA-F]+):",line)
    return int(m.group(1),16) if m else None


def contexts_for_template(lines: list[str]) -> list[dict]:
    """Find Blackfin high/low immediate constructions of 0x000f2c38."""
    out=[]
    hi_rx=re.compile(r"\b([PR][0-7])\.H\s*=\s*0xf\b",re.I)
    for i,l in enumerate(lines):
        m=hi_rx.search(l)
        if not m: continue
        reg=m.group(1).upper()
        for j in range(i+1,min(len(lines),i+16)):
            if re.search(rf"\b{reg}\.L\s*=\s*0x2c38\b",lines[j],re.I):
                lo=max(0,i-18); hi=min(len(lines),j+42)
                out.append({"runtime":hex(addr_of(l) or 0),"reg":reg,"context":lines[lo:hi]})
                break
    return out


def slice_text(lines: list[str], loaddr: int, hiaddr: int) -> list[str]:
    out=[]
    for l in lines:
        a=addr_of(l)
        if a is not None and loaddr<=a<hiaddr: out.append(l)
    return out


def summarize_component(root: bytes, objdump: pathlib.Path, work: pathlib.Path, label: str) -> tuple[dict,list[str]]:
    bf=find_component(root,"BF547")
    off=M9_TEMPLATE_RUNTIME-RAM
    if off<0 or off+32>len(bf):
        raise RuntimeError(f"{label}: runtime {M9_TEMPLATE_RUNTIME:#x} outside BF547 size {len(bf):#x}")
    template32=bf[off:off+32]
    word=u32le(bf,off)
    lines=disasm(objdump,bf,RAM,work,label)
    direct=all_occurrences(bf,M9_TEMPLATE_RUNTIME.to_bytes(4,"little"))
    ser_off=M9_SERIALIZER_START-RAM
    ser_end=M9_SERIALIZER_END-RAM
    serial=bf[ser_off:ser_end] if 0<=ser_off<ser_end<=len(bf) else b""
    return ({
        "bf547_size":len(bf),
        "bf547_sha256":sha(bf),
        "template_runtime":hex(M9_TEMPLATE_RUNTIME),
        "template_first_u32":hex(word),
        "template_set_bits":set_bits(word),
        "sharp_bit7_set":bool(word & (1<<7)),
        "shading_bit1_set":bool(word & (1<<1)),
        "blinker_bit2_set":bool(word & (1<<2)),
        "noise_bit6_set":bool(word & (1<<6)),
        "contrast_bit8_set":bool(word & (1<<8)),
        "y_bit9_set":bool(word & (1<<9)),
        "template32_sha256":sha(template32),
        "direct_pointer_u32_occurrence_runtime_offsets":[hex(x+RAM) for x in direct],
        "template_address_construction_contexts":contexts_for_template(lines),
        "serializer_probe_range":[hex(M9_SERIALIZER_START),hex(M9_SERIALIZER_END)],
        "serializer_probe_sha256":sha(serial) if serial else None,
        "serializer_probe_disassembly":slice_text(lines,M9_SERIALIZER_START,M9_SERIALIZER_END),
    },lines)


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("m9_decrypted",type=pathlib.Path)
    ap.add_argument("mm_decrypted",type=pathlib.Path)
    ap.add_argument("--objdump",type=pathlib.Path,required=True)
    ap.add_argument("--outdir",type=pathlib.Path,required=True)
    a=ap.parse_args()
    m9=a.m9_decrypted.read_bytes(); mm=a.mm_decrypted.read_bytes()
    if sha(m9)!=M9_DEC_SHA: raise SystemExit(f"M9 decrypted SHA mismatch {sha(m9)}")
    if sha(mm)!=MM_DEC_SHA: raise SystemExit(f"MM decrypted SHA mismatch {sha(mm)}")
    a.outdir.mkdir(parents=True,exist_ok=True)
    work=a.outdir/"_work"; work.mkdir(exist_ok=True)
    m9r,_=summarize_component(m9,a.objdump,work,"m9")
    mmr,_=summarize_component(mm,a.objdump,work,"mm")
    for p in work.iterdir(): p.unlink()
    work.rmdir()

    report={
        "schema":"mmonochrom.bf547.processmask1a.v1",
        "classification":"direct_MM_static_mask_crosschecked_against_independent_M9_trace",
        "m9":m9r,
        "monochrom":mmr,
        "crosscamera":{
            "bf547_byte_identical":m9r["bf547_sha256"]==mmr["bf547_sha256"],
            "template_first_u32_identical":m9r["template_first_u32"]==mmr["template_first_u32"],
            "template32_identical":m9r["template32_sha256"]==mmr["template32_sha256"],
            "serializer_probe_identical":m9r["serializer_probe_sha256"]==mmr["serializer_probe_sha256"],
            "set_bits_identical":m9r["template_set_bits"]==mmr["template_set_bits"],
        },
        "interpretation_guardrails":[
            "A matching static template and serializer proves the same BF547 job-mask source structure at this location.",
            "It does not by itself prove every capture mode uses this template unchanged; writer/override paths must still be excluded or characterized.",
            "Sharp incoming border is the sum of enabled prior spatial-stage increments actually taken by Run, not simply the Sharp +2 increment.",
        ],
    }
    (a.outdir/"MM_BF547_PROCESS_MASK_PROBE.json").write_text(json.dumps(report,indent=2)+"\n")
    with (a.outdir/"MM_BF547_PROCESS_MASK_PROBE.txt").open("w") as f:
        f.write("M Monochrom BF547 process-mask probe\n\n")
        for label,r in (("M9",m9r),("M Monochrom",mmr)):
            f.write(f"{label}: BF547 sha={r['bf547_sha256']} size={r['bf547_size']}\n")
            f.write(f"  template {r['template_runtime']} first_u32={r['template_first_u32']} bits={r['template_set_bits']}\n")
            f.write(f"  bit1(shading)={r['shading_bit1_set']} bit2(blinker)={r['blinker_bit2_set']} bit6(noise)={r['noise_bit6_set']} bit7(sharp)={r['sharp_bit7_set']} bit8(contrast)={r['contrast_bit8_set']} bit9(Y)={r['y_bit9_set']}\n")
            f.write(f"  template32 sha={r['template32_sha256']} serializer sha={r['serializer_probe_sha256']}\n")
            f.write("  template address constructions:\n")
            for c in r['template_address_construction_contexts']:
                f.write(f"    runtime={c['runtime']} reg={c['reg']}\n")
                for line in c['context']: f.write("      "+line+"\n")
            f.write("  serializer range disassembly:\n")
            for line in r['serializer_probe_disassembly']: f.write("    "+line+"\n")
        f.write("\nCross-camera:\n"+json.dumps(report['crosscamera'],indent=2)+"\n")
    print(json.dumps({"m9":{"bf547_sha":m9r['bf547_sha256'],"mask":m9r['template_first_u32'],"bits":m9r['template_set_bits']},"mm":{"bf547_sha":mmr['bf547_sha256'],"mask":mmr['template_first_u32'],"bits":mmr['template_set_bits']},"crosscamera":report['crosscamera']},indent=2))


if __name__=="__main__": main()
