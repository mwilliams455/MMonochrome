#!/usr/bin/env python3
"""Correct BF561 callgraph tracing for GNU objdump's occasional `0x0xADDR` output.

Earlier xref probes accepted only one optional `0x`, causing false-negative
caller lists.  This focused rerun traces the actual processing queue/task path
from Task_TaskInterpolation through IM_GetHead/SetCurrentJob/SetProcess/Run and
all related named routines with a regex that accepts `0x0x`, `0x`, or bare
addresses.
"""
from __future__ import annotations
import argparse,bisect,json,pathlib,re,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa:E402
import mm_sharpness_consumer_trace as base  # noqa:E402

NAMES=('Task_TaskInterpolation','IM_AppendItem','IM_GetHead','IM_SetCurrentJob','IM_GetCurrentJob','SetProcess','Run','SPI_AppendSettings','SetStructParameter','InitL1MemoryProcessing')
TRANSFER_RE=re.compile(r'\b(CALL|JUMP(?:\.S|\.L)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b',re.I)
IND_RE=re.compile(r'\b(CALL|JUMP(?:\.S|\.L)?)\s*\(\s*([PR][0-7])\s*\)',re.I)

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
 selected=[s for s in syms if s['name'] in NAMES]
 targets={int(s['addr']):s['name'] for s in selected}
 funcs={}
 for s in selected:
  lo=int(s['addr']);hi=lo+int(s['size']);i=bisect.bisect_left(addrs,lo);j=bisect.bisect_left(addrs,hi)
  funcs.setdefault(s['name'],[]).append({'addr':hex(lo),'size':int(s['size']),'body':texts[i:j]})
 calls=[];all_direct=[];indirect=[]
 for i,(addr,text,*_) in enumerate(lines):
  m=TRANSFER_RE.search(text)
  if m:
   t=int(m.group(2),16);own=owner(addr)
   all_direct.append({'site':hex(addr),'from':own,'kind':m.group(1),'target':hex(t),'target_owner':owner(t)})
   if t in targets:
    calls.append({'site':hex(addr),'from':own,'kind':m.group(1),'to':{'name':targets[t],'addr':hex(t)},'context':texts[max(0,i-55):min(len(texts),i+45)]})
  q=IND_RE.search(text)
  if q:
   own=owner(addr)
   if own and (own['name'] in NAMES or re.search(r'(Task|Process|Job|Interpolation)',own['name'],re.I)):
    indirect.append({'site':hex(addr),'from':own,'kind':q.group(1),'reg':q.group(2).upper(),'context':texts[max(0,i-55):min(len(texts),i+45)]})
 # Expand one hop: any function that directly calls a selected target gets full body.
 caller_names=sorted({x['from']['name'] for x in calls if x['from'] and x['from']['inside']})
 caller_bodies={}
 for n in caller_names:
  for s in syms:
   if s['name']==n:
    lo=int(s['addr']);hi=lo+int(s['size']);ii=bisect.bisect_left(addrs,lo);jj=bisect.bisect_left(addrs,hi)
    caller_bodies.setdefault(n,[]).append({'addr':hex(lo),'size':int(s['size']),'body':texts[ii:jj]})
 report={'schema':'mmonochrom.bf561.processing-callgraph-fix1.v1','parser_fix':'accepts 0x0xADDR emitted by GNU objdump','selected_symbols':[{'name':s['name'],'addr':hex(int(s['addr'])),'size':int(s['size'])} for s in selected],'calls_to_selected':calls,'selected_functions':funcs,'caller_bodies':caller_bodies,'relevant_indirect_calls':indirect,'classification':'corrected_processing_queue_to_setprocess_run_callgraph','questions':['Does Task_TaskInterpolation call IM_GetHead then IM_SetCurrentJob and SetProcess?','What exact pointer is placed in R0 before SetProcess?','Where does Run get invoked and with which R0/R1 objects?'],'guardrails':['Older caller-count results from probes using a single-0x regex are superseded where objdump emitted 0x0x targets.','Production RAWSCALAR1B remains frozen.']}
 (a.outdir/'MM_BF561_PROCESSING_CALLGRAPH_FIX1.json').write_text(json.dumps(report,indent=2)+'\n')
 with (a.outdir/'MM_BF561_PROCESSING_CALLGRAPH_FIX1.txt').open('w') as f:
  f.write(json.dumps({'calls':[(x['site'],x['from']['name'] if x['from'] else None,x['to']['name']) for x in calls],'caller_names':caller_names,'indirect_count':len(indirect)},indent=2)+'\n')
  for x in calls:f.write('\n===== CALL =====\n'+json.dumps(x,indent=2)+'\n')
  for n,arr in caller_bodies.items():
   for x in arr:f.write(f"\n===== CALLER {n} {x['addr']} =====\n"+'\n'.join(x['body'])+'\n')
 print(json.dumps({'calls':[(x['site'],x['from']['name'] if x['from'] else None,x['to']['name']) for x in calls],'caller_names':caller_names,'indirect_count':len(indirect)},indent=2))
if __name__=='__main__':main()
