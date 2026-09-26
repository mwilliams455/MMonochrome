#!/usr/bin/env python3
from pathlib import Path
import json, subprocess, sys, tempfile

if len(sys.argv)!=2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"

# Exposure-store host test: older drawn plans may not win against a newer latest plan,
# and a shutter boundary invalidates all prior tokens.
with tempfile.TemporaryDirectory() as d:
    p=Path(d)
    pkg=p/"com/particlesdevs/photoncamera/m9/exposure";pkg.mkdir(parents=True,exist_ok=True)
    (pkg/"MonoExposurePlan1A.java").write_text((J/"m9/exposure/MonoExposurePlan1A.java").read_text())
    (pkg/"MonoExposureStore1A.java").write_text((J/"m9/exposure/MonoExposureStore1A.java").read_text())
    (pkg/"StoreTest.java").write_text(r'''
package com.particlesdevs.photoncamera.m9.exposure;
public class StoreTest {
 static int n; static void ok(boolean b){n++;if(!b)throw new AssertionError("check "+n);}
 static MonoExposurePlan1A.Controls controls(){
  return new MonoExposurePlan1A.Controls("PHOTO",0,0,0,false,1f,6400,1f,0,"session");
 }
 static MonoExposurePlan1A plan(long id,long epoch,long created,long exp){
  return new MonoExposurePlan1A(id,epoch,created,100,"2/2",controls(),50,1000000,50,exp,100,.2,"test",0);
 }
 public static void main(String[] a){
  MonoExposureStore1A s=new MonoExposureStore1A();
  long e=s.context("2/2",controls());
  MonoExposurePlan1A p1=plan(100,e,1000,1100000);
  ok(s.publish(p1,1000)); s.drawn(p1,1100,10,1.1f);
  // New scene plan exists but has not reached GL yet.
  MonoExposurePlan1A p2=plan(200,e,1200,1400000);
  ok(s.publish(p2,1200));
  MonoExposureStore1A.Selection x=s.select(1250);
  ok(x.plan!=null && x.plan.id==200);
  ok(x.reason.contains("stale_targets_skipped"));
  s.drawn(p2,1260,20,1.4f);
  x=s.select(1270);
  ok(x.plan!=null && x.plan.id==200);
  ok(x.reason.contains("latest_plan_recent_pre_shutter_GL_draw"));
  s.captureBoundary(1280);
  ok(s.latest(1290)==null);
  // In-flight publication from the old epoch must be rejected after shutter.
  MonoExposurePlan1A old=plan(300,e,1290,1500000);
  ok(!s.publish(old,1290));
  long e2=s.context("2/2",controls());
  ok(e2!=e);
  MonoExposurePlan1A fresh=plan(400,e2,1300,1500000);
  ok(s.publish(fresh,1300));
  ok(s.latest(1301).id==400);
  System.out.println("BUFFERHYGIENE store PASS assertions="+n);
 }
}
''')
    subprocess.run(["javac","-d",str(p/"classes")]+[str(x) for x in p.rglob("*.java")],check=True)
    subprocess.run(["java","-cp",str(p/"classes"),"com.particlesdevs.photoncamera.m9.exposure.StoreTest"],check=True)

