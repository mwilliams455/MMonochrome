#!/usr/bin/env python3
"""Emit a name/size/hash inventory of nested PWAD components in decrypted MM firmware."""
from __future__ import annotations
import argparse, hashlib, json, pathlib, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad
from recover_leica_m9_mm_shared_key import MM_DEC_SHA

def sha(b): return hashlib.sha256(b).hexdigest()
def walk(data,path='root',depth=0):
    out=[]
    if depth>8 or data[:4]!=b'PWAD': return out
    try: items=pwad.parse_pwad(data)
    except Exception: return out
    for i,x in enumerate(items):
        p=f'{path}/{x.name}'
        out.append({'path':p,'name':x.name,'size':len(x.data),'sha256':sha(x.data),'is_pwad':x.data[:4]==b'PWAD'})
        if x.data[:4]==b'PWAD': out.extend(walk(x.data,p,depth+1))
    return out

def main():
    ap=argparse.ArgumentParser();ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--out',type=pathlib.Path,required=True);a=ap.parse_args()
    fw=a.mm_decrypted.read_bytes()
    if sha(fw)!=MM_DEC_SHA: raise SystemExit(f'MM decrypted SHA mismatch {sha(fw)}')
    rows=walk(fw)
    rep={'schema':'mmonochrom.component-inventory1a.v1','firmware_decrypted_sha256':sha(fw),'components':rows}
    a.out.parent.mkdir(parents=True,exist_ok=True);a.out.write_text(json.dumps(rep,indent=2)+'\n')
    print(json.dumps(rows,indent=2))
if __name__=='__main__':main()
