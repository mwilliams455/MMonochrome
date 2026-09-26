#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, shutil, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
here = Path(__file__).resolve().parent
J = root / "app/src/main/java/com/particlesdevs/photoncamera"
A = root / "app/src/main/assets/shaders/preview"
selector = J / "processing/parameters/IsoExpoSelector.java"
plan = J / "m9/exposure/MonoExposurePlan1A.java"
diag = J / "m9/exposure/MonoExposureDiagnostics1A.java"
gpu = J / "m9/preview/MonoGpuPreview2A.java"
mfm = J / "m9/M9M10rMfmTest1A.java"
main = J / "ui/camera/views/viewfinder/MainRenderer.java"
shader = A / "main_fs.glsl"
gradle = root / "app/build.gradle"

for p in (selector, plan, diag, gpu, mfm, main, shader, gradle):
    if not p.exists():
        raise SystemExit("MONOAUTO1D missing parent file: " + str(p))

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def one(s, a, b, name):
    if s.count(a) != 1:
        raise SystemExit(f"{name} anchor mismatch count={s.count(a)}: {a[:120]!r}")
    return s.replace(a, b, 1)

# JPEG/DNG/native/source photographic output remains frozen. The viewfinder shader
# change is probe-only and is checked separately below.
frozen_paths = [
    J / "m9/render/M9R35Renderer.java",
    J / "m9/export/MonoDngExport1A.java",
    J / "m9/export/MonoDngWriter1A.java",
    J / "m9/export/MonoLinearPlane1A.java",
    J / "m9/export/MonoPlacementMath1A.java",
    J / "m9/export/MonoPlacementProbe1A.java",
    root / "app/src/main/cpp/m9color_jni.cpp",
    root / "app/src/main/assets/mono/mono_curve02_gl2a.bin",
]
frozen_before = {str(p.relative_to(root)): sha(p) for p in frozen_paths if p.exists()}

# Install the policy class.
assist_dst = J / "m9/exposure/MonoPlacementAssist1D.java"
assist_dst.parent.mkdir(parents=True, exist_ok=True)
shutil.copyfile(here / "MonoPlacementAssist1D.java", assist_dst)

# 1) Probe-only shader payload: pack exact scaled SOURCE1D uint16 into R/G.
# The normal monochrome() display function is not altered.
shader_before = shader.read_text()
helper = r'''
float monoSource16Probe1D(vec3 oes) {
    if (!uMonoSourceReady2A) return -1.0;
    vec3 linearRgb=vec3(inverseChannel(oes.r,0),inverseChannel(oes.g,1),inverseChannel(oes.b,2));
    vec3 sensor=uMonoInputToSensor2A*linearRgb;
    vec3 cam16=floor(clamp(sensor*uMonoExposureScale1A,0.0,1.0)*65535.0+0.5);
    return floor(clamp(dot(cam16,uMonoSourceY2A),0.0,65535.0)+0.5);
}
'''
anchor = "void main() {\n"
shader_after = one(shader_before, anchor, helper + anchor, "shader helper")
old_probe = "    if (uMonoProbe2A) { Output=vec4(oes.rgb,y); return; }\n"
new_probe = r'''    if (uMonoProbe2A) {
        float source16=monoSource16Probe1D(oes.rgb);
        if (source16 < 0.0) { Output=vec4(0.0,0.0,y,0.0); return; }
        float hi=floor(source16/256.0);
        float lo=source16-hi*256.0;
        Output=vec4(hi/255.0,lo/255.0,y,1.0);
        return;
    }
'''
shader_after = one(shader_after, old_probe, new_probe, "shader probe branch")
# Prove the display shader can be reconstructed byte-for-byte by deleting only
# the new helper and restoring only the off-screen probe branch.
reconstructed = shader_after.replace(helper, "", 1).replace(new_probe, old_probe, 1)
if reconstructed != shader_before:
    raise SystemExit("MONOAUTO1D probe-only shader isolation failed")
shader.write_text(shader_after)

