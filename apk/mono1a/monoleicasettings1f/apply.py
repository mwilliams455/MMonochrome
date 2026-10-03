#!/usr/bin/env python3
"""LEICAAELOCK1A: explicit phone UI for first-generation M Monochrom metering memory lock."""
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
layout=root/"app/src/main/res/layout/layout_main_topbar.xml"
strings=root/"app/src/main/res/values/strings.xml"
ui=J/"ui/camera/CameraUIController.java"
capture=J/"capture/CaptureController.java"
plan=J/"m9/exposure/MonoExposurePlan1A.java"
diag=J/"m9/exposure/MonoExposureDiagnostics1A.java"
focus=J/"control/TouchFocus.java"
gradle=root/"app/build.gradle"
drawable=root/"app/src/main/res/drawable/mono_ae_lock_button_1f.xml"
closed=root/"app/src/main/res/drawable/ic_mono_ae_lock_closed_1f.xml"
open_icon=root/"app/src/main/res/drawable/ic_mono_ae_lock_open_1f.xml"

for p in [layout,strings,ui,capture,plan,diag,focus,gradle]:
    if not p.is_file(): raise SystemExit("LEICAAELOCK1A missing "+str(p))
for receipt in ["LEICASLOWEST1A_ISOLATION.json","LEICAAUTOISO1A_ISOLATION.json",
                "LEICASHARPNESS1C_ISOLATION.json","LEICATONING1A_FIX2_SOURCE1D_ISOLATION.json"]:
    if not (root/receipt).is_file(): raise SystemExit("LEICAAELOCK1A missing parent receipt "+receipt)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"LEICAAELOCK1A {label} anchor count={n}")
    return s.replace(a,b,1)
def append_resource(path,fragment):
    s=path.read_text()
    if fragment.splitlines()[0] in s: raise SystemExit("LEICAAELOCK1A resource already present")
    path.write_text(one(s,"</resources>",fragment+"\n</resources>",path.name))

# Exposure/UI only: render, DNG and Leica JPEG settings are frozen.
frozen=[
 J/"m9/render/M9R35Renderer.java",
 J/"m9/render/M9NativeColorCore.java",
 J/"m9/export/MonoDngExport1A.java",
 J/"m9/export/MonoDngWriter1A.java",
 J/"m9/export/MonoLinearPlane1A.java",
 J/"m9/exposure/MonoPlacementAssist1D.java",
 J/"m9/preview/MonoGpuPreview2A.java",
 root/"app/src/main/cpp/m9color_jni.cpp",
 root/"app/src/main/assets/shaders/preview/main_fs.glsl",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}

# ----- top-bar explicit lock state -----
append_resource(strings,
'''    <string name="mono_ae_lock">AE Lock</string>
    <string name="mono_ae_lock_locked">AE-L: LOCKED</string>
    <string name="mono_ae_lock_auto">AE-L: AUTO</string>''')

closed.parent.mkdir(parents=True,exist_ok=True)
closed.write_text('''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="@color/cam_on_surface"
        android:pathData="M7,10V7a5,5 0,0 1,10,0v3h1a2,2 0,0 1,2,2v8a2,2 0,0 1,-2,2H6a2,2 0,0 1,-2,-2v-8a2,2 0,0 1,2,-2h1zM9,10h6V7a3,3 0,0 0,-6,0v3zM6,12v8h12v-8H6z"/>
</vector>
''')
open_icon.write_text('''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="@color/cam_on_surface"
        android:pathData="M15,10V7a3,3 0,0 0,-5.83,-1H7.1A5,5 0,0 1,17,7v3h1a2,2 0,0 1,2,2v8a2,2 0,0 1,-2,2H6a2,2 0,0 1,-2,-2v-8a2,2 0,0 1,2,-2h9zM6,12v8h12v-8H6z"/>
</vector>
''')
drawable.write_text('''<?xml version="1.0" encoding="utf-8"?>
<inset xmlns:android="http://schemas.android.com/apk/res/android"
    android:inset="@dimen/topbar_button_inset">
    <selector>
        <item android:state_selected="true" android:drawable="@drawable/ic_mono_ae_lock_closed_1f"/>
        <item android:drawable="@drawable/ic_mono_ae_lock_open_1f"/>
    </selector>
</inset>
''')

