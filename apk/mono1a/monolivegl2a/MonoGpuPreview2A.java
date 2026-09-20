package com.particlesdevs.photoncamera.m9.preview;

import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.hardware.camera2.TotalCaptureResult;
import android.hardware.camera2.params.ColorSpaceTransform;
import android.hardware.camera2.params.RggbChannelVector;
import android.hardware.camera2.params.TonemapCurve;
import android.os.Build;
import android.os.SystemClock;
import android.util.Rational;
import android.util.Base64;
import com.particlesdevs.photoncamera.m9.render.M9R35Renderer;
import org.json.JSONArray;
import org.json.JSONObject;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.Map;

/** MONOLIVEGL2A_CONTROLLEDOES. Camera inputs and draw evidence, never still feedback. */
public final class MonoGpuPreview2A {
    public static final String REVISION="MONOLIVEGL2A_CONTROLLEDOES";
    public static final String CURVE_SHA="7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752";
    private static final int MAX_RESULTS=96;
    private static final long MAX_CONTEXT_AGE_NS=250000000L;
    private static final Map<Long, Frame> RESULTS=new LinkedHashMap<>();
    private static String activeCamera="";
    private static String cachedKey="";
    private static Context cachedContext;
    private static Frame latest;
    private static volatile Draw lastDraw;
    private static volatile Draw lastProbe;
    private static String configuration="not_configured";
    private static int[] availableModes=new int[0];
    private static long sequence;
    private MonoGpuPreview2A() {}

    public static synchronized void configure(CaptureRequest.Builder builder, CameraCharacteristics chars,
            String logicalId, String physicalId, boolean newSession) {
        String camera=logicalId+"/"+physicalId;
        if (newSession || !camera.equals(activeCamera)) {
            activeCamera=camera; RESULTS.clear(); latest=null; cachedContext=null; cachedKey="";
            lastDraw=null; lastProbe=null;
        }
        try {
            if (chars==null || builder==null) { configuration="missing_characteristics"; return; }
            int[] modes=chars.get(CameraCharacteristics.TONEMAP_AVAILABLE_TONE_MAP_MODES);
            availableModes=modes==null?new int[0]:modes.clone();
            boolean supported=false;
            for (int mode:availableModes) if(mode==CaptureRequest.TONEMAP_MODE_CONTRAST_CURVE) supported=true;
            Integer max=chars.get(CameraCharacteristics.TONEMAP_MAX_CURVE_POINTS);
            if (!supported || max==null || max<16) { configuration="controlled_curve_not_supported"; return; }
            float[] c=MonoPreviewMath2A.srgbCurve(max);
            builder.set(CaptureRequest.TONEMAP_MODE,CaptureRequest.TONEMAP_MODE_CONTRAST_CURVE);
            builder.set(CaptureRequest.TONEMAP_CURVE,new TonemapCurve(c,c,c));
            configuration="controlled_curve_requested_"+(c.length/2)+"_points";
        } catch (Exception e) { configuration="configure_error:"+e.getClass().getSimpleName(); }
    }

    public static synchronized void observe(CameraCharacteristics chars, CaptureRequest request,
            TotalCaptureResult total, String logicalId, String physicalId) {
        String camera=logicalId+"/"+physicalId;
        if (!camera.equals(activeCamera) || total==null || logicalId==null || physicalId==null) return;
        CaptureResult physical=total;
        if (!logicalId.equals(physicalId)) {
            if (Build.VERSION.SDK_INT<28) physical=null;
            else physical=total.getPhysicalCameraResults().get(physicalId);
        }
        try {
            Long transportTs=total.get(CaptureResult.SENSOR_TIMESTAMP);
            Long sensorTs=physical==null?null:physical.get(CaptureResult.SENSOR_TIMESTAMP);
            Context context=physical==null?Context.fallback("physical_result_unavailable"):
                    context(chars,request,physical);
            Frame f=new Frame(camera,physicalId,physical,request,context,
                    transportTs==null?-1:transportTs,sensorTs==null?-1:sensorTs,SystemClock.elapsedRealtimeNanos());
            latest=f;
            if (transportTs!=null && transportTs>0) RESULTS.put(transportTs,f);
            if (sensorTs!=null && sensorTs>0) RESULTS.put(sensorTs,f);
            while(RESULTS.size()>MAX_RESULTS) RESULTS.remove(RESULTS.keySet().iterator().next());
        } catch(Exception e) {
            latest=new Frame(camera,physicalId,null,request,Context.fallback("observe_error:"+e.getClass().getSimpleName()),
                    -1,-1,SystemClock.elapsedRealtimeNanos());
        }
    }

