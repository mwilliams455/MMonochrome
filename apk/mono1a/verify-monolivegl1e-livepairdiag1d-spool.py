#!/usr/bin/env python3
"""Structural/hash checks, plus host Java tests with the actual export/store classes.
Usage: verifier.py PhotonCamera-root [org-json.jar]
Host mocks replace Android storage/logging only; no device export success is claimed.
"""
from pathlib import Path
import hashlib, json, subprocess, sys, tempfile
if len(sys.argv) not in (2, 3):
    raise SystemExit(__doc__)
root = Path(sys.argv[1]).resolve()
java = root / 'app/src/main/java/com/particlesdevs/photoncamera'
d = (java/'m9/preview/MonoLivePairDiagnostics1E.java').read_text()
c = (java/'capture/CaptureController.java').read_text()
m = (java/'m9/M9DeferredMetadataStore.java').read_text()
h = (java/'m9/preview/MonoLivePairExport1D.java').read_text()
checks = {
 'Photo and ZSL call retained': c.count('MonoLivePairDiagnostics1E.writeCompleted(') == 2,
 'callback caches immutable bytes': 'MonoLivePairExport1D.remember(root);' in d,
 'no direct external file writer': all(x not in d for x in ['Files.write(', 'FileOutputStream', 'Environment.getExternalStorageDirectory']),
 'no asynchronous callback cache race': 'processExecutor.execute(() -> MonoLivePairDiagnostics1E.writeCompleted(' not in c,
 'metadata export calls helper': 'MonoLivePairExport1D.attachAndStage(jsonPath, bytes)' in m,
 'metadata spool gets embedded copy': 'M9DiagnosticBurstSpool.stage(jsonPath, monoCaptureBytes1D, "capture_metadata")' in m,
 'public fallback gets embedded copy': 'M9DiagnosticSidecarIO.persist(jsonPath, monoCaptureBytes1D,' in m,
 'rejected fallback retains embedded copy': 'STAGED.put(key, monoCaptureBytes1D);' in m,
 'same folder and same stem': 'captureJsonPath.resolveSibling(stem + "_MONO_LIVEPAIR.json")' in h,
 'standard spool transport': 'M9DiagnosticBurstSpool.stage(sidecar, pairBytes, "mono_live_pair")' in h,
 'missing match cannot be called valid': 'completed != null && previewAvailable' in h and 'unavailable_no_exact_callback_match' in h,
 'bounded pending cache': 'MAX_PENDING = 32' in h and 'while (COMPLETED.size() > MAX_PENDING)' in h,
 'Photo and Motion entry points remain': 'triggerZslCapture()' in c and 'onCaptureCompleted(' in c,
 'no display-parity claim': 'pair.put("displayToneParityProven", false)' in h,
}
for label, good in checks.items():
    print(('PASS ' if good else 'FAIL ') + label)
    if not good: raise SystemExit(label)
proof=json.loads((root/'MONOLIVEGL1E1D_ISOLATION.json').read_text())
if len(proof) != 8: raise SystemExit('expected eight frozen files')
for rel,digest in proof.items():
    if hashlib.sha256((root/rel).read_bytes()).hexdigest() != digest:
        raise SystemExit('changed photographic file: '+rel)
print('PASS eight unchanged photographic/preview/allocator SHA256 hashes')
if len(sys.argv) == 2:
    print('Host tests not requested; pass a real org.json jar to run them')
    raise SystemExit(0)
