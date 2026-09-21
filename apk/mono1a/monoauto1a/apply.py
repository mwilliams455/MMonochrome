#!/usr/bin/env python3
"""MONOAUTO1A: shared immutable exposure plan over exact delivered GL2B + MONOOUTPUT1A."""
from pathlib import Path
import hashlib,json,sys,re,shutil
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
J='app/src/main/java/com/particlesdevs/photoncamera/'
H=lambda b:hashlib.sha256(b).hexdigest()
proof=json.loads((root/'MONOLIVEGL2B_ISOLATION.json').read_text())
for rel,value in {**proof['frozen'],**{r:v['after'] for r,v in proof['changed'].items()}}.items():
    if H((root/rel).read_bytes())!=value:raise SystemExit('GL2B baseline mismatch '+rel)
rels={'selector':J+'processing/parameters/IsoExpoSelector.java','capture':J+'capture/CaptureController.java',
      'fragment':J+'ui/camera/CameraFragment.java','main':J+'ui/camera/views/viewfinder/MainRenderer.java',
      'gl':J+'ui/camera/views/viewfinder/GLPreview.java','gpu':J+'m9/preview/MonoGpuPreview2A.java',
      'diag':J+'m9/preview/MonoLivePairDiagnostics1E.java','export':J+'m9/preview/MonoLivePairExport1D.java','param':J+'manual/ParamController.java',
      'mfm':J+'m9/M9M10rMfmTest1A.java','motion':J+'m9/M9ModernExposurePolicy.java','gradle':'app/build.gradle'}
before={r:(root/r).read_bytes() for r in rels.values()}
# All Java not explicitly listed is sealed, including complete renderer, DNG, saver and spool.
frozen={str(p.relative_to(root)):H(p.read_bytes()) for p in (root/'app/src/main').rglob('*')
        if p.is_file() and str(p.relative_to(root)) not in rels.values()}
def one(s,a,b):
    if s.count(a)!=1:raise SystemExit('Expected one anchor '+repr(a[:100])+' count='+str(s.count(a)))
    return s.replace(a,b,1)
def get(k):return before[rels[k]].decode()
def put(k,s):(root/rels[k]).write_text(s)
def imports(s):return s.replace('\nimport ', '\nimport com.particlesdevs.photoncamera.m9.exposure.MonoExposurePlan1A;\nimport com.particlesdevs.photoncamera.m9.exposure.MonoExposureStore1A;\nimport com.particlesdevs.photoncamera.m9.exposure.MonoExposureDiagnostics1A;\nimport ',1)
# Upstream M9 planning-specific no-publication overloads. Mathematical policy unchanged.
s=get('mfm');anchor='''        JSONObject out = contract();'''
s=one(s,anchor,'''        return evaluateMonoAware1A(previewEnergyIsoSeconds,cameraRotationDegrees,eligible,eligibilityReason,true);
    }
    public static synchronized M9BacklightDiagnostic.LiveFeedbackDecision evaluateForMonoPlan1A(
            double previewEnergyIsoSeconds,int cameraRotationDegrees,boolean eligible,String eligibilityReason) {
        return evaluateMonoAware1A(previewEnergyIsoSeconds,cameraRotationDegrees,eligible,eligibilityReason,false);
    }
    private static M9BacklightDiagnostic.LiveFeedbackDecision evaluateMonoAware1A(
            double previewEnergyIsoSeconds,int cameraRotationDegrees,boolean eligible,String eligibilityReason,boolean publish) {
        JSONObject out = contract();''')
a=s.index('            M9BacklightDiagnostic.LiveFeedbackDecision legacy =');b=s.index('\n\n            if (frames < 3L',a)
part=s[a:b];shared='''            out.put("previewExposureEnergyIsoSeconds", previewEnergyIsoSeconds);
            out.put("cameraRotationDegrees", cameraRotationDegrees);
            out.put("previewLumaFrames", frames);'''
