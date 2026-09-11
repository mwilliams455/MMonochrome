#!/usr/bin/env python3
from pathlib import Path
import hashlib
import re
import sys

CURVE02_HEX = "0000010202030405050607080809090a0b0b0c0c0d0e0e0f0f10101111121213131414151516161717181819191a1a1b1b1c1c1d1d1d1e1e1f1f202021212222222323242425252626262727282829292a2a2a2b2b2c2c2d2d2d2e2e2f2f3030303131323232333334343535353636373738383839393a3a3a3b3b3c3c3d3d3d3e3e3f3f3f4040414142424243434444444545464646474748484849494a4a4b4b4b4c4c4d4d4d4e4e4f4f4f505051515152525353535454555555565657575758585959595a5a5b5b5b5c5c5c5d5d5d5e5e5f5f5f6060606161616262626363636464656565666666666767676868686969696a6a6a6b6b6b6c6c6c6d6d6d6d6e6e6e6f6f6f7070707071717172727273737373747474757575757676767677777778787878797979797a7a7a7b7b7b7b7c7c7c7c7d7d7d7d7e7e7e7e7f7f7f7f808080808181818182828282838383838484848484858585858686868687878787878888888889898989898a8a8a8a8b8b8b8b8b8c8c8c8c8c8d8d8d8d8e8e8e8e8e8f8f8f8f8f909090909091919191919292929292939393939394949494949595959595969696969697979797979798989898989999999999999a9a9a9a9a9b9b9b9b9b9b9c9c9c9c9c9d9d9d9d9d9d9e9e9e9e9e9e9f9f9f9f9f9fa0a0a0a0a0a0a1a1a1a1a1a1a2a2a2a2a2a2a3a3a3a3a3a3a4a4a4a4a4a4a5a5a5a5a5a5a5a6a6a6a6a6a6a7a7a7a7a7a7a7a8a8a8a8a8a8a9a9a9a9a9a9a9aaaaaaaaaaaaaaabababababababacacacacacacacadadadadadadadaeaeaeaeaeaeaeafafafafafafafb0b0b0b0b0b0b0b0b1b1b1b1b1b1b1b2b2b2b2b2b2b2b2b3b3b3b3b3b3b3b4b4b4b4b4b4b4b4b5b5b5b5b5b5b5b5b6b6b6b6b6b6b6b6b7b7b7b7b7b7b7b7b8b8b8b8b8b8b8b8b9b9b9b9b9b9b9b9b9bababababababababbbbbbbbbbbbbbbbbbbcbcbcbcbcbcbcbcbcbdbdbdbdbdbdbdbdbdbebebebebebebebebebfbfbfbfbfbfbfbfbfc0c0c0c0c0c0c0c0c0c1c1c1c1c1c1c1c1c1c1c2c2c2c2c2c2c2c2c2c3c3c3c3c3c3c3c3c3c3c4c4c4c4c4c4c4c4c4c4c5c5c5c5c5c5c5c5c5c5c6c6c6c6c6c6c6c6c6c6c7c7c7c7c7c7c7c7c7c7c7c8c8c8c8c8c8c8c8c8c8c9c9c9c9c9c9c9c9c9c9c9cacacacacacacacacacacacbcbcbcbcbcbcbcbcbcbcbcccccccccccccccccccccccdcdcdcdcdcdcdcdcdcdcdcdcececececececececececececfcfcfcfcfcfcfcfcfcfcfcfd0d0d0d0d0d0d0d0d0d0d0d0d1d1d1d1d1d1d1d1d1d1d1d1d2d2d2d2d2d2d2d2d2d2d2d2d2d3d3d3d3d3d3d3d3d3d3d3d3d3d4d4d4d4d4d4d4d4d4d4d4d4d4d5d5d5d5d5d5d5d5d5d5d5d5d5d6d6d6d6d6d6d6d6d6d6d6d6d6d6d7d7d7d7d7d7d7d7d7d7d7d7d7d7d8d8d8d8d8d8d8d8d8d8d8d8d8d8d9d9d9d9d9d9d9d9d9d9d9d9d9d9dadadadadadadadadadadadadadadadbdbdbdbdbdbdbdbdbdbdbdbdbdbdbdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdcdddddddddddddddddddddddddddddddedededededededededededededededededfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfe0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e0e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e1e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e2e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e3e4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e4e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e5e6e6e6e6e6e6e6e6e6e6e6e6e6e6e6e6e6e6e6e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e7e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e8e9e9e9e9e9e9e9e9e9e9e9e9e9e9e9e9e9e9e9e9e9eaeaeaeaeaeaeaeaeaeaeaeaeaeaeaeaeaeaeaeaeaeaebebebebebebebebebebebebebebebebebebebebebebecececececececececececececececececececececececededededededededededededededededededededededededeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeefefefefefefefefefefefefefefefefefefefefefefefefefeff0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f0f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f1f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f2f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f3f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f4f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f5f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f6f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f7f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f8f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9f9fafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafafbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfbfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfcfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfdfefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefefeffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff"