# 2) Increase only the tiny off-screen placement probe cadence from 1 Hz to 2 Hz.
main_before = main.read_text()
main_after = one(main_before,
        "        nextProbeNs2A=now+1000000000L;\n",
        "        nextProbeNs2A=now+500000000L; // MONOAUTO1D placement probe: 2 Hz\n",
        "MainRenderer probe cadence")
main.write_text(main_after)

# 3) Cache SOURCE1D placement once per probe so exposure-plan updates do not scan
# pixels on every preview result.
gpu_before = gpu.read_text()
s = gpu_before
s = one(s,
        "    private static volatile Draw lastProbe;\n",
        "    private static volatile Draw lastProbe;\n    private static volatile PlacementObservation1D lastPlacement1D;\n",
        "GPU placement field")
s = one(s,
        "            lastDraw=null; lastProbe=null; DRAWS.clear(); PROBES.clear(); activeSession++;\n",
        "            lastDraw=null; lastProbe=null; lastPlacement1D=null; DRAWS.clear(); PROBES.clear(); activeSession++;\n",
        "GPU session clear")
s = one(s,
        "        if(probe!=null) { lastProbe=d; PROBES.addLast(d); while(PROBES.size()>4) PROBES.removeFirst(); }\n",
        "        if(probe!=null) { lastProbe=d; PROBES.addLast(d); while(PROBES.size()>4) PROBES.removeFirst();\n"
        "            lastPlacement1D=placementFromProbe1D(d); }\n",
        "GPU publish cache")