assert shared in part
part=part.replace(shared,'');s=s[:a]+shared+'\n            if(publish) {\n'+part+'\n            }'+s[b:]
s=one(s,'        lastLive = cloneJson(out);','        if(publish) lastLive = cloneJson(out);');put('mfm',s)
s=get('motion');a='''                                                    long photonCapEndNs) {
        final double rawScore'''
s=one(s,a,'''                                                    long photonCapEndNs) {
        return adjustCaps(targetShutterNs,targetIsoNormalized,maxAnalogIsoNormalized,photonCapStartNs,photonCapEndNs,true);
    }
    public static synchronized Decision adjustCaps(long targetShutterNs,int targetIsoNormalized,
            int maxAnalogIsoNormalized,long photonCapStartNs,long photonCapEndNs,boolean publish) {
        final double rawScore''')
s=one(s,'        lastDecision = o;','        if(publish) lastDecision = o;');put('motion',s)
# IsoExpoSelector: explicit observation/controls in planning, no capture audit or double assist.
s=imports(get('selector'))
s=one(s,'    private static double mpy1 = 1.0;\n    public static ExpoPair GenerateExpoPair(int step, CaptureController captureController) {',
'''    public static ExpoPair GenerateExpoPair(int step, CaptureController captureController) {
        return generateMonoAware1A(step,captureController,null);
    }
'''+(here/'selector.inc').read_text()+'''
    private static ExpoPair generateMonoAware1A(int step,CaptureController captureController,MonoInput1A input) {
        final boolean planning=input!=null;
        boolean useTripod=planning?input.controls.tripod:IsoExpoSelector.useTripod;
        double mpy1;
        final boolean HDR=!planning && !M9Config.usesM9Pipeline() && IsoExpoSelector.HDR;''')
s=one(s,'        if (M9Config.usesM9Pipeline()) HDR = false;','        if (!planning && M9Config.usesM9Pipeline()) IsoExpoSelector.HDR = false;')
s=one(s,'''        ExpoPair pair = new ExpoPair(captureController.mPreviewExposureTime, getEXPLOW(), getEXPHIGH(),
                captureController.mPreviewIso, getISOLOW(), getISOHIGH(),getISOAnalog());
        double compensation = Math.pow(2.0,PhotonCamera.getSettings().exposureCompensation);''',
'''        ExpoPair pair = planning ? new ExpoPair(input.exposureNs,input.timeLow,input.timeHigh,input.iso,input.isoLow,input.isoHigh,input.analog)
                : new ExpoPair(captureController.mPreviewExposureTime,getEXPLOW(),getEXPHIGH(),captureController.mPreviewIso,getISOLOW(),getISOHIGH(),getISOAnalog());
        double compensation = Math.pow(2.0,planning?input.controls.userEv+input.autoEv:PhotonCamera.getSettings().exposureCompensation);''')
# Only suppress reporting within generator (not request application).
a=s.index('    private static ExpoPair generateMonoAware1A');b=s.index('    public static double getMPY()',a);body=s[a:b]
body=body.replace('if (M9Config.isCaptureTest()', 'if (!planning && M9Config.isCaptureTest()')
body=body.replace('if (M9Config.isM9Modern()) {','if (!planning && M9Config.isM9Modern()) {')
body=one(body,'''        if (PhotonCamera.getGyro() != null) {
            useTripod = PhotonCamera.getGyro().getTripod();
        }''','''        if (!planning && PhotonCamera.getGyro() != null) {
            useTripod = PhotonCamera.getGyro().getTripod();
            IsoExpoSelector.useTripod=useTripod;
        }''')
body=one(body,'double dynamicFactor = getDynamicScalingFactor();','double dynamicFactor = planning?input.dynamicFactor:getDynamicScalingFactor();')
body=one(body,'pair.exposure, pair.iso, pair.isoanalog, capStart, capEnd);','pair.exposure, pair.iso, pair.isoanalog, capStart, capEnd, !planning);')
for variable,member in [('mult','balance'),('isoLimit','isoLimit'),('shutterLimit','shutterLimit')]:
    field={'mult':'exposureBalanceMultiplier','isoLimit':'exposureBalanceIsoLimit','shutterLimit':'exposureBalanceShutterLimit'}[variable]
    body=one(body,f'{variable} = captureController.{field};',f'{variable} = planning?input.controls.{member}:captureController.{field};')
