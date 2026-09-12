#!/usr/bin/env python3
"""Close original M Monochrom BF561 active processing-record construction.

Evidence-only. This probe fixes the earlier LOW/HIGH address-reference blind spot,
resolves helper ownership around SPI_AppendSettings/IM_SetCurrentJob, scans all
BF561 disassembly for references to the scheduling globals, and follows the
first-u32 process-mask field from g_ProcessingList into g_CurrentProcessingSetti.
No firmware binary payload is emitted.
"""
from __future__ import annotations

import argparse, bisect, hashlib, json, pathlib, re, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as tr  # noqa: E402

CURRENT = 0xFEB1E064
PLIST = 0xFEB1E0A8
FOCUS_ADDRS = [0xFEB107F8, 0xFFA1045A, 0xFFA120D8, CURRENT, PLIST]
ADDRLINE = re.compile(r"^\s*([0-9a-fA-F]+):")
TRANSFER = re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b", re.I)


def sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()


def getbf(fw: bytes):
    bf=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=="BF561"),None)
    if bf is None: raise RuntimeError("outer BF561 missing")
    c={x.name.lower():x for x in pwad.parse_pwad(bf.data)}
    return tr.parse_map(c['bf0.map'].data), tr.parse_ldr(c['bf0'].data)


def read_overlay(blocks, addr, size):
    out=bytearray(); cur=addr; end=addr+size
    while cur<end:
        hit=next((b for b in blocks if int(b['addr'])<=cur<int(b['addr'])+len(b['payload'])),None)
        if hit is None: raise KeyError(f"overlay gap {cur:#x}")
        lo=int(hit['addr']); p=hit['payload']; n=min(end-cur,lo+len(p)-cur); out+=p[cur-lo:cur-lo+n]; cur+=n
    return bytes(out)


def dis_all(blocks,objdump,work):
    return tr.disassemble_blocks(blocks,objdump,work)


def owner_table(syms):
    ordered=sorted((int(s['addr']),int(s['size']),s['name']) for s in syms if int(s['size'])>0)
    starts=[x[0] for x in ordered]
    def owner(addr):
        i=bisect.bisect_right(starts,addr)-1
        if i<0:return None
        st,sz,n=ordered[i]
        if addr>=st+sz:return None
        return {'name':n,'addr':hex(st),'size':sz,'offset':addr-st}
    return owner


def reg_addr_refs(lines, target):
    """Accept either Rn/Pn LOW->HIGH or HIGH->LOW within 20 instructions."""
    hi=(target>>16)&0xffff; lo=target&0xffff; out=[]
    # strip duplicate contexts by (register, first instruction address)
    seen=set()
    for i,line in enumerate(lines):
        for reg in [f'R{x}' for x in range(8)]+[f'P{x}' for x in range(6)]:
            low=bool(re.search(rf"\b{reg}\.L\s*=\s*0x{lo:x}\b",line,re.I))
            high=bool(re.search(rf"\b{reg}\.H\s*=\s*0x{hi:x}\b",line,re.I))
            if not (low or high): continue
            for j in range(i+1,min(len(lines),i+20)):
                need = re.search(rf"\b{reg}\.H\s*=\s*0x{hi:x}\b",lines[j],re.I) if low else re.search(rf"\b{reg}\.L\s*=\s*0x{lo:x}\b",lines[j],re.I)
                if need:
                    m=ADDRLINE.match(line); a=int(m.group(1),16) if m else 0
                    key=(reg,a)
                    if key not in seen:
                        seen.add(key);out.append({'reg':reg,'site':hex(a),'order':'LOW_HIGH' if low else 'HIGH_LOW','context':lines[max(0,i-12):min(len(lines),j+30)]})
                    break
    return out


