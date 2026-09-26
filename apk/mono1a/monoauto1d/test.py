#!/usr/bin/env python3
from pathlib import Path
import json, math, subprocess, sys, tempfile

if len(sys.argv) != 2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
here = Path(__file__).resolve().parent

# Compile and exercise the actual placement policy with tiny host stubs.
with tempfile.TemporaryDirectory() as d:
    p = Path(d)
    stubs = {
        "org/json/JSONObject.java": r'''
package org.json;
import java.util.*;
public class JSONObject {
 public static final Object NULL=new Object();
 private final Map<String,Object> m=new HashMap<>();
 public JSONObject(){}
 public JSONObject(String s){}
 public JSONObject put(String k,Object v){m.put(k,v);return this;}
 public double optDouble(String k,double d){Object v=m.get(k);return v instanceof Number?((Number)v).doubleValue():d;}
 public String toString(){return "{}";}
}
''',
        "com/particlesdevs/photoncamera/m9/M9BacklightDiagnostic.java": r'''
package com.particlesdevs.photoncamera.m9;
public class M9BacklightDiagnostic {
 public static class LiveFeedbackDecision {
  public final boolean valid,wouldApply; public final double recommendedEv,appliedEv; public final String reason;
  public LiveFeedbackDecision(boolean v,boolean w,double r,double a,String s,Object o){
   valid=v;wouldApply=w;recommendedEv=r;appliedEv=a;reason=s;
  }
 }
}
''',
        "com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java": r'''
package com.particlesdevs.photoncamera.m9.preview;
public class MonoGpuPreview2A {
 public static class PlacementObservation1D {
  public final boolean valid; public final String reason,camera; public final long capturedElapsedNs,sessionId;
  public final double ageMs,planScale,scaledCenterWeightedMedian,baseCenterWeightedMedian;
  public final double scaledQ99_8,baseQ99_8,scaledClipFraction; public final int sampleCount;
  public PlacementObservation1D(boolean v,String r,double scale,double median,double q998,double clip){
   valid=v;reason=r;camera="main";capturedElapsedNs=1;sessionId=1;ageMs=100;planScale=scale;
   scaledCenterWeightedMedian=median*scale;baseCenterWeightedMedian=median;
   scaledQ99_8=q998*scale;baseQ99_8=q998;scaledClipFraction=clip;sampleCount=3072;
  }
 }
}
'''
    }
    for rel, src in stubs.items():
        f = p / rel
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(src)
    policy = p / "com/particlesdevs/photoncamera/m9/exposure/MonoPlacementAssist1D.java"
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text((here / "MonoPlacementAssist1D.java").read_text())
    test = p / "com/particlesdevs/photoncamera/m9/exposure/PlacementTest.java"
    test.write_text(r'''
package com.particlesdevs.photoncamera.m9.exposure;
import org.json.JSONObject;
import com.particlesdevs.photoncamera.m9.M9BacklightDiagnostic;
import com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A;
public class PlacementTest {
 static int n=0; static void ok(boolean b){n++;if(!b)throw new AssertionError("check "+n);}
 static void near(double a,double b,double e){ok(Math.abs(a-b)<=e);}
 static JSONObject positiveGeometry(){
  return new JSONObject().put("sceneSpreadEv",1.30).put("brightRegionFraction",3.0/24.0)
   .put("darkRegionFraction",9.0/24.0).put("upperVsLowerEv",0.94).put("edgeVsInnerEv",0.05)
   .put("integralVsCenterEv",0.20).put("integralVsLowerEv",0.30).put("negativeCandidateEv",0.0);
 }
 static M9BacklightDiagnostic.LiveFeedbackDecision mfm(double rec,double applied){
  return new M9BacklightDiagnostic.LiveFeedbackDecision(true,Math.abs(rec)>=.08,rec,applied,"test",null);
 }
 static MonoGpuPreview2A.PlacementObservation1D p(boolean valid,double median,double q998){
  return new MonoGpuPreview2A.PlacementObservation1D(valid,valid?"live":"missing",1.0,median,q998,0.0);
 }
 public static void main(String[] a) {
  near(MonoPlacementAssist1D.REFERENCE_TARGET,0.0876544,1e-12);
  double catDelta=Math.log(MonoPlacementAssist1D.REFERENCE_TARGET/0.067501776)/Math.log(2.0);
  MonoPlacementAssist1D.Decision cat=MonoPlacementAssist1D.evaluate(true,mfm(0,0),positiveGeometry(),p(true,0.067501776,0.35));
  near(cat.appliedEv,catDelta,0.005); ok(cat.reason.contains("backlit_geometry"));

  JSONObject ordinary=new JSONObject().put("sceneSpreadEv",0.25).put("brightRegionFraction",0.02)
    .put("darkRegionFraction",0.50).put("upperVsLowerEv",0.10).put("edgeVsInnerEv",0.05)
    .put("integralVsCenterEv",0.02).put("integralVsLowerEv",0.02).put("negativeCandidateEv",0.0);
  near(MonoPlacementAssist1D.evaluate(true,mfm(0,0),ordinary,p(true,0.055,0.30)).appliedEv,0.0,1e-12);

  // Source already at/above target suppresses a positive MFM request.
  near(MonoPlacementAssist1D.evaluate(true,mfm(.25,.25),positiveGeometry(),p(true,0.090,0.40)).appliedEv,0.0,1e-12);

  // Live source tail safety, not arbitrary +EV, limits positive movement.
  double h=Math.log(.92/.80)/Math.log(2.0);
  MonoPlacementAssist1D.Decision limited=MonoPlacementAssist1D.evaluate(true,mfm(.25,.25),positiveGeometry(),p(true,0.060,0.80));
  near(limited.appliedEv,h,0.005);

  JSONObject neg=new JSONObject().put("negativeCandidateEv",-0.20);
  double negDelta=Math.log(MonoPlacementAssist1D.REFERENCE_TARGET/.120)/Math.log(2.0);
  MonoPlacementAssist1D.Decision nd=MonoPlacementAssist1D.evaluate(true,mfm(-.20,-.20),neg,p(true,.120,.40));
  near(nd.appliedEv,negDelta,0.005); ok(nd.appliedEv<0);

  // No live SOURCE1D yet: preserve delivered MFM behavior rather than inventing placement.
  MonoPlacementAssist1D.Decision fallback=MonoPlacementAssist1D.evaluate(true,mfm(.25,.25),positiveGeometry(),p(false,.07,.30));
  near(fallback.appliedEv,.25,1e-12); ok(fallback.reason.contains("fallback"));

  // Manual/user/tripod eligibility remains authoritative.
  near(MonoPlacementAssist1D.evaluate(false,mfm(.25,.25),positiveGeometry(),p(true,.05,.20)).appliedEv,0.0,1e-12);
  System.out.println("MONOAUTO1D policy PASS assertions="+n);
 }
}
''')
    java = [str(f) for f in p.rglob("*.java")]
    subprocess.run(["javac", "-d", str(p / "classes")] + java, check=True)
    subprocess.run(["java", "-cp", str(p / "classes"),
                    "com.particlesdevs.photoncamera.m9.exposure.PlacementTest"], check=True)

