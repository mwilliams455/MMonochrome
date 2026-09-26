#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, math, re, shutil, sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
here=Path(__file__).resolve().parent
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
assist=J/"m9/exposure/MonoPlacementAssist1D.java"
gradle=root/"app/build.gradle"
if not assist.exists() or not gradle.exists():
    raise SystemExit("MONOAUTO1D1D parent missing")
parent=assist.read_text()
if "MONOAUTO1D_PLACEMENTASSIST1C_BROADTAIL1A" not in parent:
    raise SystemExit("MONOAUTO1D1D requires generated 1C parent")
if "BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION = 0.002" not in parent:
    raise SystemExit("MONOAUTO1D1D expected exact 1C clip allowance")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

frozen=[
    J/"m9/render/M9R35Renderer.java",
    J/"m9/export/MonoDngExport1A.java",
    J/"m9/export/MonoDngWriter1A.java",
    J/"m9/export/MonoLinearPlane1A.java",
    J/"m9/export/MonoPlacementProbe1A.java",
    J/"m9/preview/MonoGpuPreview2A.java",
    J/"m9/M9M10rMfmTest1A.java",
    root/"app/src/main/cpp/m9color_jni.cpp",
    root/"app/src/main/assets/mono/mono_curve02_gl2a.bin",
    root/"app/src/main/assets/shaders/preview/main_fs.glsl",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}

shutil.copyfile(here/"MonoPlacementAssist1D.java",assist)

g=gradle.read_text()
m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("versionName missing")
v=m.group(1)
if "monoauto1d-placementassist1d-broadtail05" not in v:
    g=g[:m.start(1)]+v+"-monoauto1d-placementassist1d-broadtail05"+g[m.end(1):]
    gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("MONOAUTO1D1D frozen non-policy seam changed: "+repr(changed))

latest_ev=0.32700269262775195
latest_raw_q998=0.5391032325338895
proof={
 "revision":"MONOAUTO1D_PLACEMENTASSIST1D_BROADTAIL05",
 "parent":"MONOAUTO1D_PLACEMENTASSIST1C_BROADTAIL1A",
 "policyChangeOnly":"BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION_0p002_to_0p005",
 "sceneIntentChanged":False,
 "placementMagnitudeChanged":False,
 "broadTailQ99TargetChanged":False,
 "globalPositiveLimitChanged":False,
 "manualAuthorityChanged":False,
 "oldMaxExistingProxyClipFraction":0.002,
 "newMaxExistingProxyClipFraction":0.005,
 "latest115229Replay":{
   "mfmRecommendedEv":latest_ev,
   "referencePlacementDeltaEv":2.388146212929508,
   "sensorRgbMaxQ99":0.6862745098039216,
   "sensorRgbMaxQ998":1.0,
   "sensorRgbMaxClipFraction":0.0026041666666666665,
   "broadTailHeadroomEv":0.5145731728297582,
   "strictPositiveHeadroomEv":0.05602807624368708,
   "old1CEligible":False,
   "new1DEligible":True,
   "expectedAppliedEv":latest_ev,
   "completedRawQ998Observed":latest_raw_q998,
   "completedRawHardClipFractionObserved":0.0010805130004882812,
   "completedRawHeadroomTo0p92EvObserved":0.7710723009854845,
   "counterfactualRawQ998At1D":latest_raw_q998*(2.0**latest_ev)
 },
 "jpegRendererChanged":False,
 "dngSamplesChanged":False,
 "baselineExposureChanged":False,
 "curve02AssetChanged":False,
 "previewProbeChanged":False,
 "postCaptureProbeChanged":False,
 "mfmChanged":False,
 "HDR":False,
 "postCaptureRescue":False,
 "frozen":after
}
(root/"MONOAUTO1D_PLACEMENTASSIST1D_BROADTAIL05_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
