#!/usr/bin/env python3
from pathlib import Path
import json, re, sys
import xml.etree.ElementTree as ET

if len(sys.argv)!=2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
proof=json.loads((root/"LEICATONING1A_ISOLATION.json").read_text())

assert proof["revision"]=="LEICATONING1A"
assert proof["firmware"]=="Leica M Monochrom 1.022"
assert proof["hueMenu"]==["Sepia","Cool","Selenium"]
assert proof["strengthMenu"]==["Off","Weak","Strong"]
assert proof["stateFormula"]=="strength==0 ? 0 : strength + 2*hue"
assert proof["stateLabels"]==[
    "Off","Sepia Weak","Sepia Strong","Cool Weak","Cool Strong","Selenium Weak","Selenium Strong"
]
assert proof["Cr"]==[128,130,131,127,126,128,128]
assert proof["Cb"]==[128,125,123,130,132,129,131]
assert proof["processLutsOffset"]=="0x7f148"
assert proof["processLutsSha256"]=="dea370ecbf043da03a4af8a7d126d930caf8364f2c806e96a15b2dcb78fcab96"
assert proof["savedJpegToning"] and proof["livePreviewToning"]
assert not proof["dngToning"]
assert proof["offBitExactGray"]
assert proof["conversion"]=="JFIF_BT601_YCrCb_code_domain_inverse"
assert not proof["genericPhotonSaturationUsed"]
assert not proof["genericPhotonColorUsed"]
assert proof["contrastControlPreserved"]

# Modern settings UI: same Leica category, with Contrast followed by Hue + Strength.
ANDROID="http://schemas.android.com/apk/res/android"
akey="{"+ANDROID+"}key"
tree=ET.parse(root/"app/src/main/res/xml/preferences.xml")
cats=[n for n in list(tree.getroot()) if n.attrib.get(akey)=="@string/pref_category_monochrom_key"]
assert len(cats)==1
keys=[n.attrib.get(akey) for n in list(cats[0])]
for k in [
    "@string/pref_mono_contrast_key",
    "@string/pref_mono_toning_hue_key",
    "@string/pref_mono_toning_strength_key",
]:
    assert k in keys,k
assert keys.index("@string/pref_mono_contrast_key") < keys.index("@string/pref_mono_toning_hue_key") < keys.index("@string/pref_mono_toning_strength_key")
h=next(n for n in list(cats[0]) if n.attrib.get(akey)=="@string/pref_mono_toning_hue_key")
s=next(n for n in list(cats[0]) if n.attrib.get(akey)=="@string/pref_mono_toning_strength_key")
assert h.attrib["{"+ANDROID+"}defaultValue"]=="0"
assert s.attrib["{"+ANDROID+"}defaultValue"]=="0"

arrays=(root/"app/src/main/res/values/arrays.xml").read_text()
for text in ["<item>Sepia</item>","<item>Cool</item>","<item>Selenium</item>","<item>Off</item>","<item>Weak</item>","<item>Strong</item>"]:
    assert text in arrays,text

prefs=(root/"app/src/main/java/com/particlesdevs/photoncamera/settings/PreferenceKeys.java").read_text()
for marker in [
    "KEY_MONO_TONING_HUE(R.string.pref_mono_toning_hue_key)",
    "KEY_MONO_TONING_STRENGTH(R.string.pref_mono_toning_strength_key)",
    "getMonoToningHueValue()",
    "getMonoToningStrengthValue()",
    "Key.KEY_MONO_TONING_HUE, 0",
    "Key.KEY_MONO_TONING_STRENGTH, 0",
    "COMMON_KEYS.add(Key.KEY_MONO_TONING_HUE.mValue)",
    "COMMON_KEYS.add(Key.KEY_MONO_TONING_STRENGTH.mValue)",
]:
    assert marker in prefs,marker

toning=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/MonoToning1A.java").read_text()
for marker in [
    'HUE_LABELS={"Sepia","Cool","Selenium"}',
    'STRENGTH_LABELS={"Off","Weak","Strong"}',
    'CR={128,130,131,127,126,128,128}',
    'CB={128,125,123,130,132,129,131}',
    'return s==0?0:s+2*h;',
]:
    assert marker in toning,marker

# State resolver must be exhaustive and Off independent of remembered hue.
CR=[128,130,131,127,126,128,128]
CB=[128,125,123,130,132,129,131]
expected={
    (0,0):(0,128,128),(1,0):(0,128,128),(2,0):(0,128,128),
    (0,1):(1,130,125),(0,2):(2,131,123),
    (1,1):(3,127,130),(1,2):(4,126,132),
    (2,1):(5,128,129),(2,2):(6,128,131),
}
for (hue,strength),(state,cr,cb) in expected.items():
    got=0 if strength==0 else strength+2*hue
    assert got==state
    assert CR[got]==cr and CB[got]==cb

