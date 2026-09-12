#!/usr/bin/env python3
"""Trace callers that feed the real 37-byte BF547 Processing-Settings payload.

Prior evidence closes 0x6d2a8 as a function that accepts the payload in R1,
then sends that same pointer with SportNet selector 0x04 / length 0x25 to both
controller endpoints through 0x696b4.  This probe works one level upstream:
find every direct/indirect reference to 0x6d2a8, preserve broad caller context,
and expose preparation of R1 / the payload object without publishing firmware
bytes.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import MM_DEC_SHA  # noqa: E402

RAM=0x20000
TARGET=0x6d2a8
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')
CALL_RE=re.compile(r'\bCALL\s+(?:0x0x|0x)?([0-9a-fA-F]+)',re.I)
PROLOGUE_RE=re.compile(r'\[--SP\].*\(R7:|\bLINK\b',re.I)

def sha(b): return hashlib.sha256(b).hexdigest()
def component(root):
    hits=[]
    def rec(d,depth=0):
        if depth>4 or d[:4]!=b'PWAD': return
        for x in pwad.parse_pwad(d):
            if x.name.upper()=='BF547': hits.append(x.data)
            if x.data[:4]==b'PWAD': rec(x.data,depth+1)
    rec(root)
    if len(hits)!=1: raise RuntimeError(f'BF547 hits={len(hits)}')
    return hits[0]
def disasm(objdump,b,work):
    p=work/'bf547.bin';p.write_bytes(b)
    r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],capture_output=True,text=True,check=True)
    p.unlink(); return r.stdout.splitlines()
def ao(l):
    m=ADDR_RE.match(l); return int(m.group(1),16) if m else -1

def nearest_function_start(lines,idx):
    # Strongest Blackfin prologue form is a register save followed shortly by LINK.
    for i in range(idx, max(-1,idx-900), -1):
        if '[--SP]' in lines[i] and any('LINK' in lines[j] for j in range(i,min(len(lines),i+8))):
            return ao(lines[i]), i
    return None, max(0,idx-180)

def direct_callers(lines):
    out=[]
    for i,l in enumerate(lines):
        m=CALL_RE.search(l)
        if not(m and int(m.group(1),16)==TARGET): continue
        fs,fi=nearest_function_start(lines,i)
        ctx=lines[max(fi,i-220):min(len(lines),i+140)]
        r1_lines=[x for x in lines[max(fi,i-120):i] if re.search(r'\bR1\s*=|\bR1\.[HL]\s*=|\bR1\s*=',x,re.I)]
        pointer_ops=[x for x in lines[max(fi,i-160):i] if re.search(r'\b(?:P[0-5]|R1)\b',x,re.I) and ('[' in x or '=' in x)]
        out.append({'call_site':hex(ao(l)),'caller_start':hex(fs) if fs is not None else None,'r1_preparation_lines':r1_lines[-20:],'pointer_preparation_tail':pointer_ops[-45:],'context':ctx})
    return out

def split_refs(lines):
    hi=(TARGET>>16)&0xffff;lo=TARGET&0xffff
    hi_re=re.compile(rf'\b([RP][0-7])\.H\s*=\s*0x{hi:x}\b',re.I)
    lo_re=re.compile(rf'\b([RP][0-7])\.L\s*=\s*0x{lo:x}\b',re.I)
    out=[]
    for i,l in enumerate(lines):
        a=hi_re.search(l);b=lo_re.search(l)
        if not(a or b): continue
        reg=(a or b).group(1).upper()
        for j in range(i+1,min(len(lines),i+20)):
            c=lo_re.search(lines[j]) if a else hi_re.search(lines[j])
            if c and c.group(1).upper()==reg:
                ctx=lines[max(0,i-35):min(len(lines),j+65)]
                out.append({'first_site':hex(ao(l)),'second_site':hex(ao(lines[j])),'register':reg,'indirect_transfers':[x for x in ctx if re.search(rf'\b(?:CALL|JUMP)\s*\(\s*{reg}\s*\)',x,re.I)],'context':ctx})
                break
    return out

def target_window(lines):
    idx=next((i for i,l in enumerate(lines) if ao(l)==TARGET),None)
    if idx is None:return []
    return lines[max(0,idx-15):min(len(lines),idx+360)]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    mm=a.mm_decrypted.read_bytes()
    if sha(mm)!=MM_DEC_SHA: raise SystemExit('MM SHA mismatch')
    bf=component(mm);a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/'_work';work.mkdir(exist_ok=True)
    lines=disasm(a.objdump,bf,work)
    for p in work.iterdir():p.unlink()
    work.rmdir()
    callers=direct_callers(lines);split=split_refs(lines)
    report={'schema':'mmonochrom.bf547.processing-payload-producer1a.v1','bf547_sha256':sha(bf),'target':hex(TARGET),'target_contract_from_prior_trace':{'arg0_R0':'controller/context','arg1_R1':'37-byte Processing-Settings payload','arg2_R2':'output/result structure','sportnet_selector':4,'sportnet_payload_bytes':37},'target_window':target_window(lines),'direct_callers':callers,'split_immediate_refs':split,'classification':'upstream_payload_provenance_evidence','guardrails':['R1 is established as the transmitted payload pointer by the prior request-builder trace.','Do not infer payload first-u32 value from field names or M9 defaults; recover actual stores/copies in the caller.','Do not alter Android sharpness until the normal still/JPEG process mask and Noise state are direct evidence.']}
    (a.outdir/'MM_BF547_PROCESSING_PAYLOAD_PRODUCER.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF547_PROCESSING_PAYLOAD_PRODUCER.txt').open('w') as f:
        f.write(json.dumps({'target':hex(TARGET),'direct_caller_sites':[x['call_site'] for x in callers],'caller_starts':[x['caller_start'] for x in callers],'split_ref_count':len(split)},indent=2)+'\n')
        f.write('\n===== TARGET WINDOW =====\n'+'\n'.join(report['target_window'])+'\n')
        for x in callers:
            f.write(f"\n===== CALLER {x['caller_start']} -> {x['call_site']} =====\n")
            f.write('R1 PREP:\n'+'\n'.join(x['r1_preparation_lines'])+'\n')
            f.write('POINTER PREP TAIL:\n'+'\n'.join(x['pointer_preparation_tail'])+'\n')
            f.write('CONTEXT:\n'+'\n'.join(x['context'])+'\n')
        f.write('\n===== SPLIT REFS =====\n'+json.dumps(split,indent=2)+'\n')
    print(json.dumps({'direct_caller_sites':[x['call_site'] for x in callers],'caller_starts':[x['caller_start'] for x in callers],'split_ref_count':len(split)},indent=2))
if __name__=='__main__': main()
