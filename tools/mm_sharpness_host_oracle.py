#!/usr/bin/env python3
"""Firmware-exact M Monochrom Standard sharpness host oracle.

Uses canonical PROCESS/LUTS bank, proven Standard selector-2 ISO schedule,
proven modifier integer arithmetic, LUT helper, two-stage [1,2,1]/4 Gaussian,
and closed normal photographic geometry Bin=0 -> B=2.

Two independent host implementations must match bit-for-bit on frozen synthetic
vectors before Android A/B work is allowed.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,struct,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad
from recover_leica_m9_mm_shared_key import MM_DEC_SHA

BANK=0x58c; ROWS=16; COUNT=2050; ROWBYTES=4100
ISOS=[320,400,500,640,800,1000,1250,1600,2000,2500,3200,4000,5000,6400,8000,10000]
STD_CODES=[8,8,8,8,4,4,4,4,4,4,4,4,3,3,2,2]
MOD={2:(1,1),3:(3,2),4:(1,0),8:(2,0)}
BORDER=2

def sha(b):return hashlib.sha256(b).hexdigest()
def lump(root,path):
 d=root
 for n in path:
  x=next((z for z in pwad.parse_pwad(d) if z.name.upper()==n.upper()),None)
  if x is None:raise KeyError('/'.join(path))
  d=x.data
 return d
def pack16(v):return struct.pack('<'+'H'*len(v),*v)
def scale_row(row,code):
 if code not in MOD:raise ValueError(code)
 mul,shift=MOD[code];out=[]
 for x in row:
  y=(x*mul)>>shift
  if y<-2048:y=-2048
  elif y>2048:y=2048
  out.append(y)
 return out
def corr(table,detail):
 clip=-table[0]
 if detail < -1024:return -clip
 if detail > 1024:return clip
 return table[1024+detail]
def apply_a(src,w,h,table):
 out=list(src);scratch=[0]*(w*h);B=BORDER
 if w-2*B<=0 or h-2*B<=0:return out
 # firmware horizontal rectangle: x=B..W-B-1, y=B-1..H-B
 for y in range(B-1,h-B+1):
  row=y*w
  for x in range(B,w-B):
   scratch[row+x]=(src[row+x-1]+2*src[row+x]+src[row+x+1])>>2
 # vertical/detail rectangle: x=B..W-B-1, y=B..H-B-1
 for y in range(B,h-B):
  row=y*w
  for x in range(B,w-B):
   p=row+x
   blur=(scratch[p-w]+2*scratch[p]+scratch[p+w])>>2
   d=src[p]-blur
   v=src[p]+corr(table,d)
   out[p]=0 if v<0 else 16383 if v>16383 else v
 return out
def apply_b(src,w,h,table):
 out=list(src);B=BORDER
 if w-2*B<=0 or h-2*B<=0:return out
 # Independent direct evaluation of the same two independently shifted stages.
 for y in range(B,h-B):
  for x in range(B,w-B):
   hs=[]
   for yy in (y-1,y,y+1):
    p=yy*w+x
    hs.append((src[p-1]+2*src[p]+src[p+1])>>2)
   blur=(hs[0]+2*hs[1]+hs[2])>>2
   p=y*w+x;d=src[p]-blur;v=src[p]+corr(table,d)
   out[p]=0 if v<0 else 16383 if v>16383 else v
 return out
def border_same(a,b,w,h,B=2):
 for y in range(h):
  for x in range(w):
   if x<B or x>=w-B or y<B or y>=h-B:
    if a[y*w+x]!=b[y*w+x]:return False
 return True
def vectors():
 out=[]
 def add(name,w,h,pix):out.append((name,w,h,[max(0,min(16383,int(x))) for x in pix]))
 add('constant8192',9,9,[8192]*81)
 w,h=13,11;add('ramp',w,h,[(x*997+y*137)%16384 for y in range(h) for x in range(w)])
 w,h=17,15;p=[4096]*(w*h);p[(h//2)*w+w//2]=16383;add('impulse',w,h,p)
 w,h=16,16;add('checker',w,h,[15000 if ((x+y)&1) else 1000 for y in range(h) for x in range(w)])
 w,h=19,17;s=0x13579bdf;p=[]
 for _ in range(w*h):
  s=(1664525*s+1013904223)&0xffffffff;p.append((s>>12)&0x3fff)
 add('lcg',w,h,p)
 add('small_guard',4,4,[i*100 for i in range(16)])
 return out
def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path,required=True);a=ap.parse_args()
 fw=a.mm_decrypted.read_bytes()
 if sha(fw)!=MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
 luts=lump(fw,['LUTS','PROCESS','LUTS']);bank=luts[BANK:BANK+ROWS*ROWBYTES]
 rows=[list(struct.unpack_from('<'+'h'*COUNT,bank,i*ROWBYTES)) for i in range(ROWS)]
 results=[]
 for slot,(iso,code,row) in enumerate(zip(ISOS,STD_CODES,rows)):
  table=scale_row(row,code)
  # LUT helper edge probes include the unused +1025 sentinel boundary.
  helper={str(d):corr(table,d) for d in (-2048,-1025,-1024,-1,0,1,1024,1025,2048)}
  vr=[]
  for name,w,h,src in vectors():
   aout=apply_a(src,w,h,table);bout=apply_b(src,w,h,table)
   if aout!=bout:raise SystemExit(f'oracle mismatch iso={iso} vector={name}')
   if not border_same(src,aout,w,h):raise SystemExit(f'border changed iso={iso} vector={name}')
   if any(x<0 or x>16383 for x in aout):raise SystemExit('range failure')
   changed=sum(x!=y for x,y in zip(src,aout))
   vr.append({'name':name,'w':w,'h':h,'input_sha256':sha(pack16(src)),'output_sha256':sha(pack16(aout)),'changed_pixels':changed,'min':min(aout),'max':max(aout),'border_unchanged':True})
  results.append({'slot':slot,'iso':iso,'modifier_code':code,'base_row_sha256':sha(bank[slot*ROWBYTES:(slot+1)*ROWBYTES]),'modified_row_sha256':sha(struct.pack('<'+'h'*COUNT,*table)),'table0':table[0],'table1024':table[1024],'table2049_unused':table[2049],'lut_helper_probes':helper,'vectors':vr})
 report={'schema':'mmonochrom.sharpness-host-oracle1a.v1','firmware_sha256':sha(fw),'process_luts_sha256':sha(luts),'bank_offset':hex(BANK),'bank_sha256':sha(bank),'selector':'Standard=2','iso_slots':ISOS,'modifier_codes':STD_CODES,'incoming_border':0,'sharp_added_border':2,'effective_border':2,'algorithm':'two independent integer implementations; horizontal and vertical shifts each >>2; LUT center index 1024; clamp14','results':results,'all_dual_implementations_match':True,'all_borders_unchanged':True}
 a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({'bank_sha256':report['bank_sha256'],'effective_border':2,'isos':[(r['iso'],r['modifier_code'],[(v['name'],v['output_sha256'][:12],v['changed_pixels']) for v in r['vectors']]) for r in results]},indent=2))
if __name__=='__main__':main()
