#!/usr/bin/env python3
"""Trace BF561 Init() writes to the runtime object, especially runtime+4.

Closed caller:
  InitInterpolation(param=R6, runtime=R7, phase=0)
    -> Init(core_id=3, param=R6, runtime=R7) on core A
    -> Init(core_id=4, param=R6, runtime=R7) on core B

Set(runtime,param) later selects the Run mask from runtime+4:
  0 -> 0x1407
  1 -> 0x17c7
  2 -> 0x0401

This probe emits complete Init bodies and their direct callees plus memory
operations around the R2/third-argument dataflow. Evidence only.
"""
from __future__ import annotations
import argparse,bisect,json,pathlib,re,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa:E402
import mm_sharpness_consumer_trace as base  # noqa:E402

TARGETS=(0xfeb10eb8,0xfeb18718)
TRANSFER_RE=re.compile(r'\b(CALL|JUMP(?:\.S|\.L)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b',re.I)

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
 def body_for_target(t):
  o=owner(t)
  if not o or not o['inside']:return []
  lo=int(o['start'],16);hi=lo+o['size'];i=bisect.bisect_left(addrs,lo);j=bisect.bisect_left(addrs,hi)
  return texts[i:j]
 def direct_calls(body):
  out=[]
  for line in body:
   m=TRANSFER_RE.search(line)
   if m:
    t=int(m.group(2),16);out.append({'line':line,'target':hex(t),'owner':owner(t)})
  return out
 result={};callee_names=set()
 for t in TARGETS:
  b=body_for_target(t);calls=direct_calls(b)
  for c in calls:
   if c['owner'] and c['owner']['inside']:callee_names.add(c['owner']['name'])
  mem=[x for x in b if '[' in x and ']' in x]
  low=[x for x in mem if re.search(r'\+\s*0x(?:0|4|8|c|10|14|18|1c|20|24|28|2c|30|34|38|3c|40|44|48|4c|50|54)\b',x,re.I) or re.search(r'\[[PR][0-7]\]',x,re.I)]
  result[hex(t)]={'owner':owner(t),'body':b,'memory_lines':mem,'low_offset_memory':low,'direct_calls':calls}
 callees={}
 for n in sorted(callee_names):
  arr=[]
  for s in syms:
   if s['name']==n:
    lo=int(s['addr']);hi=lo+int(s['size']);i=bisect.bisect_left(addrs,lo);j=bisect.bisect_left(addrs,hi)
    arr.append({'addr':hex(lo),'size':int(s['size']),'body':texts[i:j]})
  callees[n]=arr
 report={'schema':'mmonochrom.bf561.init-runtime-mode1a.v1','known_call_contract':{'coreA':'Init(R0=3,R1=param,R2=runtime)','coreB':'Init(R0=4,R1=param,R2=runtime)'},'known_set_masks':{'mode0':'0x1407','mode1':'0x17c7','mode2':'0x0401'},'init_functions':result,'direct_callee_bodies':callees,'classification':'runtime_mode_write_provenance','questions':['Where is third argument runtime saved?','What writes runtime+4?','Is the normal initialized value 0,1,or2 before Set()?'],'guardrails':['Track R2 through register saves before naming destination.','Core id 3/4 is not automatically the runtime mode.','RAWSCALAR1B stays frozen.']}
 (a.outdir/'MM_BF561_INIT_RUNTIME_MODE.json').write_text(json.dumps(report,indent=2)+'\n')
 with (a.outdir/'MM_BF561_INIT_RUNTIME_MODE.txt').open('w') as f:
  for t,d in result.items():
   f.write(f"\n===== INIT {t} owner={d['owner']} =====\n"+'\n'.join(d['body'])+'\n')
   f.write('\nLOW OFFSET MEMORY\n'+'\n'.join(d['low_offset_memory'])+'\n')
   f.write('\nDIRECT CALLS\n'+json.dumps(d['direct_calls'],indent=2)+'\n')
  for n,arr in callees.items():
   for x in arr:f.write(f"\n===== CALLEE {n} {x['addr']} =====\n"+'\n'.join(x['body'])+'\n')
 print(json.dumps({t:{'owner':d['owner'],'calls':[(c['target'],c['owner']['name'] if c['owner'] else None) for c in d['direct_calls']]} for t,d in result.items()},indent=2))
if __name__=='__main__':main()