placement_code = r'''
    public static final class PlacementObservation1D {
        public final boolean valid;
        public final String reason,camera;
        public final long capturedElapsedNs,sessionId;
        public final double ageMs,planScale,scaledCenterWeightedMedian,baseCenterWeightedMedian;
        public final double scaledQ99_8,baseQ99_8,scaledClipFraction;
        public final int sampleCount;
        PlacementObservation1D(boolean valid,String reason,String camera,long captured,long session,
                double ageMs,double scale,double scaledMedian,double baseMedian,
                double scaledQ998,double baseQ998,double clip,int samples) {
            this.valid=valid;this.reason=reason;this.camera=camera;capturedElapsedNs=captured;sessionId=session;
            this.ageMs=ageMs;planScale=scale;scaledCenterWeightedMedian=scaledMedian;
            baseCenterWeightedMedian=baseMedian;scaledQ99_8=scaledQ998;baseQ99_8=baseQ998;
            scaledClipFraction=clip;sampleCount=samples;
        }
        PlacementObservation1D withAge(double ms) {
            return new PlacementObservation1D(valid,reason,camera,capturedElapsedNs,sessionId,ms,planScale,
                    scaledCenterWeightedMedian,baseCenterWeightedMedian,scaledQ99_8,baseQ99_8,
                    scaledClipFraction,sampleCount);
        }
        static PlacementObservation1D invalid(String reason,String camera,long captured,long session) {
            return new PlacementObservation1D(false,reason,camera,captured,session,0.0,1.0,
                    Double.NaN,Double.NaN,Double.NaN,Double.NaN,0.0,0);
        }
    }

    private static PlacementObservation1D placementFromProbe1D(Draw d) {
        String camera=d==null?"":d.binding.frame.camera;
        long session=d==null?-1:d.binding.sessionId;
        long captured=d==null?0:d.elapsedNs;
        if(d==null || d.probe==null || d.w<=0 || d.h<=0)
            return PlacementObservation1D.invalid("probe_missing",camera,captured,session);
        if(!d.targetEnabled || d.probeError!=null)
            return PlacementObservation1D.invalid("source1d_probe_not_ready",camera,captured,session);
        if(!(d.scale>0.0f) || !Float.isFinite(d.scale))
            return PlacementObservation1D.invalid("invalid_plan_scale",camera,captured,session);
        final int bins=4096;
        long[] hist=new long[bins];
        double[] weighted=new double[bins];
        double w2=d.w/2.0,h2=d.h/2.0,den=2.0*0.75*0.75,totalWeight=0.0;
        int samples=0,clipped=0;
        for(int y=0;y<d.h;y++) {
            double ry=(y-h2)/h2;
            double rowWeight=Math.exp(-(ry*ry)/den);
            for(int x=0;x<d.w;x++) {
                int i=(y*d.w+x)*4;
                if((d.probe[i+3]&255)==0) continue;
                int code=((d.probe[i]&255)<<8)|(d.probe[i+1]&255);
                int bin=code>>>4;
                hist[bin]++;
                double rx=(x-w2)/w2;
                double wt=rowWeight*Math.exp(-(rx*rx)/den);
                weighted[bin]+=wt; totalWeight+=wt; samples++;
                if(code>=65535) clipped++;
            }
        }
        if(samples<64 || !(totalWeight>0.0))
            return PlacementObservation1D.invalid("insufficient_source1d_probe_samples",camera,captured,session);
        int q998=placementQuantileBin1D(hist,samples,0.998);
        int wm=placementWeightedMedianBin1D(weighted,totalWeight);
        double scaledMedian=placementBinValue1D(wm)/65535.0;
        double scaledQ998=placementBinValue1D(q998)/65535.0;
        double scale=d.scale;
        double baseMedian=scaledMedian/scale;
        double baseQ998=scaledQ998/scale;
        return new PlacementObservation1D(true,"live_source1d_probe",camera,captured,session,0.0,scale,
                scaledMedian,baseMedian,scaledQ998,baseQ998,clipped/(double)samples,samples);
    }

    private static int placementQuantileBin1D(long[] hist,int total,double q) {
        long target=Math.max(0L,Math.min(total-1L,(long)Math.floor((total-1L)*q)));
        long cumulative=0L;
        for(int i=0;i<hist.length;i++) {cumulative+=hist[i];if(cumulative>target)return i;}
        return hist.length-1;
    }

    private static int placementWeightedMedianBin1D(double[] hist,double total) {
        double target=total*0.5,cumulative=0.0;
        for(int i=0;i<hist.length;i++) {cumulative+=hist[i];if(cumulative>=target)return i;}
        return hist.length-1;
    }

    private static int placementBinValue1D(int bin) {
        return bin>=4095?65535:(bin<<4)+8;
    }

    public static synchronized PlacementObservation1D placementObservation1D(String camera) {
        PlacementObservation1D p=lastPlacement1D;
        long now=SystemClock.elapsedRealtimeNanos();
        if(p==null) return PlacementObservation1D.invalid("no_placement_probe",camera,0,activeSession);
        if(camera==null || !camera.equals(activeCamera) || !camera.equals(p.camera) || p.sessionId!=activeSession)
            return PlacementObservation1D.invalid("placement_context_mismatch",camera,p.capturedElapsedNs,activeSession);
        if(now<p.capturedElapsedNs || now-p.capturedElapsedNs>1500000000L)
            return PlacementObservation1D.invalid("placement_probe_stale",camera,p.capturedElapsedNs,activeSession);
        return p.withAge((now-p.capturedElapsedNs)/1.0e6);
    }

'''
s = one(s,
        "    private static Draw before(ArrayDeque<Draw> history,long shutter,long maxAge) {\n",
        placement_code + "    private static Draw before(ArrayDeque<Draw> history,long shutter,long maxAge) {\n",
        "GPU placement methods")
s = one(s,
        '                o.put("channels","R,G,B=pre_transform_OES_code;A=post_transform_monochrome_code");\n',
        '                o.put("channels","R=scaled_SOURCE1D_high8;G=scaled_SOURCE1D_low8;B=post_curve02_monochrome;A=placement_valid");\n'
        '                o.put("placementProbeRevision","MONOAUTO1D_SOURCE1D_PACK16");\n',
        "GPU probe diagnostic channels")
gpu.write_text(s)

# 4) Preserve the exact MFM classifier snapshot used for this plan evaluation.
mfm_before = mfm.read_text()
s = mfm_before
s = one(s,
        "    private static JSONObject lastLive = new JSONObject();\n",
        "    private static JSONObject lastLive = new JSONObject();\n"
        "    private static JSONObject lastMonoPlan1D = new JSONObject();\n",
        "MFM plan snapshot field")
s = one(s,
        "        if(publish) lastLive = cloneJson(out);\n",
        "        if(publish) lastLive = cloneJson(out); else lastMonoPlan1D = cloneJson(out);\n",
        "MFM plan snapshot publish")
