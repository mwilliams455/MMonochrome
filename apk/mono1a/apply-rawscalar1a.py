#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply-rawscalar1a.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
R = root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
N = root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java'
C = root/'app/src/main/cpp/m9color_jni.cpp'
for p in (R,N,C):
    if not p.exists(): raise SystemExit('missing '+str(p))

def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f'{label}: anchor count={n}, expected 1')
    return s.replace(a,b,1)

r=R.read_text()
if 'RAWSCALAR1A' in r:
    raise SystemExit('RAWSCALAR1A already applied')

a='''        final Bitmap source1cEqualRgbBitmap;\n        final Bitmap source1cGreenBitmap;\n        RenderCore(Bitmap bitmap, JSONObject diagnostics) {\n            this(bitmap, diagnostics, null, null);\n        }\n        RenderCore(Bitmap bitmap, JSONObject diagnostics,\n                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap) {\n            this.bitmap = bitmap;\n            this.diagnostics = diagnostics;\n            this.source1cEqualRgbBitmap = source1cEqualRgbBitmap;\n            this.source1cGreenBitmap = source1cGreenBitmap;\n        }\n'''
b='''        final Bitmap source1cEqualRgbBitmap;\n        final Bitmap source1cGreenBitmap;\n        final Bitmap rawScalar1ABitmap;\n        RenderCore(Bitmap bitmap, JSONObject diagnostics) {\n            this(bitmap, diagnostics, null, null, null);\n        }\n        RenderCore(Bitmap bitmap, JSONObject diagnostics,\n                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap) {\n            this(bitmap, diagnostics, source1cEqualRgbBitmap, source1cGreenBitmap, null);\n        }\n        RenderCore(Bitmap bitmap, JSONObject diagnostics,\n                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap,\n                   Bitmap rawScalar1ABitmap) {\n            this.bitmap = bitmap;\n            this.diagnostics = diagnostics;\n            this.source1cEqualRgbBitmap = source1cEqualRgbBitmap;\n            this.source1cGreenBitmap = source1cGreenBitmap;\n            this.rawScalar1ABitmap = rawScalar1ABitmap;\n        }\n'''
r=one(r,a,b,'RenderCore RAWSCALAR bitmap slot')

a='''            Path source1cEqualRgbPath = null;\n            Path source1cGreenPath = null;\n            boolean source1cEqualRgbSaved = false;\n            boolean source1cGreenSaved = false;\n            String source1cEqualRgbError = null;\n            String source1cGreenError = null;\n'''
b='''            Path source1cEqualRgbPath = null;\n            Path source1cGreenPath = null;\n            Path rawScalar1APath = null;\n            boolean source1cEqualRgbSaved = false;\n            boolean source1cGreenSaved = false;\n            boolean rawScalar1ASaved = false;\n            String source1cEqualRgbError = null;\n            String source1cGreenError = null;\n            String rawScalar1AError = null;\n'''
r=one(r,a,b,'RAWSCALAR save vars')

a='''            if (out.source1cGreenBitmap != null) {\n                source1cGreenPath = Paths.get(FileManager.sDCIM_CAMERA.getAbsolutePath(),\n                        stem + "_MONO_GREEN.jpg");\n                try (OutputStream auxOut = Files.newOutputStream(source1cGreenPath)) {\n                    source1cGreenSaved = out.source1cGreenBitmap.compress(\n                            Bitmap.CompressFormat.JPEG, JPEG_QUALITY, auxOut);\n                    auxOut.flush();\n                } catch (Throwable auxError) {\n                    source1cGreenError = auxError.toString();\n                } finally {\n                    if (!out.source1cGreenBitmap.isRecycled()) out.source1cGreenBitmap.recycle();\n                }\n            }\n\n            long elapsedMs = (System.nanoTime() - started) / 1_000_000L;\n'''
b='''            if (out.source1cGreenBitmap != null) {\n                source1cGreenPath = Paths.get(FileManager.sDCIM_CAMERA.getAbsolutePath(),\n                        stem + "_MONO_GREEN.jpg");\n                try (OutputStream auxOut = Files.newOutputStream(source1cGreenPath)) {\n                    source1cGreenSaved = out.source1cGreenBitmap.compress(\n                            Bitmap.CompressFormat.JPEG, JPEG_QUALITY, auxOut);\n                    auxOut.flush();\n                } catch (Throwable auxError) {\n                    source1cGreenError = auxError.toString();\n                } finally {\n                    if (!out.source1cGreenBitmap.isRecycled()) out.source1cGreenBitmap.recycle();\n                }\n            }\n            if (out.rawScalar1ABitmap != null) {\n                rawScalar1APath = Paths.get(FileManager.sDCIM_CAMERA.getAbsolutePath(),\n                        stem + "_MONO_RAWSCALAR1A.jpg");\n                try (OutputStream auxOut = Files.newOutputStream(rawScalar1APath)) {\n                    rawScalar1ASaved = out.rawScalar1ABitmap.compress(\n                            Bitmap.CompressFormat.JPEG, JPEG_QUALITY, auxOut);\n                    auxOut.flush();\n                } catch (Throwable auxError) {\n                    rawScalar1AError = auxError.toString();\n                } finally {\n                    if (!out.rawScalar1ABitmap.isRecycled()) out.rawScalar1ABitmap.recycle();\n                }\n            }\n\n            long elapsedMs = (System.nanoTime() - started) / 1_000_000L;\n'''
r=one(r,a,b,'RAWSCALAR save block')

