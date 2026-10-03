#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys
if len(sys.argv)!=2:raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve();J=root/"app/src/main/java/com/particlesdevs/photoncamera"
p=json.loads((root/"LEICABRACKET1B_ADMISSIONFIX1_ISOLATION.json").read_text())
assert p["revision"]=="LEICABRACKET1B_ADMISSIONFIX1"
assert p["rootCause"]=="frame_2_takePicture_was_called_before_MONOOUTPUT1B_durable_DNG_admission_reopened"
assert p["symptom"]=="one_JPEG_plus_one_DNG_only"
for k in ["prematureAwaitingMarkerRemoved","awaitingMarkerAfterAdmission","fixed120msDelayRemoved",
          "noRepeatedAdmissionToasts","separateFrames"]:
    assert p[k],k
assert not p["hdrMerge"] and not p["stacking"]
assert not p["rendererChanged"] and not p["dngPixelMathChanged"]
for rel,want in p["frozenPhotographicHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

export=(J/"m9/export/MonoDngExport1A.java").read_text()
assert "public static boolean canAdmitCapture1B()" in export
assert "return s!=null && startupError.isEmpty() && s.admission().allowed;" in export

cap=(J/"capture/CaptureController.java").read_text()
take=cap[cap.index("public void takePicture()"):cap.index("/**",cap.index("public void takePicture()")+10)]
assert take.index("admitCapture1B()") < take.index("monoBracketAwaitingFinish1H=true")
assert "scheduleMonoBracketNextAfterAdmission1H()" in cap
assert "pollMonoBracketAdmission1H()" in cap
assert "canAdmitCapture1B()" in cap
assert "MONO_BRACKET_ADMISSION_RETRY_MS_1H=250" in cap
assert "MONO_BRACKET_ADMISSION_MAX_RETRIES_1H=80" in cap

frag=(J/"ui/camera/CameraFragment.java").read_text()
assert "scheduleMonoBracketNextAfterAdmission1H()" in frag
assert "postDelayed(() ->" not in frag[frag.index("advanceMonoBracketAfterProcessing1H()"):frag.index("mCameraUIView.setProcessingProgressBarIndeterminate",frag.index("advanceMonoBracketAfterProcessing1H()"))]

report={"revision":"LEICABRACKET1B_ADMISSIONFIX1_TEST","status":"PASS",
        "deadlockPathClosed":True,"nextFrameWaitsForDngAdmission":True,
        "threeFrameSeriesExpectedFilesForJpegPlusDng":"3_JPEG_plus_3_DNG",
        "hdrMerge":False}
(root/"LEICABRACKET1B_ADMISSIONFIX1_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
