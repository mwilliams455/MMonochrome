#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
store=J/"m9/exposure/MonoExposureStore1A.java"
gpu=J/"m9/preview/MonoGpuPreview2A.java"
assist=J/"m9/exposure/MonoPlacementAssist1D.java"
capture=J/"capture/CaptureController.java"
gradle=root/"app/build.gradle"
for p in (store,gpu,assist,capture,gradle):
    if not p.exists(): raise SystemExit("BUFFERHYGIENE1A missing "+str(p))

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,name):
    if s.count(a)!=1:
        raise SystemExit(f"{name} anchor mismatch count={s.count(a)}")
    return s.replace(a,b,1)

if "MONOAUTO1D_PLACEMENTASSIST1D_BROADTAIL05" not in assist.read_text():
    raise SystemExit("BUFFERHYGIENE1A requires 1D BROADTAIL05 parent")
if "lastPlacement1D" not in gpu.read_text():
    raise SystemExit("BUFFERHYGIENE1A requires placement cache parent")

# Freeze all photographic rendering and the exposure mathematics themselves.
frozen=[
    J/"m9/render/M9R35Renderer.java",
    J/"m9/export/MonoDngExport1A.java",
    J/"m9/export/MonoDngWriter1A.java",
    J/"m9/export/MonoLinearPlane1A.java",
    J/"m9/export/MonoPlacementProbe1A.java",
    J/"m9/M9M10rMfmTest1A.java",
    root/"app/src/main/cpp/m9color_jni.cpp",
    root/"app/src/main/assets/mono/mono_curve02_gl2a.bin",
    root/"app/src/main/assets/shaders/preview/main_fs.glsl",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}

# 1) Controller-local exposure store: current-plan-only draw selection plus an
# explicit shutter boundary that rejects all in-flight pre-shutter plan tokens.
ss=store.read_text()
ss=one(ss,
'''    public synchronized void invalidate() { epoch++; latest=null; draws.clear(); }
''',
'''    public synchronized void invalidate() { epoch++; latest=null; draws.clear(); }
    /**
     * A still shutter is a hard scene-state boundary. The selected plan object
     * remains usable by the current capture request, but every queued/in-flight
     * plan token from before this shutter becomes invalid for the next shot.
     */
    public synchronized void captureBoundary(long shutterNs) {
        epoch++;
        latest=null;
        draws.clear();
    }
''',"store capture boundary")

ss=one(ss,
'''    public synchronized void drawn(MonoExposurePlan1A p,long now,long textureNs,float scale) {
        if(!accepts(p,now) || !Float.isFinite(scale) || scale<=0) return;
        draws.addLast(new Draw(p,now,textureNs,scale));
        while(draws.size()>48) draws.removeFirst();
    }
    public synchronized Selection select(long shutterNs) {
        for(Iterator<Draw> i=draws.descendingIterator();i.hasNext();) {
            Draw d=i.next();
            if(accepts(d.plan,shutterNs) && d.elapsedNs<=shutterNs && shutterNs-d.elapsedNs<=500000000L)
                return new Selection(d.plan,"recent_pre_shutter_GL_draw",d.elapsedNs,d.textureNs,d.scale);
        }
        MonoExposurePlan1A p=latest(shutterNs);
        return new Selection(p,p==null?"no_current_plan":"current_plan_no_recent_GL_acknowledgement",
                -1,-1,p==null?1.0f:MonoExposurePlan1A.boundedScale(p.previewScale()));
    }
''',
'''    public synchronized void drawn(MonoExposurePlan1A p,long now,long textureNs,float scale) {
        if(!accepts(p,now) || !Float.isFinite(scale) || scale<=0) return;
        // Remove entries which can no longer be selected before adding another.
        for(Iterator<Draw> i=draws.iterator();i.hasNext();) {
            Draw d=i.next();
            if(now<d.elapsedNs || now-d.elapsedNs>500000000L || !accepts(d.plan,now)) i.remove();
        }
        draws.addLast(new Draw(p,now,textureNs,scale));
        while(draws.size()>48) draws.removeFirst();
    }
    public synchronized Selection select(long shutterNs) {
        MonoExposurePlan1A current=latest(shutterNs);
        int staleTargets=0, expired=0;
        for(Iterator<Draw> i=draws.descendingIterator();i.hasNext();) {
            Draw d=i.next();
            if(!accepts(d.plan,shutterNs) || d.elapsedNs>shutterNs || shutterNs-d.elapsedNs>500000000L) {
                expired++;
                continue;
            }
            // Critical hygiene rule: a recently drawn OLD plan must never beat
            // the newer current scene plan merely because it reached GL first.
            if(current==null || d.plan.id!=current.id) {
                staleTargets++;
                continue;
            }
            return new Selection(d.plan,
                    staleTargets==0?"latest_plan_recent_pre_shutter_GL_draw":
                    "latest_plan_recent_pre_shutter_GL_draw_after_skipping_"+staleTargets+"_stale_targets",
                    d.elapsedNs,d.textureNs,d.scale);
        }
        String why=current==null?"no_current_plan":"current_latest_plan_no_matching_recent_GL_acknowledgement";
        if(staleTargets>0) why+="_stale_targets_skipped_"+staleTargets;
        if(expired>0) why+="_expired_entries_ignored_"+expired;
        return new Selection(current,why,-1,-1,current==null?1.0f:MonoExposurePlan1A.boundedScale(current.previewScale()));
    }
''',"store latest-only selection")
store.write_text(ss)

