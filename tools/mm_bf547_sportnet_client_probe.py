#!/usr/bin/env python3
"""Locate BF547-side SportNet command-0x04 / 37-byte request construction.

BF561 server evidence closes the SportNet dispatch selector for SPI_AppendSettings
as command 0x04 with table field2 0x25 (37). This probe searches the BF547
controller without importing M9 runtime values:

1. client-table candidates whose fixed-stride selector words match the BF561
   SportNet selector ordering/subsequences;
2. data neighborhoods containing u32 selector 0x04 and u32 0x25;
3. executable windows that materialize constants 0x04 and 0x25 near each other,
   with all CALL/JUMP instructions preserved for follow-up;
4. byte stores of constant 0x04 followed by 37-byte-copy style constants.

M9 is scanned only as a structural control. No firmware payload bytes are emitted.
"""
from __future__ import annotations
import argparse, hashlib, json, pathlib, re, struct, subprocess, sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402
from recover_leica_m9_mm_shared_key import M9_DEC_SHA, MM_DEC_SHA  # noqa: E402

RAM=0x20000
SELECTORS=[0x00,0x02,0x03,0x0a,0x05,0x04,0x07,0x08,0x01,0x0b,0x0c,0x06,0xff]
ADDR_RE=re.compile(r'^\s*([0-9a-fA-F]+):')
IMM_RE=re.compile(r'\b([RP][0-7]|P[0-5])(?:\.[HL])?\s*=\s*(?:0x)?(-?[0-9a-fA-F]+)\b',re.I)
TRANSFER_RE=re.compile(r'\b(?:CALL|JUMP(?:\.S|\.L)?)\b',re.I)

def sha(b):return hashlib.sha256(b).hexdigest()
def component(root):
    hits=[]
    def rec(d,depth=0):
        if depth>4 or d[:4]!=b'PWAD':return
        for x in pwad.parse_pwad(d):
            if x.name.upper()=='BF547':hits.append(x.data)
            if x.data[:4]==b'PWAD':rec(x.data,depth+1)
    rec(root)
    if len(hits)!=1:raise RuntimeError(f'BF547 hits={len(hits)}')
    return hits[0]
def disasm(objdump,b,work,stem):
    p=work/f'{stem}.bin';p.write_bytes(b)
    r=subprocess.run([str(objdump),'-D','-b','binary','-m','bfin',f'--adjust-vma={RAM:#x}',str(p)],capture_output=True,text=True,check=True);p.unlink();return r.stdout.splitlines()
def ao(line):
    m=ADDR_RE.match(line);return int(m.group(1),16) if m else 0

def stride_candidates(bf):
    out=[]
    # Search aligned u32 records with modest strides. Require >=5 selectors in the
    # exact BF561 ordering to suppress chance matches, and emit any complete run.
    for stride in range(8,33,4):
        span=(len(SELECTORS)-1)*stride+4
        for off in range(0,max(0,len(bf)-span+1),4):
            vals=[struct.unpack_from('<I',bf,off+i*stride)[0] for i in range(len(SELECTORS))]
            matches=[i for i,(a,b) in enumerate(zip(vals,SELECTORS)) if a==b]
            # longest contiguous matching selector run
            best=[];cur=[]
            for i in range(len(SELECTORS)):
                if vals[i]==SELECTORS[i]:cur.append(i)
                else:
                    if len(cur)>len(best):best=cur
                    cur=[]
            if len(cur)>len(best):best=cur
            if len(best)>=5:
                rows=[]
                for i in best:
                    base=off+i*stride
                    words=[struct.unpack_from('<I',bf,base+j)[0] for j in range(0,stride,4)]
                    rows.append({'selector_index':i,'addr':hex(RAM+base),'words_hex':[hex(x) for x in words]})
                out.append({'base':hex(RAM+off),'stride':stride,'matched_indices':best,'rows':rows})
    # dedupe overlapping same run
    uniq=[];seen=set()
    for x in out:
        k=(x['base'],x['stride'],tuple(x['matched_indices']))
        if k not in seen:seen.add(k);uniq.append(x)
    return uniq[:100]

