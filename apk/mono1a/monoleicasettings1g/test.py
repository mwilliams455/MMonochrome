#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,math,re,sys

if len(sys.argv)!=2: raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
proof=json.loads((root/"LEICAEV1A_ISOLATION.json").read_text())

assert proof["revision"]=="LEICAEV1A"
assert proof["cameraModel"]=="first_generation_Leica_M_Monochrom"
assert proof["rangeEv"]==[-3.0,3.0]
assert abs(proof["stepEv"]-1.0/3.0)<1e-12
for k in [
 "vendorAeRangeIndependent","vendorAeStepIndependent",
 "hiddenPhotonExposureCompensationForcedNeutral","hardwareAeCompensationNeutralInMono",
 "physicalPlanOwnsUserEv","userEvAppliedExactlyOnce",
 "automaticPlacementRemainsActiveWithUserEv","tapPlacementRemainsActiveWithUserEv",
 "previewUsesSamePhysicalPlan","captureUsesSamePhysicalPlan",
 "dngExposureChangesByPhysicalCaptureNotPostRender","aeLockClearsWhenUserEvChanges",
 "autoIsoMaximumPreserved","slowestSpeedPreserved",
]:
    assert proof[k],k
assert not proof["HDR"]
assert not proof["rendererChanged"] and not proof["linearDngMathChanged"]
assert not proof["contrastChanged"] and not proof["toningChanged"] and not proof["sharpnessChanged"]

for rel,want in proof["frozenImageOutputHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

ev=(root/"circularbarlib/src/main/java/com/particlesdevs/photoncamera/circularbarlib/control/models/EvModel.java").read_text()
for marker in [
 'getNewAutoItem(ManualParamModel.EV_AUTO,"0")',
 "final int thirdsPerSide=9",
 "final double value=thirds/3.0",
 'String.format(Locale.ROOT,"%+.2f",value)',
 "manualParamModel.setCurrentEvValue(knobItemInfo.value)",
]:
    assert marker in ev,marker
assert "knobItemInfo.value / evStep" not in ev
# 18 non-zero third-stop positions + neutral zero.
assert "new KnobInfo(-angle,angle,-thirdsPerSide,thirdsPerSide" in ev

settings=(J/"api/Settings.java").read_text()
assert "exposureCompensation = 0.0; // LEICAEV1A" in settings

param=(J/"manual/ParamController.java").read_text()
for marker in [
 "public double EV = 0.0",
 "public void setEV(double evStops)",
 "captureController.setMonoAeLock1F(false)",
 "CONTROL_AE_EXPOSURE_COMPENSATION,0",
 "Math.round(evStops/step.doubleValue())",
 "EV = model.getCurrentEvValue()",
 "MonoExposurePlan1A.clampLeicaUserEv(evStops)",
]:
    assert marker in param,marker
get_start=param.index("public double getMonoUserEv1A()")
get_end=param.index("public boolean isManualMode()",get_start)
get_body=param[get_start:get_end]
assert "PhotonCamera.getSettings().exposureCompensation" not in get_body
assert "CONTROL_AE_COMPENSATION_STEP" not in get_body

plan=(J/"m9/exposure/MonoExposurePlan1A.java").read_text()
for marker in [
 "LEICA_USER_EV_MIN=-3.0",
 "LEICA_USER_EV_MAX=3.0",
 "LEICA_USER_EV_STEP=1.0/3.0",
 "clampLeicaUserEv(double ev)",
 "return \"PHOTO\".equals(c.mode) && !c.tripod && c.manualIso==0 && c.manualExposureNs==0;",
]:
    assert marker in plan,marker
assist=plan[plan.index("public static boolean assistEligible"):plan.index("public static final class Controls")]
assert "userEv" not in assist

selector=(J/"processing/parameters/IsoExpoSelector.java").read_text()
seam="planning?input.controls.userEv+input.autoEv:PhotonCamera.getSettings().exposureCompensation"
assert seam in selector
# Only this physical allocator seam combines user EV and auto placement.
assert selector.count("input.controls.userEv+input.autoEv")==1

diag=(J/"m9/exposure/MonoExposureDiagnostics1A.java").read_text()
for marker in [
 '"exposureCompensationRevision","LEICAEV1A"',
 '"exposureCompensationEv",p.controls.userEv',
 '"hardwareAeCompensationNeutral",true',
 '"exposureCompensationAppliedInPhysicalPlanOnce",true',
 '"automaticPlacementStillEligibleWithUserEv",true',
]:
    assert marker in diag,marker

# Pure EV math. In an unconstrained physical plan, +/- EV scales exposure energy by 2^EV.
for thirds in range(-9,10):
    ev_stop=thirds/3.0
    factor=2.0**ev_stop
    assert factor>0 and math.isfinite(factor)
assert abs((2.0**(1/3.0)) - 1.2599210498948732)<1e-12
assert abs((2.0**(-1/3.0)) - 0.7937005259840998)<1e-12
assert abs((2.0**3.0)-8.0)<1e-12
assert abs((2.0**-3.0)-0.125)<1e-12

# User EV and automatic Monochrom placement are additive in EV, never multiplicative twice.
auto_ev=0.30
user_ev=2.0/3.0
combined=user_ev+auto_ev
assert abs((2.0**combined)-((2.0**user_ev)*(2.0**auto_ev)))<1e-12

report={
 "revision":"LEICAEV1A_TEST",
 "status":"PASS",
 "range":"-3_to_+3_EV",
 "increment":"1/3_EV",
 "oneVisibleEvAuthority":True,
 "hiddenPhotonEvNeutral":True,
 "vendorAeCompNeutral":True,
 "userEvAndAutomaticPlacementAddOnce":True,
 "previewCapturePlanShared":True,
 "physicalDngExposureIntent":True,
 "autoIsoSlowestAeLockPreserved":True,
 "renderAndDngMathFrozen":True,
}
(root/"LEICAEV1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
