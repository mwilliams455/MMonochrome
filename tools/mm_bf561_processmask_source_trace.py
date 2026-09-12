#!/usr/bin/env python3
"""Trace the true M Monochrom BF561 process-mask source.

A prior schedule probe closed that SetProcess copies source+0x2c into
runtime_process+0, and Run dispatches from runtime_process+0.  This probe
mechanically follows that field upstream through SPI_AppendSettings,
IM_AppendItem, processing-list/current-job helpers and all mapped functions
whose names are relevant.  It also inventories direct stores/loads at +0x2c
inside those functions and direct/indirect callers of SetProcess.

Evidence-only: no firmware binary bytes are emitted.
"""
from __future__ import annotations
import argparse, bisect, hashlib, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as base  # noqa: E402

NAME_RE = re.compile(r'(SetProcess|AppendSettings|AppendItem|CurrentJob|ProcessingList|ProcessingSet|GetHead|SetCurrent|StructParameter)', re.I)
TRANSFER_RE = re.compile(r'\b(?:CALL|JUMP(?:\.S|\.L)?)\s+(?:0x)?([0-9a-fA-F]+)\b', re.I)
OFF2C_RE = re.compile(r'\+\s*0x2c\]', re.I)

def sha(b: bytes) -> str: return hashlib.sha256(b).hexdigest()

def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument('mm_decrypted', type=pathlib.Path)
    ap.add_argument('--objdump', type=pathlib.Path, required=True)
    ap.add_argument('--outdir', type=pathlib.Path, required=True)
    a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if base.sha(fw) != base.MM_DEC_SHA: raise SystemExit('MM decrypted SHA mismatch')
    outer=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=='BF561'),None)
    if outer is None: raise SystemExit('BF561 missing')
    cmap={x.name.lower():x for x in pwad.parse_pwad(outer.data)}
    syms=base.parse_map(cmap['bf0.map'].data)
    blocks=base.parse_ldr(cmap['bf0'].data)
    a.outdir.mkdir(parents=True,exist_ok=True)
    work=a.outdir/'_work'; work.mkdir(exist_ok=True)
    lines=base.disassemble_blocks(blocks,a.objdump,work)
    for p in work.iterdir(): p.unlink()
    work.rmdir()
    addrs=[x[0] for x in lines]
    ordered=sorted((int(s['addr']),s['name'],int(s['size'])) for s in syms)
    starts=[x[0] for x in ordered]
    def owner(addr:int):
        i=bisect.bisect_right(starts,addr)-1
        if i<0:return None
        st,n,sz=ordered[i]
        return {'name':n,'start':hex(st),'size':sz,'offset':addr-st,'inside':addr<st+max(1,sz)}
    relevant=[s for s in syms if NAME_RE.search(s['name'])]
    relevant.sort(key=lambda s:int(s['addr']))
    funcs={}
    for s in relevant:
        lo=int(s['addr']);hi=lo+int(s['size'])
        i=bisect.bisect_left(addrs,lo);j=bisect.bisect_left(addrs,hi)
        text=[x[1] for x in lines[i:j]]
        funcs.setdefault(s['name'],[]).append({'addr':hex(lo),'size':int(s['size']),'disassembly':'\n'.join(text),'off2c_lines':[x for x in text if OFF2C_RE.search(x)]})
    target_starts={int(s['addr']):s['name'] for s in relevant}
    calls=[]
    for idx,(addr,text,_src,_ln) in enumerate(lines):
        m=TRANSFER_RE.search(text)
        if not m: continue
        t=int(m.group(1),16)
        if t in target_starts:
            calls.append({'site':hex(addr),'owner':owner(addr),'target':hex(t),'target_name':target_starts[t],'context':[x[1] for x in lines[max(0,idx-35):min(len(lines),idx+25)]]})
    # Global +0x2c accesses in mapped BF561 code, retaining owning symbol.
    off2c=[]
    for idx,(addr,text,_src,_ln) in enumerate(lines):
        if OFF2C_RE.search(text):
            off2c.append({'site':hex(addr),'owner':owner(addr),'line':text,'context':[x[1] for x in lines[max(0,idx-18):min(len(lines),idx+22)]]})
    # SetProcess bodies, summarized around the exact source+0x2c -> runtime+0 write.
    setprocess=[]
    for k,v in funcs.items():
        if k=='SetProcess': setprocess.extend(v)
    report={
      'schema':'mmonochrom.bf561.processmask-source-trace1a.v1',
      'firmware_decrypted_sha256':base.sha(fw),
      'classification':'true_runtime_process_mask_field_trace',
      'relevant_symbols':[{'name':s['name'],'addr':hex(int(s['addr'])),'size':int(s['size'])} for s in relevant],
      'functions':funcs,
      'calls_to_relevant_symbols':calls,
      'all_offset_0x2c_accesses':off2c,
      'setprocess':setprocess,
      'closed_observation':'SetProcess source+0x2c is copied into runtime_process+0 before Run; runtime_process+0 is the BITTST dispatch word.',
      'questions':[
        'Which processing-list/current-job function writes source-record +0x2c?',
        'Is +0x2c derived from the 37-byte BF547 payload, a per-list template, or a BF561-side mode table?',
        'What exact +0x2c value reaches normal still/JPEG Run, and are bits 6/7 set?'
      ],
      'guardrails':[
        'Do not interpret the 0x31343133 record marker at source+0 as the Run mask.',
        'Do not infer normal Sharp/Noise state until source+0x2c provenance and value are closed.',
        'Production RAWSCALAR1B remains frozen.'
      ]
    }
    (a.outdir/'MM_BF561_PROCESSMASK_SOURCE_TRACE.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF561_PROCESSMASK_SOURCE_TRACE.txt').open('w') as f:
        f.write('Relevant symbols:\n')
        for s in report['relevant_symbols']: f.write(json.dumps(s)+'\n')
        f.write('\n=== +0x2c accesses ===\n')
        for x in off2c:
            f.write(json.dumps({'site':x['site'],'owner':x['owner'],'line':x['line']})+'\n')
            for l in x['context']: f.write('  '+l+'\n')
        f.write('\n=== relevant callsites ===\n')
        for x in calls:
            f.write(f"\n{x['site']} {x['owner']} -> {x['target_name']} {x['target']}\n")
            for l in x['context']: f.write(l+'\n')
        for name,arr in funcs.items():
            if NAME_RE.search(name):
                for x in arr:
                    f.write(f"\n===== {name} {x['addr']} size={x['size']} =====\n{x['disassembly']}\n")
    print(json.dumps({'relevant_symbols':report['relevant_symbols'],'off2c_accesses':[(x['site'],x['owner']['name'] if x['owner'] else None,x['line']) for x in off2c],'call_count':len(calls)},indent=2))
if __name__=='__main__': main()
