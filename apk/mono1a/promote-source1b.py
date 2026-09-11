#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: promote-source1b.py <apply-mono1a.py>")
p = Path(sys.argv[1])
t = p.read_text()

def replace_once(old, new, label):
    global t
    n = t.count(old)
    if n != 1:
        raise SystemExit(f"{label} anchor count={n}, expected 1")
    t = t.replace(old, new, 1)

# Keep SOURCE1A's selected M9-Y JPEG path frozen; only expand same-frame diagnostics.
replace_once(
    '                long[] monoStats = new long[16];\n',
    '                long[] monoStats = new long[35];\n',
    'java stats length')

replace_once(
    '                d.put("curveOutputAtSourceQ99", monoStats[15]);\n',
    '''                d.put("curveOutputAtSourceQ99", monoStats[15]);
                d.put("curveOutputMeanControl", monoStats[16] / 1000.0);
                JSONObject equalRgb = new JSONObject();
                equalRgb.put("mode", "EQUAL_RGB_COUNTERFACTUAL");
                equalRgb.put("formula", "((R+G+B)/3)>>>2_to_Leica14");
                equalRgb.put("neutralAxisInvariantVsControl", true);
                equalRgb.put("photographicOutputSelected", false);
                equalRgb.put("sourceIndexQ50", monoStats[17]);
                equalRgb.put("sourceIndexQ90", monoStats[18]);
                equalRgb.put("sourceIndexQ95", monoStats[19]);
                equalRgb.put("sourceIndexQ99", monoStats[20]);
                equalRgb.put("curveOutputAtSourceQ50", monoStats[21]);
                equalRgb.put("curveOutputAtSourceQ90", monoStats[22]);
                equalRgb.put("curveOutputAtSourceQ95", monoStats[23]);
                equalRgb.put("curveOutputAtSourceQ99", monoStats[24]);
                equalRgb.put("curveOutputMean", monoStats[25] / 1000.0);
                d.put("counterfactualEqualRgb", equalRgb);
                JSONObject greenOnly = new JSONObject();
                greenOnly.put("mode", "GREEN_ONLY_COUNTERFACTUAL");
                greenOnly.put("formula", "G>>>2_to_Leica14");
                greenOnly.put("neutralAxisInvariantVsControl", true);
                greenOnly.put("photographicOutputSelected", false);
                greenOnly.put("sourceIndexQ50", monoStats[26]);
                greenOnly.put("sourceIndexQ90", monoStats[27]);
                greenOnly.put("sourceIndexQ95", monoStats[28]);
                greenOnly.put("sourceIndexQ99", monoStats[29]);
                greenOnly.put("curveOutputAtSourceQ50", monoStats[30]);
                greenOnly.put("curveOutputAtSourceQ90", monoStats[31]);
                greenOnly.put("curveOutputAtSourceQ95", monoStats[32]);
                greenOnly.put("curveOutputAtSourceQ99", monoStats[33]);
                greenOnly.put("curveOutputMean", monoStats[34] / 1000.0);
                d.put("counterfactualGreenOnly", greenOnly);
''',
    'java counterfactual diagnostics')

# Authoritative revision/schema labels only; selected source adapter remains M9-Y control.
t = t.replace('MONO1A_SOURCE1A', 'MONO1A_SOURCE1B')
t = t.replace('mmonochrome.mono1a.source1a.v1', 'mmonochrome.mono1a.source1b.v1')

replace_once(
    '            || env->GetArrayLength(statsArray) < 16) {\n',
    '            || env->GetArrayLength(statsArray) < 35) {\n',
    'jni stats validation')

replace_once(
    '''    std::vector<std::array<int64_t, 3>> local(static_cast<size_t>(workerCount));
    std::vector<std::array<uint64_t, 2048>> localIndexHist(static_cast<size_t>(workerCount));
    std::vector<int64_t> workerNs(static_cast<size_t>(workerCount), 0);
''',
    '''    std::vector<std::array<int64_t, 3>> local(static_cast<size_t>(workerCount));
    std::vector<std::array<uint64_t, 2048>> localIndexHist(static_cast<size_t>(workerCount));
    std::vector<std::array<uint64_t, 2048>> localEqualRgbHist(static_cast<size_t>(workerCount));
    std::vector<std::array<uint64_t, 2048>> localGreenOnlyHist(static_cast<size_t>(workerCount));
    std::vector<int64_t> workerNs(static_cast<size_t>(workerCount), 0);
''',
    'native histogram vectors')

