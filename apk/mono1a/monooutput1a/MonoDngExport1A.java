package com.particlesdevs.photoncamera.m9.export;

import android.graphics.Bitmap;
import android.hardware.camera2.CaptureResult;
import android.os.Build;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.m9.M9DiagnosticBurstSpool;
import com.particlesdevs.photoncamera.util.SimpleStorageHelper;
import com.particlesdevs.photoncamera.util.Log;
import org.json.JSONArray;
import org.json.JSONObject;
import org.opencv.core.Mat;
import org.opencv.core.CvType;
import java.io.BufferedOutputStream;
import java.io.InputStream;
import java.io.OutputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.ThreadPoolExecutor;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.RejectedExecutionException;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/** Separate derived export. Owns only copied luminance, never camera buffers or the primary Bitmap. */
public final class MonoDngExport1A {
    public static final String REVISION="MONOOUTPUT1A_LINEAR_DNG";
    // Developer build switch only. Normal shooting must not allocate or encode comparison images.
    private static final boolean COMPARISON_IMAGES=false;
    public static boolean comparisons(){return COMPARISON_IMAGES;}
    private static final ThreadPoolExecutor IO=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,
            new ArrayBlockingQueue<>(1),r->{Thread t=new Thread(r,"MonoDngExport1A");t.setDaemon(true);return t;},
            new ThreadPoolExecutor.AbortPolicy());
    private MonoDngExport1A(){}
    public static final class Pending {
        final MonoLinearPlane1A plane;
        final JSONObject diagnostic;
        byte[] thumbnail;
        int thumbWidth,thumbHeight;
        Pending(MonoLinearPlane1A p,JSONObject d){plane=p;diagnostic=d;}
    }
    public static Pending capture(Mat cameraRgb,int width,int height,int rotation,
            float[] weights,double representationScale) throws Exception {
        long start=System.nanoTime();
        if(cameraRgb==null||cameraRgb.type()!=CvType.CV_16UC3||cameraRgb.cols()!=width||cameraRgb.rows()!=height)
            throw new IllegalArgumentException("pre_restore_camera_RGB_shape");
        MonoLinearPlane1A p=MonoLinearPlane1A.create(width,height,rotation,weights,representationScale,
                (row,data)->{int bytes=cameraRgb.get(row,0,data);return bytes==data.length*2?data.length:-1;});
        JSONObject d=new JSONObject();
        d.put("revision",REVISION).put("status","linear_plane_copied").put("derivedFromPhoneRaw",true);
        d.put("sourceStage","post_MHC_before_uint16_representation_restore_clip_and_before_JPEG_curve");
        d.put("source1dWeights",new JSONArray(p.weights)).put("sourceUnitsPerDngWhite",p.sourceUnitsPerWhite);
        d.put("baselineExposureEv",Math.log(p.sourceUnitsPerWhite)/Math.log(2));
        d.put("baselineExposureMeaning","reversible_storage_scale_hint_not_capture_exposure_change");
        d.put("representationScale",p.representationScale).put("quantizationStepSourceUnits",p.quantizationStep);
        d.put("aboveJpegNominalWhiteCount",p.aboveJpegWhiteCount).put("negativeLuminanceClampedCount",p.negativeCount);
        d.put("preexistingMhcChannelSaturationCount",p.sensorChannelClipCount).put("maximumSourceLuminance",p.maxSource);
        d.put("headroomPolicy","metadata_derived_bound_not_scene_max_normalization");
        d.put("width",p.width).put("height",p.height).put("orientation",1).put("bitsPerSample",16).put("samplesPerPixel",1);
        d.put("compression","uncompressed_lossless_storage").put("CFA",false);
        d.put("curveBakedIntoPixels",false).put("outputSharpeningBakedIntoPixels",false);
        d.put("cobaltApplied",false).put("hdrApplied",false).put("originalRawRetained",true);
        d.put("limitations","Bayer_interpolation_and_source_luminance_mix_committed;_earlier_clipping_not_recovered");
        d.put("copyElapsedMs",(System.nanoTime()-start)/1e6);
        return new Pending(p,d);
    }
    public static void thumbnail(Pending pending,Bitmap primary) {
        if(pending==null||primary==null)return;
        Bitmap small=null;
        try {
            double s=Math.min(1.0,256.0/Math.max(primary.getWidth(),primary.getHeight()));
            int w=Math.max(1,(int)Math.round(primary.getWidth()*s)),h=Math.max(1,(int)Math.round(primary.getHeight()*s));
            small=Bitmap.createScaledBitmap(primary,w,h,true);
            int[] pixels=new int[w*h];small.getPixels(pixels,0,w,0,0,w,h);byte[] rgb=new byte[w*h*3];
            for(int i=0;i<pixels.length;i++){rgb[3*i]=(byte)(pixels[i]>>>16);rgb[3*i+1]=(byte)(pixels[i]>>>8);rgb[3*i+2]=(byte)pixels[i];}
            pending.thumbnail=rgb;pending.thumbWidth=w;pending.thumbHeight=h;
        }catch(Throwable e){note(pending.diagnostic,"thumbnailError",e.toString());}
        finally {if(small!=null&&small!=primary&&!small.isRecycled())small.recycle();}
    }
    public static JSONObject submit(Pending pending,Path originalDng,CaptureResult result,String cameraId) {
        JSONObject reply=new JSONObject();
        if(pending==null){note(reply,"status","no_linear_plane_original_RAW_retained");return reply;}
        Path output=originalDng.resolveSibling(stem(originalDng)+"_MONO_LINEAR1A.dng");
        try {
            JSONObject immutable=new JSONObject(pending.diagnostic.toString());
            immutable.put("outputPath",output.toString()).put("originalDngPath",originalDng.toString());
            MonoDngWriter1A.Metadata m=metadata(originalDng,result,cameraId,immutable.toString());
            IO.execute(()->persist(pending,output,m,immutable));
            reply=new JSONObject(immutable.toString()).put("status","queued");
        }catch(RejectedExecutionException e){note(reply,"status","export_queue_full_original_RAW_retained");
            stage(output,reply);
        }catch(Throwable e){note(reply,"status","export_submit_failed_original_RAW_retained");note(reply,"error",e.toString());stage(output,reply);}
        return reply;
    }
    private static void persist(Pending pending,Path output,MonoDngWriter1A.Metadata meta,JSONObject d){
        Path staged=null;long start=System.nanoTime();
        try {
            android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
            Path dir=PhotonCamera.getAppContext().getFilesDir().toPath().resolve("mono_linear_dng_pending");
            Files.createDirectories(dir);
            // Failed exports are retained, never silently deleted to make room for new shots.
            try(java.util.stream.Stream<Path> files=Files.list(dir)){
                if(files.limit(8).count()>=8)throw new java.io.IOException("private_pending_limit_original_RAW_retained");
            }
            staged=Files.createTempFile(dir,"mono-",".dng");
            byte[] thumb=pending.thumbnail;int tw=pending.thumbWidth,th=pending.thumbHeight;
            if(thumb==null){thumb=new byte[]{0,0,0};tw=1;th=1;d.put("thumbnailStatus","unavailable_black_placeholder");}
            else d.put("thumbnailStatus","primary_JPEG_appearance_preview_only");
            long size;
            try(OutputStream stream=new BufferedOutputStream(Files.newOutputStream(staged),65536)){
                size=MonoDngWriter1A.write(stream,pending.plane,meta,tw,th,thumb);
            }
            if(Files.size(staged)!=size)throw new java.io.IOException("staged_length_mismatch");
            d.put("stagedBytes",size).put("privateStageComplete",true);
            copyPublic(staged,output,size);
            d.put("status","exported").put("publicWriteCompleted",true);
            Files.delete(staged);staged=null;
        }catch(Throwable e){note(d,"status","failed_original_RAW_retained");note(d,"error",e.toString());
            if(staged!=null)note(d,"retainedPrivateStage",staged.toString());Log.e("MonoDng1A","derived export failed",e);
        }finally {note(d,"workerElapsedMs",(System.nanoTime()-start)/1e6);stage(output,d);}
    }
    private static void copyPublic(Path staged,Path output,long expected) throws Exception {
        Throwable first=null;
        try {OutputStream stream=SimpleStorageHelper.openOutputStreamByAbsPath(output.toString());
            if(stream!=null){try(OutputStream out=stream){copy(staged,out,expected);}return;}
        }catch(Throwable e){first=e;}
        try {if(output.getParent()!=null)Files.createDirectories(output.getParent());
            try(OutputStream out=Files.newOutputStream(output)){copy(staged,out,expected);}
        }catch(Throwable e){if(first!=null)e.addSuppressed(first);throw e;}
    }
    private static void copy(Path p,OutputStream out,long expected) throws Exception {
        long copied=0;byte[] block=new byte[65536];
        try(InputStream in=Files.newInputStream(p)){int n;while((n=in.read(block))!=-1){out.write(block,0,n);copied+=n;}}
        if(copied!=expected)throw new java.io.IOException("public_length_mismatch");out.flush();
    }
    private static String stem(Path p){String s=p.getFileName().toString();int dot=s.lastIndexOf('.');return dot>0?s.substring(0,dot):s;}
    private static void stage(Path dng,JSONObject d){
        try {Path json=dng.resolveSibling(stem(dng)+"_EXPORT.json");
            M9DiagnosticBurstSpool.stage(json,d.toString(2).getBytes(StandardCharsets.UTF_8),"monochrome_dng_export");
        }catch(Throwable e){Log.e("MonoDng1A","export diagnostic failed",e);}
    }
    private static MonoDngWriter1A.Metadata metadata(Path original,CaptureResult result,String cameraId,String description){
        MonoDngWriter1A.Metadata m=new MonoDngWriter1A.Metadata();m.make=Build.MANUFACTURER;m.model=Build.MODEL;
        m.cameraId=cameraId;m.originalName=original.getFileName().toString();m.description=description;
        Matcher match=Pattern.compile("IMG_(\\d{4})(\\d{2})(\\d{2})_(\\d{2})(\\d{2})(\\d{2})_(\\d+)").matcher(m.originalName);
        if(match.find()){m.dateTime=match.group(1)+":"+match.group(2)+":"+match.group(3)+" "+match.group(4)+":"+match.group(5)+":"+match.group(6);
            String epoch=match.group(7);if(epoch.length()>=3)m.subsecond=epoch.substring(epoch.length()-3);}
        if(result!=null){Integer iso=result.get(CaptureResult.SENSOR_SENSITIVITY);Long ns=result.get(CaptureResult.SENSOR_EXPOSURE_TIME);
            Float a=result.get(CaptureResult.LENS_APERTURE),f=result.get(CaptureResult.LENS_FOCAL_LENGTH);
            m.iso=iso==null?0:iso;m.exposureNs=ns==null?0:ns;m.aperture=a==null?0:a;m.focalLength=f==null?0:f;}
        return m;
    }
    private static void note(JSONObject o,String key,Object v){try{o.put(key,v);}catch(Exception ignored){}}
}
