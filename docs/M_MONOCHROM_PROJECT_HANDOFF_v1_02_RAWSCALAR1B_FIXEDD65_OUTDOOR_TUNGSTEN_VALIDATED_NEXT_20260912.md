# M MONOCHROM PROJECT HANDOFF v1.02

## RAWSCALAR1B FIXEDD65 — OUTDOOR + TUNGSTEN VALIDATED — PROMOTION DECISION NEXT

**Date:** 2026-09-12  
**Project:** Original Leica M Monochrom (M9-generation, firmware 1.022) photographic rendering port to Xiaomi 15 Ultra / PhotonCamera  
**Repository:** `mwilliams455/MMonochrome`  
**Current Android branch:** `apk/mono1a-rawscalar1b-fixedd65`  
**Branch head before this handoff:** `3ce5bdae86d219e41357e74fed18ab35f393cea2`  
**Build run:** `34680641558`  
**APK SHA-256:** `d27f941696f9fad9ddcce56bf629dfefcc30f538589890df9c871c0f4c83cac8`

---

## 1. Mission

Reproduce the photographic rendering behavior of the original Leica M Monochrom as faithfully as practical on the Xiaomi 15 Ultra, using firmware evidence wherever possible.

The project is deliberately **firmware-first**:

- recovered Leica firmware behavior outranks visual preference;
- Leica tone behavior must not be retuned by eye;
- Xiaomi-specific source adaptation must be clearly separated from Leica target behavior;
- no Bayer-derived luma path may be described as authentic Leica Monochrom sensor spectral behavior;
- no HDR, temporal fusion, TC20, M9 HSM, SAT3, or M9 color reconstruction is part of the Monochrom target path;
- DNG + JPEG must remain available;
- visible JPEG quality is more important than speed.

The current open problem is no longer Leica tone. It is the **Xiaomi Bayer CFA → scalar monochrome bridge** that feeds the recovered Leica scalar/tone path.

---

## 2. Canonical Leica M Monochrom firmware state

Canonical firmware:

- file: `Mm-1_022.upm`
- size: 6,001,180 bytes
- SHA-256: `53330385edfbfb9beeffa06645bffa2789e27dda614869107698919464f80ad8`
- decrypted SHA-256: `c9e14ee475408802c83774f37b19c85c57663d9840e8e4c2cfe80e14dec9a7ae`
- repeating XOR key period: 1021
- key SHA-256: `595c49ebabdaafcde7cc6cbd6aa7a37092d7c2ad4ca47d0d8bc57a04a5bed3a1`

Canonical Monochrom `curve02`:

- length: 2048 bytes
- SHA-256: `7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752`
- selector: normal ISO + sRGB + Standard → curve02
- this curve is **frozen**.

Recovered native Contrast mode 0:

```text
v = max(uint16(sample14) - pedestal, 0)
idx = v >>> 3
out8 = curve02[idx]
```

The Leica working scalar domain is `0..16383` stored in uint16.

---

## 3. Firmware/source-domain closure already achieved

The important firmware question has been closed far enough to support the current Android experiment.

### PROVEN

`Process_Contrast` is the 16-bit scalar → 8-bit Y transition:

```text
uint16 scalar
-> subtract pedestal
-> clamp low
-> >>> 3
-> 2048-entry curve
-> uint8 Y
```

`Process_Y` is downstream of this. Its canonical disassembly shows byte-domain traffic and 8×8 raster/block organization. It is **not** the CCD/scalar producer.

Recovered topology therefore is:

```text
native scalar producer
    ↓
14-bit / uint16 scalar
    ↓
Shading / scalar-domain processing
    ↓
Process_Contrast
    ↓
8-bit Y
    ↓
Process_Y / JPEG-side organization
```

The direct-call and context trace further established:

```text
Task_TaskInterpolation
    -> StartInterpolation
        -> StartInterpolation_Jolos
            -> SetProcess
            -> Run
```

`SetProcess` copies `source_descriptor+0x2c` into `Run context+0x00` immediately before `Run`. The unresolved Leica-native boundary is therefore the origin of the scalar image buffer represented by that source descriptor pointer.

### IMPORTANT M9 DIFFERENTIAL

Active M9 bf0 contains named RGB/color stages including `Process_FPGA_Y`, `Process_FPGA_YCrCb`, `Process_WB`, and `ExecuteColorMatrix_14FM1`.

Those named active M9 color stages are absent from Monochrom bf0. The Monochrom path must therefore not be modeled as ordinary M9 RGB→Y color processing.

---

## 4. Android baseline before RAWSCALAR

The existing provisional primary path remains a control:

```text
Xiaomi RAW
-> black/white normalization
-> physical Camera2 LensShadingMap
-> MHC reconstruction
-> provisional M9 Q14 luma control
-> Leica14
-> canonical Monochrom curve02
```

