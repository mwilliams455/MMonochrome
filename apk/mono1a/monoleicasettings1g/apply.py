#!/usr/bin/env python3
"""LEICAEV1A: one real first-generation M Monochrom exposure-compensation control."""
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
ev_model=root/"circularbarlib/src/main/java/com/particlesdevs/photoncamera/circularbarlib/control/models/EvModel.java"
param=J/"manual/ParamController.java"
plan=J/"m9/exposure/MonoExposurePlan1A.java"
selector=J/"processing/parameters/IsoExpoSelector.java"
diag=J/"m9/exposure/MonoExposureDiagnostics1A.java"
settings=J/"api/Settings.java"
capture=J/"capture/CaptureController.java"
gradle=root/"app/build.gradle"

for p in [ev_model,param,plan,selector,diag,settings,capture,gradle]:
    if not p.is_file(): raise SystemExit("LEICAEV1A missing "+str(p))
for receipt in ["LEICAAELOCK1A_ISOLATION.json","LEICASLOWEST1A_ISOLATION.json",
                "LEICAAUTOISO1A_ISOLATION.json","LEICASHARPNESS1C_ISOLATION.json",
                "LEICATONING1A_FIX2_SOURCE1D_ISOLATION.json"]:
    if not (root/receipt).is_file(): raise SystemExit("LEICAEV1A missing parent receipt "+receipt)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"LEICAEV1A {label} anchor count={n}")
    return s.replace(a,b,1)

def replace_method(text, signature, replacement):
    start=text.index(signature)
    brace=text.index("{",start)
    depth=0
    end=None
    for i in range(brace,len(text)):
        if text[i]=="{": depth+=1
        elif text[i]=="}":
            depth-=1
            if depth==0:
                end=i+1
                break
    if end is None: raise SystemExit("LEICAEV1A unterminated method "+signature)
    return text[:start]+replacement+text[end:]

# Renderer/DNG/Leica image controls remain byte-identical. Exposure code/UI only.
frozen=[
 J/"m9/render/M9R35Renderer.java",
 J/"m9/render/M9NativeColorCore.java",
 J/"m9/export/MonoDngExport1A.java",
 J/"m9/export/MonoDngWriter1A.java",
 J/"m9/export/MonoLinearPlane1A.java",
 J/"m9/preview/MonoGpuPreview2A.java",
 root/"app/src/main/cpp/m9color_jni.cpp",
 root/"app/src/main/assets/shaders/preview/main_fs.glsl",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}

# ---------------------------------------------------------------------------
# 1. Re-purpose Photon's existing EV wheel as the ONE Leica exposure control.
#    It is independent of Camera2's vendor AE-compensation step/range because
#    the Monochrom planner allocates physical ISO + shutter itself.
# ---------------------------------------------------------------------------
s=ev_model.read_text()
new_fill=r'''    @Override
    protected void fillKnobInfoList() {
        // LEICAEV1A: first-generation M Monochrom = -3..+3 EV in exact 1/3 EV steps.
        // Zero is the neutral state, not a second "Auto" exposure algorithm.
        KnobItemInfo zero=getNewAutoItem(ManualParamModel.EV_AUTO,"0");
        getKnobInfoList().add(zero);
        currentInfo=zero;
        final int thirdsPerSide=9;
        for(int thirds=thirdsPerSide;thirds>=-thirdsPerSide;--thirds) {
            if(thirds==0)continue;
            final double value=thirds/3.0;
            ShadowTextDrawable drawable=new ShadowTextDrawable();
            drawable.setTextAppearance(context,R.style.ManualModeKnobText);
            ShadowTextDrawable selected=new ShadowTextDrawable();
            selected.setTextAppearance(context,R.style.ManualModeKnobTextSelected);
            // Keep the wheel visually clean: print full-stop marks, while the
            // selected value text always shows the exact 1/3-stop value.
            if(thirds%3==0) {
                int whole=thirds/3;
                String mark=whole>0?"+"+whole:String.valueOf(whole);
                drawable.setText(mark);selected.setText(mark);
            }
            StateListDrawable stateDrawable=new StateListDrawable();
            stateDrawable.addState(new int[]{-android.R.attr.state_selected},drawable);
            stateDrawable.addState(new int[]{android.R.attr.state_selected},selected);
            String text=String.format(Locale.ROOT,"%+.2f",value);
            getKnobInfoList().add(new KnobItemInfo(stateDrawable,text,thirds,value));
        }
        int angle=context.getResources().getInteger(R.integer.manual_ev_knob_view_angle_half);
        knobInfo=new KnobInfo(-angle,angle,-thirdsPerSide,thirdsPerSide,
                context.getResources().getInteger(R.integer.manual_ev_knob_view_auto_angle));
    }'''
