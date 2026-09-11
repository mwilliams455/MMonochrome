#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv)!=2: raise SystemExit('usage: apply-source1d.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve()
R=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
N=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java'
C=root/'app/src/main/cpp/m9color_jni.cpp'
for p in (R,N,C):
    if not p.exists(): raise SystemExit('missing '+str(p))

def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f'{label}: anchor count={n}, expected 1')
    return s.replace(a,b,1)

r=R.read_text()
if 'MONO1A_SOURCE1D_XYZY1A' in r: raise SystemExit('SOURCE1D already applied')

# Reuse SOURCE1C equal-RGB auxiliary bitmap slot for the physically grounded XYZY probe.
# Primary M9-Y remains untouched; green-only remains as the previous bracketing control.
a='''                Bitmap equalRgbBitmap = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888);\n                Bitmap greenOnlyBitmap = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888);\n                boolean equalRgbOk = M9NativeColorCore.renderMonochrome1AVariantDirectBitmap(\n                        cam16.dataAddr(), pixels, width, height, equalRgbBitmap,\n                        cameraRotation, NATIVE_COLOR_WORKERS,\n                        MONO1A_SYNTHETIC_PEDESTAL14, 1);\n                boolean greenOnlyOk = equalRgbOk && M9NativeColorCore.renderMonochrome1AVariantDirectBitmap(\n'''
b='''                Bitmap equalRgbBitmap = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888);\n                Bitmap greenOnlyBitmap = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888);\n                NativeProspectiveSource source1dNative = buildNativeProspectiveSource(\n                        nativeCharacteristics, nativeCaptureResult);\n                final float source1dWeightR = source1dNative.sensorToXyzD50[3];\n                final float source1dWeightG = source1dNative.sensorToXyzD50[4];\n                final float source1dWeightB = source1dNative.sensorToXyzD50[5];\n                final double source1dNeutralY = source1dWeightR * source1dNative.neutral[0]\n                        + source1dWeightG * source1dNative.neutral[1]\n                        + source1dWeightB * source1dNative.neutral[2];\n                if (!Float.isFinite(source1dWeightR) || !Float.isFinite(source1dWeightG)\n                        || !Float.isFinite(source1dWeightB) || !Double.isFinite(source1dNeutralY)\n                        || source1dNeutralY <= 0.0)\n                    throw new IllegalStateException("MONO1A SOURCE1D invalid native DNG XYZ-Y transform");\n                boolean equalRgbOk = M9NativeColorCore.renderMonochrome1AWeightedDirectBitmap(\n                        cam16.dataAddr(), pixels, width, height, equalRgbBitmap,\n                        cameraRotation, NATIVE_COLOR_WORKERS, MONO1A_SYNTHETIC_PEDESTAL14,\n                        source1dWeightR, source1dWeightG, source1dWeightB);\n                boolean greenOnlyOk = equalRgbOk && M9NativeColorCore.renderMonochrome1AVariantDirectBitmap(\n'''
r=one(r,a,b,'SOURCE1D XYZY visual render')

# Replace visual filename/outer save telemetry for the reused slot.
r=one(r,'stem + "_MONO_EQUALRGB.jpg"','stem + "_MONO_XYZY.jpg"','SOURCE1D XYZY filename')
r=r.replace('source1cEqualRgbJpegPath','source1dXyzYJpegPath')
r=r.replace('source1cEqualRgbJpegSaved','source1dXyzYJpegSaved')
r=r.replace('source1cEqualRgbJpegError','source1dXyzYJpegError')

