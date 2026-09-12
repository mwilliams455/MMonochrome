#!/usr/bin/env python3
"""Trace indirect BF561 SetProcess dispatch and recover caller argument objects.

Direct-call scans found no caller of SetProcess even though SetProcess is a live
mapped routine.  This probe therefore searches the initialized BF561 LDR image
for raw function pointers to both SetProcess mirrors, identifies their owning
static/table regions from bf0.map, and traces code references to those table
addresses.  It also inventories indirect CALL/JUMP sites whose preparation
loads through those tables so R0/R1/R2 can be reconstructed.

Only derived addresses, words and disassembly text are emitted; no firmware
binary is published.
"""
from __future__ import annotations
import argparse, bisect, hashlib, json, pathlib, re, struct, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as base  # noqa: E402

TARGETS=(0xffa127d0,0xff611608)
TRANSFER_IND=re.compile(r'\b(?:CALL|JUMP(?:\.S|\.L)?)\s*\(\s*([PR][0-7])\s*\)',re.I)
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def read_byte(blocks,addr):
    for b in blocks:
        lo=int(b['addr']); data=b['payload']; hi=lo+len(data)
        if lo<=addr<hi:return data[addr-lo]
    return None

def read_u32(blocks,addr):
    bs=[]
    for k in range(4):
        v=read_byte(blocks,addr+k)
        if v is None:return None
        bs.append(v)
    return int.from_bytes(bytes(bs),'little')

def initialized_ranges(blocks):
    return [(int(b['addr']),int(b['addr'])+len(b['payload']),b['payload']) for b in blocks if b['payload']]

def raw_pointer_hits(blocks,target):
    needle=struct.pack('<I',target); out=[]
    for lo,hi,data in initialized_ranges(blocks):
        p=0
        while True:
            p=data.find(needle,p)
            if p<0:break
            out.append(lo+p); p+=1
    return sorted(set(out))

def addr_of_text(s):
    m=ADDR_RE.match(s);return int(m.group(1),16) if m else None