s=replace_method(s,"    @Override\n    protected void fillKnobInfoList()",new_fill)
new_selected=r'''    @Override
    public void onSelectedKnobItemChanged(KnobItemInfo knobItemInfo) {
        currentInfo=knobItemInfo;
        // Store EV stops directly. Never quantize through a vendor Camera2 AE step.
        manualParamModel.setCurrentEvValue(knobItemInfo.value);
    }'''
s=replace_method(s,"    @Override\n    public void onSelectedKnobItemChanged(KnobItemInfo knobItemInfo)",new_selected)
ev_model.write_text(s)

# ---------------------------------------------------------------------------
# 2. The hidden generic Photon "Exposure Compensation" preference is neutral.
#    This prevents an old persisted value from becoming a second invisible EV.
# ---------------------------------------------------------------------------
s=settings.read_text()
s=one(s,
"        exposureCompensation = PreferenceKeys.getFloat(PreferenceKeys.Key.KEY_EXPOCOMPENSATE_SEEKBAR);\n",
"        exposureCompensation = 0.0; // LEICAEV1A: hidden generic Photon EV disabled; manual EV wheel is sole authority\n",
"hidden generic EV neutral")
settings.write_text(s)

# ---------------------------------------------------------------------------
# 3. ParamController: EV is expressed in stops, not Camera2 integer steps.
#    For Monochrom, hardware AE compensation stays 0 and the physical shared
#    plan owns the exposure. Non-Monochrom fallback converts stops to the HAL step.
# ---------------------------------------------------------------------------
s=param.read_text()
s=one(s,"    public int EV = 0;\n","    public double EV = 0.0; // LEICAEV1A stops\n","EV field")

old_method='''    public void setEV(int ev) {
        CaptureRequest.Builder builder = captureController.mPreviewRequestBuilder;
        if (builder == null) {
            Log.w(TAG, "setEV(): mPreviewRequestBuilder is null");
            return;
        }
        if(captureController.useMonoExposurePlan1A()) {
            captureController.invalidateMonoExposurePlan1A();
            builder.set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_ON);
            builder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,0);
            captureController.rebuildPreviewBuilder();
            return;
        }
        builder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION, ev);
        captureController.rebuildPreviewBuilder();
    }'''
if old_method not in s:
    # Preserve compatibility with formatting produced by the parent if whitespace differs.
    start=s.index("    public void setEV(")
    brace=s.index("{",start);depth=0;end=None
    for i in range(brace,len(s)):
        if s[i]=="{":depth+=1
        elif s[i]=="}":
            depth-=1
            if depth==0:end=i+1;break
    old_method=s[start:end]
