package com.particlesdevs.photoncamera.m9.exposure;

import com.particlesdevs.photoncamera.m9.M9BacklightDiagnostic;
import com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A;
import org.json.JSONObject;

/**
 * MONOAUTO1D1C: Leica Monochrom-specific scene placement with a single-exposure
 * broad-highlight-tail budget.
 *
 * MFM supplies spatial intent. SOURCE1D supplies placement magnitude. The 1A
 * q99.8/0.92 guard remains the strict path. For a strong positive MFM scene,
 * the 1B reconstructed sensor-RGB max probe may additionally authorize exposure
 * up to its q99 -> 250/255 ceiling when the probe itself has <=0.2% clipping.
 * This deliberately allows the brightest ~1% tail to be sacrificed in a
 * single exposure instead of turning highlight protection into HDR behavior.
 */
public final class MonoPlacementAssist1D {
    public static final String REVISION = "MONOAUTO1D_PLACEMENTASSIST1C_BROADTAIL1A";
    public static final double REFERENCE_TARGET = 0.107 * (8192.0 / 10000.0);
    public static final double DEAD_BAND_EV = 0.08;
    public static final double MAX_POSITIVE_EV = 0.50;
    public static final double MAX_NEGATIVE_EV = 0.50;
    public static final double LIVE_SOURCE_Q998_LIMIT = 0.92;
    public static final double BROAD_TAIL_Q99_TARGET = 250.0 / 255.0;
    public static final double BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION = 0.002;

    private MonoPlacementAssist1D() {}

    public static final class Decision {
        public final double appliedEv;
        public final String reason;
        public final JSONObject diagnostic;

        Decision(double appliedEv, String reason, JSONObject diagnostic) {
            this.appliedEv = appliedEv;
            this.reason = reason;
            this.diagnostic = diagnostic;
        }

        public String diagnosticJson() {
            return diagnostic == null ? null : diagnostic.toString();
        }
    }

