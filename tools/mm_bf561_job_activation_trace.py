#!/usr/bin/env python3
"""Trace BF561 queued processing-list activation into SetProcess/Run.

SetProcess and Run have no ordinary/static callers in the initialized BF561
image, so treat them as exported/scheduler entrypoints.  Starting from the
known receive/list path, this probe resolves the post-append calls made by
IM_AppendItem and inventories symbols/calls around current-job/list activation,
then dumps nearby exported processing functions around SetProcess and Run.

Evidence-only; no firmware bytes are emitted.
"""
from __future__ import annotations
import argparse,bisect,json,pathlib,re,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa:E402
import mm_sharpness_consumer_trace as base  # noqa:E402

TARGET_ADDRS=(0xffa13944,0xffa02a40,0xffa02a10,0xffa1045a,0xffa03928,0xffa127d0,0xffa01790,0xffa03fb2,0xffa03fc8,0xffa1034c)
NAME_RE=re.compile(r'(Job|Process|Processing|Append|Head|Current|Run|Set|Queue|List|Start|Execute|Image)',re.I)
TRANSFER_RE=re.compile(r'\b(?:CALL|JUMP(?:\.S|\.L)?)\s+(?:0x)?([0-9a-fA-F]+)\b',re.I)

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
 fw=a.mm_decrypted.read_bytes()
 if base.sha(fw)!=base.MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
 outer=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=='BF561'),None)
 if outer is None:raise SystemExit('BF561 missing')
 cmap={x.name.lower():x for x in pwad.parse_pwad(outer.data)};syms=base.parse_map(cmap['bf0.map'].data);blocks=base.parse_ldr(cmap['bf0'].data)
 a.outdir.mkdir(parents=True,exist_ok=True);w=a.outdir/'_work';w.mkdir(exist_ok=True);lines=base.disassemble_blocks(blocks,a.objdump,w)
 for p in w.iterdir():p.unlink()
 w.rmdir()
 addrs=[x[0] for x in lines];texts=[x[1] for x in lines]
 ordered=sorted((int(s['addr']),s['name'],int(s['size'])) for s in syms);starts=[x[0] for x in ordered]
 def owner(addr):
  i=bisect.bisect_right(starts,addr)-1
  if i<0:return None
  st,n,sz=ordered[i];return {'name':n,'start':hex(st),'size':sz,'offset':addr-st,'inside':addr<st+max(1,sz)}
 def function_for_addr(addr):
  own=owner(addr)
  if not own or not own['inside']:return {'addr':hex(addr),'owner':own,'body':[]}
  st=int(own['start'],16);hi=st+own['size'];i=bisect.bisect_left(addrs,st);j=bisect.bisect_left(addrs,hi)
  return {'addr':hex(addr),'owner':own,'body':texts[i:j]}
 def direct_callers(target):
  out=[]
  for i,(addr,text,*_) in enumerate(lines):
   m=TRANSFER_RE.search(text)
   if m and int(m.group(1),16)==target:
    out.append({'site':hex(addr),'owner':owner(addr),'context':texts[max(0,i-35):min(len(texts),i+30)]})
  return out
 targets={hex(t):{'function':function_for_addr(t),'direct_callers':direct_callers(t)} for t in TARGET_ADDRS}
 # all named functions relevant to activation, with call graph edges among them
 relevant=[s for s in syms if NAME_RE.search(s['name'])]
 relevant.sort(key=lambda s:int(s['addr']))
 rstarts={int(s['addr']):s['name'] for s in relevant}
 edges=[]
 for i,(addr,text,*_) in enumerate(lines):
  m=TRANSFER_RE.search(text)
  if not m:continue
  t=int(m.group(1),16)
  if t in rstarts:
   own=owner(addr)
   if own and NAME_RE.search(own['name']):edges.append({'site':hex(addr),'from':own,'to':{'name':rstarts[t],'addr':hex(t)},'context':texts[max(0,i-18):min(len(texts),i+15)]})
 report={'schema':'mmonochrom.bf561.job-activation-trace1a.v1','targets':targets,'relevant_symbols':[{'name':s['name'],'addr':hex(int(s['addr'])),'size':int(s['size'])} for s in relevant],'activation_call_edges':edges,'classification':'queued_job_to_exported_processing_entrypoint_evidence','questions':['What do IM_AppendItem post-calls do after constructing the 68-byte record?','Where is g_CurrentProcessingSetti populated relative to SetProcess invocation?','Which object is passed as SetProcess R0 by the external scheduler/entry ABI?'],'guardrails':['Absence of an internal caller means do not invent one; exported/scheduler invocation must be inferred only from ABI/state evidence.','Do not identify record+0x2c as process mask until SetProcess R0 identity is closed.','Production RAWSCALAR1B remains frozen.']}
 (a.outdir/'MM_BF561_JOB_ACTIVATION_TRACE.json').write_text(json.dumps(report,indent=2)+'\n')
 with (a.outdir/'MM_BF561_JOB_ACTIVATION_TRACE.txt').open('w') as f:
  for t,d in targets.items():
   f.write(f"\n===== TARGET {t} owner={d['function']['owner']} =====\n")
   f.write('\n'.join(d['function']['body'])+'\n')
   f.write('\nCALLERS\n'+json.dumps(d['direct_callers'],indent=2)+'\n')
  f.write('\n===== ACTIVATION EDGES =====\n'+json.dumps(edges,indent=2)+'\n')
 print(json.dumps({'targets':{k:v['function']['owner'] for k,v in targets.items()},'caller_counts':{k:len(v['direct_callers']) for k,v in targets.items()},'activation_edge_count':len(edges)},indent=2))
if __name__=='__main__':main()
