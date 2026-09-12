#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply-sharpstd1c-isodomain1a.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
R = root / 'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
if not R.exists():
    raise SystemExit('missing ' + str(R))


def one(s, a, b, label):
    n = s.count(a)
    if n != 1:
        raise SystemExit(f'{label}: anchor count={n}, expected 1')
    return s.replace(a, b, 1)

r = R.read_text()
if 'ISODOMAIN1A' in r:
    raise SystemExit('ISODOMAIN1A already applied')
if 'SHARPSTD1A' not in r:
    raise SystemExit('SHARPSTD1A prerequisite missing')
if 'SHARPSTD1B_NORMISO' in r or '_MONO_RAWSCALAR1B_SHARPSTD1A_NORMISO.jpg' in r:
    raise SystemExit('normalized-ISO A/B overlay must not be present on physical-ISO resolved branch')

# M9 rule carried forward deliberately:
# - Photon may use its ISO-100-normalized domain internally for exposure calculations.
# - Camera2 SENSOR_SENSITIVITY is the physical capture ISO and is the only ISO domain
#   allowed to cross into Leica camera-behaviour schedules such as Monochrom sharpness.
a = '''            Integer sharpCaptureIsoObj = nativeCaptureResult != null\n                    ? nativeCaptureResult.get(CaptureResult.SENSOR_SENSITIVITY) : null;\n            final int sharpCaptureIso = sharpCaptureIsoObj != null && sharpCaptureIsoObj > 0\n                    ? sharpCaptureIsoObj : 320;\n'''
b = '''            // ISODOMAIN1A: preserve Photon's ISO-100 normalization internally, but use\n            // immutable physical Camera2 sensitivity for Leica camera-behaviour schedules.\n            Integer sharpPhysicalCaptureIsoObj = nativeCaptureResult != null\n                    ? nativeCaptureResult.get(CaptureResult.SENSOR_SENSITIVITY) : null;\n            final int sharpPhysicalCaptureIso = sharpPhysicalCaptureIsoObj != null && sharpPhysicalCaptureIsoObj > 0\n                    ? sharpPhysicalCaptureIsoObj : 320;\n'''
r = one(r, a, b, 'physical ISO source rename')

r = one(
    r,
    '                    nativeShading.representationScale, sharpCaptureIso, rawScalar1BSharpStdStats);',
    '                    nativeShading.representationScale, sharpPhysicalCaptureIso, rawScalar1BSharpStdStats);',
    'native sharpness physical ISO argument')

a = '''            if (!rawScalar1BSharpStdOk) {\n                if (!rawScalar1BSharpStdBitmap.isRecycled()) rawScalar1BSharpStdBitmap.recycle();\n                throw new IllegalStateException("MONO1A RAWSCALAR1B SHARPSTD1A native render failed");\n            }\n'''
b = '''            if (!rawScalar1BSharpStdOk) {\n                if (!rawScalar1BSharpStdBitmap.isRecycled()) rawScalar1BSharpStdBitmap.recycle();\n                throw new IllegalStateException("MONO1A RAWSCALAR1B SHARPSTD1A native render failed");\n            }\n            if (rawScalar1BSharpStdStats == null || rawScalar1BSharpStdStats.length < 8\n                    || rawScalar1BSharpStdStats[7] != sharpPhysicalCaptureIso) {\n                if (!rawScalar1BSharpStdBitmap.isRecycled()) rawScalar1BSharpStdBitmap.recycle();\n                throw new IllegalStateException("ISODOMAIN1A physical ISO invariant failed");\n            }\n'''
r = one(r, a, b, 'physical ISO runtime invariant')

a = '''                sharpStd1A.put("isoBridgePolicy", "nearest_Leica_physical_ISO_slot_in_log2_EV_clamped_320_10000_not_firmware_claim");\n'''
b = '''                sharpStd1A.put("isoBridgePolicy", "physical_Camera2_SENSOR_SENSITIVITY_only_nearest_Leica_slot_log2_clamped_320_10000");\n                sharpStd1A.put("isoDomainRevision", "ISODOMAIN1A");\n                sharpStd1A.put("cameraBehaviorIsoSource", "CaptureResult.SENSOR_SENSITIVITY_physical");\n                sharpStd1A.put("photonIso100NormalizationRole", "internal_exposure_math_only");\n                sharpStd1A.put("photonNormalizedIsoUsedForLeicaSchedule", false);\n                sharpStd1A.put("hardwareBoundaryPolicy", "Photon_normalized_internal_Camera2_request_result_physical");\n'''
r = one(r, a, b, 'ISO domain diagnostics')

r = one(
    r,
    '                d.put("source1Revision", "MONO1A_RAWSCALAR1B_PROMOTED1A_SHARPSTD1A_AB");',
    '                d.put("source1Revision", "MONO1A_RAWSCALAR1B_PROMOTED1A_SHARPSTD1A_ISODOMAIN1A");',
    'ISO domain source revision')

R.write_text(r)
print('Applied SHARPSTD1C ISODOMAIN1A: Leica sharpness is locked to physical Camera2 ISO; Photon normalized ISO remains exposure-internal only.')
