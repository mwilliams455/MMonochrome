#!/usr/bin/env python3
"""Trace how BF561 InitInterpolation selects the runtime Set() mode.

Closed context:
Task_TaskInterpolation calls
  InitInterpolation(param=0xfeb00268, runtime=0xfeb002f8, phase=1)
  RI_WaitForStart()
  InitInterpolation(param=0xfeb00268, runtime=0xfeb002f8, phase=0)

Set(runtime,param) later selects the Run mask from runtime+4:
  mode 0 -> 0x1407
  mode 1 -> 0x17c7
  mode 2 -> 0x0401

This probe emits complete InitInterpolation / RI_WaitForStart bodies and all
low-offset memory operations so runtime+4 provenance can be closed directly.
Evidence only; production Android remains frozen.
"""
from __future__ import annotations
import argparse,bisect,json,pathlib,re,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa:E402
import mm_sharpness_consumer_trace as base  # noqa:E402

NAMES=('InitInterpolation','RI_WaitForStart','Task_TaskInterpolation','StartInterpolation','StartInterpolation_Jolos','SetProcess')
TRANSFER_RE=re.compile(r'\b(CALL|JUMP(?:\.S|\.L)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b',re.I)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
 fw=a.mm_decrypted.read_bytes()
 if base.sha(fw)!=base.MM_DEC_SHA: raise SystemExit('MM SHA mismatch')
 outer=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=='BF561'),None)
 if outer is None: raise SystemExit('BF561 missing')
 cmap={x.name.lower():x for x in pwad.parse_pwad(outer.data)}
 syms=base.parse_map(cmap['bf0.map'].data);blocks=base.parse_ldr(cmap['bf0'].data)
 a.outdir.mkdir(parents=True,exist_ok=True);w=a.outdir/'_work';w.mkdir(exist_ok=True)
 lines=base.disassemble_blocks(blocks,a.objdump,w)
 for p in w.iterdir(): p.unlink()
 w.rmdir()
 texts=[x[1] for x in lines];addrs=[x[0] for x in lines]
 ordered=sorted((int(s['addr']),s['name'],int(s['size'])) for s in syms);starts=[x[0] for x in ordered]
 def owner(addr):
  i=bisect.bisect_right(starts,addr)-1
  if i<0:return None
  st,n,sz=ordered[i];return {'name':n,'start':hex(st),'size':sz,'offset':addr-st,'inside':addr<st+max(1,sz)}
 def body(s):
  lo=int(s['addr']);hi=lo+int(s['size']);i=bisect.bisect_left(addrs,lo);j=bisect.bisect_left(addrs,hi)
  return texts[i:j]
 selected=[s for s in syms if s['name'] in NAMES]
 functions={}
 for s in selected:
  b=body(s)
  low=[x for x in b if re.search(r'\[(?:P[0-5]|R[0-7])(?:\s*\+\s*0x(?:0|4|8|c|10|14|18|1c|20|24|28|2c|30|34|38|3c|40))?\]',x,re.I)]
  functions.setdefault(s['name'],[]).append({'addr':hex(int(s['addr'])),'size':int(s['size']),'body':b,'low_offset_memory':low})
 targets={int(s['addr']):s['name'] for s in selected}
 calls=[]
 for i,(addr,text,*_) in enumerate(lines):
  m=TRANSFER_RE.search(text)
  if m and int(m.group(2),16) in targets:
   calls.append({'site':hex(addr),'from':owner(addr),'to':targets[int(m.group(2),16)],'context':texts[max(0,i-45):min(len(texts),i+30)]})
 report={'schema':'mmonochrom.bf561.initinterpolation-mode-trace1a.v1','known_task_contract':{'param':'0xfeb00268','runtime':'0xfeb002f8','calls':['InitInterpolation(param,runtime,1)','RI_WaitForStart()','InitInterpolation(param,runtime,0)']},'known_set_masks':{'runtime_mode_0':'0x1407','runtime_mode_1':'0x17c7','runtime_mode_2':'0x0401'},'functions':functions,'calls_to_selected':calls,'classification':'runtime_mode_selector_evidence','decision_rule':'Identify what value is present at runtime+4 immediately before Set(runtime,param) for the normal Task_TaskInterpolation path.','guardrails':['Track register reassignment before assigning a store to runtime+4.','Do not infer mode from R2 alone unless InitInterpolation body proves the mapping.','RAWSCALAR1B production branch remains frozen.']}
 (a.outdir/'MM_BF561_INITINTERPOLATION_MODE_TRACE.json').write_text(json.dumps(report,indent=2)+'\n')
 with (a.outdir/'MM_BF561_INITINTERPOLATION_MODE_TRACE.txt').open('w') as f:
  f.write(json.dumps({'selected':[(s['name'],hex(int(s['addr'])),int(s['size'])) for s in selected],'calls':[(x['site'],x['from']['name'] if x['from'] else None,x['to']) for x in calls]},indent=2)+'\n')
  for n,arr in functions.items():
   for x in arr:
    f.write(f"\n===== {n} {x['addr']} =====\n"+'\n'.join(x['body'])+'\n')
    f.write('\nLOW-OFFSET MEMORY\n'+'\n'.join(x['low_offset_memory'])+'\n')
 print(json.dumps({'selected':[(s['name'],hex(int(s['addr'])),int(s['size'])) for s in selected],'calls':[(x['site'],x['from']['name'] if x['from'] else None,x['to']) for x in calls]},indent=2))
if __name__=='__main__':main()
