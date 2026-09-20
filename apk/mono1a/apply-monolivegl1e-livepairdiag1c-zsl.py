#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply-monolivegl1e-livepairdiag1c-zsl.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
cc = root / "app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java"
cf = root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/CameraFragment.java"
for p in (cc, cf):
    if not p.exists():
        raise SystemExit("missing assembled source: " + str(p))

c = cc.read_text()
f = cf.read_text()
if "MONOLIVEGL1E_LIVEPAIRDIAG1A" not in c:
    raise SystemExit("GL1E prerequisite missing from CaptureController")
if "MONOLIVEGL1E_LIVEPAIRDIAG1C_ZSL" in c:
    raise SystemExit("GL1E 1C already applied")

# In ZSL/Motion, the displayed frame and captured frame come from the same
# preview stream. Mirror that actual preview state into the diagnostic cache.
old = '''                if (captureController.isZslMode()) {
                    textureView.setMonoExposureScale1A(1.0f);
                } else {
'''
new = '''                if (captureController.isZslMode()) {
                    textureView.setMonoExposureScale1A(1.0f);
                    // MONOLIVEGL1E_LIVEPAIRDIAG1C_ZSL
                    Long actualExposureNs1E = result.get(CaptureResult.SENSOR_EXPOSURE_TIME);
                    Integer actualIso1E = result.get(CaptureResult.SENSOR_SENSITIVITY);
                    Long sensorTs1E = result.get(CaptureResult.SENSOR_TIMESTAMP);
                    Integer aeState1E = result.get(CaptureResult.CONTROL_AE_STATE);
                    Integer awbState1E = result.get(CaptureResult.CONTROL_AWB_STATE);
                    Integer afState1E = result.get(CaptureResult.CONTROL_AF_STATE);
                    if (actualExposureNs1E != null && actualExposureNs1E > 0L
                            && actualIso1E != null && actualIso1E > 0) {
                        captureController.updateMonoLivePairPreview1E(
                                actualIso1E, actualExposureNs1E,
                                actualIso1E, actualExposureNs1E, 1.0,
                                sensorTs1E != null ? sensorTs1E : -1L,
                                aeState1E != null ? aeState1E : -1,
                                awbState1E != null ? awbState1E : -1,
                                afState1E != null ? afState1E : -1);
                    }
                } else {
'''
if f.count(old) != 1:
    raise SystemExit("CameraFragment ZSL preview anchor mismatch")
f = f.replace(old, new, 1)

# Add passive ZSL sidecar emission inside triggerZslCapture. There is no new
# Camera2 still request in this route; the selected RAW frames are preview/ZSL
# frames, so mPreviewCaptureRequest/result are the correct authority pair.
anchor = '''        mZslCapturing = true;
        burst = false;

        int frameCount = FrameNumberSelector.getFrames();
'''
insert = '''        mZslCapturing = true;
        burst = false;

        // MONOLIVEGL1E_LIVEPAIRDIAG1C_ZSL
        // Motion mode is ZSL: capture uses buffered preview RAW frames and
        // therefore never reaches the non-ZSL capture callback below.
        final long monoZslShutterElapsedNs1E = SystemClock.elapsedRealtimeNanos();
        final long monoZslShutterWallMs1E = System.currentTimeMillis();
        final IsoExpoSelector.ExpoPair monoZslSelector1E =
                IsoExpoSelector.GenerateExpoPair(-1, this);
        final int monoZslSelectorIso1E = monoZslSelector1E != null
                ? monoZslSelector1E.iso : -1;
        final long monoZslSelectorExposureNs1E = monoZslSelector1E != null
                ? monoZslSelector1E.exposure : -1L;
        final CaptureResult monoZslResult1E = mPreviewCaptureResult;
        final CaptureRequest monoZslRequest1E = mPreviewCaptureRequest;
        final int monoZslRotation1E =
                PhotonCamera.getGravity().getCameraRotation(mSensorOrientation);
        final String monoZslPhysicalId1E = physicalID;
        final org.json.JSONObject monoZslSnapshot1E =
                MonoLivePairDiagnostics1E.capturePreviewSnapshot(
                        monoZslShutterElapsedNs1E, monoZslShutterWallMs1E,
                        monoLivePairIntendedIso1E, monoLivePairIntendedExposureNs1E,
                        monoZslSelectorIso1E, monoZslSelectorExposureNs1E,
                        monoLivePairPreviewIso1E, monoLivePairPreviewExposureNs1E,
                        1.0, monoLivePairPreviewSensorTimestampNs1E,
                        monoLivePairPreviewUpdatedElapsedNs1E,
                        monoLivePairPreviewAeState1E, monoLivePairPreviewAwbState1E,
                        monoLivePairPreviewAfState1E,
                        monoZslPhysicalId1E, monoZslRotation1E);

        int frameCount = FrameNumberSelector.getFrames();
'''
if c.count(anchor) != 1:
    raise SystemExit("triggerZslCapture entry anchor mismatch")
c = c.replace(anchor, insert, 1)

anchor2 = '''        cameraEventsListener.onCaptureSequenceCompleted(null);

        long[] frameTimestamps = new long[actualCount];
'''
insert2 = '''        cameraEventsListener.onCaptureSequenceCompleted(null);

        // ZSL has no dedicated still CaptureCallback. Persist against the
        // exact preview request/result that supplied the buffered RAW frames.
        if (monoZslRequest1E != null && monoZslResult1E != null) {
            processExecutor.execute(() -> MonoLivePairDiagnostics1E.writeCompleted(
                    monoZslSnapshot1E, monoZslRequest1E, monoZslResult1E,
                    monoZslPhysicalId1E, monoZslRotation1E));
        } else {
            Log.w(TAG, "MONOLIVEGL1E ZSL sidecar skipped: preview request/result unavailable");
        }

        long[] frameTimestamps = new long[actualCount];
'''
if c.count(anchor2) != 1:
    raise SystemExit("triggerZslCapture completion anchor mismatch")
c = c.replace(anchor2, insert2, 1)

dpath = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoLivePairDiagnostics1E.java"
d = dpath.read_text()
old_sig = '''    public static void writeCompleted(JSONObject preview, CaptureRequest request,
                                      TotalCaptureResult result, String physicalCameraId,
                                      int cameraRotationDegrees) {'''
new_sig = '''    public static void writeCompleted(JSONObject preview, CaptureRequest request,
                                      CaptureResult result, String physicalCameraId,
                                      int cameraRotationDegrees) {'''
if d.count(old_sig) != 1:
    raise SystemExit("GL1E diagnostic writer signature anchor mismatch")
d = d.replace(old_sig, new_sig, 1)

cc.write_text(c)
cf.write_text(f)
dpath.write_text(d)

print("MONOLIVEGL1E_LIVEPAIRDIAG1C_ZSL applied")
print(" - Motion/ZSL mirrors actual preview ISO/shutter with scale 1")
print(" - ZSL shutter snapshot is armed before ring-buffer selection")
print(" - sidecar completes from exact preview request/result authority")
print(" - non-ZSL diagnostic path unchanged")
print(" - preview shader and still renderer untouched")
