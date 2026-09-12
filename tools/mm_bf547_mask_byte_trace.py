#!/usr/bin/env python3
"""Trace the BF547 field serialized as process-mask byte 0.

BF561 SPI_AppendSettings copies packet+7 into the 68-byte processing record,
where Run consumes the first u32 as the process mask.  Controller serializer
code writes packet payload byte 0 at object+0x133.  In the M9 control this is
loaded from object+0x35c, while payload byte 1 is 0xff and bytes 2/3 come from
other controller fields.  This probe discovers/validates that relationship in
both M9 and original M Monochrom and enumerates all direct BF547 accesses to the
0x35c field, with nearby bit operations and constants.

No firmware bytes are emitted.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, subprocess, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import M9_DEC_SHA, MM_DEC_SHA  # noqa: E402

RAM=0x20000
OFFSETS=(0x133,0x134,0x135,0x136,0x35c,0x40,0x440)
ADDR=re.compile(r'^\s*([0-9a-fA-F]+):')
MEM=re.compile(r'\b([BWL])\[([PIS][0-7P]?)[ ]*\+[ ]*0x([0-9a-fA-F]+)\]',re.I)

def sha(b):return hashlib.sha256(b).hexdigest()
def find_component(root,name):
    want=name.upper();hits=[]
    def rec(data,depth=0):
        if depth>4 or data[:4]!=b'PWAD':return
        for x in pwad.parse_pwad(data):
            if x.name.upper()==want:hits.append(x.data)
            if x.data[:4]==b'PWAD':rec(x.data,depth+1)
    rec(root)
    if len(hits)!=1:raise RuntimeError(f'{name} hits={len(hits)}')
    return hits[0]
def disasm(objdump,blob,work,stem):
    p=work/f'{stem}.bin';p.write_bytes(blob)
    r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],capture_output=True,text=True,check=True);p.unlink();return r.stdout.splitlines()
def aof(line):
    m=ADDR.match(line);return int(m.group(1),16) if m else 0

def analyse(label,fw,objdump,work):
    bf=find_component(fw,'BF547'); lines=disasm(objdump,bf,work,label)
    hits={hex(o):[] for o in OFFSETS}
    for i,line in enumerate(lines):
        # objdump may spell byte/word/long memory operands differently, so use
        # a direct +0xNN token test as the primary locator.
        for o in OFFSETS:
            if re.search(rf'\+\s*0x{o:x}\b',line,re.I):
                hits[hex(o)].append({'addr':hex(aof(line)),'line':line,'context':lines[max(0,i-20):min(len(lines),i+34)]})
    # Serializer anchors: stores to +0x133 then +0x134 nearby.
    serializers=[]
    for i,line in enumerate(lines):
        if not re.search(r'B\[[^\]]+\+\s*0x133\]\s*=',line,re.I):continue
        if not any(re.search(r'B\[[^\]]+\+\s*0x134\]\s*=',lines[j],re.I) for j in range(i,min(len(lines),i+18))):continue
        serializers.append({'addr':hex(aof(line)),'context':lines[max(0,i-45):min(len(lines),i+80)]})
    # Direct 0x35c accesses labelled as syntactic loads/stores.
    field=[]
    for h in hits[hex(0x35c)]:
        line=h['line']; eq=line.find('='); mem=line.lower().find('+ 0x35c')
        kind='unknown'
        if eq>=0 and mem>=0:kind='store' if mem<eq else 'load'
        field.append({**h,'kind':kind})
    return {'bf547_sha256':sha(bf),'bf547_size':len(bf),'offset_accesses':hits,'serializer_anchors':serializers,'mask_byte0_field_35c_accesses':field}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('m9_decrypted',type=pathlib.Path);ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    m9=a.m9_decrypted.read_bytes();mm=a.mm_decrypted.read_bytes()
    if sha(m9)!=M9_DEC_SHA:raise SystemExit('M9 SHA mismatch')
    if sha(mm)!=MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
    a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/'_work';work.mkdir(exist_ok=True)
    mr=analyse('m9',m9,a.objdump,work); xr=analyse('mm',mm,a.objdump,work)
    for p in work.iterdir():p.unlink()
    work.rmdir()
    report={'schema':'mmonochrom.bf547.mask-byte0-trace1a.v1','classification':'controller_serializer_field_trace','m9':mr,'monochrom':xr,'closed_chain':['BF561 SPI_AppendSettings source packet+7 -> processing record byte0','Run consumes processing record u32@+0 as process mask','BF547 serializer writes payload byte0 at packet-base+7 / object+0x133','trace object+0x35c as candidate low process-mask-byte producer'],'guardrails':['0x35c is called mask byte 0 only after serializer context confirms its value is stored to payload +0; normal runtime value still requires writer/default closure','bit 6 and bit 7 of this byte correspond to Noise and Sharp only because Run bit-dispatch mapping is independently closed'],'next_questions':['What initializes/writes object+0x35c in Monochrom normal still mode?','Which UI/mode paths set or clear bits 6 and 7?','Does any writer alter byte0 between normal settings assembly and SPI transfer?']}
    (a.outdir/'MM_BF547_MASK_BYTE_TRACE.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF547_MASK_BYTE_TRACE.txt').open('w') as f:
        for label,r in (('M9',mr),('MM',xr)):
            f.write(f'===== {label} serializer anchors =====\n'+json.dumps(r['serializer_anchors'],indent=2)+'\n')
            f.write(f'\n===== {label} +0x35c accesses =====\n'+json.dumps(r['mask_byte0_field_35c_accesses'],indent=2)+'\n\n')
    print(json.dumps({'m9_serializer_anchors':len(mr['serializer_anchors']),'mm_serializer_anchors':len(xr['serializer_anchors']),'m9_field35c_accesses':[(x['addr'],x['kind'],x['line']) for x in mr['mask_byte0_field_35c_accesses']],'mm_field35c_accesses':[(x['addr'],x['kind'],x['line']) for x in xr['mask_byte0_field_35c_accesses']]},indent=2))
if __name__=='__main__':main()