s = one(s,
        "    public static synchronized JSONObject snapshotJson() {\n        return cloneJson(lastLive);\n    }\n",
        "    public static synchronized JSONObject snapshotJson() {\n        return cloneJson(lastLive);\n    }\n"
        "    public static synchronized JSONObject monoPlanSnapshot1D() {\n"
        "        return cloneJson(lastMonoPlan1D);\n"
        "    }\n",
        "MFM snapshot accessor")
mfm.write_text(s)

# 5) Carry the exact placement decision inside the immutable exposure plan.
plan_before = plan.read_text()
s = plan_before
s = one(s,
        "    public final double autoEv;\n    public final String cameraKey, autoReason;\n",
        "    public final double autoEv;\n    public final String cameraKey, autoReason, placementDiagnosticJson;\n",
        "plan diagnostic field")
old_header = """    public MonoExposurePlan1A(long id, long epoch, long createdNs, long sensorTimestampNs,
            String cameraKey, Controls controls, int observedIso, long observedExposureNs,
            int iso, long exposureNs, int postRawBoost, double autoEv, String autoReason, int flags) {
"""
new_header = """    public MonoExposurePlan1A(long id, long epoch, long createdNs, long sensorTimestampNs,
            String cameraKey, Controls controls, int observedIso, long observedExposureNs,
            int iso, long exposureNs, int postRawBoost, double autoEv, String autoReason, int flags) {
        this(id,epoch,createdNs,sensorTimestampNs,cameraKey,controls,observedIso,observedExposureNs,
                iso,exposureNs,postRawBoost,autoEv,autoReason,null,flags);
    }
    public MonoExposurePlan1A(long id, long epoch, long createdNs, long sensorTimestampNs,
            String cameraKey, Controls controls, int observedIso, long observedExposureNs,
            int iso, long exposureNs, int postRawBoost, double autoEv, String autoReason,
            String placementDiagnosticJson, int flags) {
"""
s = one(s, old_header, new_header, "plan overloaded constructor")
s = one(s,
        "        this.postRawBoost=postRawBoost; this.autoEv=autoEv; this.autoReason=autoReason; this.flags=flags;\n",
        "        this.postRawBoost=postRawBoost; this.autoEv=autoEv; this.autoReason=autoReason;\n"
        "        this.placementDiagnosticJson=placementDiagnosticJson; this.flags=flags;\n",
        "plan diagnostic assignment")
plan.write_text(s)

diag_before = diag.read_text()
s = diag_before
s = one(s,
        '                    .put("tripod",p.controls.tripod).put("autoAssistEv",p.autoEv).put("autoAssistReason",p.autoReason)\n',
        '                    .put("tripod",p.controls.tripod).put("autoAssistEv",p.autoEv).put("autoAssistReason",p.autoReason)\n',
        "diagnostic stable anchor")
anchor = '                    .put("rendererAndDngMathChanged",false);\n'
replacement = '                    .put("rendererAndDngMathChanged",false);\n'
replacement += '            if(p.placementDiagnosticJson!=null)\n'
replacement += '                o.put("monoPlacementAssist1D",new JSONObject(p.placementDiagnosticJson));\n'
s = one(s, anchor, replacement, "plan diagnostic JSON")
diag.write_text(s)

# 6) Replace MFM magnitude with the hybrid placement decision before the existing
# physical allocator. Manual/user controls remain authoritative through eligibility.
selector_before = selector.read_text()
s = selector_before
import_anchor = "import com.particlesdevs.photoncamera.m9.exposure.MonoExposureDiagnostics1A;\n"
if "import com.particlesdevs.photoncamera.m9.exposure.MonoPlacementAssist1D;\n" not in s:
    s = one(s, import_anchor,
            import_anchor + "import com.particlesdevs.photoncamera.m9.exposure.MonoPlacementAssist1D;\n",
            "selector assist import")
