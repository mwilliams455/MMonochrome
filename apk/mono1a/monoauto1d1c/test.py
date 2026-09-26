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
 static JSONObject pos(){
  return new JSONObject().put("sceneSpreadEv",2.894).put("brightRegionFraction",8.0/24.0).put("darkRegionFraction",5.0/24.0)
   .put("upperVsLowerEv",2.423).put("edgeVsInnerEv",1.067).put("integralVsCenterEv",.471)
   .put("integralVsLowerEv",.820).put("negativeCandidateEv",0.0);
 }
 static M9BacklightDiagnostic.LiveFeedbackDecision m(double ev){
  return new M9BacklightDiagnostic.LiveFeedbackDecision(true,true,ev,ev,"m10r_multifield_positive_capture_assist",null);
 }
 static MonoGpuPreview2A.PlacementObservation1D p(double median,double q998,double q99,double sensorQ998,double clip){
  return new MonoGpuPreview2A.PlacementObservation1D(true,median,q998,.533333333333,q99,sensorQ998,clip);
 }
 public static void main(String[] a){
  ok(MonoPlacementAssist1D.REVISION.equals("MONOAUTO1D_PLACEMENTASSIST1C_BROADTAIL1A"));
  near(MonoPlacementAssist1D.BROAD_TAIL_Q99_TARGET,250.0/255.0,1e-12);

  // 2026-09-26 11:05 field frame: strict 1B allowed 0.1579 EV, while
  // sensor-RGB max q99=187/255 and zero proxy clipping. 1C should select the
  // broad-tail budget: log2(250/187)=~0.41889 EV, still below +0.50.
  MonoPlacementAssist1D.Decision current=MonoPlacementAssist1D.evaluate(true,m(.5840264650751639),pos(),
    p(.013834858142912104,.8246273009048366,187.0/255.0,.8117647058823529,0.0));
  near(current.appliedEv,Math.log(250.0/187.0)/Math.log(2.0),1e-9);
  ok(current.reason.contains("broadtail"));

  // If the broad proxy is already clipped beyond the 0.2% allowance, 1C must
  // fall back to the strict 1A/1B q99.8 headroom, not invent exposure.
  MonoPlacementAssist1D.Decision clipped=MonoPlacementAssist1D.evaluate(true,m(.45),pos(),
    p(.020,.90,.80,.95,.01));
  double strict=Math.log(.92/.90)/Math.log(2.0);
  near(clipped.appliedEv,0.0,1e-12); // strict < 0.08 deadband => zero
  ok(!clipped.reason.contains("broadtail"));

  // Broad-tail permission can never exceed the actual MFM recommendation.
  MonoPlacementAssist1D.Decision weakMfm=MonoPlacementAssist1D.evaluate(true,m(.20),pos(),
    p(.020,.70,.60,.70,0.0));
  near(weakMfm.appliedEv,.20,1e-12);

  // Existing strict path remains available even when broad-tail is unavailable.
  MonoPlacementAssist1D.Decision strictOk=MonoPlacementAssist1D.evaluate(true,m(.40),pos(),
    p(.050,.60,.99,.99,.01));
  near(strictOk.appliedEv,Math.min(.5,Math.log(.92/.60)/Math.log(2.0)),1e-9);

  // Manual/user/tripod eligibility remains authoritative.
  near(MonoPlacementAssist1D.evaluate(false,m(.5),pos(),
    p(.02,.5,.5,.5,0)).appliedEv,0.0,1e-12);
  System.out.println("MONOAUTO1D1C broad-tail policy PASS assertions="+n);
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
proof=json.loads((root/"MONOAUTO1D_PLACEMENTASSIST1C_BROADTAIL1A_ISOLATION.json").read_text())

for token in [
 "MONOAUTO1D_PLACEMENTASSIST1C_BROADTAIL1A",
 "BROAD_TAIL_Q99_TARGET",
 "BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION",
 "monoauto1d_mfm_positive_broadtail_placement_lift",
 "single_exposure_preserve_broad_99pct_tail_allow_small_extreme_highlight_sacrifice"
]:
    assert token in assist,token
assert "placement1D.appliedEv" in selector
assert "sensorRgbMaxQ99_8" in gpu
assert "MONOAUTO1D1B_SOURCE1D16_SENSORRGBMAX8" in gpu
assert "MONOOUTPUT1E_BASELINE_IFD0" in writer
assert "ProfileToneCurve" not in writer
assert proof["exposurePolicyChangedFrom1B"] is True
assert proof["jpegRendererChanged"] is False
assert proof["dngSamplesChanged"] is False
assert proof["baselineExposureChanged"] is False
assert proof["curve02AssetChanged"] is False
assert proof["previewProbeChangedFrom1B"] is False
assert proof["postCaptureProbeChangedFrom1B"] is False
assert proof["HDR"] is False
assert proof["postCaptureRescue"] is False
assert proof["manualAuthorityPreserved"] is True

expected=math.log2(250.0/187.0)
assert abs(proof["current110526Replay"]["expectedAppliedEv"]-expected)<1e-12
report={
 "status":"PASS",
 "revision":"MONOAUTO1D_PLACEMENTASSIST1C_BROADTAIL1A",
 "current110526ExpectedEv":expected,
 "current110526Prior1BEv":0.15789163590289854,
 "additionalVs1BEv":expected-0.15789163590289854,
 "current110526ObservedPhysicalRawQ998":0.45985401459854014,
 "current110526CounterfactualPhysicalRawQ998":proof["current110526Replay"]["completedRawQ998CounterfactualAt1C"],
 "broadTailQ99Target":250.0/255.0,
 "maxExistingProxyClipFraction":0.002,
 "globalPositiveLimitEv":0.5,
 "phoneValidationRequired":True
}
(root/"MONOAUTO1D_PLACEMENTASSIST1C_BROADTAIL1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
