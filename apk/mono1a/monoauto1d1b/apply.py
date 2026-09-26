#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")

root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
shader=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
gpu=J/"m9/preview/MonoGpuPreview2A.java"
assist=J/"m9/exposure/MonoPlacementAssist1D.java"
probe=J/"m9/export/MonoPlacementProbe1A.java"
gradle=root/"app/build.gradle"

for p in (shader,gpu,assist,probe,gradle):
    if not p.exists(): raise SystemExit("MONOAUTO1D1B missing parent file: "+str(p))

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,name):
    if s.count(a)!=1:
        raise SystemExit(f"{name} anchor mismatch count={s.count(a)}")
    return s.replace(a,b,1)

# Output photography remains frozen. This branch only alters the off-screen probe,
# exposure diagnostics, and the diagnostic-only completed-RAW placement report.
frozen=[
    J/"m9/render/M9R35Renderer.java",
    J/"m9/export/MonoDngExport1A.java",
    J/"m9/export/MonoDngWriter1A.java",
    J/"m9/export/MonoLinearPlane1A.java",
    root/"app/src/main/cpp/m9color_jni.cpp",
    root/"app/src/main/assets/mono/mono_curve02_gl2a.bin",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}

# --- Probe payload: retain exact 16-bit SOURCE1D in R/G, replace diagnostic B
# channel with reconstructed sensor-RGB max before exposure scale and before
# SOURCE1D Y. This is intentionally *not* called physical RAW: preview ISP
# demosaic/shading may remain.
ss=shader.read_text()
old_helper=r'''
float monoSource16Probe1D(vec3 oes) {
    if (!uMonoSourceReady2A) return -1.0;
    vec3 linearRgb=vec3(inverseChannel(oes.r,0),inverseChannel(oes.g,1),inverseChannel(oes.b,2));
    vec3 sensor=uMonoInputToSensor2A*linearRgb;
    vec3 cam16=floor(clamp(sensor*uMonoExposureScale1A,0.0,1.0)*65535.0+0.5);
    return floor(clamp(dot(cam16,uMonoSourceY2A),0.0,65535.0)+0.5);
}
'''
new_helper=old_helper+r'''
float monoSensorRgbMaxProbe1B(vec3 oes) {
    if (!uMonoSourceReady2A) return -1.0;
    vec3 linearRgb=vec3(inverseChannel(oes.r,0),inverseChannel(oes.g,1),inverseChannel(oes.b,2));
    vec3 sensor=uMonoInputToSensor2A*linearRgb;
    return clamp(max(sensor.r,max(sensor.g,sensor.b)),0.0,1.0);
}
'''
ss=one(ss,old_helper,new_helper,"shader sensor proxy helper")
old_branch=r'''    if (uMonoProbe2A) {
        float source16=monoSource16Probe1D(oes.rgb);
        if (source16 < 0.0) { Output=vec4(0.0,0.0,y,0.0); return; }
        float hi=floor(source16/256.0);
        float lo=source16-hi*256.0;
        Output=vec4(hi/255.0,lo/255.0,y,1.0);
        return;
    }
'''
new_branch=r'''    if (uMonoProbe2A) {
        float source16=monoSource16Probe1D(oes.rgb);
        float sensorMax=monoSensorRgbMaxProbe1B(oes.rgb);
        if (source16 < 0.0 || sensorMax < 0.0) { Output=vec4(0.0,0.0,0.0,0.0); return; }
        float hi=floor(source16/256.0);
        float lo=source16-hi*256.0;
        Output=vec4(hi/255.0,lo/255.0,sensorMax,1.0);
        return;
    }
'''
ss=one(ss,old_branch,new_branch,"shader probe B raw-like proxy")
shader.write_text(ss)