replace_once(
    '''            auto& indexHist = localIndexHist[static_cast<size_t>(worker)];
            for (size_t j = 0; j < indexHist.size(); ++j) indexHist[j] = 0;
''',
    '''            auto& indexHist = localIndexHist[static_cast<size_t>(worker)];
            auto& equalRgbHist = localEqualRgbHist[static_cast<size_t>(worker)];
            auto& greenOnlyHist = localGreenOnlyHist[static_cast<size_t>(worker)];
            for (size_t j = 0; j < indexHist.size(); ++j) {
                indexHist[j] = 0;
                equalRgbHist[j] = 0;
                greenOnlyHist[j] = 0;
            }
''',
    'native local histogram init')

replace_once(
    '''                    ++indexHist[static_cast<size_t>(idx)];
                    const uint8_t yy = MM_MONO1A_CURVE02[idx];
''',
    '''                    ++indexHist[static_cast<size_t>(idx)];

                    // SOURCE1B counterfactuals are neutral-axis invariant: if R=G=B,
                    // both equal-RGB and green-only produce exactly the control scalar.
                    const uint32_t equalRgb16 = (r + g + b) / 3u;
                    const int32_t equalSample14 = static_cast<int32_t>(
                            std::min<uint32_t>(16383u, equalRgb16 >> 2));
                    int32_t equalV = equalSample14 - static_cast<int32_t>(pedestal14);
                    if (equalV < 0) equalV = 0;
                    int32_t equalIdx = equalV >> 3;
                    if (equalIdx > 2047) equalIdx = 2047;
                    ++equalRgbHist[static_cast<size_t>(equalIdx)];

                    const int32_t greenSample14 = static_cast<int32_t>(
                            std::min<uint32_t>(16383u, g >> 2));
                    int32_t greenV = greenSample14 - static_cast<int32_t>(pedestal14);
                    if (greenV < 0) greenV = 0;
                    int32_t greenIdx = greenV >> 3;
                    if (greenIdx > 2047) greenIdx = 2047;
                    ++greenOnlyHist[static_cast<size_t>(greenIdx)];

                    const uint8_t yy = MM_MONO1A_CURVE02[idx];
''',
    'native counterfactual accumulation')

replace_once(
    '''    std::array<uint64_t, 2048> indexHist{};
    for (int i = 0; i < workerCount; ++i) {
''',
    '''    std::array<uint64_t, 2048> indexHist{};
    std::array<uint64_t, 2048> equalRgbHist{};
    std::array<uint64_t, 2048> greenOnlyHist{};
    for (int i = 0; i < workerCount; ++i) {
''',
    'native reduced histograms')

replace_once(
    '''        const auto& srcHist = localIndexHist[static_cast<size_t>(i)];
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
''',
    '''        const auto& srcHist = localIndexHist[static_cast<size_t>(i)];
        const auto& srcEqual = localEqualRgbHist[static_cast<size_t>(i)];
        const auto& srcGreen = localGreenOnlyHist[static_cast<size_t>(i)];
        for (size_t j = 0; j < indexHist.size(); ++j) {
            indexHist[j] += srcHist[j];
            equalRgbHist[j] += srcEqual[j];
            greenOnlyHist[j] += srcGreen[j];
        }
    }
    auto quantileIndex = [&](const std::array<uint64_t, 2048>& hist,
                             uint64_t numerator, uint64_t denominator) -> int64_t {
        const uint64_t target = std::max<uint64_t>(1u,
                (static_cast<uint64_t>(pixelCount) * numerator + denominator - 1u) / denominator);
        uint64_t cumulative = 0;
        for (size_t j = 0; j < hist.size(); ++j) {
            cumulative += hist[j];
            if (cumulative >= target) return static_cast<int64_t>(j);
        }
        return 2047;
    };
    auto curveMeanMilli = [&](const std::array<uint64_t, 2048>& hist) -> int64_t {
        uint64_t sum = 0;
        for (size_t j = 0; j < hist.size(); ++j) {
            sum += hist[j] * static_cast<uint64_t>(MM_MONO1A_CURVE02[j]);
        }
        return static_cast<int64_t>((sum * 1000ull + static_cast<uint64_t>(pixelCount) / 2ull)
                / static_cast<uint64_t>(pixelCount));
    };
    const int64_t q50 = quantileIndex(indexHist, 50, 100);
    const int64_t q90 = quantileIndex(indexHist, 90, 100);
    const int64_t q95 = quantileIndex(indexHist, 95, 100);
    const int64_t q99 = quantileIndex(indexHist, 99, 100);
    const int64_t eq50 = quantileIndex(equalRgbHist, 50, 100);
    const int64_t eq90 = quantileIndex(equalRgbHist, 90, 100);
    const int64_t eq95 = quantileIndex(equalRgbHist, 95, 100);
    const int64_t eq99 = quantileIndex(equalRgbHist, 99, 100);
    const int64_t gr50 = quantileIndex(greenOnlyHist, 50, 100);
    const int64_t gr90 = quantileIndex(greenOnlyHist, 90, 100);
    const int64_t gr95 = quantileIndex(greenOnlyHist, 95, 100);
    const int64_t gr99 = quantileIndex(greenOnlyHist, 99, 100);
''',
    'native histogram reduction and quantiles')

