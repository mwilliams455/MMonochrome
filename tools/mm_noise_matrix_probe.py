#!/usr/bin/env python3
"""Close the original M Monochrom Noise selector x ISO matrix.

Known runtime consumer in Set():
  selector = runtime+0x178
  iso_slot = runtime+0x7c
  mode = *(u32 *)(runtime + 0x198 + 76*selector + 4*iso_slot)
  runtime+0x17c = mode

Sharp uses the parallel runtime table at +0x478.  Its archive source is already
proven at PROCESS/LUTS 0x410, immediately after section header 0x408.
PROCESS/LUTS header also names section 0x134.  This probe disassembles
LoadLutArchiveL3, inventories archive/runtime offsets, extracts the candidate
5x19 u32 block at 0x13c (=0x134+8), and cross-checks the proven Sharp block at
0x410.  Geometry alone is not promoted; loader evidence is emitted alongside.
"""
from __future__ import annotations
import argparse,bisect,hashlib,json,pathlib,re,struct,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa:E402
import mm_sharpness_consumer_trace as base  # noqa:E402

NOISE_SECTION=0x134
NOISE_MATRIX=0x13c
SHARP_SECTION=0x408
SHARP_MATRIX=0x410
ROWS=5
WORDS_PER_ROW=19
ISO_COUNT=16
MATRIX_BYTES=ROWS*WORDS_PER_ROW*4
EXPECTED_SHARP_STD=[8,8,8,8,4,4,4,4,4,4,4,4,3,3,2,2]
TRANSFER_RE=re.compile(r'\b(CALL|JUMP(?:\.S|\.L)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b',re.I)

def sha(b):return hashlib.sha256(b).hexdigest()
def find_lump(root,path):
 cur=root
 for name in path:
  items=pwad.parse_pwad(cur); hit=next((x for x in items if x.name.upper()==name.upper()),None)
  if hit is None: raise KeyError('/'.join(path))
  cur=hit.data
 return cur
