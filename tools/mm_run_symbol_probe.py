#!/usr/bin/env python3
"""Resolve BF561 symbols around Run/Process_Sharpness helper addresses.

Derived symbol evidence only; no firmware payload output.
"""
from __future__ import annotations
import argparse,bisect,hashlib,json,pathlib,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad
import mm_sharpness_consumer_trace as base

TARGETS=[
  0xffa11ff8,0xffa03454,0xffa028e8,0xffa00b30,0xffa015d8,0xffa007c0,
  0xffa02718,0xffa13990,0xffa127d0,0xffa01790,0xffa0287c,0xffa12fcc,
]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
 fw=a.mm_decrypted.read_bytes()
 if base.sha(fw)!=base.MM_DEC_SHA: raise SystemExit('decrypted firmware SHA mismatch')
 bf=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=='BF561'),None)
 if bf is None: raise SystemExit('BF561 missing')
 cmap={x.name.lower():x for x in pwad.parse_pwad(bf.data)}
 syms=base.parse_map(cmap['bf0.map'].data)
 ordered=sorted(syms,key=lambda s:int(s['addr'])); starts=[int(s['addr']) for s in ordered]
 out=[]
 for t in TARGETS:
  exact=[s for s in ordered if int(s['addr'])==t]
  i=bisect.bisect_right(starts,t)-1
  near=[]
  for j in range(max(0,i-5),min(len(ordered),i+7)):
   s=ordered[j];lo=int(s['addr']);near.append({'name':s['name'],'addr':hex(lo),'size':int(s['size']),'delta':t-lo,'covers':lo<=t<lo+max(1,int(s['size']))})
  out.append({'target':hex(t),'exact':[{'name':s['name'],'size':int(s['size'])} for s in exact],'near':near})
 report={'schema':'mmonochrom.run.symbolprobe1a.v1','firmware_decrypted_sha256':base.sha(fw),'targets':out}
 a.outdir.mkdir(parents=True,exist_ok=True)
 (a.outdir/'MM_RUN_SYMBOL_PROBE.json').write_text(json.dumps(report,indent=2)+'\n')
 (a.outdir/'MM_RUN_SYMBOL_PROBE.txt').write_text('\n'.join(f"{x['target']} exact={x['exact']} near={x['near']}" for x in out)+'\n')
 print(json.dumps(out,indent=2))
if __name__=='__main__':main()
