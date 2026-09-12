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