# --- Cache sensor-max tail statistics beside the existing placement observation.
gs=gpu.read_text()
gs=one(gs,
'''        public final double scaledQ99_8,baseQ99_8,scaledClipFraction;
        public final int sampleCount;
        PlacementObservation1D(boolean valid,String reason,String camera,long captured,long session,
                double ageMs,double scale,double scaledMedian,double baseMedian,
                double scaledQ998,double baseQ998,double clip,int samples) {
''',
'''        public final double scaledQ99_8,baseQ99_8,scaledClipFraction;
        public final double sensorRgbMaxQ95,sensorRgbMaxQ99,sensorRgbMaxQ99_8,sensorRgbMaxClipFraction;
        public final int sampleCount;
        PlacementObservation1D(boolean valid,String reason,String camera,long captured,long session,
                double ageMs,double scale,double scaledMedian,double baseMedian,
                double scaledQ998,double baseQ998,double clip,
                double sensorQ95,double sensorQ99,double sensorQ998,double sensorClip,int samples) {
''',"GPU observation fields")
gs=one(gs,
'''            baseCenterWeightedMedian=baseMedian;scaledQ99_8=scaledQ998;baseQ99_8=baseQ998;
            scaledClipFraction=clip;sampleCount=samples;
''',
'''            baseCenterWeightedMedian=baseMedian;scaledQ99_8=scaledQ998;baseQ99_8=baseQ998;
            scaledClipFraction=clip;sensorRgbMaxQ95=sensorQ95;sensorRgbMaxQ99=sensorQ99;
            sensorRgbMaxQ99_8=sensorQ998;sensorRgbMaxClipFraction=sensorClip;sampleCount=samples;
''',"GPU observation assignment")
gs=one(gs,
'''            return new PlacementObservation1D(valid,reason,camera,capturedElapsedNs,sessionId,ms,planScale,
                    scaledCenterWeightedMedian,baseCenterWeightedMedian,scaledQ99_8,baseQ99_8,
                    scaledClipFraction,sampleCount);
''',
'''            return new PlacementObservation1D(valid,reason,camera,capturedElapsedNs,sessionId,ms,planScale,
                    scaledCenterWeightedMedian,baseCenterWeightedMedian,scaledQ99_8,baseQ99_8,
                    scaledClipFraction,sensorRgbMaxQ95,sensorRgbMaxQ99,sensorRgbMaxQ99_8,
                    sensorRgbMaxClipFraction,sampleCount);
''',"GPU withAge")
gs=one(gs,
'''            return new PlacementObservation1D(false,reason,camera,captured,session,0.0,1.0,
                    Double.NaN,Double.NaN,Double.NaN,Double.NaN,0.0,0);
''',
'''            return new PlacementObservation1D(false,reason,camera,captured,session,0.0,1.0,
                    Double.NaN,Double.NaN,Double.NaN,Double.NaN,0.0,
                    Double.NaN,Double.NaN,Double.NaN,0.0,0);
''',"GPU invalid observation")
gs=one(gs,
'''        long[] hist=new long[bins];
        double[] weighted=new double[bins];
''',
'''        long[] hist=new long[bins];
        long[] sensorHist=new long[256];
        double[] weighted=new double[bins];
''',"GPU sensor histogram")
gs=one(gs,
'''        int samples=0,clipped=0;
''',
'''        int samples=0,clipped=0,sensorClipped=0;
''',"GPU sensor clipped count")
gs=one(gs,
'''                int code=((d.probe[i]&255)<<8)|(d.probe[i+1]&255);
                int bin=code>>>4;
                hist[bin]++;
''',
'''                int code=((d.probe[i]&255)<<8)|(d.probe[i+1]&255);
                int sensorCode=d.probe[i+2]&255;
                int bin=code>>>4;
                hist[bin]++;sensorHist[sensorCode]++;
''',"GPU sample sensor byte")
gs=one(gs,
'''                if(code>=65535) clipped++;
''',
'''                if(code>=65535) clipped++;
                if(sensorCode>=255) sensorClipped++;
''',"GPU sensor clip")
gs=one(gs,
'''        int q998=placementQuantileBin1D(hist,samples,0.998);
        int wm=placementWeightedMedianBin1D(weighted,totalWeight);
''',
'''        int q998=placementQuantileBin1D(hist,samples,0.998);
        int sensorQ95=placementQuantileBin1D(sensorHist,samples,0.95);
        int sensorQ99=placementQuantileBin1D(sensorHist,samples,0.99);
        int sensorQ998=placementQuantileBin1D(sensorHist,samples,0.998);
        int wm=placementWeightedMedianBin1D(weighted,totalWeight);
''',"GPU sensor quantiles")
gs=one(gs,
'''        return new PlacementObservation1D(true,"live_source1d_probe",camera,captured,session,0.0,scale,
                scaledMedian,baseMedian,scaledQ998,baseQ998,clipped/(double)samples,samples);
''',
'''        return new PlacementObservation1D(true,"live_source1d_plus_sensor_rgb_max_probe1b",camera,captured,session,0.0,scale,
                scaledMedian,baseMedian,scaledQ998,baseQ998,clipped/(double)samples,
                sensorQ95/255.0,sensorQ99/255.0,sensorQ998/255.0,
                sensorClipped/(double)samples,samples);
''',"GPU return proxy")
gs=one(gs,
'''                o.put("channels","R=scaled_SOURCE1D_high8;G=scaled_SOURCE1D_low8;B=post_curve02_monochrome;A=placement_valid");
                o.put("placementProbeRevision","MONOAUTO1D_SOURCE1D_PACK16");
''',
'''                o.put("channels","R=scaled_SOURCE1D_high8;G=scaled_SOURCE1D_low8;B=reconstructed_sensor_RGB_max_before_exposure_scale;A=placement_valid");
                o.put("placementProbeRevision","MONOAUTO1D1B_SOURCE1D16_SENSORRGBMAX8");
                o.put("sensorRgbMaxMeaning","raw_like_preview_proxy_not_physical_RAW_preview_ISP_demosaic_shading_may_remain");
''',"GPU diagnostic channel")
gpu.write_text(gs)

