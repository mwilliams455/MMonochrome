#!/usr/bin/env python3
"""Recover the true M Monochrom BF561 Run dispatch mask.

Corrected callgraph evidence closes the active path as:
Task_TaskInterpolation
  -> StartInterpolation(..., R0=0xfeb00268, R1=0xfeb002f8, R2=job68)
  -> StartInterpolation_Jolos
  -> SetProcess(job68, 0xfeb00268, 0xfeb002f8)
  -> Run(0xfeb002f8, 0xfeb00268)

Run immediately loads R5=[R0], so the true dispatch mask is the first word of
the persistent runtime object at 0xfeb002f8, not job+0x2c. This probe extracts
that initialized word (if present) and traces every mapped code reference/store
to both persistent objects, especially 0xfeb002f8+0.

Evidence-only: no firmware binary bytes are emitted.
"""
from __future__ import annotations
import argparse,bisect,hashlib,json,pathlib,re,struct,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa:E402
import mm_sharpness_consumer_trace as base  # noqa:E402

PARAM=0xfeb00268
RUNTIME=0xfeb002f8
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')

def read_byte(blocks,addr):
    for b in blocks:
        lo=int(b['addr']); data=b['payload']; hi=lo+len(data)
        if lo<=addr<hi:return data[addr-lo]
    return None

def read_u32(blocks,addr):
    vals=[read_byte(blocks,addr+i) for i in range(4)]
    if any(v is None for v in vals):return None
    return int.from_bytes(bytes(vals),'little')

