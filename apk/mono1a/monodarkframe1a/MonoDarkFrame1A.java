package com.particlesdevs.photoncamera.m9.render;

import android.graphics.Point;
import android.hardware.camera2.CameraCharacteristics;
import android.hardware.camera2.CameraMetadata;
import android.hardware.camera2.CaptureRequest;
import android.hardware.camera2.CaptureResult;
import android.os.Build;

import com.particlesdevs.photoncamera.util.Log;

import org.json.JSONObject;

import java.util.Arrays;
import java.util.HashSet;
import java.util.Set;

/**
 * MONODARKFRAME1A.
 *
 * Purpose-equivalent first-generation M Monochrom long-exposure correction.
 * The Leica 1.022 firmware's BlackRef decision is recovered exactly, but Android
 * has no standard application-controlled mechanical shutter or Leica sensor
 * temperature. Therefore normal phone capture uses the Leica 20-39 C threshold
 * group and only standard Camera2 metadata:
 *
 * - request the hot-pixel map for Leica-eligible exposures;
 * - prefer per-frame dynamic black level for the derived Monochrom path;
 * - when the HAL explicitly reports HOT_PIXEL_MODE_OFF, repair reported hot
 *   pixels on the private normalized Bayer copy before demosaic;
 * - never mutate the original RAW ByteBuffer;
 * - never take a second illuminated exposure or add an artificial delay.
 */
public final class MonoDarkFrame1A {
    public static final String REVISION = "MONODARKFRAME1A";
    private static final String TAG = "MonoDarkFrame1A";

    private MonoDarkFrame1A() {}

    /** Leica 1.022 normal-temperature group (20-39 C), expressed in ns. */
    public static long thresholdNsForPhysicalIso(int physicalIso) {
        final int iso = Math.max(320, Math.min(10000, physicalIso));
        if (iso <= 1000) return 250_000_000L;
        if (iso <= 4000) return 125_000_000L;
        return 66_000_000L;
    }

    /** Firmware comparison is strict: exposure must exceed, not equal, threshold. */
    public static boolean needsCorrection(int physicalIso, long exposureTimeNs) {
        return exposureTimeNs > thresholdNsForPhysicalIso(physicalIso);
    }

    /**
     * Metadata-only request change. It does not select HOT_PIXEL_MODE and thus
     * does not ask the HAL to alter the RAW pixels.
     */
    public static void configureCaptureRequest(CaptureRequest.Builder builder,
                                               CameraCharacteristics characteristics) {
        if (builder == null) return;
        Integer iso = builder.get(CaptureRequest.SENSOR_SENSITIVITY);
        Long exposure = builder.get(CaptureRequest.SENSOR_EXPOSURE_TIME);
        if (iso == null || exposure == null || iso <= 0 || exposure <= 0L) return;

        boolean available = false;
        if (characteristics != null) {
            try {
                boolean[] modes = characteristics.get(
                        CameraCharacteristics.STATISTICS_INFO_AVAILABLE_HOT_PIXEL_MAP_MODES);
                if (modes != null) {
                    for (boolean mode : modes) {
                        if (mode) { available = true; break; }
                    }
                }
            } catch (Throwable t) {
                Log.w(TAG, REVISION + " hot-pixel-map capability query failed", t);
            }
        }
        if (available) {
            try {
                builder.set(CaptureRequest.STATISTICS_HOT_PIXEL_MAP_MODE,
                        needsCorrection(iso, exposure));
            } catch (Throwable t) {
                Log.w(TAG, REVISION + " hot-pixel-map request failed", t);
            }
        }
    }

    public static final class BlackResolution {
        public final float[] levels;
        public final boolean candidate;
        public final boolean dynamicBlackUsed;
        public final int physicalIso;
        public final long exposureTimeNs;
        public final long thresholdNs;
        public final String reason;

        BlackResolution(float[] levels, boolean candidate, boolean dynamicBlackUsed,
                        int physicalIso, long exposureTimeNs, long thresholdNs, String reason) {
            this.levels = levels;
            this.candidate = candidate;
            this.dynamicBlackUsed = dynamicBlackUsed;
            this.physicalIso = physicalIso;
            this.exposureTimeNs = exposureTimeNs;
            this.thresholdNs = thresholdNs;
            this.reason = reason;
        }

