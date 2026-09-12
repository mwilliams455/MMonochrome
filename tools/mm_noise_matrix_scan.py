#!/usr/bin/env python3
"""Scan canonical Monochrom PROCESS/LUTS Noise section for the 5x19 mode matrix."""
from __future__ import annotations
import argparse,hashlib,json,pathlib,struct,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad
from recover_leica_m9_mm_shared_key import MM_DEC_SHA
SEC0=0x134;SEC1=0x408;ROWS=5;COLS=19;ISO=16;N=ROWS*COLS
SHARP=0x410;EXPECTED=[8,8,8,8,4,4,4,4,4,4,4,4,3,3,2,2]
def sha(b):return hashlib.sha256(b).hexdigest()
def lump(root,path):
 d=root
 for n in path:
  x=next((z for z in pwad.parse_pwad(d) if z.name.upper()==n.upper()),None)
  if x is None:raise KeyError('/'.join(path))
  d=x.data
 return d
def vals(b,o):return list(struct.unpack_from('<'+'I'*N,b,o))
def rows(v):return [v[i*COLS:(i+1)*COLS] for i in range(ROWS)]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path,required=True);a=ap.parse_args()
 fw=a.mm_decrypted.read_bytes()
 if sha(fw)!=MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
 b=lump(fw,['LUTS','PROCESS','LUTS']);c=[]
 for o in range(SEC0,SEC1-N*4+1,4):
  r=rows(vals(b,o)); iso=[x for rr in r for x in rr[:ISO]]; tails=[rr[ISO:] for rr in r]
  invalid=sum(x>3 for x in iso); neg1=sum(x==0xffffffff for x in iso); distinct=len(set(iso)); nonzero=sum(x!=0 for x in iso)
  # expected menu-off row should plausibly be mostly/all zero, and selector rows should remain mode-sized.
  row0_bad=sum(x>3 for x in r[0][:ISO]); row0_nonzero=sum(x!=0 for x in r[0][:ISO])
  score=invalid*1000+neg1*1000+row0_bad*100+row0_nonzero*3 + (0 if distinct>=2 else 20)
  c.append({'offset':hex(o),'score':score,'invalid_mode_values':invalid,'distinct_iso_values':sorted(set(iso))[:20],'nonzero_iso_values':nonzero,'rows':r,'tails':tails})
 c.sort(key=lambda x:(x['score'],x['offset']))
 sharp=rows(vals(b,SHARP))
 report={'schema':'mmonochrom.noise-matrix-scan1a.v1','process_luts_sha256':sha(b),'scan_range':[hex(SEC0),hex(SEC1)],'matrix_shape':[ROWS,COLS],'consumer_constraint':'first 16 u32 per row must be Process_Noise modes 0..3','top_candidates':c[:25],'sharp_positive_control':sharp[2][:ISO]==EXPECTED,'sharp_standard':sharp[2][:ISO]}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'sharp_positive_control':report['sharp_positive_control'],'top':[{k:x[k] for k in ('offset','score','invalid_mode_values','distinct_iso_values','nonzero_iso_values')} for x in c[:10]]},indent=2))
if __name__=='__main__':main()