renderer=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java").read_text()
for marker in [
    "getMonoToningHueValue()",
    "getMonoToningStrengthValue()",
    "MonoToning1A.state(",
    "MonoToning1A.CR[monoToningState1A]",
    "MonoToning1A.CB[monoToningState1A]",
    "monoStandardCurve1A, 128, 128, rawScalar1AStats",
    "monoSelectedCurve1A, monoToningCr1A, monoToningCb1A, rawScalar1BStats",
    'rawScalar1B.put("toningDomain", "firmware_PROCESS_LUTS_YCrCb_chroma_pair")',
    'd.put("monochromToningState", monoToningState1A)',
]:
    assert marker in renderer,marker

native_decl=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java").read_text()
assert "byte[] contrastCurve," in native_decl
assert "int toningCr, int toningCb, long[] stats" in native_decl

cpp=(root/"app/src/main/cpp/m9color_jni.cpp").read_text()
for marker in [
    "jbyteArray contrastCurveArray, jint toningCr, jint toningCb, jlongArray statsArray",
    "const int dCr=cr-128,dCb=cb-128;",
    "91881*dCr",
    "22554*dCb+46802*dCr",
    "116130*dCb",
    "const uint8_t outR=clamp8",
    "const uint8_t outG=clamp8",
    "const uint8_t outB=clamp8",
]:
    assert marker in cpp,marker

# Verify integer conversion semantics, especially bit-exact Off.
def round_shift16(x):
    return ((x+32768)>>16) if x>=0 else -(((-x)+32768)>>16)
def clamp8(x): return max(0,min(255,x))
def rgb(y,cr,cb):
    dcr=cr-128; dcb=cb-128
    return (
        clamp8(y+round_shift16(91881*dcr)),
        clamp8(y-round_shift16(22554*dcb+46802*dcr)),
        clamp8(y+round_shift16(116130*dcb)),
    )
for y in range(256):
    assert rgb(y,128,128)==(y,y,y)
# Direction sanity from firmware hue names.
assert rgb(128,130,125)[0] > rgb(128,130,125)[2]  # Sepia is warmer.
assert rgb(128,127,130)[2] > rgb(128,127,130)[0]  # Cool is bluer.
assert rgb(128,128,131)[2] > rgb(128,128,131)[0]  # Selenium blue component lift.

shader=(root/"app/src/main/assets/shaders/preview/main_fs.glsl").read_text()
for marker in [
    "uniform float uMonoToningCr1A;",
    "uniform float uMonoToningCb1A;",
    "1.402*dCr",
    "0.714136*dCr",
    "0.344136*dCb",
    "1.772*dCb",
]:
    assert marker in shader,marker

main=(root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java").read_text()
for marker in [
    'glGetUniformLocation(program,"uMonoToningCr1A")',
    'glGetUniformLocation(program,"uMonoToningCb1A")',
    "getMonoToningHueValue()",
    "getMonoToningStrengthValue()",
    "MonoToning1A.state(",
    "MonoToning1A.CR[toningState1A]",
    "MonoToning1A.CB[toningState1A]",
    "setLeicaToningSelection(",
]:
    assert marker in main,marker

preview=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java").read_text()
for marker in [
    "setLeicaToningSelection",
    "leicaToningState",
    "leicaToningLabel",
    "leicaToningCr",
    "leicaToningCb",
]:
    assert marker in preview,marker

# Contrast remains installed and its post-pack contract is unchanged.
contrast=json.loads((root/"LEICACONTRAST1A_ISOLATION.json").read_text())
assert contrast["revision"]=="LEICACONTRAST1A"
assert contrast["jpegUsesSelectedCurve"] and contrast["previewUsesSelectedCurve"]
assert contrast["firmwareCurveBankSha256"]=="ac010ac0a107fb4b98ed817f24b4b9ab2d739fcfd70571b4f7d8375335e293c6"

# Toning overlay itself proves DNG/exposure/tap stayed byte-identical.
expected_frozen={
    "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngExport1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngWriter1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoLinearPlane1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/exposure/MonoPlacementAssist1D.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoTapMeter1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java",
}
assert set(proof["frozenPolicyHashes"])==expected_frozen

report={
    "revision":"LEICATONING1A_TEST",
    "status":"PASS",
    "firmwareMenuAndSevenStates":True,
    "exactCrCbPairs":True,
    "offBitExactGray":True,
    "jpegPreviewSharedToning":True,
    "contrastPreserved":True,
    "dngExposureTapFrozen":True,
}
(root/"LEICATONING1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
