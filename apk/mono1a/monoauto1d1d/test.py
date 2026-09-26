#!/usr/bin/env python3
from pathlib import Path
import json, math, subprocess, sys, tempfile

if len(sys.argv)!=2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
here=Path(__file__).resolve().parent
J=root/"app/src/main/java/com/particlesdevs/photoncamera"

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
  public PlacementObservation1D(boolean v,double median,double q998,double q95,double q99,double sensorQ998,double sensorClip){
   valid=v;reason=v?"live_source1d_plus_sensor_rgb_max_probe1b":"missing";camera="main";capturedElapsedNs=1;sessionId=1;
   ageMs=20;planScale=1;scaledCenterWeightedMedian=median;baseCenterWeightedMedian=median;scaledQ99_8=q998;baseQ99_8=q998;
   scaledClipFraction=q998>=1?.01:0;sensorRgbMaxQ95=q95;sensorRgbMaxQ99=q99;sensorRgbMaxQ99_8=sensorQ998;
   sensorRgbMaxClipFraction=sensorClip;sampleCount=3072;
  }
 }
}
'''
    }
    for rel,src in stubs.items():
        f=p/rel; f.parent.mkdir(parents=True,exist_ok=True); f.write_text(src)
    pol=p/"com/particlesdevs/photoncamera/m9/exposure/MonoPlacementAssist1D.java"
    pol.parent.mkdir(parents=True,exist_ok=True)
    pol.write_text((here/"MonoPlacementAssist1D.java").read_text())
    t=p/"com/particlesdevs/photoncamera/m9/exposure/Test.java"
    t.write_text(r'''
