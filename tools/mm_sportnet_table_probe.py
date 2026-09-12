#!/usr/bin/env python3
"""Decode M Monochrom g_pSportNetFunctions and trace its dispatcher.

The SPI indirect-dispatch probe closed a literal SPI_AppendSettings function
pointer inside g_pSportNetFunctions.  The map gives this object as 156 bytes,
which is exactly 13 * 12 bytes.  This probe parses all 13 records as three
little-endian u32 fields, resolves pointer-like fields against BF0.map, and
searches executable BF0 disassembly for constructions/references to the table.
Only derived integer values and disassembly text are emitted.
"""
from __future__ import annotations
import argparse, bisect, hashlib, json, pathlib, re, struct, subprocess, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as tr  # noqa: E402

MM_DEC_SHA=tr.MM_DEC_SHA
TABLE_NAME='g_pSportNetFunctions'


def sha(b): return hashlib.sha256(b).hexdigest()

def component(root):
    bf=next((x for x in pwad.parse_pwad(root) if x.name.upper()=='BF561'),None)
    if bf is None: raise RuntimeError('outer BF561 missing')
    c={x.name.lower():x for x in pwad.parse_pwad(bf.data)}
    return tr.parse_map(c['bf0.map'].data), tr.parse_ldr(c['bf0'].data)

def read_overlay(blocks,addr,size):
    out=bytearray(); cur=addr; end=addr+size
    while cur<end:
        b=next((x for x in blocks if int(x['addr'])<=cur<int(x['addr'])+len(x['payload'])),None)
        if b is None: raise KeyError(hex(cur))
        lo=int(b['addr']); take=min(end-cur,lo+len(b['payload'])-cur)
        out+=b['payload'][cur-lo:cur-lo+take]; cur+=take
    return bytes(out)

def resolver(syms):
    exact={}; arr=[]
    for s in syms:
        a=int(s['addr']); z=int(s['size']); exact.setdefault(a,[]).append(s['name'])
        if z>0: arr.append((a,z,s['name']))
    arr.sort(); starts=[x[0] for x in arr]
    def r(a):
        o={}
        if a in exact:o['exact']=exact[a]
        i=bisect.bisect_right(starts,a)-1
        if i>=0:
            st,z,n=arr[i]
            if st<=a<st+z:o['owner']={'name':n,'addr':hex(st),'size':z,'offset':a-st}
        return o or None
    return r

def disassemble(blocks,objdump,work):
    return tr.disassemble_blocks(blocks,objdump,work)

def table_addr_contexts(dis,addr,resolve):
    hi=(addr>>16)&0xffff; lo=addr&0xffff
    out=[]
    for i,(a,line,*_) in enumerate(dis):
        mh=re.search(rf'\b([RP][0-7])\.H\s*=\s*0x{hi:x}\b',line,re.I)
        ml=re.search(rf'\b([RP][0-7])\.L\s*=\s*0x{lo:x}\b',line,re.I)
        if not (mh or ml): continue
        reg=(mh or ml).group(1).upper()
        for j in range(i+1,min(len(dis),i+18)):
            l2=dis[j][1]
            ok=(mh and re.search(rf'\b{reg}\.L\s*=\s*0x{lo:x}\b',l2,re.I)) or (ml and re.search(rf'\b{reg}\.H\s*=\s*0x{hi:x}\b',l2,re.I))
            if ok:
                out.append({'addr':hex(a),'resolve':resolve(a),'reg':reg,'context':[x[1] for x in dis[max(0,i-12):min(len(dis),j+40)]]})
                break
    return out

def literal_xrefs(blocks,addr,resolve):
    needle=struct.pack('<I',addr); out=[]
    for b in blocks:
        p=0
        while True:
            p=b['payload'].find(needle,p)
            if p<0: break
            a=int(b['addr'])+p; out.append({'addr':hex(a),'resolve':resolve(a)}); p+=1
    return out

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('mm_decrypted',type=pathlib.Path); ap.add_argument('--objdump',type=pathlib.Path,required=True); ap.add_argument('--outdir',type=pathlib.Path,required=True); a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if sha(fw)!=MM_DEC_SHA: raise SystemExit(f'MM decrypted SHA mismatch {sha(fw)}')
    syms,blocks=component(fw); r=resolver(syms)
    hit=[s for s in syms if s['name']==TABLE_NAME]
    if len(hit)!=1: raise SystemExit(f'{TABLE_NAME} hits={len(hit)}')
    s=hit[0]; base=int(s['addr']); size=int(s['size'])
    if size%12: raise SystemExit(f'unexpected table size {size}')
    raw=read_overlay(blocks,base,size)
    recs=[]
    for i in range(size//12):
        vals=list(struct.unpack_from('<III',raw,i*12))
        recs.append({'index':i,'record_addr':hex(base+i*12),'field0':vals[0],'field0_hex':hex(vals[0]),'field0_resolve':r(vals[0]),'field1':vals[1],'field1_hex':hex(vals[1]),'field1_resolve':r(vals[1]),'field2':vals[2],'field2_hex':hex(vals[2]),'field2_resolve':r(vals[2])})
    append=[x for x in recs if x['field1_resolve'] and 'SPI_AppendSettings' in x['field1_resolve'].get('exact',[])]
    a.outdir.mkdir(parents=True,exist_ok=True); work=a.outdir/'_work'; work.mkdir(exist_ok=True)
    dis=disassemble(blocks,a.objdump,work)
    ctx=table_addr_contexts(dis,base,r); lit=literal_xrefs(blocks,base,r)
    for p in work.iterdir(): p.unlink()
    work.rmdir()
    report={'schema':'mmonochrom.sportnet.table1a.v1','firmware_decrypted_sha256':sha(fw),'table':{'name':TABLE_NAME,'addr':hex(base),'size':size,'record_bytes':12,'record_count':len(recs),'sha256':sha(raw)},'records':recs,'append_settings_records':append,'table_base_code_contexts':ctx,'table_base_literal_xrefs':lit,'guardrails':['field meanings are not assigned from position alone','a record index is exact once function pointer resolution identifies SPI_AppendSettings','command semantics require tracing the dispatcher consumer of the table'], 'next_questions':['Which field is the incoming command selector?','Which code indexes the 12-byte records?','Does AppendSettings packet +7 map directly to the 37-byte BF547-produced processing settings payload?']}
    (a.outdir/'MM_SPORTNET_TABLE_PROBE.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_SPORTNET_TABLE_PROBE.txt').open('w') as f:
        f.write('M Monochrom SportNet dispatch table\n\n'+json.dumps(report['table'],indent=2)+'\n\n')
        f.write('RECORDS\n'+json.dumps(recs,indent=2)+'\n\n')
        f.write('APPEND SETTINGS RECORD\n'+json.dumps(append,indent=2)+'\n\n')
        f.write('TABLE BASE CODE CONTEXTS\n'+json.dumps(ctx,indent=2)+'\n\n')
        f.write('TABLE BASE LITERAL XREFS\n'+json.dumps(lit,indent=2)+'\n')
    print(json.dumps({'table':report['table'],'append_settings_records':append,'base_code_context_count':len(ctx),'base_literal_xref_count':len(lit)},indent=2))
if __name__=='__main__': main()