# 2) Placement cache: establish a hard shutter boundary and reduce maximum
# pre-capture placement age to 750 ms (2 Hz probe cadence is 500 ms).
gs=gpu.read_text()
gs=one(gs,
'''    private static volatile Draw lastProbe;
    private static volatile PlacementObservation1D lastPlacement1D;
''',
'''    private static volatile Draw lastProbe;
    private static volatile PlacementObservation1D lastPlacement1D;
    private static long lastCaptureBoundaryNs1E;
''',"gpu boundary field")
gs=one(gs,
'''            lastDraw=null; lastProbe=null; lastPlacement1D=null; DRAWS.clear(); PROBES.clear(); activeSession++;
''',
'''            lastDraw=null; lastProbe=null; lastPlacement1D=null; lastCaptureBoundaryNs1E=0;
            DRAWS.clear(); PROBES.clear(); activeSession++;
''',"gpu session reset")
anchor='''    public static synchronized PlacementObservation1D placementObservation1D(String camera) {
'''
method='''    public static synchronized void captureBoundary1E(String camera,long shutterElapsedNs) {
        if(camera!=null && camera.equals(activeCamera) && shutterElapsedNs>lastCaptureBoundaryNs1E)
            lastCaptureBoundaryNs1E=shutterElapsedNs;
    }

'''
gs=one(gs,anchor,method+anchor,"gpu capture boundary method")
gs=one(gs,
'''        if(now<p.capturedElapsedNs || now-p.capturedElapsedNs>1500000000L)
            return PlacementObservation1D.invalid("placement_probe_stale",camera,p.capturedElapsedNs,activeSession);
''',
'''        if(p.capturedElapsedNs<=lastCaptureBoundaryNs1E)
            return PlacementObservation1D.invalid("placement_probe_precedes_last_capture_boundary",camera,p.capturedElapsedNs,activeSession);
        if(now<p.capturedElapsedNs || now-p.capturedElapsedNs>750000000L)
            return PlacementObservation1D.invalid("placement_probe_stale_over_750ms",camera,p.capturedElapsedNs,activeSession);
''',"gpu placement freshness")
gpu.write_text(gs)

# 3) No fresh placement => no Monochrom placement assist. Previously this path
# fell back to the full MFM EV, which could bypass the highlight guard entirely.
asrc=assist.read_text()
asrc=one(asrc,
'public static final String REVISION = "MONOAUTO1D_PLACEMENTASSIST1D_BROADTAIL05";',
'public static final String REVISION = "MONOAUTO1D_PLACEMENTASSIST1E_BUFFERHYGIENE1A";',
"assist revision")
asrc=one(asrc,
'''            if (placement == null || !placement.valid) {
                applied = clamp(mfmApplied, -MAX_NEGATIVE_EV, MAX_POSITIVE_EV);
                reason = "monoauto1d_placement_unavailable_mfm_fallback"
                        + (placement == null ? "" : "_" + placement.reason);
                d.put("placementAvailable", false);
                return finish(d, applied, reason);
            }
''',
'''            if (placement == null || !placement.valid) {
                applied = 0.0;
                reason = "monoauto1e_wait_for_fresh_placement"
                        + (placement == null ? "" : "_" + placement.reason);
                d.put("placementAvailable", false);
                d.put("stalePlacementMfmFallbackSuppressed", true);
                return finish(d, applied, reason);
            }
''',"assist stale fallback")
assist.write_text(asrc)