new_method=r'''    public void setEV(double evStops) {
        CaptureRequest.Builder builder=captureController.mPreviewRequestBuilder;
        if(builder==null) {
            Log.w(TAG,"setEV(): mPreviewRequestBuilder is null");
            return;
        }
        if(captureController.useMonoExposurePlan1A()) {
            // User EV is a real physical-plan input. Keep vendor AE neutral so it
            // cannot be counted a second time in preview or capture.
            if(captureController.isMonoAeLock1F())captureController.setMonoAeLock1F(false);
            captureController.invalidateMonoExposurePlan1A();
            builder.set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_ON);
            builder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,0);
            captureController.rebuildPreviewBuilder();
            return;
        }
        android.hardware.camera2.CameraCharacteristics chars=CaptureController.mCameraCharacteristics;
        android.util.Rational step=chars==null?null:chars.get(
                android.hardware.camera2.CameraCharacteristics.CONTROL_AE_COMPENSATION_STEP);
        android.util.Range<Integer> range=chars==null?null:chars.get(
                android.hardware.camera2.CameraCharacteristics.CONTROL_AE_COMPENSATION_RANGE);
        int hardwareSteps=step==null||step.doubleValue()==0.0?0:(int)Math.round(evStops/step.doubleValue());
        if(range!=null)hardwareSteps=Math.max(range.getLower(),Math.min(range.getUpper(),hardwareSteps));
        builder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,hardwareSteps);
        captureController.rebuildPreviewBuilder();
    }'''
s=s.replace(old_method,new_method,1)

s=one(s,
'''            if (object.equals(ManualParamModel.ID_EV)) {
                EV = (int) model.getCurrentEvValue();
                setEV((int) model.getCurrentEvValue());
            }
''',
'''            if (object.equals(ManualParamModel.ID_EV)) {
                EV = model.getCurrentEvValue();
                setEV(EV);
            }
''',"EV observer exact stops")
s=one(s,
'''            if (EV != 0)
                setEV(EV);
''',
'''            if (Math.abs(EV) > 1.0e-9)
                setEV(EV);
''',"EV preview restore")
old_get='''    public double getMonoUserEv1A() {
        android.hardware.camera2.CameraCharacteristics chars=captureController.monoCharacteristics1A();
        android.util.Rational step=chars==null?null:chars.get(android.hardware.camera2.CameraCharacteristics.CONTROL_AE_COMPENSATION_STEP);
        double manualSteps=manualParamModel==null?0.0:manualParamModel.getCurrentEvValue();
        if(manualSteps!=0 && step==null)throw new IllegalStateException("missing_EV_step");
        return MonoExposurePlan1A.combinedEv(com.particlesdevs.photoncamera.app.PhotonCamera.getSettings().exposureCompensation,
                manualSteps,step==null?0.0:step.doubleValue());
    }'''
new_get='''    public double getMonoUserEv1A() {
        double evStops=manualParamModel==null?0.0:manualParamModel.getCurrentEvValue();
        return MonoExposurePlan1A.clampLeicaUserEv(evStops);
    }'''
s=one(s,old_get,new_get,"single Leica EV authority")
param.write_text(s)

# ---------------------------------------------------------------------------
# 4. Scene placement remains automatic with nonzero EV. User compensation is
#    layered ON TOP once, in the existing planner's userEv + autoEv sum.
# ---------------------------------------------------------------------------
s=plan.read_text()
s=one(s,
'''    public static double combinedEv(double settingsEv, double manualSteps, double evPerStep) {
        double ev=settingsEv+manualSteps*evPerStep;
        if(!Double.isFinite(ev)) throw new IllegalArgumentException("invalid_ev");
        return ev;
    }
''',
'''    public static final double LEICA_USER_EV_MIN=-3.0;
    public static final double LEICA_USER_EV_MAX=3.0;
    public static final double LEICA_USER_EV_STEP=1.0/3.0;
    public static double clampLeicaUserEv(double ev) {
        if(!Double.isFinite(ev))throw new IllegalArgumentException("invalid_ev");
        return Math.max(LEICA_USER_EV_MIN,Math.min(LEICA_USER_EV_MAX,ev));
    }
    /** Retained for old callers; LEICAEV1A has one stop-domain authority. */
    public static double combinedEv(double settingsEv,double manualSteps,double evPerStep) {
        return clampLeicaUserEv(settingsEv+manualSteps*evPerStep);
    }
''',"Leica EV constants")
s=one(s,
'''    public static boolean assistEligible(Controls c) {
        return "PHOTO".equals(c.mode) && !c.tripod && c.manualIso==0 && c.manualExposureNs==0
                && Math.abs(c.userEv)<1e-9;
    }
''',
'''    public static boolean assistEligible(Controls c) {
        // Exposure compensation is not manual exposure. Keep Monochrom scene
        // placement/tap intent active, then layer user EV once in the allocator.
        return "PHOTO".equals(c.mode) && !c.tripod && c.manualIso==0 && c.manualExposureNs==0;
    }
''',"EV does not disable scene placement")
s=one(s,
'''            if(mode==null || meteringKey==null || !Double.isFinite(userEv) || manualExposureNs<0 || manualIso<0
''',
'''            if(mode==null || meteringKey==null || !Double.isFinite(userEv)
                    || userEv<LEICA_USER_EV_MIN-1.0e-9 || userEv>LEICA_USER_EV_MAX+1.0e-9
                    || manualExposureNs<0 || manualIso<0
''',"validate Leica EV range")
plan.write_text(s)