def data_04_25(bf):
    out=[]; needle4=struct.pack('<I',4); positions=[];p=0
    while True:
        p=bf.find(needle4,p)
        if p<0:break
        if p%4==0:positions.append(p)
        p+=1
    for p in positions:
        lo=max(0,p-96);hi=min(len(bf)-4,p+100);rows=[]
        for q in range((lo+3)&~3,hi+1,4):
            v=struct.unpack_from('<I',bf,q)[0]
            if v in (4,0x25,0x2c,0x27) or RAM<=v<RAM+len(bf):
                rows.append({'addr':hex(RAM+q),'relative_words':(q-p)//4,'value':hex(v),'is_code_range':RAM<=v<RAM+len(bf)})
        if any(int(x['value'],16)==0x25 for x in rows):
            out.append({'selector4_addr':hex(RAM+p),'nearby_interesting_u32':rows})
    return out[:250]

def imm_value(line,val):
    # Robustly detect Blackfin constants in the objdump comment-free instruction.
    s=line.split('/*',1)[0].lower()
    toks=[f'0x{val:x}',f'= {val} ',f'= 0x{val:x} ']
    return any(t in s for t in toks)
def code_04_25(lines):
    i4=[i for i,l in enumerate(lines) if imm_value(l,4)]
    i25=[i for i,l in enumerate(lines) if imm_value(l,0x25)]
    out=[]
    for i in i4:
        near=[j for j in i25 if abs(j-i)<=90]
        for j in near:
            lo=max(0,min(i,j)-35);hi=min(len(lines),max(i,j)+55);ctx=lines[lo:hi]
            transfers=[x for x in ctx if TRANSFER_RE.search(x)]
            out.append({'const4_site':hex(ao(lines[i])),'const25_site':hex(ao(lines[j])),'line_distance':j-i,'transfers':transfers,'context':ctx})
    # sort tightest first and dedupe site pair
    out.sort(key=lambda x:abs(x['line_distance']));seen=set();ans=[]
    for x in out:
        k=(x['const4_site'],x['const25_site'])
        if k not in seen:seen.add(k);ans.append(x)
    return ans[:160]

def store4_windows(lines):
    out=[]
    # Detect direct constant-4 setup followed soon by a byte store. This is a
    # heuristic only; output remains candidate evidence.
    for i,l in enumerate(lines):
        if not imm_value(l,4):continue
        ctx=lines[max(0,i-10):min(len(lines),i+35)]
        stores=[x for x in ctx if re.search(r'\bB\[[^\]]+\]\s*=\s*R[0-7]\b',x,re.I)]
        has25=any(imm_value(x,0x25) for x in ctx)
        if stores and has25:
            out.append({'site':hex(ao(l)),'byte_stores':stores,'context':ctx})
    return out[:160]

def analyse(label,fw,objdump,work):
    bf=component(fw);lines=disasm(objdump,bf,work,label)
    return {'bf547_sha256':sha(bf),'bf547_size':len(bf),'selector_stride_candidates':stride_candidates(bf),'data_selector4_with_0x25_nearby':data_04_25(bf),'code_const4_const25_windows':code_04_25(lines),'const4_byte_store_windows_with_0x25':store4_windows(lines)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('m9_decrypted',type=pathlib.Path);ap.add_argument('mm_decrypted',type=pathlib.Path);ap.add_argument('--objdump',type=pathlib.Path,required=True);ap.add_argument('--outdir',type=pathlib.Path,required=True);a=ap.parse_args()
    m9=a.m9_decrypted.read_bytes();mm=a.mm_decrypted.read_bytes()
    if sha(m9)!=M9_DEC_SHA:raise SystemExit('M9 SHA mismatch')
    if sha(mm)!=MM_DEC_SHA:raise SystemExit('MM SHA mismatch')
    a.outdir.mkdir(parents=True,exist_ok=True);work=a.outdir/'_work';work.mkdir(exist_ok=True)
    mr=analyse('m9',m9,a.objdump,work);xr=analyse('mm',mm,a.objdump,work)
    for p in work.iterdir():p.unlink()
    work.rmdir()
    report={'schema':'mmonochrom.bf547.sportnet-client-probe1a.v1','server_truth':{'append_settings_selector':4,'payload_bytes':37,'bf561_dispatch_record_stride':12},'m9':mr,'monochrom':xr,'classification':'candidate_search_not_runtime_semantics','guardrails':['0x04/0x25 proximity alone is not producer proof.','A producer is promoted only after packet pointer flow to BF547 transport is closed.','M9 is structural control only.'],'next_questions':['Does BF547 contain a client-side table homologous to g_pSportNetFunctions?','Which tight 0x04/0x25 code window constructs or sends a 44-byte request?','Can the request payload source be followed to the process-mask u32 and Noise/Sharp settings?']}
    (a.outdir/'MM_BF547_SPORTNET_CLIENT_PROBE.json').write_text(json.dumps(report,indent=2)+'\n')
    with (a.outdir/'MM_BF547_SPORTNET_CLIENT_PROBE.txt').open('w') as f:
        for lab,r in (('M9',mr),('MM',xr)):
            f.write(f'===== {lab} =====\n')
            f.write('STRIDE CANDIDATES\n'+json.dumps(r['selector_stride_candidates'],indent=2)+'\n')
            f.write('DATA 04/25\n'+json.dumps(r['data_selector4_with_0x25_nearby'],indent=2)+'\n')
            f.write('CODE 04/25\n'+json.dumps(r['code_const4_const25_windows'],indent=2)+'\n')
            f.write('STORE WINDOWS\n'+json.dumps(r['const4_byte_store_windows_with_0x25'],indent=2)+'\n')
    print(json.dumps({lab:{'stride':len(r['selector_stride_candidates']),'data04_25':len(r['data_selector4_with_0x25_nearby']),'code04_25':len(r['code_const4_const25_windows']),'store_windows':len(r['const4_byte_store_windows_with_0x25'])} for lab,r in [('m9',mr),('mm',xr)]},indent=2))
if __name__=='__main__':main()
