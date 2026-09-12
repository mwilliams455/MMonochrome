#!/usr/bin/env python3
"""Resolve original M Monochrom BF561 processing-list helper semantics.

Evidence-only. Focuses on the helper cluster around 0xffa10300..0xffa10420 used
by PlatformStartup and Task_TaskInterpolation. It identifies exact map symbols,
disassembles the helpers, traces their callers, and records list geometry so the
source of the 68-byte active processing record can be closed without importing
M9 BF547 controller assumptions.
"""
from __future__ import annotations

import argparse, bisect, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as tr  # noqa: E402

CLUSTER_LO=0xFFA102E0
CLUSTER_HI=0xFFA10420
FOCUS=(0xFFA1031A,0xFFA1034C,0xFFA103B8,0xFEB108A0,0xFFA03E74,0xFEB107F8)
TRANSFER=re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b",re.I)


def getbf(fw: bytes):
    bf=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=="BF561"),None)
    if bf is None: raise RuntimeError('outer BF561 missing')
    c={x.name.lower():x for x in pwad.parse_pwad(bf.data)}
    return tr.parse_map(c['bf0.map'].data),tr.parse_ldr(c['bf0'].data)


def owner_table(syms):
    ordered=sorted((int(s['addr']),int(s['size']),s['name']) for s in syms if int(s['size'])>0)
    starts=[x[0] for x in ordered]
    def owner(addr):
        i=bisect.bisect_right(starts,addr)-1
        if i<0:return None
        st,sz,n=ordered[i]
        return None if addr>=st+sz else {'name':n,'addr':hex(st),'size':sz,'offset':addr-st}
    return owner,ordered


def func_dis(dis, addr, size):
    return '\n'.join(text for a,text,*_ in dis if addr<=a<addr+size)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if tr.sha(fw)!=tr.MM_DEC_SHA:raise SystemExit(f'MM decrypted SHA mismatch {tr.sha(fw)}')
    syms,blocks=getbf(fw);owner,ordered=owner_table(syms)
    a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/'_work';work.mkdir(exist_ok=True)
    dis=tr.disassemble_blocks(blocks,a.objdump,work);text=[x[1] for x in dis]

    cluster=[]
    for st,sz,n in ordered:
        if CLUSTER_LO<=st<CLUSTER_HI:
            cluster.append({'name':n,'addr':hex(st),'size':sz,'disassembly':func_dis(dis,st,sz)})

    focus={hex(x):owner(x) for x in FOCUS}
    focus_functions={}
    for x in FOCUS:
        o=owner(x)
        if o:
            st=int(o['addr'],16);focus_functions[hex(x)]={'owner':o,'disassembly':func_dis(dis,st,o['size'])}

    # collect every direct transfer to any function in cluster/focus owner set
    targets={st:(n,sz) for st,sz,n in ordered if CLUSTER_LO<=st<CLUSTER_HI}
    for x in FOCUS:
        o=owner(x)
        if o: targets[int(o['addr'],16)]=(o['name'],o['size'])
    calls=[]
    for i,(addr,line,*_) in enumerate(dis):
        m=TRANSFER.search(line)
        if not m:continue
        t=int(m.group(1),16)
        if t in targets:
            calls.append({'site':hex(addr),'owner':owner(addr),'target':hex(t),'target_name':targets[t][0],'context':text[max(0,i-14):min(len(text),i+24)]})

    # Explicitly decode list header geometry closed from IM_AppendItem.
    geometry={
      'g_ProcessingList_addr':'0xfeb1e0a8','total_size':956,'header_bytes':4,
      'record_bytes':68,'max_records':14,'identity':'4 + 14*68 = 956',
      'IM_AppendItem_fields':{'list_plus_1':'current_record_count_byte','list_plus_2':'capacity_or_limit_checked_against_14','record_base':'list+4+count*68','initial_copy_bytes':37},
      'Task_TaskInterpolation_temp_record_bytes':68,
      'IM_SetCurrentJob_copy_words':17,
    }
    report={'schema':'mmonochrom.processinglist.helperprobe1a.v1','firmware_decrypted_sha256':tr.sha(fw),'cluster_symbols':cluster,'focus_owners':focus,'focus_functions':focus_functions,'callsites':calls,'list_geometry':geometry,
      'questions':['What does helper at 0xffa103b8 return/update before each interpolation iteration?','What exact record selection/interpolation does helper at 0xffa1034c perform into the 68-byte temporary record?','Does first u32 process mask pass through unchanged or get interpolated/selected specially?']}
    (a.outdir/'MM_PROCESSINGLIST_HELPER_PROBE.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_PROCESSINGLIST_HELPER_PROBE.txt').open('w') as f:
        f.write('M Monochrom processing-list helper probe\n\n')
        f.write('List geometry:\n'+json.dumps(geometry,indent=2)+'\n\n')
        f.write('Cluster symbols:\n')
        for q in cluster:f.write(f"{q['addr']} size={q['size']} {q['name']}\n")
        for q in cluster:f.write(f"\n===== {q['name']} {q['addr']} size={q['size']} =====\n{q['disassembly']}\n")
        f.write('\nFocus callsites:\n')
        for q in calls:
            f.write(f"\nsite={q['site']} owner={q['owner']} -> {q['target_name']} {q['target']}\n")
            for line in q['context']:f.write(line+'\n')
    print(json.dumps({'focus_owners':focus,'cluster_symbols':[{k:q[k] for k in ('name','addr','size')} for q in cluster],'callsites':[{k:q[k] for k in ('site','owner','target','target_name')} for q in calls]},indent=2))
    for p in work.iterdir():p.unlink()
    work.rmdir()
if __name__=='__main__':main()