body=one(body,'pair.applyExposureBalance(mult, isoLimit, shutterLimit);','pair.applyExposureBalance(mult, isoLimit, shutterLimit, useTripod);')
body=one(body,'double currentManExp = captureController.getParamController().getCurrentExposureValue();','double currentManExp = planning?input.controls.manualExposureNs:captureController.getParamController().getCurrentExposureValue();')
body=one(body,'double currentManISO = captureController.getParamController().getCurrentISOValue();','double currentManISO = planning?input.controls.manualIso:captureController.getParamController().getCurrentISOValue();')
body=one(body,'        if(step != -1) {','        if(!planning && step != -1) {')
body=one(body,'        pair.denormalizeSystem();\n        if (!planning', '''        pair.denormalizeSystem();
        if(planning) {
            pair.iso=Math.max(input.isoLow,Math.min(input.isoHigh,pair.iso));
            pair.exposure=Math.max(input.timeLow,Math.min(input.timeHigh,pair.exposure));
        }
        if (!planning''')
s=s[:a]+body+s[b:]
s=one(s,'    private static double getDynamicScalingFactor() {','''    private static double getDynamicScalingFactor() {
        return getDynamicScalingFactor(IsoExpoSelector.useTripod,CaptureController.mCameraCharacteristics,CaptureController.mPreviewCaptureResult);
    }
    private static double getDynamicScalingFactor(boolean useTripod,CameraCharacteristics characteristics,CaptureResult result) {''')
# Only remove method-local lookups inside dynamic scaling.
a=s.index('    private static double getDynamicScalingFactor(boolean');b=s.index('    private static long getAutoSafeShutterNs',a)
part=s[a:b].replace('        CameraCharacteristics characteristics = CaptureController.mCameraCharacteristics;\n','').replace('        CaptureResult result = CaptureController.mPreviewCaptureResult;\n','')
s=s[:a]+part+s[b:]
s=one(s,'        public void applyExposureBalance(double k, int isoLimit, float shutterLimitSec) {','''        public void applyExposureBalance(double k, int isoLimit, float shutterLimitSec) {
            applyExposureBalance(k,isoLimit,shutterLimitSec,IsoExpoSelector.useTripod);
        }
        private void applyExposureBalance(double k,int isoLimit,float shutterLimitSec,boolean useTripod) {''')
put('selector',s)
# Parameter UI: neutral hardware reference, explicit dials become only plan inputs.
s=imports(get('param'))
for method,first in [('setShutter','        if (shutterNs == ManualParamModel.EXPOSURE_AUTO) {'),('setISO','        if (isoVal == ManualParamModel.ISO_AUTO) {'),('setEV','        builder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION, ev);')]:
    s=one(s,first,'''        if(captureController.useMonoExposurePlan1A()) {
            captureController.invalidateMonoExposurePlan1A();
            builder.set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_ON);
            builder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,0);
            captureController.rebuildPreviewBuilder();
            return;
        }
'''+first)
s=one(s,'    public boolean isManualMode() {','''    public double getMonoUserEv1A() {
        android.hardware.camera2.CameraCharacteristics chars=captureController.monoCharacteristics1A();
        android.util.Rational step=chars==null?null:chars.get(android.hardware.camera2.CameraCharacteristics.CONTROL_AE_COMPENSATION_STEP);
        double manualSteps=manualParamModel==null?0.0:manualParamModel.getCurrentEvValue();
        if(manualSteps!=0 && step==null)throw new IllegalStateException("missing_EV_step");
        return MonoExposurePlan1A.combinedEv(com.particlesdevs.photoncamera.app.PhotonCamera.getSettings().exposureCompensation,
                manualSteps,step==null?0.0:step.doubleValue());
    }
    public boolean isManualMode() {''')