s=layout.read_text()
s=one(s,
'                    app:layout_constraintEnd_toStartOf="@id/flash_button"\n                    app:layout_constraintTop_toTopOf="parent"\n                    tools:visibility="visible"\n                    />\n\n            <com.particlesdevs.photoncamera.ui.camera.views.FlashButton\n',
'                    app:layout_constraintEnd_toStartOf="@id/mono_ae_lock_button"\n                    app:layout_constraintTop_toTopOf="parent"\n                    tools:visibility="visible"\n                    />\n\n            <ImageButton\n'
'                    android:id="@+id/mono_ae_lock_button"\n'
'                    style="@style/Widget.AppCompat.ImageButton"\n'
'                    android:layout_width="0dp"\n'
'                    android:layout_height="wrap_content"\n'
'                    app:layout_constraintDimensionRatio="1:1"\n'
'                    android:background="@drawable/mono_ae_lock_button_1f"\n'
'                    android:foreground="?attr/selectableItemBackgroundBorderless"\n'
'                    android:contentDescription="@string/mono_ae_lock"\n'
'                    android:onClick="@{top_bar_click_listener}"\n'
'                    app:layout_constraintBottom_toBottomOf="parent"\n'
'                    app:layout_constraintStart_toEndOf="@id/grid_toggle_button"\n'
'                    app:layout_constraintEnd_toStartOf="@id/flash_button"\n'
'                    app:layout_constraintTop_toTopOf="parent"\n'
'                    tools:visibility="visible"/>\n\n'
'            <com.particlesdevs.photoncamera.ui.camera.views.FlashButton\n',
"insert AE-L button")
s=one(s,
'                    app:layout_constraintStart_toEndOf="@id/grid_toggle_button"\n                    app:layout_constraintEnd_toStartOf="@id/settings_button"\n',
'                    app:layout_constraintStart_toEndOf="@id/mono_ae_lock_button"\n                    app:layout_constraintEnd_toStartOf="@id/settings_button"\n',
"flash remains left of settings")
layout.write_text(s)

# ----- plan identity helper + diagnostic flag -----
s=plan.read_text()
s=one(s,
'    public static final int FLAG_SLOWEST_SPEED_EXCEEDED_AT_ISO_MAX = 128;\n',
'    public static final int FLAG_SLOWEST_SPEED_EXCEEDED_AT_ISO_MAX = 128;\n'
'    public static final int FLAG_AE_LOCK_HELD = 256;\n',
"AE lock flag")
anchor='''        @Override public int hashCode() {
            return java.util.Objects.hash(mode,userEv,manualExposureNs,manualIso,tripod,balance,
                    isoLimit,shutterLimit,oisMode,autoIsoMaximum,slowestSpeedMode,
                    slowestSpeedNs,lensEquivalent35mmX10,meteringKey);
        }
'''
replacement='''        /** Metering regions/recomposition may change while AE-L is held; exposure controls may not. */
        public boolean aeLockCompatible(Controls c) {
            return c!=null && mode.equals(c.mode)
                    && Double.doubleToLongBits(userEv)==Double.doubleToLongBits(c.userEv)
                    && manualExposureNs==c.manualExposureNs && manualIso==c.manualIso
                    && tripod==c.tripod && Float.floatToIntBits(balance)==Float.floatToIntBits(c.balance)
                    && isoLimit==c.isoLimit && Float.floatToIntBits(shutterLimit)==Float.floatToIntBits(c.shutterLimit)
                    && oisMode==c.oisMode && autoIsoMaximum==c.autoIsoMaximum
                    && slowestSpeedMode==c.slowestSpeedMode && slowestSpeedNs==c.slowestSpeedNs
                    && lensEquivalent35mmX10==c.lensEquivalent35mmX10;
        }
        @Override public int hashCode() {
            return java.util.Objects.hash(mode,userEv,manualExposureNs,manualIso,tripod,balance,
                    isoLimit,shutterLimit,oisMode,autoIsoMaximum,slowestSpeedMode,
                    slowestSpeedNs,lensEquivalent35mmX10,meteringKey);
        }
'''
s=one(s,anchor,replacement,"lock-compatible controls")
plan.write_text(s)

# ----- CaptureController owns a session-scoped explicit AE-L -----
s=capture.read_text()
s=one(s,
'    private final MonoExposureStore1A monoExposureStore1A = new MonoExposureStore1A();\n',
'''    private final MonoExposureStore1A monoExposureStore1A = new MonoExposureStore1A();

    // LEICAAELOCK1A: phone adaptation of first-generation M Monochrom metering memory lock.
    // The real camera holds the metered exposure while the shutter release pressure point is held.
    // A phone has no half-press, so this explicit toggle persists within the current camera session.
    private volatile boolean monoAeLock1F;
    private MonoExposurePlan1A monoAeLockSourcePlan1F;
    private MonoExposurePlan1A.Controls monoAeLockControls1F;
    private String monoAeLockCamera1F="";
''',"lock fields")

# Keep metering/tap/crop changes from invalidating the lock while exposure controls stay identical.
s=one(s,
'''        return new MonoExposurePlan1A.Controls(PhotonCamera.getSettings().selectedMode.name(),
''',
'''        if(monoAeLock1F && monoAeLockControls1F!=null)
            metering=monoAeLockControls1F.meteringKey;
        return new MonoExposurePlan1A.Controls(PhotonCamera.getSettings().selectedMode.name(),
''',"frozen metering identity")

