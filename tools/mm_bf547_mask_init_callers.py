#!/usr/bin/env python3
"""Trace callers of the BF547 routines that initialize object+0x35c.

The low process-mask byte serialized to BF561 comes from object+0x35c. Two
nearby Monochrom constructors store incoming R1 directly into that field. This
probe discovers their exact entries from the characteristic `P0 = R0; P2=0x54;
push; LINK` prologue, all direct callsites, and literal function-pointer
references. The same extraction is performed on the homologous M9 cluster only
as a structural control. No firmware bytes are emitted.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, struct, subprocess, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import M9_DEC_SHA, MM_DEC_SHA  # noqa: E402

RAM=0x20000
CALL_RE=re.compile(r'\bCALL\s+(?:0x0x|0x)?([0-9a-fA-F]+)',re.I)
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')
RTS_RE=re.compile(r'\bRTS\b',re.I)
STORE35C=re.compile(r'\[[^\]]+\+\s*0x35c\]\s*=\s*R1\b',re.I)
PROLOGUE_P0=re.compile(r'\bP0\s*=\s*R0\s*;',re.I)
PROLOGUE_54=re.compile(r'\bP2\s*=\s*0x54\b',re.I)

def sha(b): return hashlib.sha256(b).hexdigest()
def find_component(root,name):
    want=name.upper();hits=[]
    def rec(data,depth=0):
        if depth>4 or data[:4]!=b'PWAD': return
        for x in pwad.parse_pwad(data):
            if x.name.upper()==want: hits.append(x.data)
            if x.data[:4]==b'PWAD': rec(x.data,depth+1)
    rec(root)
    if len(hits)!=1: raise RuntimeError(f'{name} hits={len(hits)}')
    return hits[0]
def disasm(objdump,blob,work,stem):
    p=work/f'{stem}.bin';p.write_bytes(blob)
    r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],capture_output=True,text=True,check=True);p.unlink();return r.stdout.splitlines()
def addr_of(line):
    m=ADDR_RE.match(line);return int(m.group(1),16) if m else None

def constructor_entry(lines,idx):
    for j in range(idx-1,max(-1,idx-70),-1):
        if not PROLOGUE_P0.search(lines[j]): continue
        if any(PROLOGUE_54.search(lines[k]) for k in range(j+1,min(idx,j+8))) and any('LINK' in lines[k] for k in range(j+1,min(idx,j+14))):
            return addr_of(lines[j])
    return None

def direct_calls(lines,entries):
    out={hex(e):[] for e in entries}
    for i,l in enumerate(lines):
        m=CALL_RE.search(l)
        if not m: continue
        t=int(m.group(1),16)
        if t in entries:
            out[hex(t)].append({'site':hex(addr_of(l) or 0),'context':lines[max(0,i-32):min(len(lines),i+18)]})
    return out

def pointer_hits(bf,entries):
    out={hex(e):[] for e in entries}
    for e in entries:
        needle=struct.pack('<I',e);p=0
        while True:
            p=bf.find(needle,p)
            if p<0: break
            out[hex(e)].append(hex(RAM+p));p+=1
    return out

def analyse(label,fw,objdump,work,lo,hi):
    bf=find_component(fw,'BF547');lines=disasm(objdump,bf,work,label)
    stores=[];entries=[]
    for i,l in enumerate(lines):
        a=addr_of(l)
        if a is None or not(lo<=a<hi) or not STORE35C.search(l): continue
        ent=constructor_entry(lines,i)
        stores.append({'site':hex(a),'entry':None if ent is None else hex(ent),'context':lines[max(0,i-34):min(len(lines),i+36)]})
        if ent is not None: entries.append(ent)
    entries=sorted(set(entries));calls=direct_calls(lines,set(entries));ptrs=pointer_hits(bf,entries)
    funcs=[]
    for e in entries:
        start=next((i for i,l in enumerate(lines) if addr_of(l)==e),None);body=[]
        if start is not None:
            for l in lines[start:start+180]:
                body.append(l)
                if RTS_RE.search(l): break
        funcs.append({'entry':hex(e),'body':body})
    ptr_neighborhoods={}
    for e in entries:
        rows=[]
        for phex in ptrs[hex(e)]:
            p=int(phex,16)-RAM;loff=max(0,(p-32)&~3);hoff=min(len(bf)-4,p+36);vals=[]
            for o in range(loff,hoff+1,4):
                vals.append({'addr':hex(RAM+o),'value':hex(struct.unpack_from('<I',bf,o)[0]),'relative_words':(o-p)//4})
            rows.append({'pointer_addr':phex,'u32_neighborhood':vals})
        ptr_neighborhoods[hex(e)]=rows
    return {'bf547_sha256':sha(bf),'range':[hex(lo),hex(hi)],'stores':stores,'entries':[hex(e) for e in entries],'functions':funcs,'direct_callsites':calls,'literal_pointer_hits':ptrs,'literal_pointer_neighborhoods':ptr_neighborhoods}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('m9_decrypted',type=pathlib.Path);ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    m9=a.m9_decrypted.read_bytes();mm=a.mm_decrypted.read_bytes()
    if sha(m9)!=M9_DEC_SHA: raise SystemExit('M9 SHA mismatch')
    if sha(mm)!=MM_DEC_SHA: raise SystemExit('MM SHA mismatch')
    a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/'_work';work.mkdir(exist_ok=True)
    m9r=analyse('m9',m9,a.objdump,work,0x37a00,0x37b40);mmr=analyse('mm',mm,a.objdump,work,0x379a0,0x37ae0)
    for p in work.iterdir(): p.unlink()
    work.rmdir()
    report={'schema':'mmonochrom.bf547.mask-init-callers1b.v1','classification':'constructor_prologue_direct_caller_and_function_pointer_trace','m9':m9r,'monochrom':mmr,'guardrails':['R1 becomes the low process-mask byte only for the object instance later serialized by the confirmed 0x36ff4 routine.','Direct calls and literal pointers are distinct invocation mechanisms.','M9 validates homologous structure but does not supply Monochrom values.'],'next_questions':['Which vtable/dispatcher owns any constructor pointer reference?','Which invocation supplies the normal Monochrom object and exact R1?','Are bits 6/7 altered after constructor and before serializer?']}
    (a.outdir/'MM_BF547_MASK_INIT_CALLERS.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF547_MASK_INIT_CALLERS.txt').open('w') as f:
        for lab,r in (('M9',m9r),('MM',mmr)):
            f.write(f'===== {lab} entries/stores =====\n'+json.dumps({'entries':r['entries'],'stores':r['stores']},indent=2)+'\n')
            f.write(f'\n===== {lab} direct callsites =====\n'+json.dumps(r['direct_callsites'],indent=2)+'\n')
            f.write(f'\n===== {lab} pointer hits =====\n'+json.dumps(r['literal_pointer_hits'],indent=2)+'\n')
            f.write(f'\n===== {lab} pointer neighborhoods =====\n'+json.dumps(r['literal_pointer_neighborhoods'],indent=2)+'\n')
    print(json.dumps({'m9_entries':m9r['entries'],'mm_entries':mmr['entries'],'m9_call_counts':{k:len(v) for k,v in m9r['direct_callsites'].items()},'mm_call_counts':{k:len(v) for k,v in mmr['direct_callsites'].items()},'m9_pointer_hits':m9r['literal_pointer_hits'],'mm_pointer_hits':mmr['literal_pointer_hits']},indent=2))
if __name__=='__main__': main()
