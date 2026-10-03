#!/usr/bin/env python3
"""LEICATONING1A_FIX2_SOURCE1D: apply Leica Contrast + Toning to the actual portable SOURCE1D primary."""
from pathlib import Path
import hashlib,json,re,sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
R=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
N=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java"
C=root/"app/src/main/cpp/m9color_jni.cpp"
G=root/"app/build.gradle"
for p in (R,N,C,G):
    if not p.is_file(): raise SystemExit("FIX2 missing "+str(p))
for marker in ("LEICACONTRAST1A_ISOLATION.json","LEICATONING1A_ISOLATION.json","LEICATONING1A_FIX1_ISOLATION.json"):
    if not (root/marker).is_file(): raise SystemExit("FIX2 missing parent receipt "+marker)

def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"FIX2 {label} anchor count={n}")
    return s.replace(a,b,1)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen=[
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngExport1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngWriter1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoLinearPlane1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/exposure/MonoPlacementAssist1D.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoTapMeter1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java",
]
before={str(p.relative_to(root)):sha(p) for p in frozen}

# Java native declaration: SOURCE1D now accepts exact selected curve + firmware Cr/Cb pair.
n=N.read_text()
n=one(n,
"""    static native boolean renderMonochrome1AWeightedDirectBitmap(long camAddress,
                                                                 int pixelCount, int width, int sourceHeight,
                                                                 android.graphics.Bitmap bitmap, int cameraRotation,
                                                                 int workers, int pedestal14,
                                                                 float weightR, float weightG, float weightB);
""",
"""    static native boolean renderMonochrome1AWeightedDirectBitmap(long camAddress,
                                                                 int pixelCount, int width, int sourceHeight,
                                                                 android.graphics.Bitmap bitmap, int cameraRotation,
                                                                 int workers, int pedestal14,
                                                                 float weightR, float weightG, float weightB,
                                                                 byte[] contrastCurve, int toningCr, int toningCb);
""","SOURCE1D JNI declaration")
N.write_text(n)

# Renderer: select the exact same Leica settings used by live preview immediately before SOURCE1D render.
r=R.read_text()
r=one(r,
"""                boolean equalRgbOk = M9NativeColorCore.renderMonochrome1AWeightedDirectBitmap(
                        cam16.dataAddr(), pixels, width, height, equalRgbBitmap,
                        cameraRotation, NATIVE_COLOR_WORKERS, MONO1A_SYNTHETIC_PEDESTAL14,
                        source1dWeightR, source1dWeightG, source1dWeightB);
""",
"""                final int source1dContrast1A = MonoContrastCurves1A.clamp(
                        com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoContrastValue());
                final byte[] source1dContrastCurve1A = MonoContrastCurves1A.loadCurveOrNull(source1dContrast1A);
                final boolean source1dContrastFallback1A = source1dContrastCurve1A == null;
                final int source1dToningHue1A =
                        com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoToningHueValue();
                final int source1dToningStrength1A =
                        com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoToningStrengthValue();
                final int source1dToningState1A =
                        MonoToning1A.state(source1dToningHue1A, source1dToningStrength1A);
                final int source1dToningCr1A = MonoToning1A.CR[source1dToningState1A];
                final int source1dToningCb1A = MonoToning1A.CB[source1dToningState1A];
                boolean equalRgbOk = M9NativeColorCore.renderMonochrome1AWeightedDirectBitmap(
                        cam16.dataAddr(), pixels, width, height, equalRgbBitmap,
                        cameraRotation, NATIVE_COLOR_WORKERS, MONO1A_SYNTHETIC_PEDESTAL14,
                        source1dWeightR, source1dWeightG, source1dWeightB,
                        source1dContrastCurve1A, source1dToningCr1A, source1dToningCb1A);
""","SOURCE1D selected Leica controls")