# Placement policy host test.
with tempfile.TemporaryDirectory() as d:
    p=Path(d)
    stubs={
      "org/json/JSONObject.java":r'''
package org.json; import java.util.*;
public class JSONObject {
 public static final Object NULL=new Object(); private final Map<String,Object> m=new HashMap<>();
 public JSONObject(){} public JSONObject(String s){} public JSONObject put(String k,Object v){m.put(k,v);return this;}
 public double optDouble(String k,double d){Object v=m.get(k);return v instanceof Number?((Number)v).doubleValue():d;}
 public String toString(){return "{}";}
}
''',
      "com/particlesdevs/photoncamera/m9/M9BacklightDiagnostic.java":r'''
package com.particlesdevs.photoncamera.m9;
public class M9BacklightDiagnostic {
 public static class LiveFeedbackDecision {
  public final boolean valid,wouldApply; public final double recommendedEv,appliedEv; public final String reason;
  public LiveFeedbackDecision(boolean v,boolean w,double r,double a,String s,Object o){valid=v;wouldApply=w;recommendedEv=r;appliedEv=a;reason=s;}
 }
}
''',
      "com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java":r'''
package com.particlesdevs.photoncamera.m9.preview;
public class MonoGpuPreview2A {
 public static class PlacementObservation1D {
  public final boolean valid; public final String reason,camera; public final long capturedElapsedNs,sessionId;
  public final double ageMs,planScale,scaledCenterWeightedMedian,baseCenterWeightedMedian,scaledQ99_8,baseQ99_8,scaledClipFraction;
  public final double sensorRgbMaxQ95,sensorRgbMaxQ99,sensorRgbMaxQ99_8,sensorRgbMaxClipFraction; public final int sampleCount;
  public PlacementObservation1D(boolean v,String why,double median,double q998,double q99,double clip){
   valid=v;reason=why;camera="2/2";capturedElapsedNs=1;sessionId=1;ageMs=100;planScale=1;
   scaledCenterWeightedMedian=median;baseCenterWeightedMedian=median;scaledQ99_8=q998;baseQ99_8=q998;scaledClipFraction=0;
   sensorRgbMaxQ95=.27;sensorRgbMaxQ99=q99;sensorRgbMaxQ99_8=1;sensorRgbMaxClipFraction=clip;sampleCount=3072;
  }
 }
}
'''
    }
    for rel,src in stubs.items():
        f=p/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(src)
    pol=p/"com/particlesdevs/photoncamera/m9/exposure/MonoPlacementAssist1D.java"
    pol.parent.mkdir(parents=True,exist_ok=True)
    pol.write_text((J/"m9/exposure/MonoPlacementAssist1D.java").read_text())
    t=p/"com/particlesdevs/photoncamera/m9/exposure/PolicyTest.java"
    t.write_text(r'''
package com.particlesdevs.photoncamera.m9.exposure;
import org.json.JSONObject; import com.particlesdevs.photoncamera.m9.M9BacklightDiagnostic;
import com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A;
public class PolicyTest {
 static int n;static void ok(boolean b){n++;if(!b)throw new AssertionError("check "+n);}
 static void near(double a,double b,double e){ok(Math.abs(a-b)<=e);}
 static JSONObject geo(){return new JSONObject().put("sceneSpreadEv",3.37).put("brightRegionFraction",.375)
  .put("darkRegionFraction",.458).put("upperVsLowerEv",1.09).put("edgeVsInnerEv",-.36)
  .put("integralVsCenterEv",-.10).put("integralVsLowerEv",1.09).put("negativeCandidateEv",0);}
 static M9BacklightDiagnostic.LiveFeedbackDecision m(double e){return new M9BacklightDiagnostic.LiveFeedbackDecision(true,true,e,e,"positive",null);}
 public static void main(String[] a){
  ok(MonoPlacementAssist1D.REVISION.equals("MONOAUTO1D_PLACEMENTASSIST1E_BUFFERHYGIENE1A"));
  // Stale/missing placement must never bypass the highlight gate through full MFM fallback.
  MonoGpuPreview2A.PlacementObservation1D stale=new MonoGpuPreview2A.PlacementObservation1D(false,"placement_probe_stale_over_750ms",.02,.7,.6,0);
  MonoPlacementAssist1D.Decision d=MonoPlacementAssist1D.evaluate(true,m(.5),geo(),stale);
  near(d.appliedEv,0,1e-12);ok(d.reason.contains("wait_for_fresh_placement"));
  // The validated BROADTAIL05 arithmetic is unchanged when placement is fresh.
  MonoGpuPreview2A.PlacementObservation1D fresh=new MonoGpuPreview2A.PlacementObservation1D(true,"fresh",.016744418778776967,.884956036021894,.6862745098039216,.0026041666666666665);
  d=MonoPlacementAssist1D.evaluate(true,m(.32700269262775195),geo(),fresh);
  near(d.appliedEv,.32700269262775195,1e-12);ok(d.reason.contains("broadtail"));
  System.out.println("BUFFERHYGIENE policy PASS assertions="+n);
 }
}
''')
    subprocess.run(["javac","-d",str(p/"classes")]+[str(x) for x in p.rglob("*.java")],check=True)
    subprocess.run(["java","-cp",str(p/"classes"),"com.particlesdevs.photoncamera.m9.exposure.PolicyTest"],check=True)

store=(J/"m9/exposure/MonoExposureStore1A.java").read_text()
gpu=(J/"m9/preview/MonoGpuPreview2A.java").read_text()
assist=(J/"m9/exposure/MonoPlacementAssist1D.java").read_text()
capture=(J/"capture/CaptureController.java").read_text()
proof=json.loads((root/"MONOAUTO1D_PLACEMENTASSIST1E_BUFFERHYGIENE1A_ISOLATION.json").read_text())

assert "captureBoundary(long shutterNs)" in store
assert "d.plan.id!=current.id" in store
assert "stale_targets_skipped" in store
assert "captureBoundary1E" in gpu
assert "placement_probe_precedes_last_capture_boundary" in gpu
assert "750000000L" in gpu
assert "stalePlacementMfmFallbackSuppressed" in assist
assert "monoauto1e_wait_for_fresh_placement" in assist
assert "monoExposureStore1A.captureBoundary(shutterNs)" in capture
assert "MonoGpuPreview2A.captureBoundary1E" in capture
assert proof["broadTailCalibrationChanged"] is False
assert proof["mfmMathChanged"] is False
assert proof["sourcePlacementMathChanged"] is False
assert proof["jpegRendererChanged"] is False
assert proof["dngSamplesChanged"] is False
assert proof["curve02Changed"] is False
assert proof["HDR"] is False

report={
 "status":"PASS",
 "revision":"MONOAUTO1D_PLACEMENTASSIST1E_BUFFERHYGIENE1A",
 "exposureCalculationChanged":False,
 "bufferSelectionChanged":True,
 "crossShutterStateInvalidated":True,
 "placementMaxAgeMs":750,
 "stalePlacementMfmFallbackSuppressed":True,
 "phoneValidationRequired":True
}
(root/"MONOAUTO1D_PLACEMENTASSIST1E_BUFFERHYGIENE1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
