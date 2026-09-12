#!/usr/bin/env python3
"""Locate the indirect dispatch/table entry for BF547 Processing-Settings sender 0x6d2a8.

Direct CALL and split-immediate searches found no callers, so this probe treats
0x6d2a8 as a likely function-table/vtable target. It finds raw u32 references,
decodes neighboring table words as addresses/integers, and traces references to
the containing table region. Evidence-only; no firmware binary is emitted.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, struct, subprocess, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import MM_DEC_SHA  # noqa: E402
RAM=0x20000
TARGET=0x6d2a8
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')

def sha(b): return hashlib.sha256(b).hexdigest()
def comp(root):
 hits=[]
 def rec(d,dep=0):
  if dep>4 or d[:4]!=b'PWAD': return
  for x in pwad.parse_pwad(d):
   if x.name.upper()=='BF547': hits.append(x.data)
   if x.data[:4]==b'PWAD': rec(x.data,dep+1)
 rec(root)
 if len(hits)!=1: raise RuntimeError(f'BF547 hits={len(hits)}')
 return hits[0]
def disasm(objdump,b,work):
 p=work/'bf547.bin';p.write_bytes(b)
 r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],capture_output=True,text=True,check=True)
 p.unlink();return r.stdout.splitlines()
def ao(l):
 m=ADDR_RE.match(l);return int(m.group(1),16) if m else -1
def all_u32(b,v):
 n=struct.pack('<I',v);out=[];p=0
 while True:
  p=b.find(n,p)
  if p<0:return out
  out.append(RAM+p);p+=1
def codeish(v,b): return RAM<=v<RAM+len(b) and (v&1)==0
def split_refs(lines,target):
 hi=(target>>16)&0xffff;lo=target&0xffff
 hr=re.compile(rf'\b([RP][0-7])\.H\s*=\s*0x{hi:x}\b',re.I);lr=re.compile(rf'\b([RP][0-7])\.L\s*=\s*0x{lo:x}\b',re.I)
 out=[]
 for i,l in enumerate(lines):
  a=hr.search(l);b=lr.search(l)
  if not(a or b):continue
  reg=(a or b).group(1).upper()
  for j in range(i+1,min(len(lines),i+20)):
   c=lr.search(lines[j]) if a else hr.search(lines[j])
   if c and c.group(1).upper()==reg:
    ctx=lines[max(0,i-35):min(len(lines),j+70)]
    out.append({'first_site':hex(ao(l)),'second_site':hex(ao(lines[j])),'register':reg,'indirect_transfers':[x for x in ctx if re.search(rf'\b(?:CALL|JUMP)\s*\(\s*{reg}\s*\)',x,re.I)],'context':ctx});break
 return out
def direct_literal_refs(lines,target):
 # objdump may print an absolute data address in memory operands/comments.
 hx=f'{target:x}'.lower();out=[]
 for i,l in enumerate(lines):
  if hx in l.lower() and ao(l)!=target:
   out.append({'site':hex(ao(l)),'line':l,'context':lines[max(0,i-30):min(len(lines),i+55)]})
 return out[:200]
def table_window(b,addr,radius_words=24):
 off=addr-RAM;start=max(0,(off//4-radius_words)*4);end=min(len(b),(off//4+radius_words+1)*4)
 rows=[]
 for o in range(start,end,4):
  v=struct.unpack_from('<I',b,o)[0]
  rows.append({'addr':hex(RAM+o),'relative_words':(o-off)//4,'value':hex(v),'code_range':codeish(v,b),'target':v==TARGET})
 return rows

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
 mm=a.mm_decrypted.read_bytes()
 if sha(mm)!=MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
 bf=comp(mm);a.outdir.mkdir(parents=True,exist_ok=True);w=a.outdir/'_work';w.mkdir(exist_ok=True);lines=disasm(a.objdump,bf,w)
 for p in w.iterdir():p.unlink()
 w.rmdir()
 hits=all_u32(bf,TARGET)
 hit_rows=[]
 for h in hits:
  # Probe aligned candidate table bases from 0..64 bytes before hit so we can see
  # which nearby addresses are themselves referenced as object/vtable pointers.
  bases=[]
  for delta in range(0,68,4):
   base=h-delta
   bases.append({'candidate_base':hex(base),'u32_pointer_hits':[hex(x) for x in all_u32(bf,base)],'split_refs':split_refs(lines,base)})
  hit_rows.append({'target_pointer_addr':hex(h),'table_window':table_window(bf,h),'candidate_bases':bases})
 report={'schema':'mmonochrom.bf547.payload-dispatch-table1a.v1','bf547_sha256':sha(bf),'target':hex(TARGET),'target_u32_hits':[hex(x) for x in hits],'target_split_refs':split_refs(lines,TARGET),'target_text_refs':direct_literal_refs(lines,TARGET),'hits':hit_rows,'classification':'indirect_dispatch_table_evidence','guardrails':['A raw u32 target hit suggests a function table only when neighboring words and table-base xrefs support that interpretation.','Do not equate a table slot with a normal still/JPEG call until the owning object and callsite are traced.','Keep RAWSCALAR1B production frozen.']}
 (a.outdir/'MM_BF547_PAYLOAD_DISPATCH_TABLE.json').write_text(json.dumps(report,indent=2)+'\n')
 with (a.outdir/'MM_BF547_PAYLOAD_DISPATCH_TABLE.txt').open('w') as f:
  f.write(json.dumps({'target':hex(TARGET),'u32_hits':[hex(x) for x in hits],'split_ref_count':len(report['target_split_refs']),'text_ref_count':len(report['target_text_refs'])},indent=2)+'\n')
  for x in hit_rows:
   f.write(f"\n===== POINTER {x['target_pointer_addr']} =====\n")
   f.write(json.dumps(x,indent=2)+'\n')
 print(json.dumps({'target_u32_hits':[hex(x) for x in hits],'target_split_refs':len(report['target_split_refs']),'target_text_refs':len(report['target_text_refs'])},indent=2))
if __name__=='__main__':main()