jar=Path(sys.argv[2]).resolve()
if not jar.is_file(): raise SystemExit('JSON jar missing')
spool = r'''package com.particlesdevs.photoncamera.m9;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.HashMap;
import java.util.Map;
import org.json.JSONObject;
public final class M9DiagnosticBurstSpool {
 public static final String SCHEMA="m9cam.sidecarspool.v1.privatebundle1b";
 public static boolean accept=true, fail=false;
 public static final Map<String,JSONObject> records=new HashMap<>();
 public static Path pairPath;
 public static boolean stage(Path p, byte[] b, String role) {
  if(fail)throw new IllegalStateException("injected_spool_exception");
  records.put(role,new JSONObject(new String(b,StandardCharsets.UTF_8)));
  if(role.equals("mono_live_pair"))pairPath=p;
  return accept;
 }
}'''
io = r'''package com.particlesdevs.photoncamera.m9;
import java.nio.file.Path;
public final class M9DiagnosticSidecarIO {
 public static volatile byte[] last;
 public static boolean persist(Path p,byte[] bytes,String role){last=bytes;return true;}
}'''
log = r'''package com.particlesdevs.photoncamera.util;
public final class Log {
 public static void d(String tag,String msg){}
 public static void w(String tag,String msg){}
 public static void e(String tag,String msg){}
 public static void e(String tag,String msg,Throwable e){}
}'''
harness = r'''import java.nio.file.*;
import java.nio.charset.StandardCharsets;
import org.json.JSONObject;
import com.particlesdevs.photoncamera.m9.*;
import com.particlesdevs.photoncamera.m9.preview.MonoLivePairExport1D;
public final class Export1DHostTest {
 private static int checks=0;
 private static void ok(boolean b,String label){if(!b)throw new AssertionError(label);checks++;System.out.println("HOST PASS "+label);}
 private static JSONObject capture(long ts,String camera,String mode){return new JSONObject()
  .put("schema","m9cam.photon.capture.v2").put("dng","IMG_TEST_00.dng").put("cameraId",camera)
  .put("raw",new JSONObject().put("timestampNs",ts).put("width",4096).put("height",3072))
  .put("captureRequest",new JSONObject().put("iso",50).put("exposureTimeNs",10400000))
  .put("captureResult",new JSONObject().put("iso",50).put("exposureTimeNs",10400000))
  .put("photonExposureDecision",new JSONObject().put("preview",new JSONObject().put("iso",52).put("shutterNs",10000000).put("mode","PHOTO")));}
 private static JSONObject pair(long ts,String camera,boolean preview){JSONObject p=new JSONObject().put("cameraId",camera)
  .put("captureResult",new JSONObject().put("sensorTimestampNs",ts));
  if(preview)p.put("previewExposureAuthority",new JSONObject().put("previewResultIso",52).put("previewResultExposureTimeNs",10000000));
  return p;}
 private static byte[] bytes(JSONObject j){return j.toString().getBytes(StandardCharsets.UTF_8);}
 private static JSONObject parse(byte[] b){return new JSONObject(new String(b,StandardCharsets.UTF_8));}
 private static final Path PATH=Paths.get("/storage/emulated/0/DCIM/PhotonCamera/Raw/IMG_TEST_00_M9.json");
 private static JSONObject attach(JSONObject c){return parse(MonoLivePairExport1D.attachAndStage(PATH,bytes(c)));}
 public static void main(String[] args)throws Exception {
  JSONObject c=capture(1,"2","PHOTO");MonoLivePairExport1D.remember(pair(1,"2",true));JSONObject enriched=attach(c);JSONObject p=enriched.getJSONObject("monoLivePair");
  ok(p.getBoolean("validExposurePair")&&p.getBoolean("sidecarPrivateStaged"),"exact Photo match and private stage");
  ok(M9DiagnosticBurstSpool.pairPath.equals(PATH.resolveSibling("IMG_TEST_00_MONO_LIVEPAIR.json")),"same stem and proven Raw folder");
  enriched.remove("monoLivePair");ok(enriched.similar(c),"original capture metadata preserved semantically");
  ok(!p.getBoolean("displayToneParityProven")&&!p.getBoolean("displayPixelsSampled"),"no unsupported display parity claim");
  p=attach(capture(2,"2","MOTION")).getJSONObject("monoLivePair");
  ok(p.getString("status").equals("unavailable_no_exact_callback_match")&&!p.getBoolean("validExposurePair")&&p.getBoolean("sidecarPrivateStaged"),"Motion missing callback still exports explicit record");
  MonoLivePairExport1D.remember(pair(3,"0",true));p=attach(capture(3,"2","PHOTO")).getJSONObject("monoLivePair");ok(!p.getBoolean("completedCallbackMatchedRawTimestamp"),"different camera cannot match");
  p=attach(capture(3,"0","PHOTO")).getJSONObject("monoLivePair");ok(p.getBoolean("validExposurePair"),"unrelated camera entry not consumed");
  MonoLivePairExport1D.remember(pair(4,"2",true));p=attach(capture(5,"2","PHOTO")).getJSONObject("monoLivePair");ok(!p.getBoolean("completedCallbackMatchedRawTimestamp"),"different timestamp cannot match");
  MonoLivePairExport1D.remember(pair(6,"2",false));p=attach(capture(6,"2","PHOTO")).getJSONObject("monoLivePair");ok(p.getString("status").equals("unavailable_preview_state")&&!p.getBoolean("validExposurePair"),"missing preview is explicitly unavailable");
  M9DiagnosticBurstSpool.accept=false;MonoLivePairExport1D.remember(pair(7,"2",true));p=attach(capture(7,"2","PHOTO")).getJSONObject("monoLivePair");
  ok(p.getBoolean("validExposurePair")&&!p.getBoolean("sidecarPrivateStaged")&&p.has("sidecarStageError"),"private stage rejection preserves complete inline record");
  M9DiagnosticBurstSpool.accept=true;M9DiagnosticBurstSpool.fail=true;enriched=attach(capture(8,"2","PHOTO"));p=enriched.getJSONObject("monoLivePair");
  ok(p.getString("status").equals("diagnostic_export_exception")&&enriched.getJSONObject("raw").getLong("timestampNs")==8,"spool exception visible without losing capture metadata");
  M9DiagnosticBurstSpool.fail=false;
  for(int i=100;i<140;i++)MonoLivePairExport1D.remember(pair(i,"2",true));
  p=attach(capture(100,"2","PHOTO")).getJSONObject("monoLivePair");
  ok(!p.getBoolean("completedCallbackMatchedRawTimestamp")&&p.getJSONObject("writerTelemetry").getInt("pendingCompletedCount")<=32,"cache bounded and oldest record evicted");
  MonoLivePairExport1D.remember(pair(200,"2",true));c=capture(200,"2","PHOTO");
  M9DeferredMetadataStore.stage(PATH,bytes(c));ok(M9DeferredMetadataStore.persistAsyncForDng(PATH.resolveSibling("IMG_TEST_00.dng")),"actual deferred-store normal path accepted");
  ok(M9DiagnosticBurstSpool.records.get("capture_metadata").getJSONObject("monoLivePair").getBoolean("validExposurePair"),"actual deferred-store capture bundle includes exact pair");
  M9DiagnosticBurstSpool.accept=false;M9DiagnosticSidecarIO.last=null;MonoLivePairExport1D.remember(pair(201,"2",true));
  M9DeferredMetadataStore.stage(PATH,bytes(capture(201,"2","PHOTO")));M9DeferredMetadataStore.persistAsyncForDng(PATH.resolveSibling("IMG_TEST_00.dng"));
  for(int i=0;i<100&&M9DiagnosticSidecarIO.last==null;i++)Thread.sleep(5);
  ok(M9DiagnosticSidecarIO.last!=null&&parse(M9DiagnosticSidecarIO.last).getJSONObject("monoLivePair").getBoolean("validExposurePair"),"actual asynchronous public fallback keeps embedded pair");
  M9DiagnosticBurstSpool.accept=true;p=attach(capture(200,"2","PHOTO")).getJSONObject("monoLivePair");ok(!p.getBoolean("completedCallbackMatchedRawTimestamp"),"completed record consumed only once");
  byte[] original=bytes(c);ok(MonoLivePairExport1D.attachAndStage(null,original)==original&&MonoLivePairExport1D.attachAndStage(PATH,null)==null,"null arguments preserve existing contract");
  System.out.println("HOST TESTS PASSED: "+checks+"; storage is mocked, Android device export remains unvalidated");
 }
}'''
with tempfile.TemporaryDirectory(prefix='mono1d-host-') as td:
    td=Path(td)
    sources={'com/particlesdevs/photoncamera/m9/M9DiagnosticBurstSpool.java':spool,
             'com/particlesdevs/photoncamera/m9/M9DiagnosticSidecarIO.java':io,
             'com/particlesdevs/photoncamera/util/Log.java':log,
             'com/particlesdevs/photoncamera/m9/preview/MonoLivePairExport1D.java':h,
             'com/particlesdevs/photoncamera/m9/M9DeferredMetadataStore.java':m,
             'Export1DHostTest.java':harness}
    for rel,text in sources.items():
        f=td/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(text)
    args=['javac','-cp',str(jar),'-d',str(td/'classes')]+[str(td/x) for x in sources]
    subprocess.run(args,check=True)
    subprocess.run(['java','-cp',str(td/'classes')+':'+str(jar),'Export1DHostTest'],check=True)
print('MONOLIVEGL1E1D structural, hash and host tests PASS')