# Authoritative matrix semantics and provenance. Equal-RGB statistics remain logged as a historical
# counterfactual, but its visual slot is now XYZY; no source is auto-selected.
a='''                d.put("source1cGreenMode", "G>>>2_to_Leica14_then_curve02");\n                return new RenderCore(monoBitmap, d, equalRgbBitmap, greenOnlyBitmap);\n'''
b='''                d.put("source1cGreenMode", "G>>>2_to_Leica14_then_curve02");\n                d.put("source1cEqualRgbVisualRendered", false);\n                JSONObject source1dXyzY = new JSONObject();\n                source1dXyzY.put("schema", "mmonochrome.source1d.xyzy1a.v1");\n                source1dXyzY.put("mode", "NATIVE_DNG_SENSOR_TO_XYZ_D50_Y_ROW");\n                source1dXyzY.put("photographicOutputSelected", false);\n                source1dXyzY.put("input", "same_post_MHC_cam16_sensor_RGB");\n                source1dXyzY.put("matrixSemantics", "CameraToXYZ_D50_owns_WB_no_second_AsShotNeutral_multiply");\n                source1dXyzY.put("weightR", source1dWeightR);\n                source1dXyzY.put("weightG", source1dWeightG);\n                source1dXyzY.put("weightB", source1dWeightB);\n                source1dXyzY.put("neutralR", source1dNative.neutral[0]);\n                source1dXyzY.put("neutralG", source1dNative.neutral[1]);\n                source1dXyzY.put("neutralB", source1dNative.neutral[2]);\n                source1dXyzY.put("neutralVectorMapsToY", source1dNeutralY);\n                source1dXyzY.put("nativeInterpolationFactor", source1dNative.interpolationFactor);\n                source1dXyzY.put("sensorToXYZD50", nativeProspectiveMatrix(source1dNative.sensorToXyzD50));\n                source1dXyzY.put("formula", "clamp(Yrow_sensorToXYZD50 dot sensorRGB,0,65535)>>>2_then_curve02");\n                source1dXyzY.put("curve", "same_frozen_Monochrom_curve02");\n                source1dXyzY.put("role", "counterfactual_scene_luminance_bridge_not_Leica_spectral_truth");\n                d.put("source1dXyzY", source1dXyzY);\n                d.put("source1Revision", "MONO1A_SOURCE1D_XYZY1A");\n                d.put("source1dPolicy", "counterfactual_only_no_auto_selection_no_tone_or_exposure_change");\n                return new RenderCore(monoBitmap, d, equalRgbBitmap, greenOnlyBitmap);\n'''
r=one(r,a,b,'SOURCE1D diagnostics')
r=r.replace('mmonochrome.mono1a.source1c.v1','mmonochrome.mono1a.source1d.v1')
r=r.replace('d.put("source1Revision", "MONO1A_SOURCE1C");','d.put("source1Revision", "MONO1A_SOURCE1D_XYZY1A");')
R.write_text(r)

n=N.read_text()
a='''    /** SOURCE1C visual counterfactual only. mode 1=equal RGB, 2=green-only. */\n    static native boolean renderMonochrome1AVariantDirectBitmap(long camAddress,\n                                                                int pixelCount,\n                                                                int width,\n                                                                int sourceHeight,\n                                                                android.graphics.Bitmap bitmap,\n                                                                int cameraRotation,\n                                                                int workers,\n                                                                int pedestal14,\n                                                                int sourceMode);\n'''
b=a+'''\n    /** SOURCE1D XYZY1A counterfactual; native DNG Camera->XYZ D50 Y row. */\n    static native boolean renderMonochrome1AWeightedDirectBitmap(long camAddress,\n                                                                 int pixelCount, int width, int sourceHeight,\n                                                                 android.graphics.Bitmap bitmap, int cameraRotation,\n                                                                 int workers, int pedestal14,\n                                                                 float weightR, float weightG, float weightB);\n'''
n=one(n,a,b,'SOURCE1D native declaration')
N.write_text(n)

