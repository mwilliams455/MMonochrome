package com.particlesdevs.photoncamera.m9.preview;

import com.particlesdevs.photoncamera.m9.M9DiagnosticBurstSpool;
import com.particlesdevs.photoncamera.util.Log;
import org.json.JSONObject;
import java.nio.charset.StandardCharsets;
import java.nio.file.Path;
import java.util.LinkedHashMap;
import java.util.Map;

/** Diagnostic bytes only: no camera request, pixel, tone or exposure mutations. */
public final class MonoLivePairExport1D {
    public static final String BUILD = "MONOLIVEGL1E_LIVEPAIRDIAG1D_SPOOL";
    private static final String TAG = "MonoLivePair1D";
    private static final int MAX_PENDING = 32;
    private static final Map<String, String> COMPLETED = new LinkedHashMap<>();
    private static long rememberedCount;
    private static long writerFailureCount;
    private static long evictionCount;
    private static String lastWriterError = "";
    private MonoLivePairExport1D() {}

    private static String key(String cameraId, long timestampNs) {
        return cameraId + ":" + timestampNs;
    }

    /** Called synchronously by the capture callback; bounded memory only, no disk I/O. */
    public static synchronized void remember(JSONObject pair) {
        try {
            JSONObject result = pair.optJSONObject("captureResult");
            long timestampNs = result != null ? result.optLong("sensorTimestampNs", -1L) : -1L;
            String cameraId = pair.optString("cameraId", "");
            if (timestampNs <= 0L || cameraId.isEmpty()) {
                throw new IllegalStateException("completed_pair_identity_missing");
            }
            COMPLETED.put(key(cameraId, timestampNs), pair.toString());
            rememberedCount++;
            while (COMPLETED.size() > MAX_PENDING) {
                COMPLETED.remove(COMPLETED.keySet().iterator().next());
                evictionCount++;
            }
        } catch (Exception e) {
            noteFailure(e);
        }
    }

    public static synchronized void noteFailure(Throwable error) {
        writerFailureCount++;
        lastWriterError = error == null ? "unknown" : error.toString();
    }

    private static synchronized String take(String cameraId, long timestampNs) {
        return COMPLETED.remove(key(cameraId, timestampNs));
    }

    private static synchronized JSONObject telemetry() throws Exception {
        JSONObject out = new JSONObject();
        out.put("rememberedCount", rememberedCount);
        out.put("pendingCompletedCount", COMPLETED.size());
        out.put("evictionCount", evictionCount);
        out.put("writerFailureCount", writerFailureCount);
        out.put("lastWriterError", lastWriterError);
        return out;
    }

    /**
     * Runs at the existing deferred capture-JSON persistence boundary, for Photo and ZSL.
     * Always includes an explicit record, even if the shutter callback did not supply a pair.
     * The public file is a sibling of the actual _M9.json, not a guessed DCIM/Camera path.
     */
    public static byte[] attachAndStage(Path captureJsonPath, byte[] original) {
        if (captureJsonPath == null || original == null) return original;
        JSONObject capture = null;
        try {
            capture = new JSONObject(new String(original, StandardCharsets.UTF_8));
            JSONObject raw = capture.optJSONObject("raw");
            long rawTs = raw != null ? raw.optLong("timestampNs", -1L) : -1L;
            String cameraId = capture.optString("cameraId", "");
            String completed = rawTs > 0L ? take(cameraId, rawTs) : null;
            JSONObject pair = completed != null ? new JSONObject(completed) : new JSONObject();
            pair.put("sourceDiagnosticSchema", pair.optString("schema", "unavailable"));
            pair.put("schema", "mmonochrome.livepair.export1d.v1");
            pair.put("buildMarker", BUILD);
            pair.put("captureIdentity", capture.optString("dng", ""));
            pair.put("cameraId", cameraId);
            pair.put("rawTimestampNs", rawTs);
            pair.put("completedCallbackMatchedRawTimestamp", completed != null);
            pair.put("pairAssociation", completed != null
                    ? "exact_camera_id_and_raw_sensor_timestamp"
                    : "unavailable_no_exact_callback_match");
            // Source metadata already bound to the saved RAW: not live mutable controller state.
            pair.put("primaryCaptureRequest", capture.optJSONObject("captureRequest"));
            pair.put("primaryCaptureResult", capture.optJSONObject("captureResult"));
            JSONObject decision = capture.optJSONObject("photonExposureDecision");
            JSONObject preview = decision != null ? decision.optJSONObject("preview") : null;
            pair.put("captureMode", preview != null ? preview.optString("mode", "unknown") : "unknown");
            pair.put("writerTelemetry", telemetry());
            JSONObject authority = pair.optJSONObject("previewExposureAuthority");
            boolean previewAvailable = authority != null
                    && authority.optInt("previewResultIso", -1) > 0
                    && authority.optLong("previewResultExposureTimeNs", -1L) > 0;
            pair.put("previewSnapshotAvailable", previewAvailable);
            pair.put("validExposurePair", completed != null && previewAvailable);
            pair.put("status", completed == null ? "unavailable_no_exact_callback_match"
                    : previewAvailable ? "matched" : "unavailable_preview_state");
            pair.put("previewMeasurementKind", "cached_metadata_not_sampled_display_frame");
            pair.put("displayPixelsSampled", false);
            pair.put("displayToneParityProven", false);
            pair.put("toneOrExposureChanged", false);
            String name = captureJsonPath.getFileName().toString();
            String stem = name.endsWith("_M9.json") ? name.substring(0, name.length() - 8)
                    : name.replaceFirst("\\.json$", "");
            Path sidecar = captureJsonPath.resolveSibling(stem + "_MONO_LIVEPAIR.json");
            pair.put("sidecarPath", sidecar.toString());
            pair.put("sidecarTransport", M9DiagnosticBurstSpool.SCHEMA);
            pair.put("publicExportState", "pending_existing_spool_export_not_yet_confirmed");
            byte[] pairBytes = pair.toString(2).getBytes(StandardCharsets.UTF_8);
            boolean staged = M9DiagnosticBurstSpool.stage(sidecar, pairBytes, "mono_live_pair");
            // Embedded copy survives a separate-sidecar export failure.
            pair.put("sidecarPrivateStaged", staged);
            if (!staged) pair.put("sidecarStageError", "private_spool_rejected_use_embedded_copy");
            capture.put("monoLivePair", pair);
            Log.d(TAG, BUILD + " capture=" + name + " matched=" + (completed != null)
                    + " staged=" + staged);
            return capture.toString(2).getBytes(StandardCharsets.UTF_8);
        } catch (Throwable error) {
            noteFailure(error);
            Log.e(TAG, BUILD + " attach/stage failed: " + error);
            if (capture != null) {
                try {
                    JSONObject failure = new JSONObject();
                    failure.put("buildMarker", BUILD);
                    failure.put("status", "diagnostic_export_exception");
                    failure.put("error", error.toString());
                    failure.put("validExposurePair", false);
                    failure.put("toneOrExposureChanged", false);
                    capture.put("monoLivePair", failure);
                    return capture.toString(2).getBytes(StandardCharsets.UTF_8);
                } catch (Exception ignored) { }
            }
            return original;
        }
    }
}
