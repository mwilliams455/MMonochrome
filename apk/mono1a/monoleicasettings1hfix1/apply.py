#!/usr/bin/env python3
"""LEICABRACKET1B_ADMISSIONFIX1: wait for durable monochrome-DNG admission between bracket frames."""
from pathlib import Path
import hashlib,json,re,sys

if len(sys.argv)!=2: raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
export=J/"m9/export/MonoDngExport1A.java"
capture=J/"capture/CaptureController.java"
fragment=J/"ui/camera/CameraFragment.java"
gradle=root/"app/build.gradle"
for p in [export,capture,fragment,gradle]:
    if not p.is_file():raise SystemExit("LEICABRACKET1B missing "+str(p))
for receipt in ["LEICABRACKET1A_ISOLATION.json","LEICAEV1A_ISOLATION.json"]:
    if not (root/receipt).is_file():raise SystemExit("LEICABRACKET1B missing parent receipt "+receipt)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1:raise SystemExit(f"LEICABRACKET1B {label} anchor count={n}")
    return s.replace(a,b,1)

# Pixel/render contracts frozen. MonoDngExport transport is allowed to gain a read-only admission query.
frozen=[
 J/"m9/render/M9R35Renderer.java",J/"m9/render/M9NativeColorCore.java",
 J/"m9/export/MonoDngWriter1A.java",J/"m9/export/MonoLinearPlane1A.java",
 root/"app/src/main/cpp/m9color_jni.cpp",root/"app/src/main/assets/shaders/preview/main_fs.glsl",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
export_before=sha(export)

# Non-notifying cached admission probe for internal bracket continuation.
s=export.read_text()
anchor='''    public static boolean admitCapture1B() {
        startRecovery();MonoDngSpool1B s=store;
'''
replacement='''    public static boolean canAdmitCapture1B() {
        startRecovery();MonoDngSpool1B s=store;
        return s!=null && startupError.isEmpty() && s.admission().allowed;
    }
    public static boolean admitCapture1B() {
        startRecovery();MonoDngSpool1B s=store;
'''
s=one(s,anchor,replacement,"export non-notifying admission query")
export.write_text(s)

s=capture.read_text()
# Never mark a bracket frame "awaiting completion" until the capture has passed the
# durable-DNG admission guard. The 1A placement happened before that guard, so a
# rejected internal frame deadlocked the series after frame 1.
early='''    public void takePicture() {
        if(monoBracketActive1H) {
            synchronized(this){monoBracketAwaitingFinish1H=true;}
        }
        if (mPreviewRequestBuilder == null || mCaptureSession == null) {
'''
s=one(s,early,'''    public void takePicture() {
        if (mPreviewRequestBuilder == null || mCaptureSession == null) {
''',"remove premature awaiting marker")
admission='''        // MONOOUTPUT1B_ADMISSION: keep bounded durable storage; do not silently drop derived RAW.
        if (!com.particlesdevs.photoncamera.m9.export.MonoDngExport1A.admitCapture1B()) return;
'''
s=one(s,admission,admission+'''        if(monoBracketActive1H) {
            synchronized(this){monoBracketAwaitingFinish1H=true;}
        }
''',"mark awaiting only after admission")

field='''    private String monoBracketCamera1H="";
'''
s=one(s,field,field+'''    private int monoBracketAdmissionRetries1H;
    private static final int MONO_BRACKET_ADMISSION_RETRY_MS_1H=250;
    private static final int MONO_BRACKET_ADMISSION_MAX_RETRIES_1H=80;
''',"bracket admission fields")

method_anchor='''    public synchronized void abortMonoBracket1H(){clearMonoBracket1H("aborted");}

'''
retry_methods=r'''    /**
     * The derived monochrome DNG is staged/published asynchronously after JPEG processing.
     * A bracket must not submit its next physical exposure until the durable exporter
     * admits another full-resolution job. Poll the cached admission state without toasts.
     */
    public void scheduleMonoBracketNextAfterAdmission1H() {
        synchronized(this){monoBracketAdmissionRetries1H=0;}
        if(mBackgroundHandler!=null)
            mBackgroundHandler.postDelayed(this::pollMonoBracketAdmission1H,MONO_BRACKET_ADMISSION_RETRY_MS_1H);
    }

    private void pollMonoBracketAdmission1H() {
        synchronized(this){if(!monoBracketActive1H)return;}
        if(com.particlesdevs.photoncamera.m9.export.MonoDngExport1A.canAdmitCapture1B()) {
            activity.runOnUiThread(() -> {
                synchronized(CaptureController.this){if(!monoBracketActive1H)return;}
                takePicture();
            });
            return;
        }
        int retry;
        synchronized(this){retry=++monoBracketAdmissionRetries1H;}
        if(retry<MONO_BRACKET_ADMISSION_MAX_RETRIES_1H && mBackgroundHandler!=null) {
            mBackgroundHandler.postDelayed(this::pollMonoBracketAdmission1H,MONO_BRACKET_ADMISSION_RETRY_MS_1H);
        } else {
            abortMonoBracket1H();
            cameraEventsListener.onProcessingError("Bracket sequence stopped while waiting for monochrome DNG storage.");
        }
    }

'''+method_anchor
s=one(s,method_anchor,retry_methods,"bracket admission retry methods")
capture.write_text(s)

s=fragment.read_text()
old='''            if(captureController!=null && captureController.advanceMonoBracketAfterProcessing1H()) {
                // Separate files, never stacking: wait until the preceding JPEG/DNG job has
                // completed, then trigger the next physical shutter request.
                textureView.postDelayed(() -> {
                    if(captureController!=null && captureController.isMonoBracketActive1H())
                        captureController.takePicture();
                },120);
                return;
            }
'''
new='''            if(captureController!=null && captureController.advanceMonoBracketAfterProcessing1H()) {
                // JPEG processing can finish before the derived monochrome DNG's durable
                // publication queue accepts another full-resolution job. Wait on that
                // admission boundary instead of firing the next shutter after a fixed delay.
                captureController.scheduleMonoBracketNextAfterAdmission1H();
                return;
            }
'''
s=one(s,old,new,"replace fixed-delay continuation with admission wait")
fragment.write_text(s)

g=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m:raise SystemExit("LEICABRACKET1B versionName missing")
if "leicabracket1b-admissionfix1" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-leicabracket1b-admissionfix1"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    raise SystemExit("LEICABRACKET1B changed frozen photographic files")
proof={
 "revision":"LEICABRACKET1B_ADMISSIONFIX1",
 "rootCause":"frame_2_takePicture_was_called_before_MONOOUTPUT1B_durable_DNG_admission_reopened",
 "symptom":"one_JPEG_plus_one_DNG_only",
 "fix":"poll_non_notifying_DNG_admission_then_submit_next_physical_bracket_frame",
 "prematureAwaitingMarkerRemoved":True,
 "awaitingMarkerAfterAdmission":True,
 "fixed120msDelayRemoved":True,
 "pollIntervalMs":250,
 "maxWaitMs":20000,
 "noRepeatedAdmissionToasts":True,
 "separateFrames":True,
 "hdrMerge":False,
 "stacking":False,
 "rendererChanged":False,
 "dngPixelMathChanged":False,
 "dngExporterBeforeSha256":export_before,
 "dngExporterAfterSha256":sha(export),
 "frozenPhotographicHashes":after,
}
(root/"LEICABRACKET1B_ADMISSIONFIX1_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