put('param',s)
# Controller: same plan selected once for entire sequence, no capture-only reallocation.
s=imports(get('capture'))
s=one(s,'    public void updateMonoLivePairPreview1E(', (here/'controller.inc').read_text()+'\n    public void updateMonoLivePairPreview1E(')
s=one(s,'    public void closeCamera() {','    public void closeCamera() {\n        invalidateMonoExposurePlan1A();')
# Also invalidate when a new repeating session is configured, even if same camera was reopened.
a='''                        if (!mIsRecordingVideo) com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.configure('''
s=one(s,a,'                        invalidateMonoExposurePlan1A();\n'+a)
# At both preview request boundaries force the neutral hardware reference. Auto/manual are plan inputs.
a='''            mCaptureSession.setRepeatingRequest(mPreviewInputRequest = mPreviewRequestBuilder.build(), mCaptureCallback, mBackgroundHandler);'''
s=one(s,a,'''            if(useMonoExposurePlan1A()) {
                mPreviewRequestBuilder.set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_ON);
                mPreviewRequestBuilder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,0);
            }
'''+a)
a='''                        invalidateMonoExposurePlan1A();'''
s=one(s,a,a+'''
                        if(useMonoExposurePlan1A()) {
                            mPreviewRequestBuilder.set(CaptureRequest.CONTROL_AE_MODE,CaptureRequest.CONTROL_AE_MODE_ON);
                            mPreviewRequestBuilder.set(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION,0);
                        }''')
# Replace only the Photo/non-ZSL still method, leaving triggerZslCapture unchanged.
a=s.index('    private void captureStillPicture() {');b=s.index('            // This is the CaptureRequest.Builder',a)
block=s[a:b]
start=block.index('            final IsoExpoSelector.ExpoPair monoLivePairShutterSelector1E =');end=block.index('            SensorConfigInjector.applyToSensor',start)
oldSelector=block[start:end];block=block[:start]+block[end:]
block+='''            final MonoExposureStore1A.Selection monoSelection1A=selectMonoCapturePlan1A(monoLivePairShutterElapsedNs1E);
            final MonoExposurePlan1A monoCapturePlan1A=monoSelection1A==null?null:monoSelection1A.plan;
            if(useMonoExposurePlan1A() && monoCapturePlan1A==null) {
                mState=STATE_PREVIEW;
                unlockFocus();
                cameraEventsListener.onProcessingError("Exposure preview is not ready. Please try again.");
                return;
            }
'''+oldSelector.replace('IsoExpoSelector.GenerateExpoPair(-1, this);','monoCapturePlan1A!=null ? new IsoExpoSelector.ExpoPair(monoCapturePlan1A.exposureNs,1L,Long.MAX_VALUE,monoCapturePlan1A.iso,1,Integer.MAX_VALUE,Integer.MAX_VALUE) : IsoExpoSelector.GenerateExpoPair(-1, this);')
s=s[:a]+block+s[b:]
a=s.index('    private void captureStillPicture() {');b=s.index('    public void resetPreviewAEMode()',a) if '    public void resetPreviewAEMode()' in s[a:] else len(s)
block=s[a:b]
block=one(block,'double frametime = ExposureIndex.time2sec(IsoExpoSelector.GenerateExpoPair(-1, this).exposure);','double frametime = ExposureIndex.time2sec(monoLivePairShutterSelector1E.exposure);')
block=block.replace('IsoExpoSelector.setExpo(captureBuilder, i, this);','IsoExpoSelector.setMonoPlannedExpo1A(captureBuilder, i, this, monoCapturePlan1A);')
anchor='''                            monoLivePairPreviewAwbState1E, monoLivePairPreviewAfState1E,
                            monoLivePairPhysicalId1E, monoLivePairRotation1E);'''
block=one(block,anchor,anchor+'\n            MonoExposureDiagnostics1A.attach(monoLivePairPreviewSnapshot1E,monoSelection1A);')
s=s[:a]+block+s[b:];put('capture',s)
# Preview uses one plan, HUD consumes same stored pair, no independent selector side effects.
s=imports(get('fragment'))
a='''                        IsoExpoSelector.ExpoPair intended1A =
                                IsoExpoSelector.GenerateExpoPair(-1, captureController);'''
