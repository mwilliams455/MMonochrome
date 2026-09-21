package com.particlesdevs.photoncamera.m9.exposure;

/** Immutable physical-ISO exposure intent. M9 shared-plan architecture, no M9 render math. */
public final class MonoExposurePlan1A {
    public static final String REVISION = "MONOAUTO1A_EXPOSUREPLAN";
    public static final long MAX_AGE_NS = 1500000000L;
    public final long id, epoch, createdNs, sensorTimestampNs, observedExposureNs, exposureNs;
    public final int observedIso, iso, postRawBoost, flags;
    public final double autoEv;
    public final String cameraKey, autoReason;
    public final Controls controls;

    public MonoExposurePlan1A(long id, long epoch, long createdNs, long sensorTimestampNs,
            String cameraKey, Controls controls, int observedIso, long observedExposureNs,
            int iso, long exposureNs, int postRawBoost, double autoEv, String autoReason, int flags) {
        if (id <= 0 || epoch <= 0 || createdNs <= 0 || cameraKey == null || controls == null
                || observedIso <= 0 || observedExposureNs <= 0 || iso <= 0 || exposureNs <= 0
                || postRawBoost <= 0 || !Double.isFinite(autoEv))
            throw new IllegalArgumentException("invalid_monochrom_exposure_plan");
        this.id=id; this.epoch=epoch; this.createdNs=createdNs; this.sensorTimestampNs=sensorTimestampNs;
        this.cameraKey=cameraKey; this.controls=controls; this.observedIso=observedIso;
        this.observedExposureNs=observedExposureNs; this.iso=iso; this.exposureNs=exposureNs;
        this.postRawBoost=postRawBoost; this.autoEv=autoEv; this.autoReason=autoReason; this.flags=flags;
    }
    public static double energy(int iso, long exposureNs) { return (double) iso * exposureNs; }
    public double previewScale() { return energy(iso, exposureNs)/energy(observedIso, observedExposureNs); }
    public boolean validFor(String camera, Controls current, long token, long now) {
        return epoch==token && cameraKey.equals(camera) && controls.equals(current)
                && now>=createdNs && now-createdNs<=MAX_AGE_NS;
    }
    public static float boundedScale(double value) {
        if(!Double.isFinite(value) || value<=0) return 1.0f;
        return (float)Math.max(0.0625,Math.min(16.0,value));
    }
    /** Hardware reference remains neutral; user EV is applied once by the plan. */
    public static double combinedEv(double settingsEv, double manualSteps, double evPerStep) {
        double ev=settingsEv+manualSteps*evPerStep;
        if(!Double.isFinite(ev)) throw new IllegalArgumentException("invalid_ev");
        return ev;
    }
    public static boolean assistEligible(Controls c) {
        return "PHOTO".equals(c.mode) && !c.tripod && c.manualIso==0 && c.manualExposureNs==0
                && Math.abs(c.userEv)<1e-9;
    }
    public static final class Controls {
        public final String mode, meteringKey;
        public final double userEv;
        public final long manualExposureNs;
        public final int manualIso, isoLimit, oisMode;
        public final float balance, shutterLimit;
        public final boolean tripod;
        public Controls(String mode, double userEv, long manualExposureNs, int manualIso,
                boolean tripod, float balance, int isoLimit, float shutterLimit, int oisMode, String meteringKey) {
            if(mode==null || meteringKey==null || !Double.isFinite(userEv) || manualExposureNs<0 || manualIso<0
                    || !Float.isFinite(balance) || balance<=0 || !Float.isFinite(shutterLimit))
                throw new IllegalArgumentException("invalid_monochrom_controls");
            this.mode=mode;this.userEv=userEv;this.manualExposureNs=manualExposureNs;this.manualIso=manualIso;
            this.tripod=tripod;this.balance=balance;this.isoLimit=isoLimit;this.shutterLimit=shutterLimit;
            this.oisMode=oisMode;this.meteringKey=meteringKey;
        }
        @Override public boolean equals(Object other) {
            if(!(other instanceof Controls)) return false;
            Controls c=(Controls)other;
            return mode.equals(c.mode) && Double.doubleToLongBits(userEv)==Double.doubleToLongBits(c.userEv)
                    && manualExposureNs==c.manualExposureNs && manualIso==c.manualIso && tripod==c.tripod
                    && Float.floatToIntBits(balance)==Float.floatToIntBits(c.balance) && isoLimit==c.isoLimit
                    && Float.floatToIntBits(shutterLimit)==Float.floatToIntBits(c.shutterLimit)
                    && oisMode==c.oisMode && meteringKey.equals(c.meteringKey);
        }
        @Override public int hashCode() {
            return java.util.Objects.hash(mode,userEv,manualExposureNs,manualIso,tripod,balance,
                    isoLimit,shutterLimit,oisMode,meteringKey);
        }
    }
}
