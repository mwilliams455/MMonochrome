# Next project target

Continue from `docs/SOURCE1E_SCALAR_ARCHITECTURE_CLOSURE_v0_1.md`.

## Current state

SOURCE1E is closed strongly enough to stop searching for a post-demosaic RGB/Y coefficient formula.

Canonical M Monochrom 1.022 firmware now directly supports this photographic ordering:

```text
sensor-transfer raw-buffer bank
  -> 16-bit scalar/word image processing
  -> Shading / Noise / Sharpness
  -> Process_Contrast mode 0
  -> 8-bit Y
  -> Process_Y / block packing
```

The frozen normal-ISO / sRGB / Standard tone stage remains:

```text
v = max(uint16(sample14) - pedestal, 0)
idx = v >>> 3
out8 = curve02[idx]
```

`curve02` SHA-256:

`7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752`

Do not change this stage to compensate for Xiaomi source placement.

## Proven SOURCE1E conclusions

- `Process_Y @ 0xffa028e8` is downstream 8-bit Y/resolution/block handling, not the Monochrom sensor-scalar generator.
- `Process_Contrast @ 0xffa00b30` is the native 16-bit scalar to 8-bit LUT transition.
- `Run @ 0xffa01790` dispatches the scalar stages before `Process_Y`.
- the first ordinary `L3L1_Get` loads processing-context slot 0 into the 16-bit L1 image working plane.
- `IM_GetRawBuffer(index) = index * 0x01450000` and the interpolation job stores raw-buffer-bank addresses into the processing context.
- `SPI_SetNextImage -> Sensor_InitTransfer` points the sensor-transfer DMA at this same raw-buffer bank.
- native dual-output correction, when enabled, operates over the two selected L3 planes as 16-bit word samples before ordinary processing.
- the active M9 colour/YCrCb path is an architectural control only; its RGB-to-Y coefficients are not Monochrom spectral truth.

The firmware-supported Android insertion point is therefore a scalar image constructed before the frozen Leica contrast stage.

## Android experiment now in progress — RAWSCALAR1A

Branch:

`apk/mono1a-rawscalar1a`

RAWSCALAR1A is diagnostic only. SOURCE1D M9-Y remains the primary output and the existing XYZ-Y / GREEN controls remain available.

The candidate is formed from the same single Xiaomi RAW as follows:

1. black/white normalize the Bayer RAW;
2. apply the physical Camera2 LensShadingMap exactly once in Bayer space;
3. neutral-normalize photosites before reconstruction:
   - `R *= neutralG / neutralR`
   - `G *= 1`
   - `B *= neutralG / neutralB`
4. use the existing Malvar-He-Cutler 5x5 spatial kernel on that neutral-normalized CFA;
5. collapse the reconstructed neutral-axis `R/G/B` estimates with an equal mean;
6. restore only the physical-shading transport representation scale;
7. map the scalar to Leica `0..16383`;
8. apply the unchanged mode-0 pedestal/index arithmetic and canonical `curve02`.

No M9 luma coefficients, XYZ coefficients, SOURCECAL transform, HSM, SAT3, TC20, HDR, temporal fusion, or exposure retuning are part of RAWSCALAR1A.

This is explicitly a **Xiaomi CFA-to-scalar adapter**, not recovered Leica CCD spectral response.

## Required device validation

Use the same capture to compare:

- primary M9-Y control;
- XYZ-Y control;
- GREEN control;
- `RAWSCALAR1A`.

The first useful scenes are:

1. neutral indoor/overcast scene with fine texture;
2. strongly colour-discriminating daylight scene containing saturated red, green and blue objects plus neutrals;
3. foliage / sky scene;
4. high-contrast highlight + deep-shadow scene.

For each capture retain the JPEGs and primary JSON sidecar.

### Promotion gate

Do not promote RAWSCALAR1A unless:

- no visible 2x2 CFA lattice/checker pattern appears in neutral or coloured areas;
- fine detail is not materially worse than the current MHC-based primary;
- highlights and dense shadows retain the frozen Monochrom tone behaviour;
- strongly coloured objects do not produce phase-dependent artifacts;
- diagnostics confirm pre-colour Bayer formation and unchanged curve02;
- repeated same-RAW comparisons support the change rather than a single attractive frame.

If RAWSCALAR1A fails, refine the Xiaomi CFA reconstruction only. Do not alter Leica curve02 or reintroduce post-demosaic luma tuning to hide the failure.

## Frozen constraints

- curve02 frozen;
- native mode-0 arithmetic frozen;
- Leica 14-bit coordinate frozen;
- source pedestal policy explicit;
- physical Camera2 LensShadingMap retained;
- one RAW, no HDR or temporal fusion;
- DNG + high-quality JPEG retained;
- no TC20 render normalization;
- no M9 HSM/SAT/colour reconstruction;
- no brightness tuning to disguise source-domain errors;
- no image-quality trade for speed without explicit agreement.

## After RAWSCALAR source placement is stable

Only then return to:

- exact `Process_Noise` behaviour;
- exact `Process_Sharpness` behaviour;
- native pedestal producer semantics;
- performance optimization;
- empirical sensor spectral translation if a physically grounded Leica-vs-Xiaomi calibration source becomes available.
