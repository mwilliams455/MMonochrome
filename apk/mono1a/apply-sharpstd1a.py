#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv)!=2:
    raise SystemExit('usage: apply-sharpstd1a.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve()
R=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
N=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java'
C=root/'app/src/main/cpp/m9color_jni.cpp'
H=root/'app/src/main/cpp/mm_monochrom_standard_sharp_lut.inc'
for p in (R,N,C,H):
    if not p.exists(): raise SystemExit('missing '+str(p))

def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f'{label}: anchor count={n}, expected 1')
    return s.replace(a,b,1)

r=R.read_text()
if 'SHARPSTD1A' in r: raise SystemExit('SHARPSTD1A already applied')
if 'MONO1A_RAWSCALAR1B_PROMOTED1A' not in r: raise SystemExit('promoted RAWSCALAR1B prerequisite missing')

a='''        final Bitmap rawScalar1ABitmap;\n        final Bitmap rawScalar1BBitmap;\n        RenderCore(Bitmap bitmap, JSONObject diagnostics) {\n            this(bitmap, diagnostics, null, null, null, null);\n        }\n        RenderCore(Bitmap bitmap, JSONObject diagnostics,\n                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap) {\n            this(bitmap, diagnostics, source1cEqualRgbBitmap, source1cGreenBitmap, null, null);\n        }\n        RenderCore(Bitmap bitmap, JSONObject diagnostics,\n                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap,\n                   Bitmap rawScalar1ABitmap) {\n            this(bitmap, diagnostics, source1cEqualRgbBitmap, source1cGreenBitmap, rawScalar1ABitmap, null);\n        }\n        RenderCore(Bitmap bitmap, JSONObject diagnostics,\n                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap,\n                   Bitmap rawScalar1ABitmap, Bitmap rawScalar1BBitmap) {\n            this.bitmap = bitmap;\n            this.diagnostics = diagnostics;\n            this.source1cEqualRgbBitmap = source1cEqualRgbBitmap;\n            this.source1cGreenBitmap = source1cGreenBitmap;\n            this.rawScalar1ABitmap = rawScalar1ABitmap;\n            this.rawScalar1BBitmap = rawScalar1BBitmap;\n        }\n'''
b='''        final Bitmap rawScalar1ABitmap;\n        final Bitmap rawScalar1BBitmap;\n        final Bitmap rawScalar1BSharpStdBitmap;\n        RenderCore(Bitmap bitmap, JSONObject diagnostics) {\n            this(bitmap, diagnostics, null, null, null, null, null);\n        }\n        RenderCore(Bitmap bitmap, JSONObject diagnostics,\n                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap) {\n            this(bitmap, diagnostics, source1cEqualRgbBitmap, source1cGreenBitmap, null, null, null);\n        }\n        RenderCore(Bitmap bitmap, JSONObject diagnostics,\n                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap,\n                   Bitmap rawScalar1ABitmap) {\n            this(bitmap, diagnostics, source1cEqualRgbBitmap, source1cGreenBitmap, rawScalar1ABitmap, null, null);\n        }\n        RenderCore(Bitmap bitmap, JSONObject diagnostics,\n                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap,\n                   Bitmap rawScalar1ABitmap, Bitmap rawScalar1BBitmap) {\n            this(bitmap, diagnostics, source1cEqualRgbBitmap, source1cGreenBitmap, rawScalar1ABitmap, rawScalar1BBitmap, null);\n        }\n        RenderCore(Bitmap bitmap, JSONObject diagnostics,\n                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap,\n                   Bitmap rawScalar1ABitmap, Bitmap rawScalar1BBitmap,\n                   Bitmap rawScalar1BSharpStdBitmap) {\n            this.bitmap = bitmap;\n            this.diagnostics = diagnostics;\n            this.source1cEqualRgbBitmap = source1cEqualRgbBitmap;\n            this.source1cGreenBitmap = source1cGreenBitmap;\n            this.rawScalar1ABitmap = rawScalar1ABitmap;\n            this.rawScalar1BBitmap = rawScalar1BBitmap;\n            this.rawScalar1BSharpStdBitmap = rawScalar1BSharpStdBitmap;\n        }\n'''
r=one(r,a,b,'RenderCore sharp diagnostic slot')

