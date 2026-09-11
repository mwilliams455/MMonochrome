#!/usr/bin/env python3
from pathlib import Path


def once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"{label}: anchor count={n}, expected 1")
    return text.replace(old, new, 1)


p = Path("apk/mono1a/apply-mono1a.py")
t = p.read_text()

t = once(t, "import hashlib\nimport sys\n", "import hashlib\nimport re\nimport sys\n", "import re")
t = once(
    t,
    'gradle = root / "app/build.gradle"\nfor p in (renderer, native, cpp, gradle):\n',
    'gradle = root / "app/build.gradle"\nstrings = root / "app/src/main/res/values/strings.xml"\nfor p in (renderer, native, cpp, gradle, strings):\n',
    "strings path",
)

t = once(
    t,
    "                long[] monoStats = new long[8];\n",
    "                long[] monoStats = new long[16];\n",
    "mono stats length",
)

old_diag_tail = '''                d.put("nativeMonoRenderNs", monoStats[6]);
                d.put("nativePedestal14Echo", monoStats[7]);
                return new RenderCore(monoBitmap, d);
'''
new_diag_tail = '''                d.put("nativeMonoRenderNs", monoStats[6]);
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
'''
t = once(t, old_diag_tail, new_diag_tail, "SOURCE1A diagnostic tail")

marker = 'r = replace_once(r, needle, insert + needle, "mono early render")\nrenderer.write_text(r)\n'
extra = '''r = replace_once(r, needle, insert + needle, "mono early render")

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

# Capture-time queued snapshots are frozen before the background worker; make their
# identity truthful even though the surrounding capture framework retains M9 class names.
r = replace_once(
    r,
    '            d.put("developmentDngPersistence", "bounded_async_single_worker_after_jpeg_with_sync_fallback");\n',
    '            d.put("developmentDngPersistence", "bounded_async_single_worker_after_jpeg_with_sync_fallback");\n'
    '            if (MONO1A_ENABLED) {\n'
    '                d.put("schema", "mmonochrome.mono1a.queued.source1a.v1");\n'
    '                d.put("reference", "MONO1A_SOURCE1A queued capture snapshot");\n'
    '                d.put("pipeline", "physical Camera2 LensShadingMap -> MHC live-neutral -> M9Y control -> Leica14 mode0 -> Monochrom curve02");\n'
    '                d.put("resolutionMode", "MONO1A_SOURCE1A");\n'
    '                d.put("tc20Applied", false);\n'
    '                d.put("hsmApplied", false);\n'
    '                d.put("sat3Applied", false);\n'
    '                d.put("m9ColorPipelineApplied", false);\n'
    '                d.put("hdrApplied", false);\n'
    '            }\n',
    "SOURCE1A queued diagnostics",
)
renderer.write_text(r)
'''
t = once(t, marker, extra, "renderer SOURCE1A insert")

# Exact full-frame source LUT-index quantiles from the same native pixel pass.
t = once(
    t,
    "            || env->GetArrayLength(statsArray) < 8) {\n",
    "            || env->GetArrayLength(statsArray) < 16) {\n",
    "native stats validation",
)
t = once(
    t,
    "    std::vector<std::array<int64_t, 3>> local(static_cast<size_t>(workerCount));\n    std::vector<int64_t> workerNs(static_cast<size_t>(workerCount), 0);\n",
    "    std::vector<std::array<int64_t, 3>> local(static_cast<size_t>(workerCount));\n    std::vector<std::array<uint64_t, 2048>> localIndexHist(static_cast<size_t>(workerCount));\n    std::vector<int64_t> workerNs(static_cast<size_t>(workerCount), 0);\n",
    "native index histogram storage",
)
t = once(
    t,
    "            int64_t low = 0, high = 0, nearWhite = 0;\n            for (int y = y0; y < y1; ++y) {\n",
    "            int64_t low = 0, high = 0, nearWhite = 0;\n            auto& indexHist = localIndexHist[static_cast<size_t>(worker)];\n            indexHist.fill(0);\n            for (int y = y0; y < y1; ++y) {\n",
    "native per-worker histogram",
)
t = once(
    t,
    "                    if (idx > 2047) { idx = 2047; ++high; }\n                    const uint8_t yy = MM_MONO1A_CURVE02[idx];\n",
    "                    if (idx > 2047) { idx = 2047; ++high; }\n                    ++indexHist[static_cast<size_t>(idx)];\n                    const uint8_t yy = MM_MONO1A_CURVE02[idx];\n",
    "native histogram count",
)
old_aggregate = '''    int64_t low = 0, high = 0, nearWhite = 0, workerSum = 0;
    for (int i = 0; i < workerCount; ++i) {
        low += local[static_cast<size_t>(i)][0];
        high += local[static_cast<size_t>(i)][1];
        nearWhite += local[static_cast<size_t>(i)][2];
        workerSum += workerNs[static_cast<size_t>(i)];
    }
'''
new_aggregate = '''    int64_t low = 0, high = 0, nearWhite = 0, workerSum = 0;
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
'''
t = once(t, old_aggregate, new_aggregate, "native histogram aggregate")