CURVE02 = bytes.fromhex(CURVE02_HEX)
CURVE02_SHA256 = "7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752"
if len(CURVE02) != 2048:
    raise SystemExit(f"curve02 length={len(CURVE02)} expected=2048")
if hashlib.sha256(CURVE02).hexdigest() != CURVE02_SHA256:
    raise SystemExit("curve02 SHA-256 mismatch")

if len(sys.argv) != 2:
    raise SystemExit("usage: apply-mono1a.py <PhotonCamera-root>")
root = Path(sys.argv[1])
renderer = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
native = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java"
cpp = root / "app/src/main/cpp/m9color_jni.cpp"
gradle = root / "app/build.gradle"
strings = root / "app/src/main/res/values/strings.xml"
for p in (renderer, native, cpp, gradle, strings):
    if not p.exists():
        raise SystemExit(f"missing expected file: {p}")

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label} anchor count={n} expected=1")
    return text.replace(old, new, 1)

r = renderer.read_text()
r = replace_once(
    r,
    "    public static final int JPEG_QUALITY = 95;\n",
    "    public static final int JPEG_QUALITY = 95;\n"
    "    // MONO1A: controlled M Monochrom 1.022 native-resolution renderer gate.\n"
    "    private static final boolean MONO1A_ENABLED = true;\n"
    "    private static final int MONO1A_SYNTHETIC_PEDESTAL14 = 0;\n",
    "renderer constants",
)

r = replace_once(
    r,
    '            String edgeSelector = edgeDecision.optString("selector", "HOLD");\n',
    '            if (MONO1A_ENABLED) {\n'
    '                edgeDecision.put("selectorBeforeMono1AOverride", edgeDecision.optString("selector", "HOLD"));\n'
    '                edgeDecision.put("selector", "HOLD");\n'
    '                edgeDecision.put("reason", "MONO1A_firmware_tone_path_no_M9_edge_placement");\n'
    '            }\n'
    '            String edgeSelector = MONO1A_ENABLED ? "HOLD" : edgeDecision.optString("selector", "HOLD");\n',
    "edge placement",
)

needle = (
    "        // DEMOSAICAB1A encoded mode 54 is diagnostic-only. It is consumed before\n"
    "        // bridge decoding and never changes production mode 0/3 arithmetic.\n"
)
insert = (
    "        // MONO1A uses only the physical Camera2 LensShadingMap upstream. M9-specific\n"
    "        // NORM030/decomposition/guard policy is deliberately bypassed.\n"
    "        if (MONO1A_ENABLED) {\n"
    "            applyShadingLumaDecomp1A = false;\n"
    "            normalizeShadingLumaOutsideMedian1A = false;\n"
    "            applyShadedGuard1A = false;\n"
    "            applyShadedGuardCap20Ev1A = false;\n"
    "        }\n\n"
)
r = replace_once(r, needle, insert + needle, "mono shading policy")