a='''            Path rawScalar1BPath = null;\n            boolean source1cEqualRgbSaved = false;\n            boolean source1cGreenSaved = false;\n            boolean rawScalar1ASaved = false;\n            boolean rawScalar1BSaved = false;\n            String source1cEqualRgbError = null;\n            String source1cGreenError = null;\n            String rawScalar1AError = null;\n            String rawScalar1BError = null;\n'''
b='''            Path rawScalar1BPath = null;\n            Path rawScalar1BSharpStdPath = null;\n            boolean source1cEqualRgbSaved = false;\n            boolean source1cGreenSaved = false;\n            boolean rawScalar1ASaved = false;\n            boolean rawScalar1BSaved = false;\n            boolean rawScalar1BSharpStdSaved = false;\n            String source1cEqualRgbError = null;\n            String source1cGreenError = null;\n            String rawScalar1AError = null;\n            String rawScalar1BError = null;\n            String rawScalar1BSharpStdError = null;\n'''
r=one(r,a,b,'sharp save vars')

a='''            if (out.rawScalar1BBitmap != null) {\n                rawScalar1BPath = Paths.get(FileManager.sDCIM_CAMERA.getAbsolutePath(),\n                        stem + "_MONO_M9Y_CONTROL.jpg");\n                try (OutputStream auxOut = Files.newOutputStream(rawScalar1BPath)) {\n                    rawScalar1BSaved = out.rawScalar1BBitmap.compress(\n                            Bitmap.CompressFormat.JPEG, JPEG_QUALITY, auxOut);\n                    auxOut.flush();\n                } catch (Throwable auxError) {\n                    rawScalar1BError = auxError.toString();\n                } finally {\n                    if (!out.rawScalar1BBitmap.isRecycled()) out.rawScalar1BBitmap.recycle();\n                }\n            }\n\n            long elapsedMs = (System.nanoTime() - started) / 1_000_000L;\n'''
b='''            if (out.rawScalar1BBitmap != null) {\n                rawScalar1BPath = Paths.get(FileManager.sDCIM_CAMERA.getAbsolutePath(),\n                        stem + "_MONO_M9Y_CONTROL.jpg");\n                try (OutputStream auxOut = Files.newOutputStream(rawScalar1BPath)) {\n                    rawScalar1BSaved = out.rawScalar1BBitmap.compress(\n                            Bitmap.CompressFormat.JPEG, JPEG_QUALITY, auxOut);\n                    auxOut.flush();\n                } catch (Throwable auxError) {\n                    rawScalar1BError = auxError.toString();\n                } finally {\n                    if (!out.rawScalar1BBitmap.isRecycled()) out.rawScalar1BBitmap.recycle();\n                }\n            }\n            if (out.rawScalar1BSharpStdBitmap != null) {\n                rawScalar1BSharpStdPath = Paths.get(FileManager.sDCIM_CAMERA.getAbsolutePath(),\n                        stem + "_MONO_RAWSCALAR1B_SHARPSTD1A.jpg");\n                try (OutputStream auxOut = Files.newOutputStream(rawScalar1BSharpStdPath)) {\n                    rawScalar1BSharpStdSaved = out.rawScalar1BSharpStdBitmap.compress(\n                            Bitmap.CompressFormat.JPEG, JPEG_QUALITY, auxOut);\n                    auxOut.flush();\n                } catch (Throwable auxError) {\n                    rawScalar1BSharpStdError = auxError.toString();\n                } finally {\n                    if (!out.rawScalar1BSharpStdBitmap.isRecycled()) out.rawScalar1BSharpStdBitmap.recycle();\n                }\n            }\n\n            long elapsedMs = (System.nanoTime() - started) / 1_000_000L;\n'''
r=one(r,a,b,'sharp save block')

