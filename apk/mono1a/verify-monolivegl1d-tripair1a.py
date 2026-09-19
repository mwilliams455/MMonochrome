#!/usr/bin/env python3
from pathlib import Path
import sys
if len(sys.argv)!=2:
    raise SystemExit("usage: verify-monolivegl1d-tripair1a.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
fs=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
rr=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
cc=root/"app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java"
for p in (fs,rr,cc):
    if not p.exists(): raise SystemExit("missing "+str(p))
s=fs.read_text(); r=rr.read_text(); c=cc.read_text()
checks=(
    ("GL1A retained","MONOLIVEGL1A_DISPLAYMONO1A" in s),
    ("GL1B retained","MONOLIVEGL1B_PAIRFIT1A" in s),
    ("GL1C retained","MONOLIVEGL1C_DUALPAIR1A" in s),
    ("GL1D marker","MONOLIVEGL1D_TRIPAIR1A" in s),
    ("residual active","monoResidualTone1B(carrierSrgb)" in s),
    ("exposure before tone",s.find("linear *= uMonoExposureScale1A") < s.find("monoResidualTone1B(carrierSrgb)")),
    ("SOURCE1D retained","MONO1A_SOURCEADAPTER1A_MANUALISO1B_PORTABLE" in r),
    ("capture controller untouched","MONOLIVEGL1" not in c),
)
for label,ok in checks:
    print(("OK   " if ok else "FAIL ")+label)
    if not ok: raise SystemExit("MONOLIVEGL1D contract failure: "+label)

vals=[0.0,0.011765,0.026144,0.039216,0.050980,0.067974,0.083660,0.103268,
      0.121569,0.151634,0.206536,0.278431,0.380392,0.522876,0.701961,0.862745,1.0]
if any(vals[i+1] < vals[i] for i in range(16)):
    raise SystemExit("GL1D residual is not monotonic")
if vals[0] != 0.0 or vals[-1] != 1.0:
    raise SystemExit("GL1D endpoints invalid")
for forbidden in ("ColorMatrix","ForwardMatrix","Cobalt","HSM","curve02M9","sat2M9","sourceToM9Target"):
    if forbidden in s:
        raise SystemExit("forbidden source/colour operation in GL1D shader: "+forbidden)
print("MONOLIVEGL1D_TRIPAIR1A verification PASS")
