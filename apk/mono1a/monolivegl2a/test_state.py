#!/usr/bin/env python3
"""Run the actual metadata/binding class using deterministic Android/JSON mocks (not phone validation)."""
from pathlib import Path
import subprocess,sys,tempfile
root=Path(sys.argv[1]); pkg='com/particlesdevs/photoncamera/m9/preview/'
stubs={
'android/os/Build.java':'package android.os; public class Build {public static class VERSION {public static int SDK_INT=36;}}',
'android/os/SystemClock.java':'package android.os; public class SystemClock {public static long now=1000000000L; public static long elapsedRealtimeNanos(){return now;}}',
'android/util/Rational.java':'''package android.util; public class Rational extends Number {final int a,b;public Rational(int a,int b){this.a=a;this.b=b;} public double doubleValue(){return (double)a/b;}public float floatValue(){return (float)doubleValue();}public int intValue(){return (int)doubleValue();}public long longValue(){return (long)doubleValue();}public String toString(){return a+"/"+b;}}''',
'android/util/Base64.java':'package android.util;public class Base64 {public static final int NO_WRAP=2;public static String encodeToString(byte[] b,int f){return java.util.Base64.getEncoder().encodeToString(b);}}',
'android/hardware/camera2/params/TonemapCurve.java':'''package android.hardware.camera2.params;public class TonemapCurve {private float[][] a;public TonemapCurve(float[] r,float[] g,float[] b){a=new float[][]{r.clone(),g.clone(),b.clone()};}public int getPointCount(int c){return a[c].length/2;}public void copyColorCurve(int c,float[] d,int o){System.arraycopy(a[c],0,d,o,a[c].length);}public String toString(){return java.util.Arrays.deepToString(a);}}''',
'android/hardware/camera2/params/ColorSpaceTransform.java':'''package android.hardware.camera2.params;import android.util.Rational;public class ColorSpaceTransform {private Rational[] a;public ColorSpaceTransform(Rational[] a){this.a=a.clone();}public void copyElements(Rational[] b,int o){System.arraycopy(a,0,b,o,9);}public String toString(){return java.util.Arrays.toString(a);}}''',
'android/hardware/camera2/params/RggbChannelVector.java':'''package android.hardware.camera2.params;public class RggbChannelVector {float r,e,o,b;public RggbChannelVector(float r,float e,float o,float b){this.r=r;this.e=e;this.o=o;this.b=b;}public float getRed(){return r;}public float getGreenEven(){return e;}public float getGreenOdd(){return o;}public float getBlue(){return b;}public String toString(){return r+","+e+","+o+","+b;}}''',
'org/json/JSONArray.java':'''package org.json;public class JSONArray {public Object value; public JSONArray(){value=new java.util.ArrayList<>();}public JSONArray(Object v){value=v;}@SuppressWarnings("unchecked") public JSONArray put(Object v){((java.util.List<Object>)value).add(v);return this;}}''',
'org/json/JSONObject.java':'''package org.json;public class JSONObject {public static final Object NULL=new Object();private java.util.Map<String,Object> data=new java.util.HashMap<>();public JSONObject put(String k,Object v){data.put(k,v);return this;}public Object get(String k){if(!data.containsKey(k))throw new IllegalArgumentException(k);return data.get(k);}public boolean has(String k){return data.containsKey(k);}public JSONObject getJSONObject(String k){return (JSONObject)get(k);}public String getString(String k){return (String)get(k);}public boolean getBoolean(String k){return (Boolean)get(k);}}''',
'com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java':'''package com.particlesdevs.photoncamera.m9.render;import android.hardware.camera2.*;public class M9R35Renderer {public static int calls;public static float[] exportMonoPreviewY2A(CameraCharacteristics c,CaptureResult r){calls++;return new float[]{.627451f,.7578125f,.042553194f};}}'''
}
traits={
'CameraCharacteristics':{'TONEMAP_AVAILABLE_TONE_MAP_MODES':'int[]','TONEMAP_MAX_CURVE_POINTS':'Integer'},
'CaptureRequest':{'TONEMAP_MODE':'Integer','TONEMAP_CURVE':'android.hardware.camera2.params.TonemapCurve'},
'CaptureResult':{'SENSOR_TIMESTAMP':'Long','TONEMAP_MODE':'Integer','TONEMAP_CURVE':'android.hardware.camera2.params.TonemapCurve','COLOR_CORRECTION_TRANSFORM':'android.hardware.camera2.params.ColorSpaceTransform','COLOR_CORRECTION_GAINS':'android.hardware.camera2.params.RggbChannelVector','SENSOR_NEUTRAL_COLOR_POINT':'android.util.Rational[]','CONTROL_POST_RAW_SENSITIVITY_BOOST':'Integer','SENSOR_SENSITIVITY':'Integer','SENSOR_EXPOSURE_TIME':'Long','SHADING_MODE':'Integer','COLOR_CORRECTION_MODE':'Integer','CONTROL_AE_MODE':'Integer','CONTROL_AWB_MODE':'Integer'}}
for cls,fields in traits.items():
 s='package android.hardware.camera2;public class '+cls+' { public static final int TONEMAP_MODE_CONTRAST_CURVE=0; public static class Key<T> {} private java.util.Map<Object,Object> m=new java.util.HashMap<>(); @SuppressWarnings("unchecked") public <T>T get(Key<T> k){return (T)m.get(k);} public <T>void set(Key<T> k,T v){m.put(k,v);}'
 for name,t in fields.items():s+='public static final Key<'+t+'> '+name+'=new Key<>();'
 if cls=='CaptureRequest':s+='public static class Builder extends CaptureRequest {public CaptureRequest build(){return this;}}'
 stubs['android/hardware/camera2/'+cls+'.java']=s+'}'
