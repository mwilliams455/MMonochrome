#!/usr/bin/env python3
from pathlib import Path

p = Path('apk/mono1a/apply-mono1a.py')
t = p.read_text()


def replace_once(old, new, label):
    global t
    n = t.count(old)
    if n != 1:
        raise SystemExit(f'{label}: anchor count={n}, expected 1')
    t = t.replace(old, new, 1)


# Java-side stats array and truthful SOURCE1B telemetry. Rendering remains M9Y.
replace_once(
    '                long[] monoStats = new long[16];\n',
    '                long[] monoStats = new long[32];\n',
    'java stats length')

replace_once(
    '                d.put("curveOutputAtSourceQ99", monoStats[15]);\n'
    '                return new RenderCore(monoBitmap, d);\n',
    '                d.put("curveOutputAtSourceQ99", monoStats[15]);\n'
    '                JSONObject source1b = new JSONObject();\n'
    '                source1b.put("schema", "mmonochrome.source1b.controls.v1");\n'
    '                source1b.put("mode", "diagnostic_same_post_MHC_buffer_no_pixel_mutation");\n'
    '                source1b.put("renderedControl", "M9Y_Q14");\n'
    '                source1b.put("neutralScaleInvariant", "R_equals_G_equals_B_produces_same_source_coordinate_all_controls");\n'
    '                source1b.put("greenOnlyFormula", "G>>>2_to_Leica14_then_same_pedestal_and_curve02");\n'
    '                source1b.put("rgbMeanFormula", "((R+G+B)/3)>>>2_to_Leica14_then_same_pedestal_and_curve02");\n'
    '                source1b.put("greenOnlyIndexQ50", monoStats[16]);\n'
    '                source1b.put("greenOnlyIndexQ90", monoStats[17]);\n'
    '                source1b.put("greenOnlyIndexQ95", monoStats[18]);\n'
    '                source1b.put("greenOnlyIndexQ99", monoStats[19]);\n'
    '                source1b.put("greenOnlyCurveQ50", monoStats[20]);\n'
    '                source1b.put("greenOnlyCurveQ90", monoStats[21]);\n'
    '                source1b.put("greenOnlyCurveQ95", monoStats[22]);\n'
    '                source1b.put("greenOnlyCurveQ99", monoStats[23]);\n'
    '                source1b.put("rgbMeanIndexQ50", monoStats[24]);\n'
    '                source1b.put("rgbMeanIndexQ90", monoStats[25]);\n'
    '                source1b.put("rgbMeanIndexQ95", monoStats[26]);\n'
    '                source1b.put("rgbMeanIndexQ99", monoStats[27]);\n'
    '                source1b.put("rgbMeanCurveQ50", monoStats[28]);\n'
    '                source1b.put("rgbMeanCurveQ90", monoStats[29]);\n'
    '                source1b.put("rgbMeanCurveQ95", monoStats[30]);\n'
    '                source1b.put("rgbMeanCurveQ99", monoStats[31]);\n'
    '                d.put("source1bControls", source1b);\n'
    '                return new RenderCore(monoBitmap, d);\n',
    'java SOURCE1B telemetry')

if t.count('MONO1A_SOURCE1A') < 1:
    raise SystemExit('SOURCE1A revision anchors missing')
t = t.replace('MONO1A_SOURCE1A', 'MONO1A_SOURCE1B')
if t.count('mmonochrome.mono1a.source1a.v1') < 1:
    raise SystemExit('SOURCE1A schema anchors missing')
t = t.replace('mmonochrome.mono1a.source1a.v1', 'mmonochrome.mono1a.source1b.v1')

# Native stats capacity.
replace_once(
    '            || env->GetArrayLength(statsArray) < 16) {\n',
    '            || env->GetArrayLength(statsArray) < 32) {\n',
    'native stats validation')

# Per-worker control histograms. They share the exact post-MHC RGB buffer used by M9Y.
replace_once(
    '    std::vector<std::array<uint64_t, 2048>> localIndexHist(static_cast<size_t>(workerCount));\n'
    '    std::vector<int64_t> workerNs(static_cast<size_t>(workerCount), 0);\n',
    '    std::vector<std::array<uint64_t, 2048>> localIndexHist(static_cast<size_t>(workerCount));\n'
    '    std::vector<std::array<uint64_t, 2048>> localGreenHist(static_cast<size_t>(workerCount));\n'
    '    std::vector<std::array<uint64_t, 2048>> localMeanHist(static_cast<size_t>(workerCount));\n'
    '    std::vector<int64_t> workerNs(static_cast<size_t>(workerCount), 0);\n',
    'native worker hist vectors')