        public JSONObject toJson() {
            JSONObject j = new JSONObject();
            try {
                j.put("revision", REVISION);
                j.put("policy", "Leica_1.022_nominal_temperature_group_20_39C");
                j.put("temperatureSource", "unavailable_on_standard_Camera2_nominal_group_used");
                j.put("physicalIso", physicalIso);
                j.put("exposureTimeNs", exposureTimeNs);
                j.put("thresholdNs", thresholdNs);
                j.put("strictGreaterThanThreshold", true);
                j.put("candidate", candidate);
                j.put("dynamicBlackUsed", dynamicBlackUsed);
                j.put("reason", reason);
                if (levels != null && levels.length >= 4) {
                    j.put("level0", levels[0]); j.put("level1", levels[1]);
                    j.put("level2", levels[2]); j.put("level3", levels[3]);
                }
            } catch (Throwable ignored) {}
            return j;
        }
    }

    public static BlackResolution resolveBlackLevels(float[] fallback,
                                                     CaptureResult result,
                                                     int physicalIso,
                                                     long exposureTimeNs) {
        float[] base = fallback != null ? fallback.clone() : new float[]{64f,64f,64f,64f};
        long threshold = thresholdNsForPhysicalIso(physicalIso);
        boolean candidate = needsCorrection(physicalIso, exposureTimeNs);
        if (!candidate || result == null || Build.VERSION.SDK_INT < Build.VERSION_CODES.N) {
            return new BlackResolution(base, candidate, false, physicalIso, exposureTimeNs,
                    threshold, candidate ? "dynamic_black_unavailable" : "below_Leica_threshold");
        }
        try {
            float[] dynamic = result.get(CaptureResult.SENSOR_DYNAMIC_BLACK_LEVEL);
            if (dynamic != null && dynamic.length >= 4) {
                float[] use = new float[4];
                for (int i = 0; i < 4; i++) {
                    float v = dynamic[i];
                    if (!Float.isFinite(v) || v < 0f) {
                        return new BlackResolution(base, true, false, physicalIso, exposureTimeNs,
                                threshold, "dynamic_black_invalid_fallback_static");
                    }
                    use[i] = v;
                }
                return new BlackResolution(use, true, true, physicalIso, exposureTimeNs,
                        threshold, "per_frame_SENSOR_DYNAMIC_BLACK_LEVEL");
            }
        } catch (Throwable t) {
            Log.w(TAG, REVISION + " dynamic black read failed", t);
        }
        return new BlackResolution(base, true, false, physicalIso, exposureTimeNs,
                threshold, "dynamic_black_missing_fallback_static");
    }

    public static final class CorrectionStats {
        public final boolean candidate;
        public final int physicalIso;
        public final long exposureTimeNs;
        public final long thresholdNs;
        public final Integer hotPixelMode;
        public final Boolean hotPixelMapMode;
        public final int reported;
        public final int inFrame;
        public final int corrected;
        public final String reason;

        CorrectionStats(boolean candidate, int physicalIso, long exposureTimeNs, long thresholdNs,
                        Integer hotPixelMode, Boolean hotPixelMapMode,
                        int reported, int inFrame, int corrected, String reason) {
            this.candidate=candidate; this.physicalIso=physicalIso;
            this.exposureTimeNs=exposureTimeNs; this.thresholdNs=thresholdNs;
            this.hotPixelMode=hotPixelMode; this.hotPixelMapMode=hotPixelMapMode;
            this.reported=reported; this.inFrame=inFrame; this.corrected=corrected;
            this.reason=reason;
        }

        public JSONObject toJson() {
            JSONObject j=new JSONObject();
            try {
                j.put("revision",REVISION);
                j.put("policy","Leica_1.022_nominal_temperature_group_20_39C");
                j.put("physicalIso",physicalIso);
                j.put("exposureTimeNs",exposureTimeNs);
                j.put("thresholdNs",thresholdNs);
                j.put("candidate",candidate);
                if(hotPixelMode!=null)j.put("captureResultHotPixelMode",hotPixelMode);
                if(hotPixelMapMode!=null)j.put("captureResultHotPixelMapMode",hotPixelMapMode);
                j.put("reportedHotPixels",reported);
                j.put("inFrameHotPixels",inFrame);
                j.put("correctedHotPixels",corrected);
                j.put("originalRawMutated",false);
                j.put("secondExposureTaken",false);
                j.put("artificialDelay",false);
                j.put("reason",reason);
            } catch(Throwable ignored){}
            return j;
        }
    }

    private static int resultIso(CaptureResult result) {
        if(result==null)return 320;
        Integer v=result.get(CaptureResult.SENSOR_SENSITIVITY);
        return v!=null&&v>0?v:320;
    }

    private static long resultExposure(CaptureResult result) {
        if(result==null)return 0L;
        Long v=result.get(CaptureResult.SENSOR_EXPOSURE_TIME);
        return v!=null&&v>0L?v:0L;
    }