This primary is useful only as a control. Its M9 Bayer-luma weighting is **not Monochrom sensor truth**.

SOURCE1D also retained diagnostic outputs:

- `_MONO_XYZY.jpg`
- `_MONO_GREEN.jpg`

These are counterfactual controls, not promotion candidates.

---

## 5. RAWSCALAR1A experiment

RAWSCALAR1A moved scalar formation upstream into the photosite domain:

```text
Xiaomi Bayer RAW
-> black/white normalization
-> physical Camera2 LensShadingMap
-> live-neutral CFA normalization
-> MHC 5x5 reconstruction
-> equal mean of reconstructed neutral-axis R/G/B
-> restore shading representation scale
-> Leica 14-bit coordinate
-> canonical Monochrom curve02
```

RAWSCALAR1A structurally passed:

- no obvious 2×2 Bayer checker/lattice artifact;
- fine texture remained acceptable;
- one-source RAW → monochrome scalar rendering worked at full resolution.

However, RAWSCALAR1A uses the per-shot Camera2 neutral. That means the effective spectral weighting changes with illuminant/AWB state.

That is conceptually weak for emulating a physical monochrome detector whose spectral response is fixed.

RAWSCALAR1A therefore remains **diagnostic only**.

---

## 6. RAWSCALAR1B FIXEDD65 experiment

Branch:

`apk/mono1a-rawscalar1b-fixedd65`

RAWSCALAR1B changes one thing only:

- the live per-shot neutral is replaced by a fixed D65 camera-neutral derived from immutable CameraCharacteristics calibration/color metadata.

Everything else is frozen relative to RAWSCALAR1A:

- same Bayer input;
- same physical LensShadingMap;
- same MHC 5×5 spatial reconstruction;
- same equal-mean scalar collapse;
- same shading representation-scale restoration;
- same Leica 14-bit coordinate;
- same pedestal policy;
- same canonical Monochrom `curve02`;
- same JPEG quality;
- same DNG persistence;
- no exposure/tone compensation.

Expected and device-confirmed fixed proxy:

```text
fixedNeutral ≈ [0.49099448, 1.00000000, 0.70471549]
fixedGain    ≈ [2.03668284, 1.00000000, 1.41901243]
```

The renderer records:

```text
perShotNeutralUsed = false
referenceIlluminant = D65
curve02Sha256 = 7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752
```

This is a **fixed Xiaomi sensor spectral proxy**, not recovered Leica CCD quantum efficiency.

---

## 7. First outdoor RAWSCALAR1B validation

Scene: overcast daylight landscape / path / grass / trees / cloud field.

Approximate JPEG statistics:

| Output | Mean | Median | P90 | P95 | P99 |
|---|---:|---:|---:|---:|---:|
| Primary M9-Y control | 95.65 | 53 | 202 | 208 | 218 |
| RAWSCALAR1B D65 | 100.69 | 53 | 211 | 217 | 226 |
| RAWSCALAR1A live neutral | 108.20 | 61 | 222 | 227 | 236 |
| GREEN | 110.25 | 70 | 221 | 227 | 235 |
| XYZ-Y | 109.36 | 68 | 220 | 226 | 235 |

Important result:

- RAWSCALAR1B retained the **same median as the primary (53)**;
- it gave the cloud field more separation than the primary;
- it was materially less globally lifted than RAWSCALAR1A;
- RAWSCALAR1B vs primary correlation was about `0.99940`;
- RAWSCALAR1B vs RAWSCALAR1A correlation was about `0.99962`;
- no obvious CFA lattice/checker failure was observed.

Outdoor highlight fraction at JPEG code >=224:

- RAWSCALAR1B: ~1.95%
- RAWSCALAR1A: ~8.21%

Conclusion from first outdoor gate:

**RAWSCALAR1B passed and was preferred architecturally over RAWSCALAR1A.**

Repo validation commit:

`3ce5bdae86d219e41357e74fed18ab35f393cea2`

---

## 8. Indoor tungsten validation

Capture stem:

`IMG_20260912_083250_1789198370327_00`

Scene: indoor tungsten / mixed household lighting with face/skin, dark hair, textured sofa, plaid fabric, hands/legs, wall, monitor and furniture.

Capture metadata:

- physical camera: `2`
- RAW: 4096×3072 RGGB
- ISO: `1708`
- exposure: `19.634736 ms`
- aperture: `f/1.63`
- focal length: `8.72 mm`
- black level: `[64,64,64,64]`
- white level: `1023`
- live neutral: `[0.4560546875, 1, 0.4775390625]`

The live neutral is now substantially different from the fixed D65 proxy, especially in blue.

