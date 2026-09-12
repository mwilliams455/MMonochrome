# Next project target

Continue from `docs/SOURCE1E_PROCESS_Y_TRACE_v0_1.md`, `docs/MONO_SIGNAL_DOMAIN_v0_4.md`, `docs/NATIVE_CONTRAST_MODE_v0_3.md`, and `docs/LUT_SELECTOR_TRACE_v0_3.md`.

## Current state

The first real MONO1A APK path is working on-device. The downstream Leica tone stage remains frozen and firmware-grounded:

- normal ISO / sRGB / Standard -> canonical curve `02`;
- JPEG resolution `100%` -> `Process_Contrast` mode `0`;
- Monochrom working signal range is `0..16383` in 16-bit storage;
- `context+128` is the shared signal pedestal / black-reference coordinate used by Shading and Contrast;
- native mode-0 Contrast arithmetic is exactly:

```text
v = max(uint16(sample14) - pedestal, 0)
idx = v >>> 3
out8 = curve02[idx]
```

Do not alter this stage to compensate for Xiaomi source placement.

## SOURCE1D result

The first same-RAW SOURCE1D continuity test compared the existing post-MHC M9-Y control, Green-only, and native Camera->XYZ D50 Y-row counterfactual.

XYZ-Y vs M9-Y was approximately:

```text
correlation  ~0.99840
affine R^2   ~0.9968
residual MAE ~2.21 8-bit codes
M9-Y ~= 0.8999 * XYZ-Y - 3.09
```

This is strong evidence that, on the tested scene, post-demosaic RGB weighting mostly changes global source placement rather than revealing a fundamentally different monochrome material ordering.

Do not continue inventing RGB luma coefficient sets. A colour-discriminating daylight capture remains useful as confirmation, but it does not block SOURCE1E.

## Important BF561 topology correction

The canonical Monochrom `bf0.map` does **not** retain the named M9 colour-camera stages:

```text
Process_WB
ExecuteColorMatrix_14FM1
Process_FPGA_Y
Process_FPGA_YCrCb
SetMatrixL3
L3L1_Put16BitRGB
L3L1_Put3rgb
L3L1_Put3yycrcb
```

Monochrom does retain:

```text
Process_Y
L3L1_Put8BitY
Process_Shading
Process_Contrast
Process_Noise
Process_Sharpness
```

Therefore `Process_FPGA_Y` is no longer a Monochrom trace target. M9 BT.601 Y remains a useful control/provenance reference only.

## Immediate research target — SOURCE1E

Recover the actual scalar buffer lineage:

```text
native producer
  -> Process_Y / Process_Shading / Process_Contrast
  -> L3L1_Put8BitY
```

Priority work:

1. run `tools/trace_scalar_topology.py` against locally extracted Monochrom `bf0.map` and, when available, the matching M9 imaging-overlay map;
2. extract exact `Process_Y` and `L3L1_Put8BitY` function bytes from Monochrom BF561;
3. extend the existing strict small Blackfin decoder only for opcodes actually present in those routines;
4. recover entry arguments, pointers, widths, strides, arithmetic, shifts/clamps and calls;
5. trace the buffers backward to their producer and forward through Shading/Contrast/output;
6. recover runtime processing-list order rather than treating dispatcher case order as photographic order.

Do not claim native CCD/FPGA semantics until that consumer/producer chain is closed.

## Xiaomi source-adapter consequence

If firmware evidence confirms that the Monochrom processor receives a single scalar intensity field early, build the next same-RAW counterfactual in the **photosite domain**, before RGB demosaic weighting.

Compare against the frozen controls:

- post-MHC M9-Y control;
- post-MHC XYZ-Y control;
- direct/photosite-domain Bayer scalar reconstruction;
- CFA-neutral or green-pair estimator only when explicitly justified.

Do not invent Leica spectral coefficients and do not select a method merely because it looks attractive.

## Frozen constraints

- curve02 frozen;
- native mode-0 arithmetic frozen;
- 14-bit Leica coordinate frozen;
- source pedestal policy explicit;
- physical Camera2 LensShadingMap retained;
- single RAW / no HDR / no temporal fusion;
- DNG + high-quality JPEG;
- no TC20 render normalization;
- no M9 HSM, SAT stages or colour reconstruction;
- no visual brightness tuning to disguise source-domain uncertainty;
- no image-quality trade for speed without explicit agreement.

## Later, not now

Only after the scalar source/input path is stable:

- `Process_Noise`;
- `Process_Sharpness`;
- exact pedestal producer semantics;
- performance optimization of the Android renderer.

The immediate fidelity bottleneck is no longer curve selection. It is the native scalar producer consumed by the Monochrom processing path.