a='''            if (rawScalar1BPath != null) {\n                diag.put("m9YControlJpegPath", rawScalar1BPath.toString());\n                diag.put("m9YControlJpegSaved", rawScalar1BSaved);\n                if (rawScalar1BError != null) diag.put("m9YControlJpegError", rawScalar1BError);\n            }\n            diag.put("parityPngEnabled", SAVE_PARITY_PNG);\n'''
b='''            if (rawScalar1BPath != null) {\n                diag.put("m9YControlJpegPath", rawScalar1BPath.toString());\n                diag.put("m9YControlJpegSaved", rawScalar1BSaved);\n                if (rawScalar1BError != null) diag.put("m9YControlJpegError", rawScalar1BError);\n            }\n            if (rawScalar1BSharpStdPath != null) {\n                diag.put("sharpStd1AJpegPath", rawScalar1BSharpStdPath.toString());\n                diag.put("sharpStd1AJpegSaved", rawScalar1BSharpStdSaved);\n                if (rawScalar1BSharpStdError != null) diag.put("sharpStd1AJpegError", rawScalar1BSharpStdError);\n            }\n            diag.put("parityPngEnabled", SAVE_PARITY_PNG);\n'''
r=one(r,a,b,'sharp saved diagnostics')

a='''        Bitmap rawScalar1BBitmap = null;\n        long[] rawScalar1AStats = null;\n        long[] rawScalar1BStats = null;\n        float[] rawScalar1BFixedD65Neutral = null;\n'''
b='''        Bitmap rawScalar1BBitmap = null;\n        Bitmap rawScalar1BSharpStdBitmap = null;\n        long[] rawScalar1AStats = null;\n        long[] rawScalar1BStats = null;\n        long[] rawScalar1BSharpStdStats = null;\n        float[] rawScalar1BFixedD65Neutral = null;\n'''
r=one(r,a,b,'sharp render vars')

a='''            if (!rawScalar1BOk) {\n                if (!rawScalar1BBitmap.isRecycled()) rawScalar1BBitmap.recycle();\n                throw new IllegalStateException("MONO1A RAWSCALAR1B fixed-D65 native render failed");\n            }\n        }\n'''
b='''            if (!rawScalar1BOk) {\n                if (!rawScalar1BBitmap.isRecycled()) rawScalar1BBitmap.recycle();\n                throw new IllegalStateException("MONO1A RAWSCALAR1B fixed-D65 native render failed");\n            }\n\n            Integer sharpCaptureIsoObj = nativeCaptureResult != null\n                    ? nativeCaptureResult.get(CaptureResult.SENSOR_SENSITIVITY) : null;\n            final int sharpCaptureIso = sharpCaptureIsoObj != null && sharpCaptureIsoObj > 0\n                    ? sharpCaptureIsoObj : 320;\n            rawScalar1BSharpStdBitmap = Bitmap.createBitmap(rawScalarOutW, rawScalarOutH, Bitmap.Config.ARGB_8888);\n            rawScalar1BSharpStdStats = new long[12];\n            boolean rawScalar1BSharpStdOk = M9NativeColorCore.renderMonochrome1ARawScalarSharpStdDirectBitmap(\n                    norm16, width, height, rawScalar1BSharpStdBitmap, cameraRotation, NATIVE_COLOR_WORKERS,\n                    MONO1A_SYNTHETIC_PEDESTAL14,\n                    rawScalar1BFixedD65Neutral[0], rawScalar1BFixedD65Neutral[1], rawScalar1BFixedD65Neutral[2],\n                    nativeShading.representationScale, sharpCaptureIso, rawScalar1BSharpStdStats);\n            if (!rawScalar1BSharpStdOk) {\n                if (!rawScalar1BSharpStdBitmap.isRecycled()) rawScalar1BSharpStdBitmap.recycle();\n                throw new IllegalStateException("MONO1A RAWSCALAR1B SHARPSTD1A native render failed");\n            }\n        }\n'''
r=one(r,a,b,'sharp native call')

