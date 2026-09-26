package com.particlesdevs.photoncamera.m9.exposure;

import com.particlesdevs.photoncamera.m9.M9BacklightDiagnostic;
import com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A;
import org.json.JSONObject;

/**
 * MONOAUTO1D: Leica Monochrom-specific pre-capture scene placement assist.
 *
 * MFM supplies scene/spatial intent. The live Monochrom GPU probe supplies the
 * SOURCE1D scene-linear placement magnitude before curve02. Positive movement
 * is bounded by a conservative live SOURCE1D q99.8 ceiling and the existing
 * physical Photon/Camera2 allocator. This class never edits rendered pixels,
 * DNG samples, BaselineExposure, or curve02.
 */
public final class MonoPlacementAssist1D {
    public static final String REVISION = "MONOAUTO1D_PLACEMENTASSIST1A";
    public static final double REFERENCE_TARGET = 0.107 * (8192.0 / 10000.0);
    public static final double DEAD_BAND_EV = 0.08;
    public static final double MAX_POSITIVE_EV = 0.50;
    public static final double MAX_NEGATIVE_EV = 0.50;
    public static final double LIVE_SOURCE_Q998_LIMIT = 0.92;

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
            d.put("magnitudeDomain", "live_SOURCE1D_XYZ_D50_Y_before_curve02");
            d.put("intentDomain", "M10R_4x6_multifield_preview_geometry_proxy");
            d.put("physicalRawTailAvailablePreCapture", false);
            d.put("positiveSafety",
                    "live_SOURCE1D_q99p8_proxy_plus_existing_hardware_AE_and_physical_allocator_limits");
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
                // Preserve the already-delivered MONOAUTO1A/MFM behavior until a
                // recent live SOURCE1D placement probe exists.
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

            double median = placement.baseCenterWeightedMedian;
            double q998 = placement.baseQ99_8;
            if (!finite(median) || median <= 0.0 || !finite(q998) || q998 <= 0.0) {
                applied = clamp(mfmApplied, -MAX_NEGATIVE_EV, MAX_POSITIVE_EV);
                reason = "monoauto1d_invalid_source_probe_mfm_fallback";
                return finish(d, applied, reason);
            }

            double referenceDelta = log2(REFERENCE_TARGET / median);
            double q998Headroom = log2(LIVE_SOURCE_Q998_LIMIT / q998);
            // If the currently displayed planned SOURCE1D probe clipped, q99.8
            // underestimates the unscaled base tail. This bound remains safe
            // relative to the observed plan scale.
            double clippedLowerBoundHeadroom = placement.scaledClipFraction > 0.0
                    ? log2(LIVE_SOURCE_Q998_LIMIT * placement.planScale)
                    : Double.POSITIVE_INFINITY;
            double positiveHeadroom = Math.min(q998Headroom, clippedLowerBoundHeadroom);

            d.put("referencePlacementDeltaEv", referenceDelta);
            d.put("sourceQ99_8HeadroomTo0p92Ev", q998Headroom);
            d.put("clipAwarePositiveHeadroomEv",
                    finite(positiveHeadroom) ? positiveHeadroom : JSONObject.NULL);

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

            d.put("positiveGeometryIntent", positiveGeometry);
            d.put("positiveIntent", positiveIntent);
            d.put("negativeIntent", negativeIntent);

            if (positiveIntent && referenceDelta > DEAD_BAND_EV) {
                double safeHeadroom = Math.max(0.0,
                        finite(positiveHeadroom) ? positiveHeadroom : 0.0);
                applied = Math.min(referenceDelta, Math.min(MAX_POSITIVE_EV, safeHeadroom));
                if (applied < DEAD_BAND_EV) {
                    applied = 0.0;
                    reason = "monoauto1d_positive_blocked_by_live_source_headroom";
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
            d.put("predictedSourceCenterAfterAssist",
                    median * Math.pow(2.0, applied));
            d.put("predictedSourceQ99_8AfterAssist",
                    q998 * Math.pow(2.0, applied));
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