stubs['android/hardware/camera2/TotalCaptureResult.java']='''package android.hardware.camera2;public class TotalCaptureResult extends CaptureResult {public java.util.Map<String,TotalCaptureResult> physical=new java.util.HashMap<>();public java.util.Map<String,TotalCaptureResult> getPhysicalCameraResults(){return physical;}}'''
test=r'''
package com.particlesdevs.photoncamera.m9.preview;
import android.hardware.camera2.*;import android.hardware.camera2.params.*;import android.util.Rational;import android.os.SystemClock;import org.json.*;
public class StateTest {
 static int count;static void yes(boolean b){count++;if(!b)throw new AssertionError("state "+count);}
 static CameraCharacteristics chars(){CameraCharacteristics c=new CameraCharacteristics();c.set(CameraCharacteristics.TONEMAP_AVAILABLE_TONE_MAP_MODES,new int[]{0,1,2});c.set(CameraCharacteristics.TONEMAP_MAX_CURVE_POINTS,64);return c;}
 static TotalCaptureResult result(long ts) {TotalCaptureResult r=new TotalCaptureResult();float[] curve=MonoPreviewMath2A.srgbCurve(64);r.set(CaptureResult.TONEMAP_MODE,0);r.set(CaptureResult.TONEMAP_CURVE,new TonemapCurve(curve,curve,curve));Rational[] a=new Rational[9];for(int i=0;i<9;i++)a[i]=new Rational(i%4==0?1:0,1);r.set(CaptureResult.COLOR_CORRECTION_TRANSFORM,new ColorSpaceTransform(a));r.set(CaptureResult.COLOR_CORRECTION_GAINS,new RggbChannelVector(2,1,1,1.5f));r.set(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT,new Rational[]{new Rational(1,2),new Rational(1,1),new Rational(2,3)});r.set(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST,100);r.set(CaptureResult.SENSOR_TIMESTAMP,ts);r.set(CaptureResult.SENSOR_SENSITIVITY,500);r.set(CaptureResult.SENSOR_EXPOSURE_TIME,10000000L);return r;}
 public static void main(String[] args)throws Exception {
  CameraCharacteristics c=chars();CaptureRequest.Builder q=new CaptureRequest.Builder();
  MonoGpuPreview2A.configure(q,c,"2","2",true);yes(q.get(CaptureRequest.TONEMAP_MODE)==0);
  yes(q.get(CaptureRequest.TONEMAP_CURVE).getPointCount(0)==64);
  yes(!MonoGpuPreview2A.bind(1).context.ready);
  MonoGpuPreview2A.observe(c,q,result(100),"2","2");MonoGpuPreview2A.Binding first=MonoGpuPreview2A.bind(100);
  yes(first.exact);yes(first.context.ready);yes(first.context.json().getString("source").equals("SOURCE1D_NATIVE_DNG_XYZ_Y"));
  float[] temp=first.context.y();temp[0]=999;yes(first.context.y()[0]!=999);
  byte[] raw=first.context.inverse();raw[0]=99;yes(first.context.inverse()[0]!=99);
  // A later callback cannot rewrite the context retained by a draw binding.
  TotalCaptureResult altered=result(101);altered.set(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST,200);
  MonoGpuPreview2A.observe(c,q,altered,"2","2");MonoGpuPreview2A.Binding second=MonoGpuPreview2A.bind(101);
  yes(second.context!=first.context);yes(first.context.undo()[0]==.5f);yes(second.context.undo()[0]==.25f);
  byte[] pixels={1,2,3,4};MonoGpuPreview2A.publish(first,.5f,0,false,true,SystemClock.now,pixels,1,1,200000,"ok");pixels[0]=77;
  JSONObject snap=MonoGpuPreview2A.snapshot(SystemClock.now+1);yes(snap.getString("status").equals("draw_recorded"));
  yes(snap.getJSONObject("draw").getBoolean("targetShaderEnabled"));
  yes(((Number)snap.getJSONObject("draw").get("uniformExposureScale")).floatValue()==.5f);
  yes(snap.getJSONObject("pairedProbe").getString("rgba8Base64").equals("AQIDBA=="));
  yes(!snap.getJSONObject("draw").getBoolean("framebufferPresentedToDisplayProven"));
  yes(MonoGpuPreview2A.snapshot(SystemClock.now-1).getString("status").startsWith("unavailable"));
  yes(MonoGpuPreview2A.snapshot(SystemClock.now+500000001L).getString("status").startsWith("unavailable"));
  MonoGpuPreview2A.publish(second,1,0,false,true,SystemClock.now+10,null,0,0,0,null);
  yes(!MonoGpuPreview2A.snapshot(SystemClock.now+11).getBoolean("probeIsShutterDraw"));
  yes(!MonoGpuPreview2A.bind(102).exact);SystemClock.now+=300000000L;yes(!MonoGpuPreview2A.bind(102).context.ready);
  // Every missing/noninvertible source case is a fallback, never RAW transforms on unchecked OES.
  for(int n=0;n<7;n++){TotalCaptureResult r=result(200+n);
   switch(n){case 0:r.set(CaptureResult.TONEMAP_MODE,1);break;case 1:r.set(CaptureResult.TONEMAP_CURVE,null);break;case 2:r.set(CaptureResult.COLOR_CORRECTION_TRANSFORM,null);break;case 3:r.set(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST,null);break;case 4:r.set(CaptureResult.COLOR_CORRECTION_GAINS,new RggbChannelVector(2,1,2,1));break;case 5:r.set(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT,null);break;case 6:float[] a={0,0,.5f,.5f,1,.5f};r.set(CaptureResult.TONEMAP_CURVE,new TonemapCurve(a,a,a));}
   MonoGpuPreview2A.observe(c,q,r,"2","2");yes(!MonoGpuPreview2A.bind(200+n).context.ready);
  }
  // Do not substitute logical metadata for an absent physical-camera result.
  MonoGpuPreview2A.configure(q,c,"0","2",true);MonoGpuPreview2A.observe(c,q,result(400),"0","2");
  yes(!MonoGpuPreview2A.bind(400).context.ready);yes(MonoGpuPreview2A.bind(400).context.reason.equals("physical_result_unavailable"));
  TotalCaptureResult logical=result(500);logical.physical.put("2",result(501));MonoGpuPreview2A.observe(c,q,logical,"0","2");
  MonoGpuPreview2A.Binding physical=MonoGpuPreview2A.bind(501);yes(physical.context.ready);yes(physical.exact);yes(MonoGpuPreview2A.bind(500).exact);
  MonoGpuPreview2A.publish(physical,1,0,false,true,SystemClock.now,null,0,0,0,null);
  yes(MonoGpuPreview2A.snapshot(SystemClock.now+1).getJSONObject("draw").getBoolean("textureMatchesPhysicalTimestamp"));
  MonoGpuPreview2A.configure(q,c,"4","4",true);yes(!MonoGpuPreview2A.bind(501).context.ready);
  yes(MonoGpuPreview2A.snapshot(SystemClock.now+1).getString("status").startsWith("unavailable"));
  MonoGpuPreview2A.observe(c,q,result(900),"0","2");yes(!MonoGpuPreview2A.bind(900).context.ready);
  CameraCharacteristics unsupported=chars();unsupported.set(CameraCharacteristics.TONEMAP_AVAILABLE_TONE_MAP_MODES,new int[]{1});
  CaptureRequest.Builder u=new CaptureRequest.Builder();MonoGpuPreview2A.configure(u,unsupported,"5","5",true);yes(u.get(CaptureRequest.TONEMAP_MODE)==null);
  yes(!MonoGpuPreview2A.bind(501).context.ready);
  System.out.println("MONOLIVEGL2A STATE PASS assertions="+count+"; actual binding class, mocked Android/JSON, not device validation");
 }
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d)
 for rel,source in stubs.items():f=p/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(source)
 for name in ['MonoPreviewMath2A.java','MonoGpuPreview2A.java']:
  f=p/pkg/name;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes((root/'app/src/main/java'/pkg/name).read_bytes())
 (p/pkg/'StateTest.java').write_text(test)
 subprocess.run(['javac','-d',str(p/'classes')]+[str(f) for f in p.rglob('*.java')],check=True)
 subprocess.run(['java','-cp',str(p/'classes'),'com.particlesdevs.photoncamera.m9.preview.StateTest'],check=True)