Effective live vs fixed gain difference:

```text
R: live path ≈ +0.1065 EV vs fixed D65
B: live path ≈ +0.5614 EV vs fixed D65
G: unchanged
```

That is exactly the illuminant-dependent spectral weighting drift RAWSCALAR1B was designed to remove.

### JPEG statistics for the tungsten frame

Output ordering for the uploaded set:

1. primary control
2. RAWSCALAR1B D65
3. RAWSCALAR1A
4. GREEN
5. XYZ-Y

Measured full-frame grayscale statistics:

| Output | Mean | Median | P90 | P95 | P99 |
|---|---:|---:|---:|---:|---:|
| Primary control | 107.08 | 123 | 158 | 171 | 200 |
| RAWSCALAR1B D65 | 114.38 | 132 | 167 | 181 | 211 |
| RAWSCALAR1A live neutral | 123.19 | 142 | 177 | 190 | 219 |
| GREEN | 122.97 | 143 | 177 | 187 | 214 |
| XYZ-Y | 124.45 | 144 | 179 | 193 | 221 |

JPEG fraction at code >=224:

- primary: ~0.044%
- RAWSCALAR1B: ~0.260%
- RAWSCALAR1A: ~0.646%
- GREEN: ~0.366%
- XYZ-Y: ~0.810%

JPEG fraction at code >=240:

- primary: 0%
- RAWSCALAR1B: ~0.001%
- RAWSCALAR1A: ~0.043%
- GREEN: ~0.004%
- XYZ-Y: ~0.071%

### RAWSCALAR native diagnostics in the tungsten frame

RAWSCALAR1A:

```text
neutral = [0.4560546875, 1, 0.4775390625]
lowClampCount = 1655
highClampCount = 28
nearWhiteOutputCount = 74
neutralAxisHighClipCount = 17353
```

RAWSCALAR1B:

```text
fixedNeutral = [0.4909944832, 1, 0.7047154903]
perShotNeutralUsed = false
lowClampCount = 1485
highClampCount = 13
nearWhiteOutputCount = 36
neutralAxisHighClipCount = 25359
```

Do not equate `neutralAxisHighClipCount` with final JPEG clipping; they describe different internal stages. The final RAWSCALAR1B JPEG highlight occupancy remained low.

### Visual/structural interpretation

RAWSCALAR1B remains free of an obvious 2×2 CFA lattice/checker artifact in:

- sofa texture;
- hair;
- plaid shirt;
- facial detail;
- broad wall gradients.

Relative to RAWSCALAR1A / GREEN / XYZ-Y, RAWSCALAR1B is more restrained:

- face and hands are less aggressively lifted;
- textured sofa remains well separated;
- hair remains dark with visible structure;
- shirt pattern remains readable;
- highlights are less occupied.

The tungsten capture therefore strengthens the architectural case for fixed D65 because the live-neutral path changes spectral weighting substantially under this illuminant.

---

## 9. Current judgment

### Preferred working bridge

**RAWSCALAR1B FIXEDD65 is now the preferred provisional Xiaomi → Monochrom scalar bridge.**

### Status of alternatives

- RAWSCALAR1A: retain as diagnostic-only live-neutral counterfactual.
- GREEN: diagnostic-only green-channel control.
- XYZ-Y: diagnostic-only scene-luminance counterfactual.
- Primary M9-Y: provisional historical/control output only; do not call it authentic Monochrom spectral behavior.

### Important wording constraint

Do **not** claim:

> RAWSCALAR1B reproduces the original Leica Monochrom CCD spectral response.

The defensible claim is:

> RAWSCALAR1B is currently the strongest Xiaomi Bayer-to-scalar translation architecture because its effective CFA weighting is fixed rather than changing with per-shot AWB/illuminant state, while preserving the recovered Leica scalar/tone stage unchanged.

---

## 10. Promotion decision

The project has now completed:

1. structural RAWSCALAR1A gate;
2. first outdoor RAWSCALAR1B gate;
3. indoor tungsten RAWSCALAR1B gate.

Both 1B device gates support promotion.

Recommended next move:

### Promote RAWSCALAR1B provisionally

Make RAWSCALAR1B the working monochrome scalar output while retaining:

- RAWSCALAR1A diagnostic output;
- GREEN diagnostic output;
- XYZ-Y diagnostic output;
- current DNG persistence.

Promotion must **not** alter:

- canonical curve02;
- Leica working-coordinate mapping;
- JPEG quality;
- physical LensShadingMap policy;
- MHC kernel;
- exposure policy;
- capture policy.

Do not add tone tuning just to make the promoted image visually match the old primary.

---

## 11. One optional confirmation before/after promotion

A final high-value material-separation scene would contain, in one frame:

