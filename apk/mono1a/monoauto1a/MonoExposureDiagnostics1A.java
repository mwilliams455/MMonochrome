package com.particlesdevs.photoncamera.m9.exposure;
import org.json.JSONObject;

public final class MonoExposureDiagnostics1A {
    private MonoExposureDiagnostics1A() {}
    public static JSONObject plan(MonoExposurePlan1A p) {
        JSONObject o=new JSONObject();
        try {
            o.put("revision",MonoExposurePlan1A.REVISION).put("id",p.id).put("epoch",p.epoch)
                    .put("cameraKey",p.cameraKey).put("createdElapsedNs",p.createdNs)
                    .put("observationSensorTimestampNs",p.sensorTimestampNs)
                    .put("observedIso",p.observedIso).put("observedExposureNs",p.observedExposureNs)
                    .put("iso",p.iso).put("exposureNs",p.exposureNs).put("userEv",p.controls.userEv)
                    .put("manualIso",p.controls.manualIso).put("manualExposureNs",p.controls.manualExposureNs)
                    .put("tripod",p.controls.tripod).put("autoAssistEv",p.autoEv).put("autoAssistReason",p.autoReason)
                    .put("previewScaleAtObservation",p.previewScale()).put("postRawBoostAtObservation",p.postRawBoost)
                    .put("nominalEnergyIsoNs",MonoExposurePlan1A.energy(p.iso,p.exposureNs))
                    .put("exposureFlags",p.flags).put("assistAppliedAgainAtCapture",false)
                    .put("renderedDarkScenePlacementPorted",false).put("allocation2GPorted",false)
                    .put("rendererAndDngMathChanged",false);
        } catch(Exception e) { throw new IllegalStateException("monochrom_plan_json",e); }
        return o;
    }
    public static void attach(JSONObject o,MonoExposureStore1A.Selection selected) {
        try {
            if(selected==null) {o.put("monoExposurePlanStatus","legacy_non_photo_route");return;}
            o.put("monoExposurePlanSelectionReason",selected.reason);
            if(selected.plan!=null)o.put("monoExposurePlan1A",plan(selected.plan));
            o.put("monoPlanDrawElapsedNs",selected.drawElapsedNs).put("monoPlanTextureTimestampNs",selected.textureTimestampNs)
                    .put("monoPlanDrawScale",selected.scale).put("displayCompositorPresentationProven",false);
        }catch(Exception e){throw new IllegalStateException("monochrom_plan_attachment",e);}
    }
}
