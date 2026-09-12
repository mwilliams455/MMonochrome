# RAWSCALAR1A device validation

Date: 2026-09-12
Branch: `apk/mono1a-rawscalar1a`
Build run: `34678686394`
Build head: `135293ca651c45cf846d3c109e51b68545eb9afd`
APK SHA-256: `52c5b67e6b643f4616a458b4330979af79a6a3e6ebd440cd36b64f26e327b0bc`

## Purpose

Test the SOURCE1E firmware conclusion on-device without promoting a new photographic source.

The current SOURCE1D M9-Y image remains primary. Existing XYZ-Y and GREEN controls remain present. RAWSCALAR1A adds a fourth same-RAW monochrome JPEG:

`*_MONO_RAWSCALAR1A.jpg`

## RAWSCALAR1A formation

The diagnostic source is formed before RGB colour rendering:

1. normalize the Bayer RAW using the existing black/white normalization;
2. apply the physical Camera2 LensShadingMap once in Bayer space;
3. neutral-normalize photosites using captured neutral metadata:
   - `R *= neutralG / neutralR`
   - `G *= 1`
   - `B *= neutralG / neutralB`
4. apply the existing MHC 5x5 geometry to the neutral-normalized CFA;
5. collapse reconstructed neutral-axis R/G/B by equal mean;
6. restore the lens-shading transport representation scale;
7. map 16-bit scalar to Leica 14-bit coordinate;
8. apply the unchanged Monochrom mode-0 pedestal/index arithmetic and canonical curve02.

This is a Xiaomi CFA-to-scalar reconstruction. It is not claimed to reproduce Leica CCD spectral sensitivity.

## Frozen controls

RAWSCALAR1A does not change:

- the primary SOURCE1D M9-Y path;
- curve02;
- Leica 14-bit coordinate;
- mode-0 contrast arithmetic;
- exposure policy;
- physical Camera2 LensShadingMap;
- DNG saving;
- JPEG quality.

It does not add TC20, HDR, temporal fusion, HSM, SAT3, SOURCECAL colour rendering, M9 colour reconstruction, M9 luma coefficients, or XYZ coefficients to the RAWSCALAR output.

## First device capture

For one capture, retain:

- primary JPEG;
- `_MONO_XYZY.jpg`;
- `_MONO_GREEN.jpg`;
- `_MONO_RAWSCALAR1A.jpg`;
- primary JSON sidecar;
- SOURCECAL/RAWSHADING sidecars if produced;
- DNG if practical.

Preferred first scene: neutral indoor or overcast scene with fine texture and a few coloured objects. A second strongly colour-discriminating daylight scene should follow.

## Pass/fail questions

1. Is RAWSCALAR free of 2x2 CFA checker/lattice artifacts in neutrals and coloured regions?
2. Is fine texture/detail materially worse than the M9-Y control?
3. Are local brightness relationships stable, rather than phase-dependent?
4. Do highlights and dense shadows retain the expected frozen Monochrom tone response?
5. Does RAWSCALAR behave sensibly on saturated red/green/blue objects without colour-phase artifacts?
6. Does the JSON report `rawScalar1A.schema = mmonochrome.rawscalar1a.v1`, `m9LumaCoefficientsApplied=false`, `xyzCoefficientsApplied=false`, and the canonical curve02 SHA?

Do not tune curve02 or exposure to fix a RAWSCALAR failure. Any failure at this gate belongs to the Xiaomi CFA-to-scalar reconstruction.

## On-device results — 2026-09-12

Two 12 MP same-RAW indoor sets were captured and compared: a bicycle/toy scene and a portrait scene. Each produced the primary M9-Y control, RAWSCALAR1A, GREEN, and XYZ-Y outputs.

### Structural gate

RAWSCALAR1A passes the first structural gate.