s=one(s,a,'''                        MonoExposurePlan1A monoPlan1A=captureController.useMonoExposurePlan1A()
                                ?captureController.updateMonoExposurePlan1A(result):null;
                        if(captureController.useMonoExposurePlan1A() && monoPlan1A==null) return;
                        IsoExpoSelector.ExpoPair intended1A = monoPlan1A==null
                                ?IsoExpoSelector.GenerateExpoPair(-1,captureController)
                                :new IsoExpoSelector.ExpoPair(monoPlan1A.exposureNs,1L,Long.MAX_VALUE,monoPlan1A.iso,1,Integer.MAX_VALUE,Integer.MAX_VALUE);''')
s=one(s,'                                textureView.setMonoExposureScale1A((float) scale1A);','''                                if(monoPlan1A!=null)textureView.setMonoExposurePlan1A(new MonoExposureStore1A.Presentation(
                                        monoPlan1A,captureController.getMonoExposureStore1A()));
                                else textureView.setMonoExposureScale1A((float) scale1A);''')
s=s.replace('IsoExpoSelector.ExpoPair expoPair = IsoExpoSelector.GenerateExpoPair(-1, captureController);','IsoExpoSelector.ExpoPair expoPair = IsoExpoSelector.monoHudPair1A(captureController);')
put('fragment',s)
s=imports(get('gl'));s=one(s,'    public void setMonoExposureScale1A(float scale) {','''    public void setMonoExposurePlan1A(MonoExposureStore1A.Presentation state) {
        if(mRenderer!=null)mRenderer.setMonoExposurePlan1A(state);
    }
    public void setMonoExposureScale1A(float scale) {''');put('gl',s)
s=imports(get('main'))
s=one(s,'    public void setMonoExposureScale1A(float scale) {','''    private volatile MonoExposureStore1A.Presentation monoPresentation1A;
    public void setMonoExposurePlan1A(MonoExposureStore1A.Presentation state) {monoPresentation1A=state;}
    public void setMonoExposureScale1A(float scale) {
        monoPresentation1A=null;''')
s=one(s,'        final float exposureForDraw2A=mMonoExposureScale1A;','        float exposureForDraw2A=mMonoExposureScale1A;\n        final MonoExposureStore1A.Presentation exposureState1A=monoPresentation1A;')
anchor='''        bindMono2A(binding2A.context);'''
s=one(s,anchor,'''        final long nowPlan1A=android.os.SystemClock.elapsedRealtimeNanos();
        final boolean planForDraw1A=exposureState1A!=null && exposureState1A.store.accepts(exposureState1A.plan,nowPlan1A)
                && exposureState1A.plan.cameraKey.equals(binding2A.cameraKey1A());
        if(planForDraw1A) {
            double frameEnergy1A=binding2A.physicalExposureEnergy1A();
            exposureForDraw2A=MonoExposurePlan1A.boundedScale(frameEnergy1A>0
                    ?MonoExposurePlan1A.energy(exposureState1A.plan.iso,exposureState1A.plan.exposureNs)/frameEnergy1A
                    :exposureState1A.plan.previewScale());
        } else if(exposureState1A!=null) exposureForDraw2A=1.0f;
'''+anchor)
anchor='''        long drawNs2A=android.os.SystemClock.elapsedRealtimeNanos();'''
s=one(s,anchor,anchor+'''
        if(planForDraw1A)exposureState1A.store.drawn(exposureState1A.plan,drawNs2A,binding2A.textureTimestampNs,exposureForDraw2A);''')
