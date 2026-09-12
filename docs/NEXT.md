# Next project target

Date: 2026-09-12

## Current working Android state

Branch:

`apk/mono1a-rawscalar1b-promoted1a`

RAWSCALAR1B FIXEDD65 is **device-validated as the selected working Xiaomi -> original M Monochrom scalar bridge**.

The normal JPEG is RAWSCALAR1B. Retained diagnostics are `_MONO_M9Y_CONTROL.jpg`, `_MONO_RAWSCALAR1A.jpg`, `_MONO_GREEN.jpg`, `_MONO_XYZY.jpg`, plus DNG and JSON diagnostics.

Validation capture:

`IMG_20260912_102047_1789204847548_00`

See `docs/RAWSCALAR1B_PROMOTION1A.md`, `docs/RAWSCALAR1B_PROMOTED1A_DEVICE_VALIDATION.md`, `docs/RAWSCALAR1B_FIXED_D65_DEVICE_VALIDATION.md`, `docs/MONO_SIGNAL_DOMAIN_v0_4.md`, and `docs/NATIVE_CONTRAST_MODE_v0_3.md`.

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

Unless new firmware evidence requires a change, do not alter canonical Monochrom curve02, Leica 14-bit working-coordinate mapping, physical LensShadingMap policy, MHC kernel, JPEG quality, DNG persistence, exposure/capture policy, or the no-HDR / no-temporal-fusion / no-TC20 / no-M9-HSM / no-SAT3 / no-color-reconstruction rule.

Do not tune Leica tone by eye.

## Sharpness arithmetic and geometry: closed

The Monochrom Standard sharpness consumer is no longer an arithmetic mystery.

The canonical source bank is:

```text
16 ISO rows * 2050 signed-int16 values * 2 bytes
= 65,600 bytes
```

Canonical range:

```text
0x58c .. 0x105cc
```

The recovered Standard path is an ISO-dependent nonlinear unsharp mask in the 14-bit scalar domain. `UM_Gauss3LUT` uses the exact separable Gaussian:

```text
horizontal = (L + 2*C + R) >> 2
vertical   = (T + 2*C + B) >> 2
detail     = source - blur
correction = centered 2050-word LUT(detail)
out        = clamp(source + correction, 0, 16383)
```

Standard selector = `2`. The recovered Standard ISO strength schedule is:

```text
ISO 320-640    code 8 = 2.00x
ISO 800-4000   code 4 = 1.00x
ISO 5000-6400  code 3 = 0.75x
ISO 8000-10000 code 2 = 0.50x
```

Geometry is also closed. Sharp itself adds exactly `+2` to the incoming valid-border accumulator. If the incoming border is `b`, the Sharp output border is `b+2`; pixels outside the processed rectangle remain unchanged. There is no mirror/replicate/synthetic padding.

See:

- `docs/MM_SHARPNESS_LUTBANK1A.md`
- `docs/MM_SHARPNESS_KERNEL1A.md`
- `docs/MM_SHARPNESS_GEOMETRY1A.md`

## Process scheduling boundary: current exact state

`Run` loads its process mask from settings word `+0`. Its closed dispatch includes:

```text
bit 6 -> Noise
bit 7 -> Sharpness
bit 8 -> Contrast
bit 9 -> Y
```

The processing-list machinery is also closed:

```text
g_ProcessingList = 4-byte header + 14 * 68-byte records
IM_GetHead        = complete 68-byte record copy
IM_SetCurrentJob  = complete 17-word / 68-byte copy
```

On the SportNet receive side, command selector `0x04` maps to `SPI_AppendSettings`, with payload size `0x25` = 37 bytes. `SPI_AppendSettings` copies exactly `request+7 .. request+43` into a local 37-byte buffer. `IM_AppendItem` then copies those same 37 bytes to processing-record offset zero. Therefore the first u32 of the **real command-0x04 payload** is the process mask that reaches `Run`; BF561 does not rewrite that mask on the receive/list path.

See `docs/MM_APPENDSETTINGS_MASK_PATH1A.md`.

## Corrected false lead

The BF547 routine at `0x36ff4` must **not** be treated as the command-0x04 AppendSettings producer merely because its object layout has `0x133 - 0x12c = 7`.

That routine copies a fixed `0x31343133` template word from `0xeb440` to object `+0x12c` and serializes unrelated object state at `+0x133..`. Its `+0x35c` source field is initialized with values `0..6` across seven controller objects. This cannot be promoted as the normal low process-mask byte for Noise bit 6 / Sharpness bit 7.

Direct-call, literal-pointer and split-immediate xref probes also found no evidence tying `0x36ff4` to the SportNet `0x04` sender path.

The old packet-alignment hypothesis is therefore retired.

## Immediate research target

The next task is now sharply bounded: recover the **real BF547 SportNet client-side producer of command `0x04` with a 37-byte payload**.

Work in this order:

1. Locate the BF547-side SportNet client request builder / dispatch metadata for selector `0x04` and payload length `0x25`.
2. Trace the payload source pointer back to the normal still/JPEG processing-settings structure.
3. Recover the exact normal process-mask u32 and therefore whether Noise and Sharp are enabled for the Standard photographic path.
4. If Noise is enabled, recover its normal mode so the incoming border to Sharp is exact (`0`, `+2`, or `+4` before Sharp's own `+2`).
5. Only then implement or promote a firmware-exact Standard sharpness Android A/B. Do not guess the incoming border.
6. Keep the validated RAWSCALAR1B photographic branch frozen while this proceeds.

A separate upstream scalar-producer/spectral-truth investigation remains valuable, but it should not be mixed with this process-scheduling closure.

## Performance note

The first promoted device capture took roughly 5.4 s for the complete diagnostic-bank render, while the RAWSCALAR1B native render itself was only about 119 ms. Do not optimize the photographic kernel based on diagnostic-bank wall time. Remove or reduce diagnostics only when requested, then remeasure before considering renderer-speed changes.