needle = (
    "            long colorContextStartedNs = System.nanoTime();\n"
    "            // The mixed calibration asset is loaded only to retain Leica firmware curve02.\n"
)
insert = """            if (MONO1A_ENABLED) {
                final int rotation = ((cameraRotation % 360) + 360) % 360;
                final int outW = (rotation == 90 || rotation == 270) ? height : width;
                final int outH = (rotation == 90 || rotation == 270) ? width : height;
                Bitmap monoBitmap = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888);
                long[] monoStats = new long[16];
                boolean monoOk = M9NativeColorCore.renderMonochrome1ADirectBitmap(
                        cam16.dataAddr(), pixels, width, height, monoBitmap,
                        cameraRotation, NATIVE_COLOR_WORKERS,
                        MONO1A_SYNTHETIC_PEDESTAL14, monoStats);
                if (!monoOk) {
                    if (!monoBitmap.isRecycled()) monoBitmap.recycle();
                    throw new IllegalStateException("MONO1A native direct Bitmap render failed");
                }
                JSONObject d = new JSONObject();
                d.put("schema", "mmonochrome.mono1a.native.v1");
                d.put("renderer", "MONO1A");
                d.put("target", "Leica M Monochrom 1.022");
                d.put("nativeResolution", true);
                d.put("contrastMode", 0);
                d.put("curve", "firmware_curve02_normalISO_sRGB_Standard");
                d.put("curve02Sha256", "7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752");
                d.put("leicaSignalDomain", "uint14_0_16383_in_uint16_storage");
                d.put("syntheticPedestal14", MONO1A_SYNTHETIC_PEDESTAL14);
                d.put("pedestalPolicy", "Xiaomi_black_subtracted_source_adapter_zero_not_native_Leica_value");
                d.put("sourceAdapter", "DEMOSAICMHCNEUTRAL1A_M9Y_CONTROL1A");
                d.put("sourceAdapterStatus", "provisional_Bayer_to_monochrome_only");
                d.put("sourceLuma", "(4899*R+9617*G+1868*B)>>>14_then>>>2_to_Leica14");
                d.put("sourceLumaProvenance", "M9_Q14_luma_control_not_Monochrom_sensor_spectral_truth");
                d.put("physicalLensShadingMapApplied", nativeShading.applied);
                d.put("m9ColorPipelineApplied", false);
                d.put("tc20Applied", false);
                d.put("hsmApplied", false);
                d.put("sat3Applied", false);
                d.put("m9EdgePlacementApplied", false);
                d.put("hdrApplied", false);
                d.put("jpegQuality", JPEG_QUALITY);
                d.put("demosaicFoundation", "DEMOSAICMHCNEUTRAL1A_FROZEN1A");
                d.put("nativePixelCount", monoStats[0]);
                d.put("lutLowClampCount", monoStats[1]);
                d.put("lutHighIndexCount", monoStats[2]);
                d.put("nearWhiteOutputCount", monoStats[3]);
                d.put("nativeWorkerNsSum", monoStats[4]);
                d.put("nativeWorkersUsed", monoStats[5]);
                d.put("nativeMonoRenderNs", monoStats[6]);
                d.put("nativePedestal14Echo", monoStats[7]);
                d.put("source1Revision", "MONO1A_SOURCE1A");
                d.put("sourceStage", "physical_Camera2_gainmap_then_MHC_live_neutral_then_M9Y_control_then_Leica14");
                d.put("sourceCalibrationNativeTransformApplied", false);
                d.put("sourceCalibrationRole", "not_in_MONO1A_pixel_path_capture_audit_only");
                d.put("norm030ProductionApplied", false);
                d.put("norm030LumaNormalizationApplied", false);
                d.put("shadingLumaDecompositionApplied", false);
                d.put("shadedGuardApplied", false);
                d.put("physicalShadingPolicy", "full_Camera2_LensShadingMap_no_M9_luma_decomposition");
                d.put("sourceIndexQ50", monoStats[8]);
                d.put("sourceIndexQ90", monoStats[9]);
                d.put("sourceIndexQ95", monoStats[10]);
                d.put("sourceIndexQ99", monoStats[11]);
                d.put("curveOutputAtSourceQ50", monoStats[12]);
                d.put("curveOutputAtSourceQ90", monoStats[13]);
                d.put("curveOutputAtSourceQ95", monoStats[14]);
                d.put("curveOutputAtSourceQ99", monoStats[15]);
                return new RenderCore(monoBitmap, d);
            }

"""
r = replace_once(r, needle, insert + needle, "mono early render")