old_stats = '''    const jlong stats[8] = {
        static_cast<jlong>(pixelCount), static_cast<jlong>(low), static_cast<jlong>(high),
        static_cast<jlong>(nearWhite), static_cast<jlong>(workerSum), static_cast<jlong>(workerCount),
        static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                nativeEnded - nativeStarted).count()), static_cast<jlong>(pedestal14)
    };
    env->SetLongArrayRegion(statsArray, 0, 8, stats);
'''
new_stats = '''    const jlong stats[16] = {
        static_cast<jlong>(pixelCount), static_cast<jlong>(low), static_cast<jlong>(high),
        static_cast<jlong>(nearWhite), static_cast<jlong>(workerSum), static_cast<jlong>(workerCount),
        static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                nativeEnded - nativeStarted).count()), static_cast<jlong>(pedestal14),
        static_cast<jlong>(q50), static_cast<jlong>(q90), static_cast<jlong>(q95), static_cast<jlong>(q99),
        static_cast<jlong>(MM_MONO1A_CURVE02[q50]), static_cast<jlong>(MM_MONO1A_CURVE02[q90]),
        static_cast<jlong>(MM_MONO1A_CURVE02[q95]), static_cast<jlong>(MM_MONO1A_CURVE02[q99])
    };
    env->SetLongArrayRegion(statsArray, 0, 16, stats);
'''
t = once(t, old_stats, new_stats, "native SOURCE1A stats output")

t = once(
    t,
    "versionName '0.01-mmonochrome-mono1a-native'",
    "versionName '0.02-mmonochrome-source1a'",
    "version name",
)
t = once(
    t,
    'outputFileName = "MMonochrome-MONO1A-${versionBuild}-${variant.name}.apk"',
    'outputFileName = "MMonochrome-SOURCE1A-${versionBuild}-${variant.name}.apk"',
    "apk name",
)

t = once(
    t,
    'gradle.write_text(g)\nprint("MONO1A overlay applied")\n',
    '''gradle.write_text(g)

s = strings.read_text()
s, app_name_count = re.subn(
    r'(<string\s+name="app_name"[^>]*>).*?(</string>)',
    r'\1M Monochrom Camera\2', s, count=1)
if app_name_count != 1:
    raise SystemExit(f"app_name anchors={app_name_count}")
strings.write_text(s)
print("MONO1A SOURCE1A overlay applied")
''',
    "app label patch",
)

p.write_text(t)

wf = Path(".github/workflows/build-mono1a-native.yml")
w = wf.read_text()
w = once(
    w,
    "grep -n \"versionName '0.01-mmonochrome-mono1a-native'\" \"$G\"",
    "grep -n \"versionName '0.02-mmonochrome-source1a'\" \"$G\"",
    "workflow version verifier",
)
w = once(
    w,
    "grep -n 'MMonochrome-MONO1A-' \"$G\"",
    "grep -n 'MMonochrome-SOURCE1A-' \"$G\"\n          grep -n 'MONO1A_SOURCE1A' \"$R\"\n          grep -n 'norm030ProductionApplied.*false' \"$R\"\n          grep -n 'M Monochrom Camera' \"$ROOT/app/src/main/res/values/strings.xml\"",
    "workflow SOURCE1A verifier",
)
w = w.replace("name: MMonochrome-MONO1A-NATIVE", "name: MMonochrome-SOURCE1A-NATIVE")
wf.write_text(w)

print("SOURCE1A promotion patch applied")
