#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply-manualiso-preserve1c.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
param = root / 'app/src/main/java/com/particlesdevs/photoncamera/manual/ParamController.java'
iso_expo = root / 'app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java'
for p in (param, iso_expo):
    if not p.exists():
        raise SystemExit('missing ' + str(p))

def one(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: anchor count={n}, expected 1')
    return s.replace(old, new, 1)

# MANUALISO1C / SHUTTERLOCK1A
# Device evidence from the controlled tripod series:
#   UI shutter was held at 1/64 for ISO 3200 -> 6400 -> 12800.
#   ISO 3200 and 6400 capture requests both retained 15,624,999 ns.
#   A later ISO-12800 attempt reported 22,097,086 ns in the capture result.
#
# The concrete Photon bug closed here is in ParamController.setISO(): it receives the
# ManualParamModel's currentExposure but ignores it and writes mPreviewExposureTime.
# Changing ISO can therefore contaminate the preview builder with a drifting preview
# shutter even while the manual model/UI remains locked. This patch makes the manual
# shutter authoritative whenever it is selected and adds final physical-pair traces.
# Rendering is untouched.

p = param.read_text()
if 'MANUALISO1C_SHUTTERLOCK_SETISO' in p:
    raise SystemExit('MANUALISO1C already applied to ParamController')

old = '''    public void setShutter(long shutterNs, int currentISO) {\n        CaptureRequest.Builder builder = captureController.mPreviewRequestBuilder;\n'''
new = '''    public void setShutter(long shutterNs, int currentISO) {\n        // MANUALISO1C_TRACE_SHUTTER: preserve and expose the exact manual shutter request.\n        Log.i(TAG, "MANUALISO1C setShutter shutterNs=" + shutterNs + " currentISO=" + currentISO);\n        CaptureRequest.Builder builder = captureController.mPreviewRequestBuilder;\n'''
p = one(p, old, new, 'ParamController shutter trace')

old = '''        } else {\n            builder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_OFF);\n            builder.set(CaptureRequest.SENSOR_EXPOSURE_TIME, Math.min(shutterNs, ExposureIndex.sec / 5));\n            builder.set(CaptureRequest.SENSOR_SENSITIVITY, captureController.mPreviewIso);\n        }\n        captureController.rebuildPreviewBuilder();\n    }\n\n    public void setISO(int isoVal, double currentExposure) {\n'''
new = '''        } else {\n            builder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_OFF);\n            long exposureToApply = Math.min(shutterNs, ExposureIndex.sec / 5);\n            int isoToKeep = currentISO > ManualParamModel.ISO_AUTO\n                    ? currentISO\n                    : captureController.mPreviewIso;\n            // MANUALISO1C_SHUTTERLOCK_SETSHUTTER: shutter changes must not replace an\n            // explicit manual ISO with the latest Camera2 preview-result ISO.\n            builder.set(CaptureRequest.SENSOR_EXPOSURE_TIME, exposureToApply);\n            builder.set(CaptureRequest.SENSOR_SENSITIVITY, isoToKeep);\n            Log.i(TAG, "MANUALISO1C setShutter appliedExposureNs=" + exposureToApply\n                    + " appliedIso=" + isoToKeep\n                    + " previewIso=" + captureController.mPreviewIso);\n        }\n        captureController.rebuildPreviewBuilder();\n    }\n\n    public void setISO(int isoVal, double currentExposure) {\n'''
p = one(p, old, new, 'ParamController setShutter manual ISO preservation')

old = '''        } else {\n            builder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_OFF);\n            builder.set(CaptureRequest.SENSOR_SENSITIVITY, isoVal);\n            builder.set(CaptureRequest.SENSOR_EXPOSURE_TIME, captureController.mPreviewExposureTime);\n        }\n        captureController.rebuildPreviewBuilder();\n    }\n'''
new = '''        } else {\n            builder.set(CaptureRequest.CONTROL_AE_MODE, CaptureRequest.CONTROL_AE_MODE_OFF);\n            builder.set(CaptureRequest.SENSOR_SENSITIVITY, isoVal);\n            // MANUALISO1C_SHUTTERLOCK_SETISO: ISO changes must not replace an explicit\n            // manual shutter with the latest Camera2 preview-result shutter.\n            long exposureToKeep = currentExposure > ManualParamModel.EXPOSURE_AUTO\n                    ? (long) currentExposure\n                    : captureController.mPreviewExposureTime;\n            builder.set(CaptureRequest.SENSOR_EXPOSURE_TIME, exposureToKeep);\n            Log.i(TAG, "MANUALISO1C setISO physicalIso=" + isoVal\n                    + " manualExposureNs=" + (long) currentExposure\n                    + " previewExposureNs=" + captureController.mPreviewExposureTime\n                    + " appliedExposureNs=" + exposureToKeep);\n        }\n        captureController.rebuildPreviewBuilder();\n    }\n'''
p = one(p, old, new, 'ParamController setISO manual shutter preservation')

old = '''    public void setupPreview() {\n        if (manualParamModel != null) {\n            if(ISO != -1)\n                setISO(ISO, manualParamModel.getCurrentExposureValue());\n            if(EV != 0)\n                setEV(EV);\n            if(SHUTTER != -1)\n                setShutter(SHUTTER, ISO);\n            if(FOCUS != -1)\n                setFocus(FOCUS);\n        }\n    }\n\n    public double getCurrentExposureValue() {\n'''
new = '''    public void setupPreview() {\n        if (manualParamModel != null) {\n            // MANUALISO1C_SHUTTERLOCK_SETUP: ManualParamModel is the authoritative UI state.\n            // Reapply the pair atomically enough for preview purposes: ISO first while keeping\n            // the model shutter, then shutter again so Camera2 cannot leave a stale preview value.\n            double modelISO = manualParamModel.getCurrentISOValue();\n            double modelExposure = manualParamModel.getCurrentExposureValue();\n            if (modelISO != ManualParamModel.ISO_AUTO)\n                setISO((int) modelISO, modelExposure);\n            if (modelExposure != ManualParamModel.EXPOSURE_AUTO)\n                setShutter((long) modelExposure, (int) modelISO);\n            if(EV != 0)\n                setEV(EV);\n            if(FOCUS != -1)\n                setFocus(FOCUS);\n            Log.i(TAG, "MANUALISO1C setupPreview modelISO=" + modelISO\n                    + " modelExposureNs=" + (long) modelExposure\n                    + " latchedISO=" + ISO + " latchedShutterNs=" + SHUTTER);\n        }\n    }\n\n    public long getLatchedManualShutterNs() {\n        return SHUTTER > ManualParamModel.EXPOSURE_AUTO ? SHUTTER : -1L;\n    }\n\n    public double getCurrentExposureValue() {\n'''
p = one(p, old, new, 'ParamController setupPreview model authority')
param.write_text(p)

e = iso_expo.read_text()
if 'MANUALISO1C_TRACE_FINAL_PHYSICAL' in e:
    raise SystemExit('MANUALISO1C already applied to IsoExpoSelector')
old = '''        pair.denormalizeSystem();\n        if (M9Config.isCaptureTest()) M9ExposureDiagnostics.recordFinalSystem(pair.iso, pair.exposure);\n        return pair;\n    }\n\n    public static double getMPY() {\n'''
new = '''        pair.denormalizeSystem();\n        if (M9Config.isCaptureTest()) M9ExposureDiagnostics.recordFinalSystem(pair.iso, pair.exposure);\n        // MANUALISO1C_TRACE_FINAL_PHYSICAL: exact pair written by setExpo() to Camera2.\n        Log.i(TAG, "MANUALISO1C finalPhysical step=" + step\n                + " iso=" + pair.iso\n                + " exposureNs=" + pair.exposure\n                + " manualIso=" + currentManISO\n                + " manualExposureNs=" + (long) currentManExp);\n        return pair;\n    }\n\n    public static double getMPY() {\n'''
e = one(e, old, new, 'IsoExpoSelector final physical trace')
iso_expo.write_text(e)

print('MANUALISO1C SHUTTERLOCK1A applied')
print('  setISO: preserves explicit ManualParamModel shutter')
print('  setShutter: preserves explicit ManualParamModel ISO')
print('  setupPreview: reapplies ISO/shutter from authoritative model state')
print('  allocator: unchanged except final physical-pair trace')
print('  renderer/sharpness/tone: unchanged')
