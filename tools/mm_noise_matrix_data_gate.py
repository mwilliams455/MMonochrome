#!/usr/bin/env python3
"""Fast canonical PROCESS/LUTS matrix gate; no disassembler required."""
from __future__ import annotations
import argparse,hashlib,json,pathlib,struct,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad
from recover_leica_m9_mm_shared_key import MM_DEC_SHA
ROWS=5; WORDS=19; ISO=16
NOISE_SECTION=0x134; NOISE=0x13c; SHARP_SECTION=0x408; SHARP=0x410
EXPECTED_SHARP=[8,8,8,8,4,4,4,4,4,4,4,4,3,3,2,2]
def sha(b):return hashlib.sha256(b).hexdigest()
def lump(root,path):
 d=root
 for n in path:
  x=next((z for z in pwad.parse_pwad(d) if z.name.upper()==n.upper()),None)
  if x is None:raise KeyError('/'.join(path))
  d=x.data
 return d
def mat(b,o):
 v=struct.unpack_from('<'+'I'*(ROWS*WORDS),b,o)
 return [list(v[r*WORDS:(r+1)*WORDS]) for r in range(ROWS)]
def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path,required=True);a=ap.parse_args()
 fw=a.mm_decrypted.read_bytes()
 if sha(fw)!=MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
 b=lump(fw,['LUTS','PROCESS','LUTS']); noise=mat(b,NOISE); sharp=mat(b,SHARP)
 header=list(struct.unpack_from('<18I',b,4))
 out={'schema':'mmonochrom.noise-matrix-data-gate1a.v1','process_luts_sha256':sha(b),'header_offsets':[hex(x) for x in header],'sections':{'noise':hex(NOISE_SECTION),'sharp':hex(SHARP_SECTION)},'matrix_offsets':{'noise':hex(NOISE),'sharp':hex(SHARP)},'noise_rows':noise,'sharp_rows':sharp,'noise_standard_selector2_iso16':noise[2][:ISO],'noise_standard_tail':noise[2][ISO:],'sharp_standard_selector2_iso16':sharp[2][:ISO],'sharp_positive_control':sharp[2][:ISO]==EXPECTED_SHARP,'parallel_plus8':NOISE==NOISE_SECTION+8 and SHARP==SHARP_SECTION+8,'classification':'archive_data_gate_not_alone_loader_proof'}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(out,indent=2)+'\n')
 print(json.dumps({'noise_standard':out['noise_standard_selector2_iso16'],'noise_tail':out['noise_standard_tail'],'sharp_standard':out['sharp_standard_selector2_iso16'],'sharp_positive_control':out['sharp_positive_control']},indent=2))
if __name__=='__main__':main()