def u32s(b,off,n):return list(struct.unpack_from('<'+'I'*n,b,off))
def matrix(b,off):
 vals=u32s(b,off,ROWS*WORDS_PER_ROW)
 return [vals[i*WORDS_PER_ROW:(i+1)*WORDS_PER_ROW] for i in range(ROWS)]

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
 fw=a.mm_decrypted.read_bytes()
 if base.sha(fw)!=base.MM_DEC_SHA: raise SystemExit('MM SHA mismatch')
 luts=find_lump(fw,['LUTS','PROCESS','LUTS'])
 a.outdir.mkdir(parents=True,exist_ok=True)
 noise=matrix(luts,NOISE_MATRIX); sharp=matrix(luts,SHARP_MATRIX)
 # BF561 symbol/disassembly
 outer=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=='BF561'),None);cmap={x.name.lower():x for x in pwad.parse_pwad(outer.data)}
 syms=base.parse_map(cmap['bf0.map'].data);blocks=base.parse_ldr(cmap['bf0'].data)
 w=a.outdir/'_work';w.mkdir(exist_ok=True);lines=base.disassemble_blocks(blocks,a.objdump,w)
 for p in w.iterdir():p.unlink()
 w.rmdir()
 texts=[x[1] for x in lines];addrs=[x[0] for x in lines]
 ordered=sorted((int(s['addr']),s['name'],int(s['size'])) for s in syms);starts=[x[0] for x in ordered]
 def owner(addr):
  i=bisect.bisect_right(starts,addr)-1
  if i<0:return None
  st,n,sz=ordered[i];return {'name':n,'start':hex(st),'size':sz,'offset':addr-st,'inside':addr<st+max(1,sz)}
 loaders=[s for s in syms if s['name']=='LoadLutArchiveL3']
 loader_bodies=[]
 for s in loaders:
  lo=int(s['addr']);hi=lo+int(s['size']);i=bisect.bisect_left(addrs,lo);j=bisect.bisect_left(addrs,hi);b=texts[i:j]
  interesting=[x for x in b if re.search(r'0x(?:134|13c|198|408|410|478|17c|178|7c)\b',x,re.I) or 'CALL' in x or 'memcpy' in x.lower() or 'DMA' in x]
  loader_bodies.append({'addr':hex(lo),'size':int(s['size']),'body':b,'interesting':interesting})
 # scan full code for materializations/accesses of runtime table offsets and archive section constants
 pats={
  'noise_runtime_198':re.compile(r'0x198\b',re.I),
  'sharp_runtime_478':re.compile(r'0x478\b',re.I),
  'noise_archive_134':re.compile(r'0x134\b',re.I),
  'noise_archive_13c':re.compile(r'0x13c\b',re.I),
  'sharp_archive_408':re.compile(r'0x408\b',re.I),
  'sharp_archive_410':re.compile(r'0x410\b',re.I),
 }
 refs={k:[] for k in pats}
 for idx,(addr,text,*_) in enumerate(lines):
  for k,p in pats.items():
   if p.search(text): refs[k].append({'site':hex(addr),'owner':owner(addr),'line':text,'context':texts[max(0,idx-8):min(len(texts),idx+14)]})
 header=list(struct.unpack_from('<18I',luts,4))
 report={
  'schema':'mmonochrom.noise-matrix1a.v1',
  'process_luts_sha256':sha(luts),'process_luts_size':len(luts),
  'header_offsets':[hex(x) for x in header],
  'noise_candidate':{'section':hex(NOISE_SECTION),'matrix':hex(NOISE_MATRIX),'rows':noise,'standard_selector2_iso16':noise[2][:ISO_COUNT],'tail_metadata':noise[2][ISO_COUNT:]},
  'sharp_control':{'section':hex(SHARP_SECTION),'matrix':hex(SHARP_MATRIX),'rows':sharp,'standard_selector2_iso16':sharp[2][:ISO_COUNT],'matches_proven_standard':sharp[2][:ISO_COUNT]==EXPECTED_SHARP_STD,'tail_metadata':sharp[2][ISO_COUNT:]},
  'parallel_geometry':{'section_delta':SHARP_SECTION-NOISE_SECTION,'matrix_delta':SHARP_MATRIX-NOISE_MATRIX,'matrix_bytes':MATRIX_BYTES,'both_matrix_plus8':NOISE_MATRIX==NOISE_SECTION+8 and SHARP_MATRIX==SHARP_SECTION+8},
  'load_lut_archive_l3':loader_bodies,
  'code_refs':refs,
  'classification':'noise_matrix_candidate_with_loader_and_parallel_sharp_control',
  'promotion_rule':'Promote 0x13c as Noise selector x ISO matrix only if loader/runtime evidence links the 0x134 section to the runtime Noise structure/table; sharp 0x410 is the positive structural control.',
  'guardrails':['Do not infer Noise mode from visual preference.','Do not assume archive parallelism alone is consumer proof.','RAWSCALAR1B remains frozen.']
 }
 (a.outdir/'MM_NOISE_MATRIX_PROBE.json').write_text(json.dumps(report,indent=2)+'\n')
 with (a.outdir/'MM_NOISE_MATRIX_PROBE.txt').open('w') as f:
  f.write(json.dumps({'header_offsets':report['header_offsets'],'noise_std':noise[2][:ISO_COUNT],'noise_tail':noise[2][ISO_COUNT:],'sharp_std':sharp[2][:ISO_COUNT],'sharp_control_matches':report['sharp_control']['matches_proven_standard'],'loader_symbols':[(x['addr'],x['size']) for x in loader_bodies]},indent=2)+'\n')
  f.write('\n===== NOISE CANDIDATE 5x19 =====\n'+json.dumps(noise,indent=2)+'\n')
  f.write('\n===== SHARP CONTROL 5x19 =====\n'+json.dumps(sharp,indent=2)+'\n')
  for x in loader_bodies:f.write(f"\n===== LoadLutArchiveL3 {x['addr']} =====\n"+'\n'.join(x['body'])+'\n')
  f.write('\n===== CODE REFS =====\n'+json.dumps(refs,indent=2)+'\n')
 print(json.dumps({'noise_standard':noise[2][:ISO_COUNT],'noise_tail':noise[2][ISO_COUNT:],'sharp_standard':sharp[2][:ISO_COUNT],'sharp_control_matches':report['sharp_control']['matches_proven_standard'],'loader_count':len(loader_bodies)},indent=2))
if __name__=='__main__':main()
