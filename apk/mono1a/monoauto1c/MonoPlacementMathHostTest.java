import com.particlesdevs.photoncamera.m9.export.MonoPlacementMath1A;

public final class MonoPlacementMathHostTest {
    private static void near(double a, double b, double eps, String name) {
        if (!Double.isFinite(a) || Math.abs(a-b) > eps)
            throw new AssertionError(name + " got=" + a + " expected=" + b);
    }
    public static void main(String[] args) {
        near(MonoPlacementMath1A.REFERENCE_TARGET, 0.0876544, 1e-12, "reference");
        near(MonoPlacementMath1A.evToReference(329.0/3750.0),
                -0.0012985712750254682, 1e-12, "typ246_global_median");
        near(MonoPlacementMath1A.evToReference(330.0/3750.0),
                -0.005677011785599775, 1e-12, "typ246_weighted_median");
        near(MonoPlacementMath1A.evToReference(0.067501776),
                0.3769010513907082, 1e-12, "cat_weighted_median");
        near(MonoPlacementMath1A.headroomEv(0.735,0.95),
                Math.log(0.95/0.735)/Math.log(2.0), 1e-12, "headroom");
        near(MonoPlacementMath1A.boundedByPositiveHeadroom(0.4,0.2), 0.2, 1e-12, "bounded");
        near(MonoPlacementMath1A.boundedByPositiveHeadroom(-0.3,0.2), -0.3, 1e-12, "negative_unbounded");
        near(MonoPlacementMath1A.applyEv(0.067501776,
                MonoPlacementMath1A.evToReference(0.067501776)),
                MonoPlacementMath1A.REFERENCE_TARGET, 1e-12, "placement_identity");
        near(MonoPlacementMath1A.sourceFromStoredCode(32768,2.0),
                (32768.0/65535.0)*2.0, 1e-12, "stored_code");
        System.out.println("MONOAUTO1C placement math PASS");
    }
}
