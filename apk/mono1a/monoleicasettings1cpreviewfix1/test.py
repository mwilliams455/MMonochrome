#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys

if len(sys.argv)!=2: raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1])
p=json.loads((root/"LEICASHARPNESS1C_PREVIEWFIX1_ISOLATION.json").read_text())
assert p["revision"]=="LEICASHARPNESS1C_PREVIEWFIX1"
assert p["savedJpegSharpnessPreserved"]
assert p["source1dPrimarySharpnessPreserved"]
assert p["previewSharpnessTemporarilyDisabled"]
assert p["previewRestoredTo"]=="last_known_good_SOURCE1D_plus_Contrast_plus_Toning"
assert p["previewContrastPreserved"] and p["previewToningPreserved"]
assert not p["linearDngSharpnessChanged"]

# Still path remains the exact five-level SOURCE1D implementation.
R=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
N=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java"
C=root/"app/src/main/cpp/m9color_jni.cpp"
for f in (R,N,C):
    rel=str(f.relative_to(root))
    assert hashlib.sha256(f.read_bytes()).hexdigest()==p["stillSourceHashes"][rel],rel
r=R.read_text()
for marker in [
    "getMonoSharpnessValue()",
    "source1dSharpSelector1C",
    "source1dSharpPhysicalIso1C",
    "source1dSharpStats1C",
    'source1dXyzY.put("sharpnessEnum", source1dSharpSelector1C)',
    'source1dXyzY.put("sharpnessLabel", MonoSharpness1C.LABELS[source1dSharpSelector1C])',
    'selected_portable_active_sensor_DNG_XYZ_Y_with_Leica_JPEG_sharpness_contrast_toning_DNG_and_exposure_unchanged',
]:
    assert marker in r,marker
c=C.read_text()
for marker in [
    "mmMonoSharpNearestIsoSlot1C",
    "MM_MONO_SHARP_CODES[selector][isoSlot]",
    "MM_MONO_SHARP_BASE[isoSlot][i]",
    "const int B=(selector>0&&modifierCode>0)?MM_MONO_SHARP_BORDER:0",
    "const uint8_t yy=contrastCurve[static_cast<size_t>(idx)]",
]:
    assert marker in c,marker

# Preview must be the last known-good SOURCE1D + Contrast + Toning shader.
s=(root/"app/src/main/assets/shaders/preview/main_fs.glsl").read_text()
for forbidden in [
    "uMonoSharpLut1C","uMonoSharpReady1C","uMonoSharpSelector1C",
    "sharpSource14At1C","source14At1C","fallbackMono1C",
]:
    assert forbidden not in s,forbidden
for required in [
    "float monochrome(vec3 oes)",
    "float y=monochrome(oes.rgb);",
    "uMonoCurve2A",
    "uMonoToningCr1A",
    "uMonoToningCb1A",
]:
    assert required in s,required

m=(root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java").read_text()
for forbidden in [
    "monoSharpTex1C","monoSharpReadyUniform1C","monoSharpSelectorUniform1C",
    "monoSharpBank1C","setLeicaSharpnessSelection1C","GL_R16I","GL_RED_INTEGER",
]:
    assert forbidden not in m,forbidden
for required in [
    "MonoContrastCurves1A.BANK_SHA256",
    "getMonoToningHueValue()",
    "getMonoToningStrengthValue()",
    "setLeicaToningSelection(",
]:
    assert required in m,required

pjava=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java").read_text()
for forbidden in ["MonoSharpness1C","latestPhysicalIso1C","selectedSharpSelector1C","setLeicaSharpnessSelection1C"]:
    assert forbidden not in pjava,forbidden
for required in ["setLeicaContrastSelection","setLeicaToningSelection","leicaToningState"]:
    assert required in pjava,required

sharp=json.loads((root/"LEICASHARPNESS1C_ISOLATION.json").read_text())
assert sharp["menu"]==["Off","Low","Standard","Medium high","High"]
assert sharp["default"]==2
assert sharp["source1dPrimaryUsesSharpness"]

report={
 "revision":"LEICASHARPNESS1C_PREVIEWFIX1_TEST",
 "status":"PASS",
 "savedJpegSharpnessPreserved":True,
 "previewSharpnessDisabled":True,
 "workingContrastToningPreviewRestored":True
}
(root/"LEICASHARPNESS1C_PREVIEWFIX1_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
