# Next project target

Date: 2026-09-12

## Current working Android state

Branch:

`apk/mono1a-rawscalar1b-promoted1a`

RAWSCALAR1B FIXEDD65 is now **device-validated as the selected working Xiaomi -> original M Monochrom scalar bridge**.

The normal JPEG is RAWSCALAR1B. Retained diagnostics are:

- `_MONO_M9Y_CONTROL.jpg`
- `_MONO_RAWSCALAR1A.jpg`
- `_MONO_GREEN.jpg`
- `_MONO_XYZY.jpg`
- DNG and JSON diagnostics

Validation capture:

`IMG_20260912_102047_1789204847548_00`

See:

- `docs/RAWSCALAR1B_PROMOTION1A.md`
- `docs/RAWSCALAR1B_PROMOTED1A_DEVICE_VALIDATION.md`
- `docs/RAWSCALAR1B_FIXED_D65_DEVICE_VALIDATION.md`
- `docs/MONO_SIGNAL_DOMAIN_v0_4.md`
- `docs/NATIVE_CONTRAST_MODE_v0_3.md`

## Frozen Leica target truths

Normal ISO / sRGB / Standard uses canonical Monochrom `curve02`.

`Process_Contrast` mode 0 is frozen as:

```text
v = max(uint16(sample14) - pedestal, 0)
idx = v >>> 3
out8 = curve02[idx]
```

Canonical curve02 SHA-256:

`7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752`

Recovered topology remains:

```text
native scalar producer
    -> 14-bit / uint16 scalar
    -> scalar-domain processing / shading
    -> Process_Contrast
    -> 8-bit Y
    -> Process_Y / JPEG-side organization
```

Do not reinterpret downstream `Process_Y` as the CCD/scalar producer.

## Current source bridge

Selected path:

```text
Xiaomi Bayer RAW
-> black/white normalization
-> physical Camera2 LensShadingMap
-> fixed D65 camera-neutral CFA normalization
-> MHC 5x5 spatial reconstruction
-> equal mean of reconstructed fixed-D65-axis R/G/B
-> restore shading representation scale
-> Leica 14-bit coordinate
-> canonical Monochrom curve02
```

This is a **fixed Xiaomi camera spectral proxy**. It is not recovered Leica Monochrom CCD quantum-efficiency truth.

Do not reintroduce per-shot AWB into the selected scalar bridge merely to make individual scenes look preferable.

## Keep frozen

Unless new firmware evidence requires a change, do not alter:

- canonical Monochrom curve02;
- Leica 14-bit working-coordinate mapping;
- physical LensShadingMap policy;
- MHC kernel;
- JPEG quality;
- DNG persistence;
- exposure/capture policy;
- no HDR / temporal fusion / TC20 / M9 HSM / SAT3 / color reconstruction in the Monochrom target path.

Do not tune Leica tone by eye.

## Immediate research target

The highest-value remaining fidelity problem is now **upstream of `Process_Contrast`**.

1. Continue producer-boundary tracing for the source descriptor scalar buffer feeding the interpolation / processing chain.
2. Investigate the `16 x 2 x 2050-byte` ISO-aligned bank and `LoadISODataL1` consumer to determine whether it contributes scalar-domain noise, detail, shading, or ISO-dependent correction before Contrast.
3. Locate additional callers/data flow around `Task_TaskInterpolation -> StartInterpolation -> StartInterpolation_Jolos -> SetProcess -> Run` that can identify the exact source-buffer producer.
4. Keep RAWSCALAR1A, GREEN, XYZ-Y and M9-Y as diagnostic controls while producer research continues.
5. Keep full-resolution sharpness / periodic-artifact validation separate from spectral-bridge validation.

## Performance note

The first promoted device capture took roughly 5.4 s for the complete diagnostic-bank render, while the RAWSCALAR1B native render itself was only about 119 ms. Do not optimize the photographic kernel based on diagnostic-bank wall time. Remove or reduce diagnostics only when requested, then remeasure before considering renderer-speed changes.