# --- Policy revision: expose proxy but keep 1A exposure arithmetic byte-for-byte
# equivalent. No new headroom authority is promoted from one phone sample.
asrc=assist.read_text()
asrc=one(asrc,'public static final String REVISION = "MONOAUTO1D_PLACEMENTASSIST1A";',
               'public static final String REVISION = "MONOAUTO1D_PLACEMENTASSIST1B_RAWPROXY1A";',
               "assist revision")
asrc=one(asrc,
'''            d.put("physicalRawTailAvailablePreCapture", false);
            d.put("positiveSafety",
                    "live_SOURCE1D_q99p8_proxy_plus_existing_hardware_AE_and_physical_allocator_limits");
''',
'''            d.put("physicalRawTailAvailablePreCapture", false);
            d.put("positiveSafety",
                    "PLACEMENTASSIST1A_live_SOURCE1D_q99p8_authority_retained_pending_raw_proxy_validation");
            d.put("sensorRgbMaxProxyAvailable", placement != null && placement.valid);
            d.put("sensorRgbMaxProxyUsedToMutateCapture", false);
            d.put("sensorRgbMaxProxyDomain",
                    "reconstructed_sensor_RGB_max_before_plan_scale_preview_ISP_demosaic_shading_may_remain");
''',"assist safety provenance")
asrc=one(asrc,
'''            d.put("placementSampleCount", placement.sampleCount);

            double median = placement.baseCenterWeightedMedian;
''',
'''            d.put("placementSampleCount", placement.sampleCount);
            d.put("sensorRgbMaxQ95", placement.sensorRgbMaxQ95);
            d.put("sensorRgbMaxQ99", placement.sensorRgbMaxQ99);
            d.put("sensorRgbMaxQ99_8", placement.sensorRgbMaxQ99_8);
            d.put("sensorRgbMaxClipFraction", placement.sensorRgbMaxClipFraction);
            d.put("sensorRgbMaxProxyRole","diagnostic_crosscheck_against_completed_physical_RAW_tail");

            double median = placement.baseCenterWeightedMedian;
''',"assist proxy diagnostics")
assist.write_text(asrc)

