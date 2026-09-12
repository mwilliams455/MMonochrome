#!/usr/bin/env python3
"""Determine whether the BF561 current-job/list +0x2c word is mutated after append.

IM_AppendItem initializes each 68-byte list record +0x2c from payload byte 7
via a 32-bit multiply by 0x01450000. Such a value cannot provide Run bits
0..10. This probe traces every code reference to g_CurrentProcessingSetti,
g_ProcessingList, and the exact current-job +0x2c address, identifying writes
or transformations after IM_SetCurrentJob. If no mutation exists, SetProcess R0
cannot be the unchanged current-job/list record.
"""
from __future__ import annotations
import argparse,bisect,json,pathlib,re,struct,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa:E402
import mm_sharpness_consumer_trace as base  # noqa:E402

CURRENT=0xfeb1e064
CURRENT_2C=CURRENT+0x2c
PLIST=0xfeb1e0a8
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
 fw=a.mm_decrypted.read_bytes()
 if base.sha(fw)!=base.MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
 outer=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=='BF561'),None);cmap={x.name.lower():x for x in pwad.parse_pwad(outer.data)}
 syms=base.parse_map(cmap['bf0.map'].data);blocks=base.parse_ldr(cmap['bf0'].data)
 a.outdir.mkdir(parents=True,exist_ok=True);w=a.outdir/'_work';w.mkdir(exist_ok=True);lines=base.disassemble_blocks(blocks,a.objdump,w)
 for p in w.iterdir():p.unlink()
 w.rmdir()
 texts=[x[1] for x in lines];addrs=[x[0] for x in lines]
 ordered=sorted((int(s['addr']),s['name'],int(s['size'])) for s in syms);starts=[x[0] for x in ordered]
 def owner(addr):
  i=bisect.bisect_right(starts,addr)-1
  if i<0:return None
  st,n,sz=ordered[i];return {'name':n,'start':hex(st),'size':sz,'offset':addr-st,'inside':addr<st+max(1,sz)}
 def splitrefs(target):
  hi=(target>>16)&0xffff;lo=target&0xffff;hr=re.compile(rf'\b([PR][0-7])\.H\s*=\s*0x{hi:x}\b',re.I);lr=re.compile(rf'\b([PR][0-7])\.L\s*=\s*0x{lo:x}\b',re.I);out=[]
  for i,(addr,text,*_) in enumerate(lines):
   x=hr.search(text);y=lr.search(text)
   if not(x or y):continue
   reg=(x or y).group(1).upper()
   for j in range(i+1,min(len(lines),i+20)):
    z=lr.search(lines[j][1]) if x else hr.search(lines[j][1])
    if z and z.group(1).upper()==reg:
     ctx=lines[max(0,i-40):min(len(lines),j+100)]
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
 targets={
  'current':{'addr':hex(CURRENT),'split_refs':splitrefs(CURRENT),'literal_hits':literal_hits(CURRENT)},
  'current_plus_2c':{'addr':hex(CURRENT_2C),'split_refs':splitrefs(CURRENT_2C),'literal_hits':literal_hits(CURRENT_2C)},
  'processing_list':{'addr':hex(PLIST),'split_refs':splitrefs(PLIST),'literal_hits':literal_hits(PLIST)},
 }
 # All code contexts with explicit +0x2c memory accesses owned by job/list/process functions.
 off2c=[]
 for i,(addr,text,*_) in enumerate(lines):
  if '+ 0x2c]' in text.lower():
   own=owner(addr)
   if own and re.search(r'(Job|Process|List|IM_|SPI_)',own['name'],re.I):
    off2c.append({'site':hex(addr),'owner':own,'line':text,'context':texts[max(0,i-30):min(len(texts),i+45)]})
 report={'schema':'mmonochrom.bf561.currentjob-mask-mutation1a.v1','targets':targets,'semantic_offset_2c_accesses':off2c,'classification':'current_job_mask_mutation_or_source_exclusion','decision_rule':'If current/current+0x2c has no post-copy writer capable of introducing low Run bits, SetProcess R0 is not the unchanged g_CurrentProcessingSetti/list-record object.','guardrails':['Do not treat address construction alone as a write; inspect the surrounding memory operation.','Do not change Android rendering from this probe.']}
 (a.outdir/'MM_BF561_CURRENTJOB_MASK_MUTATION.json').write_text(json.dumps(report,indent=2)+'\n')
 with (a.outdir/'MM_BF561_CURRENTJOB_MASK_MUTATION.txt').open('w') as f:
  f.write(json.dumps({'targets':{k:{'split_ref_count':len(v['split_refs']),'literal_hits':v['literal_hits']} for k,v in targets.items()},'semantic_off2c_count':len(off2c)},indent=2)+'\n')
  for k,v in targets.items():f.write(f'\n===== {k} {v["addr"]} =====\n'+json.dumps(v,indent=2)+'\n')
  f.write('\n===== SEMANTIC +0x2C =====\n'+json.dumps(off2c,indent=2)+'\n')
 print(json.dumps({'split_refs':{k:len(v['split_refs']) for k,v in targets.items()},'literal_hits':{k:v['literal_hits'] for k,v in targets.items()},'semantic_off2c_count':len(off2c)},indent=2))
if __name__=='__main__':main()