put('main',s)
# Physical observation lookup uses already accepted camera/session results; no logical-camera substitution.
s=get('gpu')
a='''    public static synchronized Binding bind(long textureTimestampNs) {'''
s=one(s,a,'''    public static final class PlanObservation1A {
        public final CaptureResult result; public final long receivedNs;
        PlanObservation1A(CaptureResult r,long n){result=r;receivedNs=n;}
    }
    public static synchronized PlanObservation1A planObservation1A(String camera,long timestamp) {
        Frame f=RESULTS.get(timestamp);long now=SystemClock.elapsedRealtimeNanos();
        if(!camera.equals(activeCamera) || f==null || !camera.equals(f.camera) || f.result==null
                || now<f.receivedNs || now-f.receivedNs>MAX_CONTEXT_AGE_NS) return null;
        return new PlanObservation1A(f.result,f.receivedNs);
    }
'''+a)
a='''        Binding(Frame f,long t,boolean e,long seq){'''
s=one(s,a,'''        public String cameraKey1A() {return frame.camera;}
        public double physicalExposureEnergy1A() {
            Integer i=frame.result==null?null:frame.result.get(CaptureResult.SENSOR_SENSITIVITY);
            Long t=frame.result==null?null:frame.result.get(CaptureResult.SENSOR_EXPOSURE_TIME);
            return i==null||i<=0||t==null||t<=0?0.0:(double)i*t;
        }
'''+a)
s=one(s,'out.put("capturePolicyArithmeticChanged",false)','out.put("capturePolicyArithmeticChanged",true).put("exposurePlanRevision","MONOAUTO1A_EXPOSUREPLAN")')
put('gpu',s)
# Completed callback records the allocation actually requested and delivered against the selected plan.
s=get('diag');anchor='''            root.put("exposureParity", parity);'''
s=one(s,anchor,anchor+'''
            JSONObject monoPlan1A=root.optJSONObject("monoExposurePlan1A");
            if(monoPlan1A!=null) {
                double target1A=monoPlan1A.optDouble("nominalEnergyIsoNs",0.0);
                Integer actualIso1A=result.get(CaptureResult.SENSOR_SENSITIVITY);
                Long actualTime1A=result.get(CaptureResult.SENSOR_EXPOSURE_TIME);
                if(target1A>0 && actualIso1A!=null && actualTime1A!=null)
                    parity.put("recordedVsSharedPlanEv",Math.log((double)actualIso1A*actualTime1A/target1A)/Math.log(2.0));
            }''')
put('diag',s)
# Make the new plan authoritative in ordinary metadata too; old audit snapshots remain labelled legacy.
s=get('export')
s=one(s,'            pair.put("writerTelemetry", telemetry());','''            pair.put("writerTelemetry", telemetry());
            if(pair.has("monoExposurePlan1A")) {
                JSONObject selected=pair.optJSONObject("monoExposurePlan1A");
                capture.put("monoExposurePlan1A",selected);
                capture.put("exposureDecisionAuthority","MONOAUTO1A_EXPOSUREPLAN");
                capture.put("legacyPhotonExposureAuditIsCaptureAuthority",false);
                pair.put("captureMode","PHOTO");
                pair.put("exposurePlanRevision","MONOAUTO1A_EXPOSUREPLAN");
            }''')
put('export',s)
# Add pure classes and change label, not package/signing.
for name in ['MonoExposurePlan1A.java','MonoExposureStore1A.java','MonoExposureDiagnostics1A.java']:
    p=root/J/'m9/exposure'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((here/name).read_bytes())
s=get('gradle');s=one(s,"versionName '0.02-mmonochrome-gl2b-monooutput1a'","versionName '0.03-mmonochrome-gl2b-monoauto1a'");put('gradle',s)
for rel,h in frozen.items():
    if H((root/rel).read_bytes())!=h:raise SystemExit('Sealed renderer/output file changed '+rel)
report={'revision':'MONOAUTO1A_EXPOSUREPLAN','baselineCommit':'ed9487ce6f5e9411cbdf99968b77af660e180811',
        'changed':{r:{'before':H(v),'after':H((root/r).read_bytes())} for r,v in before.items()},'frozen':frozen,
        'stage':'shared_plan_only_existing_MFM_assist','renderedAutoPlacementPorted':False,'allocation2GPorted':False,
        'physicalValidationCompleted':False}
(root/'MONOAUTO1A_ISOLATION.json').write_text(json.dumps(report,indent=2)+'\n')
print('MONOAUTO1A applied: shared immutable control/camera plan, GL acknowledgement and single capture allocation')
print('Renderer/DNG/shader/native and all other unchanged files sealed:',len(frozen))
