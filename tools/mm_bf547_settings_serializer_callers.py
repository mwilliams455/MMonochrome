#!/usr/bin/env python3
"""Trace callers of the original M Monochrom BF547 settings serializer.

The serializer at 0x36ff4 is proven to place object+0x35c into packet payload
byte zero, which BF561 receives as processing-record byte zero.  This probe
finds all direct calls and literal function pointers to that serializer, plus
its M9 homolog 0x37070, and emits caller-side setup around R0/R1/R2.

No firmware bytes are emitted.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, struct, subprocess, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import M9_DEC_SHA, MM_DEC_SHA  # noqa: E402

RAM=0x20000
M9_SERIALIZER=0x37070
MM_SERIALIZER=0x36ff4
CALL_RE=re.compile(r'\bCALL\s+(?:0x0x|0x)?([0-9a-fA-F]+)',re.I)
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')

def sha(b):return hashlib.sha256(b).hexdigest()
def comp(root):
    want='BF547';hits=[]
    def rec(d,depth=0):
        if depth>4 or d[:4]!=b'PWAD':return
        for x in pwad.parse_pwad(d):
            if x.name.upper()==want:hits.append(x.data)
            if x.data[:4]==b'PWAD':rec(x.data,depth+1)
    rec(root)
    if len(hits)!=1:raise RuntimeError(f'BF547 hits={len(hits)}')
    return hits[0]
def disasm(objdump,b,work,stem):
    p=work/f'{stem}.bin';p.write_bytes(b)
    r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],capture_output=True,text=True,check=True);p.unlink();return r.stdout.splitlines()
def addr(line):
    m=ADDR_RE.match(line);return int(m.group(1),16) if m else 0
def analyse(label,fw,objdump,work,target):
    bf=comp(fw);lines=disasm(objdump,bf,work,label);calls=[]
    for i,l in enumerate(lines):
        m=CALL_RE.search(l)
        if m and int(m.group(1),16)==target:
            calls.append({'site':hex(addr(l)),'context':lines[max(0,i-42):min(len(lines),i+26)]})
    ptr=[];needle=struct.pack('<I',target);p=0
    while True:
        p=bf.find(needle,p)
        if p<0:break
        ptr.append(hex(RAM+p));p+=1
    # serializer body until RTS
    start=next(i for i,l in enumerate(lines) if addr(l)==target);body=[]
    for l in lines[start:start+180]:
        body.append(l)
        if re.search(r'\bRTS\b',l):break
    return {'bf547_sha256':sha(bf),'serializer':hex(target),'direct_callsites':calls,'literal_pointer_hits':ptr,'serializer_body':body}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('m9_decrypted',type=pathlib.Path);ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    m9=a.m9_decrypted.read_bytes();mm=a.mm_decrypted.read_bytes()
    if sha(m9)!=M9_DEC_SHA:raise SystemExit('M9 SHA mismatch')
    if sha(mm)!=MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
    a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/'_work';work.mkdir(exist_ok=True)
    m9r=analyse('m9',m9,a.objdump,work,M9_SERIALIZER);mmr=analyse('mm',mm,a.objdump,work,MM_SERIALIZER)
    for p in work.iterdir():p.unlink()
    work.rmdir()
    report={'schema':'mmonochrom.bf547.settings-serializer-callers1a.v1','m9':m9r,'monochrom':mmr,'known_chain':['serializer payload byte0 <- object+0x35c','BF561 SPI_AppendSettings payload byte0 -> processing-record byte0','Run process mask = processing-record u32@0'],'guardrails':['Direct-call absence does not exclude indirect invocation; literal pointers are reported separately.','M9 is structural control only.'],'next_questions':['Which normal still-capture state machine invokes the serializer?','Does its object pointer originate in the initializer whose R1 writes +0x35c?','Is any +0x35c writer reachable between initializer and serializer?']}
    (a.outdir/'MM_BF547_SETTINGS_SERIALIZER_CALLERS.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF547_SETTINGS_SERIALIZER_CALLERS.txt').open('w') as f:
        for lab,r in (('M9',m9r),('MM',mmr)):
            f.write(f'===== {lab} serializer {r["serializer"]} =====\n')
            f.write('DIRECT CALLS\n'+json.dumps(r['direct_callsites'],indent=2)+'\n')
            f.write('POINTER HITS\n'+json.dumps(r['literal_pointer_hits'],indent=2)+'\n')
            f.write('BODY\n'+'\n'.join(r['serializer_body'])+'\n\n')
    print(json.dumps({'m9_direct_calls':len(m9r['direct_callsites']),'mm_direct_calls':len(mmr['direct_callsites']),'m9_pointer_hits':m9r['literal_pointer_hits'],'mm_pointer_hits':mmr['literal_pointer_hits']},indent=2))
if __name__=='__main__':main()