- clearly red material/object;
- clearly green material/foliage;
- clearly blue material/object;
- skin;
- white/grey neutral surface.

Purpose:

- quantify local material ordering;
- ensure fixed D65 does not collapse toward green-only behavior;
- compare 1B vs 1A under an explicit chromatic stress scene.

This test is useful but no longer required to justify the current architectural preference.

---

## 12. Current Android output bank

One shutter press on the RAWSCALAR1B test build should retain:

- primary `.jpg` — provisional M9-Y control
- `_MONO_RAWSCALAR1A.jpg`
- `_MONO_RAWSCALAR1B_D65.jpg`
- `_MONO_XYZY.jpg`
- `_MONO_GREEN.jpg`
- DNG
- primary JSON
- source calibration / raw shading diagnostics

The app may still display the inherited M9 PhotonCamera name. That is cosmetic and not part of this validation block.

---

## 13. Non-negotiable project constraints

Keep these frozen unless new firmware evidence forces a change:

- no HDR;
- no temporal fusion;
- no TC20;
- no M9 HSM;
- no SAT3;
- no color reconstruction in the Monochrom target;
- no arbitrary Leica tone tuning;
- canonical Monochrom curve02 remains exact;
- DNG + JPEG;
- full-quality JPEG output;
- firmware evidence outranks visual guesses;
- source adapter and Leica target behavior remain conceptually separated.

---

## 14. Immediate next actions for the next chat

1. **Promote RAWSCALAR1B provisionally** on a new branch derived from `apk/mono1a-rawscalar1b-fixedd65`, unless the user explicitly asks for one final RGB-material stress capture first.
2. Make RAWSCALAR1B the selected monochrome JPEG output, but keep diagnostic variants available initially.
3. Do not alter exposure, tone, curve02, MHC, or physical shading behavior during promotion.
4. Update JSON schema/policy strings so promoted RAWSCALAR1B is clearly identified as:
   - fixed Xiaomi camera spectral proxy;
   - not Leica CCD QE truth;
   - no per-shot neutral used.
5. Build CI and install-test one ordinary scene.
6. After promotion stability, simplify the diagnostic bank only if requested.
7. Continue firmware producer-boundary research separately; do not block the useful Android scalar bridge on full Leica CCD spectral reconstruction.

---

## 15. Key files / evidence for continuation

Tungsten capture:

- `IMG_20260912_083250_1789198370327_00.jpg`
- `IMG_20260912_083250_1789198370327_00_MONO_RAWSCALAR1B_D65.jpg`
- `IMG_20260912_083250_1789198370327_00_MONO_RAWSCALAR1A.jpg`
- `IMG_20260912_083250_1789198370327_00_MONO_GREEN.jpg`
- `IMG_20260912_083250_1789198370327_00_MONO_XYZY.jpg`
- `IMG_20260912_083250_1789198370327_00_M9.json`
- `IMG_20260912_083250_1789198370327_00_M9_PRIMARY.json`
- `IMG_20260912_083250_1789198370327_00_M9_SOURCECAL1A.json`
- `IMG_20260912_083250_1789198370327_00_M9_RAWSHADING1A.json`
- diagnostic burst JSONs

Relevant repository docs:

- `docs/RAWSCALAR1A_DEVICE_VALIDATION.md`
- `docs/RAWSCALAR1B_FIXED_D65_DEVICE_VALIDATION.md`
- `docs/NEXT.md`
- `docs/MONO_SIGNAL_DOMAIN_v0_4.md`
- `docs/NATIVE_CONTRAST_MODE_v0_3.md`

---

## 16. Handoff summary

The project has moved beyond guessing RGB luma coefficients.

Firmware forensics established that the original M Monochrom tone path consumes a pre-Contrast 16-bit scalar image and converts it to 8-bit Y through the canonical curve. `Process_Y` is downstream and is not the source producer.

RAWSCALAR1A proved that a clean full-resolution photosite-domain Xiaomi CFA → scalar path is technically viable, but its per-shot neutral makes spectral weighting move with illumination.

RAWSCALAR1B fixes that conceptual weakness by deriving a fixed D65 camera-neutral from immutable Xiaomi camera metadata while leaving all later reconstruction and Leica tone behavior frozen.

It passed both an overcast outdoor scene and an indoor tungsten/skin/textile scene without obvious CFA lattice artifacts, with healthier tonal restraint than RAWSCALAR1A and substantially less illuminant-dependent weighting.

**Current recommendation: promote RAWSCALAR1B FIXEDD65 provisionally as the working Xiaomi → Monochrom scalar bridge, retain RAWSCALAR1A/GREEN/XYZ-Y as diagnostics, and keep Leica curve02 and the rest of the Monochrom target path frozen.**