get_anchor='''    public MonoExposurePlan1A getMonoExposurePlan1A() {
'''
methods=r'''    public boolean isMonoAeLock1F() { return monoAeLock1F; }

    private void publishMonoAeLockUi1F(boolean locked) {
        if(activity==null)return;
        activity.runOnUiThread(() -> {
            android.view.View v=activity.findViewById(com.particlesdevs.photoncamera.R.id.mono_ae_lock_button);
            if(v!=null) {
                v.setSelected(locked);
                v.setContentDescription(activity.getString(com.particlesdevs.photoncamera.R.string.mono_ae_lock)
                        +(locked?" locked":" auto"));
            }
        });
    }

    private synchronized void clearMonoAeLockFields1F(String reason) {
        monoAeLock1F=false;
        monoAeLockSourcePlan1F=null;
        monoAeLockControls1F=null;
        monoAeLockCamera1F="";
        com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.clear("ae_lock_clear_"+reason);
        publishMonoAeLockUi1F(false);
    }

    public synchronized boolean setMonoAeLock1F(boolean enabled) {
        if(!enabled) {
            clearMonoAeLockFields1F("user_unlock");
            monoExposureStore1A.invalidate();
            return false;
        }
        if(!useMonoExposurePlan1A())return false;
        MonoExposurePlan1A.Controls controls=monoControls1A();
        // Original metering memory lock belongs to aperture-priority exposure;
        // an explicit manual shutter is already its own exposure lock.
        if(controls.manualExposureNs>0)return false;
        String camera=monoCameraKey1A();
        long now=SystemClock.elapsedRealtimeNanos();
        long token=monoExposureStore1A.context(camera,controls);
        MonoExposurePlan1A p=monoExposureStore1A.latest(now);
        if(p==null) {
            p=IsoExpoSelector.planMonoExposure1A(this,mPreviewCaptureResult,camera,token,controls);
            if(p!=null)monoExposureStore1A.publish(p,now);
        }
        if(p==null)return false;
        monoAeLockSourcePlan1F=p;
        monoAeLockControls1F=controls;
        monoAeLockCamera1F=camera;
        monoAeLock1F=true;
        com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.clear("ae_lock_engaged");
        publishMonoAeLockUi1F(true);
        return true;
    }

    public synchronized boolean toggleMonoAeLock1F() {
        return setMonoAeLock1F(!monoAeLock1F);
    }

    private MonoExposurePlan1A projectMonoAeLock1F(CaptureResult observation,String camera,long token,
            MonoExposurePlan1A.Controls controls) {
        MonoExposurePlan1A locked=monoAeLockSourcePlan1F;
        if(!monoAeLock1F||locked==null||observation==null)return null;
        Integer observedIso=observation.get(CaptureResult.SENSOR_SENSITIVITY);
        Long observedTime=observation.get(CaptureResult.SENSOR_EXPOSURE_TIME);
        Long sensorTs=observation.get(CaptureResult.SENSOR_TIMESTAMP);
        Integer boost=observation.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST);
        if(observedIso==null||observedIso<=0||observedTime==null||observedTime<=0)return null;
        long now=SystemClock.elapsedRealtimeNanos();
        return new MonoExposurePlan1A(now,token,now,sensorTs==null?-1:sensorTs,camera,controls,
                observedIso,observedTime,locked.iso,locked.exposureNs,
                boost==null||boost<=0?100:boost,locked.autoEv,
                "leica_metering_memory_lock",
                locked.flags|MonoExposurePlan1A.FLAG_AE_LOCK_HELD);
    }

'''
s=one(s,get_anchor,methods+get_anchor,"AE lock methods")

old_update='''    public MonoExposurePlan1A updateMonoExposurePlan1A(CaptureResult observation) {
        if(!useMonoExposurePlan1A()) {monoExposureStore1A.invalidate();return null;}
        MonoExposurePlan1A.Controls controls=monoControls1A();
        String camera=monoCameraKey1A();
        long token=monoExposureStore1A.context(camera,controls);
        MonoExposurePlan1A plan=IsoExpoSelector.planMonoExposure1A(this,observation,camera,token,controls);
        // Allocation can overlap a dial change/camera reopen: never publish across that boundary.
        monoExposureStore1A.context(monoCameraKey1A(),monoControls1A());
        return monoExposureStore1A.publish(plan,SystemClock.elapsedRealtimeNanos())?plan:null;
    }
'''
new_update='''    public MonoExposurePlan1A updateMonoExposurePlan1A(CaptureResult observation) {
        if(!useMonoExposurePlan1A()) {
            clearMonoAeLockFields1F("non_photo_context");
            monoExposureStore1A.invalidate();return null;
        }
        MonoExposurePlan1A.Controls controls=monoControls1A();
        String camera=monoCameraKey1A();
        if(monoAeLock1F && (monoAeLockSourcePlan1F==null
                || !camera.equals(monoAeLockCamera1F)
                || monoAeLockControls1F==null
                || !monoAeLockControls1F.aeLockCompatible(controls))) {
            clearMonoAeLockFields1F("camera_or_exposure_control_change");
            controls=monoControls1A();
        }
        long token=monoExposureStore1A.context(camera,controls);
        MonoExposurePlan1A plan=monoAeLock1F
                ?projectMonoAeLock1F(observation,camera,token,controls)
                :IsoExpoSelector.planMonoExposure1A(this,observation,camera,token,controls);
        // Allocation can overlap a dial change/camera reopen: never publish across that boundary.
        monoExposureStore1A.context(monoCameraKey1A(),monoControls1A());
        return monoExposureStore1A.publish(plan,SystemClock.elapsedRealtimeNanos())?plan:null;
    }
'''
s=one(s,old_update,new_update,"locked plan projection")