# SOURCE1A: remove inherited M9 claims from the final primary sidecar. These fields
# are outside the early MONO renderer and otherwise overwrite truthful MONO diagnostics.
r = replace_once(
    r,
    """            diag.put("sourceCalibrationNativeTransformApplied", true);
            diag.put("rawShadingGainMapApplied", true);
            diag.put("rawShadingPhase", "production_NORM030_linear_Bayer_pre_demosaic");
""",
    """            diag.put("sourceCalibrationNativeTransformApplied", false);
            diag.put("sourceCalibrationAuditRole", "capture_metadata_audit_only_not_MONO1A_pixel_path");
            diag.put("rawShadingGainMapApplied", diag.optBoolean("physicalLensShadingMapApplied", false));
            diag.put("rawShadingPhase", "physical_Camera2_LensShadingMap_linear_Bayer_pre_demosaic_no_NORM030_luma_normalization");
""",
    "SOURCE1A final sidecar truth",
)

r = replace_once(
    r,
    """        d.put("schema", "m9cam.renderer.basishsm.v1p.nativesource1a.production");
        d.put("nativeSourceProduction1A", true);
        d.put("nativeSourceTransformApplied", true);
        d.put("sourceAdapterProvider", "Xiaomi_Camera2_DNG_SOURCECAL2A_CMFIX");
        d.put("sourceTransformFamily", "SOURCECAL2A_CMFIX_DNG_dual_illuminant_math_CM_unchanged_FM_D50_normalized_live_neutral");
        d.put("cobaltSourceAdapterApplied", false);
        d.put("cobaltSourceColorMatrixApplied", false);
        d.put("cobaltSourceForwardMatrixApplied", false);
        d.put("cobaltSourceHsmRoleApplied", false);
        d.put("historicalBasisHsmTargetBehaviorApplied", true);
        d.put("historicalBasisHsmRole", "frozen_BASISHSM1A_target_behavior_not_source_transform");
        d.put("historicalBasisDataProvenance", "legacy_profile_role_reconstruction_retained_only_after_native_scene_transform");
        d.put("m9FirmwareCurve02Retained", true);
        d.put("norm030ProductionApplied", true);
        d.put("norm030TargetOutsideMedianEv", 0.30);
        d.put("norm030UsesSceneBrightness", false);
        d.put("norm030UsesFinalClipFeedback", false);
        d.put("norm030UsesPrimaryFeedback", false);
        d.put("productionSelfMeter", true);
        d.put("fixedPrimaryGainReferenceRole", "diagnostic_placeholder_only_not_render_gain_when_selfMeter_true");
        d.remove("meterParityGainRatioVsPrimary");
        d.remove("meterParityGainDeltaEvVsPrimary");
        d.put("pipeline", "NORM030 physical LensShadingMap -> DEMOSAICMHCNEUTRAL1A live-neutral balanced 5x5 MHC -> native Xiaomi SOURCECAL2A -> BASISHSM1A historical working-basis/H25 target role -> M9 bridge -> TC20 -> SAT3 M06/M07 -> curve02 -> exact BT601 4:2:2 -> M9Modern TG1");
""",
    """        d.put("schema", "mmonochrome.mono1a.source1a.v1");
        d.put("source1Revision", "MONO1A_SOURCE1A");
        d.put("nativeSourceProduction1A", false);
        d.put("nativeSourceTransformApplied", false);
        d.put("sourceAdapterProvider", "Xiaomi_Camera2_physical_gainmap_plus_MHC_live_neutral");
        d.put("sourceTransformFamily", "provisional_Bayer_to_monochrome_M9Y_control");
        d.put("cobaltSourceAdapterApplied", false);
        d.put("cobaltSourceColorMatrixApplied", false);
        d.put("cobaltSourceForwardMatrixApplied", false);
        d.put("cobaltSourceHsmRoleApplied", false);
        d.put("historicalBasisHsmTargetBehaviorApplied", false);
        d.put("historicalBasisHsmRole", "not_in_MONO1A_pixel_path");
        d.put("historicalBasisDataProvenance", "not_in_MONO1A_pixel_path");
        d.put("m9FirmwareCurve02Retained", false);
        d.put("monochromFirmwareCurve02Applied", true);
        d.put("norm030ProductionApplied", false);
        d.put("norm030TargetOutsideMedianEv", 0.0);
        d.put("norm030UsesSceneBrightness", false);
        d.put("norm030UsesFinalClipFeedback", false);
        d.put("norm030UsesPrimaryFeedback", false);
        d.put("productionSelfMeter", false);
        d.put("fixedPrimaryGainReferenceRole", "not_used_MONO1A");
        d.remove("meterParityGainRatioVsPrimary");
        d.remove("meterParityGainDeltaEvVsPrimary");
        d.put("pipeline", "black_white_normalize -> physical Camera2 LensShadingMap -> DEMOSAICMHCNEUTRAL1A -> provisional M9Y scalar -> Leica14 mode0 -> M Monochrom 1.022 curve02");
""",
    "SOURCE1A production wrapper truth",
)

