#!/usr/bin/env python3
"""Execute real immutable plan/store and real IsoExpoSelector/ParamController using deterministic device stubs."""
from pathlib import Path
import sys,re,json,hashlib,subprocess,tempfile
root=Path(sys.argv[1]).resolve();J=root/'app/src/main/java/com/particlesdevs/photoncamera'
stubs={
'android/util/Range.java':'''package android.util;public class Range<T>{T l,h;public Range(T l,T h){this.l=l;this.h=h;}public T getLower(){return l;}public T getUpper(){return h;}}''',
'android/util/SizeF.java':'''package android.util;public class SizeF{float w,h;public SizeF(float w,float h){this.w=w;this.h=h;}public float getWidth(){return w;}}''',
'android/util/Rational.java':'''package android.util;public class Rational{int a,b;public Rational(int a,int b){this.a=a;this.b=b;}public double doubleValue(){return (double)a/b;}}''',
'android/graphics/Rect.java':'''package android.graphics;public class Rect{public int width(){return 100;}}''',
'android/os/SystemClock.java':'''package android.os;public class SystemClock{public static long now=10000000000L;public static long elapsedRealtimeNanos(){return ++now;}}''',
'android/os/Build.java':'''package android.os;public class Build{public static class VERSION{public static int SDK_INT=36;}public static class VERSION_CODES{public static int R=30;}}''',
'androidx/annotation/NonNull.java':'package androidx.annotation;public @interface NonNull {}',
'android/hardware/camera2/CameraMetadata.java':'''package android.hardware.camera2;public class CameraMetadata {public static final int LENS_OPTICAL_STABILIZATION_MODE_ON=1;}''',
'org/json/JSONObject.java':'''package org.json;import java.util.*;public class JSONObject{public static final Object NULL=new Object();public Map<String,Object> m=new HashMap<>();public JSONObject(){}public JSONObject(String s){} public JSONObject put(String k,Object v){m.put(k,v);return this;}public double optDouble(String k,double d){Object o=m.get(k);return o instanceof Number?((Number)o).doubleValue():d;}public String optString(String k,String d){return m.containsKey(k)?String.valueOf(m.get(k)):d;}public JSONObject optJSONObject(String k){Object v=m.get(k);return v instanceof JSONObject?(JSONObject)v:null;}public boolean has(String k){return m.containsKey(k);}public Object get(String k){return m.get(k);}}''',
'com/particlesdevs/photoncamera/util/Log.java':'''package com.particlesdevs.photoncamera.util;public class Log{public static void v(Object...a){}public static void d(Object...a){}public static void i(Object...a){}public static void w(Object...a){}}''',
'com/particlesdevs/photoncamera/api/CameraMode.java':'''package com.particlesdevs.photoncamera.api;public enum CameraMode{PHOTO,NIGHT,MOTION,RAWVIDEO,UNLIMITED,VIDEO}''',
'com/particlesdevs/photoncamera/settings/PreferenceKeys.java':'''package com.particlesdevs.photoncamera.settings;public class PreferenceKeys{public static int getBracketingMode(){return 0;}public static int getAeMode(){return 1;}public static int getAfMode(){return 1;}}''',
'com/particlesdevs/photoncamera/processing/parameters/ExposureIndex.java':'''package com.particlesdevs.photoncamera.processing.parameters;public class ExposureIndex{public static final long sec=1000000000L;public static long sec2time(double s){return (long)(s*1e9);}public static double time2sec(long t){return t/1e9;}public static String sec2string(double s){return ""+s;}}''',
'com/particlesdevs/photoncamera/circularbarlib/control/ManualParamModel.java':'''package com.particlesdevs.photoncamera.circularbarlib.control;public class ManualParamModel extends java.util.Observable{public static final int EXPOSURE_AUTO=0,ISO_AUTO=0,FOCUS_AUTO=-1;public static final String ID_ISO="iso",ID_EV="ev",ID_SHUTTER="shutter",ID_FOCUS="focus",PANEL_INVISIBILITY="hidden";public double iso,exp,ev;public boolean isManualMode(){return iso>0||exp>0;}public double getCurrentISOValue(){return iso;}public double getCurrentExposureValue(){return exp;}public double getCurrentEvValue(){return ev;}public double getCurrentFocusValue(){return -1;}}''',
'com/particlesdevs/photoncamera/m9/M9Config.java':'''package com.particlesdevs.photoncamera.m9;public class M9Config{public static boolean usesM9Pipeline(){return true;}public static boolean isCaptureTest(){return true;}public static boolean isM9Modern(){return true;}}''',
'com/particlesdevs/photoncamera/m9/M9BacklightDiagnostic.java':'''package com.particlesdevs.photoncamera.m9;public class M9BacklightDiagnostic{public static class LiveFeedbackDecision{public boolean wouldApply;public double appliedEv,recommendedEv;public String reason="fixture_existing_assist";}public static void recordLiveFeedbackApplication(Object...a){}}''',
'com/particlesdevs/photoncamera/m9/M9M10rMfmTest1A.java':'''package com.particlesdevs.photoncamera.m9;public class M9M10rMfmTest1A{public static int planCalls,legacyCalls;public static double assist;public static M9BacklightDiagnostic.LiveFeedbackDecision evaluateForMonoPlan1A(double e,int r,boolean eligible,String why){planCalls++;M9BacklightDiagnostic.LiveFeedbackDecision d=new M9BacklightDiagnostic.LiveFeedbackDecision();d.appliedEv=eligible?assist:0;return d;}public static M9BacklightDiagnostic.LiveFeedbackDecision evaluateLiveFeedback(double e,int r,boolean b,String s){legacyCalls++;return new M9BacklightDiagnostic.LiveFeedbackDecision();}}''',
'com/particlesdevs/photoncamera/m9/M9ModernExposurePolicy.java':'''package com.particlesdevs.photoncamera.m9;public class M9ModernExposurePolicy{public static int publishes;public static class Decision{public long capStartNs,capEndNs;public boolean applied;}public static Decision adjustCaps(long t,int i,int a,long s,long e,boolean publish){if(publish)publishes++;Decision d=new Decision();d.capStartNs=s;d.capEndNs=e;return d;}public static org.json.JSONObject snapshotJson(){return new org.json.JSONObject();}}''',
'com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java':'''package com.particlesdevs.photoncamera.m9.preview;import android.hardware.camera2.CaptureResult;public class MonoGpuPreview2A{public static CaptureResult fixture;public static class PlanObservation1A{public CaptureResult result;public long receivedNs;}public static PlanObservation1A planObservation1A(String c,long t){if(fixture==null)return null;PlanObservation1A p=new PlanObservation1A();p.result=fixture;p.receivedNs=android.os.SystemClock.elapsedRealtimeNanos();return p;}}''',
'com/particlesdevs/photoncamera/capture/CaptureController.java':'''package com.particlesdevs.photoncamera.capture;import android.hardware.camera2.*;import com.particlesdevs.photoncamera.manual.ParamController;import com.particlesdevs.photoncamera.m9.exposure.*;public class CaptureController{public static CameraCharacteristics mCameraCharacteristics;public static CaptureResult mPreviewCaptureResult;public int mPreviewIso=1000,mSensorOrientation=0,cameraRotation=0,oisMode=0,exposureBalanceIsoLimit=-1;public long mPreviewExposureTime=10000000L;public float exposureBalanceMultiplier=1,exposureBalanceShutterLimit=-1;public CaptureRequest.Builder mPreviewRequestBuilder=new CaptureRequest.Builder();public ParamController param=new ParamController(this);public boolean enabled=true;public int invalidations;public MonoExposurePlan1A last;public ParamController getParamController(){return param;}public MonoExposurePlan1A getMonoExposurePlan1A(){return last;}public boolean useMonoExposurePlan1A(){return enabled;}public CameraCharacteristics monoCharacteristics1A(){return mCameraCharacteristics;}public void invalidateMonoExposurePlan1A(){invalidations++;}public void rebuildPreviewBuilder(){}public void resetPreviewAEMode(){}public void unlockFocus(){}}''',
'com/particlesdevs/photoncamera/app/PhotonCamera.java':'''package com.particlesdevs.photoncamera.app;import com.particlesdevs.photoncamera.api.CameraMode;import com.particlesdevs.photoncamera.capture.CaptureController;public class PhotonCamera{public static class Settings{public CameraMode selectedMode=CameraMode.PHOTO;public double exposureCompensation;public boolean eisPhoto;}public static class Gyro{public boolean tripod;public boolean getTripod(){return tripod;}public int getFilteredShakiness(){return 100;}}public static class Gravity{public int getCameraRotation(int i){return 0;}}public static Settings settings=new Settings();public static Gyro gyro=new Gyro();public static CaptureController controller;public static Settings getSettings(){return settings;}public static Gyro getGyro(){return gyro;}public static Gravity getGravity(){return new Gravity();}public static CaptureController getCaptureController(){return controller;}}'''
}
fields={
'CameraCharacteristics':{'SENSOR_INFO_SENSITIVITY_RANGE':'android.util.Range<Integer>','SENSOR_INFO_EXPOSURE_TIME_RANGE':'android.util.Range<Long>','SENSOR_MAX_ANALOG_SENSITIVITY':'Integer','LENS_INFO_AVAILABLE_FOCAL_LENGTHS':'float[]','SENSOR_INFO_PHYSICAL_SIZE':'android.util.SizeF','SENSOR_INFO_ACTIVE_ARRAY_SIZE':'android.graphics.Rect','LENS_INFO_AVAILABLE_OPTICAL_STABILIZATION':'int[]','CONTROL_AE_COMPENSATION_STEP':'android.util.Rational'},
'CaptureRequest':{'CONTROL_AE_MODE':'Integer','CONTROL_AE_EXPOSURE_COMPENSATION':'Integer','SENSOR_EXPOSURE_TIME':'Long','SENSOR_SENSITIVITY':'Integer','CONTROL_AF_MODE':'Integer','LENS_FOCUS_DISTANCE':'Float'},
'CaptureResult':{'SENSOR_TIMESTAMP':'Long','SENSOR_SENSITIVITY':'Integer','SENSOR_EXPOSURE_TIME':'Long','CONTROL_AE_MODE':'Integer','CONTROL_AE_EXPOSURE_COMPENSATION':'Integer','CONTROL_POST_RAW_SENSITIVITY_BOOST':'Integer','CONTROL_ZOOM_RATIO':'Float','SCALER_CROP_REGION':'android.graphics.Rect'}}
for name,fs in fields.items():
 s='package android.hardware.camera2;public class '+name+' { public static final int CONTROL_AE_MODE_OFF=0,CONTROL_AE_MODE_ON=1,CONTROL_AF_MODE_OFF=0; public static class Key<T>{}private java.util.Map<Object,Object> m=new java.util.HashMap<>(); @SuppressWarnings("unchecked") public <T>T get(Key<T>k){return (T)m.get(k);} public <T>void set(Key<T>k,T v){m.put(k,v);}'
 for key,t in fs.items():s+='public static final Key<'+t+'> '+key+'=new Key<>();'
 if name=='CaptureRequest':s+='private Object tag;public void setTag(Object v){tag=v;}public Object getTag(){return tag;}public static class Builder extends CaptureRequest{public CaptureRequest build(){return this;}}'
 stubs['android/hardware/camera2/'+name+'.java']=s+'}'
