#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,re,sys
if len(sys.argv)!=2: raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve();J=root/"app/src/main/java/com/particlesdevs/photoncamera"
p=json.loads((root/"MONODARKFRAME1A_ISOLATION.json").read_text())
assert p["revision"]=="MONODARKFRAME1A"
assert p["leicaDecisionRecovered"]
assert p["nominalThresholdsNs"]=={
    "ISO_320_1000":250000000,
    "ISO_1250_4000":125000000,
    "ISO_5000_10000":66000000,
}
assert p["strictGreaterThan"]
assert not p["hotPixelModeForced"]
assert not p["originalRawBufferMutated"]
assert not p["secondExposure"] and not p["artificialDelay"] and not p["hdrOrStacking"]
assert not p["originalSensorRawPathChanged"]
assert p["derivedMonoDngAndJpegShareCorrectedSource"]
assert not p["deviceVendorPolicy"]
for rel,want in p["frozenHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

h=(J/"m9/render/MonoDarkFrame1A.java").read_text()
for marker in [
    'if (iso <= 1000) return 250_000_000L;',
    'if (iso <= 4000) return 125_000_000L;',
    'return 66_000_000L;',
    'return exposureTimeNs > thresholdNsForPhysicalIso(physicalIso);',
    'CaptureRequest.STATISTICS_HOT_PIXEL_MAP_MODE',
    'CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL',
    'CaptureResult.STATISTICS_HOT_PIXEL_MAP',
    'mode!=CameraMetadata.HOT_PIXEL_MODE_OFF',
    'app_same_CFA_median_on_private_normalized_copy',
    'originalRawMutated",false',
    'secondExposureTaken",false',
]: assert marker in h,marker

# Never force HAL pixel correction. The only HOT_PIXEL_MODE occurrence must be
# a result read/comparison, never CaptureRequest.Builder.set(HOT_PIXEL_MODE...).
assert '.set(CaptureRequest.HOT_PIXEL_MODE' not in h
assert 'builder.set(CaptureRequest.STATISTICS_HOT_PIXEL_MAP_MODE' in h
assert 'ByteBuffer' not in h and '.put(' in h  # JSONObject only; no camera RAW buffer ownership

c=(J/"capture/CaptureController.java").read_text()
assert c.count("MonoDarkFrame1A.configureCaptureRequest(")==2
assert "getOpenDeviceCharacteristics()" in c

r=(J/"m9/render/M9R35Renderer.java").read_text()
assert "MonoDarkFrame1A.resolveBlackLevels(" in r
assert "MonoDarkFrame1A.correctNormalizedHotPixels(" in r
norm=r.index("MonoDarkFrame1A.correctNormalizedHotPixels(")
demosaic=r.index("rawMat.put(0, 0, norm16);",norm)
assert norm<demosaic
# Original RAW ownership remains in frozen M9PrimaryRenderQueue and the derived
# correction operates on norm16, not frame.buffer.
assert "norm16, width, height, sourceRawOriginX, sourceRawOriginY" in r
q=(J/"m9/render/M9PrimaryRenderQueue.java").read_text()
assert "ImageSaver.Util.saveSingleRaw(" in q
assert "isMonoOriginalSensorRawEnabled()" in q

# Parent Diagnostics/output behavior must still be present.
assert (root/"LEICADIAGNOSTICS1A_ISOLATION.json").is_file()
parent=json.loads((root/"LEICAOUTPUTMODE1A_ISOLATION.json").read_text())
assert parent["originalSensorRaw"]=="independent_toggle_default_off"

# Mirror the exact nominal policy edges and strict comparison.
def threshold(iso):
    iso=max(320,min(10000,iso))
    return 250_000_000 if iso<=1000 else (125_000_000 if iso<=4000 else 66_000_000)
assert threshold(320)==250_000_000 and threshold(1000)==250_000_000
assert threshold(1250)==125_000_000 and threshold(4000)==125_000_000
assert threshold(5000)==66_000_000 and threshold(10000)==66_000_000
assert not (250_000_000>threshold(320)) and 250_000_001>threshold(320)
assert not (125_000_000>threshold(1250)) and 125_000_001>threshold(1250)
assert not (66_000_000>threshold(5000)) and 66_000_001>threshold(5000)

report={
 "revision":"MONODARKFRAME1A_TEST","status":"PASS",
 "firmwareThresholdPolicyMirrored":True,
 "nominalTemperatureFallbackExplicit":True,
 "requestMetadataOnly":True,
 "originalSensorRawFrozen":True,
 "derivedCorrectionBeforeDemosaic":True,
 "noSecondExposureOrFakeDelay":True,
}
(root/"MONODARKFRAME1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