    /**
     * Repairs only the private normalized Bayer copy, using same-CFA (two-pixel)
     * neighbours. The original camera RAW buffer is never written.
     */
    public static CorrectionStats correctNormalizedHotPixels(short[] norm16,
                                                              int width, int height,
                                                              int sourceOriginX, int sourceOriginY,
                                                              int whiteLevel,
                                                              long[] rawCountsFlat,
                                                              CaptureResult result) {
        final int iso=resultIso(result);
        final long exposure=resultExposure(result);
        final long threshold=thresholdNsForPhysicalIso(iso);
        final boolean candidate=needsCorrection(iso,exposure);
        if(!candidate || result==null || norm16==null) {
            return new CorrectionStats(candidate,iso,exposure,threshold,null,null,0,0,0,
                    candidate?"missing_result_or_normalized_plane":"below_Leica_threshold");
        }

        Integer mode=null; Boolean mapMode=null; Point[] map=null;
        try { mode=result.get(CaptureResult.HOT_PIXEL_MODE); } catch(Throwable ignored){}
        try { mapMode=result.get(CaptureResult.STATISTICS_HOT_PIXEL_MAP_MODE); } catch(Throwable ignored){}
        try { map=result.get(CaptureResult.STATISTICS_HOT_PIXEL_MAP); } catch(Throwable ignored){}

        final int reported=map!=null?map.length:0;
        if(mode==null) {
            return new CorrectionStats(true,iso,exposure,threshold,null,mapMode,reported,0,0,
                    "HAL_hot_pixel_mode_unknown_fail_closed_no_double_correction");
        }
        if(mode!=CameraMetadata.HOT_PIXEL_MODE_OFF) {
            return new CorrectionStats(true,iso,exposure,threshold,mode,mapMode,reported,0,0,
                    "HAL_hot_pixel_correction_active_trust_HAL_no_double_correction");
        }
        if(map==null || map.length==0) {
            return new CorrectionStats(true,iso,exposure,threshold,mode,mapMode,reported,0,0,
                    "no_reported_hot_pixel_map");
        }

        final Set<Long> hot=new HashSet<>();
        int inFrame=0;
        for(Point p:map) {
            if(p==null)continue;
            int x=p.x-sourceOriginX, y=p.y-sourceOriginY;
            if(x>=0&&x<width&&y>=0&&y<height) {
                hot.add((((long)y)<<32)|(x&0xffffffffL)); inFrame++;
            }
        }
        if(hot.isEmpty()) {
            return new CorrectionStats(true,iso,exposure,threshold,mode,mapMode,reported,0,0,
                    "reported_hot_pixels_outside_RAW_crop");
        }

        final int[] dx={-2,2,0,0,-2,2,-2,2};
        final int[] dy={0,0,-2,2,-2,-2,2,2};
        final int max=Math.max(2,whiteLevel);
        int[] indices=new int[hot.size()];
        int[] replacements=new int[hot.size()];
        int pending=0;

        for(long key:hot) {
            int y=(int)(key>>32), x=(int)key;
            int[] vals=new int[8]; int n=0;
            for(int k=0;k<8;k++) {
                int nx=x+dx[k], ny=y+dy[k];
                if(nx<0||nx>=width||ny<0||ny>=height)continue;
                long nk=(((long)ny)<<32)|(nx&0xffffffffL);
                if(hot.contains(nk))continue;
                vals[n++]=norm16[ny*width+nx]&0xffff;
            }
            if(n<3)continue;
            Arrays.sort(vals,0,n);
            int replacement=(n&1)!=0?vals[n/2]:(vals[n/2-1]+vals[n/2]+1)/2;
            indices[pending]=y*width+x;
            replacements[pending]=Math.max(0,Math.min(max-1,replacement));
            pending++;
        }

        for(int i=0;i<pending;i++) {
            int index=indices[i], y=index/width, x=index-y*width;
            int old=norm16[index]&0xffff, replacement=replacements[i];
            if(old==replacement)continue;
            norm16[index]=(short)replacement;
            if(rawCountsFlat!=null && rawCountsFlat.length>=4*max) {
                int sensorX=x+sourceOriginX, sensorY=y+sourceOriginY;
                int plane=((sensorY&1)<<1)|(sensorX&1);
                int oldBin=Math.max(0,Math.min(max-1,old));
                int newBin=Math.max(0,Math.min(max-1,replacement));
                int oldIndex=plane*max+oldBin, newIndex=plane*max+newBin;
                if(rawCountsFlat[oldIndex]>0)rawCountsFlat[oldIndex]--;
                rawCountsFlat[newIndex]++;
            }
        }
        return new CorrectionStats(true,iso,exposure,threshold,mode,mapMode,reported,inFrame,pending,
                pending>0?"app_same_CFA_median_on_private_normalized_copy":"insufficient_same_CFA_neighbours");
    }
}
