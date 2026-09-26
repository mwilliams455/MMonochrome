#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, shutil, sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
here=Path(__file__).resolve().parent
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
assist=J/"m9/exposure/MonoPlacementAssist1D.java"
gradle=root/"app/build.gradle"
if not assist.exists() or not gradle.exists():
    raise SystemExit("MONOAUTO1D1C parent missing")
parent=assist.read_text()
if "MONOAUTO1D_PLACEMENTASSIST1B_RAWPROXY1A" not in parent:
    raise SystemExit("MONOAUTO1D1C requires generated 1B parent")
if "sensorRgbMaxQ99" not in parent:
    raise SystemExit("MONOAUTO1D1C requires 1B sensor proxy observation")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen=[
    J/"m9/render/M9R35Renderer.java",
    J/"m9/export/MonoDngExport1A.java",
    J/"m9/export/MonoDngWriter1A.java",
    J/"m9/export/MonoLinearPlane1A.java",
    J/"m9/export/MonoPlacementProbe1A.java",
    J/"m9/preview/MonoGpuPreview2A.java",
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
if "monoauto1d-placementassist1c-broadtail1a" not in v:
    g=g[:m.start(1)]+v+"-monoauto1d-placementassist1c-broadtail1a"+g[m.end(1):]
    gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("MONOAUTO1D1C frozen non-policy seam changed: "+repr(changed))

proof={
 "revision":"MONOAUTO1D_PLACEMENTASSIST1C_BROADTAIL1A",
 "parent":"MONOAUTO1D_PLACEMENTASSIST1B_RAWPROXY1A",
 "exposurePolicyChangedFrom1B":True,
 "policyChangeOnly":"positive_headroom_selection",
 "sceneIntent":"existing_MFM_unchanged",
 "placementMagnitude":"existing_live_SOURCE1D_reference_delta_unchanged",
 "strictHighlightPath":"existing_SOURCE1D_q99p8_to_0p92_retained",
 "broadTailPath":{
   "requiresStrongPositiveMfm":True,
   "requiresPositiveGeometry":True,
   "proxy":"reconstructed_sensor_RGB_max",
   "quantile":0.99,
   "target":250.0/255.0,
   "maxExistingProxyClipFraction":0.002,
   "boundedByMfmRecommendedEv":True,
   "boundedByGlobalPositiveLimitEv":0.50,
   "interpretation":"single_exposure_small_extreme_highlight_sacrifice_not_HDR"
 },
 "current110526Replay":{
   "mfmRecommendedEv":0.5840264650751639,
   "referencePlacementDeltaEv":2.663518660757086,
   "strictQ998HeadroomEv":0.15789163590289854,
   "sensorRgbMaxQ99":187.0/255.0,
   "broadTailHeadroomEv":__import__("math").log2((250.0/255.0)/(187.0/255.0)),
   "expectedAppliedEv":__import__("math").log2(250.0/187.0),
   "completedRawQ998ObservedAfter1B":0.45985401459854014,
   "completedRawQ998CounterfactualAt1C":0.45985401459854014 * (2.0 ** (__import__("math").log2(250.0/187.0)-0.15789163590289854))
 },
 "jpegRendererChanged":False,
 "dngSamplesChanged":False,
 "baselineExposureChanged":False,
 "curve02AssetChanged":False,
 "previewProbeChangedFrom1B":False,
 "postCaptureProbeChangedFrom1B":False,
 "HDR":False,
 "postCaptureRescue":False,
 "manualAuthorityPreserved":True,
 "frozen":after
}
(root/"MONOAUTO1D_PLACEMENTASSIST1C_BROADTAIL1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
