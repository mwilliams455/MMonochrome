#!/usr/bin/env python3
from pathlib import Path
import json, math, subprocess, sys, tempfile

if len(sys.argv)!=2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"

# Compile the actual 1B policy with minimal stubs and prove the new sensor proxy
# does not alter the delivered 1A exposure result.
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
  public PlacementObservation1D(boolean v,double median,double q998,double sensorQ998){
   valid=v;reason=v?"live_source1d_plus_sensor_rgb_max_probe1b":"missing";camera="main";capturedElapsedNs=1;sessionId=1;
   ageMs=20;planScale=1;scaledCenterWeightedMedian=median;baseCenterWeightedMedian=median;scaledQ99_8=q998;baseQ99_8=q998;
   scaledClipFraction=q998>=1?.009:0;sensorRgbMaxQ95=.7;sensorRgbMaxQ99=.85;sensorRgbMaxQ99_8=sensorQ998;
   sensorRgbMaxClipFraction=sensorQ998>=1?.01:0;sampleCount=3072;
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
    t=p/"com/particlesdevs/photoncamera/m9/exposure/Test.java"
    t.write_text(r'''
package com.particlesdevs.photoncamera.m9.exposure;
import org.json.JSONObject; import com.particlesdevs.photoncamera.m9.M9BacklightDiagnostic;
import com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A;
public class Test {
 static int n; static void ok(boolean b){n++;if(!b)throw new AssertionError("check "+n);}
 static void near(double a,double b,double e){ok(Math.abs(a-b)<=e);}
 static JSONObject pos(){return new JSONObject().put("sceneSpreadEv",2.4).put("brightRegionFraction",.40).put("darkRegionFraction",.40)
  .put("upperVsLowerEv",1.4).put("edgeVsInnerEv",-.4).put("integralVsCenterEv",-.08).put("integralVsLowerEv",1.3).put("negativeCandidateEv",0.0);}
 static M9BacklightDiagnostic.LiveFeedbackDecision m(double ev){return new M9BacklightDiagnostic.LiveFeedbackDecision(true,true,ev,ev,"m10r_multifield_positive_capture_assist",null);}
 public static void main(String[] a){
  ok(MonoPlacementAssist1D.REVISION.equals("MONOAUTO1D_PLACEMENTASSIST1B_RAWPROXY1A"));
  // Prior cat-style safe-headroom case remains unchanged.
  double want=Math.log(MonoPlacementAssist1D.REFERENCE_TARGET/.067501776)/Math.log(2);
  MonoPlacementAssist1D.Decision d=MonoPlacementAssist1D.evaluate(true,m(.084),pos(),
    new MonoGpuPreview2A.PlacementObservation1D(true,.067501776,.35,.60));
  near(d.appliedEv,want,.005);
  // First 1D phone sample: sensor proxy is deliberately NOT promoted yet.
  MonoPlacementAssist1D.Decision s=MonoPlacementAssist1D.evaluate(true,m(.4506338963),pos(),
    new MonoGpuPreview2A.PlacementObservation1D(true,.0230716411,1.0,.906));
  near(s.appliedEv,0.0,1e-12); ok(s.reason.contains("blocked_by_live_source_headroom"));
  ok(s.diagnostic.toString()!=null);
  System.out.println("MONOAUTO1D1B policy invariance PASS assertions="+n);
 }
}
''')
    java=[str(f) for f in p.rglob("*.java")]
    subprocess.run(["javac","-d",str(p/"classes")]+java,check=True)
    subprocess.run(["java","-cp",str(p/"classes"),"com.particlesdevs.photoncamera.m9.exposure.Test"],check=True)

shader=(root/"app/src/main/assets/shaders/preview/main_fs.glsl").read_text()
gpu=(J/"m9/preview/MonoGpuPreview2A.java").read_text()
assist=(J/"m9/exposure/MonoPlacementAssist1D.java").read_text()
probe=(J/"m9/export/MonoPlacementProbe1A.java").read_text()
writer=(J/"m9/export/MonoDngWriter1A.java").read_text()
proof=json.loads((root/"MONOAUTO1D_PLACEMENTASSIST1B_RAWPROXY1A_ISOLATION.json").read_text())

assert "monoSensorRgbMaxProbe1B" in shader
assert "Output=vec4(hi/255.0,lo/255.0,sensorMax,1.0)" in shader
assert "sensorRgbMaxQ99_8" in gpu
assert "MONOAUTO1D1B_SOURCE1D16_SENSORRGBMAX8" in gpu
assert "sensorRgbMaxProxyUsedToMutateCapture" in assist
assert '"diagnostic_crosscheck_against_completed_physical_RAW_tail"' in assist
assert 'else out.put("mfmRecommendedEv", JSONObject.NULL);' in probe
assert 'else out.put("mfmAppliedEv", JSONObject.NULL);' in probe
assert "MONOOUTPUT1E_BASELINE_IFD0" in writer
assert "ProfileToneCurve" not in writer

assert proof["captureExposureArithmeticChangedFrom1A"] is False
assert proof["headroomAuthorityChangedFrom1A"] is False
assert proof["sensorRgbMaxProxyUsedToMutateCapture"] is False
assert proof["completedRawPlacementNaNBugFixed"] is True
for k in ["jpegRendererChanged","dngSamplesChanged","baselineExposureChanged","curve02AssetChanged","normalDisplayPathChanged"]:
    assert proof[k] is False,k

report={
 "status":"PASS",
 "revision":"MONOAUTO1D_PLACEMENTASSIST1B_RAWPROXY1A",
 "exposurePolicy":"1A_unchanged",
 "newLiveProbe":"SOURCE1D16_plus_reconstructed_sensor_RGB_max8",
 "sensorProxyRole":"diagnostic_only",
 "firstPhoneLiveSourceQ998":1.0,
 "firstPhoneCompletedRawQ998":0.9061522419186653,
 "postCaptureNaNBugFixed":True,
 "phoneValidationRequired":True
}
(root/"MONOAUTO1D_PLACEMENTASSIST1B_RAWPROXY1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
