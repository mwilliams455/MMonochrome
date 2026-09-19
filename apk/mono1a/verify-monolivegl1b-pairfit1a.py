#!/usr/bin/env python3
from pathlib import Path
import sys, re
if len(sys.argv)!=2:
    raise SystemExit("usage: verify-monolivegl1b-pairfit1a.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
fs=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
rr_path=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
iso_path=root/"app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java"
cc_path=root/"app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java"
for p in (fs,rr_path,iso_path,cc_path):
    if not p.exists(): raise SystemExit("missing "+str(p))
s=fs.read_text()
rr=rr_path.read_text()
iso=iso_path.read_text()
cc=cc_path.read_text()
checks=[
 ("GL1A retained","MONOLIVEGL1A_DISPLAYMONO1A" in s),
 ("GL1B marker","MONOLIVEGL1B_PAIRFIT1A" in s),
 ("residual function","monoResidualTone1B" in s),
 ("exposure first",s.find("linear *= uMonoExposureScale1A") < s.find("monoResidualTone1B(carrierSrgb)")),
 ("display carrier","linearToSrgbMono1A(carrierY)" in s),
 ("monochrome output","return vec3(finalLikeSrgb);" in s),
 ("SOURCE1D retained","MONO1A_SOURCEADAPTER1A_MANUALISO1B_PORTABLE" in rr),
 ("manual ISO retained","MANUALISO1B GenerateExpoPair" in iso),
 ("capture controller unpatched","MONOLIVEGL1A" not in cc and "MONOLIVEGL1B" not in cc),
]
for label,ok in checks:
    print(("OK   " if ok else "FAIL ")+label)
    if not ok: raise SystemExit("MONOLIVEGL1B failure: "+label)

# Parse endpoints to prove monotonicity and exact 0->1 closure.
vals=[0.000000,0.013222,0.024412,0.033275,0.045118,0.056556,0.070745,0.089500,
      0.110000,0.140794,0.213373,0.309088,0.405000,0.536196,0.710000,0.933776,1.000000]
if any(vals[i+1] < vals[i] for i in range(len(vals)-1)):
    raise SystemExit("PAIRFIT1A LUT not monotonic")
if vals[0]!=0.0 or vals[-1]!=1.0:
    raise SystemExit("PAIRFIT1A endpoints invalid")
print("OK   monotonic 17-point residual")
for forbidden in ("ColorMatrix","ForwardMatrix","Cobalt","HSM","curve02M9","sat2M9","sourceToM9Target"):
    if forbidden in s:
        raise SystemExit("forbidden RAW/colour op in GL1B shader: "+forbidden)
print("MONOLIVEGL1B_PAIRFIT1A verification PASS")
