#!/usr/bin/env python3
"""Discover the original M Monochrom BF547 process-mask source structurally.

The earlier process-mask probe deliberately tested the independently known M9
runtime address 0x000f2c38 in both BF547 images.  That test rejected direct
address transfer: the Monochrom bytes and serializer neighborhood differ.

This probe does not assume a Monochrom address.  It locates serializer-like code
from the distinctive settings-record writes (+0x133/+0x134 and nearby fields),
walks backwards for absolute-address materializations feeding four-byte copies,
and validates the same method against the M9 control where 0x000f2c38 is known.
Only derived addresses, integer words, hashes and disassembly text are emitted.
"""
from __future__ import annotations

import argparse, hashlib, json, pathlib, re, subprocess, sys
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import M9_DEC_SHA, MM_DEC_SHA  # noqa: E402

RAM = 0x20000
KNOWN_M9_MASK = 0xF2C38
WRITE133 = re.compile(r"B\[P5 \+ 0x133\]\s*=", re.I)
WRITE134 = re.compile(r"B\[P5 \+ 0x134\]\s*=", re.I)
ADDR_LINE = re.compile(r"^\s*([0-9a-fA-F]+):")
IMM_HI = re.compile(r"\b([RP][0-7])\.H\s*=\s*0x([0-9a-fA-F]+)\b", re.I)
IMM_LO = re.compile(r"\b([RP][0-7])\.L\s*=\s*0x([0-9a-fA-F]+)\b", re.I)
CALL = re.compile(r"\bCALL\s+0x0x([0-9a-fA-F]+)|\bCALL\s+0x([0-9a-fA-F]+)", re.I)


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def find_component(root: bytes, name: str) -> bytes:
    want=name.upper(); hits=[]
    def rec(data: bytes, depth: int=0):
        if depth>4 or data[:4]!=b"PWAD": return
        for x in pwad.parse_pwad(data):
            if x.name.upper()==want: hits.append(x.data)
            if x.data[:4]==b"PWAD": rec(x.data,depth+1)
    rec(root)
    if len(hits)!=1: raise RuntimeError(f"{name} hits={len(hits)}")
    return hits[0]


def disasm(objdump: pathlib.Path, blob: bytes, vma: int, work: pathlib.Path, stem: str) -> list[str]:
    p=work/f"{stem}.bin"; p.write_bytes(blob)
    r=subprocess.run([str(objdump),"-D","-b","binary","-m","bfin",f"--adjust-vma={vma:#x}",str(p)],capture_output=True,text=True,check=True)
    p.unlink()
    return r.stdout.splitlines()


def addr_of(line: str) -> int | None:
    m=ADDR_LINE.match(line)
    return int(m.group(1),16) if m else None


def materialized_addresses(lines: list[str], lo: int, hi: int, bf_size: int) -> list[dict]:
    """Pair same-register .H/.L immediates in either order within 14 instructions."""
    out=[]
    for i in range(lo, hi):
        mh=IMM_HI.search(lines[i]); ml=IMM_LO.search(lines[i])
        if not (mh or ml): continue
        reg=(mh or ml).group(1).upper()
        for j in range(i+1,min(hi,i+15)):
            mh2=IMM_HI.search(lines[j]); ml2=IMM_LO.search(lines[j])
            pairs=[]
            if mh and ml2 and ml2.group(1).upper()==reg:
                pairs.append((int(mh.group(2),16),int(ml2.group(2),16)))
            if ml and mh2 and mh2.group(1).upper()==reg:
                pairs.append((int(mh2.group(2),16),int(ml.group(2),16)))
            for hv,lv in pairs:
                v=((hv&0xffff)<<16)|(lv&0xffff)
                if RAM <= v < RAM+bf_size:
                    out.append({"reg":reg,"value":hex(v),"first_line_index":i,"second_line_index":j,
                                "first_addr":hex(addr_of(lines[i]) or 0),"second_addr":hex(addr_of(lines[j]) or 0)})
    # stable dedupe
    seen=set(); ans=[]
    for x in out:
        k=(x['reg'],x['value'],x['first_addr'],x['second_addr'])
        if k not in seen: seen.add(k); ans.append(x)
    return ans


