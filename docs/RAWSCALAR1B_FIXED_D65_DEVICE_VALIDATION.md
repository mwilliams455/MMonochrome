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

## First on-device result — overcast daylight landscape

Capture stem: `IMG_20260912_084149_1789198909517_00`.

Capture metadata:

```text
ISO 50
1.513640 ms (~1/661 s)
RGGB
black 64 / white 1023
live neutral = [0.3603515625, 1.0, 0.5908203125]
fixed D65 neutral = [0.49099448, 1.0, 0.70471549]
fixed D65 gains = [2.03668284, 1.0, 1.41901243]
perShotNeutralUsed = false
curve02 SHA = 7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752
```

The live-neutral RAWSCALAR1A gains implied by this capture are approximately `[2.7751, 1.0, 1.6926]`. Relative to fixed D65, RAWSCALAR1A therefore boosts the R photosites about 1.363x (+0.446 EV) and B about 1.193x (+0.254 EV) before the same MHC/scalar-collapse stage. The experiment is therefore exercising a materially different spectral weighting, not a near-identity setting.

Uploaded 1536x2048 JPEG preview statistics:

| Output | Mean | Median | P90 | P95 | P99 | <=48 | >=224 |
|---|---:|---:|---:|---:|---:|---:|---:|
| primary M9-Y control | 95.65 | 53 | 202 | 208 | 218 | 47.5% | 0.17% |
| RAWSCALAR1B D65 | 100.69 | 53 | 211 | 217 | 226 | 47.3% | 1.95% |
| RAWSCALAR1A live neutral | 108.20 | 61 | 222 | 227 | 236 | 42.5% | 8.21% |
| GREEN | 110.25 | 70 | 221 | 227 | 235 | 36.5% | 7.77% |
| XYZ-Y | 109.36 | 68 | 220 | 226 | 235 | 37.6% | 7.08% |

Pairwise structure is extremely stable. RAWSCALAR1B vs primary has correlation `0.99940`; an affine fit gives slope `1.05398`, intercept `-0.1278`, RMSE `2.71`, MAE `2.19`, P95 absolute residual `5.17`. RAWSCALAR1B vs RAWSCALAR1A has correlation `0.99962`, affine RMSE `2.24`, MAE `1.82`, P95 absolute residual `4.20`.

The fixed-D65 candidate is not simply a global darkening of RAWSCALAR1A. Broad-region means (primary / 1B / 1A) are:

```text
sky top 45%       171.07 / 180.74 / 191.79
horizon middle    47.15  / 48.45  / 54.62
ground bottom 40% 29.10  / 30.32  / 34.37
center path        27.63  / 30.34  / 34.52
```

After removing the best global affine relationship to the primary control, RAWSCALAR1B still has small spatial/material residuals (for example center path about +1.35 code values and right-ground region about -2.28). That is the expected signature of changed CFA spectral weighting rather than a pure tone/exposure shift.

Visual inspection and the output statistics show no obvious CFA checker/lattice failure in RAWSCALAR1B. The D65 candidate also retains the dark foreground while giving the cloud field more separation than the M9-Y control. Its median remains exactly 53 in this scene, while RAWSCALAR1A rises to 61. Highlight pressure remains controlled: 1B has no meaningful 240+ population (0.014%) and its native diagnostic reports zero high clamps and zero near-white output count.

### First-result decision

**RAWSCALAR1B passes the first outdoor structural/photometric gate and is the stronger architecture than RAWSCALAR1A.**

Reason: it removes shot-dependent AWB/neutral weighting, keeps the same spatial reconstruction and Leica curve, remains artifact-free in this capture, and produces a materially different but controlled spectral response. RAWSCALAR1A should remain as a diagnostic control rather than the preferred source bridge.

This is not yet a final promotion to Leica spectral truth. A Bayer Xiaomi sensor cannot recover the original Monochrom CCD quantum-efficiency curve from firmware alone. The next validation must therefore test *stability and material ordering*, not visual similarity to the current primary.

## Next gate

Keep the current APK; no new renderer build is justified yet.

Capture at least one non-daylight scene with mixed coloured materials — preferably indoor warm/tungsten illumination — while retaining the same five-output bank. The decisive comparison is RAWSCALAR1A vs RAWSCALAR1B on red, green, blue, skin/fabric/wood or similarly spectrally distinct surfaces. RAWSCALAR1B should keep a fixed response while 1A changes with the live neutral. If 1B remains artifact-free and local brightness ordering stays plausible across that illuminant change, promote fixed-D65 as the provisional Xiaomi-to-Monochrom scalar bridge and retire live-neutral 1A from candidate status.

## Promotion rule

Do not promote RAWSCALAR1B merely because it looks darker, brighter, or more dramatic. Promotion requires stable local-material ordering, no CFA artifacts, acceptable detail, healthy clipping, and better conceptual consistency across illuminants than the live-neutral RAWSCALAR1A path.

The fixed D65 proxy is still not Leica CCD spectral truth. If it passes, it becomes the stronger Xiaomi-to-scalar bridge for further validation, not evidence that the original Leica sensor QE curve has been recovered.