a='''            if (source1cGreenPath != null) {\n                diag.put("source1cGreenJpegPath", source1cGreenPath.toString());\n                diag.put("source1cGreenJpegSaved", source1cGreenSaved);\n                if (source1cGreenError != null) diag.put("source1cGreenJpegError", source1cGreenError);\n            }\n            diag.put("parityPngEnabled", SAVE_PARITY_PNG);\n'''
b='''            if (source1cGreenPath != null) {\n                diag.put("source1cGreenJpegPath", source1cGreenPath.toString());\n                diag.put("source1cGreenJpegSaved", source1cGreenSaved);\n                if (source1cGreenError != null) diag.put("source1cGreenJpegError", source1cGreenError);\n            }\n            if (rawScalar1APath != null) {\n                diag.put("rawScalar1AJpegPath", rawScalar1APath.toString());\n                diag.put("rawScalar1AJpegSaved", rawScalar1ASaved);\n                if (rawScalar1AError != null) diag.put("rawScalar1AJpegError", rawScalar1AError);\n            }\n            diag.put("parityPngEnabled", SAVE_PARITY_PNG);\n'''
r=one(r,a,b,'RAWSCALAR save diagnostics')

a='''        NativeProspectiveShadingStats nativeShading = applyNativeShading\n                ? (applyShadingLumaDecomp1A\n                        ? applyNativeProspectiveGainMapLumaDecomp1A(\n                                norm16, width, height, nativeLiveGainMap, effectiveShadingLumaAuthorityAlpha)\n                        : applyNativeProspectiveGainMap(norm16, width, height, nativeLiveGainMap))\n                : NativeProspectiveShadingStats.none();\n\n        // DEMOSAICAB1A keeps the production MHC direct RGB16 path exact. Only encoded\n'''
b='''        NativeProspectiveShadingStats nativeShading = applyNativeShading\n                ? (applyShadingLumaDecomp1A\n                        ? applyNativeProspectiveGainMapLumaDecomp1A(\n                                norm16, width, height, nativeLiveGainMap, effectiveShadingLumaAuthorityAlpha)\n                        : applyNativeProspectiveGainMap(norm16, width, height, nativeLiveGainMap))\n                : NativeProspectiveShadingStats.none();\n\n        Bitmap rawScalar1ABitmap = null;\n        long[] rawScalar1AStats = null;\n        if (MONO1A_ENABLED) {\n            final int rawScalarRotation = ((cameraRotation % 360) + 360) % 360;\n            final int rawScalarOutW = (rawScalarRotation == 90 || rawScalarRotation == 270) ? height : width;\n            final int rawScalarOutH = (rawScalarRotation == 90 || rawScalarRotation == 270) ? width : height;\n            rawScalar1ABitmap = Bitmap.createBitmap(rawScalarOutW, rawScalarOutH, Bitmap.Config.ARGB_8888);\n            rawScalar1AStats = new long[8];\n            boolean rawScalar1AOk = M9NativeColorCore.renderMonochrome1ARawScalarDirectBitmap(\n                    norm16, width, height, rawScalar1ABitmap, cameraRotation, NATIVE_COLOR_WORKERS,\n                    MONO1A_SYNTHETIC_PEDESTAL14, neutralF[0], neutralF[1], neutralF[2],\n                    nativeShading.representationScale, rawScalar1AStats);\n            if (!rawScalar1AOk) {\n                if (!rawScalar1ABitmap.isRecycled()) rawScalar1ABitmap.recycle();\n                throw new IllegalStateException("MONO1A RAWSCALAR1A native render failed");\n            }\n        }\n\n        // DEMOSAICAB1A keeps the production MHC direct RGB16 path exact. Only encoded\n'''
r=one(r,a,b,'RAWSCALAR pre-demosaic render')

