#!/usr/bin/env python3
"""Trace Leica M Monochrom 1.022 Toning controls and consumers.

Evidence-only. No firmware bytes are emitted.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, struct, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad
from recover_leica_m9_mm_shared_key import MM_DEC_SHA

RAM=0x20000
BF547_SHA="8f82e5eb08c4933d821ce3df903a14846e300f940fee353514d37cda2c70b621"
HUE_CONTROL=0x1029
STRENGTH_CONTROL=0x1030
HUE_MENU_OFF=0xBE758
STRENGTH_MENU_OFF=0xBE7E0
REG_HUE_OFF=0xC0A48
REG_STRENGTH_OFF=0xC0A60
MENU_STRIDE=20
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')
CALL_RE=re.compile(r'\b(CALL|JUMP(?:\.L|\.S)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)',re.I)

def sha(b): return hashlib.sha256(b).hexdigest()

def component(root):
    hits=[]
    def rec(d,depth=0):
        if depth>4 or d[:4]!=b'PWAD': return
        for x in pwad.parse_pwad(d):
            if x.name.upper()=='BF547': hits.append(x.data)
            if x.data[:4]==b'PWAD': rec(x.data,depth+1)
    rec(root)
    if len(hits)!=1: raise RuntimeError(f'BF547 hits={len(hits)}')
    return hits[0]

def cstr(b,off):
    return b[off:].split(b'\0',1)[0].decode('ascii','replace')

def menu_record(b,off):
    ptr,val=struct.unpack_from('<II',b,off)
    if ptr<RAM: raise AssertionError(f'bad menu ptr {ptr:#x}')
    return {'file_off':hex(off),'string':cstr(b,ptr-RAM),'value':val,'ptr':hex(ptr)}

def reg_record(b,off):
    vals=struct.unpack_from('<6I',b,off)
    return {
        'file_off':hex(off),
        'control_id':hex(vals[0]),
        'menu_ptr':hex(vals[1]),
        'state_ptr':hex(vals[2]),
        'reserved':hex(vals[3]),
        'callback':hex(vals[4]),
        'tail':hex(vals[5]),
    }

def disasm(objdump,b,work):
    p=work/'bf547.bin'; p.write_bytes(b)
    r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],
        capture_output=True,text=True,check=True)
    p.unlink(); return r.stdout.splitlines()

def ao(line):
    m=ADDR_RE.match(line); return int(m.group(1),16) if m else -1

def function_window(lines,addr,limit=500):
    start=None
    for i,l in enumerate(lines):
        if ao(l)==addr:
            start=i;break
    if start is None:
        # nearest boundary
        cand=[(abs(ao(l)-addr),i) for i,l in enumerate(lines) if ao(l)>=0 and abs(ao(l)-addr)<=4]
        if not cand:return []
        start=min(cand)[1]
    out=[]
    for l in lines[start:start+limit]:
        out.append(l)
        if re.search(r'\bRTS\b',l): break
    return out

def direct_xrefs(lines,target):
    out=[]
    for i,l in enumerate(lines):
        m=CALL_RE.search(l)
        if m and int(m.group(2),16)==target:
            out.append({'site':hex(ao(l)),'kind':m.group(1),'context':lines[max(0,i-40):min(len(lines),i+45)]})
    return out

def literal_hits(b,target):
    n=struct.pack('<I',target);out=[];p=0
    while True:
        p=b.find(n,p)
        if p<0:break
        out.append(hex(RAM+p));p+=1
    return out

def split_refs(lines,target):
    hi=(target>>16)&0xffff;lo=target&0xffff
    hi_re=re.compile(rf'\b([RP][0-7])\.H\s*=\s*0x{hi:x}\b',re.I)
    lo_re=re.compile(rf'\b([RP][0-7])\.L\s*=\s*0x{lo:x}\b',re.I)
    out=[]
    for i,l in enumerate(lines):
        first=hi_re.search(l) or lo_re.search(l)
        if not first:continue
        reg=first.group(1).upper()
        looking=lo_re if hi_re.search(l) else hi_re
        for j in range(i+1,min(len(lines),i+18)):
            other=looking.search(lines[j])
            if other and other.group(1).upper()==reg:
                out.append({'first':hex(ao(l)),'second':hex(ao(lines[j])),'reg':reg,
                    'context':lines[max(0,i-28):min(len(lines),j+60)]})
                break
    return out

def profile_field_consumers(lines):
    """Find windows that reconstruct active_profile*0xac and read +0x18/+0x1c."""
    out=[]
    for i,l in enumerate(lines):
        if not re.search(r'\b0xac\b',l,re.I):
            continue
        ctx=lines[max(0,i-45):min(len(lines),i+90)]
        text='\n'.join(ctx)
        if '0x488' not in text:
            continue
        reads=[]
        for x in ctx:
            if re.search(r'=\s*\[[P][0-7]\s*\+\s*0x(?:18|1c)\]',x,re.I):
                reads.append(x)
        if reads:
            out.append({'site':hex(ao(l)),'reads':reads,'context':ctx})
    # dedupe overlapping sites by first read line text
    uniq=[];seen=set()
    for x in out:
        key=tuple(x['reads'])
        if key in seen: continue
        seen.add(key);uniq.append(x)
    return uniq

def string_refs(lines,bf,file_off):
    target=RAM+file_off
    return {'target':hex(target),'literal_hits':literal_hits(bf,target),'split_refs':split_refs(lines,target)}

def call_targets_in_range(lines,lo,hi):
    out=[]
    for i,l in enumerate(lines):
        m=CALL_RE.search(l)
        if not m: continue
        t=int(m.group(2),16)
        if lo <= t < hi:
            out.append({'site':hex(ao(l)),'target':hex(t),'context':lines[max(0,i-20):min(len(lines),i+25)]})
    return out

def u32_window(bf,runtime_addr,count=32,before_words=4):
    off=runtime_addr-RAM-before_words*4
    if off<0 or off+(count+before_words)*4>len(bf): return []
    vals=struct.unpack_from('<'+('I'*(count+before_words)),bf,off)
    return [{'addr':hex(RAM+off+i*4),'value':hex(v)} for i,v in enumerate(vals)]

def literal_offset_accesses(lines,offset):
    pat=re.compile(rf'0x{offset:x}\b',re.I)
    out=[]
    for i,l in enumerate(lines):
        if pat.search(l):
            out.append({'site':hex(ao(l)),'line':l,'context':lines[max(0,i-60):min(len(lines),i+100)]})
    return out

def offset_accesses(lines,offsets):
    out={}
    for off in offsets:
        pat=re.compile(rf'\[[^\]]+\+\s*0x{off:x}\]',re.I)
        rows=[]
        for i,l in enumerate(lines):
            if pat.search(l):
                rows.append({'site':hex(ao(l)),'line':l,'context':lines[max(0,i-55):min(len(lines),i+85)]})
        out[hex(off)]=rows
    return out

def address_window(lines,lo,hi):
    return [l for l in lines if lo <= ao(l) < hi]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('mm_decrypted',type=pathlib.Path)
    ap.add_argument('--objdump',type=pathlib.Path,required=True)
    ap.add_argument('--outdir',type=pathlib.Path,required=True)
    a=ap.parse_args()
    mm=a.mm_decrypted.read_bytes()
    if sha(mm)!=MM_DEC_SHA: raise SystemExit('MM decrypted SHA mismatch')
    bf=component(mm)
    if sha(bf)!=BF547_SHA: raise SystemExit('BF547 SHA mismatch')
    a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/'_work';work.mkdir(exist_ok=True)
    lines=disasm(a.objdump,bf,work)
    for p in work.iterdir():p.unlink()
    work.rmdir()

    hue=[menu_record(bf,HUE_MENU_OFF+i*MENU_STRIDE) for i in range(3)]
    strength=[menu_record(bf,STRENGTH_MENU_OFF+i*MENU_STRIDE) for i in range(3)]
    if [(x['string'],x['value']) for x in hue] != [('Sepia',0),('Cool',1),('Selenium',2)]:
        raise AssertionError(hue)
    if [(x['string'],x['value']) for x in strength] != [('Off',0),('Weak',1),('Strong',2)]:
        raise AssertionError(strength)

    hr=reg_record(bf,REG_HUE_OFF); sr=reg_record(bf,REG_STRENGTH_OFF)
    if int(hr['control_id'],16)!=HUE_CONTROL or int(sr['control_id'],16)!=STRENGTH_CONTROL:
        raise AssertionError('control registration mismatch')
    hcb=int(hr['callback'],16); scb=int(sr['callback'],16)
    hstate=int(hr['state_ptr'],16); sstate=int(sr['state_ptr'],16)

    targets={
      'hue_callback':hcb,'strength_callback':scb,
      'hue_state':hstate,'strength_state':sstate,
      'hue_control':HUE_CONTROL,'strength_control':STRENGTH_CONTROL,
    }
    refs={}
    for name,t in targets.items():
        refs[name]={
            'target':hex(t),
            'literal_hits':literal_hits(bf,t),
            'split_refs':split_refs(lines,t),
            'direct_xrefs':direct_xrefs(lines,t) if name in ('hue_callback','strength_callback','hue_state','strength_state') else [],
        }

    report={
      'schema':'mmonochrom.toning1a.trace.v1',
      'firmware':'Leica M Monochrom 1.022',
      'bf547_sha256':sha(bf),
      'menu':{'hue':hue,'strength':strength},
      'controls':{'hue':hr,'strength':sr},
      'callbacks':{
        'hue':function_window(lines,hcb),
        'strength':function_window(lines,scb),
      },
      'getters':{
        'hue':function_window(lines,hstate),
        'strength':function_window(lines,sstate),
      },
      'refs':refs,
      'profile_field_consumers':profile_field_consumers(lines),
      'jpeg_string_refs':{
        'LoadJPEG':string_refs(lines,bf,0xCD83C),
        'AbortJPEG':string_refs(lines,bf,0xCD848),
        'ErrorJPEG':string_refs(lines,bf,0xCD854),
        'ColorMatrix':string_refs(lines,bf,0xCE36C),
        'ConvertYCrCb':string_refs(lines,bf,0xCE378),
        'YCrCb':string_refs(lines,bf,0xCFCD8),
      },
      'job_toning_field_accesses':offset_accesses(lines,[0x450,0x454,0x458,0x45c]),
      'job_builder_window':address_window(lines,0x37600,0x37a80),
      'job_builder_function':{
        'address':'0x376c4',
        'body':address_window(lines,0x376c4,0x379a4),
        'direct_callers':direct_xrefs(lines,0x376c4),
        'literal_hits':literal_hits(bf,0x376c4),
        'split_refs':split_refs(lines,0x376c4),
      },
      'job_builder_call_targets':call_targets_in_range(lines,0x37600,0x37a80),
      'strength_resolver':{
        'address':'0xaba8c',
        'body':address_window(lines,0xaba8c,0xabb80),
        'direct_xrefs':direct_xrefs(lines,0xaba8c),
        'state_formula':'strength==0 ? 0 : strength + 2*hue',
        'state_map':{
          'Off':0,'Sepia Weak':1,'Sepia Strong':2,
          'Cool Weak':3,'Cool Strong':4,
          'Selenium Weak':5,'Selenium Strong':6
        },
        'table_root_runtime':'0xdb7ac',
        'table_root_refs':{
          'literal_hits':literal_hits(bf,0xdb7ac),
          'split_refs':split_refs(lines,0xdb7ac),
        },
        'table_u32_window':u32_window(bf,0xdb7ac,48,8),
        'parameter_offset_d42c_accesses':literal_offset_accesses(lines,0xd42c),
        'parameter_offset_d430_accesses':literal_offset_accesses(lines,0xd430),
      },
      'jpeg_debug_windows':{
        'LoadJPEG':address_window(lines,0x638b0,0x63b40),
        'ColorMatrix_ConvertYCrCb':address_window(lines,0x79040,0x79160),
      },
      'manual_semantics':{
        'hue':['Sepia','Blue/Cool','Selenium'],
        'strength':['Off','Weak','Strong'],
        'jpeg_only':True,
      },
      'guardrails':[
        'Menu enum closure does not prove color arithmetic.',
        'Do not implement RGB tint constants until the JPEG toning consumer is traced.',
        'DNG must remain unaffected.'
      ]
    }
    (a.outdir/'MM_TONING1A_TRACE.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_TONING1A_TRACE.txt').open('w') as f:
        f.write(json.dumps({k:v for k,v in report.items() if k not in ('callbacks','refs')},indent=2)+'\n')
        for name,body in report['callbacks'].items():
            f.write(f'\n===== {name.upper()} SETTER =====\n'+'\n'.join(body)+'\n')
        for name,body in report['getters'].items():
            f.write(f'\n===== {name.upper()} GETTER =====\n'+'\n'.join(body)+'\n')
        f.write('\n===== JOB BUILDER 0x376C4 =====\n'+'\n'.join(report['job_builder_function']['body'])+'\n')
        f.write('\n===== JOB BUILDER CALLERS =====\n'+json.dumps(report['job_builder_function']['direct_callers'],indent=2)+'\n')
        f.write('\n===== JOB BUILDER BROAD WINDOW =====\n'+'\n'.join(report['job_builder_window'])+'\n')
        f.write('\n===== JOB BUILDER CALL TARGETS =====\n'+json.dumps(report['job_builder_call_targets'],indent=2)+'\n')
        f.write('\n===== STRENGTH RESOLVER 0xABA8C =====\n'+'\n'.join(report['strength_resolver']['body'])+'\n')
        f.write('\n===== STRENGTH STATE MAP =====\n'+json.dumps(report['strength_resolver']['state_map'],indent=2)+'\n')
        f.write('\n===== STRENGTH TABLE ROOT REFS =====\n'+json.dumps(report['strength_resolver']['table_root_refs'],indent=2)+'\n')
        f.write('\n===== STRENGTH TABLE ROOT 0xDB7AC =====\n'+json.dumps(report['strength_resolver']['table_u32_window'],indent=2)+'\n')
        f.write('\n===== PARAM OFFSET D42C ACCESSES =====\n'+json.dumps(report['strength_resolver']['parameter_offset_d42c_accesses'],indent=2)+'\n')
        f.write('\n===== PARAM OFFSET D430 ACCESSES =====\n'+json.dumps(report['strength_resolver']['parameter_offset_d430_accesses'],indent=2)+'\n')
        f.write('\n===== JOB TONING FIELD ACCESSES =====\n'+json.dumps(report['job_toning_field_accesses'],indent=2)+'\n')
        f.write('\n===== JPEG DEBUG WINDOWS =====\n'+json.dumps(report['jpeg_debug_windows'],indent=2)+'\n')
        f.write('\n===== PROFILE FIELD CONSUMERS =====\n'+json.dumps(report['profile_field_consumers'],indent=2)+'\n')
        f.write('\n===== JPEG STRING REFERENCES =====\n'+json.dumps(report['jpeg_string_refs'],indent=2)+'\n')
        f.write('\n===== REFERENCES =====\n'+json.dumps(refs,indent=2)+'\n')
    print(json.dumps({
        'hue':[(x['string'],x['value']) for x in hue],
        'strength':[(x['string'],x['value']) for x in strength],
        'hue_callback':hex(hcb),'strength_callback':hex(scb),
        'hue_state':hex(hstate),'strength_state':hex(sstate),
        'hue_state_refs':len(refs['hue_state']['split_refs']),
        'strength_state_refs':len(refs['strength_state']['split_refs'])
    },indent=2))

if __name__=='__main__': main()