old = """        M9BacklightDiagnostic.LiveFeedbackDecision feedback=M9M10rMfmTest1A.evaluateForMonoPlan1A(
                MonoExposurePlan1A.energy(iso,exposure)/1e9,rotation,eligible,
                eligible?"eligible_mono_shared_auto_plan":"mono_manual_ev_or_tripod_bypass");
        MonoInput1A input=new MonoInput1A(iso,exposure,chars,observation,controls,feedback.appliedEv);
"""
new = """        M9BacklightDiagnostic.LiveFeedbackDecision feedback=M9M10rMfmTest1A.evaluateForMonoPlan1A(
                MonoExposurePlan1A.energy(iso,exposure)/1e9,rotation,eligible,
                eligible?"eligible_mono_shared_auto_plan":"mono_manual_ev_or_tripod_bypass");
        MonoPlacementAssist1D.Decision placement1D=MonoPlacementAssist1D.evaluate(
                eligible,feedback,M9M10rMfmTest1A.monoPlanSnapshot1D(),
                com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.placementObservation1D(cameraKey));
        MonoInput1A input=new MonoInput1A(iso,exposure,chars,observation,controls,placement1D.appliedEv);
"""
s = one(s, old, new, "selector placement decision")
old_return = """        return new MonoExposurePlan1A(now,token,entry.receivedNs,physicalTs==null?-1:physicalTs,cameraKey,controls,
                iso,exposure,pair.iso,pair.exposure,boost==null||boost<=0?100:boost,feedback.appliedEv,feedback.reason,flags);
"""
new_return = """        return new MonoExposurePlan1A(now,token,entry.receivedNs,physicalTs==null?-1:physicalTs,cameraKey,controls,
                iso,exposure,pair.iso,pair.exposure,boost==null||boost<=0?100:boost,
                placement1D.appliedEv,placement1D.reason,placement1D.diagnosticJson(),flags);
"""
s = one(s, old_return, new_return, "selector plan provenance")
selector.write_text(s)

# Version marker.
g = gradle.read_text()
m = re.search(r"versionName\s+'([^']+)'", g)
if not m:
    raise SystemExit("versionName missing")
if "monoauto1d" not in m.group(1):
    g = g[:m.start(1)] + m.group(1) + "-monoauto1d-placementassist1a" + g[m.end(1):]
    gradle.write_text(g)

frozen_after = {str(p.relative_to(root)): sha(p) for p in frozen_paths if p.exists()}
if frozen_before != frozen_after:
    changed = [k for k in frozen_before if frozen_before[k] != frozen_after.get(k)]
    raise SystemExit("MONOAUTO1D frozen JPEG/DNG/native assets changed: " + repr(changed))

changed_paths = [assist_dst, shader, main, gpu, mfm, plan, diag, selector, gradle]
proof = {
    "revision": "MONOAUTO1D_PLACEMENTASSIST1A",
    "parent": "MONOAUTO1C_PLACEMENTPROBE1A",
    "captureExposureChanged": True,
    "captureExposureChangeLocation": "pre_capture_shared_exposure_plan_before_existing_physical_allocator",
    "sceneIntent": "M10R_4x6_multifield_geometry",
    "placementMagnitude": "live_SOURCE1D_XYZ_D50_Y_before_curve02",
    "referenceTarget": 0.107 * (8192.0 / 10000.0),
    "positiveLimitEv": 0.50,
    "negativeLimitEv": -0.50,
    "liveSourceQ998Limit": 0.92,
    "physicalRawTailAvailablePreCapture": False,
    "positiveSafety": "live_SOURCE1D_q99p8_proxy_plus_hardware_AE_and_allocator_limits",
    "manualEvIsoShutterTripodAuthorityPreserved": True,
    "HDR": False,
    "postCaptureRescue": False,
    "jpegRendererChanged": False,
    "dngSamplesChanged": False,
    "baselineExposureChanged": False,
    "curve02AssetChanged": False,
    "normalDisplayMonochromeFunctionChanged": False,
    "probeCadenceHz": 2.0,
    "frozen": frozen_after,
    "changed": {
        str(p.relative_to(root)): sha(p) for p in changed_paths if p.exists()
    }
}
(root / "MONOAUTO1D_PLACEMENTASSIST1A_ISOLATION.json").write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
