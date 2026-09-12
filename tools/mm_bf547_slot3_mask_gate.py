#!/usr/bin/env python3
"""Close the M Monochrom BF547 slot-3 process-mask source.

Evidence gathered by earlier probes:
- 0x39edc maps processing slots to record types.
- slot 3 maps to type 0, so the 0x39ffc special type-3 branch is bypassed.
- the transmitted 37-byte record lives at state+0x12c.
- routine 0x36ff4 computes state+0x12c and calls 0xb7e84 with R2=4 and
  source 0xeb440.

This probe extracts the real Monochrom four-byte template at 0xeb440, its set
bits, all direct references/callers of the initializer, and the relevant
callee/slot-mapper disassembly. It publishes only derived integer/hash/text
evidence, never firmware bytes.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import MM_DEC_SHA  # noqa: E402

RAM=0x20000
INIT=0x36ff4
COPY=0xb7e84
SLOT_MAP=0x39edc
TEMPLATE=0xeb440
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')
TRANSFER_RE=re.compile(r'\b(CALL|JUMP(?:\.L|\.S)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)', re.I)

def sha(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def component(root:bytes)->bytes:
    hits=[]
    def rec(d:bytes,k:int=0):
        if k>4 or d[:4]!=b'PWAD': return
        for x in pwad.parse_pwad(d):
            if x.name.upper()=='BF547': hits.append(x.data)
            if x.data[:4]==b'PWAD': rec(x.data,k+1)
    rec(root)
    if len(hits)!=1: raise RuntimeError(f'BF547 hits={len(hits)}')
    return hits[0]
def disasm(objdump:pathlib.Path,b:bytes,w:pathlib.Path)->list[str]:
    p=w/'bf547.bin';p.write_bytes(b)
    r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],capture_output=True,text=True,check=True)
    p.unlink();return r.stdout.splitlines()
def ao(l:str)->int:
    m=ADDR_RE.match(l);return int(m.group(1),16) if m else -1
def window(lines:list[str],addr:int,before:int=20,after:int=120)->list[str]:
    idx=next((i for i,l in enumerate(lines) if ao(l)==addr),None)
    return [] if idx is None else lines[max(0,idx-before):min(len(lines),idx+after)]
def xrefs(lines:list[str],target:int)->list[dict]:
    out=[]
    for i,l in enumerate(lines):
        m=TRANSFER_RE.search(l)
        if m and int(m.group(2),16)==target:
            out.append({'site':hex(ao(l)),'kind':m.group(1),'context':lines[max(0,i-90):min(len(lines),i+70)]})
    return out
def split_refs(lines:list[str],target:int)->list[dict]:
    hi=(target>>16)&0xffff;lo=target&0xffff
    hr=re.compile(rf'\b([RP][0-7])\.H\s*=\s*0x{hi:x}\b',re.I)
    lr=re.compile(rf'\b([RP][0-7])\.L\s*=\s*0x{lo:x}\b',re.I)
    out=[]
    for i,l in enumerate(lines):
        a=hr.search(l);b=lr.search(l)
        if not(a or b): continue
        reg=(a or b).group(1).upper()
        for j in range(i+1,min(len(lines),i+18)):
            c=lr.search(lines[j]) if a else hr.search(lines[j])
            if c and c.group(1).upper()==reg:
                out.append({'first_site':hex(ao(l)),'second_site':hex(ao(lines[j])),'register':reg,'context':lines[max(0,i-35):min(len(lines),j+65)]})
                break
    return out
def bits(v:int)->list[int]: return [i for i in range(32) if v&(1<<i)]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if sha(fw)!=MM_DEC_SHA: raise SystemExit('MM SHA mismatch')
    bf=component(fw);a.outdir.mkdir(parents=True,exist_ok=True);w=a.outdir/'_work';w.mkdir(exist_ok=True)
    lines=disasm(a.objdump,bf,w)
    for p in w.iterdir():p.unlink()
    w.rmdir()
    off=TEMPLATE-RAM
    if off<0 or off+4>len(bf): raise SystemExit('template outside BF547')
    word=int.from_bytes(bf[off:off+4],'little')
    slot_map={0:0,1:2,2:3,3:0,4:3,5:3}
    report={
      'schema':'mmonochrom.bf547.slot3-mask-gate1a.v1',
      'bf547_sha256':sha(bf),
      'template_runtime':hex(TEMPLATE),
      'template_u32':hex(word),
      'template_u32_sha256':sha(bf[off:off+4]),
      'template_set_bits':bits(word),
      'named_bits':{
        'bit1_shading':bool(word&(1<<1)),
        'bit2_blinker':bool(word&(1<<2)),
        'bit6_noise':bool(word&(1<<6)),
        'bit7_sharp':bool(word&(1<<7)),
        'bit8_contrast':bool(word&(1<<8)),
        'bit9_y':bool(word&(1<<9)),
      },
      'slot_to_record_type':slot_map,
      'slot3_record_type':slot_map[3],
      'slot3_enters_type3_special_branch':slot_map[3]==3,
      'initializer':{'addr':hex(INIT),'window':window(lines,INIT,20,170),'direct_xrefs':xrefs(lines,INIT)},
      'copy_helper':{'addr':hex(COPY),'window':window(lines,COPY,10,100),'direct_xrefs_nearby_count':len(xrefs(lines,COPY))},
      'slot_mapper':{'addr':hex(SLOT_MAP),'window':window(lines,SLOT_MAP,8,50)},
      'template_address_refs':split_refs(lines,TEMPLATE),
      'classification':'direct_monochrom_persistent_process_mask_source',
      'guardrails':[
        'The template word is the normal persistent record initializer only if 0x36ff4 is on the state initialization path used by the slot-3 still/JPEG state; direct caller evidence is included for that closure.',
        'Slot 3 maps to type 0, so the type-3 special branch at 0x39ffc is not taken for the hard-coded slot-3 submission.',
        'Do not use the earlier 0xF2C38 cross-camera probe as the Monochrom mask source; it has no matching Monochrom address-construction path.'
      ]
    }
    (a.outdir/'MM_BF547_SLOT3_MASK_GATE.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF547_SLOT3_MASK_GATE.txt').open('w') as f:
        f.write(json.dumps({k:report[k] for k in ('template_runtime','template_u32','template_set_bits','named_bits','slot_to_record_type','slot3_record_type','slot3_enters_type3_special_branch')},indent=2)+'\n')
        f.write('\n===== INITIALIZER =====\n'+'\n'.join(report['initializer']['window'])+'\n')
        f.write('\n===== INITIALIZER XREFS =====\n'+json.dumps(report['initializer']['direct_xrefs'],indent=2)+'\n')
        f.write('\n===== COPY HELPER =====\n'+'\n'.join(report['copy_helper']['window'])+'\n')
        f.write('\n===== SLOT MAPPER =====\n'+'\n'.join(report['slot_mapper']['window'])+'\n')
        f.write('\n===== TEMPLATE ADDRESS REFS =====\n'+json.dumps(report['template_address_refs'],indent=2)+'\n')
    print(json.dumps({'template_u32':hex(word),'bits':bits(word),'named_bits':report['named_bits'],'slot3_type':slot_map[3],'initializer_xrefs':[(x['site'],x['kind']) for x in report['initializer']['direct_xrefs']]},indent=2))
if __name__=='__main__': main()