replace_once(
    '            auto& indexHist = localIndexHist[static_cast<size_t>(worker)];\n'
    '            for (size_t j = 0; j < indexHist.size(); ++j) indexHist[j] = 0;\n',
    '            auto& indexHist = localIndexHist[static_cast<size_t>(worker)];\n'
    '            auto& greenHist = localGreenHist[static_cast<size_t>(worker)];\n'
    '            auto& meanHist = localMeanHist[static_cast<size_t>(worker)];\n'
    '            for (size_t j = 0; j < indexHist.size(); ++j) {\n'
    '                indexHist[j] = 0;\n'
    '                greenHist[j] = 0;\n'
    '                meanHist[j] = 0;\n'
    '            }\n',
    'native worker hist init')

replace_once(
    '                    const int32_t sample14 = static_cast<int32_t>(\n'
    '                            std::min<uint32_t>(16383u, y16 >> 2));\n'
    '                    int32_t v = sample14 - static_cast<int32_t>(pedestal14);\n',
    '                    const int32_t sample14 = static_cast<int32_t>(\n'
    '                            std::min<uint32_t>(16383u, y16 >> 2));\n'
    '                    const int32_t green14 = static_cast<int32_t>(\n'
    '                            std::min<uint32_t>(16383u, g >> 2));\n'
    '                    const uint32_t mean16 = (r + g + b) / 3u;\n'
    '                    const int32_t mean14 = static_cast<int32_t>(\n'
    '                            std::min<uint32_t>(16383u, mean16 >> 2));\n'
    '                    int32_t greenV = green14 - static_cast<int32_t>(pedestal14);\n'
    '                    if (greenV < 0) greenV = 0;\n'
    '                    int32_t greenIdx = greenV >> 3;\n'
    '                    if (greenIdx > 2047) greenIdx = 2047;\n'
    '                    int32_t meanV = mean14 - static_cast<int32_t>(pedestal14);\n'
    '                    if (meanV < 0) meanV = 0;\n'
    '                    int32_t meanIdx = meanV >> 3;\n'
    '                    if (meanIdx > 2047) meanIdx = 2047;\n'
    '                    ++greenHist[static_cast<size_t>(greenIdx)];\n'
    '                    ++meanHist[static_cast<size_t>(meanIdx)];\n'
    '                    int32_t v = sample14 - static_cast<int32_t>(pedestal14);\n',
    'native alternative source formulas')

replace_once(
    '    std::array<uint64_t, 2048> indexHist{};\n'
    '    for (int i = 0; i < workerCount; ++i) {\n',
    '    std::array<uint64_t, 2048> indexHist{};\n'
    '    std::array<uint64_t, 2048> greenHist{};\n'
    '    std::array<uint64_t, 2048> meanHist{};\n'
    '    for (int i = 0; i < workerCount; ++i) {\n',
    'native merged hist declarations')

replace_once(
    '        const auto& srcHist = localIndexHist[static_cast<size_t>(i)];\n'
    '        for (size_t j = 0; j < indexHist.size(); ++j) indexHist[j] += srcHist[j];\n'
    '    }\n'
    '    auto quantileIndex = [&](uint64_t numerator, uint64_t denominator) -> int64_t {\n'
    '        const uint64_t target = std::max<uint64_t>(1u,\n'
    '                (static_cast<uint64_t>(pixelCount) * numerator + denominator - 1u) / denominator);\n'
    '        uint64_t cumulative = 0;\n'
    '        for (size_t j = 0; j < indexHist.size(); ++j) {\n'
    '            cumulative += indexHist[j];\n'
    '            if (cumulative >= target) return static_cast<int64_t>(j);\n'
    '        }\n'
    '        return 2047;\n'
    '    };\n'
    '    const int64_t q50 = quantileIndex(50, 100);\n'
    '    const int64_t q90 = quantileIndex(90, 100);\n'
    '    const int64_t q95 = quantileIndex(95, 100);\n'
    '    const int64_t q99 = quantileIndex(99, 100);\n',
    '        const auto& srcHist = localIndexHist[static_cast<size_t>(i)];\n'
    '        const auto& srcGreen = localGreenHist[static_cast<size_t>(i)];\n'
    '        const auto& srcMean = localMeanHist[static_cast<size_t>(i)];\n'
    '        for (size_t j = 0; j < indexHist.size(); ++j) {\n'
    '            indexHist[j] += srcHist[j];\n'
    '            greenHist[j] += srcGreen[j];\n'
    '            meanHist[j] += srcMean[j];\n'
    '        }\n'
    '    }\n'
    '    auto quantileIndex = [&](const std::array<uint64_t, 2048>& hist,\n'
    '                             uint64_t numerator, uint64_t denominator) -> int64_t {\n'
    '        const uint64_t target = std::max<uint64_t>(1u,\n'
    '                (static_cast<uint64_t>(pixelCount) * numerator + denominator - 1u) / denominator);\n'
    '        uint64_t cumulative = 0;\n'
    '        for (size_t j = 0; j < hist.size(); ++j) {\n'
    '            cumulative += hist[j];\n'
    '            if (cumulative >= target) return static_cast<int64_t>(j);\n'
    '        }\n'
    '        return 2047;\n'
    '    };\n'
    '    const int64_t q50 = quantileIndex(indexHist, 50, 100);\n'
    '    const int64_t q90 = quantileIndex(indexHist, 90, 100);\n'
    '    const int64_t q95 = quantileIndex(indexHist, 95, 100);\n'
    '    const int64_t q99 = quantileIndex(indexHist, 99, 100);\n'
    '    const int64_t gq50 = quantileIndex(greenHist, 50, 100);\n'
    '    const int64_t gq90 = quantileIndex(greenHist, 90, 100);\n'
    '    const int64_t gq95 = quantileIndex(greenHist, 95, 100);\n'
    '    const int64_t gq99 = quantileIndex(greenHist, 99, 100);\n'
    '    const int64_t mq50 = quantileIndex(meanHist, 50, 100);\n'
    '    const int64_t mq90 = quantileIndex(meanHist, 90, 100);\n'
    '    const int64_t mq95 = quantileIndex(meanHist, 95, 100);\n'
    '    const int64_t mq99 = quantileIndex(meanHist, 99, 100);\n',
    'native histogram merge and quantiles')