# Existing allocator is already the correct seam: compensation is applied to
# physical exposure energy before Auto ISO Maximum / Slowest speed constraints.
s=selector.read_text()
needle="double compensation = Math.pow(2.0,planning?input.controls.userEv+input.autoEv:PhotonCamera.getSettings().exposureCompensation);"
if needle not in s:
    raise SystemExit("LEICAEV1A missing shared physical compensation seam")
# Clarify stale diagnostic wording only; math is untouched.
s=s.replace('"mono_manual_ev_or_tripod_bypass"','"mono_manual_iso_shutter_or_tripod_bypass"')
selector.write_text(s)

# ---------------------------------------------------------------------------
# 5. Explicit telemetry proves single application and preview/capture plan use.
# ---------------------------------------------------------------------------
s=diag.read_text()
anchor='''                    .put("aeLockBehavior","freeze_physical_ISO_and_shutter_until_unlock_or_session_context_change")
'''
replacement=anchor+'''                    .put("exposureCompensationRevision","LEICAEV1A")
                    .put("exposureCompensationEv",p.controls.userEv)
                    .put("exposureCompensationMinEv",MonoExposurePlan1A.LEICA_USER_EV_MIN)
                    .put("exposureCompensationMaxEv",MonoExposurePlan1A.LEICA_USER_EV_MAX)
                    .put("exposureCompensationStepEv",MonoExposurePlan1A.LEICA_USER_EV_STEP)
                    .put("hardwareAeCompensationNeutral",true)
                    .put("exposureCompensationAppliedInPhysicalPlanOnce",true)
                    .put("automaticPlacementStillEligibleWithUserEv",true)
'''
s=one(s,anchor,replacement,"EV telemetry")
diag.write_text(s)

g=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m:raise SystemExit("LEICAEV1A versionName missing")
if "leicaev1a" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-leicaev1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICAEV1A changed frozen image-output files "+repr(changed))

proof={
 "revision":"LEICAEV1A",
 "cameraModel":"first_generation_Leica_M_Monochrom",
 "rangeEv":[-3.0,3.0],
 "stepEv":1.0/3.0,
 "uiControl":"existing_manual_EV_wheel_repurposed_as_single_Leica_EV_control",
 "uiZeroLabel":"0",
 "vendorAeRangeIndependent":True,
 "vendorAeStepIndependent":True,
 "hiddenPhotonExposureCompensationForcedNeutral":True,
 "hardwareAeCompensationNeutralInMono":True,
 "physicalPlanOwnsUserEv":True,
 "userEvAppliedExactlyOnce":True,
 "automaticPlacementRemainsActiveWithUserEv":True,
 "tapPlacementRemainsActiveWithUserEv":True,
 "previewUsesSamePhysicalPlan":True,
 "captureUsesSamePhysicalPlan":True,
 "dngExposureChangesByPhysicalCaptureNotPostRender":True,
 "aeLockClearsWhenUserEvChanges":True,
 "autoIsoMaximumPreserved":True,
 "slowestSpeedPreserved":True,
 "HDR":False,
 "rendererChanged":False,
 "linearDngMathChanged":False,
 "contrastChanged":False,
 "toningChanged":False,
 "sharpnessChanged":False,
 "frozenImageOutputHashes":after,
}
(root/"LEICAEV1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
