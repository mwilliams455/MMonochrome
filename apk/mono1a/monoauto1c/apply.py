#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, shutil, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
here = Path(__file__).resolve().parent
J = root / "app/src/main/java/com/particlesdevs/photoncamera"
renderer = J / "m9/render/M9R35Renderer.java"
exporter = J / "m9/export/MonoDngExport1A.java"
writer = J / "m9/export/MonoDngWriter1A.java"
gradle = root / "app/build.gradle"

for p in (renderer, exporter, writer, gradle):
    if not p.exists():
        raise SystemExit("missing required parent file: " + str(p))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

sealed_paths = [
    J / "capture/CaptureController.java",
    J / "processing/parameters/IsoExpoSelector.java",
    J / "ui/camera/views/viewfinder/MainRenderer.java",
    J / "ui/camera/views/viewfinder/GLPreview.java",
    J / "m9/preview/MonoGpuPreview2A.java",
    J / "m9/preview/MonoPreviewMath2A.java",
    J / "m9/export/MonoDngWriter1A.java",
    root / "app/src/main/cpp/m9color_jni.cpp",
    root / "app/src/main/assets/shaders/preview/main_fs.glsl",
]
sealed_before = {str(p.relative_to(root)): sha(p) for p in sealed_paths if p.exists()}

for name in ("MonoPlacementMath1A.java", "MonoPlacementProbe1A.java"):
    dst = J / "m9/export" / name
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(here / name, dst)

e = exporter.read_text()
r = renderer.read_text()
e_before = e
r_before = r

old_sig = """    public static Pending capture(Mat cameraRgb,int width,int height,int rotation,
            float[] weights,double representationScale) throws Exception {"""
new_sig = """    public static Pending capture(Mat cameraRgb,int width,int height,int rotation,
            float[] weights,double representationScale,
            double rawUq99,double rawUq995,double rawUq998,double rawHardClipFraction) throws Exception {"""
if e.count(old_sig) != 1:
    raise SystemExit("MonoDngExport1A capture signature anchor mismatch")
e = e.replace(old_sig, new_sig, 1)

anchor = """        d.put("limitations","Bayer_interpolation_and_source_luminance_mix_committed;_earlier_clipping_not_recovered");
        d.put("copyElapsedMs",(System.nanoTime()-start)/1e6);
        return new Pending(p,d);
"""
replacement = """        d.put("limitations","Bayer_interpolation_and_source_luminance_mix_committed;_earlier_clipping_not_recovered");
        d.put("monoPlacementProbe1A",MonoPlacementProbe1A.evaluate(
                p,rawUq99,rawUq995,rawUq998,rawHardClipFraction));
        d.put("copyElapsedMs",(System.nanoTime()-start)/1e6);
        return new Pending(p,d);
"""
if e.count(anchor) != 1:
    raise SystemExit("MonoDngExport1A diagnostic anchor mismatch")
e = e.replace(anchor, replacement, 1)
exporter.write_text(e)

pattern = re.compile(
    r'(monoDngPending1A\s*=\s*MonoDngExport1A\.capture\(cam16,width,height,cameraRotation,\s*'
    r'new float\[\]\{monoDngSource1A\.sensorToXyzD50\[3\],monoDngSource1A\.sensorToXyzD50\[4\],monoDngSource1A\.sensorToXyzD50\[5\]\},\s*'
    r'applyNativeShading && nativeShading\.applied \? nativeShading\.representationScale : 1\.0)(\);)'
)
m = pattern.search(r)
if not m:
    raise SystemExit("renderer MonoDngExport1A capture-call anchor mismatch")
new_call = m.group(1) + """,
                            tail.uq99,tail.uq995,tail.uq998,tail.clipFraction""" + m.group(2)
r = r[:m.start()] + new_call + r[m.end():]

marker_anchor = '                d.put("outputRevision",MonoDngExport1A.REVISION);'
marker_repl = '                d.put("placementProbeRevision",MonoPlacementProbe1A.REVISION);\n' + marker_anchor
if marker_anchor not in r:
    raise SystemExit("renderer outputRevision anchor missing")
if "placementProbeRevision" not in r:
    r = r.replace(marker_anchor, marker_repl, 1)

renderer.write_text(r)

g = gradle.read_text()
mver = re.search(r"versionName\s+'([^']+)'", g)
if not mver:
    raise SystemExit("versionName missing")
if "monoauto1c" not in mver.group(1):
    g = g[:mver.start(1)] + mver.group(1) + "-monoauto1c-placementprobe1a" + g[mver.end(1):]
    gradle.write_text(g)

sealed_after = {str(p.relative_to(root)): sha(p) for p in sealed_paths if p.exists()}
if sealed_before != sealed_after:
    changed = [k for k in sealed_before if sealed_before[k] != sealed_after.get(k)]
    raise SystemExit("sealed photographic/control files changed: " + repr(changed))

proof = {
    "revision": "MONOAUTO1C_PLACEMENTPROBE1A",
    "mode": "diagnostic_only",
    "parent": "MONOOUTPUT1E_BASELINE_IFD0",
    "referenceTarget": 0.107 * (8192.0 / 10000.0),
    "referenceOrigin": "recovered_M9_TC20_scene_key_reference",
    "runtimeInputs": [
        "SOURCE1D derived linear plane",
        "physical RAW q99/q99.5/q99.8 from existing RawTail",
        "physical RAW hard clip fraction",
        "existing M10-R MFM live snapshot"
    ],
    "captureExposureChanged": False,
    "jpegRenderChanged": False,
    "curve02Changed": False,
    "dngSamplesChanged": False,
    "baselineExposureChanged": False,
    "previewChanged": False,
    "sourceAdapterChanged": False,
    "exporterBeforeSha256": hashlib.sha256(e_before.encode()).hexdigest(),
    "exporterAfterSha256": sha(exporter),
    "rendererBeforeSha256": hashlib.sha256(r_before.encode()).hexdigest(),
    "rendererAfterSha256": sha(renderer),
    "sealedFiles": sealed_after
}
(root / "MONOAUTO1C_PLACEMENTPROBE1A_ISOLATION.json").write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
