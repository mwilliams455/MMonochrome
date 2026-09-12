#!/usr/bin/env python3
"""Trace direct, literal, and split-immediate BF547 references for settings lifecycle.

Targets include the original M Monochrom settings serializer, the two routines
that initialize object+0x35c from incoming R1, and the reset routine that can
zero object+0x35c.  Blackfin code may materialize targets as H/L halves before
an indirect CALL/JUMP, so simple absolute CALL/literal searches are insufficient.

The M9 homolog targets are scanned as a structural control. No firmware bytes
are emitted.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, struct, subprocess, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import M9_DEC_SHA, MM_DEC_SHA  # noqa: E402
RAM=0x20000
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')
CALL_DIRECT_RE=re.compile(r'\bCALL\s+(?:0x0x|0x)?([0-9a-fA-F]+)',re.I)

def sha(b):return hashlib.sha256(b).hexdigest()
def comp(root):
    hits=[]
    def rec(d,depth=0):
        if depth>4 or d[:4]!=b'PWAD':return
        for x in pwad.parse_pwad(d):
            if x.name.upper()=='BF547':hits.append(x.data)
            if x.data[:4]==b'PWAD':rec(x.data,depth+1)
    rec(root)
    if len(hits)!=1:raise RuntimeError(f'BF547 hits={len(hits)}')
    return hits[0]
def disasm(objdump,b,work,stem):
    p=work/f'{stem}.bin';p.write_bytes(b)
    r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],capture_output=True,text=True,check=True);p.unlink();return r.stdout.splitlines()
def ao(l):
    m=ADDR_RE.match(l);return int(m.group(1),16) if m else 0

def refs_for(lines,bf,target):
    high=(target>>16)&0xffff;low=target&0xffff
    direct=[]
    for i,l in enumerate(lines):
        m=CALL_DIRECT_RE.search(l)
        if m and int(m.group(1),16)==target:
            direct.append({'site':hex(ao(l)),'context':lines[max(0,i-22):min(len(lines),i+18)]})
    literal=[];needle=struct.pack('<I',target);p=0
    while True:
        p=bf.find(needle,p)
        if p<0:break
        literal.append(hex(RAM+p));p+=1
    # Pair target halves loaded to same R/P register in either order within a
    # 16-instruction window. Keep broader context so any CALL/JUMP through that
    # register is visible without assigning semantics automatically.
    split=[]
    hi_re=re.compile(rf'\b([RP][0-7])\.H\s*=\s*0x{high:x}\b',re.I)
    lo_re=re.compile(rf'\b([RP][0-7])\.L\s*=\s*0x{low:x}\b',re.I)
    for i,l in enumerate(lines):
        first_h=hi_re.search(l);first_l=lo_re.search(l)
        if not(first_h or first_l):continue
        reg=(first_h or first_l).group(1).upper()
        for j in range(i+1,min(len(lines),i+17)):
            second=(lo_re.search(lines[j]) if first_h else hi_re.search(lines[j]))
            if second and second.group(1).upper()==reg:
                ctx=lines[max(0,i-18):min(len(lines),j+32)]
                indirect=[x for x in ctx if re.search(rf'\b(?:CALL|JUMP)\s*\(\s*{reg}\s*\)',x,re.I)]
                split.append({'first_site':hex(ao(l)),'second_site':hex(ao(lines[j])),'register':reg,'indirect_transfers_in_context':indirect,'context':ctx})
                break
    return {'target':hex(target),'direct_calls':direct,'literal_u32_hits':literal,'split_immediate_hits':split}

def analyse(label,fw,objdump,work,targets):
    bf=comp(fw);lines=disasm(objdump,bf,work,label)
    return {'bf547_sha256':sha(bf),'targets':{name:refs_for(lines,bf,t) for name,t in targets.items()}}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('m9_decrypted',type=pathlib.Path);ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    m9=a.m9_decrypted.read_bytes();mm=a.mm_decrypted.read_bytes()
    if sha(m9)!=M9_DEC_SHA:raise SystemExit('M9 SHA mismatch')
    if sha(mm)!=MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
    a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/'_work';work.mkdir(exist_ok=True)
    # M9 homologs are +0x7c serializer, +0x58 constructors, and reset +0x1dc.
    # The reset homolog address is observed directly from the prior byte trace.
    m9t={'serializer':0x37070,'ctor_a':0x37a68,'ctor_b':0x37ad0,'reset_35c':0x9673a}
    mmt={'serializer':0x36ff4,'ctor_a':0x37a10,'ctor_b':0x37a78,'reset_35c':0x96916}
    mr=analyse('m9',m9,a.objdump,work,m9t);xr=analyse('mm',mm,a.objdump,work,mmt)
    for p in work.iterdir():p.unlink()
    work.rmdir()
    report={'schema':'mmonochrom.bf547.settings-lifecycle-indirect-xrefs1a.v1','m9':mr,'monochrom':xr,'guardrails':['A split-immediate address construction is an xref candidate; it becomes an invocation only when subsequent register flow reaches an indirect CALL/JUMP.','reset_35c target is the store site, not necessarily the enclosing function entry.','M9 homologs are structural controls only.']}
    (a.outdir/'MM_BF547_INDIRECT_XREFS.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF547_INDIRECT_XREFS.txt').open('w') as f:
        for lab,r in (('M9',mr),('MM',xr)):
            f.write(f'===== {lab} =====\n')
            for n,x in r['targets'].items():
                f.write(f'\n--- {n} {x["target"]} ---\n')
                f.write(json.dumps({'direct_calls':x['direct_calls'],'literal_u32_hits':x['literal_u32_hits'],'split_immediate_hits':x['split_immediate_hits']},indent=2)+'\n')
    print(json.dumps({lab:{n:{'direct':len(x['direct_calls']),'literal':len(x['literal_u32_hits']),'split':len(x['split_immediate_hits']),'indirect_transfer_contexts':sum(bool(y['indirect_transfers_in_context']) for y in x['split_immediate_hits'])} for n,x in r['targets'].items()} for lab,r in [('m9',mr),('mm',xr)]},indent=2))
if __name__=='__main__':main()
