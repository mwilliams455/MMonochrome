#!/usr/bin/env python3
"""Production request/context/history regression tests. Android/JSON are mocked."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
parent=here.parent/'monolivegl2a/test_state.py'
scope={'__name__':'parent_fixture_definitions'}
exec(parent.read_text().split('with tempfile.TemporaryDirectory() as d:')[0],scope)
stubs=scope['stubs'];test=scope['test'];pkg=scope['pkg']
# Extend the inherited mock only to emulate detached JSONObject string snapshots.
s=stubs['org/json/JSONObject.java']
s=s.replace('public JSONObject put(','''private static final java.util.Map<String,java.util.Map<String,Object>> snapshots=new java.util.HashMap<>();
public JSONObject(){} public JSONObject(String text){data.putAll(snapshots.get(text));}
public String toString(){String id="snapshot:"+snapshots.size();snapshots.put(id,new java.util.HashMap<>(data));return id;}
public JSONObject put(''')
stubs['org/json/JSONObject.java']=s
extra=r'''
  // GL2B math: endpoints, uniform input coordinates, correct sRGB output and exact inverse.
  for(int limit:new int[]{16,32,64,128}) {
   float[] tc=MonoPreviewMath2A.srgbCurve(limit);
   for(int i=0;i<tc.length/2;i++) {
    double x=(double)i/(tc.length/2-1);yes(Math.abs(tc[2*i]-x)<1e-7);
    double y=x<=.0031308?12.92*x:1.055*Math.pow(x,1.0/2.4)-.055;
    yes(Math.abs(tc[2*i+1]-y)<1e-7);
   }
   yes(MonoPreviewMath2A.curveOutputError(tc,tc)==0);
   yes(MonoPreviewMath2A.curveOutputError(tc,new float[]{0,0,1,1})>.28);
  }
  float[] curve=MonoPreviewMath2A.srgbCurve(64);
  float[] resampled=new float[curve.length*2-2];
  for(int i=0;i<resampled.length/2;i++) {
   float x=(float)i/(resampled.length/2-1);resampled[2*i]=x;
   resampled[2*i+1]=(float)MonoPreviewMath2A.curveOutput(curve,x);
  }
  yes(MonoPreviewMath2A.curveOutputError(curve,resampled)<1e-6);
  yes(Double.isInfinite(MonoPreviewMath2A.curveOutputError(null,curve)));
  // Recorded failure class: valid monotonic near-identity is not the requested sRGB curve.
  c=chars();q=new CaptureRequest.Builder();MonoGpuPreview2A.configure(q,c,"tele","tele",true);
  TotalCaptureResult wrong=result(1001);float[] linear={0,0,.25f,.245f,.5f,.496f,.75f,.745f,1,1};
  wrong.set(CaptureResult.TONEMAP_CURVE,new TonemapCurve(linear,linear,linear));
  int calls=com.particlesdevs.photoncamera.m9.render.M9R35Renderer.calls;
  MonoGpuPreview2A.observe(c,q,wrong,"tele","tele");
  MonoGpuPreview2A.Binding rejected=MonoGpuPreview2A.bind(1001);
  yes(!rejected.context.ready);yes(rejected.context.reason.equals("reported_curve_disagrees_with_request"));
  yes(com.particlesdevs.photoncamera.m9.render.M9R35Renderer.calls==calls);
  JSONObject contract=rejected.context.json().getJSONObject("curveContract2B");
  yes(!contract.getBoolean("agrees"));yes(((Number)contract.get("maxOutputError")).doubleValue()>.28);
  yes(rejected.context.inverse().length==0);
  MonoGpuPreview2A.observe(c,q,wrong,"tele","tele");yes(MonoGpuPreview2A.bind(1001).context==rejected.context);
  // A single contradictory channel is sufficient to reject.
  wrong=result(1002);wrong.set(CaptureResult.TONEMAP_CURVE,new TonemapCurve(curve,linear,curve));
  MonoGpuPreview2A.observe(c,q,wrong,"tele","tele");yes(!MonoGpuPreview2A.bind(1002).context.ready);
  // Small LUT rounding is allowed; agreement recovers without restarting the camera.
  float[] quantized=curve.clone();for(int i=1;i<quantized.length;i+=2)quantized[i]=Math.round(quantized[i]*4095)/4095f;
  TotalCaptureResult good=result(1003);good.set(CaptureResult.TONEMAP_CURVE,new TonemapCurve(quantized,quantized,quantized));
  MonoGpuPreview2A.observe(c,q,good,"tele","tele");MonoGpuPreview2A.Binding recovered=MonoGpuPreview2A.bind(1003);
  yes(recovered.context.ready);yes(recovered.context.json().getJSONObject("curveContract2B").getBoolean("agrees"));
  yes(!rejected.context.ready);yes(rejected.context.inverse().length==0);
  // Cache key must include the actual request, not only the reported result.
  CaptureRequest.Builder different=new CaptureRequest.Builder();different.set(CaptureRequest.TONEMAP_MODE,0);
  different.set(CaptureRequest.TONEMAP_CURVE,new TonemapCurve(linear,linear,linear));
  MonoGpuPreview2A.observe(c,different,good,"tele","tele");yes(!MonoGpuPreview2A.bind(1003).context.ready);
  yes(MonoGpuPreview2A.bind(1003).context.reason.equals("unexpected_preview_curve_request"));
  MonoGpuPreview2A.observe(c,q,good,"tele","tele");yes(MonoGpuPreview2A.bind(1003).context.ready);
  different.set(CaptureRequest.TONEMAP_CURVE,null);
  MonoGpuPreview2A.observe(c,different,good,"tele","tele");yes(!MonoGpuPreview2A.bind(1003).context.ready);
  // A post-shutter publish used to erase access to the eligible previous draw.
  MonoGpuPreview2A.configure(q,c,"history","history",true);MonoGpuPreview2A.observe(c,q,result(1100),"history","history");
  MonoGpuPreview2A.Binding h=MonoGpuPreview2A.bind(1100);long now=SystemClock.now;
  MonoGpuPreview2A.publish(h,1,0,false,true,now,new byte[]{1,2,3,4},1,1,0,null);
  MonoGpuPreview2A.publish(h,2,0,false,true,now+20,null,0,0,0,null);
  snap=MonoGpuPreview2A.snapshot(now+10);
  yes(snap.getString("status").equals("draw_recorded"));
  yes(((Number)snap.getJSONObject("draw").get("uniformExposureScale")).floatValue()==1);
  yes(snap.getJSONObject("pairedProbe").getString("rgba8Base64").equals("AQIDBA=="));
  // A missing fresh draw must not suppress an otherwise valid older paired probe.
  snap=MonoGpuPreview2A.snapshot(now+600000000L);yes(snap.getString("status").startsWith("unavailable"));
  yes(snap.has("pairedProbe"));yes(!snap.getBoolean("probeIsShutterDraw"));
  yes(!MonoGpuPreview2A.snapshot(now+2000000001L).has("pairedProbe"));
  // Bounded history and no cross-camera reuse.
  for(int i=0;i<100;i++)MonoGpuPreview2A.publish(h,1,0,false,true,now+100+i,new byte[]{1,2,3,4},1,1,0,null);
  snap=MonoGpuPreview2A.snapshot(now+500);
  yes(((Number)snap.get("drawHistoryCount")).intValue()==32);
  yes(((Number)snap.get("probeHistoryCount")).intValue()==4);
  MonoGpuPreview2A.configure(q,c,"newcamera","newcamera",true);
  MonoGpuPreview2A.publish(h,1,0,false,true,now+1000,null,0,0,0,null);
  snap=MonoGpuPreview2A.snapshot(now+1001);yes(!snap.has("draw"));yes(!snap.has("pairedProbe"));
  yes(!snap.getBoolean("displayToneParityProven"));
  // Reopening the same camera also invalidates in-flight older-session bindings.
  MonoGpuPreview2A.observe(c,q,result(1500),"newcamera","newcamera");
  MonoGpuPreview2A.Binding oldSession=MonoGpuPreview2A.bind(1500);
  MonoGpuPreview2A.configure(q,c,"newcamera","newcamera",true);
  MonoGpuPreview2A.publish(oldSession,1,0,false,true,now+2000,null,0,0,0,null);
  yes(!MonoGpuPreview2A.snapshot(now+2001).has("draw"));
'''
anchor='  System.out.println("MONOLIVEGL2A STATE PASS assertions="'
assert test.count(anchor)==1
test=test.replace(anchor,extra+anchor).replace('MONOLIVEGL2A STATE PASS','MONOLIVEGL2B STATE AND CURVE PASS')
with tempfile.TemporaryDirectory() as d:
    p=Path(d)
    for rel,source in stubs.items():
        f=p/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(source)
    for name in ['MonoPreviewMath2A.java','MonoGpuPreview2A.java']:
        f=p/pkg/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((root/'app/src/main/java'/pkg/name).read_bytes())
    (p/pkg/'StateTest.java').write_text(test)
    subprocess.run(['javac','-d',str(p/'classes')]+[str(f) for f in p.rglob('*.java')],check=True)
    subprocess.run(['java','-cp',str(p/'classes'),'com.particlesdevs.photoncamera.m9.preview.StateTest'],check=True)
proof=json.loads((root/'MONOLIVEGL2B_ISOLATION.json').read_text())
for rel,h in proof['frozen'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==h,rel
for rel,v in proof['changed'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==v['after'],rel
print('MONOLIVEGL2B frozen still/shader/export/allocator hashes PASS; phone preview not validated')