# SOURCE1D's own provenance must describe the actual selected photographic path.
r=one(r,
'                source1dXyzY.put("formula", "clamp(Yrow_sensorToXYZD50 dot sensorRGB,0,65535)>>>2_then_curve02");\n'
'                source1dXyzY.put("curve", "same_frozen_Monochrom_curve02");\n',
'                source1dXyzY.put("formula", "clamp(Yrow_sensorToXYZD50 dot sensorRGB,0,65535)>>>2_then_selected_M_Monochrom_contrast_curve_then_firmware_toning");\n'
'                source1dXyzY.put("curve", "firmware_normalISO_sRGB_curve0" + source1dContrast1A);\n'
'                source1dXyzY.put("contrastEnum", source1dContrast1A);\n'
'                source1dXyzY.put("contrastLabel", MonoContrastCurves1A.LABELS[source1dContrast1A]);\n'
'                source1dXyzY.put("contrastCurveSha256", MonoContrastCurves1A.SHA256[source1dContrast1A]);\n'
'                source1dXyzY.put("contrastCurveFallbackToStandard", source1dContrastFallback1A);\n'
'                source1dXyzY.put("contrastCurveRuntimeError", MonoContrastCurves1A.lastLoadError());\n'
'                source1dXyzY.put("toningState", source1dToningState1A);\n'
'                source1dXyzY.put("toningLabel", MonoToning1A.STATE_LABELS[source1dToningState1A]);\n'
'                source1dXyzY.put("toningCr", source1dToningCr1A);\n'
'                source1dXyzY.put("toningCb", source1dToningCb1A);\n'
'                source1dXyzY.put("toningDomain", "firmware_PROCESS_LUTS_YCrCb_chroma_pair");\n',
"SOURCE1D provenance")

# Portable policy now accurately states that target JPEG tone/toning is active while source calibration remains portable.
r=one(r,
'                d.put("source1dPolicy", "selected_portable_active_sensor_DNG_XYZ_Y_no_target_tone_or_exposure_change");\n',
'                d.put("source1dPolicy", "selected_portable_active_sensor_DNG_XYZ_Y_with_Leica_JPEG_contrast_and_toning_DNG_and_exposure_unchanged");\n',
"SOURCE1D policy")

# Update pipeline wording if the frozen SOURCE1D pipeline marker is present.
oldpipe='black_white_normalize -> physical Camera2 LensShadingMap -> DEMOSAICMHCNEUTRAL1A -> SOURCE1D_XYZ_D50_Y -> Leica14 mode0 -> M Monochrom 1.022 curve02'
if oldpipe in r:
    r=r.replace(oldpipe,
        'black_white_normalize -> physical Camera2 LensShadingMap -> DEMOSAICMHCNEUTRAL1A -> SOURCE1D_XYZ_D50_Y -> Leica14 mode0 -> selected M Monochrom contrast curve -> optional firmware YCrCb toning',1)
R.write_text(r)

# C++: replace only the SOURCE1D weighted renderer with the same selected curve + YCrCb implementation.
c=C.read_text()
needle="Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1AWeightedDirectBitmap("
pos=c.find(needle)
if pos<0 or c.find(needle,pos+1)>=0: raise SystemExit("FIX2 SOURCE1D JNI function uniqueness failure")
start=c.rfind('extern "C" JNIEXPORT jboolean JNICALL',0,pos)
if start<0: raise SystemExit("FIX2 SOURCE1D JNI start missing")
brace=c.find('{',pos)
if brace<0: raise SystemExit("FIX2 SOURCE1D JNI brace missing")
depth=0; end=None
for i in range(brace,len(c)):
    if c[i]=='{': depth+=1
    elif c[i]=='}':
        depth-=1
        if depth==0:
            end=i+1
            break
if end is None: raise SystemExit("FIX2 SOURCE1D JNI end missing")

