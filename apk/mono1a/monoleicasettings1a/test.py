#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys
import xml.etree.ElementTree as ET

if len(sys.argv) != 2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root = Path(sys.argv[1]).resolve()
proof = json.loads((root / "LEICACONTRAST1A_ISOLATION.json").read_text())
assert proof["revision"] == "LEICACONTRAST1A"
assert proof["menu"] == ["Low","Medium low","Standard","Medium high","High"]
assert proof["menuEnum"] == [0,1,2,3,4]
assert proof["default"] == 2
assert proof["processContrastMode"] == 0
assert proof["jpegUsesSelectedCurve"]
assert proof["previewUsesSelectedCurve"]
assert not proof["dngToneChanged"]
assert not proof["genericPhotonContrastUsed"]
assert not proof["sharpnessChanged"]
assert not proof["toningChanged"]

bank = (root / "app/src/main/assets/mono/mono_contrast_curves.bin").read_bytes()
assert len(bank) == 10240
curves = [bank[i*2048:(i+1)*2048] for i in range(5)]
assert len({hashlib.sha256(x).hexdigest() for x in curves}) == 5
assert hashlib.sha256(curves[2]).hexdigest() == "7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752"
for curve in curves:
    assert all(curve[i] <= curve[i+1] for i in range(2047))

ANDROID="http://schemas.android.com/apk/res/android"
akey="{"+ANDROID+"}key"
tree=ET.parse(root/"app/src/main/res/xml/preferences.xml")
cats=[n for n in list(tree.getroot()) if n.attrib.get(akey)=="@string/pref_category_monochrom_key"]
assert len(cats)==1
items=[n for n in list(cats[0]) if n.attrib.get(akey)=="@string/pref_mono_contrast_key"]
assert len(items)==1
assert items[0].attrib["{"+ANDROID+"}defaultValue"]=="2"

p=(root/"app/src/main/java/com/particlesdevs/photoncamera/settings/PreferenceKeys.java").read_text()
for marker in [
    "KEY_MONO_CONTRAST(R.string.pref_mono_contrast_key)",
    "getMonoContrastValue()",
    "Key.KEY_MONO_CONTRAST, 2",
    "COMMON_KEYS.add(Key.KEY_MONO_CONTRAST.mValue)",
]:
    assert marker in p, marker

r=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java").read_text()
for marker in [
    "getMonoContrastValue()",
    "MonoContrastCurves1A.DEFAULT, rawScalar1AStats",
    "monoContrast1A, rawScalar1BStats",
    'rawScalar1B.put("contrastEnum", monoContrast1A)',
    'd.put("monochromContrastCurveSha256", MonoContrastCurves1A.SHA256[monoContrast1A])',
]:
    assert marker in r, marker

n=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java").read_text()
assert "double representationScale, int contrastSelector," in n

c=(root/"app/src/main/cpp/m9color_jni.cpp").read_text()
for marker in [
    '#include "mm_monochrom_contrast_curves.inc"',
    "jint contrastSelector, jlongArray statsArray",
    "const uint8_t* contrastCurve=MM_MONO_CONTRAST_CURVES[monoContrast];",
    "const uint8_t yy=contrastCurve[idx]",
]:
    assert marker in c, marker

g=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java").read_text()
for marker in [
    "setLeicaContrastSelection",
    "leicaContrastEnum",
    "leicaContrastCurveSha256",
]:
    assert marker in g, marker

m=(root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java").read_text()
for marker in [
    "mono_contrast_curves.bin",
    "getMonoContrastValue()",
    "MonoContrastCurves1A.BANK_SHA256",
    "MonoContrastCurves1A.SHA256[selectedContrast1A]",
]:
    assert marker in m, marker

# DNG and exposure policy must remain byte-identical to the validated modern parent.
frozen=json.loads((Path(__file__).resolve().parents[2]/"upstream1b"/"frozen_monochrome.json").read_text())
must_freeze=[
    "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngExport1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngWriter1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoLinearPlane1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/exposure/MonoPlacementAssist1D.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoTapMeter1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java",
]
for rel in must_freeze:
    got=hashlib.sha256((root/rel).read_bytes()).hexdigest()
    assert got==frozen[rel], (rel,got,frozen[rel])

report={
    "revision":"LEICACONTRAST1A_TEST",
    "status":"PASS",
    "fiveFirmwareCurves":True,
    "standardIsCurve02":True,
    "jpegAndPreviewShareSelection":True,
    "dngAndExposureFrozen":True,
}
(root/"LEICACONTRAST1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
