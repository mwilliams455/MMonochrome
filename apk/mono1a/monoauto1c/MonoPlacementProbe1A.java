package com.particlesdevs.photoncamera.m9.export;

import com.particlesdevs.photoncamera.m9.M9M10rMfmTest1A;
import org.json.JSONObject;

/**
 * MONOAUTO1C placement probe.
 *
 * Diagnostic only. Scans the already-owned derived scene-linear monochrome plane,
 * compares its centre-weighted placement against the recovered M9 TC20 reference,
 * and reports raw-tail headroom and the already-existing M10-R MFM live recommendation.
 * No capture, JPEG, preview, curve, DNG samples, or BaselineExposure values are changed.
 */
public final class MonoPlacementProbe1A {
    public static final String REVISION = "MONOAUTO1C_PLACEMENTPROBE1A";
    private static final double CENTER_WIDTH = 0.75;
    private MonoPlacementProbe1A() {}

    public static JSONObject evaluate(MonoLinearPlane1A plane,
            double rawUq99, double rawUq995, double rawUq998, double rawHardClipFraction) {
        JSONObject out = new JSONObject();
        long started = System.nanoTime();
        try {
            out.put("schema", "mmonochrome.placementprobe.v1a");
            out.put("revision", REVISION);
            out.put("mode", "diagnostic_only_no_exposure_mutation");
            out.put("captureExposureChanged", false);
            out.put("jpegRenderChanged", false);
            out.put("curve02Changed", false);
            out.put("dngSamplesChanged", false);
            out.put("baselineExposureChanged", false);
            out.put("referenceTarget", MonoPlacementMath1A.REFERENCE_TARGET);
            out.put("referenceOrigin", "recovered_M9_TC20_0p107_times_8192_over_10000");
            out.put("leicaTyp246OracleNote",
                    "single_sample_global_median_329_over_3750_close_to_reference_not_a_universal_Leica_AE_constant");

            if (plane == null || plane.pixels == null || plane.pixels.length == 0
                    || plane.width <= 0 || plane.height <= 0) {
                out.put("valid", false).put("reason", "missing_linear_plane");
                return out;
            }

            long[] hist = new long[65536];
            double[] weightedHist = new double[65536];
            double[] colWeight = new double[plane.width];
            double w2 = plane.width / 2.0;
            double h2 = plane.height / 2.0;
            double den = 2.0 * CENTER_WIDTH * CENTER_WIDTH;
            for (int x = 0; x < plane.width; x++) {
                double rx = (x - w2) / w2;
                colWeight[x] = Math.exp(-(rx * rx) / den);
            }

            double totalWeight = 0.0;
            for (int y = 0; y < plane.height; y++) {
                double ry = (y - h2) / h2;
                double rowWeight = Math.exp(-(ry * ry) / den);
                int row = y * plane.width;
                for (int x = 0; x < plane.width; x++) {
                    int code = plane.pixels[row + x] & 0xffff;
                    hist[code]++;
                    double wt = rowWeight * colWeight[x];
                    weightedHist[code] += wt;
                    totalWeight += wt;
                }
            }

            long total = plane.pixels.length;
            int q25Code = quantileCode(hist, total, 0.25);
            int q50Code = quantileCode(hist, total, 0.50);
            int q90Code = quantileCode(hist, total, 0.90);
            int q95Code = quantileCode(hist, total, 0.95);
            int q99Code = quantileCode(hist, total, 0.99);
            int q995Code = quantileCode(hist, total, 0.995);
            int q998Code = quantileCode(hist, total, 0.998);
            int weightedMedianCode = weightedMedianCode(weightedHist, totalWeight);

            double q25 = MonoPlacementMath1A.sourceFromStoredCode(q25Code, plane.sourceUnitsPerWhite);
            double q50 = MonoPlacementMath1A.sourceFromStoredCode(q50Code, plane.sourceUnitsPerWhite);
            double q90 = MonoPlacementMath1A.sourceFromStoredCode(q90Code, plane.sourceUnitsPerWhite);
            double q95 = MonoPlacementMath1A.sourceFromStoredCode(q95Code, plane.sourceUnitsPerWhite);
            double q99 = MonoPlacementMath1A.sourceFromStoredCode(q99Code, plane.sourceUnitsPerWhite);
            double q995 = MonoPlacementMath1A.sourceFromStoredCode(q995Code, plane.sourceUnitsPerWhite);
            double q998 = MonoPlacementMath1A.sourceFromStoredCode(q998Code, plane.sourceUnitsPerWhite);
            double weightedMedian = MonoPlacementMath1A.sourceFromStoredCode(
                    weightedMedianCode, plane.sourceUnitsPerWhite);

            double referenceDeltaEv = MonoPlacementMath1A.evToReference(weightedMedian);
            double rawHeadroom95Ev = MonoPlacementMath1A.headroomEv(rawUq998, 0.95);
            double rawHeadroom92Ev = MonoPlacementMath1A.headroomEv(rawUq998, 0.92);
            double bounded95Ev = MonoPlacementMath1A.boundedByPositiveHeadroom(
                    referenceDeltaEv, rawHeadroom95Ev);
            double scale = Math.pow(2.0, referenceDeltaEv);

            out.put("valid", Double.isFinite(referenceDeltaEv));
            out.put("sourceDomain", "SOURCE1D_XYZ_D50_Y_before_curve02");
            out.put("sourceUnitsPerDngWhite", plane.sourceUnitsPerWhite);
            out.put("representationScale", plane.representationScale);
            out.put("sourceQ25", q25);
            out.put("sourceQ50", q50);
            out.put("sourceQ90", q90);
            out.put("sourceQ95", q95);
            out.put("sourceQ99", q99);
            out.put("sourceQ99_5", q995);
            out.put("sourceQ99_8", q998);
            out.put("sourceCenterWeightedMedian", weightedMedian);
            out.put("sourceGlobalMedian", q50);
            out.put("referencePlacementDeltaEv", referenceDeltaEv);
            out.put("referencePlacementScale", scale);
            out.put("sourceQ99_8AfterReference", MonoPlacementMath1A.applyEv(q998, referenceDeltaEv));
            out.put("sourceMaxAfterReference", MonoPlacementMath1A.applyEv(plane.maxSource, referenceDeltaEv));

            out.put("rawUq99", rawUq99);
            out.put("rawUq99_5", rawUq995);
            out.put("rawUq99_8", rawUq998);
            out.put("rawHardClipFraction", rawHardClipFraction);
            out.put("rawHeadroomTo0p95Ev", rawHeadroom95Ev);
            out.put("rawHeadroomTo0p92Ev", rawHeadroom92Ev);
            out.put("referenceDeltaBoundedByRaw0p95Ev", bounded95Ev);
            out.put("raw0p95ConstraintWouldBind",
                    Double.isFinite(referenceDeltaEv) && Double.isFinite(rawHeadroom95Ev)
                            && referenceDeltaEv > 0.0 && referenceDeltaEv > rawHeadroom95Ev);
            out.put("rawUq99_8AfterReference",
                    MonoPlacementMath1A.applyEv(rawUq998, referenceDeltaEv));

            JSONObject mfm = M9M10rMfmTest1A.snapshotJson();
            if (mfm != null) {
                out.put("m10rMfmSnapshot", new JSONObject(mfm.toString()));
                double mfmRecommended = mfm.optDouble("recommendedExposureCorrectionEv", Double.NaN);
                double mfmApplied = mfm.optDouble("appliedExposureCorrectionEv", Double.NaN);
                out.put("mfmRecommendedEv", mfmRecommended);
                out.put("mfmAppliedEv", mfmApplied);
                out.put("mfmReason", mfm.optString("reason", ""));
                if (Double.isFinite(mfmRecommended))
                    out.put("referenceMinusMfmRecommendedEv", referenceDeltaEv - mfmRecommended);
                if (Double.isFinite(mfmApplied))
                    out.put("referenceMinusMfmAppliedEv", referenceDeltaEv - mfmApplied);
            }
            out.put("reason", "placement_probe_complete");
        } catch (Throwable t) {
            try {
                out.put("valid", false);
                out.put("reason", "placement_probe_exception");
                out.put("error", t.toString());
            } catch (Throwable ignored) {}
        } finally {
            try { out.put("elapsedMs", (System.nanoTime() - started) / 1.0e6); }
            catch (Throwable ignored) {}
        }
        return out;
    }

    private static int quantileCode(long[] hist, long total, double q) {
        if (total <= 0) return 0;
        long target = Math.max(0L, Math.min(total - 1L,
                (long)Math.floor((total - 1L) * q)));
        long cumulative = 0L;
        for (int i = 0; i < hist.length; i++) {
            cumulative += hist[i];
            if (cumulative > target) return i;
        }
        return hist.length - 1;
    }

    private static int weightedMedianCode(double[] hist, double totalWeight) {
        if (!(totalWeight > 0.0) || !Double.isFinite(totalWeight)) return 0;
        double half = totalWeight * 0.5;
        double cumulative = 0.0;
        for (int i = 0; i < hist.length; i++) {
            cumulative += hist[i];
            if (cumulative >= half) return i;
        }
        return hist.length - 1;
    }
}