    public static Decision evaluate(boolean eligible,
            M9BacklightDiagnostic.LiveFeedbackDecision mfmDecision,
            JSONObject mfm,
            MonoGpuPreview2A.PlacementObservation1D placement) {
        JSONObject d = new JSONObject();
        double applied = 0.0;
        String reason = "monoauto1d_neutral";
        try {
            d.put("schema", "mmonochrome.sceneplacement.v1d");
            d.put("revision", REVISION);
            d.put("referenceTarget", REFERENCE_TARGET);
            d.put("deadBandEv", DEAD_BAND_EV);
            d.put("positiveLimitEv", MAX_POSITIVE_EV);
            d.put("negativeLimitEv", -MAX_NEGATIVE_EV);
            d.put("liveSourceQ99_8Limit", LIVE_SOURCE_Q998_LIMIT);
            d.put("broadTailQ99Target", BROAD_TAIL_Q99_TARGET);
            d.put("broadTailMaxExistingClipFraction", BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION);
            d.put("magnitudeDomain", "live_SOURCE1D_XYZ_D50_Y_before_curve02");
            d.put("intentDomain", "M10R_4x6_multifield_preview_geometry_proxy");
            d.put("physicalRawTailAvailablePreCapture", false);
            d.put("positiveSafety",
                    "strict_SOURCE1D_q99p8_0p92_plus_strong_MFM_sensorRGBmax_q99_broad_tail_budget");
            d.put("highlightBudget",
                    "single_exposure_preserve_broad_99pct_tail_allow_small_extreme_highlight_sacrifice");
            d.put("HDR", false);
            d.put("postCaptureRescue", false);

            double mfmRecommended = mfmDecision == null ? 0.0 : mfmDecision.recommendedEv;
            double mfmApplied = mfmDecision == null ? 0.0 : mfmDecision.appliedEv;
            d.put("mfmRecommendedEv", mfmRecommended);
            d.put("mfmAppliedEvBeforePlacement", mfmApplied);
            d.put("mfmReason", mfmDecision == null ? "missing_mfm" : mfmDecision.reason);
            d.put("mfmSnapshot", mfm == null ? JSONObject.NULL : new JSONObject(mfm.toString()));

            if (!eligible) {
                reason = "monoauto1d_manual_ev_iso_shutter_or_tripod_bypass";
                return finish(d, 0.0, reason);
            }

            if (placement == null || !placement.valid) {
                applied = clamp(mfmApplied, -MAX_NEGATIVE_EV, MAX_POSITIVE_EV);
                reason = "monoauto1d_placement_unavailable_mfm_fallback"
                        + (placement == null ? "" : "_" + placement.reason);
                d.put("placementAvailable", false);
                return finish(d, applied, reason);
            }

            d.put("placementAvailable", true);
            d.put("placementReason", placement.reason);
            d.put("placementAgeMs", placement.ageMs);
            d.put("placementPlanScale", placement.planScale);
            d.put("sourceCenterWeightedMedianScaled", placement.scaledCenterWeightedMedian);
            d.put("sourceCenterWeightedMedianHardwareAeBase", placement.baseCenterWeightedMedian);
            d.put("sourceQ99_8Scaled", placement.scaledQ99_8);
            d.put("sourceQ99_8HardwareAeBase", placement.baseQ99_8);
            d.put("sourceScaledClipFraction", placement.scaledClipFraction);
            d.put("placementSampleCount", placement.sampleCount);
            d.put("sensorRgbMaxQ95", placement.sensorRgbMaxQ95);
            d.put("sensorRgbMaxQ99", placement.sensorRgbMaxQ99);
            d.put("sensorRgbMaxQ99_8", placement.sensorRgbMaxQ99_8);
            d.put("sensorRgbMaxClipFraction", placement.sensorRgbMaxClipFraction);
            d.put("sensorRgbMaxProxyRole",
                    "broad_tail_guard_only_not_claimed_physical_RAW_reconstruction");

            double median = placement.baseCenterWeightedMedian;
            double q998 = placement.baseQ99_8;
            if (!finite(median) || median <= 0.0 || !finite(q998) || q998 <= 0.0) {
                applied = clamp(mfmApplied, -MAX_NEGATIVE_EV, MAX_POSITIVE_EV);
                reason = "monoauto1d_invalid_source_probe_mfm_fallback";
                return finish(d, applied, reason);
            }

            double referenceDelta = log2(REFERENCE_TARGET / median);
            double q998Headroom = log2(LIVE_SOURCE_Q998_LIMIT / q998);
            double clippedLowerBoundHeadroom = placement.scaledClipFraction > 0.0
                    ? log2(LIVE_SOURCE_Q998_LIMIT * placement.planScale)
                    : Double.POSITIVE_INFINITY;
            double strictPositiveHeadroom = Math.min(q998Headroom, clippedLowerBoundHeadroom);

            d.put("referencePlacementDeltaEv", referenceDelta);
            d.put("sourceQ99_8HeadroomTo0p92Ev", q998Headroom);
            d.put("strictClipAwarePositiveHeadroomEv",
                    finite(strictPositiveHeadroom) ? strictPositiveHeadroom : JSONObject.NULL);

            double sceneSpread = opt(mfm, "sceneSpreadEv");
            double brightFraction = opt(mfm, "brightRegionFraction");
            double darkFraction = opt(mfm, "darkRegionFraction");
            double upperVsLower = opt(mfm, "upperVsLowerEv");
            double edgeVsInner = opt(mfm, "edgeVsInnerEv");
            double integralVsCenter = opt(mfm, "integralVsCenterEv");
            double integralVsLower = opt(mfm, "integralVsLowerEv");
            double negativeCandidate = opt(mfm, "negativeCandidateEv");

            boolean positiveGeometry =
                    finite(sceneSpread) && sceneSpread >= 0.70
                    && finite(brightFraction) && brightFraction >= 0.08
                    && finite(darkFraction) && darkFraction >= 0.20
                    && ((finite(upperVsLower) && upperVsLower >= 0.30)
                        || (finite(edgeVsInner) && edgeVsInner >= 0.20))
                    && ((finite(integralVsCenter) && integralVsCenter >= 0.08)
                        || (finite(integralVsLower) && integralVsLower >= 0.08));

            boolean positiveIntent = mfmRecommended >= DEAD_BAND_EV || positiveGeometry;
            boolean negativeIntent = mfmRecommended <= -DEAD_BAND_EV
                    || (finite(negativeCandidate) && negativeCandidate <= -DEAD_BAND_EV);

            double broadTailHeadroom = finite(placement.sensorRgbMaxQ99)
                    && placement.sensorRgbMaxQ99 > 0.0
                    ? log2(BROAD_TAIL_Q99_TARGET / placement.sensorRgbMaxQ99)
                    : Double.NaN;
            boolean broadTailEligible =
                    positiveGeometry
                    && mfmRecommended >= DEAD_BAND_EV
                    && finite(broadTailHeadroom) && broadTailHeadroom > 0.0
                    && finite(placement.sensorRgbMaxClipFraction)
                    && placement.sensorRgbMaxClipFraction <= BROAD_TAIL_MAX_EXISTING_CLIP_FRACTION
                    && placement.sensorRgbMaxQ99 < BROAD_TAIL_Q99_TARGET;
            double broadTailMfmBoundedHeadroom = broadTailEligible
                    ? Math.min(broadTailHeadroom, Math.max(0.0, mfmRecommended))
                    : 0.0;

            d.put("positiveGeometryIntent", positiveGeometry);
            d.put("positiveIntent", positiveIntent);
            d.put("negativeIntent", negativeIntent);
            d.put("broadTailHeadroomEv",
                    finite(broadTailHeadroom) ? broadTailHeadroom : JSONObject.NULL);
            d.put("broadTailEligible", broadTailEligible);
            d.put("broadTailMfmBoundedHeadroomEv", broadTailMfmBoundedHeadroom);

            if (positiveIntent && referenceDelta > DEAD_BAND_EV) {
                double strict = Math.max(0.0,
                        finite(strictPositiveHeadroom) ? strictPositiveHeadroom : 0.0);
                double selectedHeadroom = Math.max(strict, broadTailMfmBoundedHeadroom);
                boolean broadTailSelected = broadTailMfmBoundedHeadroom > strict + 1.0e-9;
                d.put("selectedPositiveHeadroomEv", selectedHeadroom);
                d.put("broadTailSelected", broadTailSelected);

                applied = Math.min(referenceDelta, Math.min(MAX_POSITIVE_EV, selectedHeadroom));
                if (applied < DEAD_BAND_EV) {
                    applied = 0.0;
                    reason = "monoauto1d_positive_blocked_by_live_highlight_budget";
                } else if (broadTailSelected) {
                    reason = "monoauto1d_mfm_positive_broadtail_placement_lift";
                } else {
                    reason = positiveGeometry && mfmRecommended < DEAD_BAND_EV
                            ? "monoauto1d_backlit_geometry_source_placement_lift"
                            : "monoauto1d_mfm_positive_source_placement_lift";
                }
            } else if (negativeIntent && referenceDelta < -DEAD_BAND_EV) {
                applied = Math.max(referenceDelta, -MAX_NEGATIVE_EV);
                reason = "monoauto1d_mfm_negative_source_placement_moderation";
            } else if ((positiveIntent && referenceDelta <= DEAD_BAND_EV)
                    || (negativeIntent && referenceDelta >= -DEAD_BAND_EV)) {
                applied = 0.0;
                reason = "monoauto1d_intent_present_source_already_placed";
            } else {
                applied = 0.0;
                reason = "monoauto1d_no_spatial_scene_intent";
            }

            d.put("requestedPlacementEvBeforeAllocator", applied);
            d.put("predictedSourceCenterAfterAssist", median * Math.pow(2.0, applied));
            d.put("predictedSourceQ99_8AfterAssist", q998 * Math.pow(2.0, applied));
            d.put("predictedSensorRgbMaxQ99AfterAssist",
                    finite(placement.sensorRgbMaxQ99)
                            ? placement.sensorRgbMaxQ99 * Math.pow(2.0, applied)
                            : JSONObject.NULL);
            return finish(d, applied, reason);
        } catch (Throwable t) {
            try {
                d.put("error", t.toString());
                d.put("fallbackMfmAppliedEv",
                        mfmDecision == null ? 0.0 : mfmDecision.appliedEv);
            } catch (Throwable ignored) {}
            applied = mfmDecision == null ? 0.0
                    : clamp(mfmDecision.appliedEv, -MAX_NEGATIVE_EV, MAX_POSITIVE_EV);
            reason = "monoauto1d_exception_mfm_fallback";
            return finish(d, applied, reason);
        }
    }

    private static Decision finish(JSONObject d, double ev, String reason) {
        try {
            d.put("appliedExposureCorrectionEv", ev);
            d.put("reason", reason);
        } catch (Throwable ignored) {}
        return new Decision(ev, reason, d);
    }

    private static double opt(JSONObject o, String key) {
        return o == null ? Double.NaN : o.optDouble(key, Double.NaN);
    }

    private static double log2(double v) {
        return Math.log(Math.max(v, 1.0e-12)) / Math.log(2.0);
    }

    private static double clamp(double v, double lo, double hi) {
        return Math.max(lo, Math.min(hi, v));
    }

    private static boolean finite(double v) {
        return !Double.isNaN(v) && !Double.isInfinite(v);
    }
}