def summarize(label: str, root: bytes, objdump: pathlib.Path, work: pathlib.Path) -> dict:
    bf=find_component(root,"BF547")
    lines=disasm(objdump,bf,RAM,work,label)
    anchors=[]
    for i,line in enumerate(lines):
        if not WRITE133.search(line): continue
        # Require +0x134 in a tight local window to avoid unrelated object writes.
        if not any(WRITE134.search(lines[j]) for j in range(i,min(len(lines),i+16))):
            continue
        lo=max(0,i-80); hi=min(len(lines),i+120)
        mats=materialized_addresses(lines,lo,i+8,len(bf))
        enriched=[]
        for m in mats:
            v=int(m['value'],16); off=v-RAM
            raw=bf[off:off+32]
            if len(raw)<4: continue
            word=int.from_bytes(raw[:4],'little')
            dist=i-m['second_line_index']
            enriched.append({**m,"distance_in_disassembly_lines_to_write133":dist,
                "first_u32":hex(word),"set_bits":[b for b in range(32) if word&(1<<b)],
                "window32_sha256":sha(raw) if len(raw)==32 else None})
        anchors.append({
            "write133_addr":hex(addr_of(line) or 0),
            "context":lines[lo:hi],
            "materialized_bf547_addresses_before_anchor":enriched,
        })
    return {"bf547_sha256":sha(bf),"bf547_size":len(bf),"anchors":anchors}


def rank_candidates(r: dict) -> list[dict]:
    c=[]
    for a in r['anchors']:
        for x in a['materialized_bf547_addresses_before_anchor']:
            # Four-byte source is expected close to the serializer prologue. Prefer
            # addresses materialized nearest before +0x133 and avoid code-local
            # addresses by no hard classification beyond distance.
            c.append({"write133_addr":a['write133_addr'],**x})
    c.sort(key=lambda x:(abs(x['distance_in_disassembly_lines_to_write133']),int(x['value'],16)))
    return c[:40]


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('m9_decrypted',type=pathlib.Path)
    ap.add_argument('mm_decrypted',type=pathlib.Path)
    ap.add_argument('--objdump',type=pathlib.Path,required=True)
    ap.add_argument('--outdir',type=pathlib.Path,required=True)
    a=ap.parse_args(); a.outdir.mkdir(parents=True,exist_ok=True)
    m9=a.m9_decrypted.read_bytes(); mm=a.mm_decrypted.read_bytes()
    if sha(m9)!=M9_DEC_SHA: raise SystemExit(f"M9 decrypted SHA mismatch {sha(m9)}")
    if sha(mm)!=MM_DEC_SHA: raise SystemExit(f"MM decrypted SHA mismatch {sha(mm)}")
    work=a.outdir/'_work'; work.mkdir(exist_ok=True)
    m9r=summarize('m9',m9,a.objdump,work); mmr=summarize('mm',mm,a.objdump,work)
    for p in work.iterdir(): p.unlink()
    work.rmdir()
    m9rank=rank_candidates(m9r); mmrank=rank_candidates(mmr)
    known=[x for x in m9rank if int(x['value'],16)==KNOWN_M9_MASK]
    report={
      'schema':'mmonochrom.bf547.mask-source-discovery1a.v1',
      'classification':'structural_serializer_anchor_and_backward_absolute_source_discovery',
      'm9':m9r,'monochrom':mmr,
      'm9_ranked_candidates':m9rank,'monochrom_ranked_candidates':mmrank,
      'm9_known_mask_recovered_in_ranked_candidates':bool(known),
      'm9_known_mask':hex(KNOWN_M9_MASK),
      'guardrails':[
        'A Monochrom candidate is not promoted solely because it is nearest to the serializer anchor.',
        'The method is considered structurally credible only if it independently re-finds the known M9 0xF2C38 source.',
        'Candidate first_u32 values are source-memory contents, not automatically process masks until the copy call and destination field are closed.',
      ],
      'next_questions':[
        'Which Monochrom candidate is passed as the source to the 4-byte copy whose destination is processing-record +0x12c?',
        'Does that copied u32 set Sharp bit 7 and Noise bit 6 in the normal still-JPEG path?',
        'Are there mode-specific writers/overrides after the template copy and before the 37-byte SPI payload is sent?',
      ]
    }
    (a.outdir/'MM_BF547_MASK_SOURCE_DISCOVERY.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF547_MASK_SOURCE_DISCOVERY.txt').open('w') as f:
        f.write('M Monochrom BF547 process-mask source discovery\n\n')
        f.write(f"M9 known source recovered={bool(known)} known={KNOWN_M9_MASK:#x}\n")
        f.write('\nM9 ranked candidates:\n'+json.dumps(m9rank,indent=2)+'\n')
        f.write('\nMonochrom ranked candidates:\n'+json.dumps(mmrank,indent=2)+'\n')
        for label,r in (('M9',m9r),('MM',mmr)):
            for a0 in r['anchors']:
                f.write(f"\n===== {label} serializer anchor {a0['write133_addr']} =====\n")
                for line in a0['context']: f.write(line+'\n')
    print(json.dumps({
      'm9_anchor_count':len(m9r['anchors']),'mm_anchor_count':len(mmr['anchors']),
      'm9_known_mask_recovered':bool(known),
      'm9_top_candidates':m9rank[:8], 'mm_top_candidates':mmrank[:12]
    },indent=2))

if __name__=='__main__': main()