def extract_symbol_disassembly(lines, sym):
    lo=int(sym['addr']);hi=lo+int(sym['size']);out=[]
    for addr,text,*_ in lines:
        if lo<=addr<hi:out.append(text)
    return '\n'.join(out)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if tr.sha(fw)!=tr.MM_DEC_SHA:raise SystemExit(f"MM decrypted SHA mismatch {tr.sha(fw)}")
    syms,blocks=getbf(fw);owner=owner_table(syms)
    a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/'_work';work.mkdir(exist_ok=True)
    dis=dis_all(blocks,a.objdump,work); textlines=[x[1] for x in dis]

    focus={hex(x):owner(x) for x in FOCUS_ADDRS}
    refs={hex(x):reg_addr_refs(textlines,x) for x in FOCUS_ADDRS}
    # Attach owner of every xref site.
    for target,items in refs.items():
        for x in items:x['owner']=owner(int(x['site'],16))

    # All symbols that contain at least one global reference; emit full function
    # disassembly so record-field arithmetic around the xref is inspectable.
    ref_funcs={}
    for target in (CURRENT,PLIST):
        key=hex(target); groups={}
        for r in refs[key]:
            o=r['owner'];name='UNOWNED' if o is None else f"{o['name']}@{o['addr']}"
            groups.setdefault(name,[]).append(r)
        ref_funcs[key]=[]
        for name,rs in groups.items():
            o=rs[0]['owner']
            if o is None: continue
            sym={'addr':int(o['addr'],16),'size':o['size']}
            ref_funcs[key].append({'owner':o,'refs':rs,'disassembly':extract_symbol_disassembly(dis,sym)})

    # Resolve focus helper owners and all callsites to their exact entry address.
    callsites={hex(x):[] for x in FOCUS_ADDRS[:3]}
    for idx,(addr,text,*_) in enumerate(dis):
        m=TRANSFER.search(text)
        if not m:continue
        targ=int(m.group(1),16)
        if targ in FOCUS_ADDRS[:3]:
            callsites[hex(targ)].append({'site':hex(addr),'owner':owner(addr),'context':textlines[max(0,idx-20):min(len(textlines),idx+35)]})

    # Emit full disassembly of owner functions containing focus helper addresses.
    helper_funcs={}
    for x in FOCUS_ADDRS[:3]:
        o=owner(x);key=hex(x)
        if o:
            helper_funcs[key]={'owner':o,'disassembly':extract_symbol_disassembly(dis,{'addr':int(o['addr'],16),'size':o['size']})}
        else:helper_funcs[key]={'owner':None,'disassembly':''}

    # Locate copies of the exact active-record size 0x44 and processing-list item
    # sizes/strides near all global-reference contexts without assuming semantics.
    size_literals=[]
    for idx,line in enumerate(textlines):
        if re.search(r"(?:0x44|0x11\s*\(X\))",line,re.I):
            m=ADDRLINE.match(line);site=int(m.group(1),16) if m else 0
            o=owner(site)
            if o and (o['name'].startswith('SPI_') or o['name'].startswith('IM_') or 'Process' in o['name'] or o['name'] in ('Run','Set','SetProcess','SetStructParameter')):
                size_literals.append({'site':hex(site),'owner':o,'line':line,'context':textlines[max(0,idx-8):min(len(textlines),idx+14)]})

    report={'schema':'mmonochrom.processing-record.probe1a.v1','firmware_decrypted_sha256':tr.sha(fw),'focus_owners':focus,'absolute_address_refs':refs,'global_ref_functions':ref_funcs,'focus_helper_callsites':callsites,'focus_helper_functions':helper_funcs,'record_size_literal_contexts':size_literals,
      'known_constraints':{'active_record_addr':hex(CURRENT),'active_record_size':68,'processing_list_addr':hex(PLIST),'processing_list_size':956,'run_mask_field':'active_record+0x00'},
      'next_questions':['Which processing-list entry/default feeds normal Standard capture?','What first-u32 mask is copied to active_record+0x00?','Which earlier spatial stages enabled by that mask alter border before Sharp?']}
    (a.outdir/'MM_PROCESSING_RECORD_PROBE.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_PROCESSING_RECORD_PROBE.txt').open('w') as f:
        f.write('M Monochrom processing-record probe\n\nFocus owners:\n'+json.dumps(focus,indent=2)+'\n')
        for target in (hex(PLIST),hex(CURRENT)):
            f.write(f"\n===== references to {target} =====\n")
            for q in ref_funcs[target]:
                f.write(f"\n--- {q['owner']} ---\n{q['disassembly']}\n")
        for target,q in helper_funcs.items():f.write(f"\n===== helper {target} owner={q['owner']} =====\n{q['disassembly']}\n")
        f.write('\n===== helper callsites =====\n'+json.dumps(callsites,indent=2)+'\n')
        f.write('\n===== record-size literals =====\n'+json.dumps(size_literals,indent=2)+'\n')
    print(json.dumps({'focus_owners':focus,'ref_counts':{k:len(v) for k,v in refs.items()},'global_ref_owners':{k:[x['owner'] for x in v] for k,v in ref_funcs.items()},'helper_callsite_counts':{k:len(v) for k,v in callsites.items()},'record_size_contexts':len(size_literals)},indent=2))
    for p in work.iterdir():p.unlink()
    work.rmdir()
if __name__=='__main__':main()