a='''                d.put("rawScalar1B", rawScalar1B);\n                d.put("rawScalar1BPolicy", "promoted_primary_fixed_Xiaomi_spectral_proxy_no_per_shot_AWB_no_tone_or_exposure_change");\n                d.put("source1Revision", "MONO1A_RAWSCALAR1B_PROMOTED1A");\n'''
b='''                d.put("rawScalar1B", rawScalar1B);\n                d.put("rawScalar1BPolicy", "promoted_primary_fixed_Xiaomi_spectral_proxy_no_per_shot_AWB_no_tone_or_exposure_change");\n                JSONObject sharpStd1A = new JSONObject();\n                sharpStd1A.put("schema", "mmonochrom.rawscalar1b.sharpstd1a.v1");\n                sharpStd1A.put("revision", "SHARPSTD1A");\n                sharpStd1A.put("photographicOutputSelected", false);\n                sharpStd1A.put("baselinePrimaryPreserved", true);\n                sharpStd1A.put("selector", 2);\n                sharpStd1A.put("selectorLabel", "Standard");\n                sharpStd1A.put("noiseMode", 0);\n                sharpStd1A.put("incomingBorder", 0);\n                sharpStd1A.put("sharpAddedBorder", 2);\n                sharpStd1A.put("effectiveBorder", 2);\n                sharpStd1A.put("isoBridgePolicy", "nearest_Leica_physical_ISO_slot_in_log2_EV_clamped_320_10000_not_firmware_claim");\n                sharpStd1A.put("sharpBankSha256", "282a6e7eb0603203d5ddb36f32862e0340a9cc2d24c35b4c0af2b1bd79c06d10");\n                sharpStd1A.put("hostOracle", "dual_integer_implementations_all_16_ISO_slots_passed");\n                if (rawScalar1BSharpStdStats != null && rawScalar1BSharpStdStats.length >= 12) {\n                    sharpStd1A.put("nativePixelCount", rawScalar1BSharpStdStats[0]);\n                    sharpStd1A.put("changedScalarPixels", rawScalar1BSharpStdStats[1]);\n                    sharpStd1A.put("selectedLeicaIsoSlot", rawScalar1BSharpStdStats[2]);\n                    sharpStd1A.put("selectedLeicaIso", rawScalar1BSharpStdStats[3]);\n                    sharpStd1A.put("modifierCode", rawScalar1BSharpStdStats[4]);\n                    sharpStd1A.put("nativeRenderNs", rawScalar1BSharpStdStats[5]);\n                    sharpStd1A.put("effectiveBorderNative", rawScalar1BSharpStdStats[6]);\n                    sharpStd1A.put("captureIso", rawScalar1BSharpStdStats[7]);\n                    sharpStd1A.put("nearWhiteOutputCount", rawScalar1BSharpStdStats[8]);\n                    sharpStd1A.put("scalarLowClampCount", rawScalar1BSharpStdStats[9]);\n                    sharpStd1A.put("scalarHighClampCount", rawScalar1BSharpStdStats[10]);\n                    sharpStd1A.put("neutralAxisClipCount", rawScalar1BSharpStdStats[11]);\n                }\n                d.put("sharpStd1A", sharpStd1A);\n                d.put("rawScalar1BSharpStdPolicy", "diagnostic_AB_only_firmware_exact_after_explicit_Xiaomi_to_Leica_ISO_slot_bridge");\n                d.put("source1Revision", "MONO1A_RAWSCALAR1B_PROMOTED1A_SHARPSTD1A_AB");\n'''
r=one(r,a,b,'sharp diagnostics object')

a='''                return new RenderCore(rawScalar1BBitmap, d, equalRgbBitmap, greenOnlyBitmap, rawScalar1ABitmap, monoBitmap);\n'''
b='''                return new RenderCore(rawScalar1BBitmap, d, equalRgbBitmap, greenOnlyBitmap, rawScalar1ABitmap, monoBitmap, rawScalar1BSharpStdBitmap);\n'''
r=one(r,a,b,'sharp diagnostic return')
R.write_text(r)

n=N.read_text()
if 'renderMonochrome1ARawScalarSharpStdDirectBitmap' in n: raise SystemExit('sharp native declaration already present')
a='''    static native boolean renderMonochrome1ARawScalarDirectBitmap(short[] raw,\n                                                                  int width, int sourceHeight,\n                                                                  android.graphics.Bitmap bitmap,\n                                                                  int cameraRotation, int workers, int pedestal14,\n                                                                  float neutralR, float neutralG, float neutralB,\n                                                                  double representationScale, long[] stats);\n'''
b=a+'''\n\n    /** SHARPSTD1A: RAWSCALAR1B plus firmware-exact Monochrom Standard sharpness, diagnostic A/B only. */\n    static native boolean renderMonochrome1ARawScalarSharpStdDirectBitmap(short[] raw,\n                                                                          int width, int sourceHeight,\n                                                                          android.graphics.Bitmap bitmap,\n                                                                          int cameraRotation, int workers, int pedestal14,\n                                                                          float neutralR, float neutralG, float neutralB,\n                                                                          double representationScale, int captureIso,\n                                                                          long[] stats);\n'''
n=one(n,a,b,'sharp native declaration')
N.write_text(n)

