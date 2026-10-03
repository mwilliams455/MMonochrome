#!/usr/bin/env python3
"""Generate exact five-level Leica M Monochrom 1.022 sharpness tables.

Firmware bytes are consumed only during CI. The repository stores no Leica LUT
payload. Output:
- C++ premodified tables for the full-resolution SOURCE1D still renderer.
- A compact little-endian int16 asset for the GL preview.
- Java metadata containing menu/ISO/code mapping and asset identity.
"""
from __future__ import annotations
import argparse,hashlib,json,pathlib,struct,sys
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent))
import pwad

MM_DEC_SHA="c9e14ee475408802c83774f37b19c85c57663d9840e8e4c2cfe80e14dec9a7ae"
PROCESS_SHA="dea370ecbf043da03a4af8a7d126d930caf8364f2c806e96a15b2dcb78fcab96"
BANK_SHA="282a6e7eb0603203d5ddb36f32862e0340a9cc2d24c35b4c0af2b1bd79c06d10"
BANK_OFF=0x58C
MATRIX_OFF=0x410
SELECTORS=5
ISO_COUNT=16
COUNT=2050
ROW_BYTES=4100
ISOS=[320,400,500,640,800,1000,1250,1600,2000,2500,3200,4000,5000,6400,8000,10000]
LABELS=["Off","Low","Standard","Medium high","High"]
EXPECTED_CODES=[
 [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
 [4,4,4,4,2,2,2,2,2,2,2,2,2,2,1,1],
 [8,8,8,8,4,4,4,4,4,4,4,4,3,3,2,2],
 [11,11,11,11,8,8,8,8,8,8,8,7,6,5,4,3],
 [12,12,12,12,11,11,11,11,11,11,11,10,9,8,7,6],
]
MOD={
 1:(1,2),2:(1,1),3:(3,2),4:(1,0),5:(5,2),6:(3,1),
 7:(7,2),8:(2,0),9:(5,1),10:(3,0),11:(13,2),12:(5,0),
}
def sha(b): return hashlib.sha256(b).hexdigest()
def lump(root,path):
    d=root
    for name in path:
        hit=next((x for x in pwad.parse_pwad(d) if x.name.upper()==name.upper()),None)
        if hit is None: raise KeyError("/".join(path))
        d=hit.data
    return d
def scale(row,code):
    if code==0: return [0]*len(row)
    mul,shift=MOD[code]
    out=[]
    for x in row:
        # Python >> on negative integers is arithmetic, matching Blackfin >>>.
        y=(x*mul)>>shift
        if y<-2048:y=-2048
        elif y>2048:y=2048
        out.append(y)
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("mm_decrypted",type=pathlib.Path)
    ap.add_argument("--cpp-out",type=pathlib.Path,required=True)
    ap.add_argument("--asset-out",type=pathlib.Path,required=True)
    ap.add_argument("--java-out",type=pathlib.Path,required=True)
    ap.add_argument("--report-out",type=pathlib.Path,required=True)
    a=ap.parse_args()

    fw=a.mm_decrypted.read_bytes()
    if sha(fw)!=MM_DEC_SHA: raise SystemExit("M Monochrom decrypted SHA mismatch")
    luts=lump(fw,["LUTS","PROCESS","LUTS"])
    if sha(luts)!=PROCESS_SHA: raise SystemExit("PROCESS/LUTS SHA mismatch")
    bank=luts[BANK_OFF:BANK_OFF+ISO_COUNT*ROW_BYTES]
    if len(bank)!=ISO_COUNT*ROW_BYTES or sha(bank)!=BANK_SHA:
        raise SystemExit("sharpness source bank identity mismatch")

    codes=[]
    for selector in range(SELECTORS):
        off=MATRIX_OFF+selector*19*4
        row=list(struct.unpack_from("<"+"I"*19,luts,off))
        codes.append(row[:16])
    if codes!=EXPECTED_CODES:
        raise SystemExit("sharpness selector x ISO matrix mismatch")

    raw_rows=[
        list(struct.unpack_from("<"+"h"*COUNT,bank,i*ROW_BYTES))
        for i in range(ISO_COUNT)
    ]
    tables=[]
    for selector in range(SELECTORS):
        tables.append([scale(raw_rows[i],codes[selector][i]) for i in range(ISO_COUNT)])

    # Asset layout: selector-major, ISO-major, 2050 signed little-endian int16.
    asset=bytearray()
    for selector in range(SELECTORS):
        for iso in range(ISO_COUNT):
            asset.extend(struct.pack("<"+"h"*COUNT,*tables[selector][iso]))
    asset=bytes(asset)
    expected_size=SELECTORS*ISO_COUNT*COUNT*2
    if len(asset)!=expected_size: raise SystemExit("sharpness asset size mismatch")
    asset_sha=sha(asset)
    a.asset_out.parent.mkdir(parents=True,exist_ok=True)
    a.asset_out.write_bytes(asset)

    a.cpp_out.parent.mkdir(parents=True,exist_ok=True)
    lines=[
      "// GENERATED from hash-verified Leica M Monochrom 1.022; do not edit.",
      "// Source bank SHA256: "+BANK_SHA,
      "// Preview/still premodified asset SHA256: "+asset_sha,
      "#pragma once",
      "#include <cstdint>",
      "static constexpr int MM_MONO_SHARP_SELECTOR_COUNT = 5;",
      "static constexpr int MM_MONO_SHARP_ISO_COUNT = 16;",
      "static constexpr int MM_MONO_SHARP_LUT_COUNT = 2050;",
      "static constexpr int MM_MONO_SHARP_BORDER = 2;",
      "static constexpr int MM_MONO_SHARP_ISOS[16] = {"+",".join(map(str,ISOS))+"};",
      "static constexpr int MM_MONO_SHARP_CODES[5][16] = {",
    ]
    for row in codes: lines.append("  {"+",".join(map(str,row))+"},")
    lines.append("};")
    lines.append("static constexpr int16_t MM_MONO_SHARP_LUT[5][16][2050] = {")
    for selector in range(SELECTORS):
        lines.append(" { // "+LABELS[selector])
        for iso,row in enumerate(tables[selector]):
            lines.append("  { // ISO %d code %d"%(ISOS[iso],codes[selector][iso]))
            for j in range(0,COUNT,32):
                lines.append("    "+",".join(map(str,row[j:j+32]))+",")
            lines.append("  },")
        lines.append(" },")
    lines.append("};")
    a.cpp_out.write_text("\n".join(lines)+"\n")

    a.java_out.parent.mkdir(parents=True,exist_ok=True)
    label_lits=",".join('"'+x+'"' for x in LABELS)
    iso_lits=",".join(map(str,ISOS))
    code_rows=",".join("new int[]{"+",".join(map(str,row))+"}" for row in codes)
    a.java_out.write_text(f'''package com.particlesdevs.photoncamera.m9.render;

public final class MonoSharpness1C {{
    public static final int DEFAULT=2;
    public static final int SELECTOR_COUNT=5;
    public static final int ISO_COUNT=16;
    public static final int LUT_COUNT=2050;
    public static final int BORDER=2;
    public static final String ASSET="mono/mono_sharpness5.bin";
    public static final String SOURCE_BANK_SHA256="{BANK_SHA}";
    public static final String ASSET_SHA256="{asset_sha}";
    public static final String[] LABELS=new String[]{{{label_lits}}};
    public static final int[] ISOS=new int[]{{{iso_lits}}};
    public static final int[][] CODES=new int[][]{{{code_rows}}};
    private MonoSharpness1C() {{}}
    public static int clampSelector(int v) {{ return v<0?0:(v>4?4:v); }}
    public static int nearestIsoSlot(int iso) {{
        if(iso<=ISOS[0]) return 0;
        if(iso>=ISOS[ISO_COUNT-1]) return ISO_COUNT-1;
        double target=Math.log(iso)/Math.log(2.0);
        int best=0; double bestD=Math.abs(target-Math.log(ISOS[0])/Math.log(2.0));
        for(int i=1;i<ISO_COUNT;i++) {{
            double d=Math.abs(target-Math.log(ISOS[i])/Math.log(2.0));
            if(d<bestD) {{ bestD=d; best=i; }}
        }}
        return best;
    }}
    public static int code(int selector,int iso) {{
        int s=clampSelector(selector), slot=nearestIsoSlot(Math.max(1,iso));
        return CODES[s][slot];
    }}
}}
''')

    report={
      "schema":"mmonochrome.sharpness1c.tables.v1",
      "firmware":"Leica M Monochrom 1.022",
      "firmwareDecryptedSha256":MM_DEC_SHA,
      "processLutsSha256":PROCESS_SHA,
      "sourceBankSha256":BANK_SHA,
      "assetSha256":asset_sha,
      "assetBytes":len(asset),
      "labels":LABELS,
      "isos":ISOS,
      "codes":codes,
      "border":2,
      "kernel":"two_stage_integer_[1,2,1]/4_then_centered_detail_LUT",
      "firmwareBytesCommitted":False,
    }
    a.report_out.parent.mkdir(parents=True,exist_ok=True)
    a.report_out.write_text(json.dumps(report,indent=2)+"\n")
    print(json.dumps(report,indent=2))

if __name__=="__main__": main()
