# RAWSCALAR1B PROMOTION1A

Date: 2026-09-12

## Decision

RAWSCALAR1B FIXEDD65 is provisionally promoted as the selected Xiaomi -> original M Monochrom scalar bridge.

This promotion changes **selection only**. It does not change:

- physical Camera2 LensShadingMap policy;
- black/white normalization;
- MHC 5x5 spatial reconstruction;
- fixed D65 camera-neutral derivation;
- equal-mean scalar collapse;
- Leica 14-bit working coordinate;
- pedestal policy;
- canonical Monochrom curve02;
- JPEG quality;
- DNG persistence;
- exposure/capture policy.

The promoted output must continue to be described as a **fixed Xiaomi camera spectral proxy**, not Leica CCD quantum-efficiency truth.

## Additional outdoor confirmation capture

Capture stem: `IMG_20260912_084112_1789198872486_00`

Scene: high-contrast overcast landscape with dark tree canopy, grass/path foreground and bright cloud field.

The uploaded JPEG copies were 1536x2048, so the numbers below describe those review copies. They are suitable for relative output comparison but are not a replacement for full-resolution artifact inspection.

| Output | Mean | Median | P90 | P95 | P99 | >=224 | >=240 |
|---|---:|---:|---:|---:|---:|---:|---:|
| Primary M9-Y control | 74.44 | 36 | 196 | 205 | 216 | 0.207% | 0.004% |
| RAWSCALAR1B D65 | 78.17 | 36 | 207 | 215 | 225 | 1.503% | 0.022% |
| RAWSCALAR1A live neutral | 84.31 | 40 | 218 | 225 | 235 | 6.092% | 0.282% |
| GREEN | 86.63 | 47 | 216 | 224 | 234 | 5.466% | 0.229% |
| XYZ-Y | 85.79 | 45 | 215 | 223 | 233 | 4.998% | 0.208% |

Pairwise correlation:

- RAWSCALAR1B vs primary: ~0.99936
- RAWSCALAR1B vs RAWSCALAR1A: ~0.99957

Useful regional observation from the same review copies:

- RAWSCALAR1B raised the bright sky by roughly 9-11 JPEG codes relative to the primary control;
- the central dark tree moved only roughly 2-3 codes;
- the lower-left grass was essentially unchanged/slightly darker relative to primary;
- RAWSCALAR1A remained materially brighter than 1B in sky, tree and foreground.

This is not behaving like a simple global exposure lift. It is consistent with the scalar-source weighting change remaining material-dependent while the downstream Leica curve stays frozen.

No obvious CFA checker/lattice failure was visible in the supplied review copies. Full-resolution inspection remains the authority for fine periodic artifacts.

## Promotion implementation

Branch:

`apk/mono1a-rawscalar1b-promoted1a`

Promotion overlay:

`apk/mono1a/promote-rawscalar1b.py`

Built code commit:

`0ff4bbbcf5b4b7bd10d9d5caf907f7059d1f5989`

GitHub Actions run:

`34684736282`

Artifact:

`MMonochrome-RAWSCALAR1B-PROMOTED1A`

APK:

`MMonochrome-MONO1A-26681-debug.apk`

APK SHA-256:

`f0706a860bb9323687db515122b36f46f891dd26bee8ecb4d68e63b37411684b`

The CI source-assembly verification and Android build both passed.

## Output-bank behavior after promotion

Expected normal JPEG:

- `<stem>.jpg` = promoted RAWSCALAR1B FIXEDD65

Retained diagnostics:

- `<stem>_MONO_RAWSCALAR1A.jpg`
- `<stem>_MONO_XYZY.jpg`
- `<stem>_MONO_GREEN.jpg`
- `<stem>_MONO_M9Y_CONTROL.jpg`
- DNG and diagnostics JSONs

The old duplicate `<stem>_MONO_RAWSCALAR1B_D65.jpg` auxiliary is intentionally removed because RAWSCALAR1B is now the primary payload.

## Next device gate

Install the PROMOTED1A APK and take one ordinary scene.

Verify:

1. the normal `<stem>.jpg` now visually matches the former RAWSCALAR1B D65 rendering;
2. `_MONO_M9Y_CONTROL.jpg`, `_MONO_RAWSCALAR1A.jpg`, `_MONO_XYZY.jpg`, and `_MONO_GREEN.jpg` are still produced;
3. DNG persists normally;
4. diagnostics report `MONO1A_RAWSCALAR1B_PROMOTED1A`, `photographicOutputSelected=true`, `perShotNeutralUsed=false`, and Leica spectral truth false;
5. no crash, freeze, or visible quality regression is introduced by the ownership swap.

Do not retune tone or exposure during this gate.