a='''                d.put("source1dPolicy", "counterfactual_only_no_auto_selection_no_tone_or_exposure_change");\n                return new RenderCore(monoBitmap, d, equalRgbBitmap, greenOnlyBitmap);\n'''
b='''                d.put("source1dPolicy", "counterfactual_only_no_auto_selection_no_tone_or_exposure_change");\n                JSONObject rawScalar1A = new JSONObject();\n                rawScalar1A.put("schema", "mmonochrome.rawscalar1a.v1");\n                rawScalar1A.put("photographicOutputSelected", false);\n                rawScalar1A.put("inputDomain", "normalized_linear_Bayer_after_physical_Camera2_LensShadingMap_before_MHC_RGB");\n                rawScalar1A.put("cfa", "RGGB");\n                rawScalar1A.put("neutralNormalization", "R*=neutralG/neutralR,G*=1,B*=neutralG/neutralB_before_spatial_reconstruction");\n                rawScalar1A.put("neutralR", neutralF[0]);\n                rawScalar1A.put("neutralG", neutralF[1]);\n                rawScalar1A.put("neutralB", neutralF[2]);\n                rawScalar1A.put("spatialReconstruction", "MHC_5x5_kernel_on_neutral_normalized_CFA");\n                rawScalar1A.put("scalarCollapse", "equal_mean_of_reconstructed_neutral_axis_R_G_B");\n                rawScalar1A.put("representationScaleRestored", nativeShading.representationScale);\n                rawScalar1A.put("leicaWorkingCoordinate", "clamp(round(scalar16),0,65535)>>>2_to_uint14");\n                rawScalar1A.put("curve", "same_frozen_Monochrom_curve02");\n                rawScalar1A.put("curve02Sha256", "7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752");\n                rawScalar1A.put("m9LumaCoefficientsApplied", false);\n                rawScalar1A.put("xyzCoefficientsApplied", false);\n                rawScalar1A.put("sourcecalApplied", false);\n                rawScalar1A.put("wbColorPipelineApplied", false);\n                rawScalar1A.put("leicaSpectralTruth", false);\n                rawScalar1A.put("role", "SOURCE1E_raw_domain_Xiaomi_CFA_to_scalar_diagnostic_not_Leica_CCD_spectral_emulation");\n                if (rawScalar1AStats != null && rawScalar1AStats.length >= 8) {\n                    rawScalar1A.put("nativePixelCount", rawScalar1AStats[0]);\n                    rawScalar1A.put("lowClampCount", rawScalar1AStats[1]);\n                    rawScalar1A.put("highClampCount", rawScalar1AStats[2]);\n                    rawScalar1A.put("nearWhiteOutputCount", rawScalar1AStats[3]);\n                    rawScalar1A.put("nativeWorkersUsed", rawScalar1AStats[4]);\n                    rawScalar1A.put("nativeRenderNs", rawScalar1AStats[5]);\n                    rawScalar1A.put("neutralAxisLowClipCount", rawScalar1AStats[6]);\n                    rawScalar1A.put("neutralAxisHighClipCount", rawScalar1AStats[7]);\n                }\n                d.put("rawScalar1A", rawScalar1A);\n                d.put("source1eArchitectureClosure", "16bit_scalar_pre_contrast_ProcessY_post_contrast");\n                d.put("rawScalar1APolicy", "diagnostic_only_primary_SOURCE1D_M9Y_unchanged");\n                return new RenderCore(monoBitmap, d, equalRgbBitmap, greenOnlyBitmap, rawScalar1ABitmap);\n'''
r=one(r,a,b,'RAWSCALAR diagnostics and return')
R.write_text(r)

n=N.read_text()
a='''    /** SOURCE1D XYZY1A counterfactual; native DNG Camera->XYZ D50 Y row. */\n    static native boolean renderMonochrome1AWeightedDirectBitmap(long camAddress,\n                                                                 int pixelCount, int width, int sourceHeight,\n                                                                 android.graphics.Bitmap bitmap, int cameraRotation,\n                                                                 int workers, int pedestal14,\n                                                                 float weightR, float weightG, float weightB);\n'''
b=a+'''\n\n    /** SOURCE1E RAWSCALAR1A diagnostic formed directly from normalized shaded Bayer CFA. */\n    static native boolean renderMonochrome1ARawScalarDirectBitmap(short[] raw,\n                                                                  int width, int sourceHeight,\n                                                                  android.graphics.Bitmap bitmap,\n                                                                  int cameraRotation, int workers, int pedestal14,\n                                                                  float neutralR, float neutralG, float neutralB,\n                                                                  double representationScale, long[] stats);\n'''
n=one(n,a,b,'RAWSCALAR native declaration')
N.write_text(n)

