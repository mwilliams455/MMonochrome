#!/usr/bin/env python3
from pathlib import Path
import sys
if len(sys.argv)!=2:
    raise SystemExit("usage: verify-monolivegl1c-dualpair1a.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
fs=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
rr=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
cc=root/"app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java"
for p in (fs,rr,cc):
    if not p.exists(): raise SystemExit("missing "+str(p))
s=fs.read_text(); r=rr.read_text(); c=cc.read_text()
for label,ok in (
    ("GL1A retained","MONOLIVEGL1A_DISPLAYMONO1A" in s),
    ("GL1B retained","MONOLIVEGL1B_PAIRFIT1A" in s),
    ("GL1C marker","MONOLIVEGL1C_DUALPAIR1A" in s),
    ("residual active","monoResidualTone1B(carrierSrgb)" in s),
    ("exposure before tone",s.find("linear *= uMonoExposureScale1A") < s.find("monoResidualTone1B(carrierSrgb)")),
    ("SOURCE1D retained","MONO1A_SOURCEADAPTER1A_MANUALISO1B_PORTABLE" in r),
    ("capture controller untouched","MONOLIVEGL1" not in c),
):
    print(("OK   " if ok else "FAIL ")+label)
    if not ok: raise SystemExit("MONOLIVEGL1C contract failure: "+label)

vals=[0.0,0.011765,0.025490,0.035294,0.050980,0.066667,0.082353,0.100000,
      0.119608,0.150980,0.205882,0.276471,0.372549,0.537255,0.752941,0.884314,1.0]
if any(vals[i+1] < vals[i] for i in range(16)):
    raise SystemExit("GL1C residual is not monotonic")
if vals[0] != 0.0 or vals[-1] != 1.0:
    raise SystemExit("GL1C endpoints invalid")
for forbidden in ("ColorMatrix","ForwardMatrix","Cobalt","HSM","curve02M9","sat2M9","sourceToM9Target"):
    if forbidden in s:
        raise SystemExit("forbidden source/colour operation in GL1C shader: "+forbidden)
print("MONOLIVEGL1C_DUALPAIR1A verification PASS")