renderer.write_text(r)

n = native.read_text()
anchor = """    static native boolean renderBlockParallelDirectBitmap(long handle,
                                                          long camAddress,
                                                          int pixelCount,
                                                          int width,
                                                          android.graphics.Bitmap bitmap,
                                                          int blockY0,
                                                          int sourceHeight,
                                                          double gain,
                                                          double tgCbGain,
                                                          double tgCrGain,
                                                          int cameraRotation,
                                                          int workers,
                                                          long[] stats);
"""
addition = anchor + """
    /** MONO1A: provisional Xiaomi source luminance + firmware-exact Monochrom mode-0 curve02. */
    static native boolean renderMonochrome1ADirectBitmap(long camAddress,
                                                         int pixelCount,
                                                         int width,
                                                         int sourceHeight,
                                                         android.graphics.Bitmap bitmap,
                                                         int cameraRotation,
                                                         int workers,
                                                         int pedestal14,
                                                         long[] stats);
"""
n = replace_once(n, anchor, addition, "native declaration")
native.write_text(n)

c = cpp.read_text()
if "MM_MONO1A_CURVE02" in c:
    raise SystemExit("MONO1A C++ already present")
curve_bytes = bytes.fromhex(CURVE02_HEX)
if len(curve_bytes) != 2048:
    raise SystemExit(f"curve02 length={len(curve_bytes)}")
