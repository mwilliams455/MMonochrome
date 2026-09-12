# RAWSCALAR1B PROMOTED1A DEVICE VALIDATION

Date: 2026-09-12

## Result

PROMOTED1A passed its first on-device ordinary-scene validation.

Capture stem:

`IMG_20260912_102047_1789204847548_00`

The normal `<stem>.jpg` is now RAWSCALAR1B FIXEDD65, and the retained diagnostic bank is present:

- `_MONO_M9Y_CONTROL.jpg`
- `_MONO_RAWSCALAR1A.jpg`
- `_MONO_GREEN.jpg`
- `_MONO_XYZY.jpg`

The old duplicate `_MONO_RAWSCALAR1B_D65.jpg` is correctly absent because RAWSCALAR1B is now the primary payload.

The primary sidecar reports:

- renderer schema `mmonochrome.mono1a.rawscalar1b.promoted1a.v1`;
- `rawScalar1B.photographicOutputSelected = true`;
- `rawScalar1B.perShotNeutralUsed = false`;
- `rawScalar1B.referenceIlluminant = D65`;
- `monochromPrimarySource = RAWSCALAR1B_FIXED_D65`;
- `monochromPrimaryLeicaSpectralTruth = false`;
- canonical curve02 SHA-256 `7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752`;
- `jpegSaved = true`;
- `dngSaved = true`.

This closes the promotion wiring gate: the primary selection swap is active on device and did not fall back to the old M9-Y control.

## Capture metadata

- physical camera: `2`
- RAW: 4096x3072 RGGB
- ISO: `143`
- exposure: `26.643356 ms`
- aperture: `f/1.63`
- focal length: `8.72 mm`
- live neutral: `[0.4150390625, 1, 0.5146484375]`
- fixed RAWSCALAR1B neutral: `[0.4909944832, 1, 0.7047154903]`

Relative live-neutral gain versus fixed-D65 gain:

- red: about `+0.242 EV` in the live-neutral path;
- green: unchanged;
- blue: about `+0.453 EV` in the live-neutral path.

This is another useful illuminant-dependent separation case: RAWSCALAR1A is expected to move materially relative to the fixed-D65 primary even though both share the same frozen downstream Leica curve.

## Uploaded review-copy statistics

The uploaded JPEGs are 1536x2048 review copies while the renderer reports a native 3072x4096 finished bitmap. The numbers below are therefore for relative comparison only.

| Output | Mean | Median | P90 | P95 | P99 | <=48 | >=224 | >=240 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| RAWSCALAR1B promoted primary | 66.48 | 53 | 142 | 176 | 220 | 43.53% | 0.975% | 0.841% |
| M9-Y control | 61.45 | 49 | 132 | 166 | 212 | 49.88% | 0.920% | 0.753% |
| RAWSCALAR1A live neutral | 73.72 | 60 | 154 | 187 | 230 | 38.24% | 1.144% | 0.922% |
| GREEN | 73.37 | 61 | 151 | 185 | 230 | 38.71% | 1.089% | 0.923% |
| XYZ-Y | 74.27 | 61 | 155 | 189 | 230 | 37.68% | 1.166% | 0.917% |

The promoted primary is again tonally intermediate between the restrained M9-Y historical control and the brighter live-neutral / green / XYZ-Y counterfactuals.

Pairwise comparison of the promoted primary review copy:

- vs M9-Y control: correlation `~0.99910`, mean absolute difference `~5.05` JPEG codes;
- vs RAWSCALAR1A: correlation `~0.99868`, mean absolute difference `~7.24` codes;
- vs GREEN: correlation `~0.99639`, mean absolute difference `~7.08` codes;
- vs XYZ-Y: correlation `~0.99848`, mean absolute difference `~7.80` codes.

The primary is therefore not accidentally identical to any diagnostic output.

## Subject-region behavior

Approximate review-copy region means:

| Region | M9-Y | RAWSCALAR1B primary | RAWSCALAR1A | GREEN | XYZ-Y |
|---|---:|---:|---:|---:|---:|
| hair | 29.2 | 32.0 | 36.3 | 36.5 | 36.7 |
| cheek/face | 110.4 | 118.1 | 127.5 | 125.2 | 128.7 |
| ear | 73.7 | 80.5 | 88.2 | 84.7 | 89.0 |
| hand | 104.2 | 112.9 | 122.2 | 117.1 | 122.8 |
| shoulder | 93.6 | 101.6 | 111.5 | 108.8 | 113.0 |

This is a useful portrait validation result. RAWSCALAR1B gives the subject more separation than the M9-Y control without the larger live-neutral lift seen in RAWSCALAR1A. Hair remains dark with internal structure rather than being raised toward the skin values.

No obvious CFA checker/lattice artifact is visible in the supplied review copies. Full-resolution device JPEG inspection remains authoritative for fine periodic artifacts.

## Highlight behavior

The scene contains a bright lamp/window-like region and bright skin/object highlights. The promoted primary remains controlled:

- JPEG `>=224`: about `0.975%`;
- JPEG `>=240`: about `0.841%`.

The primary renderer diagnostics report `nearWhiteOutputCount = 80701` over 12,582,912 native pixels, while the old M9-Y control path reports a substantially smaller mean but similar extreme-highlight occupancy in the review JPEG. This supports the interpretation that the selection change primarily alters material/tonal placement rather than introducing a broad clipping failure.

## Performance observation

The full diagnostic-bank render took about `5433 ms`, but the selected RAWSCALAR1B native render itself reports only about `118.8 ms` (`nativeRenderNs = 118773906`). DNG persistence took about `489 ms`.

The current multi-output diagnostic build is therefore not a good proxy for eventual single-output performance. Do not trade JPEG quality for speed while diagnostics remain enabled. If the diagnostic bank is later reduced, measure performance again before optimizing the photographic renderer.

## Decision

**RAWSCALAR1B PROMOTED1A is device-validated as the working primary Xiaomi -> original M Monochrom scalar bridge.**

The defensible wording remains:

> RAWSCALAR1B is a fixed Xiaomi camera spectral proxy feeding the recovered Leica scalar/tone stage. It is not recovered Leica Monochrom CCD quantum-efficiency behavior.

Keep frozen:

- canonical Monochrom curve02;
- Leica 14-bit coordinate mapping;
- physical LensShadingMap policy;
- MHC kernel;
- JPEG quality;
- DNG persistence;
- exposure/capture policy.

## Next research target

Do not spend the next block retuning tone by eye. The highest-value remaining fidelity work is upstream of the frozen Leica curve:

1. continue firmware producer-boundary research for the native Monochrom scalar source;
2. investigate whether the unresolved 16 x 2 x 2050-byte ISO-aligned bank / `LoadISODataL1` path contains scalar-domain noise/detail/shading behavior relevant to the Monochrom image before `Process_Contrast`;
3. retain RAWSCALAR1A/GREEN/XYZ-Y/M9-Y only as diagnostics until enough material-separation evidence exists to simplify them;
4. keep full-resolution sharpness / periodic-artifact checks separate from spectral-bridge validation.