c=C.read_text()
if 'renderMonochrome1ARawScalarSharpStdDirectBitmap' in c: raise SystemExit('sharp JNI already present')
fn=r'''

#include "mm_monochrom_standard_sharp_lut.inc"

static int mmMonoNearestIsoSlotEv(int captureIso) {
    if (captureIso <= MM_MONO_STD_SHARP_ISOS[0]) return 0;
    if (captureIso >= MM_MONO_STD_SHARP_ISOS[MM_MONO_STD_SHARP_ISO_COUNT-1]) return MM_MONO_STD_SHARP_ISO_COUNT-1;
    const double target=std::log2(static_cast<double>(captureIso));
    int best=0; double bestD=std::abs(target-std::log2(static_cast<double>(MM_MONO_STD_SHARP_ISOS[0])));
    for(int i=1;i<MM_MONO_STD_SHARP_ISO_COUNT;++i){
        const double d=std::abs(target-std::log2(static_cast<double>(MM_MONO_STD_SHARP_ISOS[i])));
        if(d<bestD){bestD=d;best=i;}
    }
    return best;
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1ARawScalarSharpStdDirectBitmap(
        JNIEnv* env, jclass, jshortArray rawArray, jint width, jint sourceHeight,
        jobject bitmap, jint cameraRotation, jint workers, jint pedestal14,
        jfloat neutralR, jfloat neutralG, jfloat neutralB, jdouble representationScale,
        jint captureIso, jlongArray statsArray) {
    if(!rawArray||!bitmap||width<=0||sourceHeight<=0||workers<=0||pedestal14<0||pedestal14>16383
            ||!std::isfinite(neutralR)||!std::isfinite(neutralG)||!std::isfinite(neutralB)
            ||neutralR<=0.0f||neutralG<=0.0f||neutralB<=0.0f
            ||!std::isfinite(representationScale)||representationScale<=0.0){
        throwIllegalArgument(env,"Invalid MONO1A SHARPSTD1A arguments");return JNI_FALSE;
    }
    const int64_t pixels64=static_cast<int64_t>(width)*static_cast<int64_t>(sourceHeight);
    if(pixels64<=0||pixels64>0x7fffffffLL||env->GetArrayLength(rawArray)<static_cast<jsize>(pixels64))return JNI_FALSE;
    int rotation=cameraRotation%360;if(rotation<0)rotation+=360;
    const uint32_t outW=static_cast<uint32_t>((rotation==90||rotation==270)?sourceHeight:width);
    const uint32_t outH=static_cast<uint32_t>((rotation==90||rotation==270)?width:sourceHeight);
    AndroidBitmapInfo info{};
    if(AndroidBitmap_getInfo(env,bitmap,&info)!=ANDROID_BITMAP_RESULT_SUCCESS||info.format!=ANDROID_BITMAP_FORMAT_RGBA_8888
            ||info.width!=outW||info.height!=outH||info.stride<outW*4u)return JNI_FALSE;
    jboolean isCopy=JNI_FALSE;
    jshort* raw=static_cast<jshort*>(env->GetPrimitiveArrayCritical(rawArray,&isCopy));
    if(!raw)return JNI_FALSE;
    const auto started=std::chrono::steady_clock::now();
    const double invR=static_cast<double>(neutralG)/static_cast<double>(neutralR);
    const double invB=static_cast<double>(neutralG)/static_cast<double>(neutralB);
    if(!std::isfinite(invR)||!std::isfinite(invB)||invR<=0.0||invB<=0.0){env->ReleasePrimitiveArrayCritical(rawArray,raw,JNI_ABORT);return JNI_FALSE;}
    const int wc=std::max(1,std::min(static_cast<int>(workers),static_cast<int>(sourceHeight)));
    std::vector<uint16_t> image(static_cast<size_t>(pixels64));
    std::vector<std::array<uint64_t,3>> ws(static_cast<size_t>(wc));
    std::vector<std::thread> threads;threads.reserve(static_cast<size_t>(wc));
    for(int worker=0;worker<wc;++worker){
        const int y0=(sourceHeight*worker)/wc,y1=(sourceHeight*(worker+1))/wc;
        threads.emplace_back([&,worker,y0,y1](){
            uint64_t low=0,high=0,neutralClip=0;
            for(int y=y0;y<y1;++y){const size_t row=static_cast<size_t>(y)*static_cast<size_t>(width);
                for(int x=0;x<width;++x){
                    const double C=mhcNAt(raw,width,sourceHeight,y,x,invR,1.0,invB),N=mhcNAt(raw,width,sourceHeight,y-1,x,invR,1.0,invB),S=mhcNAt(raw,width,sourceHeight,y+1,x,invR,1.0,invB),W=mhcNAt(raw,width,sourceHeight,y,x-1,invR,1.0,invB),E=mhcNAt(raw,width,sourceHeight,y,x+1,invR,1.0,invB);
                    const double NN=mhcNAt(raw,width,sourceHeight,y-2,x,invR,1.0,invB),SS=mhcNAt(raw,width,sourceHeight,y+2,x,invR,1.0,invB),WW=mhcNAt(raw,width,sourceHeight,y,x-2,invR,1.0,invB),EE=mhcNAt(raw,width,sourceHeight,y,x+2,invR,1.0,invB);
                    const double NW=mhcNAt(raw,width,sourceHeight,y-1,x-1,invR,1.0,invB),NE=mhcNAt(raw,width,sourceHeight,y-1,x+1,invR,1.0,invB),SW=mhcNAt(raw,width,sourceHeight,y+1,x-1,invR,1.0,invB),SE=mhcNAt(raw,width,sourceHeight,y+1,x+1,invR,1.0,invB);
                    const double g=(4.0*C+2.0*(N+S+W+E)-(NN+SS+WW+EE))/8.0;
                    const double o=(12.0*C+4.0*(NW+NE+SW+SE)-3.0*(NN+SS+WW+EE))/16.0;
                    const double hh=(10.0*C+8.0*(W+E)+(NN+SS)-2.0*(NW+NE+SW+SE)-2.0*(WW+EE))/16.0;
                    const double vv=(10.0*C+8.0*(N+S)+(WW+EE)-2.0*(NW+NE+SW+SE)-2.0*(NN+SS))/16.0;
                    const bool ey=(y&1)==0,ex=(x&1)==0;double rr,gg,bb;
                    if(ey&&ex){rr=C;gg=g;bb=o;}else if(!ey&&!ex){rr=o;gg=g;bb=C;}else if(ey){rr=hh;gg=C;bb=vv;}else{rr=vv;gg=C;bb=hh;}
                    if(rr<0.0||gg<0.0||bb<0.0||rr>65535.0||gg>65535.0||bb>65535.0)neutralClip++;
                    double scalar=((rr+gg+bb)/3.0)*representationScale;
                    if(!std::isfinite(scalar)||scalar<=0.0){scalar=0.0;low++;}else if(scalar>=65535.0){scalar=65535.0;high++;}
                    const uint32_t source16=static_cast<uint32_t>(std::llround(scalar));
                    image[row+static_cast<size_t>(x)]=static_cast<uint16_t>(std::min<uint32_t>(16383u,source16>>2));
                }}
            ws[static_cast<size_t>(worker)]={low,high,neutralClip};
        });
    }
    for(auto& t:threads)t.join();threads.clear();
    env->ReleasePrimitiveArrayCritical(rawArray,raw,JNI_ABORT);raw=nullptr;

    const int isoSlot=mmMonoNearestIsoSlotEv(captureIso>0?captureIso:MM_MONO_STD_SHARP_ISOS[0]);
    const int16_t* table=MM_MONO_STD_SHARP_LUT[isoSlot];
    const int clipMag=-static_cast<int>(table[0]);
    const int B=MM_MONO_STD_SHARP_BORDER;
    uint64_t changed=0;
    if(width-2*B>0&&sourceHeight-2*B>0){
        std::vector<uint16_t> scratch(static_cast<size_t>(pixels64));
        for(int y=B-1;y<=sourceHeight-B;++y){const size_t row=static_cast<size_t>(y)*static_cast<size_t>(width);
            for(int x=B;x<width-B;++x){const size_t p=row+static_cast<size_t>(x);
                scratch[p]=static_cast<uint16_t>((static_cast<uint32_t>(image[p-1])+2u*image[p]+image[p+1])>>2);
            }}
        for(int y=B;y<sourceHeight-B;++y){const size_t row=static_cast<size_t>(y)*static_cast<size_t>(width);
            for(int x=B;x<width-B;++x){const size_t p=row+static_cast<size_t>(x);
                const int blur=(static_cast<int>(scratch[p-width])+2*static_cast<int>(scratch[p])+static_cast<int>(scratch[p+width]))>>2;
                const int detail=static_cast<int>(image[p])-blur;int correction;
                if(detail < -1024)correction=-clipMag;else if(detail>1024)correction=clipMag;else correction=static_cast<int>(table[1024+detail]);
                int v=static_cast<int>(image[p])+correction;if(v<0)v=0;else if(v>16383)v=16383;
                if(v!=image[p])changed++;image[p]=static_cast<uint16_t>(v);
            }}
    }

    void* bitmapPixels=nullptr;
    if(AndroidBitmap_lockPixels(env,bitmap,&bitmapPixels)!=ANDROID_BITMAP_RESULT_SUCCESS||!bitmapPixels)return JNI_FALSE;
    auto* dst=static_cast<uint8_t*>(bitmapPixels);uint64_t near=0;
    for(int y=0;y<sourceHeight;++y){const size_t row=static_cast<size_t>(y)*static_cast<size_t>(width);
        for(int x=0;x<width;++x){
            int32_t v=static_cast<int32_t>(image[row+static_cast<size_t>(x)])-pedestal14;if(v<0)v=0;
            int idx=v>>3;if(idx>2047)idx=2047;const uint8_t yy=MM_MONO1A_CURVE02[idx];if(yy>=250)near++;
            int dx,dy;if(rotation==90){dx=sourceHeight-1-y;dy=x;}else if(rotation==180){dx=width-1-x;dy=sourceHeight-1-y;}else if(rotation==270){dx=y;dy=width-1-x;}else{dx=x;dy=y;}
            uint8_t* d=dst+static_cast<size_t>(dy)*static_cast<size_t>(info.stride)+static_cast<size_t>(dx)*4u;
            const jint argb=static_cast<jint>(0xff000000u|(uint32_t(yy)<<16)|(uint32_t(yy)<<8)|uint32_t(yy));storeArgbAsRgba8888(d,argb);
        }}
    const int unlock=AndroidBitmap_unlockPixels(env,bitmap);
    const auto ended=std::chrono::steady_clock::now();uint64_t low=0,high=0,neutralClip=0;for(const auto&s:ws){low+=s[0];high+=s[1];neutralClip+=s[2];}
    if(statsArray&&env->GetArrayLength(statsArray)>=12){const jlong ns=static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(ended-started).count());
        const jlong stats[12]={static_cast<jlong>(pixels64),static_cast<jlong>(changed),static_cast<jlong>(isoSlot),static_cast<jlong>(MM_MONO_STD_SHARP_ISOS[isoSlot]),static_cast<jlong>(MM_MONO_STD_SHARP_CODES[isoSlot]),ns,static_cast<jlong>(B),static_cast<jlong>(captureIso),static_cast<jlong>(near),static_cast<jlong>(low),static_cast<jlong>(high),static_cast<jlong>(neutralClip)};
        env->SetLongArrayRegion(statsArray,0,12,stats);
    }
    return unlock==ANDROID_BITMAP_RESULT_SUCCESS&&!env->ExceptionCheck()?JNI_TRUE:JNI_FALSE;
}
'''
C.write_text(c.rstrip()+fn+'\n')
print('MONO1A SHARPSTD1A A/B applied')
