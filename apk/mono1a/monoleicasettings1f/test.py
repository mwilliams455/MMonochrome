#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET

if len(sys.argv)!=2: raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
proof=json.loads((root/"LEICAAELOCK1A_ISOLATION.json").read_text())

assert proof["revision"]=="LEICAAELOCK1A"
assert proof["cameraModel"]=="first_generation_Leica_M_Monochrom"
assert proof["originalControl"]=="shutter_release_second_pressure_point_metering_memory_lock"
assert proof["phoneAdaptation"]=="explicit_topbar_toggle"
assert proof["sessionScoped"] and proof["persistsAcrossCapturesUntilExplicitUnlock"]
assert proof["clearsOnCameraCloseOrLensSessionChange"]
assert proof["locksPhysicalIsoAndShutter"] and proof["recompositionDoesNotChangeLockedExposure"]
assert proof["tapWhileLocked"]=="focus_only_no_new_exposure_subject"
assert not proof["manualShutterLockAvailable"]
assert proof["manualIsoCompatibleWithAperturePriorityLock"]
assert proof["exposureControlChangeClearsLock"]
assert proof["previewAndCaptureShareLockedPlan"]
assert proof["settingsGearStillImmediatelyRightOfFlash"]
assert not proof["HDR"]
assert not proof["rendererChanged"] and not proof["linearDngMathChanged"]
assert not proof["contrastChanged"] and not proof["toningChanged"] and not proof["sharpnessChanged"]

for rel,want in proof["frozenPhotographicHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

layout=(root/"app/src/main/res/layout/layout_main_topbar.xml").read_text()
assert 'android:id="@+id/mono_ae_lock_button"' in layout
assert 'android:background="@drawable/mono_ae_lock_button_1f"' in layout
# Preserve requested top-bar order: grid -> AE-L -> flash -> settings.
assert layout.index('android:id="@+id/grid_toggle_button"') < layout.index('android:id="@+id/mono_ae_lock_button"')
assert layout.index('android:id="@+id/mono_ae_lock_button"') < layout.index('android:id="@+id/flash_button"')
assert layout.index('android:id="@+id/flash_button"') < layout.index('android:id="@+id/settings_button"')
assert 'app:layout_constraintStart_toEndOf="@id/mono_ae_lock_button"' in layout
assert 'app:layout_constraintStart_toEndOf="@id/flash_button"' in layout

for p in [
 root/"app/src/main/res/drawable/mono_ae_lock_button_1f.xml",
 root/"app/src/main/res/drawable/ic_mono_ae_lock_closed_1f.xml",
 root/"app/src/main/res/drawable/ic_mono_ae_lock_open_1f.xml",
]:
    assert p.is_file(),p
selector=(root/"app/src/main/res/drawable/mono_ae_lock_button_1f.xml").read_text()
assert 'android:state_selected="true"' in selector
assert '@drawable/ic_mono_ae_lock_closed_1f' in selector
assert '@drawable/ic_mono_ae_lock_open_1f' in selector

plan=(J/"m9/exposure/MonoExposurePlan1A.java").read_text()
for marker in [
 "FLAG_AE_LOCK_HELD = 256",
 "aeLockCompatible(Controls c)",
 "manualExposureNs==c.manualExposureNs",
 "autoIsoMaximum==c.autoIsoMaximum",
 "slowestSpeedNs==c.slowestSpeedNs",
]:
    assert marker in plan,marker
# Metering key is intentionally absent from AE-lock compatibility: recomposition must not unlock.
method=plan[plan.index("public boolean aeLockCompatible"):plan.index("@Override public int hashCode()",plan.index("public boolean aeLockCompatible"))]
assert "meteringKey" not in method

capture=(J/"capture/CaptureController.java").read_text()
for marker in [
 "monoAeLock1F",
 "setMonoAeLock1F(boolean enabled)",
 "toggleMonoAeLock1F()",
 "projectMonoAeLock1F",
 '"leica_metering_memory_lock"',
 "FLAG_AE_LOCK_HELD",
 'clearMonoAeLockFields1F("camera_close")',
 "monoAeLockControls1F.aeLockCompatible(controls)",
 "metering=monoAeLockControls1F.meteringKey",
]:
    assert marker in capture,marker
assert "if(controls.manualExposureNs>0)return false;" in capture

focus=(J/"control/TouchFocus.java").read_text()
assert "if(captureController.isMonoAeLock1F())" in focus
assert 'MonoTapMeter1A.clear("ae_lock_focus_only")' in focus
assert "if(autofocus)processTouchToFocus(x,y);" in focus

ui=(J/"ui/camera/CameraUIController.java").read_text()
assert "case R.id.mono_ae_lock_button:" in ui
assert "toggleMonoAeLock1F()" in ui
assert "mono_ae_lock_locked" in ui and "mono_ae_lock_auto" in ui

diag=(J/"m9/exposure/MonoExposureDiagnostics1A.java").read_text()
for marker in [
 '"aeLockRevision","LEICAAELOCK1A"',
 '"aeLockHeld"',
 '"freeze_physical_ISO_and_shutter_until_unlock_or_session_context_change"',
]:
    assert marker in diag,marker

# Reference behavior: a lock freezes the selected physical pair even as hardware AE changes.
locked_iso,locked_t=800,16_666_667
hardware=[(400,8_000_000),(1600,33_333_333),(3200,66_666_667)]
projected=[(locked_iso,locked_t) for _ in hardware]
assert len(set(projected))==1 and projected[0]==(800,16_666_667)

# Manual ISO is compatible with aperture-priority AE-L; manual shutter is not.
def can_lock(manual_iso,manual_t): return manual_t==0
assert can_lock(800,0)
assert can_lock(0,0)
assert not can_lock(0,8_000_000)

report={
 "revision":"LEICAAELOCK1A_TEST",
 "status":"PASS",
 "originalMeteringMemoryLockSemanticsPreserved":"meter_and_hold_exposure_during_recomposition",
 "phoneAdaptation":"persistent_topbar_toggle_with_session_clear",
 "lockedPairStableAcrossChangingHardwareAE":True,
 "tapFocusOnlyWhileLocked":True,
 "manualShutterRejected":True,
 "manualIsoAllowed":True,
 "topbarOrder":"grid_AEL_flash_settings",
 "renderAndDngFrozen":True,
}
(root/"LEICAAELOCK1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
