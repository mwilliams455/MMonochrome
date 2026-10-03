#!/usr/bin/env python3
"""Apply LEICATONING1A_FIX1: verified contrast-bank cache + nonfatal Standard fallback."""
from pathlib import Path
import json, re, sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
meta=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/MonoContrastCurves1A.java"
renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
native_cpp=root/"app/src/main/cpp/m9color_jni.cpp"
main_renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java"
gradle=root/"app/build.gradle"
for p in [meta,renderer,native_cpp,main_renderer,gradle]:
    if not p.is_file(): raise SystemExit("FIX1 missing "+str(p))

def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"FIX1 {label} anchor count={n}")
    return s.replace(a,b,1)

# 1. Make the bank cache installable by the already-successful preview path.
s=meta.read_text()
s=one(s,
"""    private static volatile byte[] bank;

    private MonoContrastCurves1A() {}
""",
"""    private static volatile byte[] bank;
    private static volatile String lastLoadError="";

    private MonoContrastCurves1A() {}
""","meta state")

s=one(s,
"""    private static String sha256(byte[] data) throws Exception {
        byte[] hash = MessageDigest.getInstance("SHA-256").digest(data);
        StringBuilder out = new StringBuilder();
        for (byte b : hash) out.append(String.format(Locale.ROOT, "%02x", b & 255));
        return out.toString();
    }

    public static byte[] loadBank() {
""",
"""    private static String sha256(byte[] data) throws Exception {
        byte[] hash = MessageDigest.getInstance("SHA-256").digest(data);
        StringBuilder out = new StringBuilder();
        for (byte b : hash) out.append(String.format(Locale.ROOT, "%02x", b & 255));
        return out.toString();
    }

    private static void verifyBank(byte[] data) throws Exception {
        if (data == null || data.length != CURVE_COUNT * CURVE_SIZE)
            throw new IllegalStateException("Leica Contrast bank length");
        if (!BANK_SHA256.equals(sha256(data)))
            throw new IllegalStateException("Leica Contrast bank checksum");
        for (int i = 0; i < CURVE_COUNT; i++) {
            byte[] curve = Arrays.copyOfRange(data, i * CURVE_SIZE, (i + 1) * CURVE_SIZE);
            if (!SHA256[i].equals(sha256(curve)))
                throw new IllegalStateException("Leica Contrast curve checksum " + i);
        }
    }

    /** Installs a bank already loaded and verified by the live-preview Activity context. */
    public static boolean installVerifiedBank(byte[] data) {
        try {
            verifyBank(data);
            bank = Arrays.copyOf(data, data.length);
            lastLoadError="";
            return true;
        } catch (Throwable t) {
            lastLoadError=t.toString();
            return false;
        }
    }

    public static String lastLoadError() { return lastLoadError; }

    public static byte[] tryLoadBank() {
        byte[] cached=bank;
        if (cached!=null) return cached;
        synchronized (MonoContrastCurves1A.class) {
            if (bank!=null) return bank;
            try (InputStream in = PhotonCamera.getAppContext().getAssets().open(ASSET)) {
                byte[] data = new byte[CURVE_COUNT * CURVE_SIZE];
                int offset = 0, n;
                while(offset<data.length && (n=in.read(data,offset,data.length-offset))>0) offset+=n;
                if(offset!=data.length || in.read()!=-1) throw new IllegalStateException("Leica Contrast bank length");
                verifyBank(data);
                bank=data;
                lastLoadError="";
                return bank;
            } catch(Throwable t) {
                lastLoadError=t.toString();
                return null;
            }
        }
    }

    public static byte[] loadBank() {
""","meta install helpers")

old_load="""    public static byte[] loadBank() {
        byte[] cached = bank;
        if (cached != null) return cached;
        synchronized (MonoContrastCurves1A.class) {
            if (bank != null) return bank;
            try (InputStream in = PhotonCamera.getAppContext().getAssets().open(ASSET)) {
                byte[] data = new byte[CURVE_COUNT * CURVE_SIZE];
                int offset = 0, n;
                while (offset < data.length && (n = in.read(data, offset, data.length - offset)) > 0) offset += n;
                if (offset != data.length || in.read() != -1) throw new IllegalStateException("Leica Contrast bank length");
                if (!BANK_SHA256.equals(sha256(data))) throw new IllegalStateException("Leica Contrast bank checksum");
                for (int i = 0; i < CURVE_COUNT; i++) {
                    byte[] curve = Arrays.copyOfRange(data, i * CURVE_SIZE, (i + 1) * CURVE_SIZE);
                    if (!SHA256[i].equals(sha256(curve))) throw new IllegalStateException("Leica Contrast curve checksum " + i);
                }
                bank = data;
                return data;
            } catch (Throwable t) {
                throw new IllegalStateException("Leica Contrast firmware bank unavailable", t);
            }
        }
    }

    public static byte[] loadCurve(int selector) {
        int value = clamp(selector);
        byte[] data = loadBank();
        return Arrays.copyOfRange(data, value * CURVE_SIZE, (value + 1) * CURVE_SIZE);
    }
"""
new_load="""    public static byte[] loadBank() {
        byte[] data=tryLoadBank();
        if(data==null) throw new IllegalStateException("Leica Contrast firmware bank unavailable: "+lastLoadError);
        return data;
    }

    public static byte[] loadCurveOrNull(int selector) {
        int value=clamp(selector);
        byte[] data=tryLoadBank();
        return data==null ? null : Arrays.copyOfRange(data,value*CURVE_SIZE,(value+1)*CURVE_SIZE);
    }

    public static byte[] loadCurve(int selector) {
        byte[] curve=loadCurveOrNull(selector);
        if(curve==null) throw new IllegalStateException("Leica Contrast firmware bank unavailable: "+lastLoadError);
        return curve;
    }
"""
s=one(s,old_load,new_load,"meta nonfatal loader")
meta.write_text(s)