    private static Context context(CameraCharacteristics chars,CaptureRequest request,CaptureResult result) throws Exception {
        Integer mode=result.get(CaptureResult.TONEMAP_MODE);
        Integer requested=request==null?null:request.get(CaptureRequest.TONEMAP_MODE);
        if (mode==null || mode!=CaptureResult.TONEMAP_MODE_CONTRAST_CURVE || requested==null ||
                requested!=CaptureRequest.TONEMAP_MODE_CONTRAST_CURVE) return Context.fallback("controlled_curve_not_reported");
        TonemapCurve tone=result.get(CaptureResult.TONEMAP_CURVE);
        ColorSpaceTransform transform=result.get(CaptureResult.COLOR_CORRECTION_TRANSFORM);
        RggbChannelVector gains=result.get(CaptureResult.COLOR_CORRECTION_GAINS);
        Rational[] neutral=result.get(CaptureResult.SENSOR_NEUTRAL_COLOR_POINT);
        Integer boost=result.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST);
        if(tone==null || transform==null || gains==null || neutral==null || chars==null || boost==null || boost<=0)
            return Context.fallback("incomplete_source_contract");
        if(Math.abs(gains.getGreenEven()-gains.getGreenOdd())>0.01f)
            return Context.fallback("unequal_green_gains");
        String key=System.identityHashCode(chars)+"|"+tone+"|"+transform+"|"+gains+"|"+Arrays.toString(neutral)+"|"+boost;
        if (key.equals(cachedKey) && cachedContext!=null) return cachedContext;
        float[][] curves=new float[3][];
        for(int c=0;c<3;c++) {
            curves[c]=new float[tone.getPointCount(c)*2]; tone.copyColorCurve(c,curves[c],0);
            if(!MonoPreviewMath2A.validCurve(curves[c])) return Context.fallback("noninvertible_reported_curve");
        }
        Rational[] elements=new Rational[9]; transform.copyElements(elements,0);
        double[] ccm=new double[9];
        for(int i=0;i<9;i++) ccm[i]=elements[i].doubleValue();
        double[] wb={gains.getRed(),(gains.getGreenEven()+gains.getGreenOdd())*0.5,gains.getBlue()};
        float[] undo=MonoPreviewMath2A.undoColor(ccm,wb,boost);
        // Export only the native DNG Y row. No M9 target colour, HSM, or Cobalt profile.
        float[] y=M9R35Renderer.exportMonoPreviewY2A(chars,result);
        for(float v:y) if(!Float.isFinite(v)) return Context.fallback("invalid_source1d_y");
        Context out=new Context(undo,y,MonoPreviewMath2A.inverseTexture(curves),curves,ccm,wb,boost);
        cachedKey=key; cachedContext=out; return out;
    }

    public static synchronized Binding bind(long textureTimestampNs) {
        Frame f=RESULTS.get(textureTimestampNs);
        boolean exact=f!=null;
        if(f==null && latest!=null && SystemClock.elapsedRealtimeNanos()-latest.receivedNs<=MAX_CONTEXT_AGE_NS) f=latest;
        if(f==null) f=new Frame(activeCamera,"",null,null,Context.fallback("no_recent_preview_metadata"),-1,-1,0);
        return new Binding(f,textureTimestampNs,exact,++sequence);
    }
    public static void publish(Binding binding,float scale,int peak,boolean mirror,boolean targetEnabled,
            long elapsedNs,byte[] probe,int probeWidth,int probeHeight,long probeElapsedNs,String probeError) {
        Draw d=new Draw(binding,scale,peak,mirror,targetEnabled,elapsedNs,probe,probeWidth,probeHeight,probeElapsedNs,probeError);
        lastDraw=d;
        if(probe!=null) lastProbe=d;
    }
    public static synchronized JSONObject snapshot(long shutterElapsedNs) {
        JSONObject out=new JSONObject();
        try {
            out.put("revision",REVISION).put("requestConfiguration",configuration);
            out.put("availableToneMapModes",new JSONArray(availableModes));
            out.put("sourceReconstructionExact",false).put("displayToneParityProven",false);
            out.put("capturePolicyArithmeticChanged",false).put("previewYuvStatisticsResponseMayChange",true);
            out.put("limitations","ISP_demosaic_shading_and_irreversible_gamut_clipping_remain;_controlled_metadata_is_not_pixel_proof");
            Draw d=lastDraw;
            if(d==null || !d.binding.frame.camera.equals(activeCamera) || d.elapsedNs>shutterElapsedNs ||
                    shutterElapsedNs-d.elapsedNs>500000000L) {
                out.put("status","unavailable_recent_pre_shutter_draw"); return out;
            }
            out.put("status","draw_recorded").put("draw",d.json(false));
            out.put("drawAgeMsAtShutter",(shutterElapsedNs-d.elapsedNs)/1e6);
            Draw p=lastProbe;
            if(p!=null && p.binding.frame.camera.equals(activeCamera) && p.elapsedNs<=shutterElapsedNs &&
                    shutterElapsedNs-p.elapsedNs<=2000000000L) {
                out.put("pairedProbe",p.json(true));
                out.put("probeAgeMsAtShutter",(shutterElapsedNs-p.elapsedNs)/1e6);
                out.put("probeIsShutterDraw",p.binding.sequence==d.binding.sequence);
            } else out.put("pairedProbeStatus","unavailable_recent_pre_shutter_probe");
        } catch(Exception e) { try {out.put("error",e.toString());} catch(Exception ignored) {} }
        return out;
    }

    public static final class Context {
        public final boolean ready;
        public final String reason;
        private final float[] undo,y;
        private final byte[] inverse;
        private final float[][] curves;
        private final double[] ccm,wb;
        private final int boost;
        private Context(String reason) {
            ready=false; this.reason=reason; undo=new float[]{1,0,0,0,1,0,0,0,1}; y=new float[]{0.2126f,0.7152f,0.0722f};
            inverse=new byte[0]; curves=new float[0][]; ccm=new double[0]; wb=new double[0]; boost=0;
        }
        private Context(float[] undo,float[] y,byte[] inverse,float[][] curves,double[] ccm,double[] wb,int boost) {
            ready=true; reason="controlled_input_reported_not_device_pixel_validated";
            this.undo=undo.clone(); this.y=y.clone(); this.inverse=inverse.clone();
            this.curves=new float[curves.length][];
            for(int i=0;i<curves.length;i++) this.curves[i]=curves[i].clone();
            this.ccm=ccm.clone(); this.wb=wb.clone(); this.boost=boost;
        }
        static Context fallback(String reason) { return new Context(reason); }
        public float[] undo(){return undo.clone();}
        public float[] y(){return y.clone();}
        public byte[] inverse(){return inverse.clone();}
        JSONObject json() throws Exception {
            JSONObject o=new JSONObject();
            o.put("ready",ready).put("reason",reason).put("fittedResidualApplied",false);
            o.put("source",ready?"SOURCE1D_NATIVE_DNG_XYZ_Y":"exposure_only_monochrome_OES_fallback");
            o.put("firmwareCurveEligible",ready).put("curve02Sha256",CURVE_SHA);
            o.put("inverseReportedToneApplied",ready).put("postRawBoostRemoved",boost);
            o.put("inputToSensorColumnMajor",new JSONArray(undo)).put("source1dY",new JSONArray(y));
            o.put("reportedColorMatrixRowMajor",new JSONArray(ccm)).put("reportedWbGains",new JSONArray(wb));
            JSONArray a=new JSONArray(); for(float[] c:curves) a.put(new JSONArray(c));
            o.put("reportedToneCurves",a).put("secondLensShadingMapApplied",false);
            o.put("CobaltApplied",false).put("HDR",false).put("CPU_RAW_preview",false);
            return o;
        }
    }
    private static final class Frame {
        final String camera,physicalId; final CaptureResult result; final CaptureRequest request;
        final Context context; final long transportTs,sensorTs,receivedNs;
        Frame(String camera,String physicalId,CaptureResult r,CaptureRequest q,Context context,long t,long s,long n) {
            this.camera=camera;this.physicalId=physicalId;result=r;request=q;this.context=context;transportTs=t;sensorTs=s;receivedNs=n;
        }
    }
    public static final class Binding {
        private final Frame frame;
        public final Context context; public final long textureTimestampNs,sequence; public final boolean exact;
        Binding(Frame f,long t,boolean e,long seq){frame=f;context=f.context;textureTimestampNs=t;exact=e;sequence=seq;}
    }
    private static final class Draw {
        final Binding binding; final float scale; final int peak; final boolean mirror,targetEnabled;
        final long elapsedNs,probeElapsedNs; final byte[] probe; final int w,h; final String probeError;
        Draw(Binding b,float s,int p,boolean m,boolean enabled,long n,byte[] bytes,int w,int h,long cost,String error) {
            binding=b;scale=s;peak=p;mirror=m;targetEnabled=enabled;elapsedNs=n;probe=bytes==null?null:bytes.clone();this.w=w;this.h=h;
            probeElapsedNs=cost;probeError=error;
        }
        JSONObject json(boolean pixels) throws Exception {
            Frame f=binding.frame; JSONObject o=new JSONObject();
            o.put("sequence",binding.sequence).put("cameraKey",f.camera).put("physicalCameraId",f.physicalId);
            o.put("textureTimestampNs",binding.textureTimestampNs).put("resultSensorTimestampNs",f.sensorTs);
            o.put("transportSensorTimestampNs",f.transportTs).put("exactTextureResultTimestampMatch",binding.exact);
            o.put("textureMatchesTransportTimestamp",binding.textureTimestampNs>0 && binding.textureTimestampNs==f.transportTs);
            o.put("textureMatchesPhysicalTimestamp",binding.textureTimestampNs>0 && binding.textureTimestampNs==f.sensorTs);
            o.put("contextBinding",binding.exact?"exact_timestamp":"recent_metadata_not_exact_texture_frame");
            o.put("metadataReceivedElapsedNs",f.receivedNs).put("drawElapsedNs",elapsedNs);
            o.put("targetShaderEnabled",targetEnabled).put("framebufferPresentedToDisplayProven",false);
            o.put("uniformExposureScale",scale).put("focusPeaking",peak).put("mirror",mirror).put("source2A",f.context.json());
            if(f.result!=null) {
                JSONObject r=new JSONObject();
                r.put("iso",f.result.get(CaptureResult.SENSOR_SENSITIVITY));
                r.put("exposureTimeNs",f.result.get(CaptureResult.SENSOR_EXPOSURE_TIME));
                r.put("postRawSensitivityBoost",f.result.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST));
                r.put("toneMapMode",f.result.get(CaptureResult.TONEMAP_MODE));
                r.put("shadingMode",f.result.get(CaptureResult.SHADING_MODE));
                r.put("colorCorrectionMode",f.result.get(CaptureResult.COLOR_CORRECTION_MODE));
                r.put("aeMode",f.result.get(CaptureResult.CONTROL_AE_MODE));
                r.put("awbMode",f.result.get(CaptureResult.CONTROL_AWB_MODE)); o.put("previewResult",r);
            }
            o.put("probeError",probeError==null?JSONObject.NULL:probeError);
            if(pixels && probe!=null) {
                o.put("kind","same_OES_texture_same_shader_downsample_probe_not_display_framebuffer");
                o.put("width",w).put("height",h).put("rowOrder","GL_bottom_to_top");
                o.put("channels","R,G,B=pre_transform_OES_code;A=post_transform_monochrome_code");
                o.put("focusPeakingIncluded",false).put("readbackElapsedMs",probeElapsedNs/1e6);
                o.put("rgba8Base64",Base64.encodeToString(probe,Base64.NO_WRAP));
            }
            return o;
        }
    }
}