fn=r'''extern "C" JNIEXPORT jboolean JNICALL
Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1AWeightedDirectBitmap(
        JNIEnv* env, jclass, jlong camAddress, jint pixelCount, jint width, jint sourceHeight,
        jobject bitmap, jint cameraRotation, jint workers, jint pedestal14,
        jfloat weightR, jfloat weightG, jfloat weightB,
        jbyteArray contrastCurveArray, jint toningCr, jint toningCb) {
    const auto* cam = reinterpret_cast<const jshort*>(static_cast<uintptr_t>(camAddress));
    if (!cam || !bitmap || width <= 0 || sourceHeight <= 0 || pixelCount != width * sourceHeight
            || workers <= 0 || pedestal14 < 0 || pedestal14 > 16383
            || !std::isfinite(weightR) || !std::isfinite(weightG) || !std::isfinite(weightB)) {
        throwIllegalArgument(env, "Invalid MONO1A SOURCE1D weighted arguments"); return JNI_FALSE;
    }
    std::array<uint8_t,2048> contrastCurve{};
    if (contrastCurveArray && env->GetArrayLength(contrastCurveArray) == 2048) {
        std::array<jbyte,2048> contrastBytes{};
        env->GetByteArrayRegion(contrastCurveArray,0,2048,contrastBytes.data());
        if (env->ExceptionCheck()) return JNI_FALSE;
        for(size_t i=0;i<contrastCurve.size();++i) contrastCurve[i]=static_cast<uint8_t>(contrastBytes[i]);
    } else {
        // Same nonfatal capture policy as RAWSCALAR: Standard curve02 if multi-curve bank is unavailable.
        for(size_t i=0;i<contrastCurve.size();++i) contrastCurve[i]=MM_MONO1A_CURVE02[i];
    }
    const int cr=std::max(0,std::min(255,static_cast<int>(toningCr)));
    const int cb=std::max(0,std::min(255,static_cast<int>(toningCb)));
    const int dCr=cr-128,dCb=cb-128;
    auto roundShift16=[](int x)->int { return x>=0 ? ((x+32768)>>16) : -(((-x)+32768)>>16); };
    auto clamp8=[](int x)->uint8_t { return static_cast<uint8_t>(x<0?0:(x>255?255:x)); };

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
                    const uint8_t yy=contrastCurve[static_cast<size_t>(idx)];
                    const uint8_t outR=clamp8(static_cast<int>(yy)+roundShift16(91881*dCr));
                    const uint8_t outG=clamp8(static_cast<int>(yy)-roundShift16(22554*dCb+46802*dCr));
                    const uint8_t outB=clamp8(static_cast<int>(yy)+roundShift16(116130*dCb));
                    argb[p]=static_cast<jint>(0xff000000u|(uint32_t(outR)<<16)|(uint32_t(outG)<<8)|uint32_t(outB));
                }
            }
            writeCompletedSubrangeToBitmap(argb.data(),dst,info.stride,sourceHeight,width,0,sourceHeight,y0,y1,cameraRotation);
        });
    }
    for (auto& t:threads) t.join();
    const int u=AndroidBitmap_unlockPixels(env,bitmap);
    return u==ANDROID_BITMAP_RESULT_SUCCESS && !env->ExceptionCheck() ? JNI_TRUE : JNI_FALSE;
}'''
c=c[:start]+fn+c[end:]
C.write_text(c)

# Build identity.
g=G.read_text(); m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("FIX2 versionName missing")
if "fix2source1d" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-fix2source1d"+g[m.end(1):]
G.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("FIX2 modified frozen DNG/exposure/tap files "+repr(changed))

proof={
 "revision":"LEICATONING1A_FIX2_SOURCE1D",
 "rootCause":"Leica settings were wired to RAWSCALAR diagnostic path while portable primary JPEG is SOURCE1D_NATIVE_DNG_XYZ_Y",
 "portablePrimary":"SOURCE1D_NATIVE_DNG_XYZ_Y",
 "source1dUsesSelectedContrast":True,
 "source1dUsesSelectedToning":True,
 "source1dMissingCurveFallback":"validated_standard_curve02",
 "previewAndPrimarySettingsShared":True,
 "linearDngToneChanged":False,
 "linearDngToningChanged":False,
 "exposureChanged":False,
 "tapMeterChanged":False,
 "rawScalarDiagnosticPathRetained":True,
 "frozenPolicyHashes":after
}
(root/"LEICATONING1A_FIX2_SOURCE1D_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