c=C.read_text()
if 'renderMonochrome1AWeightedDirectBitmap' in c: raise SystemExit('SOURCE1D JNI already present')
fn=r'''

extern "C" JNIEXPORT jboolean JNICALL
Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1AWeightedDirectBitmap(
        JNIEnv* env, jclass, jlong camAddress, jint pixelCount, jint width, jint sourceHeight,
        jobject bitmap, jint cameraRotation, jint workers, jint pedestal14,
        jfloat weightR, jfloat weightG, jfloat weightB) {
    const auto* cam = reinterpret_cast<const jshort*>(static_cast<uintptr_t>(camAddress));
    if (!cam || !bitmap || width <= 0 || sourceHeight <= 0 || pixelCount != width * sourceHeight
            || workers <= 0 || pedestal14 < 0 || pedestal14 > 16383
            || !std::isfinite(weightR) || !std::isfinite(weightG) || !std::isfinite(weightB)) {
        throwIllegalArgument(env, "Invalid MONO1A SOURCE1D weighted arguments"); return JNI_FALSE;
    }
    int rotation = cameraRotation % 360; if (rotation < 0) rotation += 360;
    const uint32_t outW = static_cast<uint32_t>((rotation == 90 || rotation == 270) ? sourceHeight : width);
    const uint32_t outH = static_cast<uint32_t>((rotation == 90 || rotation == 270) ? width : sourceHeight);
    AndroidBitmapInfo info{};
    if (AndroidBitmap_getInfo(env, bitmap, &info) != ANDROID_BITMAP_RESULT_SUCCESS
            || info.format != ANDROID_BITMAP_FORMAT_RGBA_8888 || info.width != outW
            || info.height != outH || info.stride < outW * 4u) return JNI_FALSE;
    void* rawPixels = nullptr;
    if (AndroidBitmap_lockPixels(env, bitmap, &rawPixels) != ANDROID_BITMAP_RESULT_SUCCESS || !rawPixels) return JNI_FALSE;
    std::vector<jint> argb(static_cast<size_t>(pixelCount));
    const int wc = std::max(1, std::min(static_cast<int>(workers), sourceHeight));
    std::vector<std::thread> threads; threads.reserve(static_cast<size_t>(wc));
    auto* dst = static_cast<uint8_t*>(rawPixels);
    const double wr=weightR, wg=weightG, wb=weightB;
    for (int worker=0; worker<wc; ++worker) {
        const int y0=(sourceHeight*worker)/wc, y1=(sourceHeight*(worker+1))/wc;
        threads.emplace_back([&,y0,y1]() {
            for (int y=y0; y<y1; ++y) {
                const size_t row=static_cast<size_t>(y)*static_cast<size_t>(width);
                for (int x=0; x<width; ++x) {
                    const size_t p=row+static_cast<size_t>(x), ci=p*3u;
                    double source=wr*u16(cam[ci])+wg*u16(cam[ci+1])+wb*u16(cam[ci+2]);
                    source=std::max(0.0,std::min(65535.0,source));
                    const uint32_t source16=static_cast<uint32_t>(std::llround(source));
                    int32_t v=static_cast<int32_t>(std::min<uint32_t>(16383u,source16>>2))-pedestal14;
                    if (v<0) v=0; int32_t idx=v>>3; if (idx>2047) idx=2047;
                    const uint8_t yy=MM_MONO1A_CURVE02[idx];
                    argb[p]=static_cast<jint>(0xff000000u|(uint32_t(yy)<<16)|(uint32_t(yy)<<8)|uint32_t(yy));
                }
            }
            writeCompletedSubrangeToBitmap(argb.data(),dst,info.stride,sourceHeight,width,0,sourceHeight,y0,y1,cameraRotation);
        });
    }
    for (auto& t:threads) t.join();
    const int u=AndroidBitmap_unlockPixels(env,bitmap);
    return u==ANDROID_BITMAP_RESULT_SUCCESS && !env->ExceptionCheck() ? JNI_TRUE : JNI_FALSE;
}
'''
# raw string above contains real newlines; append at EOF after SOURCE1C variant.
C.write_text(c.rstrip()+fn+'\n')
print('MONO1A SOURCE1D XYZY1A applied')
