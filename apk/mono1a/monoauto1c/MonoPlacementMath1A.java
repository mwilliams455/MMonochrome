package com.particlesdevs.photoncamera.m9.export;

/** Diagnostic-only source-placement math. Never mutates capture, render, or DNG samples. */
public final class MonoPlacementMath1A {
    public static final String REVISION = "MONOAUTO1C_PLACEMENTPROBE1A";
    /** Recovered M9 TC20 scene-key reference: 0.107 * 8192 / 10000. */
    public static final double REFERENCE_TARGET = 0.107 * (8192.0 / 10000.0);
    private MonoPlacementMath1A() {}

    public static double log2(double v) {
        return Math.log(Math.max(v, 1.0e-12)) / Math.log(2.0);
    }

    public static double evToReference(double observed) {
        if (!Double.isFinite(observed) || observed <= 0.0) return Double.NaN;
        return log2(REFERENCE_TARGET / observed);
    }

    public static double headroomEv(double tail, double limit) {
        if (!Double.isFinite(tail) || tail <= 0.0 || !Double.isFinite(limit) || limit <= 0.0)
            return Double.NaN;
        return log2(limit / tail);
    }

    public static double boundedByPositiveHeadroom(double requestEv, double headroomEv) {
        if (!Double.isFinite(requestEv) || !Double.isFinite(headroomEv)) return Double.NaN;
        if (requestEv <= 0.0) return requestEv;
        return Math.min(requestEv, Math.max(0.0, headroomEv));
    }

    public static double applyEv(double value, double ev) {
        if (!Double.isFinite(value) || !Double.isFinite(ev)) return Double.NaN;
        return value * Math.pow(2.0, ev);
    }

    public static double sourceFromStoredCode(int code, double sourceUnitsPerWhite) {
        if (code < 0 || code > 65535 || !Double.isFinite(sourceUnitsPerWhite) || sourceUnitsPerWhite <= 0.0)
            return Double.NaN;
        return (code / 65535.0) * sourceUnitsPerWhite;
    }
}
