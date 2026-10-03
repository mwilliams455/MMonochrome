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

# The exact firmware-derived bank is deliberately absent from Git/source builds.
bank_path = root / "app/src/main/assets/mono/mono_contrast_curves.bin"
assert not bank_path.exists(), "firmware-derived Contrast bank must be post-packed, not stored in Git"
meta = (root / "app/src/main/java/com/particlesdevs/photoncamera/m9/render/MonoContrastCurves1A.java").read_text()
for marker in [
    'BANK_SHA256 = "ac010ac0a107fb4b98ed817f24b4b9ab2d739fcfd70571b4f7d8375335e293c6"',
    '"b836ab85030a67633bbd3d0b4f7cc7b238e288b33f8b30ef41c51339538f9a94"',
    '"b76e1faf8016b6667415e4d1b7b8c12853763dacc764ec1fa4f7371cd08e7773"',
    '"7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752"',
    '"68a8ac917fa13bb6ca030a436a42b8fd588561e0fc2ca032470d27ea36432c97"',
    '"d26670886bdbbaa2e61fe0696d523b2e8dedd8476b75301bbd3c9049106671fb"',
    'ASSET = "mono/mono_contrast_curves.bin"',
    "loadCurve(int selector)",
]:
    assert marker in meta, marker

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
    "monoStandardCurve1A, rawScalar1AStats",
    "monoSelectedCurve1A, rawScalar1BStats",
    'rawScalar1B.put("contrastEnum", monoContrast1A)',
    'd.put("monochromContrastCurveSha256", MonoContrastCurves1A.SHA256[monoContrast1A])',
]:
    assert marker in r, marker

n=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java").read_text()
assert "double representationScale, byte[] contrastCurve," in n

c=(root/"app/src/main/cpp/m9color_jni.cpp").read_text()
for marker in [
    "jbyteArray contrastCurveArray, jlongArray statsArray",
    "MONO1A Contrast curve must be 2048 bytes",
    "GetByteArrayRegion(contrastCurveArray,0,2048",
    "const uint8_t yy=contrastCurve[static_cast<size_t>(idx)]",
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
    "MonoContrastCurves1A.ASSET",
    "getMonoContrastValue()",
    "MonoContrastCurves1A.BANK_SHA256",
    "MonoContrastCurves1A.SHA256[selectedContrast1A]",
]:
    assert marker in m, marker

# DNG, exposure-placement and tap-meter code are snapshotted before the
# Contrast overlay and proven byte-identical afterward by apply.py.
assert proof["dngExposureTapFilesByteIdentical"]
expected_frozen = {
    "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngExport1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngWriter1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoLinearPlane1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/exposure/MonoPlacementAssist1D.java",
    "app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoTapMeter1A.java",
    "app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java",
}
assert set(proof["frozenPolicyHashes"]) == expected_frozen

report={
    "revision":"LEICACONTRAST1A_TEST",
    "status":"PASS",
    "fiveFirmwareCurvesMetadata":True,
    "curveBankPostPackRequired":True,
    "standardIsCurve02":True,
    "jpegAndPreviewShareSelection":True,
    "dngAndExposureFrozen":True,
}
(root/"LEICACONTRAST1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