# 2. Preview is the proven successful asset reader; publish its exact bank to the shared cache.
s=main_renderer.read_text()
s=one(s,
"""            monoContrastBank1A=data;
            monoContrastSelector1A=-1;
""",
"""            monoContrastBank1A=data;
            if(!com.particlesdevs.photoncamera.m9.render.MonoContrastCurves1A.installVerifiedBank(data))
                throw new java.io.IOException("contrast_shared_cache_rejected");
            monoContrastSelector1A=-1;
""","preview cache publish")
main_renderer.write_text(s)

# 3. Still renderer never throws merely because the curve asset cannot be reopened.
s=renderer.read_text()
s=one(s,
"""        final byte[] monoStandardCurve1A = MonoContrastCurves1A.loadCurve(MonoContrastCurves1A.DEFAULT);
        final byte[] monoSelectedCurve1A = MonoContrastCurves1A.loadCurve(monoContrast1A);
""",
"""        final byte[] monoStandardCurve1A = MonoContrastCurves1A.loadCurveOrNull(MonoContrastCurves1A.DEFAULT);
        final byte[] monoSelectedCurve1A = MonoContrastCurves1A.loadCurveOrNull(monoContrast1A);
        final boolean monoContrastCurveFallback1A = monoSelectedCurve1A == null;
""","renderer nonfatal contrast load")

# Add telemetry wherever toning telemetry is already emitted.
s=one(s,
'                rawScalar1B.put("toningDomain", "firmware_PROCESS_LUTS_YCrCb_chroma_pair");\n',
'                rawScalar1B.put("toningDomain", "firmware_PROCESS_LUTS_YCrCb_chroma_pair");\n'
'                rawScalar1B.put("contrastCurveFallbackToStandard", monoContrastCurveFallback1A);\n'
'                rawScalar1B.put("contrastCurveRuntimeError", MonoContrastCurves1A.lastLoadError());\n',
"raw fallback telemetry")
s=one(s,
'                d.put("monochromToningCb", monoToningCb1A);\n',
'                d.put("monochromToningCb", monoToningCb1A);\n'
'                d.put("monochromContrastCurveFallbackToStandard", monoContrastCurveFallback1A);\n'
'                d.put("monochromContrastCurveRuntimeError", MonoContrastCurves1A.lastLoadError());\n',
"root fallback telemetry")
renderer.write_text(s)

# 4. JNI treats null/bad curve as Standard curve02, never as fatal capture failure.
s=native_cpp.read_text()
old="""    if (!contrastCurveArray || env->GetArrayLength(contrastCurveArray) != 2048) {
        AndroidBitmap_unlockPixels(env,bitmap);
        throwIllegalArgument(env, "MONO1A Contrast curve must be 2048 bytes");
        return JNI_FALSE;
    }
    std::array<jbyte,2048> contrastBytes{};
    env->GetByteArrayRegion(contrastCurveArray,0,2048,contrastBytes.data());
    if (env->ExceptionCheck()) { AndroidBitmap_unlockPixels(env,bitmap); return JNI_FALSE; }
    std::array<uint8_t,2048> contrastCurve{};
    for (size_t i=0;i<contrastCurve.size();++i) contrastCurve[i]=static_cast<uint8_t>(contrastBytes[i]);
"""
new="""    std::array<uint8_t,2048> contrastCurve{};
    if (contrastCurveArray && env->GetArrayLength(contrastCurveArray) == 2048) {
        std::array<jbyte,2048> contrastBytes{};
        env->GetByteArrayRegion(contrastCurveArray,0,2048,contrastBytes.data());
        if (env->ExceptionCheck()) { AndroidBitmap_unlockPixels(env,bitmap); return JNI_FALSE; }
        for (size_t i=0;i<contrastCurve.size();++i) contrastCurve[i]=static_cast<uint8_t>(contrastBytes[i]);
    } else {
        // FIX1: never lose a capture because the post-packed multi-curve bank could not be reopened.
        // Standard curve02 is already part of the validated Monochrom native baseline.
        for (size_t i=0;i<contrastCurve.size();++i) contrastCurve[i]=MM_MONO1A_CURVE02[i];
    }
"""
s=one(s,old,new,"native Standard fallback")
native_cpp.write_text(s)

# Identity.
s=gradle.read_text()
m=re.search(r"versionName\s+'([^']+)'",s)
if not m: raise SystemExit("FIX1 versionName missing")
if "fix1" not in m.group(1):
    s=s[:m.start(1)]+m.group(1)+"-fix1"+s[m.end(1):]
gradle.write_text(s)

proof={
 "revision":"LEICATONING1A_FIX1",
 "rootCause":"still_renderer_lazy_AssetManager_reopen_threw_after_preview_had_verified_same_bank",
 "previewInstallsVerifiedSharedBank":True,
 "stillUsesSharedCacheFirst":True,
 "stillAssetReopenNonfatal":True,
 "nativeMissingCurveFallback":"validated_standard_curve02",
 "captureMustNotFailForMissingContrastBank":True,
 "toningMathChanged":False,
 "dngPolicyChanged":False,
 "contrastExactWhenBankAvailable":True
}
(root/"LEICATONING1A_FIX1_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