replace_once(
    '''    const jlong stats[16] = {
        static_cast<jlong>(pixelCount), static_cast<jlong>(low), static_cast<jlong>(high),
        static_cast<jlong>(nearWhite), static_cast<jlong>(workerSum), static_cast<jlong>(workerCount),
        static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                nativeEnded - nativeStarted).count()), static_cast<jlong>(pedestal14),
        static_cast<jlong>(q50), static_cast<jlong>(q90), static_cast<jlong>(q95), static_cast<jlong>(q99),
        static_cast<jlong>(MM_MONO1A_CURVE02[q50]), static_cast<jlong>(MM_MONO1A_CURVE02[q90]),
        static_cast<jlong>(MM_MONO1A_CURVE02[q95]), static_cast<jlong>(MM_MONO1A_CURVE02[q99])
    };
    env->SetLongArrayRegion(statsArray, 0, 16, stats);
''',
    '''    const jlong stats[35] = {
        static_cast<jlong>(pixelCount), static_cast<jlong>(low), static_cast<jlong>(high),
        static_cast<jlong>(nearWhite), static_cast<jlong>(workerSum), static_cast<jlong>(workerCount),
        static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(
                nativeEnded - nativeStarted).count()), static_cast<jlong>(pedestal14),
        static_cast<jlong>(q50), static_cast<jlong>(q90), static_cast<jlong>(q95), static_cast<jlong>(q99),
        static_cast<jlong>(MM_MONO1A_CURVE02[q50]), static_cast<jlong>(MM_MONO1A_CURVE02[q90]),
        static_cast<jlong>(MM_MONO1A_CURVE02[q95]), static_cast<jlong>(MM_MONO1A_CURVE02[q99]),
        static_cast<jlong>(curveMeanMilli(indexHist)),
        static_cast<jlong>(eq50), static_cast<jlong>(eq90), static_cast<jlong>(eq95), static_cast<jlong>(eq99),
        static_cast<jlong>(MM_MONO1A_CURVE02[eq50]), static_cast<jlong>(MM_MONO1A_CURVE02[eq90]),
        static_cast<jlong>(MM_MONO1A_CURVE02[eq95]), static_cast<jlong>(MM_MONO1A_CURVE02[eq99]),
        static_cast<jlong>(curveMeanMilli(equalRgbHist)),
        static_cast<jlong>(gr50), static_cast<jlong>(gr90), static_cast<jlong>(gr95), static_cast<jlong>(gr99),
        static_cast<jlong>(MM_MONO1A_CURVE02[gr50]), static_cast<jlong>(MM_MONO1A_CURVE02[gr90]),
        static_cast<jlong>(MM_MONO1A_CURVE02[gr95]), static_cast<jlong>(MM_MONO1A_CURVE02[gr99]),
        static_cast<jlong>(curveMeanMilli(greenOnlyHist))
    };
    env->SetLongArrayRegion(statsArray, 0, 35, stats);
''',
    'native stats expansion')

p.write_text(t)
print('MONO1A SOURCE1B counterfactual diagnostics promoted')