c=C.read_text()
if 'renderMonochrome1ARawScalarDirectBitmap' in c:
    raise SystemExit('RAWSCALAR JNI already present')
fn=r'''

// SOURCE1E RAWSCALAR1A. Xiaomi CFA-to-scalar adapter; not Leica CCD spectral truth.
extern "C" JNIEXPORT jboolean JNICALL
Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1ARawScalarDirectBitmap(
        JNIEnv* env, jclass, jshortArray rawArray, jint width, jint sourceHeight,
        jobject bitmap, jint cameraRotation, jint workers, jint pedestal14,
        jfloat neutralR, jfloat neutralG, jfloat neutralB, jdouble representationScale,
        jlongArray statsArray) {
    if (!rawArray || !bitmap || width <= 0 || sourceHeight <= 0 || workers <= 0
            || pedestal14 < 0 || pedestal14 > 16383
            || !std::isfinite(neutralR) || !std::isfinite(neutralG) || !std::isfinite(neutralB)
            || neutralR <= 0.0f || neutralG <= 0.0f || neutralB <= 0.0f
            || !std::isfinite(representationScale) || representationScale <= 0.0) {
        throwIllegalArgument(env, "Invalid MONO1A RAWSCALAR1A arguments"); return JNI_FALSE;
    }
    const int64_t pixels64=static_cast<int64_t>(width)*static_cast<int64_t>(sourceHeight);
    if(pixels64<=0 || pixels64>0x7fffffffLL || env->GetArrayLength(rawArray)<static_cast<jsize>(pixels64)) return JNI_FALSE;
    int rotation=cameraRotation%360; if(rotation<0)rotation+=360;
    const uint32_t outW=static_cast<uint32_t>((rotation==90||rotation==270)?sourceHeight:width);
    const uint32_t outH=static_cast<uint32_t>((rotation==90||rotation==270)?width:sourceHeight);
    AndroidBitmapInfo info{};
    if(AndroidBitmap_getInfo(env,bitmap,&info)!=ANDROID_BITMAP_RESULT_SUCCESS || info.format!=ANDROID_BITMAP_FORMAT_RGBA_8888
            || info.width!=outW || info.height!=outH || info.stride<outW*4u) return JNI_FALSE;
    void* rawPixels=nullptr;
    if(AndroidBitmap_lockPixels(env,bitmap,&rawPixels)!=ANDROID_BITMAP_RESULT_SUCCESS || !rawPixels) return JNI_FALSE;
    jboolean isCopy=JNI_FALSE;
    jshort* raw=static_cast<jshort*>(env->GetPrimitiveArrayCritical(rawArray,&isCopy));
    if(!raw){AndroidBitmap_unlockPixels(env,bitmap);return JNI_FALSE;}
    const double invR=static_cast<double>(neutralG)/static_cast<double>(neutralR);
    const double invB=static_cast<double>(neutralG)/static_cast<double>(neutralB);
    if(!std::isfinite(invR)||!std::isfinite(invB)||invR<=0.0||invB<=0.0){
        env->ReleasePrimitiveArrayCritical(rawArray,raw,JNI_ABORT); AndroidBitmap_unlockPixels(env,bitmap); return JNI_FALSE;
    }
    std::vector<jint> argb(static_cast<size_t>(pixels64));
    const int wc=std::max(1,std::min(static_cast<int>(workers),static_cast<int>(sourceHeight)));
    std::vector<std::array<uint64_t,4>> ws(static_cast<size_t>(wc));
    std::vector<std::thread> threads; threads.reserve(static_cast<size_t>(wc));
    auto* dst=static_cast<uint8_t*>(rawPixels); const auto started=std::chrono::steady_clock::now();
    for(int worker=0;worker<wc;++worker){
        const int y0=(sourceHeight*worker)/wc,y1=(sourceHeight*(worker+1))/wc;
        threads.emplace_back([&,worker,y0,y1](){
            uint64_t low=0,high=0,near=0,neutralClip=0;
            for(int y=y0;y<y1;++y){const size_t row=static_cast<size_t>(y)*static_cast<size_t>(width);
                for(int x=0;x<width;++x){
                    const double C=mhcNAt(raw,width,sourceHeight,y,x,invR,1.0,invB),N=mhcNAt(raw,width,sourceHeight,y-1,x,invR,1.0,invB),S=mhcNAt(raw,width,sourceHeight,y+1,x,invR,1.0,invB),W=mhcNAt(raw,width,sourceHeight,y,x-1,invR,1.0,invB),E=mhcNAt(raw,width,sourceHeight,y,x+1,invR,1.0,invB);
                    const double NN=mhcNAt(raw,width,sourceHeight,y-2,x,invR,1.0,invB),SS=mhcNAt(raw,width,sourceHeight,y+2,x,invR,1.0,invB),WW=mhcNAt(raw,width,sourceHeight,y,x-2,invR,1.0,invB),EE=mhcNAt(raw,width,sourceHeight,y,x+2,invR,1.0,invB);
                    const double NW=mhcNAt(raw,width,sourceHeight,y-1,x-1,invR,1.0,invB),NE=mhcNAt(raw,width,sourceHeight,y-1,x+1,invR,1.0,invB),SW=mhcNAt(raw,width,sourceHeight,y+1,x-1,invR,1.0,invB),SE=mhcNAt(raw,width,sourceHeight,y+1,x+1,invR,1.0,invB);
                    const double g=(4.0*C+2.0*(N+S+W+E)-(NN+SS+WW+EE))/8.0;
                    const double o=(12.0*C+4.0*(NW+NE+SW+SE)-3.0*(NN+SS+WW+EE))/16.0;
                    const double hh=(10.0*C+8.0*(W+E)+(NN+SS)-2.0*(NW+NE+SW+SE)-2.0*(WW+EE))/16.0;
                    const double vv=(10.0*C+8.0*(N+S)+(WW+EE)-2.0*(NW+NE+SW+SE)-2.0*(NN+SS))/16.0;
                    const bool ey=(y&1)==0,ex=(x&1)==0; double rr,gg,bb;
                    if(ey&&ex){rr=C;gg=g;bb=o;} else if(!ey&&!ex){rr=o;gg=g;bb=C;} else if(ey){rr=hh;gg=C;bb=vv;} else{rr=vv;gg=C;bb=hh;}
                    if(rr<0.0||gg<0.0||bb<0.0||rr>65535.0||gg>65535.0||bb>65535.0)neutralClip++;
                    double scalar=((rr+gg+bb)/3.0)*representationScale;
                    if(!std::isfinite(scalar)||scalar<=0.0){scalar=0.0;low++;} else if(scalar>=65535.0){scalar=65535.0;high++;}
                    const uint32_t source16=static_cast<uint32_t>(std::llround(scalar));
                    int32_t v=static_cast<int32_t>(std::min<uint32_t>(16383u,source16>>2))-pedestal14; if(v<0)v=0;
                    int32_t idx=v>>3;if(idx>2047)idx=2047;const uint8_t yy=MM_MONO1A_CURVE02[idx];if(yy>=250)near++;
                    const size_t p=row+static_cast<size_t>(x);argb[p]=static_cast<jint>(0xff000000u|(uint32_t(yy)<<16)|(uint32_t(yy)<<8)|uint32_t(yy));
                }}
            ws[static_cast<size_t>(worker)]={low,high,near,neutralClip};
            writeCompletedSubrangeToBitmap(argb.data(),dst,info.stride,sourceHeight,width,0,sourceHeight,y0,y1,cameraRotation);
        });
    }
    for(auto& t:threads)t.join(); const auto ended=std::chrono::steady_clock::now();
    env->ReleasePrimitiveArrayCritical(rawArray,raw,JNI_ABORT); const int unlock=AndroidBitmap_unlockPixels(env,bitmap);
    uint64_t low=0,high=0,near=0,neutralClip=0;for(const auto& s:ws){low+=s[0];high+=s[1];near+=s[2];neutralClip+=s[3];}
    if(statsArray&&env->GetArrayLength(statsArray)>=8){const jlong ns=static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(ended-started).count());
        const jlong stats[8]={static_cast<jlong>(pixels64),static_cast<jlong>(low),static_cast<jlong>(high),static_cast<jlong>(near),static_cast<jlong>(wc),ns,0,static_cast<jlong>(neutralClip)};env->SetLongArrayRegion(statsArray,0,8,stats);}
    return unlock==ANDROID_BITMAP_RESULT_SUCCESS&&!env->ExceptionCheck()?JNI_TRUE:JNI_FALSE;
}
'''
C.write_text(c.rstrip()+fn+'\n')
print('MONO1A RAWSCALAR1A applied')
