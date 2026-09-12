# Next project target

Date: 2026-09-12

## Current working Android state

Branch:

`apk/mono1a-rawscalar1b-promoted1a`

RAWSCALAR1B FIXEDD65 is **device-validated as the selected working Xiaomi -> original M Monochrom scalar bridge**.

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

## Sharpness source bank: direct consumer closure

The earlier `16 x 2 x 2050-byte` wording was incorrect. The canonical M Monochrom `PROCESS/LUTS` sharpness source bank is:

```text
16 ISO rows * 2050 signed-int16 values * 2 bytes
= 65,600 bytes
```

Canonical range:

```text
0x58c .. 0x105cc
```

Direct firmware tracing now closes the path:

```text
PROCESS/LUTS header
  +0x14 -> 0x58c source-bank offset
  metadata block -> count 2050
        |
LoadLutArchiveL3
        |
sharp+0x08 = archive + 0x58c
sharp+0x14 = 2050
        |
SetStructParameter / Set
  ISO slot + sharpness selector -> modifier code
        |
Run
        |
LoadAndModifySharpnessDa
  selected 4100-byte row -> scratch
  signed scale/shift and clamp [-2048,+2048]
        |
Process_Sharpness
        |
UM_Gauss3LUT
```

`LoadISODataL1` is **not** the 2050-value row copier. It handles a much smaller ISO-indexed scalar/metadata field. The actual row loader is `LoadAndModifySharpnessDa`.

See `docs/MM_SHARPNESS_LUTBANK1A.md`.

## Immediate research target

The next sharpness question is no longer bank identity. It is the **exact arithmetic and table interpretation inside `UM_Gauss3LUT`**.

1. Disassemble both mirrored `UM_Gauss3LUT` instances and close their argument layout.
2. Determine why `Process_Sharpness` derives a `1025` half-count coordinate from the 2050-word row and whether the row is structurally two 1025-word halves.
3. Recover integer widths, signedness, interpolation/index arithmetic, rounding and saturation used by `UM_Gauss3LUT`.
4. Identify the image-buffer input/output domain at this stage and whether the function is an in-place/detail reconstruction primitive or a LUT-guided Gaussian operation with separate source/destination buffers.
5. Trace branch conditions around `Process_Sharpness` so the firmware dispatcher is not mistaken for unconditional photographic ordering.
6. Continue the separate upstream scalar-producer boundary trace after this sharpness block; do not mix the two questions.

No Android sharpness implementation should be added until the above arithmetic is closed. The promoted RAWSCALAR1B photographic path remains frozen during this research.

## Performance note

The first promoted device capture took roughly 5.4 s for the complete diagnostic-bank render, while the RAWSCALAR1B native render itself was only about 119 ms. Do not optimize the photographic kernel based on diagnostic-bank wall time. Remove or reduce diagnostics only when requested, then remeasure before considering renderer-speed changes.
