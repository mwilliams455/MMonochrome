#!/usr/bin/env python3
"""Trace persistent M Monochrom BF547 Processing-Settings state.

The shot builder at 0x39f1c proves the transmitted 37-byte record lives at
state+0x12c and refreshes only selected dynamic fields.  This probe finds the
persistent initializer/setter paths for that state, especially mask bytes 0..3,
Sharpness candidate +0x0c, and proven nNoise +0x0d.  It also traces callers of
0x3a010/0x39f1c so the owning camera-state object can be distinguished from the
special MARKER serializer path.

Evidence-only: no firmware bytes are emitted.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import MM_DEC_SHA  # noqa: E402

RAM=0x20000
TARGETS=(0x3a010,0x39f1c,0x36fe4,0x6d2a8)
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')
TRANSFER_RE=re.compile(r'\b(CALL|JUMP(?:\.L|\.S)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)',re.I)
IMM12C_RE=re.compile(r'\b([PR][0-7])\s*=\s*0x12c\b',re.I)
STORE_RE=re.compile(r'\b(?:B|W)?\[([^\]]+)\]\s*=')
LOAD_RE=re.compile(r'=\s*(?:B|W)?\[([^\]]+)\]')

def sha(b): return hashlib.sha256(b).hexdigest()
def comp(root):
    hits=[]
    def rec(d,k=0):
        if k>4 or d[:4]!=b'PWAD': return
        for x in pwad.parse_pwad(d):
            if x.name.upper()=='BF547': hits.append(x.data)
            if x.data[:4]==b'PWAD': rec(x.data,k+1)
    rec(root)
    if len(hits)!=1: raise RuntimeError(f'BF547 hits={len(hits)}')
    return hits[0]
def disasm(objdump,b,w):
    p=w/'bf547.bin'; p.write_bytes(b)
    r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],capture_output=True,text=True,check=True)
    p.unlink(); return r.stdout.splitlines()
def ao(l):
    m=ADDR_RE.match(l); return int(m.group(1),16) if m else -1

def context(lines,i,before=70,after=110): return lines[max(0,i-before):min(len(lines),i+after)]
def xrefs(lines,target):
    out=[]
    for i,l in enumerate(lines):
        m=TRANSFER_RE.search(l)
        if m and int(m.group(2),16)==target:
            out.append({'site':hex(ao(l)),'kind':m.group(1),'context':context(lines,i,100,65)})
    return out

def imm12c_contexts(lines):
    out=[]
    for i,l in enumerate(lines):
        m=IMM12C_RE.search(l)
        if not m: continue
        reg=m.group(1).upper(); ctx=context(lines,i,80,150)
        # Highlight expressions using the register as an additive base and stores/loads soon after.
        uses=[x for x in ctx if re.search(rf'\b{reg}\b',x,re.I)]
        stores=[x for x in ctx if STORE_RE.search(x)]
        out.append({'site':hex(ao(l)),'register':reg,'uses':uses,'stores':stores,'context':ctx})
    return out

def field_accesses(lines,offhex):
    # Broad inventory of explicit +offset byte accesses; semantics require nearby state+0x12c provenance.
    pat=re.compile(rf'\b([PR][0-7])\s*\+\s*0x{offhex}\b',re.I)
    out=[]
    for i,l in enumerate(lines):
        if pat.search(l):
            out.append({'site':hex(ao(l)),'line':l,'context':context(lines,i,45,55)})
    return out

def firstword_patterns(lines):
    # Candidate fullword stores and OR/bit-set operations near any state+0x12c construction.
    out=[]
    for block in imm12c_contexts(lines):
        c=block['context']
        candidates=[x for x in c if ('[P' in x or '[R' in x) and ('=' in x) and any(tok in x for tok in ('BITSET','BITCLR','|','&','[P','[R'))]
        out.append({'site':block['site'],'candidates':candidates})
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('mm_decrypted',type=pathlib.Path); ap.add_argument('--objdump',type=pathlib.Path,required=True); ap.add_argument('--outdir',type=pathlib.Path,required=True); a=ap.parse_args()
    mm=a.mm_decrypted.read_bytes()
    if sha(mm)!=MM_DEC_SHA: raise SystemExit('MM SHA mismatch')
    bf=comp(mm); a.outdir.mkdir(parents=True,exist_ok=True); w=a.outdir/'_work'; w.mkdir(exist_ok=True)
    lines=disasm(a.objdump,bf,w)
    for p in w.iterdir(): p.unlink()
    w.rmdir()
    refs={hex(t):xrefs(lines,t) for t in TARGETS}
    i12=imm12c_contexts(lines)
    report={
        'schema':'mmonochrom.bf547.persistent-processing-settings1a.v1',
        'bf547_sha256':sha(bf),
        'known_record':{'base_expression':'state + 0x12c','bytes':37,'process_mask_offset':'0x00..0x03','nNoise_offset':'0x0d'},
        'transfer_xrefs':refs,
        'imm_0x12c_contexts':i12,
        'field_0x0c_accesses':field_accesses(lines,'c'),
        'field_0x0d_accesses':field_accesses(lines,'d'),
        'firstword_candidate_patterns':firstword_patterns(lines),
        'classification':'persistent_state_initializer_and_setter_evidence',
        'guardrails':[
            'An explicit +0x0c/+0x0d access is not a Processing-Settings field unless its base is proven to state+0x12c or the 37-byte payload pointer.',
            'The 0x36fe4 MARKER path is special-case evidence and must not be treated as the normal process-mask initializer without a normal-still control-flow proof.',
            'Do not promote Android Sharpness/Noise until normal still/JPEG mask and persistent field values are closed.'
        ]
    }
    (a.outdir/'MM_BF547_PERSISTENT_PROCESSING_SETTINGS.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF547_PERSISTENT_PROCESSING_SETTINGS.txt').open('w') as f:
        f.write(json.dumps({'xrefs':{k:[(x['site'],x['kind']) for x in v] for k,v in refs.items()},'imm_0x12c_sites':[x['site'] for x in i12],'field0c_count':len(report['field_0x0c_accesses']),'field0d_count':len(report['field_0x0d_accesses'])},indent=2)+'\n')
        for t,rows in refs.items():
            f.write(f'\n===== XREFS {t} =====\n'+json.dumps(rows,indent=2)+'\n')
        for x in i12:
            f.write(f"\n===== IMM 0x12c {x['site']} reg={x['register']} =====\n"+'\n'.join(x['context'])+'\n')
        f.write('\n===== +0x0c ACCESSES =====\n'+json.dumps(report['field_0x0c_accesses'],indent=2)+'\n')
        f.write('\n===== +0x0d ACCESSES =====\n'+json.dumps(report['field_0x0d_accesses'],indent=2)+'\n')
    print(json.dumps({'xrefs':{k:[(x['site'],x['kind']) for x in v] for k,v in refs.items()},'imm_0x12c_sites':[x['site'] for x in i12],'field0c_count':len(report['field_0x0c_accesses']),'field0d_count':len(report['field_0x0d_accesses'])},indent=2))
if __name__=='__main__': main()
