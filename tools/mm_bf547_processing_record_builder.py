#!/usr/bin/env python3
"""Decode the BF547 Processing-Settings record builder that tail-calls 0x6d2a8.

A canonical disassembly probe proved 0x39fde is JUMP.L 0x6d2a8 with R1=P5.
Therefore P5 is the exact 37-byte payload copied into SportNet request+7 and
ultimately into the BF561 processing record. This probe preserves the complete
builder body and its callers, and mechanically inventories stores to P5 so the
process mask / Sharpness / Noise fields can be recovered from Monochrom itself.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, subprocess, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import MM_DEC_SHA  # noqa: E402
RAM=0x20000
BUILDER=0x39f1c
TAIL=0x39fde
TARGET=0x6d2a8
END=0x39fe2
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')
TRANSFER_RE=re.compile(r'\b(CALL|JUMP(?:\.L|\.S)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)',re.I)

def sha(b):return hashlib.sha256(b).hexdigest()
def comp(root):
 h=[]
 def rec(d,k=0):
  if k>4 or d[:4]!=b'PWAD':return
  for x in pwad.parse_pwad(d):
   if x.name.upper()=='BF547':h.append(x.data)
   if x.data[:4]==b'PWAD':rec(x.data,k+1)
 rec(root)
 if len(h)!=1:raise RuntimeError(f'BF547 hits={len(h)}')
 return h[0]
def disasm(objdump,b,w):
 p=w/'bf547.bin';p.write_bytes(b)
 r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],capture_output=True,text=True,check=True)
 p.unlink();return r.stdout.splitlines()
def ao(l):
 m=ADDR_RE.match(l);return int(m.group(1),16) if m else -1
def rng(lines,lo,hi):return [l for l in lines if lo<=ao(l)<hi]
def refs(lines,target):
 out=[]
 for i,l in enumerate(lines):
  m=TRANSFER_RE.search(l)
  if m and int(m.group(2),16)==target:
   out.append({'site':hex(ao(l)),'kind':m.group(1),'context':lines[max(0,i-90):min(len(lines),i+40)]})
 return out

def main():
 ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
 mm=a.mm_decrypted.read_bytes()
 if sha(mm)!=MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
 bf=comp(mm);a.outdir.mkdir(parents=True,exist_ok=True);w=a.outdir/'_work';w.mkdir(exist_ok=True);lines=disasm(a.objdump,bf,w)
 for p in w.iterdir():p.unlink()
 w.rmdir()
 body=rng(lines,BUILDER,END)
 broad=rng(lines,0x39e80,0x3a010)
 p5stores=[l for l in body if re.search(r'(?:B|W)?\[P5(?:\s*\+[^\]]+)?\]\s*=',l,re.I)]
 p5loads=[l for l in body if re.search(r'=\s*(?:B|W)?\[P5(?:\s*\+[^\]]+)?\]',l,re.I)]
 source_reads=[l for l in body if re.search(r'=\s*(?:B|W)?\[(?:P2|P3|P4|R7)(?:\s*\+[^\]]+)?\]',l,re.I)]
 report={'schema':'mmonochrom.bf547.processing-record-builder1a.v1','bf547_sha256':sha(bf),'builder':hex(BUILDER),'tail_site':hex(TAIL),'tail_target':hex(TARGET),'builder_body':body,'broad_context':broad,'p5_stores':p5stores,'p5_loads':p5loads,'source_reads':source_reads,'builder_refs':refs(lines,BUILDER),'tail_target_refs':refs(lines,TARGET),'classification':'direct_processing_payload_builder_evidence','closed_input_fact':'At 0x39fde, R1=P5 then JUMP.L 0x6d2a8; prior trace proves 0x6d2a8 transmits R1 as the 37-byte selector-4 payload.','questions':['What writes P5 offsets +0..+3 (process mask)?','Which P5 offsets map to Sharpness and Noise?','Are Sharp and Noise enabled in the normal still/JPEG mask?','What normal Noise mode/value is copied?'],'guardrails':['Use only stores/copies in this builder to name Monochrom payload fields.','Do not substitute M9 field/default values where Monochrom stores are not directly closed.','Production RAWSCALAR1B remains frozen.']}
 (a.outdir/'MM_BF547_PROCESSING_RECORD_BUILDER.json').write_text(json.dumps(report,indent=2)+'\n')
 with (a.outdir/'MM_BF547_PROCESSING_RECORD_BUILDER.txt').open('w') as f:
  f.write(json.dumps({'builder':hex(BUILDER),'tail':hex(TAIL),'target':hex(TARGET),'builder_ref_sites':[(x['site'],x['kind']) for x in report['builder_refs']],'target_ref_sites':[(x['site'],x['kind']) for x in report['tail_target_refs']]},indent=2)+'\n')
  f.write('\n===== COMPLETE BUILDER =====\n'+'\n'.join(body)+'\n')
  f.write('\n===== P5 STORES =====\n'+'\n'.join(p5stores)+'\n')
  f.write('\n===== SOURCE READS =====\n'+'\n'.join(source_reads)+'\n')
  f.write('\n===== BUILDER REFERENCES =====\n'+json.dumps(report['builder_refs'],indent=2)+'\n')
 print(json.dumps({'builder_refs':[(x['site'],x['kind']) for x in report['builder_refs']],'target_refs':[(x['site'],x['kind']) for x in report['tail_target_refs']],'p5_store_count':len(p5stores)},indent=2))
if __name__=='__main__':main()
