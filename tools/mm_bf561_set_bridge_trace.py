#!/usr/bin/env python3
"""Decode BF561 Set() bridge called by SetProcess immediately before Run.

Corrected callgraph closes:
  SetProcess(job, param=0xfeb00268, runtime=0xfeb002f8)
    -> Set(runtime, param)
    -> InitL1MemoryProcessing(param, runtime)
  StartInterpolation_Jolos -> Run(runtime, param)

This probe emits the complete mapped Set() bodies and mechanically inventories
loads/stores involving low offsets of the two arguments, especially offset 0,
to determine how the Run header mask is produced.
"""
from __future__ import annotations
import argparse,bisect,json,pathlib,re,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa:E402
import mm_sharpness_consumer_trace as base  # noqa:E402

TARGETS=(0xfeb1160c,0xfeb18e6c)
TRANSFER_RE=re.compile(r'\b(?:CALL|JUMP(?:\.S|\.L)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b',re.I)

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
 def body(target):
  o=owner(target)
  if not o or not o['inside']:return []
  st=int(o['start'],16);hi=st+o['size'];i=bisect.bisect_left(addrs,st);j=bisect.bisect_left(addrs,hi)
  return texts[i:j]
 def callers(target):
  out=[]
  for i,(addr,text,*_) in enumerate(lines):
   m=TRANSFER_RE.search(text)
   if m and int(m.group(1),16)==target:
    out.append({'site':hex(addr),'owner':owner(addr),'context':texts[max(0,i-35):min(len(texts),i+25)]})
  return out
 result={}
 for t in TARGETS:
  b=body(t)
  low=[x for x in b if re.search(r'\[(?:P[0-5]|R[0-7])(?:\s*\+\s*0x(?:0|4|8|c|10|14|18|1c|20|24|28|2c|30))?\]',x,re.I)]
  result[hex(t)]={'owner':owner(t),'body':b,'low_offset_memory_lines':low,'callers':callers(t)}
 report={'schema':'mmonochrom.bf561.set-bridge-trace1a.v1','functions':result,'classification':'setprocess_to_run_header_bridge_evidence','closed_call_contract':'SetProcess calls Set(R0=runtime 0xfeb002f8, R1=parameter 0xfeb00268) before Run(runtime,param).','questions':['Does Set copy param[0] to runtime[0]?','Does Set transform or mask the first word before runtime[0]?','Which additional runtime header words are copied from param?'],'guardrails':['Track argument register reassignment before naming source/destination.','Production RAWSCALAR1B remains frozen.']}
 (a.outdir/'MM_BF561_SET_BRIDGE_TRACE.json').write_text(json.dumps(report,indent=2)+'\n')
 with (a.outdir/'MM_BF561_SET_BRIDGE_TRACE.txt').open('w') as f:
  for t,d in result.items():
   f.write(f"\n===== SET {t} owner={d['owner']} =====\n"+'\n'.join(d['body'])+'\n')
   f.write('\nLOW-OFFSET MEMORY\n'+'\n'.join(d['low_offset_memory_lines'])+'\n')
   f.write('\nCALLERS\n'+json.dumps(d['callers'],indent=2)+'\n')
 print(json.dumps({t:{'owner':d['owner'],'callers':[(x['site'],x['owner']['name'] if x['owner'] else None) for x in d['callers']],'low_offset_line_count':len(d['low_offset_memory_lines'])} for t,d in result.items()},indent=2))
if __name__=='__main__':main()
