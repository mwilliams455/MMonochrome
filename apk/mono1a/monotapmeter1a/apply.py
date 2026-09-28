#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, shutil, sys

if len(sys.argv)!=2:
    raise SystemExit('usage: apply.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve()
here=Path(__file__).resolve().parent
J=root/'app/src/main/java/com/particlesdevs/photoncamera'
paths={
 'swipe':J/'control/Swipe.java',
 'focus':J/'control/TouchFocus.java',
 'capture':J/'capture/CaptureController.java',
 'camera':J/'ui/camera/CameraFragment.java',
 'gl':J/'ui/camera/views/viewfinder/GLPreview.java',
 'renderer':J/'ui/camera/views/viewfinder/MainRenderer.java',
 'overlay':J/'ui/camera/views/viewfinder/SurfaceViewOverViewfinder.java',
 'selector':J/'processing/parameters/IsoExpoSelector.java',
 'assist':J/'m9/exposure/MonoPlacementAssist1D.java',
 'gpu':J/'m9/preview/MonoGpuPreview2A.java',
 'tap':J/'m9/preview/MonoTapMeter1A.java',
 'gradle':root/'app/build.gradle',
}
for k,p in paths.items():
    if k!='tap' and not p.is_file(): raise SystemExit('MONOTAPMETER1A missing '+str(p))
if paths['tap'].exists(): raise SystemExit('MONOTAPMETER1A helper already exists')

EXPECTED={
 'control/Swipe.java':'051b1d5a22602a7d48e1697aa3170ed3a0828f22f6666cb97c4cf3106a82bd9d',
 'control/TouchFocus.java':'f0d458d4fb9f59a11c4e19db02c8695a13ed0b0ce45edd6b7286a722f54a562c',
 'capture/CaptureController.java':'ed02fbf45e26cecdcc0b905faaa175eeebf4d8ef6da46ac5ee0cc7ade545f115',
 'ui/camera/CameraFragment.java':'f26d4924746173bb311f34b485b9c010f85efc0afb7d3207585ed4661a218711',
 'ui/camera/views/viewfinder/GLPreview.java':'45c05c69616c9ddd3b4291a306a21b3919cb8f6e3e1eb9886192ecda30e3cb77',
 'ui/camera/views/viewfinder/MainRenderer.java':'5397258bd978068fe8452735a788cffa04f139fe0eb7322f062b22f6726736fb',
 'ui/camera/views/viewfinder/SurfaceViewOverViewfinder.java':'f9f6ffe580ba670a6e41c8cf8336d749a30758d12c1979c1943170948595d2c3',
 'processing/parameters/IsoExpoSelector.java':'c4cee0b7480fa1f307ceb1fdd8e6f6fa80bf4b413740400ffb455c196be34a8b',
 'm9/exposure/MonoPlacementAssist1D.java':'2559e41a70beba2217176d80852eac18c50f7775d107e722f2593c2e069deeec',
 'm9/preview/MonoGpuPreview2A.java':'3d7bcb8d0271e8becb80931506dc1ac66401d5dd43dd0b7f6b79068aee1c6dea',
}

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
for rel,expected in EXPECTED.items():
    actual=sha(J/rel)
    if actual!=expected: raise SystemExit('MONOTAPMETER1A exact 1H source mismatch '+rel+' '+actual)

def one(s,a,b,name):
    c=s.count(a)
    if c!=1: raise SystemExit(f'{name} anchor count={c}')
    return s.replace(a,b,1)

def java_method(s,start_marker):
    a=s.index(start_marker);brace=s.index('{',a);depth=0
    for i in range(brace,len(s)):
        if s[i]=='{': depth+=1
        elif s[i]=='}':
            depth-=1
            if depth==0:return s[a:i+1]
    raise SystemExit('unterminated Java method '+start_marker)

frozen=[
 J/'m9/render/M9R35Renderer.java',
 J/'m9/export/MonoDngExport1A.java',
 J/'m9/export/MonoDngWriter1A.java',
 J/'m9/export/MonoLinearPlane1A.java',
 J/'m9/export/MonoPlacementMath1A.java',
 J/'m9/export/MonoPlacementProbe1A.java',
 J/'m9/M9M10rMfmTest1A.java',
 root/'app/src/main/cpp/m9color_jni.cpp',
 root/'app/src/main/assets/mono/mono_curve02_gl2a.bin',
 root/'app/src/main/assets/shaders/preview/main_fs.glsl',
]
frozen_before={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}
assist_before=paths['assist'].read_text()
auto_method_before=java_method(assist_before,'    public static Decision evaluate(boolean eligible,')

paths['tap'].parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(here/'MonoTapMeter1A.java',paths['tap'])

s=paths['swipe'].read_text()
s=one(s,
'''    private void startTouchToFocus(MotionEvent event) {
''',
'''    private void startTouchToFocus(MotionEvent event) {
        if(cameraFragment.getTouchFocus()!=null && cameraFragment.getTouchFocus().processMonoTap1A(
                event.getRawX(),event.getRawY(),
                manualModeConsole.getManualParamModel().getCurrentFocusValue()==ManualParamModel.FOCUS_AUTO))return;
''','Swipe tap intercept')
paths['swipe'].write_text(s)

s=paths['focus'].read_text()
insert='''
    /** MONOTAPMETER1A: focus if possible, but meter the selected subject even without AF. */
    public boolean processMonoTap1A(float rawX,float rawY,boolean autofocus) {
        if(captureController==null || !captureController.useMonoExposurePlan1A())return false;
        long now=SystemClock.elapsedRealtimeNanos();
        com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.Geometry g=
                com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.currentGeometry(now);
        if(g==null)return false;
        int[] origin=new int[2];textureView.getLocationOnScreen(origin);
        float x=rawX-origin[0],y=rawY-origin[1];
        if(x<0||y<0||x>=textureView.getWidth()||y>=textureView.getHeight())return true;
        if(com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.insideSelection(x,y,now)) {
            com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.clear("tap_box_return_to_auto");
            resetFocusCircle();setInitialAFAE();textureView.requestRender();return true;
        }
        if(com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.choose(x,y,now)) {
            if(autofocus)processTouchToFocus(x,y);
            textureView.requestRender();
        }
        return true;
    }
'''
s=one(s,
'''    public void processTouchToFocus(float fx, float fy) {
''',
insert+'''
    public void processTouchToFocus(float fx, float fy) {
''','TouchFocus tap method')
s=one(s,
'''            if (maxRegions(characteristics, CameraCharacteristics.CONTROL_MAX_REGIONS_AE) > 0) {
                builder.set(CaptureRequest.CONTROL_AE_REGIONS, regions);
                aeRegionsWritten = true;
            }
''',
'''            if (maxRegions(characteristics, CameraCharacteristics.CONTROL_MAX_REGIONS_AE) > 0) {
                boolean monoTap=com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A
                        .selection(SystemClock.elapsedRealtimeNanos())!=null;
                builder.set(CaptureRequest.CONTROL_AE_REGIONS,monoTap
                        ?new MeteringRectangle[]{new MeteringRectangle(0,0,0,0,0)}:regions);
                aeRegionsWritten = true;
            }
''','TouchFocus neutral HAL AE')
s=one(s,
'''    public void resetFocusCircle() {
        focusCircleView.removeCallbacks(hideFocusCircleRunnable);
''',
'''    public void resetFocusCircle() {
        com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.clear("focus_reset_or_return_to_auto");
        focusCircleView.removeCallbacks(hideFocusCircleRunnable);
''','TouchFocus clear selection')
paths['focus'].write_text(s)

# A tap generation is part of the exposure-plan control identity. This closes
# the select/replace/clear/expiry race without changing no-tap exposure math.
s=paths['capture'].read_text()
s=one(s,
'''        if(mPreviewRequestBuilder!=null) {
            metering+="|"+mPreviewRequestBuilder.get(CaptureRequest.SCALER_CROP_REGION);
            metering+="|"+java.util.Arrays.toString(mPreviewRequestBuilder.get(CaptureRequest.CONTROL_AE_REGIONS));
            if(Build.VERSION.SDK_INT>=30) metering+="|"+mPreviewRequestBuilder.get(CaptureRequest.CONTROL_ZOOM_RATIO);
        }
        return new MonoExposurePlan1A.Controls(PhotonCamera.getSettings().selectedMode.name(),
''',
'''        if(mPreviewRequestBuilder!=null) {
            metering+="|"+mPreviewRequestBuilder.get(CaptureRequest.SCALER_CROP_REGION);
            metering+="|"+java.util.Arrays.toString(mPreviewRequestBuilder.get(CaptureRequest.CONTROL_AE_REGIONS));
            if(Build.VERSION.SDK_INT>=30) metering+="|"+mPreviewRequestBuilder.get(CaptureRequest.CONTROL_ZOOM_RATIO);
        }
        metering+="|monoTapEpoch="+com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A
                .controlEpoch(SystemClock.elapsedRealtimeNanos());
        return new MonoExposurePlan1A.Controls(PhotonCamera.getSettings().selectedMode.name(),
''','capture tap generation control identity')
paths['capture'].write_text(s)

s=paths['gl'].read_text()
s=one(s,
'''    public void onPause() {
        fireOnSurfaceTextureDestroyed(getSurfaceTexture());
''',
'''    public void onPause() {
        com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.clear("preview_paused");
        fireOnSurfaceTextureDestroyed(getSurfaceTexture());
''','GLPreview pause clear')
paths['gl'].write_text(s)

s=paths['renderer'].read_text()
s=one(s,
'''    private volatile boolean mMirrorPreview;
''',
'''    private volatile boolean mMirrorPreview;
    private final int[] mMonoTapViewport1A=new int[4];
''','renderer tap viewport field')
s=one(s,
'''        GLES20.glUniform1f(uMonoExposureScale1A, exposureForDraw2A);

        GLES20.glVertexAttribPointer(vPosition, 2, GLES20.GL_FLOAT, false, 4 * 2, pVertex);
''',
'''        GLES20.glUniform1f(uMonoExposureScale1A, exposureForDraw2A);
        if(planForDraw1A && boundSourceReady2A) {
            GLES20.glGetIntegerv(GLES20.GL_VIEWPORT,mMonoTapViewport1A,0);
            int tapProbeW1A=mMonoTapViewport1A[2]>mMonoTapViewport1A[3]?64:48;
            int tapProbeH1A=mMonoTapViewport1A[2]>mMonoTapViewport1A[3]?48:64;
            com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.configure(
                    exposureState1A.plan.cameraKey,exposureState1A.plan.controls.mode,nowPlan1A,
                    mView.getWidth(),mView.getHeight(),mMonoTapViewport1A,mTexRotateMatrix,
                    mirrorForDraw2A,tapProbeW1A,tapProbeH1A);
        }

        GLES20.glVertexAttribPointer(vPosition, 2, GLES20.GL_FLOAT, false, 4 * 2, pVertex);
''','renderer configure tap geometry')
paths['renderer'].write_text(s)

s=paths['overlay'].read_text()
s=one(s,
'''                    drawAFDebugText(canvas);
                }
                surfaceHolder.unlockCanvasAndPost(canvas);
''',
'''                    drawAFDebugText(canvas);
                }
                drawMonoTap1A(canvas);
                surfaceHolder.unlockCanvasAndPost(canvas);
''','overlay draw tap')
method='''
    private void drawMonoTap1A(Canvas canvas) {
        com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.Selection s=
                com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.selection(
                        android.os.SystemClock.elapsedRealtimeNanos());
        if(s==null||s.geometry.width!=getWidth()||s.geometry.height!=getHeight())return;
        double[] r=s.viewRect();
        rectPaint.setColor(Color.YELLOW);rectPaint.setStyle(Paint.Style.STROKE);
        canvas.drawRect((float)r[0],(float)r[1],(float)r[2],(float)r[3],rectPaint);
        float x=8*mDensity;
        float y=Math.max(18*mDensity,Math.min(getHeight()-22*mDensity,(float)r[3]+18*mDensity));
        canvas.drawText(com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.status(),x,y,hudPaint);
        canvas.drawText("Tap box: AUTO · expires in 15s",x,y+16*mDensity,hudPaint);
    }
'''
s=one(s,
'''    private void drawHUD(Canvas canvas) {
''',method+'''
    private void drawHUD(Canvas canvas) {
''','overlay tap method')
s=one(s,
'''                canvas.drawColor(0, PorterDuff.Mode.CLEAR);//Clears the canvas
                mHolder.unlockCanvasAndPost(canvas);
''',
'''                canvas.drawColor(0, PorterDuff.Mode.CLEAR);//Clears the canvas
                drawMonoTap1A(canvas);
                mHolder.unlockCanvasAndPost(canvas);
''','overlay clear retains tap')
paths['overlay'].write_text(s)

s=paths['camera'].read_text()
s=one(s,
'''            } else {
                if (surfaceView.isCanvasDrawn) {
                    surfaceView.clear();
                }
            }
''',
'''            } else {
                if (com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.selection(
                        android.os.SystemClock.elapsedRealtimeNanos()) != null) {
                    surfaceView.refresh();
                } else if (surfaceView.isCanvasDrawn) {
                    surfaceView.clear();
                }
            }
''','CameraFragment preserve tap overlay')
paths['camera'].write_text(s)

s=paths['gpu'].read_text()
s=one(s,
'''    private static volatile PlacementObservation1D lastPlacement1D;
    private static long lastCaptureBoundaryNs1E;
''',
'''    private static volatile PlacementObservation1D lastPlacement1D;
    private static volatile TapObservation1A lastTapObservation1A;
    private static long lastCaptureBoundaryNs1E;
''','gpu tap observation field')
s=one(s,
'''            lastDraw=null; lastProbe=null; lastPlacement1D=null; lastCaptureBoundaryNs1E=0;
''',
'''            lastDraw=null; lastProbe=null; lastPlacement1D=null; lastTapObservation1A=null; lastCaptureBoundaryNs1E=0;
            MonoTapMeter1A.clear("camera_session_change");
''','gpu session clear tap')
s=one(s,
'''        if(probe!=null) { lastProbe=d; PROBES.addLast(d); while(PROBES.size()>4) PROBES.removeFirst();
            lastPlacement1D=placementFromProbe1D(d); }
''',
'''        if(probe!=null) { lastProbe=d; PROBES.addLast(d); while(PROBES.size()>4) PROBES.removeFirst();
            lastPlacement1D=placementFromProbe1D(d);
            lastTapObservation1A=tapFromProbe1A(d); }
''','gpu publish tap measurement')
anchor='''    public static synchronized void captureBoundary1E(String camera,long shutterElapsedNs) {
'''
tap_code=r'''    public static final class TapObservation1A {
        public final boolean valid;
        public final String reason,camera;
        public final long selectionId,capturedElapsedNs,sessionId;
        public final double ageMs,planScale,baseMedian,baseQ25,baseQ90,baseQ95;
        public final double scaledClipFraction,sensorRgbMaxQ95,sensorRgbMaxQ99,sensorRgbMaxClipFraction;
        public final int sampleCount;
        TapObservation1A(boolean valid,String reason,String camera,long selectionId,long captured,long session,
                double ageMs,double planScale,double median,double q25,double q90,double q95,double clip,
                double sensorQ95,double sensorQ99,double sensorClip,int samples) {
            this.valid=valid;this.reason=reason;this.camera=camera;this.selectionId=selectionId;
            capturedElapsedNs=captured;sessionId=session;this.ageMs=ageMs;this.planScale=planScale;
            baseMedian=median;baseQ25=q25;baseQ90=q90;baseQ95=q95;scaledClipFraction=clip;
            sensorRgbMaxQ95=sensorQ95;sensorRgbMaxQ99=sensorQ99;
            sensorRgbMaxClipFraction=sensorClip;sampleCount=samples;
        }
        TapObservation1A withAge(double ms) {
            return new TapObservation1A(valid,reason,camera,selectionId,capturedElapsedNs,sessionId,ms,planScale,
                    baseMedian,baseQ25,baseQ90,baseQ95,scaledClipFraction,sensorRgbMaxQ95,
                    sensorRgbMaxQ99,sensorRgbMaxClipFraction,sampleCount);
        }
        static TapObservation1A invalid(String reason,String camera,long id,long captured,long session) {
            return new TapObservation1A(false,reason,camera,id,captured,session,0.0,1.0,
                    Double.NaN,Double.NaN,Double.NaN,Double.NaN,0.0,
                    Double.NaN,Double.NaN,0.0,0);
        }
    }

    private static TapObservation1A tapFromProbe1A(Draw d) {
        String camera=d==null?"":d.binding.frame.camera;long session=d==null?-1:d.binding.sessionId;
        long captured=d==null?0:d.elapsedNs;
        MonoTapMeter1A.Selection s=MonoTapMeter1A.selection(captured);
        if(s==null)return TapObservation1A.invalid("tap_inactive",camera,-1,captured,session);
        if(d==null||d.probe==null||d.w<=0||d.h<=0)
            return TapObservation1A.invalid("tap_probe_missing",camera,s.id,captured,session);
        if(!camera.equals(s.geometry.camera)||s.geometry.probeWidth!=d.w||s.geometry.probeHeight!=d.h)
            return TapObservation1A.invalid("tap_geometry_mismatch",camera,s.id,captured,session);
        if(!d.targetEnabled||d.probeError!=null||!(d.scale>0.0f)||!Float.isFinite(d.scale))
            return TapObservation1A.invalid("tap_source1d_probe_not_ready",camera,s.id,captured,session);
        long[] hist=new long[4096],sensorHist=new long[256];int samples=0,clipped=0,sensorClipped=0;
        for(int y=s.y0;y<s.y1;y++)for(int x=s.x0;x<s.x1;x++) {
            int i=(y*d.w+x)*4;if(i<0||i+3>=d.probe.length||(d.probe[i+3]&255)==0)continue;
            int code=((d.probe[i]&255)<<8)|(d.probe[i+1]&255),sensor=d.probe[i+2]&255;
            hist[code>>>4]++;sensorHist[sensor]++;samples++;
            if(code>=65535)clipped++;if(sensor>=255)sensorClipped++;
        }
        if(samples<4)return TapObservation1A.invalid("tap_insufficient_samples",camera,s.id,captured,session);
        double scale=d.scale;
        double q25=placementBinValue1D(placementQuantileBin1D(hist,samples,.25))/65535.0/scale;
        double median=placementBinValue1D(placementQuantileBin1D(hist,samples,.50))/65535.0/scale;
        double q90=placementBinValue1D(placementQuantileBin1D(hist,samples,.90))/65535.0/scale;
        double q95=placementBinValue1D(placementQuantileBin1D(hist,samples,.95))/65535.0/scale;
        int sensorQ95=placementQuantileBin1D(sensorHist,samples,.95);
        int sensorQ99=placementQuantileBin1D(sensorHist,samples,.99);
        return new TapObservation1A(true,"fresh_exact_selected_SOURCE1D_patch",camera,s.id,captured,session,0.0,scale,
                median,q25,q90,q95,clipped/(double)samples,sensorQ95/255.0,sensorQ99/255.0,
                sensorClipped/(double)samples,samples);
    }

    public static synchronized TapObservation1A tapObservation1A(String camera) {
        long now=SystemClock.elapsedRealtimeNanos();MonoTapMeter1A.Selection s=MonoTapMeter1A.selection(now);
        if(s==null)return TapObservation1A.invalid("tap_inactive",camera,-1,0,activeSession);
        TapObservation1A p=lastTapObservation1A;
        if(p==null)return TapObservation1A.invalid("no_tap_probe_yet",camera,s.id,0,activeSession);
        if(camera==null||!camera.equals(activeCamera)||!camera.equals(s.geometry.camera)||!camera.equals(p.camera)
                ||p.sessionId!=activeSession||p.selectionId!=s.id)
            return TapObservation1A.invalid("tap_generation_or_context_mismatch",camera,s.id,p.capturedElapsedNs,activeSession);
        if(p.capturedElapsedNs<s.createdNs)
            return TapObservation1A.invalid("tap_probe_precedes_selection",camera,s.id,p.capturedElapsedNs,activeSession);
        if(p.capturedElapsedNs<=lastCaptureBoundaryNs1E)
            return TapObservation1A.invalid("tap_probe_precedes_last_capture_boundary",camera,s.id,p.capturedElapsedNs,activeSession);
        if(now<p.capturedElapsedNs||now-p.capturedElapsedNs>750000000L)
            return TapObservation1A.invalid("tap_probe_stale_over_750ms",camera,s.id,p.capturedElapsedNs,activeSession);
        return p.withAge((now-p.capturedElapsedNs)/1e6);
    }

'''
s=one(s,anchor,tap_code+anchor,'gpu tap observation code')
paths['gpu'].write_text(s)

s=paths['assist'].read_text()
s=one(s,
'''import com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A;
''',
'''import com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A;
import com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A;
''','assist tap import')
s=one(s,
'''    public static final double BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION = 0.005;
''',
'''    public static final double BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION = 0.005;

    public static final String TAP_REVISION = "MONOTAPMETER1A_LOWKEYREAD1A";
    public static final double TAP_MEDIAN_FLOOR_SOURCE1D = 0.050;
    public static final double TAP_Q25_FLOOR_SOURCE1D = 0.015;
    public static final double TAP_MEDIAN_APPEARANCE_CEILING_SOURCE1D = 0.065;
    public static final double TAP_MAX_POSITIVE_EV = 0.40;
''','assist tap constants')
tap_policy=r'''    public static Decision evaluateTap(boolean eligible,
            MonoGpuPreview2A.PlacementObservation1D placement,
            MonoGpuPreview2A.TapObservation1A tap,
            MonoTapMeter1A.Selection selection) {
        JSONObject d=new JSONObject();double applied=0.0;String reason="monotap1a_waiting";
        long generation=selection==null?-1:selection.id;
        try {
            d.put("schema","mmonochrome.tapmeter.v1a").put("revision",TAP_REVISION)
                    .put("tapSelectionRevision",MonoTapMeter1A.REVISION)
                    .put("meterDomain","SOURCE1D_XYZ_D50_Y_before_curve02")
                    .put("positiveOnly",true).put("HDR",false).put("localRelighting",false)
                    .put("postCaptureRescue",false).put("onePhysicalExposure",true)
                    .put("tapMedianFloorSource1D",TAP_MEDIAN_FLOOR_SOURCE1D)
                    .put("tapQ25FloorSource1D",TAP_Q25_FLOOR_SOURCE1D)
                    .put("tapMedianAppearanceCeilingSource1D",TAP_MEDIAN_APPEARANCE_CEILING_SOURCE1D)
                    .put("tapPositiveLimitEv",TAP_MAX_POSITIVE_EV)
                    .put("automaticFrameReferenceSource1D",REFERENCE_TARGET)
                    .put("tapDoesNotNormalizeToFrameReference",true)
                    .put("curve02ApproxCodes",new JSONObject().put("medianFloor",51)
                            .put("q25Floor",19).put("medianAppearanceCeiling",64)
                            .put("automaticFrameReference",83));
            if(selection!=null)d.put("tapSelection",selection.json(android.os.SystemClock.elapsedRealtimeNanos()));
            if(!eligible) {
                reason="monotap1a_manual_ev_iso_shutter_or_tripod_bypass";
                MonoTapMeter1A.status(generation,"TAP PAUSED");return finish(d,0.0,reason);
            }
            if(tap==null||!tap.valid) {
                reason="monotap1a_wait_for_fresh_selected_patch"+(tap==null?"":"_"+tap.reason);
                MonoTapMeter1A.status(generation,"TAP …");d.put("tapMeasurementFresh",false);
                return finish(d,0.0,reason);
            }
            if(placement==null||!placement.valid) {
                reason="monotap1a_wait_for_fresh_global_headroom"+(placement==null?"":"_"+placement.reason);
                MonoTapMeter1A.status(generation,"TAP …");d.put("tapMeasurementFresh",true).put("globalHeadroomFresh",false);
                return finish(d,0.0,reason);
            }
            double median=tap.baseMedian,q25=tap.baseQ25;
            if(!finite(median)||median<=0.0||!finite(q25)||q25<0.0) {
                reason="monotap1a_invalid_selected_patch";MonoTapMeter1A.status(generation,"TAP …");
                return finish(d,0.0,reason);
            }
            d.put("tapMeasurementFresh",true).put("globalHeadroomFresh",true)
                    .put("tapAgeMs",tap.ageMs).put("tapPlanScale",tap.planScale)
                    .put("tapBaseMedian",median).put("tapBaseQ25",q25)
                    .put("tapBaseQ90",tap.baseQ90).put("tapBaseQ95",tap.baseQ95)
                    .put("tapScaledClipFraction",tap.scaledClipFraction)
                    .put("tapSensorRgbMaxQ95",tap.sensorRgbMaxQ95)
                    .put("tapSensorRgbMaxQ99",tap.sensorRgbMaxQ99)
                    .put("tapSensorRgbMaxClipFraction",tap.sensorRgbMaxClipFraction)
                    .put("tapSampleCount",tap.sampleCount);

            double medianNeed=median<TAP_MEDIAN_FLOOR_SOURCE1D
                    ?log2(TAP_MEDIAN_FLOOR_SOURCE1D/median):0.0;
            double q25Need=q25<TAP_Q25_FLOOR_SOURCE1D
                    ?log2(TAP_Q25_FLOOR_SOURCE1D/Math.max(q25,1.0e-6)):0.0;
            double requested=Math.max(medianNeed,q25Need);
            double appearanceHeadroom=Math.max(0.0,log2(TAP_MEDIAN_APPEARANCE_CEILING_SOURCE1D/median));
            double appearanceBound=Math.min(TAP_MAX_POSITIVE_EV,appearanceHeadroom);

            double q998=placement.baseQ99_8;
            double strictQ998=finite(q998)&&q998>0.0?log2(LIVE_SOURCE_Q998_LIMIT/q998):0.0;
            double strictClip=placement.scaledClipFraction>0.0
                    ?log2(LIVE_SOURCE_Q998_LIMIT*placement.planScale):Double.POSITIVE_INFINITY;
            double strictHeadroom=Math.max(0.0,Math.min(strictQ998,strictClip));
            double broadHeadroom=finite(placement.sensorRgbMaxQ99)&&placement.sensorRgbMaxQ99>0.0
                    ?log2(BROAD_TAIL_Q99_TARGET/placement.sensorRgbMaxQ99):Double.NaN;
            boolean broadEligible=finite(broadHeadroom)&&broadHeadroom>0.0
                    &&finite(placement.sensorRgbMaxClipFraction)
                    &&placement.sensorRgbMaxClipFraction<=BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION
                    &&placement.sensorRgbMaxQ99<BROAD_TAIL_Q99_TARGET;
            double globalHeadroom=Math.max(strictHeadroom,broadEligible?Math.max(0.0,broadHeadroom):0.0);

            double candidate=Math.min(requested,appearanceBound);
            applied=Math.min(candidate,Math.min(MAX_POSITIVE_EV,globalHeadroom));
            if(applied<DEAD_BAND_EV)applied=0.0;
            boolean readable=requested<=DEAD_BAND_EV;
            boolean appearanceLimited=requested>appearanceBound+1.0e-9;
            boolean highlightLimited=candidate>globalHeadroom+1.0e-9;
            d.put("tapMedianNeedEv",medianNeed).put("tapQ25NeedEv",q25Need)
                    .put("tapRequestedReadabilityEv",requested)
                    .put("tapAppearanceHeadroomEv",appearanceHeadroom)
                    .put("tapAppearanceBoundEv",appearanceBound)
                    .put("strictGlobalHeadroomEv",strictHeadroom)
                    .put("broadTailEligibleFromExplicitTapIntent",broadEligible)
                    .put("broadTailGlobalHeadroomEv",finite(broadHeadroom)?broadHeadroom:JSONObject.NULL)
                    .put("selectedGlobalHeadroomEv",globalHeadroom)
                    .put("appearanceLimited",appearanceLimited)
                    .put("highlightLimited",highlightLimited)
                    .put("predictedTapMedianAfterAssist",median*Math.pow(2.0,applied))
                    .put("predictedTapQ25AfterAssist",q25*Math.pow(2.0,applied))
                    .put("predictedGlobalSourceQ99_8AfterAssist",q998*Math.pow(2.0,applied));
            if(readable) {
                applied=0.0;reason="monotap1a_subject_already_readable_lowkey";
                MonoTapMeter1A.status(generation,"TAP 0.00");
            } else if(applied<=0.0) {
                reason=highlightLimited?"monotap1a_highlight_budget_blocks_lift":"monotap1a_lowkey_appearance_floor_blocks_lift";
                MonoTapMeter1A.status(generation,highlightLimited?"TAP LIMITED":"TAP LOW-KEY");
            } else if(highlightLimited) {
                reason="monotap1a_highlight_limited_subject_lift";
                MonoTapMeter1A.status(generation,String.format(java.util.Locale.ROOT,"TAP %+.2f · LIMITED",applied));
            } else if(appearanceLimited) {
                reason="monotap1a_lowkey_appearance_limited_subject_lift";
                MonoTapMeter1A.status(generation,String.format(java.util.Locale.ROOT,"TAP %+.2f · LOW-KEY",applied));
            } else {
                reason="monotap1a_bounded_subject_readability_lift";
                MonoTapMeter1A.status(generation,String.format(java.util.Locale.ROOT,"TAP %+.2f",applied));
            }
            d.put("requestedSubjectEvBeforeAllocator",applied);
            return finish(d,applied,reason);
        } catch(Throwable t) {
            try{d.put("error",t.toString());}catch(Throwable ignored){}
            MonoTapMeter1A.status(generation,"TAP …");
            return finish(d,0.0,"monotap1a_exception_no_assist");
        }
    }

'''
s=one(s,
'''    private static Decision finish(JSONObject d, double ev, String reason) {
''',
tap_policy+'''    private static Decision finish(JSONObject d, double ev, String reason) {
''','assist tap policy')
paths['assist'].write_text(s)

s=paths['selector'].read_text()
old='''        M9BacklightDiagnostic.LiveFeedbackDecision feedback=M9M10rMfmTest1A.evaluateForMonoPlan1A(
                MonoExposurePlan1A.energy(iso,exposure)/1e9,rotation,eligible,
                eligible?"eligible_mono_shared_auto_plan":"mono_manual_ev_or_tripod_bypass");
        MonoPlacementAssist1D.Decision placement1D=MonoPlacementAssist1D.evaluate(
                eligible,feedback,M9M10rMfmTest1A.monoPlanSnapshot1D(),
                com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.placementObservation1D(cameraKey));
'''
new='''        final long tapNow1A=android.os.SystemClock.elapsedRealtimeNanos();
        com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.Selection tap1A=
                com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.selection(tapNow1A);
        if(tap1A!=null && (!cameraKey.equals(tap1A.geometry.camera)||!controls.mode.equals(tap1A.geometry.mode))) {
            com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.clear("plan_context_change");tap1A=null;
        }
        MonoPlacementAssist1D.Decision placement1D;
        if(tap1A!=null) {
            placement1D=MonoPlacementAssist1D.evaluateTap(eligible,
                    com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.placementObservation1D(cameraKey),
                    com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.tapObservation1A(cameraKey),tap1A);
        } else {
            M9BacklightDiagnostic.LiveFeedbackDecision feedback=M9M10rMfmTest1A.evaluateForMonoPlan1A(
                    MonoExposurePlan1A.energy(iso,exposure)/1e9,rotation,eligible,
                    eligible?"eligible_mono_shared_auto_plan":"mono_manual_ev_or_tripod_bypass");
            placement1D=MonoPlacementAssist1D.evaluate(
                    eligible,feedback,M9M10rMfmTest1A.monoPlanSnapshot1D(),
                    com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.placementObservation1D(cameraKey));
        }
'''
s=one(s,old,new,'selector tap routing')
s=one(s,
'''        int flags=(pair.isIsoLimited?1:0)|(pair.isShutterLimited?2:0)|(pair.isIsoManualOverLimit?4:0)
                |(pair.isShutterManualOverLimit?8:0)|(pair.isShutterTripodBypassed?16:0);
''',
'''        int flags=(pair.isIsoLimited?1:0)|(pair.isShutterLimited?2:0)|(pair.isIsoManualOverLimit?4:0)
                |(pair.isShutterManualOverLimit?8:0)|(pair.isShutterTripodBypassed?16:0);
        if(tap1A!=null && placement1D.appliedEv>0.0 && (flags&3)!=0)
            com.particlesdevs.photoncamera.m9.preview.MonoTapMeter1A.status(tap1A.id,
                    String.format(java.util.Locale.ROOT,"TAP %+.2f · LIMITED",placement1D.appliedEv));
''','selector physical limit status')
paths['selector'].write_text(s)

g=paths['gradle'].read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m:raise SystemExit('versionName missing')
g=g[:m.start(1)]+m.group(1)+'-monotapmeter1b-lowkeyread1a-intentboundary1a'+g[m.end(1):]
paths['gradle'].write_text(g)

auto_method_after=java_method(paths['assist'].read_text(),'    public static Decision evaluate(boolean eligible,')
if auto_method_after!=auto_method_before:
    raise SystemExit('MONOTAPMETER1A changed existing no-tap MonoPlacementAssist evaluate() body')

frozen_after={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}
if frozen_before!=frozen_after:
    raise SystemExit('MONOTAPMETER1A frozen photographic seam changed: '+repr([k for k in frozen_before if frozen_before[k]!=frozen_after.get(k)]))

proof={
 'revision':'MONOTAPMETER1B_LOWKEYREAD1A_INTENTBOUNDARY1A',
 'parent':'MONOOUTPUT1H_SAVELOOKUP1A / MONOAUTO1D_PLACEMENTASSIST1E_BUFFERHYGIENE1A',
 'selectionLifetimeSeconds':15,
 'tapPositiveOnly':True,
 'tapMedianFloorSource1D':0.050,
 'tapQ25FloorSource1D':0.015,
 'tapMedianAppearanceCeilingSource1D':0.065,
 'tapMaxPositiveEv':0.40,
 'automaticFrameReferenceSource1D':0.107*(8192.0/10000.0),
 'curve02ApproxCodes':{'tapMedianFloor':51,'tapQ25Floor':19,'tapMedianAppearanceCeiling':64,'automaticFrameReference':83},
 'tapOverridesSubjectIntentGateOnly':True,
 'strictAndBroadTailHighlightSafetyRetained':True,
 'vendorTapAeNeutralizedWhileSelectionActive':True,
 'oneGlobalCaptureExposure':True,
 'HDR':False,'localRelighting':False,'postCaptureRescue':False,
 'measurementMaxAgeMs':750,'measurementInvalidatedByExisting1EShutterBoundary':True,
 'selectionRetainedAcrossShutter':True,
 'tapGenerationInExposureControlIdentity':True,
 'selectionReplaceClearExpiryInvalidateOldPlanEligibility':True,
 'noTapAutomaticPolicyMethodByteIdentical':True,
 'rendererChanged':False,'dngPixelMathChanged':False,'curve02Changed':False,
 'frozen':frozen_after,
 'runtimeChanged':[str(paths[k].relative_to(root)) for k in ['swipe','focus','capture','camera','gl','renderer','overlay','selector','assist','gpu','tap']],
}
(root/'MONOTAPMETER1A_ISOLATION.json').write_text(json.dumps(proof,indent=2)+'\n')
print(json.dumps(proof,indent=2))
