#!/usr/bin/env python3
"""Follow the canonical M Monochrom BF547 Sharpening controller descriptor.

Evidence-only. Finds the literal label, resolves descriptor xrefs under the
M-generation +0x20000 static-RAM mapping, follows +0x14 options pointer and
decodes consecutive 20-byte Leica menu records. No firmware bytes are emitted.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import pwad  # noqa: E402

MM_DEC_SHA = "c9e14ee475408802c83774f37b19c85c57663d9840e8e4c2cfe80e14dec9a7ae"
RAM = 0x20000
DESC_SIZE = 0x20
OPTIONS_PTR_OFF = 0x14
MENU_STRIDE = 0x14


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def find_all(b: bytes, needle: bytes) -> list[int]:
    out=[]; p=0
    while True:
        p=b.find(needle,p)
        if p<0:return out
        out.append(p); p+=1


def cstr(b: bytes, off: int, maxlen: int=128):
    if not 0 <= off < len(b): return None
    e=b.find(b"\0",off,min(len(b),off+maxlen))
    if e<=off:return None
    raw=b[off:e]
    if any(x<0x20 or x>0x7e for x in raw):return None
    return raw.decode("ascii")


def ptr_text(b: bytes, ptr: int):
    if not RAM <= ptr < RAM+len(b):return None
    return cstr(b,ptr-RAM)


def xrefs(b: bytes, text: str):
    string_offsets=find_all(b,text.encode()+b"\0") or find_all(b,text.encode())
    out=[]
    for so in string_offsets:
        pat=struct.pack("<I",so+RAM)
        for xo in find_all(b,pat):
            out.append((so,xo))
    return sorted(set(out))


def descriptor(b: bytes, off: int):
    if off<0 or off+DESC_SIZE>len(b):return None
    vals=struct.unpack_from("<8I",b,off)
    return {
        "off":hex(off),"addr":hex(off+RAM),
        "label_ptr":hex(vals[0]),"label":ptr_text(b,vals[0]),
        "control_id":hex(vals[1]),"word_08":hex(vals[2]),"type":vals[3],
        "word_10":hex(vals[4]),"options_ptr":hex(vals[5]),
        "word_18":hex(vals[6]),"word_1c":hex(vals[7]),
    }


def menu(b: bytes, ptr: int, max_records: int=16):
    off=ptr-RAM; rows=[]
    for i in range(max_records):
        ro=off+i*MENU_STRIDE
        if ro<0 or ro+MENU_STRIDE>len(b):break
        vals=struct.unpack_from("<5I",b,ro)
        label=ptr_text(b,vals[0])
        if label is None:break
        rows.append({"index":i,"record_off":hex(ro),"record_addr":hex(ro+RAM),
                     "label_ptr":hex(vals[0]),"label":label,"enum":vals[1],
                     "word_08":hex(vals[2]),"word_0c":hex(vals[3]),"word_10":hex(vals[4])})
    return rows


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("mm_decrypted",type=pathlib.Path)
    ap.add_argument("--outdir",type=pathlib.Path,required=True)
    a=ap.parse_args()
    root=a.mm_decrypted.read_bytes()
    if sha(root)!=MM_DEC_SHA:raise SystemExit(f"decrypted firmware SHA mismatch: {sha(root)}")
    outer=pwad.parse_pwad(root)
    hits=[x for x in outer if x.name.upper()=="BF547"]
    if not hits:
        # recurse one level if the component is nested
        for x in outer:
            if x.data[:4]==b"PWAD":
                hits.extend(y for y in pwad.parse_pwad(x.data) if y.name.upper()=="BF547")
    if len(hits)!=1:raise SystemExit(f"BF547 hits={len(hits)}")
    b=hits[0].data

    controls={}
    for name in ("Sharpening","Contrast","Color saturation","Noise"):
        rows=[]
        for so,xo in xrefs(b,name):
            d=descriptor(b,xo)
            if d is None:continue
            d["string_off"]=hex(so)
            op=int(d["options_ptr"],16)
            d["menu_records"]=menu(b,op) if RAM<=op<RAM+len(b) else []
            rows.append(d)
        controls[name]=rows

    sharp=[x for x in controls["Sharpening"] if x.get("label")=="Sharpening"]
    if len(sharp)!=1:
        raise SystemExit(f"expected exactly one Sharpening descriptor, got {len(sharp)}; raw={controls['Sharpening']}")
    s=sharp[0]
    if not s["menu_records"]:
        raise SystemExit("Sharpening options pointer did not decode as Leica menu records")

    report={
        "schema":"mmonochrom.sharpness.menu1a.v1",
        "firmware_decrypted_sha256":sha(root),
        "bf547_sha256":sha(b),
        "static_ram_offset":hex(RAM),
        "descriptor_size":DESC_SIZE,
        "options_pointer_offset":hex(OPTIONS_PTR_OFF),
        "menu_record_stride":MENU_STRIDE,
        "controls":controls,
        "sharpening":s,
        "mapping":[{"label":r["label"],"enum":r["enum"]} for r in s["menu_records"]],
        "classification":"firmware_direct_controller_menu_mapping",
    }
    a.outdir.mkdir(parents=True,exist_ok=True)
    (a.outdir/"MM_SHARPNESS_MENU_PROBE.json").write_text(json.dumps(report,indent=2)+"\n")
    with (a.outdir/"MM_SHARPNESS_MENU_PROBE.txt").open("w") as f:
        f.write(f"BF547 SHA256 {sha(b)}\n")
        f.write("Sharpening descriptor:\n"+json.dumps({k:v for k,v in s.items() if k!="menu_records"},indent=2)+"\n")
        f.write("Sharpening menu:\n")
        for r in s["menu_records"]:
            f.write(f"enum {r['enum']}: {r['label']} ({r['record_off']})\n")
    print(json.dumps({"bf547_sha256":sha(b),"descriptor":{k:v for k,v in s.items() if k!="menu_records"},"mapping":report["mapping"]},indent=2))


if __name__=="__main__":main()
