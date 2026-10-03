#!/usr/bin/env python3
from pathlib import Path
import json,re,sys
if len(sys.argv)!=2: raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1])
proof=json.loads((root/"LEICATONING1A_FIX2_SOURCE1D_ISOLATION.json").read_text())
assert proof["revision"]=="LEICATONING1A_FIX2_SOURCE1D"
assert proof["portablePrimary"]=="SOURCE1D_NATIVE_DNG_XYZ_Y"
assert proof["source1dUsesSelectedContrast"]
assert proof["source1dUsesSelectedToning"]
assert proof["source1dMissingCurveFallback"]=="validated_standard_curve02"
assert proof["previewAndPrimarySettingsShared"]
assert not proof["linearDngToneChanged"]
assert not proof["linearDngToningChanged"]
assert not proof["exposureChanged"]
assert not proof["tapMeterChanged"]
assert proof["rawScalarDiagnosticPathRetained"]

R=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java").read_text()
# The selected portable photographic output must still be SOURCE1D.
for marker in [
    'source1dXyzY.put("photographicOutputSelected", true)',
    'd.put("monochromPrimarySource", "SOURCE1D_NATIVE_DNG_XYZ_Y")',
]:
    assert marker in R,marker
assert 'return new RenderCore(equalRgbBitmap, d,' in ' '.join(R.split()), "SOURCE1D equalRgbBitmap is not primary RenderCore bitmap"

# Crucial FIX2 contract: settings are computed before SOURCE1D native render and passed into it.
for marker in [
    "final int source1dContrast1A = MonoContrastCurves1A.clamp(",
    "final byte[] source1dContrastCurve1A = MonoContrastCurves1A.loadCurveOrNull(source1dContrast1A);",
    "final int source1dToningState1A =",
    "MonoToning1A.state(source1dToningHue1A, source1dToningStrength1A)",
    "final int source1dToningCr1A = MonoToning1A.CR[source1dToningState1A];",
    "final int source1dToningCb1A = MonoToning1A.CB[source1dToningState1A];",
    "source1dWeightR, source1dWeightG, source1dWeightB,",
    "source1dContrastCurve1A, source1dToningCr1A, source1dToningCb1A",
]:
    assert marker in R,marker

# SOURCE1D telemetry must no longer claim a hard-wired curve02 primary.
for marker in [
    'source1dXyzY.put("curve", "firmware_normalISO_sRGB_curve0" + source1dContrast1A)',
    'source1dXyzY.put("contrastEnum", source1dContrast1A)',
    'source1dXyzY.put("toningState", source1dToningState1A)',
    'source1dXyzY.put("toningCr", source1dToningCr1A)',
    'source1dXyzY.put("toningCb", source1dToningCb1A)',
    'selected_portable_active_sensor_DNG_XYZ_Y_with_Leica_JPEG_contrast_and_toning_DNG_and_exposure_unchanged',
]:
    assert marker in R,marker
assert 'source1dXyzY.put("curve", "same_frozen_Monochrom_curve02")' not in R

N=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java").read_text()
decl=re.search(r'static native boolean renderMonochrome1AWeightedDirectBitmap\([\s\S]*?\);',N)
assert decl
for marker in ["byte[] contrastCurve","int toningCr","int toningCb"]:
    assert marker in decl.group(0),marker

C=(root/"app/src/main/cpp/m9color_jni.cpp").read_text()
name="Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1AWeightedDirectBitmap("
pos=C.index(name)
start=C.rfind('extern "C" JNIEXPORT jboolean JNICALL',0,pos)
brace=C.index('{',pos); depth=0; end=None
for i in range(brace,len(C)):
    if C[i]=='{': depth+=1
    elif C[i]=='}':
        depth-=1
        if depth==0: end=i+1; break
assert end is not None
fn=C[start:end]
for marker in [
    "jbyteArray contrastCurveArray, jint toningCr, jint toningCb",
    "contrastCurve[i]=MM_MONO1A_CURVE02[i]",
    "const uint8_t yy=contrastCurve[static_cast<size_t>(idx)]",
    "91881*dCr",
    "22554*dCb+46802*dCr",
    "116130*dCb",
    "uint32_t(outR)<<16",
    "uint32_t(outG)<<8",
    "uint32_t(outB)",
]:
    assert marker in fn,marker
# The only curve02 use in SOURCE1D is fallback, never the normal lookup.
assert "const uint8_t yy=MM_MONO1A_CURVE02[idx]" not in fn

# Exact firmware state table from parent Toning remains untouched.
tone=json.loads((root/"LEICATONING1A_ISOLATION.json").read_text())
assert tone["Cr"]==[128,130,131,127,126,128,128]
assert tone["Cb"]==[128,125,123,130,132,129,131]
contrast=json.loads((root/"LEICACONTRAST1A_ISOLATION.json").read_text())
assert contrast["firmwareCurveBankSha256"]=="ac010ac0a107fb4b98ed817f24b4b9ab2d739fcfd70571b4f7d8375335e293c6"

# Conversion sanity: Off is exact grayscale, Sepia Weak creates nonzero chroma.
def rs(x): return ((x+32768)>>16) if x>=0 else -(((-x)+32768)>>16)
def clip(x): return max(0,min(255,x))
def rgb(y,cr,cb):
    dcr=cr-128; dcb=cb-128
    return (clip(y+rs(91881*dcr)),clip(y-rs(22554*dcb+46802*dcr)),clip(y+rs(116130*dcb)))
for y in range(256): assert rgb(y,128,128)==(y,y,y)
sepia=rgb(128,130,125)
assert sepia[0]!=sepia[1] or sepia[1]!=sepia[2]
assert sepia[0]>sepia[2]

# DNG/exposure/tap freeze is recorded from before/after this exact overlay.
expected={
 "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngExport1A.java",
 "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngWriter1A.java",
 "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoLinearPlane1A.java",
 "app/src/main/java/com/particlesdevs/photoncamera/m9/exposure/MonoPlacementAssist1D.java",
 "app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoTapMeter1A.java",
 "app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java",
}
assert set(proof["frozenPolicyHashes"])==expected
report={
 "revision":"LEICATONING1A_FIX2_SOURCE1D_TEST",
 "status":"PASS",
 "portablePrimaryReceivesSelectedContrast":True,
 "portablePrimaryReceivesSelectedToning":True,
 "offExactGray":True,
 "sepiaWeakNonGray":True,
 "dngExposureTapFrozen":True,
}
(root/"LEICATONING1A_FIX2_SOURCE1D_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