def split_immediate_refs(lines,target):
    hi=(target>>16)&0xffff;lo=target&0xffff
    hr=re.compile(rf'\b([PR][0-7])\.H\s*=\s*0x{hi:x}\b',re.I)
    lr=re.compile(rf'\b([PR][0-7])\.L\s*=\s*0x{lo:x}\b',re.I)
    out=[]
    texts=[x[1] for x in lines]
    for i,(_,l,*_) in enumerate(lines):
        a=hr.search(l); b=lr.search(l)
        if not(a or b):continue
        reg=(a or b).group(1).upper()
        for j in range(i+1,min(len(lines),i+18)):
            l2=lines[j][1]; c=lr.search(l2) if a else hr.search(l2)
            if c and c.group(1).upper()==reg:
                ctx=texts[max(0,i-35):min(len(texts),j+70)]
                out.append({'first_site':hex(lines[i][0]),'second_site':hex(lines[j][0]),'reg':reg,'context':ctx})
                break
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if base.sha(fw)!=base.MM_DEC_SHA:raise SystemExit('MM decrypted SHA mismatch')
    outer=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=='BF561'),None)
    if outer is None:raise SystemExit('BF561 missing')
    cmap={x.name.lower():x for x in pwad.parse_pwad(outer.data)}
    syms=base.parse_map(cmap['bf0.map'].data); blocks=base.parse_ldr(cmap['bf0'].data)
    a.outdir.mkdir(parents=True,exist_ok=True); work=a.outdir/'_work';work.mkdir(exist_ok=True)
    lines=base.disassemble_blocks(blocks,a.objdump,work)
    for p in work.iterdir():p.unlink()
    work.rmdir()
    texts=[x[1] for x in lines]; addrs=[x[0] for x in lines]
    ordered=sorted((int(s['addr']),s['name'],int(s['size'])) for s in syms); starts=[x[0] for x in ordered]
    def owner(addr):
        i=bisect.bisect_right(starts,addr)-1
        if i<0:return None
        st,n,sz=ordered[i]
        return {'name':n,'start':hex(st),'size':sz,'offset':addr-st,'inside':addr<st+max(1,sz)}
    target_hits={}
    table_bases=set()
    for t in TARGETS:
        hits=raw_pointer_hits(blocks,t); arr=[]
        for h in hits:
            # preserve +/- 16 words around hit and candidate aligned bases up to 64B before
            words=[]
            for aa in range(h-64,h+68,4):
                v=read_u32(blocks,aa)
                if v is not None:words.append({'addr':hex(aa),'rel':aa-h,'value':hex(v),'owner':owner(aa)})
            bases=[]
            for d in range(0,68,4):
                b=h-d
                # only keep bases that have at least one split-immediate reference in code
                refs=split_immediate_refs(lines,b)
                if refs:
                    table_bases.add(b);bases.append({'base':hex(b),'refs':refs})
            arr.append({'pointer_addr':hex(h),'owner':owner(h),'window':words,'referenced_candidate_bases':bases})
        target_hits[hex(t)]={'raw_pointer_hits':arr,'direct_split_refs':split_immediate_refs(lines,t)}
    # For every candidate table base, find code contexts and nearby indirect calls.
    tables=[]
    for b in sorted(table_bases):
        refs=split_immediate_refs(lines,b)
        derived=[]
        for r in refs:
            # approximate index from second site, then scan next 100 instructions for table loads + indirect call
            ss=int(r['second_site'],16); i=bisect.bisect_left(addrs,ss)
            ctx=lines[max(0,i-25):min(len(lines),i+130)]
            ind=[]
            for addr,text,*_ in ctx:
                m=TRANSFER_IND.search(text)
                if m:ind.append({'site':hex(addr),'reg':m.group(1).upper(),'line':text})
            derived.append({'ref':r,'indirect_transfers_nearby':ind,'context':[x[1] for x in ctx]})
        tables.append({'base':hex(b),'owner':owner(b),'refs':derived})
    # Global indirect transfers around any owner with process/job/list semantics, useful if table base is loaded indirectly.
    semantic=re.compile(r'(Process|Job|Settings|List|SPI|IM_)',re.I)
    indirect=[]
    for i,(addr,text,*_) in enumerate(lines):
        m=TRANSFER_IND.search(text)
        if not m:continue
        own=owner(addr)
        ctx=texts[max(0,i-45):min(len(texts),i+35)]
        if (own and semantic.search(own['name'])) or any(semantic.search(x) for x in ctx):
            indirect.append({'site':hex(addr),'owner':own,'reg':m.group(1).upper(),'line':text,'context':ctx})
    report={'schema':'mmonochrom.bf561.setprocess-dispatch-trace1a.v1','firmware_decrypted_sha256':base.sha(fw),'targets':target_hits,'candidate_tables':tables,'semantic_indirect_transfers':indirect,'classification':'indirect_setprocess_dispatch_and_argument_provenance','questions':['Which table slot points to SetProcess?','What code loads that slot and what are R0/R1/R2 immediately before the indirect call?','Does R0 equal g_CurrentProcessingSetti / a 68-byte list record, or another state object?'],'guardrails':['Do not equate IM_AppendItem record+0x2c with Run mask until SetProcess R0 identity is proven.','The 0x31343133 source-record marker is not the Run dispatch mask.','Keep production RAWSCALAR1B frozen.']}
    (a.outdir/'MM_BF561_SETPROCESS_DISPATCH_TRACE.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF561_SETPROCESS_DISPATCH_TRACE.txt').open('w') as f:
        f.write(json.dumps({'targets':{k:[x['pointer_addr'] for x in v['raw_pointer_hits']] for k,v in target_hits.items()},'candidate_table_bases':[x['base'] for x in tables],'semantic_indirect_count':len(indirect)},indent=2)+'\n')
        for t,v in target_hits.items():
            f.write(f'\n===== TARGET {t} =====\n'+json.dumps(v,indent=2)+'\n')
        for tb in tables:
            f.write(f"\n===== TABLE {tb['base']} owner={tb['owner']} =====\n"+json.dumps(tb,indent=2)+'\n')
        f.write('\n===== SEMANTIC INDIRECT TRANSFERS =====\n'+json.dumps(indirect,indent=2)+'\n')
    print(json.dumps({'target_pointer_hits':{k:[x['pointer_addr'] for x in v['raw_pointer_hits']] for k,v in target_hits.items()},'candidate_table_bases':[hex(x) for x in sorted(table_bases)],'semantic_indirect_count':len(indirect)},indent=2))
if __name__=='__main__':main()