- No visible 2x2 CFA checker/lattice pattern was found in smooth walls, skin, bedding, cabinet surfaces, or the bicycle body.
- Quantitative 2-pixel parity testing after local high-pass removal found checker amplitudes effectively at zero relative to ordinary image high-frequency energy.
- Fine texture is retained in hair, skin, handlebar perforations, fabric, and specular edges.
- No obvious resolution collapse or phase-dependent local brightness instability was observed.

### Tone placement

RAWSCALAR1A is consistently brighter than the current sensor-space M9-Y control while remaining very close to XYZ-Y.

Bicycle/toy scene, uploaded JPEG domain:

- primary mean / median: `82.42 / 80`
- RAWSCALAR1A: `93.92 / 94`
- GREEN: `92.71 / 92`
- XYZ-Y: `95.06 / 96`
- RAWSCALAR1A vs primary correlation: `0.99546`
- RAWSCALAR1A vs XYZ-Y correlation: `0.99619`
- RAWSCALAR1A vs XYZ-Y: about `77.3%` of pixels within 5 codes and `95.7%` within 10 codes.

Portrait scene:

- primary mean / median: `66.49 / 61`
- RAWSCALAR1A: `79.26 / 75`
- GREEN: `77.85 / 74`
- XYZ-Y: `79.07 / 75`
- RAWSCALAR1A vs primary correlation: `0.99470`
- RAWSCALAR1A vs XYZ-Y correlation: `0.99499`
- RAWSCALAR1A vs XYZ-Y: about `75.6%` of pixels within 5 codes and `94.2%` within 10 codes.

The brighter placement must not be corrected by changing curve02 or exposure. It is a source-adapter consequence.

### Colour-discriminating evidence already present

The bicycle/toy scene contains a useful coloured spider graphic. GREEN suppresses much of that graphic while RAWSCALAR1A and XYZ-Y preserve a clear tonal separation. Therefore RAWSCALAR1A is not simply collapsing to the green-only control.

### Clipping / headroom

RAWSCALAR1A diagnostic counters remain small relative to 12,582,912 pixels.

Bicycle/toy scene:

- low clamp: `16,463` (`0.131%`)
- high clamp: `3,022` (`0.024%`)
- near-white output: `3,934` (`0.031%`)
- neutral-axis reconstruction high excursion: `69,070` (`0.549%`)

Portrait scene:

- low clamp: `191` (`0.0015%`)
- high clamp: `0`
- near-white output: `0`
- neutral-axis reconstruction high excursion: `8,179` (`0.065%`)

No clipping-based rejection is justified from these two captures.

### Important interpretation

RAWSCALAR1A uses the live `AsShotNeutral`-equivalent neutral point before reconstruction. The two captures used materially different neutral vectors:

- bicycle/toy: `[0.6015625, 1.0, 0.357421875]`
- portrait: `[0.517578125, 1.0, 0.408203125]`

That means RAWSCALAR1A is an illuminant-normalized scene-luminance estimator, not a fixed spectral-response model. Its close agreement with the independently derived XYZ-Y counterfactual is therefore understandable and useful, but it is also the reason RAWSCALAR1A must not yet be promoted as a Leica Monochrom spectral substitute.

The original M Monochrom sensor records without a colour filter array; a physical monochrome photosite does not apply per-shot AWB-style R/B reweighting before detection. Therefore the next spectral-proxy experiment should be fixed with respect to illuminant rather than driven directly by the live neutral vector.

## Decision

`RAWSCALAR1A`: **STRUCTURAL PASS / PHOTOGRAPHIC PROMOTION HOLD**.

Keep RAWSCALAR1A as a successful proof that a full-resolution pre-colour scalar can be constructed on-device without Bayer lattice artifacts. Do not promote it over SOURCE1D yet.

The next step is not another tone change. It is to define and test a fixed-spectral raw-domain proxy (`RAWSCALAR1B`) while keeping the same MHC geometry and frozen Leica curve02 stage. Candidate weighting must be justified from sensor/calibration evidence, not chosen by visual preference.