# A camera/lens/session close ends the phone toggle, analogous to releasing the original pressure point.
s=one(s,
'''    public void closeCamera() {
        invalidateMonoExposurePlan1A();
''',
'''    public void closeCamera() {
        clearMonoAeLockFields1F("camera_close");
        invalidateMonoExposurePlan1A();
''',"close clears AE lock")
capture.write_text(s)

# ----- Tap while AE-L is held = focus/recompose only, never a new exposure subject -----
s=focus.read_text()
anchor='''        if(com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.insideSelection(x,y,now)) {
'''
replacement='''        if(captureController.isMonoAeLock1F()) {
            com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.clear("ae_lock_focus_only");
            if(autofocus)processTouchToFocus(x,y);
            return true;
        }
'''+anchor
s=one(s,anchor,replacement,"tap focus-only under AE lock")
focus.write_text(s)

# ----- top-bar click -----
s=ui.read_text()
anchor='''            case R.id.flash_button:
                PreferenceKeys.setAeMode((PreferenceKeys.getAeMode() + 1) % 2); //cycles in 0 (torch), 1 (off)
'''
insert='''            case R.id.mono_ae_lock_button:
                boolean monoLocked1F=cameraFragment.captureController.toggleMonoAeLock1F();
                view.setSelected(monoLocked1F);
                cameraFragment.showSnackBar(cameraFragment.getString(
                        monoLocked1F ? R.string.mono_ae_lock_locked : R.string.mono_ae_lock_auto));
                break;

'''
s=one(s,anchor,insert+anchor,"AE-L click handler")
ui.write_text(s)

# ----- diagnostics -----
s=diag.read_text()
anchor='''                    .put("slowestSpeedExceededAtIsoMax",(p.flags&MonoExposurePlan1A.FLAG_SLOWEST_SPEED_EXCEEDED_AT_ISO_MAX)!=0)
'''
replacement=anchor+'''                    .put("aeLockRevision","LEICAAELOCK1A")
                    .put("aeLockHeld",(p.flags&MonoExposurePlan1A.FLAG_AE_LOCK_HELD)!=0)
                    .put("aeLockBehavior","freeze_physical_ISO_and_shutter_until_unlock_or_session_context_change")
'''
s=one(s,anchor,replacement,"AE lock diagnostics")
diag.write_text(s)

g=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m:raise SystemExit("LEICAAELOCK1A versionName missing")
if "leicaaelock1a" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-leicaaelock1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICAAELOCK1A changed frozen photographic files "+repr(changed))

proof={
 "revision":"LEICAAELOCK1A",
 "cameraModel":"first_generation_Leica_M_Monochrom",
 "originalControl":"shutter_release_second_pressure_point_metering_memory_lock",
 "phoneAdaptation":"explicit_topbar_toggle",
 "uiLabel":"AE Lock",
 "uiLockedIndicator":"closed_padlock",
 "sessionScoped":True,
 "persistsAcrossCapturesUntilExplicitUnlock":True,
 "clearsOnCameraCloseOrLensSessionChange":True,
 "locksPhysicalIsoAndShutter":True,
 "recompositionDoesNotChangeLockedExposure":True,
 "tapWhileLocked":"focus_only_no_new_exposure_subject",
 "manualShutterLockAvailable":False,
 "manualIsoCompatibleWithAperturePriorityLock":True,
 "exposureControlChangeClearsLock":True,
 "previewAndCaptureShareLockedPlan":True,
 "settingsGearStillImmediatelyRightOfFlash":True,
 "HDR":False,
 "rendererChanged":False,
 "linearDngMathChanged":False,
 "contrastChanged":False,
 "toningChanged":False,
 "sharpnessChanged":False,
 "frozenPhotographicHashes":after,
}
(root/"LEICAAELOCK1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