def bits(v):return [i for i in range(32) if v&(1<<i)]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if base.sha(fw)!=base.MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
    outer=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=='BF561'),None)
    if outer is None:raise SystemExit('BF561 missing')
    cmap={x.name.lower():x for x in pwad.parse_pwad(outer.data)}
    syms=base.parse_map(cmap['bf0.map'].data); blocks=base.parse_ldr(cmap['bf0'].data)
    a.outdir.mkdir(parents=True,exist_ok=True);w=a.outdir/'_work';w.mkdir(exist_ok=True)
    lines=base.disassemble_blocks(blocks,a.objdump,w)
    for p in w.iterdir():p.unlink()
    w.rmdir()
    texts=[x[1] for x in lines]
    ordered=sorted((int(s['addr']),s['name'],int(s['size'])) for s in syms);starts=[x[0] for x in ordered]
    def owner(addr):
        i=bisect.bisect_right(starts,addr)-1
        if i<0:return None
        st,n,sz=ordered[i];return {'name':n,'start':hex(st),'size':sz,'offset':addr-st,'inside':addr<st+max(1,sz)}
    def splitrefs(target):
        hi=(target>>16)&0xffff;lo=target&0xffff
        hr=re.compile(rf'\b([PR][0-7])\.H\s*=\s*0x{hi:x}\b',re.I)
        lr=re.compile(rf'\b([PR][0-7])\.L\s*=\s*0x{lo:x}\b',re.I)
        out=[]
        for i,(addr,text,*_) in enumerate(lines):
            x=hr.search(text);y=lr.search(text)
            if not(x or y):continue
            reg=(x or y).group(1).upper()
            for j in range(i+1,min(len(lines),i+18)):
                z=lr.search(lines[j][1]) if x else hr.search(lines[j][1])
                if z and z.group(1).upper()==reg:
                    ctx=lines[max(0,i-45):min(len(lines),j+110)]
                    out.append({'first_site':hex(addr),'second_site':hex(lines[j][0]),'owner':owner(addr),'reg':reg,'context':[q[1] for q in ctx]});break
        return out
    def literal_hits(target):
        needle=struct.pack('<I',target);out=[]
        for b in blocks:
            data=b['payload'];p=0
            while True:
                p=data.find(needle,p)
                if p<0:break
                out.append(hex(int(b['addr'])+p));p+=1
        return out
    def refs_for_range(baseaddr,size=0x90):
        out=[]
        for off in range(0,size,4):
            addr=baseaddr+off
            refs=splitrefs(addr)
            if refs:out.append({'offset':hex(off),'addr':hex(addr),'refs':refs})
        return out
    runtime_word=read_u32(blocks,RUNTIME)
    param_word=read_u32(blocks,PARAM)
    # Search explicit memory accesses through registers known to be loaded with exact base in nearby contexts.
    runtime_refs=splitrefs(RUNTIME);param_refs=splitrefs(PARAM)
    report={
      'schema':'mmonochrom.bf561.runmask-runtime-object1a.v1',
      'firmware_sha256':base.sha(fw),
      'closed_call_path':[
        'Task_TaskInterpolation -> StartInterpolation(job68)',
        'StartInterpolation_Jolos -> SetProcess(job68, 0xfeb00268, 0xfeb002f8)',
        'StartInterpolation_Jolos -> Run(0xfeb002f8, 0xfeb00268)',
        'Run: R5=[R0]'
      ],
      'param_object':{'addr':hex(PARAM),'owner':owner(PARAM),'initialized_u32':None if param_word is None else hex(param_word),'literal_hits':literal_hits(PARAM),'split_refs':param_refs},
      'runtime_object':{'addr':hex(RUNTIME),'owner':owner(RUNTIME),'initialized_u32':None if runtime_word is None else hex(runtime_word),'initialized_set_bits':[] if runtime_word is None else bits(runtime_word),'named_dispatch_bits':None if runtime_word is None else {
        'noise_bit6':bool(runtime_word&(1<<6)),
        'sharp_bit7':bool(runtime_word&(1<<7)),
        'contrast_bit8':bool(runtime_word&(1<<8)),
        'y_bit9':bool(runtime_word&(1<<9)),
        'bit10':bool(runtime_word&(1<<10)),
      },'literal_hits':literal_hits(RUNTIME),'split_refs':runtime_refs},
      'runtime_nearby_address_refs':refs_for_range(RUNTIME,0x90),
      'classification':'true_run_mask_runtime_object_trace',
      'decision_rule':'If runtime+0 has a stable initialized or explicitly written value before Run, that value is the Run BITTST mask for the active Jolos path.',
      'guardrails':['Do not use job+0x2c as the Run mask; corrected StartInterpolation argument order disproves that interpretation.','Distinguish static initialization from runtime writes and report both.','Production RAWSCALAR1B remains frozen.']
    }
    (a.outdir/'MM_BF561_RUNMASK_RUNTIME_OBJECT.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF561_RUNMASK_RUNTIME_OBJECT.txt').open('w') as f:
        f.write(json.dumps({'param_addr':hex(PARAM),'param_initialized_u32':report['param_object']['initialized_u32'],'runtime_addr':hex(RUNTIME),'runtime_initialized_u32':report['runtime_object']['initialized_u32'],'runtime_set_bits':report['runtime_object']['initialized_set_bits'],'named_dispatch_bits':report['runtime_object']['named_dispatch_bits'],'param_ref_count':len(param_refs),'runtime_ref_count':len(runtime_refs)},indent=2)+'\n')
        f.write('\n===== RUNTIME REFS =====\n'+json.dumps(runtime_refs,indent=2)+'\n')
        f.write('\n===== PARAM REFS =====\n'+json.dumps(param_refs,indent=2)+'\n')
        f.write('\n===== RUNTIME NEARBY REFS =====\n'+json.dumps(report['runtime_nearby_address_refs'],indent=2)+'\n')
    print(json.dumps({'runtime_initialized_u32':report['runtime_object']['initialized_u32'],'runtime_set_bits':report['runtime_object']['initialized_set_bits'],'named_dispatch_bits':report['runtime_object']['named_dispatch_bits'],'runtime_ref_count':len(runtime_refs),'param_ref_count':len(param_refs)},indent=2))
if __name__=='__main__':main()