package com.particlesdevs.photoncamera.m9.exposure;
import org.json.JSONObject; import com.particlesdevs.photoncamera.m9.M9BacklightDiagnostic;
import com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A;
public class Test {
 static int n; static void ok(boolean b){n++;if(!b)throw new AssertionError("check "+n);}
 static void near(double a,double b,double e){ok(Math.abs(a-b)<=e);}
 static JSONObject latestGeometry(){
  return new JSONObject().put("sceneSpreadEv",3.374925688592755)
   .put("brightRegionFraction",.375).put("darkRegionFraction",.4583333333333333)
   .put("upperVsLowerEv",1.0899993482454589).put("edgeVsInnerEv",-0.3673729602104112)
   .put("integralVsCenterEv",-0.09882492361970298).put("integralVsLowerEv",1.0895881147691842)
   .put("negativeCandidateEv",0.0);
 }
 static M9BacklightDiagnostic.LiveFeedbackDecision m(double ev){
  return new M9BacklightDiagnostic.LiveFeedbackDecision(true,true,ev,ev,"m10r_multifield_positive_capture_assist",null);
 }
 static MonoGpuPreview2A.PlacementObservation1D p(double median,double q998,double q99,double sensorQ998,double clip){
  return new MonoGpuPreview2A.PlacementObservation1D(true,median,q998,.27450980392156865,q99,sensorQ998,clip);
 }
 public static void main(String[] a){
  ok(MonoPlacementAssist1D.REVISION.equals("MONOAUTO1D_PLACEMENTASSIST1D_BROADTAIL05"));
  near(MonoPlacementAssist1D.BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION,.005,1e-12);

  // 2026-09-26 11:52 field frame. 1C rejected 0.2604% proxy clipping;
  // 1D must accept it and be bounded by the MFM request (+0.327 EV).
  double mfm=.32700269262775195;
  MonoPlacementAssist1D.Decision latest=MonoPlacementAssist1D.evaluate(true,m(mfm),latestGeometry(),
    p(.016744418778776967,.884956036021894,.6862745098039216,1.0,.0026041666666666665));
  near(latest.appliedEv,mfm,1e-12);
  ok(latest.reason.contains("broadtail"));

  // Exact 0.5% remains eligible.
  MonoPlacementAssist1D.Decision edge=MonoPlacementAssist1D.evaluate(true,m(.25),latestGeometry(),
    p(.02,.90,.70,.95,.005));
  near(edge.appliedEv,.25,1e-12);

  // Above 0.5% must reject broad-tail and fall back to the strict q99.8 path.
  MonoPlacementAssist1D.Decision over=MonoPlacementAssist1D.evaluate(true,m(.30),latestGeometry(),
    p(.02,.90,.70,.95,.006));
  near(over.appliedEv,0.0,1e-12);
  ok(!over.reason.contains("broadtail"));

  // Broad-tail still cannot exceed global +0.50 or MFM recommendation.
  MonoPlacementAssist1D.Decision cap=MonoPlacementAssist1D.evaluate(true,m(.70),latestGeometry(),
    p(.01,.90,.50,.60,0.0));
  near(cap.appliedEv,.50,1e-12);
  MonoPlacementAssist1D.Decision weak=MonoPlacementAssist1D.evaluate(true,m(.18),latestGeometry(),
    p(.02,.90,.50,.60,0.0));
  near(weak.appliedEv,.18,1e-12);

  // Manual/user/tripod authority remains absolute.
  near(MonoPlacementAssist1D.evaluate(false,m(.5),latestGeometry(),
    p(.02,.5,.5,.5,0)).appliedEv,0.0,1e-12);
  System.out.println("MONOAUTO1D1D BROADTAIL05 PASS assertions="+n);
 }
}
''')
    java=[str(f) for f in p.rglob("*.java")]
    subprocess.run(["javac","-d",str(p/"classes")]+java,check=True)
    subprocess.run(["java","-cp",str(p/"classes"),"com.particlesdevs.photoncamera.m9.exposure.Test"],check=True)

assist=(J/"m9/exposure/MonoPlacementAssist1D.java").read_text()
selector=(J/"processing/parameters/IsoExpoSelector.java").read_text()
gpu=(J/"m9/preview/MonoGpuPreview2A.java").read_text()
writer=(J/"m9/export/MonoDngWriter1A.java").read_text()
proof=json.loads((root/"MONOAUTO1D_PLACEMENTASSIST1D_BROADTAIL05_ISOLATION.json").read_text())

assert 'MONOAUTO1D_PLACEMENTASSIST1D_BROADTAIL05' in assist
assert 'BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION = 0.005' in assist
assert 'BROAD_TAIL_Q99_TARGET = 250.0 / 255.0' in assist
assert 'MAX_POSITIVE_EV = 0.50' in assist
assert "placement1D.appliedEv" in selector
assert "sensorRgbMaxQ99_8" in gpu
assert "MONOOUTPUT1E_BASELINE_IFD0" in writer
assert "ProfileToneCurve" not in writer
assert proof["policyChangeOnly"]=="BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION_0p002_to_0p005"
for k in ["sceneIntentChanged","placementMagnitudeChanged","broadTailQ99TargetChanged",
          "globalPositiveLimitChanged","manualAuthorityChanged","jpegRendererChanged",
          "dngSamplesChanged","baselineExposureChanged","curve02AssetChanged",
          "previewProbeChanged","postCaptureProbeChanged","mfmChanged","HDR","postCaptureRescue"]:
    assert proof[k] is False,k

latest=proof["latest115229Replay"]
assert latest["old1CEligible"] is False
assert latest["new1DEligible"] is True
assert abs(latest["expectedAppliedEv"]-.32700269262775195)<1e-12
assert abs(latest["counterfactualRawQ998At1D"]-.6762535455047799)<1e-12

report={
 "status":"PASS",
 "revision":"MONOAUTO1D_PLACEMENTASSIST1D_BROADTAIL05",
 "onlyPolicyChange":"existing_proxy_clip_allowance_0.002_to_0.005",
 "latest115229ExpectedAppliedEv":latest["expectedAppliedEv"],
 "latest115229Prior1CAppliedEv":0.0,
 "latest115229ObservedRawQ998":latest["completedRawQ998Observed"],
 "latest115229CounterfactualRawQ998":latest["counterfactualRawQ998At1D"],
 "broadTailQ99Target":250.0/255.0,
 "globalPositiveLimitEv":0.5,
 "phoneValidationRequired":True
}
(root/"MONOAUTO1D_PLACEMENTASSIST1D_BROADTAIL05_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
