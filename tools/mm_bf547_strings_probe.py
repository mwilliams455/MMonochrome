#!/usr/bin/env python3
"""Search printable BF547 strings for network/settings anchors. Evidence-only."""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad
from recover_leica_m9_mm_shared_key import MM_DEC_SHA

def sha(b): return hashlib.sha256(b).hexdigest()
def bf547(root):
    hits=[]
    def rec(d,depth=0):
        if depth>4 or d[:4]!=b'PWAD': return
        for x in pwad.parse_pwad(d):
            if x.name.upper()=='BF547': hits.append(x.data)
            if x.data[:4]==b'PWAD': rec(x.data,depth+1)
    rec(root)
    if len(hits)!=1: raise RuntimeError(f'BF547 hits={len(hits)}')
    return hits[0]
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('mm_decrypted',type=pathlib.Path); ap.add_argument('--out',type=pathlib.Path,required=True); a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if sha(fw)!=MM_DEC_SHA: raise SystemExit('MM SHA mismatch')
    b=bf547(fw); rows=[]
    for m in re.finditer(rb'[\x20-\x7e]{4,}',b):
        s=m.group().decode('ascii','replace')
        if re.search(r'(sport|net|spi|setting|process|sharp|noise|interpol|slave|master|transfer|append|image|jolos)',s,re.I):
            rows.append({'addr':hex(0x20000+m.start()),'text':s[:300]})
    rep={'schema':'mmonochrom.bf547.strings1a.v1','bf547_sha256':sha(b),'matches':rows}
    a.out.parent.mkdir(parents=True,exist_ok=True); a.out.write_text(json.dumps(rep,indent=2)+'\n')
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
