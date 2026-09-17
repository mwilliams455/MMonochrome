package com.particlesdevs.photoncamera.m9.render;

/** Portable Bayer lattice resolver shared with the M9 source-adapter contract. */
public final class M9CfaResolver {
    public enum Pattern {
        RGGB(0), GRBG(1), GBRG(2), BGGR(3), UNSUPPORTED(-1);
        public final int camera2Value;
        Pattern(int camera2Value) { this.camera2Value = camera2Value; }
    }
    public enum Site { RED, GREEN_1, GREEN_2, BLUE }
    private M9CfaResolver() {}
    public static Pattern fromCamera2(int value) {
        switch (value) {
            case 0: return Pattern.RGGB;
            case 1: return Pattern.GRBG;
            case 2: return Pattern.GBRG;
            case 3: return Pattern.BGGR;
            default: return Pattern.UNSUPPORTED;
        }
    }
    public static boolean isSupported(int value) { return fromCamera2(value) != Pattern.UNSUPPORTED; }
    public static Site colorAt(int localX, int localY, Pattern pattern, int originX, int originY) {
        if (pattern == null || pattern == Pattern.UNSUPPORTED) throw new IllegalArgumentException("unsupported CFA pattern");
        int x = Math.floorMod(localX + originX, 2);
        int y = Math.floorMod(localY + originY, 2);
        switch (pattern) {
            case RGGB:
                if (y == 0) return x == 0 ? Site.RED : Site.GREEN_1;
                return x == 0 ? Site.GREEN_2 : Site.BLUE;
            case GRBG:
                if (y == 0) return x == 0 ? Site.GREEN_1 : Site.RED;
                return x == 0 ? Site.BLUE : Site.GREEN_2;
            case GBRG:
                if (y == 0) return x == 0 ? Site.GREEN_1 : Site.BLUE;
                return x == 0 ? Site.RED : Site.GREEN_2;
            case BGGR:
                if (y == 0) return x == 0 ? Site.BLUE : Site.GREEN_1;
                return x == 0 ? Site.GREEN_2 : Site.RED;
            default: throw new IllegalArgumentException("unsupported CFA pattern");
        }
    }
    public static int lensShadingChannelAt(int localX, int localY, Pattern pattern, int originX, int originY) {
        Site site = colorAt(localX, localY, pattern, originX, originY);
        if (site == Site.RED) return 0;
        if (site == Site.BLUE) return 3;
        return Math.floorMod(localY + originY, 2) == 0 ? 1 : 2;
    }
    public static int lensShadingChannelAt(int localX, int localY, int camera2Pattern, int originX, int originY) {
        Pattern p = fromCamera2(camera2Pattern);
        if (p == Pattern.UNSUPPORTED) throw new IllegalArgumentException("unsupported CFA pattern");
        return lensShadingChannelAt(localX, localY, p, originX, originY);
    }
    public static String localPhaseName(Pattern p, int ox, int oy) {
        if (p == null || p == Pattern.UNSUPPORTED) return "UNSUPPORTED";
        return symbol(colorAt(0,0,p,ox,oy))+symbol(colorAt(1,0,p,ox,oy))+symbol(colorAt(0,1,p,ox,oy))+symbol(colorAt(1,1,p,ox,oy));
    }
    private static String symbol(Site s) {
        switch(s){ case RED:return "R"; case BLUE:return "B"; default:return "G"; }
    }
}