selector=(J/'processing/parameters/IsoExpoSelector.java').read_text()
for name in ['M9ExposureAudit','M9ExposureDiagnostics','M9SceneExposureDiagnostic']:
 methods=set(re.findall(name+r'\.(\w+)\(',selector));s='package com.particlesdevs.photoncamera.m9;public class '+name+'{public static int calls;'
 for m in methods:s+='public static void '+m+'(Object... args){calls++;}'
 stubs['com/particlesdevs/photoncamera/m9/'+name+'.java']=s+'}'
test=r'''
package com.particlesdevs.photoncamera.m9.exposure;
import android.hardware.camera2.*;import android.util.*;import android.os.SystemClock;
import com.particlesdevs.photoncamera.capture.CaptureController;import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.processing.parameters.IsoExpoSelector;
import com.particlesdevs.photoncamera.m9.*;import com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A;
import com.particlesdevs.photoncamera.circularbarlib.control.ManualParamModel;
public class AutoTest {
 static int checks;static void ok(boolean b){checks++;if(!b)throw new AssertionError("check "+checks);}
 static MonoExposurePlan1A.Controls controls(double ev,int iso,long t,boolean tripod){return new MonoExposurePlan1A.Controls("PHOTO",ev,t,iso,tripod,1,-1,-1,0,"crop");}
 static MonoExposurePlan1A plan(long id,long epoch,long n,MonoExposurePlan1A.Controls c){return new MonoExposurePlan1A(id,epoch,n,id,"main",c,1000,10000000,250,40000000,100,.08,"assist",0);}
 static void near(double a,double b,double eps){ok(Math.abs(a-b)<eps);}
 public static void main(String[] args)throws Exception {
  MonoExposureStore1A store=new MonoExposureStore1A();MonoExposurePlan1A.Controls c=controls(0,0,0,false);
  long n=10000000000L,epoch=store.context("main",c);MonoExposurePlan1A p=plan(1,epoch,n,c);
  ok(store.publish(p,n));ok(store.select(n).plan==p);ok(store.select(n).reason.contains("no_recent"));
  store.drawn(p,n+10,100,1);ok(store.select(n+11).plan==p);ok(store.select(n+11).reason.contains("GL_draw"));
  MonoExposurePlan1A q=plan(2,epoch,n+20,c);ok(store.publish(q,n+20));store.drawn(q,n+30,101,1);
  ok(store.select(n+25).plan==p);ok(store.select(n+31).plan==q);
  ok(store.select(n+500000031L).plan==q);ok(store.select(n+1600000000L).plan==null);
  ok(!store.accepts(p,n-1));
  MonoExposurePlan1A.Controls manual=controls(1,6400,10000000,false);
  long e2=store.context("main",manual);ok(e2!=epoch);ok(!store.accepts(q,n+40));
  ok(store.select(n+40).plan==null);ok(!store.publish(q,n+40));store.drawn(q,n+40,100,1);ok(store.select(n+41).plan==null);
  MonoExposurePlan1A m=plan(3,e2,n+50,manual);ok(store.publish(m,n+50));store.invalidate();ok(!store.accepts(m,n+51));
  long e3=store.context("tele",manual);ok(e3!=e2);ok(!store.publish(m,n+52));
  ok(!MonoExposurePlan1A.assistEligible(manual));ok(MonoExposurePlan1A.assistEligible(c));
  ok(!MonoExposurePlan1A.assistEligible(controls(-1,0,0,false)));ok(!MonoExposurePlan1A.assistEligible(controls(0,0,0,true)));
  near(MonoExposurePlan1A.combinedEv(.5,-3,1.0/3),-.5,1e-9);
  ok(MonoExposurePlan1A.boundedScale(Double.NaN)==1);ok(MonoExposurePlan1A.boundedScale(100)==16);ok(MonoExposurePlan1A.boundedScale(.0001)==.0625);
  boolean bad=false;try{controls(Double.NaN,0,0,false);}catch(IllegalArgumentException e){bad=true;}ok(bad);
  // Concurrent publish/read may see old or new WHOLE plans, never mixed ISO and shutter.
  MonoExposureStore1A raced=new MonoExposureStore1A();long raceEpoch=raced.context("main",c);
  Thread writer=new Thread(()->{for(int i=1;i<=4000;i++)raced.publish(plan(i,raceEpoch,n+i,c),n+5000);});writer.start();
  for(int i=0;i<4000;i++){MonoExposurePlan1A x=raced.latest(n+5000);ok(x==null||(x.iso==250&&x.exposureNs==40000000&&x.epoch==raceEpoch));}
  writer.join();ok(raced.latest(n+5000).id==4000);
  // REAL delivered allocator, with physical metadata and policy/Android fixture dependencies.
  CameraCharacteristics chars=new CameraCharacteristics();
  chars.set(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE,new Range<Integer>(50,12800));
  chars.set(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE,new Range<Long>(10000L,30000000000L));
  chars.set(CameraCharacteristics.SENSOR_MAX_ANALOG_SENSITIVITY,3200);
  chars.set(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE,new SizeF(13,10));
  chars.set(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS,new float[]{8.7f});
  chars.set(CameraCharacteristics.CONTROL_AE_COMPENSATION_STEP,new Rational(1,3));
  CaptureController.mCameraCharacteristics=chars;CaptureController cc=new CaptureController();PhotonCamera.controller=cc;
  CaptureResult obs=new CaptureResult();obs.set(CaptureResult.SENSOR_SENSITIVITY,1000);
  obs.set(CaptureResult.SENSOR_EXPOSURE_TIME,10000000L);obs.set(CaptureResult.SENSOR_TIMESTAMP,100L);
  obs.set(CaptureResult.CONTROL_AE_MODE,1);obs.set(CaptureResult.CONTROL_AE_EXPOSURE_COMPENSATION,0);
  MonoGpuPreview2A.fixture=obs;CaptureController.mPreviewCaptureResult=obs;
  double oldProduct=0;MonoExposurePlan1A base=null;
  for(double ev:new double[]{-2,-1,0,1,2}) {
   MonoExposurePlan1A x=IsoExpoSelector.planMonoExposure1A(cc,obs,"main",1,controls(ev,0,0,false));ok(x!=null);
   double product=MonoExposurePlan1A.energy(x.iso,x.exposureNs);ok(product>oldProduct);oldProduct=product;
   near(Math.log(product/1e10)/Math.log(2),ev,.015);if(ev==0)base=x;
  }
  M9M10rMfmTest1A.assist=.25;
  MonoExposurePlan1A assisted=IsoExpoSelector.planMonoExposure1A(cc,obs,"main",1,c);
  near(Math.log(MonoExposurePlan1A.energy(assisted.iso,assisted.exposureNs)/1e10)/Math.log(2),.25,.015);
  int legacy=M9M10rMfmTest1A.legacyCalls,planned=M9M10rMfmTest1A.planCalls;
  ok(IsoExpoSelector.fullpairs.isEmpty());ok(IsoExpoSelector.pairs.isEmpty());
  CaptureRequest.Builder builder=new CaptureRequest.Builder();
  for(int i=0;i<3;i++){IsoExpoSelector.setMonoPlannedExpo1A(builder,i,cc,assisted);
   ok(builder.get(CaptureRequest.SENSOR_SENSITIVITY)==assisted.iso);
   ok(builder.get(CaptureRequest.SENSOR_EXPOSURE_TIME)==assisted.exposureNs);ok(builder.getTag()==assisted);}
  ok(M9M10rMfmTest1A.planCalls==planned && M9M10rMfmTest1A.legacyCalls==legacy);
  ok(IsoExpoSelector.fullpairs.size()==3);ok(IsoExpoSelector.lastSelectedExposure==assisted.exposureNs);
  ok(M9ExposureAudit.calls==0 && M9ExposureDiagnostics.calls==0 && M9ModernExposurePolicy.publishes==0);
  // Physical ISO values (including above analog ceiling) survive without double normalization.
  for(int requested:new int[]{50,100,3200,6400,12800}) {
   MonoExposurePlan1A x=IsoExpoSelector.planMonoExposure1A(cc,obs,"main",1,controls(0,requested,20000000L,false));
   ok(x.iso==requested);ok(x.exposureNs==20000000);ok(x.autoEv==0);
  }
  MonoExposurePlan1A clipped=IsoExpoSelector.planMonoExposure1A(cc,obs,"main",1,controls(0,20000,40000000000L,false));
  ok(clipped.iso==12800 && clipped.exposureNs==30000000000L);
  obs.set(CaptureResult.CONTROL_AE_EXPOSURE_COMPENSATION,1);ok(IsoExpoSelector.planMonoExposure1A(cc,obs,"main",1,c)==null);
  obs.set(CaptureResult.CONTROL_AE_EXPOSURE_COMPENSATION,0);obs.set(CaptureResult.CONTROL_AE_MODE,0);
  ok(IsoExpoSelector.planMonoExposure1A(cc,obs,"main",1,c)==null);obs.set(CaptureResult.CONTROL_AE_MODE,1);
  MonoGpuPreview2A.fixture=null;ok(IsoExpoSelector.planMonoExposure1A(cc,obs,"main",1,c)==null);MonoGpuPreview2A.fixture=obs;
  // REAL ParamController: same dials are plan inputs, not a second hardware EV/ISO operation.
  ManualParamModel model=new ManualParamModel();model.iso=6400;model.exp=20000000;model.ev=3;
  cc.param.update(model,ManualParamModel.ID_ISO);cc.param.update(model,ManualParamModel.ID_SHUTTER);cc.param.update(model,ManualParamModel.ID_EV);
  ok(cc.mPreviewRequestBuilder.get(CaptureRequest.CONTROL_AE_MODE)==1);
  ok(cc.mPreviewRequestBuilder.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)==0);
  ok(cc.mPreviewRequestBuilder.get(CaptureRequest.SENSOR_SENSITIVITY)==null);
  ok(cc.param.getCurrentISOValue()==6400 && cc.param.getCurrentExposureValue()==20000000);
  PhotonCamera.settings.exposureCompensation=-.5;near(cc.param.getMonoUserEv1A(),.5,1e-9);
  ok(cc.invalidations==3);
  cc.enabled=false;cc.param.setEV(-2);ok(cc.mPreviewRequestBuilder.get(CaptureRequest.CONTROL_AE_EXPOSURE_COMPENSATION)==-2);
  System.out.println("MONOAUTO1A PASS assertions="+checks+"; real plan/store/allocator/manual controller; mocked device dependencies");
 }
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)
 for rel,src in stubs.items():f=p/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(src)
 for rel in ['processing/parameters/IsoExpoSelector.java','manual/ParamController.java',
             'm9/exposure/MonoExposurePlan1A.java','m9/exposure/MonoExposureStore1A.java','m9/exposure/MonoExposureDiagnostics1A.java']:
  f=p/'com/particlesdevs/photoncamera'/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text((J/rel).read_text())
 t=p/'com/particlesdevs/photoncamera/m9/exposure/AutoTest.java';t.write_text(test)
 subprocess.run(['javac','-d',str(p/'classes')]+[str(f) for f in p.rglob('*.java')],check=True)
 subprocess.run(['java','-cp',str(p/'classes'),'com.particlesdevs.photoncamera.m9.exposure.AutoTest'],check=True)
proof=json.loads((root/'MONOAUTO1A_ISOLATION.json').read_text())
for rel,h in proof['frozen'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==h,rel
# Real capture hooks and no renderer feedback; not just presence of a new unused class.
cap=(J/'capture/CaptureController.java').read_text();main=(J/'ui/camera/views/viewfinder/MainRenderer.java').read_text()
a=cap.index('    private void captureStillPicture()');b=cap.index('    public void resetPreviewAEMode()',a)
assert 'IsoExpoSelector.setExpo(' not in cap[a:b]
assert cap[a:b].count('setMonoPlannedExpo1A(')==2
assert 'setMonoExposurePlan1A' in (J/'ui/camera/CameraFragment.java').read_text()
assert '.store.drawn(' in main and 'physicalExposureEnergy1A()' in main
assert 'shared_auto_plan' in selector and '!planning && M9Config.isCaptureTest()' in selector
print('MONOAUTO1A active integration hooks + sealed render/DNG/native/shader checks PASS')
