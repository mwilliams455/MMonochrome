#!/usr/bin/env python3
"""Hash-bound verifier for the M Monochrom dual-output scalar correction path.

Claims are intentionally narrow and tied to canonical 1.022 BF561 bytes:
- Run's bit-10 special path invokes CorrectionDualOutput before the ordinary
  InitL1MemoryProcessing / scalar processing loop.
- CorrectionDualOutput iterates over processing-context L3 slot 0 and slot 1
  (context+0x00 and context+0x04), DMA-copies each selected L3 plane into the
  same L1 16-bit working plane at context+0x34, applies one of the native
  Process_DualOutputCorrec routines, and can DMA-copy the corrected plane back
  to the same selected L3 slot.
- Both native correction routines operate on 16-bit word samples.
- The ordinary Run path subsequently performs its initial L3L1_Get with
  selector 0.

This proves scalar/word-domain dual-output correction topology.  It does not
identify the sensor spectral response, analog readout physics, or assert that
all captures enable bit 10.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

ANCHORS = {
    "Run": (2444, "9a7aef3a340f4617b547accff61ed72ddb8b466cd5d01f0758542e0756fd58f0"),
    "CorrectionDualOutput": (874, "56a2756027cf6803525c9c9aac0096d59470cf466a4e27724417216de625a4ad"),
    "Process_DualOutputCorrec_0": (890, "b5aedafcafe154e37791aa88f3daba3ce5cd4cc21ba41fdba6ca9efec59c2b86"),
    "Process_DualOutputCorrec_1": (1198, "4d768941d48977a185cb29af572dea5f4192e73342b95d27d5254b947d2e6a69"),
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def lines(path: Path) -> list[str]:
    return [x.lower().replace("0x0x", "0x") for x in path.read_text(errors="replace").splitlines()]


def at(path: Path) -> dict[int, str]:
    out={}
    for raw in lines(path):
        m=re.match(r"^\s*([0-9a-f]+):",raw)
        if m: out[int(m.group(1),16)]=raw
    return out


def require(cond: bool, msg: str, problems: list[str]) -> None:
    if not cond: problems.append(msg)


def has(seq: list[str], *needles: str) -> bool:
    return any(all(n.lower() in x for n in needles) for x in seq)


def verify_anchor(name: str, path: Path, problems: list[str]) -> None:
    size, sha=ANCHORS[name]
    data=path.read_bytes()
    require(len(data)==size,f"{name}: size {len(data)} != {size}",problems)
    require(digest(path)==sha,f"{name}: SHA-256 drift",problems)


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--run-bin",required=True,type=Path)
    ap.add_argument("--run-dis",required=True,type=Path)
    ap.add_argument("--correction-bin",required=True,type=Path)
    ap.add_argument("--correction-dis",required=True,type=Path)
    ap.add_argument("--process0-bin",required=True,type=Path)
    ap.add_argument("--process0-dis",required=True,type=Path)
    ap.add_argument("--process1-bin",required=True,type=Path)
    ap.add_argument("--process1-dis",required=True,type=Path)
    ap.add_argument("--strict",action="store_true")
    args=ap.parse_args()

    problems=[]
    verify_anchor("Run",args.run_bin,problems)
    verify_anchor("CorrectionDualOutput",args.correction_bin,problems)
    verify_anchor("Process_DualOutputCorrec_0",args.process0_bin,problems)
    verify_anchor("Process_DualOutputCorrec_1",args.process1_bin,problems)

    run=lines(args.run_dis); corr=lines(args.correction_dis)
    p0=lines(args.process0_dis); p1=lines(args.process1_dis)
    run_at=at(args.run_dis)

    # Run special path: bit 10 check, qualifying jump to CorrectionDualOutput,
    # return to ordinary path, then InitL1MemoryProcessing later in that path.
    require(has(run,"bittst (r5, 0xa)"),"Run: bit-10 gate missing",problems)
    require(has(run,"jump.s 0xffa02114"),"Run: special branch to CorrectionDualOutput call missing",problems)
    require("call 0xffa11c8c" in run_at.get(0xffa02114,""),"Run: CorrectionDualOutput call target drift",problems)
    require("jump.s 0xffa017e0" in run_at.get(0xffa0211a,""),"Run: correction return to ordinary path missing",problems)
    require("call 0xffa120d8" in run_at.get(0xffa01846,""),"Run: InitL1MemoryProcessing anchor missing",problems)
    require("call 0xffa122d2" in run_at.get(0xffa01acc,""),"Run: initial L3L1_Get anchor missing",problems)
    require("r1 = r1 - r1" in run_at.get(0xffa01ac2,""),"Run: initial L3L1_Get selector-0 zeroing missing",problems)

    # CorrectionDualOutput receives context in R1 -> P4, saves context and
    # context+4 as the two L3 pointer-slot addresses, then selects one per pass.
    require(has(corr,"p4 = r1"),"CorrectionDualOutput: context R1->P4 missing",problems)
    require(has(corr,"p5 = p4"),"CorrectionDualOutput: context slot0 base save missing",problems)
    require(has(corr,"p4 += 0x4"),"CorrectionDualOutput: context+4 slot1 step missing",problems)
    require(has(corr,"[fp -0x20] = p4"),"CorrectionDualOutput: context+4 save missing",problems)
    require(has(corr,"p1 = p5"),"CorrectionDualOutput: slot0 selection missing",problems)
    require(has(corr,"if !cc p1 = p0"),"CorrectionDualOutput: alternate slot1 selection missing",problems)
    require(has(corr,"r5 = [p1]"),"CorrectionDualOutput: selected L3 pointer load missing",problems)

    # Selected L3 pointer -> common L1 16-bit plane, followed by optional
    # writeback to the same selected L3 pointer.
    require(has(corr,"r1 = [p5 + 0x34]"),"CorrectionDualOutput: context+0x34 L1 working pointer missing",problems)
    require(has(corr,"r0 = [fp + 0xc]"),"CorrectionDualOutput: selected L3 pointer as DMA R0 missing",problems)
    require(has(corr,"call 0xffa02d72"),"CorrectionDualOutput: DMACopyWindow missing",problems)
    require(has(corr,"call 0xffa02dbe"),"CorrectionDualOutput: DMACopyBackWindow missing",problems)
    require(has(corr,"call 0xffa11910"),"CorrectionDualOutput: first native correction routine missing",problems)
    require(has(corr,"call 0xffa00d30"),"CorrectionDualOutput: second native correction routine missing",problems)

    # Both native algorithms visibly read and write 16-bit words. Avoid
    # overfitting exact loop counts; hash anchors already protect semantics.
    for label,seq in (("process0",p0),("process1",p1)):
        require(any("= w[" in x for x in seq),f"{label}: 16-bit word loads missing",problems)
        require(any("w[" in x and "] =" in x for x in seq),f"{label}: 16-bit word stores missing",problems)

    out={
        "schema":"mmonochrom.source1e.dual_output_scalar.v1",
        "scope":"hash_bound_preprocessing_topology_not_capture_enablement_or_sensor_spectral_response",
        "run_special_path":{
            "gate":"processing bit 10 plus Run mode conditions",
            "correction_call":"0xffa02114 -> CorrectionDualOutput@0xffa11c8c",
            "resume":"0xffa0211a -> 0xffa017e0 ordinary Run path",
            "ordinary_initial_get":"L3L1_Get(selector=0) at 0xffa01acc",
        },
        "dual_output_slots":{
            "slot0":"processing context +0x00",
            "slot1":"processing context +0x04",
            "working_plane":"processing context +0x34 (16-bit L1)",
            "operation":"each selected L3 plane is DMA-loaded, word-domain corrected, and can be DMA-written back in place",
        },
        "native_algorithms":{
            "0xffa11910":"16-bit word-sample Process_DualOutputCorrec occurrence 0",
            "0xffa00d30":"16-bit word-sample Process_DualOutputCorrec occurrence 1",
        },
        "conclusion":(
            "The canonical M Monochrom dual-output correction is a pre-normal-processing, 16-bit scalar-word stage over the two job-selected L3 planes at context+0 and context+4. "
            "After that special stage, ordinary Run begins by loading selector 0 into the scalar L1 working plane. No RGB/YCrCb generation is involved in this verified segment."
        ),
        "problems":problems,
        "verified":not problems,
    }
    print(json.dumps(out,indent=2))
    if args.strict and problems: raise SystemExit(2)

if __name__=="__main__":
    main()