curve_values = ",".join(str(x) for x in curve_bytes)
append = r'''

// MONO1A — firmware-derived M Monochrom 1.022 normal-ISO/sRGB/Standard curve02.
// The Bayer->monochrome luma above this curve is explicitly a provisional Xiaomi
// source adapter. Leica mode-0 itself is exact: max(sample14-P,0) >>> 3.
static constexpr uint8_t MM_MONO1A_CURVE02[2048] = {__CURVE_VALUES__};

extern "C" JNIEXPORT jboolean JNICALL
Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1ADirectBitmap(
        JNIEnv* env, jclass,
        jlong camAddress,
        jint pixelCount,
        jint width,
        jint sourceHeight,
        jobject bitmap,
        jint cameraRotation,
        jint workers,
        jint pedestal14,
        jlongArray statsArray) {
    const auto* cam = reinterpret_cast<const jshort*>(static_cast<uintptr_t>(camAddress));
    if (!cam || !bitmap || !statsArray || width <= 0 || sourceHeight <= 0
            || pixelCount != width * sourceHeight || workers <= 0
            || pedestal14 < 0 || pedestal14 > 16383
            || env->GetArrayLength(statsArray) < 16) {
        throwIllegalArgument(env, "Invalid MONO1A direct Bitmap arguments");
        return JNI_FALSE;
    }
    int rotation = cameraRotation % 360;
    if (rotation < 0) rotation += 360;
    const uint32_t expectedWidth = static_cast<uint32_t>(
            (rotation == 90 || rotation == 270) ? sourceHeight : width);
    const uint32_t expectedHeight = static_cast<uint32_t>(
            (rotation == 90 || rotation == 270) ? width : sourceHeight);
    AndroidBitmapInfo info{};
    if (AndroidBitmap_getInfo(env, bitmap, &info) != ANDROID_BITMAP_RESULT_SUCCESS
            || info.format != ANDROID_BITMAP_FORMAT_RGBA_8888
            || info.width != expectedWidth || info.height != expectedHeight
            || info.stride < expectedWidth * 4u) return JNI_FALSE;
    void* rawPixels = nullptr;
    if (AndroidBitmap_lockPixels(env, bitmap, &rawPixels) != ANDROID_BITMAP_RESULT_SUCCESS
            || rawPixels == nullptr) return JNI_FALSE;

    const auto nativeStarted = std::chrono::steady_clock::now();
    std::vector<jint> argb(static_cast<size_t>(pixelCount));
    const int workerCount = std::max(1, std::min(static_cast<int>(workers), sourceHeight));
    std::vector<std::thread> threads;
    threads.reserve(static_cast<size_t>(workerCount));
    std::vector<std::array<int64_t, 3>> local(static_cast<size_t>(workerCount));
    std::vector<std::array<uint64_t, 2048>> localIndexHist(static_cast<size_t>(workerCount));
    std::vector<int64_t> workerNs(static_cast<size_t>(workerCount), 0);
    auto* bitmapBase = static_cast<uint8_t*>(rawPixels);
    for (int worker = 0; worker < workerCount; ++worker) {
        const int y0 = (sourceHeight * worker) / workerCount;
        const int y1 = (sourceHeight * (worker + 1)) / workerCount;
        threads.emplace_back([&, worker, y0, y1]() {
            const auto ws = std::chrono::steady_clock::now();
            int64_t low = 0, high = 0, nearWhite = 0;
            auto& indexHist = localIndexHist[static_cast<size_t>(worker)];
            indexHist.fill(0);
            for (int y = y0; y < y1; ++y) {
                const size_t row = static_cast<size_t>(y) * static_cast<size_t>(width);
                for (int x = 0; x < width; ++x) {
                    const size_t p = row + static_cast<size_t>(x);
                    const size_t ci = p * 3u;
                    const uint32_t r = u16(cam[ci]);
                    const uint32_t g = u16(cam[ci + 1]);
                    const uint32_t b = u16(cam[ci + 2]);
                    const uint32_t y16 = static_cast<uint32_t>(
                            (4899ull * r + 9617ull * g + 1868ull * b) >> 14);
                    const int32_t sample14 = static_cast<int32_t>(
                            std::min<uint32_t>(16383u, y16 >> 2));
                    int32_t v = sample14 - static_cast<int32_t>(pedestal14);
                    if (v < 0) { v = 0; ++low; }
                    int32_t idx = v >> 3;
                    if (idx > 2047) { idx = 2047; ++high; }
                    ++indexHist[static_cast<size_t>(idx)];
                    const uint8_t yy = MM_MONO1A_CURVE02[idx];
                    if (yy >= 250) ++nearWhite;
                    argb[p] = static_cast<jint>(0xff000000u
                            | (static_cast<uint32_t>(yy) << 16)
                            | (static_cast<uint32_t>(yy) << 8)
                            | static_cast<uint32_t>(yy));
                }
            }
            writeCompletedSubrangeToBitmap(argb.data(), bitmapBase, info.stride,
                    sourceHeight, width, 0, sourceHeight, y0, y1, cameraRotation);
            local[static_cast<size_t>(worker)] = {low, high, nearWhite};
            workerNs[static_cast<size_t>(worker)] =
                    std::chrono::duration_cast<std::chrono::nanoseconds>(
                            std::chrono::steady_clock::now() - ws).count();
        });
    }
    for (auto& t : threads) t.join();
    int64_t low = 0, high = 0, nearWhite = 0, workerSum = 0;
    std::array<uint64_t, 2048> indexHist{};
    for (int i = 0; i < workerCount; ++i) {
        low += local[static_cast<size_t>(i)][0];
        high += local[static_cast<size_t>(i)][1];
        nearWhite += local[static_cast<size_t>(i)][2];
        workerSum += workerNs[static_cast<size_t>(i)];
        const auto& srcHist = localIndexHist[static_cast<size_t>(i)];
        for (size_t j = 0; j < indexHist.size(); ++j) indexHist[j] += srcHist[j];
    }
    auto quantileIndex = [&](uint64_t numerator, uint64_t denominator) -> int64_t {
        const uint64_t target = std::max<uint64_t>(1u,
                (static_cast<uint64_t>(pixelCount) * numerator + denominator - 1u) / denominator);
        uint64_t cumulative = 0;
        for (size_t j = 0; j < indexHist.size(); ++j) {
            cumulative += indexHist[j];
            if (cumulative >= target) return static_cast<int64_t>(j);
        }
        return 2047;
    };
    const int64_t q50 = quantileIndex(50, 100);
    const int64_t q90 = quantileIndex(90, 100);
    const int64_t q95 = quantileIndex(95, 100);
    const int64_t q99 = quantileIndex(99, 100);
    const int unlockResult = AndroidBitmap_unlockPixels(env, bitmap);
    const auto nativeEnded = std::chrono::steady_clock::now();
    if (unlockResult != ANDROID_BITMAP_RESULT_SUCCESS) return JNI_FALSE;
    const jlong stats[16] = {
        static_cast<jlong>(pixelCount), static_cast<jlong>(low), static_cast<jlong>(high),
        static_cast<jlong>(nearWhite), static_cast<jlong>(workerSum), static_cast<jlong>(workerCount),
        static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                nativeEnded - nativeStarted).count()), static_cast<jlong>(pedestal14),
        static_cast<jlong>(q50), static_cast<jlong>(q90), static_cast<jlong>(q95), static_cast<jlong>(q99),
        static_cast<jlong>(MM_MONO1A_CURVE02[q50]), static_cast<jlong>(MM_MONO1A_CURVE02[q90]),
        static_cast<jlong>(MM_MONO1A_CURVE02[q95]), static_cast<jlong>(MM_MONO1A_CURVE02[q99])
    };
    env->SetLongArrayRegion(statsArray, 0, 16, stats);
    return env->ExceptionCheck() ? JNI_FALSE : JNI_TRUE;
}
'''.replace("__CURVE_VALUES__", curve_values)
c += append
cpp.write_text(c)

g = gradle.read_text()
g = replace_once(g,
    "applicationId 'com.m9project.m9cam.photon'",
    "applicationId 'com.m9project.mmonochrome.photon'",
    "application id")
version_lines = [line for line in g.splitlines() if line.strip().startswith("versionName '")]
if len(version_lines) != 1:
    raise SystemExit(f"versionName anchors={len(version_lines)}")
g = g.replace(version_lines[0], "        versionName '0.01-mmonochrome-mono1a-native'", 1)
g = replace_once(g,
    'outputFileName = "M9Cam-NAB1-${versionBuild}-${variant.name}.apk"',
    'outputFileName = "MMonochrome-MONO1A-${versionBuild}-${variant.name}.apk"',
    "apk output name")
gradle.write_text(g)

s = strings.read_text()
s, app_name_count = re.subn(
    r'(<string\s+name="app_name"[^>]*>).*?(</string>)',
    r'M Monochrom Camera', s, count=1)
if app_name_count != 1:
    raise SystemExit(f"app_name anchors={app_name_count}")
strings.write_text(s)
print("MONO1A SOURCE1A overlay applied")
