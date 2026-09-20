package com.particlesdevs.photoncamera.m9.preview;

/** Controlled-input transport math. No scene fits, sensor-name branches, or exposure policy. */
public final class MonoPreviewMath2A {
    private MonoPreviewMath2A() {}
    public static double decode(double s) {
        return s <= 0.04045 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    }
    public static float[] srgbCurve(int limit) {
        int n = Math.max(2, Math.min(64, limit));
        float[] a = new float[n * 2];
        for (int i = 0; i < n; i++) {
            double s = (double) i / (n - 1);
            a[i * 2] = (float) decode(s); a[i * 2 + 1] = (float) s;
        }
        return a;
    }
    public static boolean validCurve(float[] c) {
        if (c == null || c.length < 4 || c.length > 8192 || (c.length & 1) != 0) return false;
        for (float v : c) if (!Float.isFinite(v) || v < 0 || v > 1) return false;
        if (Math.abs(c[0]) > 1e-6 || Math.abs(c[1]) > 1e-6 ||
                Math.abs(c[c.length-2]-1) > 1e-6 || Math.abs(c[c.length-1]-1) > 1e-6) return false;
        for (int i = 2; i < c.length; i += 2)
            if (c[i] <= c[i-2] || c[i+1] <= c[i-1]) return false;
        return true;
    }
    public static double invert(float[] c, double s) {
        s = Math.max(0, Math.min(1, s));
        for (int i = 2; i < c.length; i += 2) {
            if (s <= c[i+1]) return c[i-2] + (c[i]-c[i-2]) * (s-c[i-1]) / (c[i+1]-c[i-1]);
        }
        return 1;
    }
    /** High and low bytes in separate RGBA8 rows: interpolating the reconstruction is linear. */
    public static byte[] inverseTexture(float[][] curves) {
        if (curves == null || curves.length != 3) throw new IllegalArgumentException("curve_channels");
        byte[] bytes = new byte[1024 * 2 * 4];
        for (int c = 0; c < 3; c++) {
            if (!validCurve(curves[c])) throw new IllegalArgumentException("noninvertible_curve");
            for (int i = 0; i < 1024; i++) {
                int q = (int) Math.round(65535 * invert(curves[c], i / 1023.0));
                bytes[4*i+c] = (byte) (q >>> 8); bytes[4096+4*i+c] = (byte) q;
            }
        }
        return bytes;
    }
    public static double[] inverse3(double[] a) {
        if (a == null || a.length != 9) throw new IllegalArgumentException("matrix_size");
        for (double v : a) if (!Double.isFinite(v)) throw new IllegalArgumentException("matrix_nonfinite");
        double d = a[0]*(a[4]*a[8]-a[5]*a[7])-a[1]*(a[3]*a[8]-a[5]*a[6])+a[2]*(a[3]*a[7]-a[4]*a[6]);
        if (!Double.isFinite(d) || Math.abs(d) < 1e-5) throw new IllegalArgumentException("matrix_singular");
        double[] b = {a[4]*a[8]-a[5]*a[7],a[2]*a[7]-a[1]*a[8],a[1]*a[5]-a[2]*a[4],
                a[5]*a[6]-a[3]*a[8],a[0]*a[8]-a[2]*a[6],a[2]*a[3]-a[0]*a[5],
                a[3]*a[7]-a[4]*a[6],a[1]*a[6]-a[0]*a[7],a[0]*a[4]-a[1]*a[3]};
        for (int i = 0; i < 9; i++) {
            b[i] /= d;
            if (!Double.isFinite(b[i]) || Math.abs(b[i]) > 32) throw new IllegalArgumentException("matrix_ill_conditioned");
        }
        return b;
    }
    public static float[] undoColor(double[] ccm, double[] wb, int boost) {
        if (wb == null || wb.length != 3 || boost <= 0) throw new IllegalArgumentException("gain_missing");
        double[] a = inverse3(ccm);
        float[] col = new float[9];
        for (int r = 0; r < 3; r++) {
            if (!Double.isFinite(wb[r]) || wb[r] <= 0) throw new IllegalArgumentException("gain_invalid");
            for (int c = 0; c < 3; c++) col[c*3+r] = (float) (a[r*3+c] / (wb[r] * boost / 100.0));
        }
        return col;
    }
    public static int source1dIndex(int r, int g, int b, float[] y) {
        double q = Math.max(0, Math.min(65535, (double)y[0]*r + (double)y[1]*g + (double)y[2]*b));
        return ((int) Math.floor(q + 0.5)) >>> 5;
    }
}
