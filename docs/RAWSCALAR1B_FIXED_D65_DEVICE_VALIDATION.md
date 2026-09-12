# RAWSCALAR1B FIXEDD65 device validation

Date: 2026-09-12
Branch: `apk/mono1a-rawscalar1b-fixedd65`
Build run: `34680641558`
Build head: `48be9caeb6c76b6a0888ac9cb9d2758feb1aaf1b`
APK SHA-256: `d27f941696f9fad9ddcce56bf629dfefcc30f538589890df9c871c0f4c83cac8`

## Why this experiment exists

RAWSCALAR1A passed the first structural gate: the photosite-domain Bayer reconstruction produced a clean full-resolution monochrome image without an obvious 2x2 CFA lattice or unacceptable texture loss. Its remaining conceptual problem is that it uses the live `SENSOR_NEUTRAL_COLOR_POINT`, so its R/G/B CFA normalization changes from shot to shot with illuminant/AWB state.

That is not a suitable final proxy for a physical monochrome detector whose spectral response is fixed.

RAWSCALAR1B therefore changes one thing only: the CFA spectral proxy is fixed to a D65 camera-neutral derived from immutable `CameraCharacteristics` metadata. It is a Xiaomi sensor translation experiment, not a claim about the Leica CCD spectral response.

## Fixed D65 proxy

The Xiaomi physical main-camera metadata advertises D65 as reference illuminant 1 (`21`). RAWSCALAR1B computes once per render from immutable characteristics:

```text
XYZ_D65 -> (CalibrationTransform_D65 * ColorTransform_D65) -> camera response
camera response -> normalize G = 1
```

For the camera metadata observed in the RAWSCALAR1A captures this predicts approximately:

```text
fixed camera neutral ~= [0.4910, 1.0000, 0.7048]
fixed CFA gains      ~= [2.0367, 1.0000, 1.4189]
```

The actual values used by the device are written to the JSON sidecar as `rawScalar1B.fixedNeutral*` and `rawScalar1B.fixedGain*`. The render does not read the live capture neutral for its RAWSCALAR1B pixel formation. The live neutral is logged only for comparison.

## What is frozen

RAWSCALAR1B reuses the exact same native RAWSCALAR1A renderer and changes only the neutral arguments supplied to it. Therefore the following remain unchanged:

- same black/white-normalized Bayer source;
- same physical Camera2 LensShadingMap application;
- same MHC 5x5 spatial reconstruction;
- same equal mean collapse of the reconstructed scalar axes;
- same lens-shading representation-scale restoration;
- same Leica 14-bit coordinate;
- same synthetic pedestal policy;
- same canonical Monochrom curve02;
- same JPEG quality and DNG persistence;
- no exposure or tone compensation.

No M9 luma coefficients, XYZ luma coefficients, SOURCECAL render transform, HSM, SAT3, TC20, HDR or temporal fusion are added to RAWSCALAR1B.

## Output bank

One capture should now retain:

- primary JPEG — existing provisional M9-Y control;
- `_MONO_RAWSCALAR1A.jpg` — live-neutral photosite-domain control;
- `_MONO_RAWSCALAR1B_D65.jpg` — fixed-D65 photosite-domain candidate;
- `_MONO_XYZY.jpg` — scene-luminance counterfactual;
- `_MONO_GREEN.jpg` — green-only control;
- primary JSON sidecar.

## First comparison

Use an ordinary indoor scene similar to the existing validation capture first. A second daylight scene should contain clearly red, green and blue objects or materials.

Primary questions:

1. Does RAWSCALAR1B remain free of CFA checker/lattice artifacts?
2. Does it preserve the same fine detail as RAWSCALAR1A?
3. How much do local material brightness relationships change between 1A and 1B?
4. Does the fixed proxy avoid the large shot-to-shot spectral weighting change implied by live neutral metadata?
5. Does the fixed proxy produce plausible red/green/blue separation without collapsing toward green-only behavior?
6. Are clipping and shadow-floor statistics still healthy?
7. Does the JSON confirm `perShotNeutralUsed=false` and the canonical curve02 SHA?

## Promotion rule

Do not promote RAWSCALAR1B merely because it looks darker, brighter, or more dramatic. Promotion requires stable local-material ordering, no CFA artifacts, acceptable detail, healthy clipping, and better conceptual consistency across illuminants than the live-neutral RAWSCALAR1A path.

The fixed D65 proxy is still not Leica CCD spectral truth. If it passes, it becomes the stronger Xiaomi-to-scalar bridge for further validation, not evidence that the original Leica sensor QE curve has been recovered.