replace_once(
    '    const jlong stats[16] = {\n'
    '        static_cast<jlong>(pixelCount), static_cast<jlong>(low), static_cast<jlong>(high),\n'
    '        static_cast<jlong>(nearWhite), static_cast<jlong>(workerSum), static_cast<jlong>(workerCount),\n'
    '        static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(\n'
    '                nativeEnded - nativeStarted).count()), static_cast<jlong>(pedestal14),\n'
    '        static_cast<jlong>(q50), static_cast<jlong>(q90), static_cast<jlong>(q95), static_cast<jlong>(q99),\n'
    '        static_cast<jlong>(MM_MONO1A_CURVE02[q50]), static_cast<jlong>(MM_MONO1A_CURVE02[q90]),\n'
    '        static_cast<jlong>(MM_MONO1A_CURVE02[q95]), static_cast<jlong>(MM_MONO1A_CURVE02[q99])\n'
    '    };\n'
    '    env->SetLongArrayRegion(statsArray, 0, 16, stats);\n',
    '    const jlong stats[32] = {\n'
    '        static_cast<jlong>(pixelCount), static_cast<jlong>(low), static_cast<jlong>(high),\n'
    '        static_cast<jlong>(nearWhite), static_cast<jlong>(workerSum), static_cast<jlong>(workerCount),\n'
    '        static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(\n'
    '                nativeEnded - nativeStarted).count()), static_cast<jlong>(pedestal14),\n'
    '        static_cast<jlong>(q50), static_cast<jlong>(q90), static_cast<jlong>(q95), static_cast<jlong>(q99),\n'
    '        static_cast<jlong>(MM_MONO1A_CURVE02[q50]), static_cast<jlong>(MM_MONO1A_CURVE02[q90]),\n'
    '        static_cast<jlong>(MM_MONO1A_CURVE02[q95]), static_cast<jlong>(MM_MONO1A_CURVE02[q99]),\n'
    '        static_cast<jlong>(gq50), static_cast<jlong>(gq90), static_cast<jlong>(gq95), static_cast<jlong>(gq99),\n'
    '        static_cast<jlong>(MM_MONO1A_CURVE02[gq50]), static_cast<jlong>(MM_MONO1A_CURVE02[gq90]),\n'
    '        static_cast<jlong>(MM_MONO1A_CURVE02[gq95]), static_cast<jlong>(MM_MONO1A_CURVE02[gq99]),\n'
    '        static_cast<jlong>(mq50), static_cast<jlong>(mq90), static_cast<jlong>(mq95), static_cast<jlong>(mq99),\n'
    '        static_cast<jlong>(MM_MONO1A_CURVE02[mq50]), static_cast<jlong>(MM_MONO1A_CURVE02[mq90]),\n'
    '        static_cast<jlong>(MM_MONO1A_CURVE02[mq95]), static_cast<jlong>(MM_MONO1A_CURVE02[mq99])\n'
    '    };\n'
    '    env->SetLongArrayRegion(statsArray, 0, 32, stats);\n',
    'native stats payload')

p.write_text(t)
print('MONO1A SOURCE1B diagnostic controls promoted')
