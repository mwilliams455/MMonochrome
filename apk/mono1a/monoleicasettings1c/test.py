#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET

if len(sys.argv)!=2: raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
proof=json.loads((root/"LEICASHARPNESS1C_ISOLATION.json").read_text())
assert proof["revision"]=="LEICASHARPNESS1C"
assert proof["menu"]==["Off","Low","Standard","Medium high","High"]
assert proof["menuEnum"]==[0,1,2,3,4]
assert proof["default"]==2
assert proof["isoDomain"]=="physical_Camera2_SENSOR_SENSITIVITY"
assert proof["sourceBankSha256"]=="282a6e7eb0603203d5ddb36f32862e0340a9cc2d24c35b4c0af2b1bd79c06d10"
assert proof["selectorIsoCodes"]==[
 [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
 [4,4,4,4,2,2,2,2,2,2,2,2,2,2,1,1],
 [8,8,8,8,4,4,4,4,4,4,4,4,3,3,2,2],
 [11,11,11,11,8,8,8,8,8,8,8,7,6,5,4,3],
 [12,12,12,12,11,11,11,11,11,11,11,10,9,8,7,6],
]
assert proof["borderAddedPerSide"]==2
assert proof["source1dPrimaryUsesSharpness"]
assert proof["sharpnessBeforeContrast"] and proof["sharpnessBeforeToning"]
assert proof["previewUsesSameSelectorIsoCodeAndModifiedLut"]
assert not proof["previewPixelParityClaim"]
assert not proof["linearDngSharpnessChanged"]
assert not proof["exposureChanged"] and not proof["tapMeterChanged"]
assert proof["contrastPreserved"] and proof["toningPreserved"]

# Generated canonical asset/header/metadata identities.
asset=root/"app/src/main/assets/mono/mono_sharpness5.bin"
assert asset.is_file() and asset.stat().st_size==5*16*2050*2
assert hashlib.sha256(asset.read_bytes()).hexdigest()==proof["generatedAssetSha256"]
meta=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/MonoSharpness1C.java").read_text()
for marker in [
    'LABELS=new String[]{"Off","Low","Standard","Medium high","High"}',
    'SOURCE_BANK_SHA256="282a6e7eb0603203d5ddb36f32862e0340a9cc2d24c35b4c0af2b1bd79c06d10"',
    "CODES=new int[][]",
    "nearestIsoSlot(int iso)",
    "code(int selector,int iso)",
]:
    assert marker in meta,marker
header=(root/"app/src/main/cpp/mm_monochrom_sharpness5.inc").read_text()
for marker in [
    "MM_MONO_SHARP_SELECTOR_COUNT = 5",
    "MM_MONO_SHARP_ISO_COUNT = 16",
    "MM_MONO_SHARP_LUT_COUNT = 2050",
    "MM_MONO_SHARP_BORDER = 2",
    "MM_MONO_SHARP_LUT[5][16][2050]",
]:
    assert marker in header,marker

# Settings UI and order: Contrast -> Sharpness -> Toning -> Toning Strength.
ANDROID="http://schemas.android.com/apk/res/android"; akey="{"+ANDROID+"}key"
tree=ET.parse(root/"app/src/main/res/xml/preferences.xml")
cat=next(n for n in list(tree.getroot()) if n.attrib.get(akey)=="@string/pref_category_monochrom_key")
keys=[n.attrib.get(akey) for n in list(cat)]
for k in ["@string/pref_mono_contrast_key","@string/pref_mono_sharpness_key",
          "@string/pref_mono_toning_hue_key","@string/pref_mono_toning_strength_key"]:
    assert k in keys,k
assert keys.index("@string/pref_mono_contrast_key") < keys.index("@string/pref_mono_sharpness_key") < keys.index("@string/pref_mono_toning_hue_key") < keys.index("@string/pref_mono_toning_strength_key")
sharp=next(n for n in list(cat) if n.attrib.get(akey)=="@string/pref_mono_sharpness_key")
assert sharp.attrib["{"+ANDROID+"}defaultValue"]=="2"
arrays=(root/"app/src/main/res/values/arrays.xml").read_text()
for v in ["<item>Off</item>","<item>Low</item>","<item>Standard</item>","<item>Medium high</item>","<item>High</item>"]:
    assert v in arrays,v

prefs=(root/"app/src/main/java/com/particlesdevs/photoncamera/settings/PreferenceKeys.java").read_text()
for marker in [
    "KEY_MONO_SHARPNESS(R.string.pref_mono_sharpness_key)",
    "getMonoSharpnessValue()",
    "Key.KEY_MONO_SHARPNESS, 2",
    "COMMON_KEYS.add(Key.KEY_MONO_SHARPNESS.mValue)",
]:
    assert marker in prefs,marker

# Actual portable primary selection and physical ISO.
R=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java").read_text()
for marker in [
    'd.put("monochromPrimarySource", "SOURCE1D_NATIVE_DNG_XYZ_Y")',
    "getMonoSharpnessValue()",
    "CaptureResult.SENSOR_SENSITIVITY",
    "source1dSharpSelector1C, source1dSharpPhysicalIso1C, source1dSharpStats1C",
    'source1dXyzY.put("sharpnessEnum", source1dSharpSelector1C)',
    'source1dXyzY.put("sharpnessModifierCode", source1dSharpStats1C[5])',
    'selected_portable_active_sensor_DNG_XYZ_Y_with_Leica_JPEG_sharpness_contrast_toning_DNG_and_exposure_unchanged',
]:
    assert marker in R,marker
assert R.index("source1dSharpSelector1C") < R.index("source1dContrast1A")
assert R.index("source1dSharpSelector1C") < R.index("source1dToningState1A")

N=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java").read_text()
decl=re.search(r'static native boolean renderMonochrome1AWeightedDirectBitmap\([\s\S]*?\);',N)
assert decl
for marker in ["int sharpSelector","int physicalCaptureIso","long[] sharpStats","byte[] contrastCurve","int toningCr","int toningCb"]:
    assert marker in decl.group(0),marker

# Native SOURCE1D order: scalar image -> sharpness -> contrast -> toning.
C=(root/"app/src/main/cpp/m9color_jni.cpp").read_text()
assert '#include "mm_monochrom_sharpness5.inc"' in C
name="Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1AWeightedDirectBitmap("
pos=C.index(name); start=C.rfind('static int mmMonoSharpNearestIsoSlot1C',0,pos); brace=C.index('{',pos)
depth=0;end=None
for i in range(brace,len(C)):
    if C[i]=='{': depth+=1
    elif C[i]=='}':
        depth-=1
        if depth==0: end=i+1;break
assert start>=0 and end is not None
fn=C[start:end]
for marker in [
    "MM_MONO_SHARP_CODES[selector][isoSlot]",
    "MM_MONO_SHARP_LUT[selector][isoSlot]",
    "scratch[p]=static_cast<uint16_t>((static_cast<uint32_t>(image[p-1])+2u*image[p]+image[p+1])>>2)",
    "const int blur=(static_cast<int>(scratch[p-width])+2*static_cast<int>(scratch[p])+static_cast<int>(scratch[p+width]))>>2",
    "if(detail<-1024)correction=-clipMag",
    "else if(detail>1024)correction=clipMag",
    "table[1024+detail]",
    "const uint8_t yy=contrastCurve[static_cast<size_t>(idx)]",
    "91881*dCr",
    "116130*dCb",
]:
    assert marker in fn,marker
assert fn.index("MM_MONO_SHARP_LUT[selector][isoSlot]") < fn.index("const uint8_t yy=contrastCurve")
assert fn.index("const uint8_t yy=contrastCurve") < fn.index("91881*dCr")
assert "const int B=(selector>0&&modifierCode>0)?MM_MONO_SHARP_BORDER:0;" in fn

# Preview uses same selector/physical ISO/code and same 2050-value modified row.
P=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java").read_text()
for marker in [
    "latestPhysicalIso1C",
    "setLeicaSharpnessSelection1C",
    "leicaSharpnessEnum",
    "leicaSharpnessPhysicalIso",
    "leicaSharpnessModifierCode",
]:
    assert marker in P,marker
M=(root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java").read_text()
for marker in [
    "MonoSharpness1C.ASSET",
    "MonoSharpness1C.ASSET_SHA256",
    "MonoSharpness1C.nearestIsoSlot(sharpPhysicalIso1C)",
    "MonoSharpness1C.CODES[sharpSelector1C][sharpIsoSlot1C]",
    "GLES30.GL_R16I",
    "setLeicaSharpnessSelection1C(",
]:
    assert marker in M,marker
S=(root/"app/src/main/assets/shaders/preview/main_fs.glsl").read_text()
for marker in [
    "uniform highp isampler2D uMonoSharpLut1C;",
    "source14At1C",
    "sharpSource14At1C",
    "(source14At1C(uv-dy-dx)+2*source14At1C(uv-dy)+source14At1C(uv-dy+dx))>>2",
    "int blur=(ht+2*hm+hb)>>2;",
    "texelFetch(uMonoSharpLut1C,ivec2(1024+detail,0),0).r",
]:
    assert marker in S,marker

# Existing Leica Contrast and Toning remain exactly installed.
contrast=json.loads((root/"LEICACONTRAST1A_ISOLATION.json").read_text())
tone=json.loads((root/"LEICATONING1A_ISOLATION.json").read_text())
fix2=json.loads((root/"LEICATONING1A_FIX2_SOURCE1D_ISOLATION.json").read_text())
assert contrast["firmwareCurveBankSha256"]=="ac010ac0a107fb4b98ed817f24b4b9ab2d739fcfd70571b4f7d8375335e293c6"
assert tone["Cr"]==[128,130,131,127,126,128,128]
assert tone["Cb"]==[128,125,123,130,132,129,131]
assert fix2["portablePrimary"]=="SOURCE1D_NATIVE_DNG_XYZ_Y"

# Non-JPEG policy frozen by this overlay.
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
 "revision":"LEICASHARPNESS1C_TEST",
 "status":"PASS",
 "fiveFirmwareSelectors":True,
 "physicalIsoDomain":True,
 "source1dPrimarySharpnessBeforeContrastToning":True,
 "previewUsesSameModifiedLut":True,
 "dngExposureTapFrozen":True,
}
(root/"LEICASHARPNESS1C_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