# 4) Once the current shutter plan has been selected, invalidate both controller
# plan-buffer state and placement state for the NEXT shot. The selected immutable
# plan object is still used for this capture request.
cs=capture.read_text()
old='''    private MonoExposureStore1A.Selection selectMonoCapturePlan1A(long shutterNs) {
        if(!useMonoExposurePlan1A()) return null;
        monoExposureStore1A.context(monoCameraKey1A(),monoControls1A());
        MonoExposureStore1A.Selection selected=monoExposureStore1A.select(shutterNs);
        if(selected.plan!=null) return selected;
        // Correct current controls win over stale drawn controls. No hardware-AE exposure fallback.
        MonoExposurePlan1A fresh=updateMonoExposurePlan1A(mPreviewCaptureResult);
        return fresh==null?selected:new MonoExposureStore1A.Selection(fresh,
                "fresh_current_control_plan_not_yet_GL_drawn",-1,-1,MonoExposurePlan1A.boundedScale(fresh.previewScale()));
    }
'''
new='''    private MonoExposureStore1A.Selection selectMonoCapturePlan1A(long shutterNs) {
        if(!useMonoExposurePlan1A()) return null;
        final String camera1E=monoCameraKey1A();
        monoExposureStore1A.context(camera1E,monoControls1A());
        MonoExposureStore1A.Selection selected=monoExposureStore1A.select(shutterNs);
        if(selected.plan==null) {
            // Correct current controls win over stale drawn controls. No hardware-AE exposure fallback.
            MonoExposurePlan1A fresh=updateMonoExposurePlan1A(mPreviewCaptureResult);
            if(fresh!=null) selected=new MonoExposureStore1A.Selection(fresh,
                    "fresh_current_control_plan_not_yet_GL_drawn",-1,-1,
                    MonoExposurePlan1A.boundedScale(fresh.previewScale()));
        }
        if(selected.plan!=null) {
            // The immutable selected plan survives for this request. Everything
            // feeding the next request must be newer than this shutter.
            com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.captureBoundary1E(camera1E,shutterNs);
            monoExposureStore1A.captureBoundary(shutterNs);
        }
        return selected;
    }
'''
cs=one(cs,old,new,"capture plan shutter boundary")
capture.write_text(cs)

g=gradle.read_text()
m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("versionName missing")
v=m.group(1)
if "monoauto1d1e-bufferhygiene1a" not in v:
    g=g[:m.start(1)]+v+"-monoauto1d1e-bufferhygiene1a"+g[m.end(1):]
    gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("BUFFERHYGIENE1A frozen photographic seam changed: "+repr(changed))

proof={
 "revision":"MONOAUTO1D_PLACEMENTASSIST1E_BUFFERHYGIENE1A",
 "parent":"MONOAUTO1D_PLACEMENTASSIST1D_BROADTAIL05",
 "broadTailCalibrationChanged":False,
 "mfmMathChanged":False,
 "sourcePlacementMathChanged":False,
 "jpegRendererChanged":False,
 "dngSamplesChanged":False,
 "curve02Changed":False,
 "HDR":False,
 "bufferChanges":{
   "exposureStoreCurrentPlanDrawOnly":True,
   "exposureStoreShutterEpochBoundary":True,
   "placementShutterBoundary":True,
   "placementMaxAgeMs":750,
   "stalePlacementMfmFallbackSuppressed":True,
   "expiredDrawEntriesPruned":True
 },
 "oldRisksClosed":[
   "recent_GL_draw_from_older_plan_could_beat_newer_latest_plan",
   "pre_shutter_placement_cache_could_feed_successive_shot",
   "placement_cache_was_accepted_for_up_to_1500ms",
   "missing_or_stale_placement_could_fall_back_to_unguarded_MFM_EV"
 ],
 "frozen":after
}
(root/"MONOAUTO1D_PLACEMENTASSIST1E_BUFFERHYGIENE1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
