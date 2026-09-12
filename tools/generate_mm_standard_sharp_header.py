#!/usr/bin/env python3
"""Generate build-local M Monochrom Standard sharpness LUT header.

Reads only a hash-verified decrypted M Monochrom 1.022 image and writes the 16
already-modified Standard sharp rows needed by the Android A/B. Firmware bytes
are not committed to the repository.
"""
from __future__ import annotations
import argparse,hashlib,pathlib,struct,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad
MM_DEC_SHA='c9e14ee475408802c83774f37b19c85c57663d9840e8e4c2cfe80e14dec9a7ae'
BANK_OFFSET=0x58c
ROWS=16
COUNT=2050
ROW_BYTES=4100
ISOS=[320,400,500,640,800,1000,1250,1600,2000,2500,3200,4000,5000,6400,8000,10000]
CODES=[8,8,8,8,4,4,4,4,4,4,4,4,3,3,2,2]
MOD={2:(1,1),3:(3,2),4:(1,0),8:(2,0)}
EXPECTED_BANK_SHA='282a6e7eb0603203d5ddb36f32862e0340a9cc2d24c35b4c0af2b1bd79c06d10'
def sha(b):return hashlib.sha256(b).hexdigest()
def find_lump(root,path):
 d=root
 for name in path:
  hit=next((x for x in pwad.parse_pwad(d) if x.name.upper()==name.upper()),None)
  if hit is None:raise KeyError('/'.join(path))
  d=hit.data
 return d
def scale(row,code):
 mul,shift=MOD[code];out=[]
 for x in row:
  y=(x*mul)>>shift
  if y<-2048:y=-2048
  elif y>2048:y=2048
  out.append(y)
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path,required=True);a=ap.parse_args()
 fw=a.mm_decrypted.read_bytes()
 if sha(fw)!=MM_DEC_SHA:raise SystemExit('MM decrypted SHA mismatch')
 luts=find_lump(fw,['LUTS','PROCESS','LUTS']);bank=luts[BANK_OFFSET:BANK_OFFSET+ROWS*ROW_BYTES]
 if len(bank)!=ROWS*ROW_BYTES or sha(bank)!=EXPECTED_BANK_SHA:raise SystemExit(f'Sharp bank identity mismatch: {sha(bank)}')
 rows=[]
 for i,code in enumerate(CODES):
  raw=list(struct.unpack_from('<'+'h'*COUNT,bank,i*ROW_BYTES));rows.append(scale(raw,code))
 lines=[]
 lines.append('// GENERATED from canonical Leica M Monochrom 1.022; do not edit.')
 lines.append('// Source bank SHA256: '+EXPECTED_BANK_SHA)
 lines.append('#pragma once')
 lines.append('#include <cstdint>')
 lines.append('static constexpr int MM_MONO_STD_SHARP_ISO_COUNT = 16;')
 lines.append('static constexpr int MM_MONO_STD_SHARP_LUT_COUNT = 2050;')
 lines.append('static constexpr int MM_MONO_STD_SHARP_BORDER = 2;')
 lines.append('static constexpr int MM_MONO_STD_SHARP_ISOS[16] = {'+','.join(map(str,ISOS))+'};')
 lines.append('static constexpr int MM_MONO_STD_SHARP_CODES[16] = {'+','.join(map(str,CODES))+'};')
 lines.append('static constexpr int16_t MM_MONO_STD_SHARP_LUT[16][2050] = {')
 for i,row in enumerate(rows):
  lines.append('  { // ISO %d code %d' % (ISOS[i],CODES[i]))
  for j in range(0,COUNT,32):lines.append('    '+','.join(map(str,row[j:j+32]))+',')
  lines.append('  },')
 lines.append('};')
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text('\n'.join(lines)+'\n')
 print('bank_sha256='+sha(bank));print('header_sha256='+sha(a.out.read_bytes()));print('rows=16 count=2050 border=2')
if __name__=='__main__':main()