J = root / "app/src/main/java/com/particlesdevs/photoncamera"
selector = (J / "processing/parameters/IsoExpoSelector.java").read_text()
plan = (J / "m9/exposure/MonoExposurePlan1A.java").read_text()
diag = (J / "m9/exposure/MonoExposureDiagnostics1A.java").read_text()
gpu = (J / "m9/preview/MonoGpuPreview2A.java").read_text()
mfm = (J / "m9/M9M10rMfmTest1A.java").read_text()
main = (J / "ui/camera/views/viewfinder/MainRenderer.java").read_text()
shader = (root / "app/src/main/assets/shaders/preview/main_fs.glsl").read_text()
writer = (J / "m9/export/MonoDngWriter1A.java").read_text()
proof = json.loads((root / "MONOAUTO1D_PLACEMENTASSIST1A_ISOLATION.json").read_text())

assert "MonoPlacementAssist1D.evaluate(" in selector
assert "placement1D.appliedEv" in selector
assert "placement1D.diagnosticJson()" in selector
assert "monoPlanSnapshot1D()" in mfm
assert "lastMonoPlan1D" in mfm
assert "PlacementObservation1D" in gpu
assert "placementFromProbe1D" in gpu
assert "scaled_SOURCE1D_high8" in gpu
assert "monoSource16Probe1D" in shader
assert "Output=vec4(hi/255.0,lo/255.0,y,1.0)" in shader
assert "nextProbeNs2A=now+500000000L" in main
assert "placementDiagnosticJson" in plan
assert "monoPlacementAssist1D" in diag

# Parent photographic semantics remain present.
assert "MONOOUTPUT1E_BASELINE_IFD0" in writer
assert "ProfileToneCurve" not in writer

assert proof["captureExposureChanged"] is True
assert proof["jpegRendererChanged"] is False
assert proof["dngSamplesChanged"] is False
assert proof["baselineExposureChanged"] is False
assert proof["curve02AssetChanged"] is False
assert proof["normalDisplayMonochromeFunctionChanged"] is False
assert proof["manualEvIsoShutterTripodAuthorityPreserved"] is True
assert proof["HDR"] is False
assert proof["postCaptureRescue"] is False
assert abs(proof["referenceTarget"] - 0.0876544) < 1e-12

report = {
    "status": "PASS",
    "revision": "MONOAUTO1D_PLACEMENTASSIST1A",
    "referenceTarget": 0.0876544,
    "catPriorWeightedMedianExample": 0.067501776,
    "catExpectedPlacementEv": math.log(0.0876544 / 0.067501776, 2.0),
    "positiveLimitEv": 0.50,
    "negativeLimitEv": -0.50,
    "liveSourceQ998Limit": 0.92,
    "sceneIntent": "M10R_4x6_multifield_geometry",
    "placementMagnitude": "live_SOURCE1D_before_curve02",
    "phoneValidationRequired": True
}
(root / "MONOAUTO1D_PLACEMENTASSIST1A_TEST_REPORT.json").write_text(
    json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
