#!/usr/bin/env python3
"""Recover the shared Leica M9/M Monochrom 1021-byte XOR stream.

Evidence/build helper. No firmware or key bytes are embedded or retained.
"""
from __future__ import annotations
import argparse, hashlib, json, math
from pathlib import Path
PERIOD=1021
M9_BODY_OFFSET=0x00451050
MM_BODY_OFFSET=0x00119350
BODY_SIZE=143_418
M9_RAW_SHA="c3d30d7124abe6a3674cf2095719c178454b8773b1454cb70cf54ae468024da4"
MM_RAW_SHA="53330385edfbfb9beeffa06645bffa2789e27dda614869107698919464f80ad8"
KEY_SHA="595c49ebabdaafcde7cc6cbd6aa7a37092d7c2ad4ca47d0d8bc57a04a5bed3a1"
M9_DEC_SHA="4f962bb7799ad9a6745ab36c2a3ba59757bfcbd205f50472ddf1b904a5756d20"
MM_DEC_SHA="c9e14ee475408802c83774f37b19c85c57663d9840e8e4c2cfe80e14dec9a7ae"
def sha(data): return hashlib.sha256(data).hexdigest()
def decrypt(data,key): return bytes(v^key[i%len(key)] for i,v in enumerate(data))
def build_edges(m9,mm):
    delta=(MM_BODY_OFFSET-M9_BODY_OFFSET)%PERIOD
    if math.gcd(delta,PERIOD)!=1: raise RuntimeError('BODY offset delta does not span key period')
    edge=[None]*PERIOD
    for i in range(PERIOD):
        a=(M9_BODY_OFFSET+i)%PERIOD
        edge[a]=m9[M9_BODY_OFFSET+i]^mm[MM_BODY_OFFSET+i]
    if any(v is None for v in edge): raise RuntimeError('incomplete key equation graph')
    return [int(v) for v in edge],delta
def key_from_seed(edge,delta,seed):
    key=[None]*PERIOD; key[0]=seed; cur=0
    for _ in range(PERIOD-1):
        nxt=(cur+delta)%PERIOD
        if key[nxt] is not None: raise RuntimeError('key cycle closed early')
        key[nxt]=int(key[cur])^edge[cur]; cur=nxt
    if (cur+delta)%PERIOD!=0 or (int(key[cur])^edge[cur])!=seed: raise RuntimeError('inconsistent equations')
    return bytes(int(v) for v in key)
def recover(m9,mm):
    edge,delta=build_edges(m9,mm); candidates=[]
    for seed in range(256):
        key=key_from_seed(edge,delta,seed)
        if bytes(m9[i]^key[i%PERIOD] for i in range(4))==b'PWAD': candidates.append((seed,key))
    if len(candidates)!=1: raise RuntimeError(f'expected one PWAD-compatible key, got {len(candidates)}')
    seed,key=candidates[0]; return key,delta,seed
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('m9_upd',type=Path); ap.add_argument('mm_upm',type=Path); ap.add_argument('--m9-out',type=Path); ap.add_argument('--mm-out',type=Path); ap.add_argument('--meta-out',type=Path); a=ap.parse_args()
    m9=a.m9_upd.read_bytes(); mm=a.mm_upm.read_bytes()
    if sha(m9)!=M9_RAW_SHA: raise SystemExit(f'M9 raw SHA mismatch: {sha(m9)}')
    if sha(mm)!=MM_RAW_SHA: raise SystemExit(f'MM raw SHA mismatch: {sha(mm)}')
    key,delta,seed=recover(m9,mm)
    if sha(key)!=KEY_SHA: raise SystemExit(f'key SHA mismatch: {sha(key)}')
    m9d=decrypt(m9,key); mmd=decrypt(mm,key)
    if sha(m9d)!=M9_DEC_SHA or sha(mmd)!=MM_DEC_SHA: raise SystemExit('decrypted SHA mismatch')
    if m9d[:4]!=b'PWAD' or mmd[:4]!=b'PWAD': raise SystemExit('decryption did not yield PWAD')
    if m9d[M9_BODY_OFFSET:M9_BODY_OFFSET+BODY_SIZE]!=mmd[MM_BODY_OFFSET:MM_BODY_OFFSET+BODY_SIZE]: raise SystemExit('shared BODY verification failed')
    meta={'schema':'leica.m9-mm.shared-key-recovery.v1','period':PERIOD,'offset_delta_mod_period':delta,'gcd_delta_period':math.gcd(delta,PERIOD),'pw_ad_seed':seed,'m9_raw_sha256':sha(m9),'mm_raw_sha256':sha(mm),'key_sha256':sha(key),'m9_decrypted_sha256':sha(m9d),'mm_decrypted_sha256':sha(mmd),'shared_body_exact':True}
    print(json.dumps(meta,indent=2))
    if a.m9_out:a.m9_out.write_bytes(m9d)
    if a.mm_out:a.mm_out.write_bytes(mmd)
    if a.meta_out:a.meta_out.write_text(json.dumps(meta,indent=2)+'\n')
if __name__=='__main__':main()