# --- Fix MONOAUTO1C completed-RAW diagnostic NaN exception. Missing MFM snapshot
# now produces JSON null/absence, never invalidates otherwise valid placement data.
ps=probe.read_text()
old='''                double mfmRecommended = mfm.optDouble("recommendedExposureCorrectionEv", Double.NaN);
                double mfmApplied = mfm.optDouble("appliedExposureCorrectionEv", Double.NaN);
                out.put("mfmRecommendedEv", mfmRecommended);
                out.put("mfmAppliedEv", mfmApplied);
                out.put("mfmReason", mfm.optString("reason", ""));
                if (Double.isFinite(mfmRecommended))
                    out.put("referenceMinusMfmRecommendedEv", referenceDeltaEv - mfmRecommended);
                if (Double.isFinite(mfmApplied))
                    out.put("referenceMinusMfmAppliedEv", referenceDeltaEv - mfmApplied);
'''
new='''                double mfmRecommended = mfm.optDouble("recommendedExposureCorrectionEv", Double.NaN);
                double mfmApplied = mfm.optDouble("appliedExposureCorrectionEv", Double.NaN);
                if (Double.isFinite(mfmRecommended)) {
                    out.put("mfmRecommendedEv", mfmRecommended);
                    out.put("referenceMinusMfmRecommendedEv", referenceDeltaEv - mfmRecommended);
                } else out.put("mfmRecommendedEv", JSONObject.NULL);
                if (Double.isFinite(mfmApplied)) {
                    out.put("mfmAppliedEv", mfmApplied);
                    out.put("referenceMinusMfmAppliedEv", referenceDeltaEv - mfmApplied);
                } else out.put("mfmAppliedEv", JSONObject.NULL);
                out.put("mfmReason", mfm.optString("reason", ""));
'''
ps=one(ps,old,new,"completed probe NaN fix")
probe.write_text(ps)

g=gradle.read_text()
m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("versionName missing")
v=m.group(1)
if "monoauto1d-placementassist1b-rawproxy1a" not in v:
    g=g[:m.start(1)]+v+"-monoauto1d-placementassist1b-rawproxy1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}
if before!=after:
    raise SystemExit("MONOAUTO1D1B photographic output seam changed")

proof={
 "revision":"MONOAUTO1D_PLACEMENTASSIST1B_RAWPROXY1A",
 "parent":"MONOAUTO1D_PLACEMENTASSIST1A",
 "captureExposureArithmeticChangedFrom1A":False,
 "sourcePlacementAuthorityChangedFrom1A":False,
 "headroomAuthorityChangedFrom1A":False,
 "newSensorRgbMaxProxy":"diagnostic_only_not_physical_RAW",
 "sensorRgbMaxProxyUsedToMutateCapture":False,
 "completedRawPlacementNaNBugFixed":True,
 "reasonForNoHeadroomPromotion":"first_phone_sample_proved_live_SOURCE1D_tail_and_physical_RAW_tail_are_not_same_domain; new sensor proxy requires phone validation",
 "firstPhoneSampleEvidence":{
   "liveSourceQ998":1.0,
   "liveSourceClipFraction":0.009114583333333334,
   "completedRawQ998":0.9061522419186653,
   "completedRawHardClipFraction":0.00557096799214681,
   "mfmRecommendedEv":0.4506338963265084,
   "appliedEv":0.0
 },
 "jpegRendererChanged":False,
 "dngSamplesChanged":False,
 "baselineExposureChanged":False,
 "curve02AssetChanged":False,
 "normalDisplayPathChanged":False,
 "HDR":False,
 "frozen":after
}
(root/"MONOAUTO1D_PLACEMENTASSIST1B_RAWPROXY1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
