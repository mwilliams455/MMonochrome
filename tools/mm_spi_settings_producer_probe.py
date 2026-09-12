#!/usr/bin/env python3
"""Trace the original M Monochrom settings packet into SPI_AppendSettings.

Evidence-only. Starts at the closed BF561 consumer SPI_AppendSettings (0xffa03e74),
finds every direct caller, recursively resolves caller ownership, and records the
register/pointer setup around each call so the 37-byte settings payload origin
and its message/dispatcher path can be recovered without importing M9 BF547
absolute addresses.

No firmware binary bytes are emitted.
"""
from __future__ import annotations

import argparse, bisect, json, pathlib, re, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
import mm_sharpness_consumer_trace as tr  # noqa: E402

TARGET = 0xFFA03E74
TRANSFER = re.compile(r"\b(?:call|jump(?:\.s|\.l)?)\s+(?:0x0x|0x)?([0-9a-fA-F]+)\b", re.I)
IMM = re.compile(r"0x([0-9a-fA-F]+)")


def getbf(fw: bytes):
    bf=next((x for x in pwad.parse_pwad(fw) if x.name.upper()=="BF561"),None)
    if bf is None: raise RuntimeError('outer BF561 missing')
    c={x.name.lower():x for x in pwad.parse_pwad(bf.data)}
    return tr.parse_map(c['bf0.map'].data),tr.parse_ldr(c['bf0'].data)


def owners(syms):
    arr=sorted((int(s['addr']),int(s['size']),s['name']) for s in syms if int(s['size'])>0)
    starts=[x[0] for x in arr]
    def own(addr):
        i=bisect.bisect_right(starts,addr)-1
        if i<0:return None
        st,sz,n=arr[i]
        if addr>=st+sz:return None
        return {'name':n,'addr':hex(st),'size':sz,'offset':addr-st}
    return own,arr


def function_lines(dis, o):
    if not o:return []
    lo=int(o['addr'],16);hi=lo+int(o['size'])
    return [text for a,text,*_ in dis if lo<=a<hi]


def direct_calls(dis, own, target):
    out=[]
    texts=[x[1] for x in dis]
    for i,(addr,line,*_) in enumerate(dis):
        m=TRANSFER.search(line)
        if not m or int(m.group(1),16)!=target:continue
        out.append({'site':hex(addr),'owner':own(addr),'context':texts[max(0,i-36):min(len(texts),i+24)]})
    return out


def recursive_callers(dis, own, seed, depth=3):
    levels=[]; targets={seed}; seen_targets=set()
    for d in range(depth):
        level=[]; next_targets=set()
        for t in sorted(targets):
            if t in seen_targets:continue
            seen_targets.add(t)
            for c in direct_calls(dis,own,t):
                c['target']=hex(t);level.append(c)
                o=c['owner']
                if o:next_targets.add(int(o['addr'],16))
        levels.append({'depth':d+1,'calls':level})
        targets=next_targets
        if not targets:break
    return levels


def referenced_constants(lines):
    vals=[]
    for line in lines:
        for m in IMM.finditer(line):
            v=int(m.group(1),16)
            if v<=0xffff: vals.append(v)
    # compact frequency table, useful for command IDs, sizes and offsets
    counts={}
    for v in vals:counts[v]=counts.get(v,0)+1
    return [{'value':hex(v),'decimal':v,'count':n} for v,n in sorted(counts.items(), key=lambda kv:(-kv[1],kv[0]))[:80]]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if tr.sha(fw)!=tr.MM_DEC_SHA:raise SystemExit(f'MM decrypted SHA mismatch {tr.sha(fw)}')
    syms,blocks=getbf(fw);own,arr=owners(syms)
    a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/'_work';work.mkdir(exist_ok=True)
    dis=tr.disassemble_blocks(blocks,a.objdump,work)
    chain=recursive_callers(dis,own,TARGET,4)

    # Collect unique owner bodies reached in the reverse call graph.
    bodies=[];seen=set()
    for level in chain:
        for c in level['calls']:
            o=c['owner']
            if not o:continue
            k=(o['addr'],o['name'])
            if k in seen:continue
            seen.add(k);lines=function_lines(dis,o)
            bodies.append({'owner':o,'constants':referenced_constants(lines),'disassembly':'\n'.join(lines)})

    target_owner=own(TARGET)
    target_lines=function_lines(dis,target_owner)
    report={
      'schema':'mmonochrom.spi.settings-producer1a.v1',
      'firmware_decrypted_sha256':tr.sha(fw),
      'target':{'addr':hex(TARGET),'owner':target_owner,'known_payload_contract':'R0 packet base; SPI_AppendSettings copies 37 bytes from packet+7 into a processing-list record'},
      'reverse_call_graph':chain,
      'caller_function_bodies':bodies,
      'target_function':{'owner':target_owner,'constants':referenced_constants(target_lines),'disassembly':'\n'.join(target_lines)},
      'questions':['Which dispatcher/message handler directly calls SPI_AppendSettings?','What is R0 at that callsite and how is packet+7 populated?','What command/message ID selects this handler?','Can the first u32 at packet+7 be tied to controller Standard JPEG processing settings?']
    }
    (a.outdir/'MM_SPI_SETTINGS_PRODUCER_PROBE.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_SPI_SETTINGS_PRODUCER_PROBE.txt').open('w') as f:
        f.write('M Monochrom SPI settings producer probe\n\n')
        for level in chain:
            f.write(f"===== reverse caller depth {level['depth']} =====\n")
            for c in level['calls']:
                f.write(f"site={c['site']} owner={c['owner']} target={c['target']}\n")
                for line in c['context']:f.write(line+'\n')
                f.write('\n')
        for b in bodies:
            f.write(f"\n===== function {b['owner']} =====\n")
            f.write('constants='+json.dumps(b['constants'])+'\n')
            f.write(b['disassembly']+'\n')
        f.write(f"\n===== SPI_AppendSettings {target_owner} =====\n"+'\n'.join(target_lines)+'\n')
    print(json.dumps({'target_owner':target_owner,'call_graph':[{'depth':x['depth'],'calls':[{'site':c['site'],'owner':c['owner'],'target':c['target']} for c in x['calls']]} for x in chain],'caller_bodies':[b['owner'] for b in bodies]},indent=2))
    for p in work.iterdir():p.unlink()
    work.rmdir()
if __name__=='__main__':main()
