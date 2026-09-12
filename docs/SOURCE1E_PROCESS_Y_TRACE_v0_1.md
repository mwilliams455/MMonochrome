# M Monochrom SOURCE1E — scalar topology / Process_Y trace v0.1

Date: 2026-09-12
Branch: `research/source1e-processy`
Target: original Leica M Monochrom 1.022

## Status

SOURCE1D has now done the job it was designed to do on the first continuity capture: the post-MHC XYZ-Y counterfactual is overwhelmingly explainable by global brightness/scale placement relative to the M9-Y control, rather than by a strongly different material-luminance ordering.

Measured on the same RAW/output geometry:

| source | mean | median | correlation vs M9-Y | affine R^2 vs M9-Y | affine residual MAE |
|---|---:|---:|---:|---:|---:|
| M9-Y control | ~75.47 | 74 | 1.0 | 1.0 | 0 |
| Green-only | ~86.19 | 87 | ~0.99660 | ~0.9932 | ~3.09 |
| XYZ-Y | ~87.30 | 89 | ~0.99840 | ~0.9968 | ~2.21 |

Best simple fit for this capture was approximately:

```text
M9-Y ~= 0.8999 * XYZ-Y - 3.09
```

This is enough to stop inventing further post-demosaic RGB coefficient sets as the primary research direction. A colour-discriminating daylight capture remains useful as a confirmation record, but it does not block the next firmware trace.

## 1. Important correction to the previous handoff

The current canonical `docs/FIRMWARE_BASELINE_v0_1.md` establishes a stronger symbol-map fact than the earlier broad shared-vocabulary note.

In the Monochrom BF561 `bf0.map`, the following M9 colour-path symbols are removed:

- `ExecuteColorMatrix_14FM1`
- `Process_WB`
- `Process_FPGA_Y`
- `Process_FPGA_YCrCb`
- `SetMatrixL3`
- `LoadLutDataL3`
- `L3L1_Put16BitRGB`
- `L3L1_Put3rgb`
- `L3L1_Put3yycrcb`
- `Process_DNGNoise`
- colour interpolation / difference helpers

Monochrom retains the scalar/spatial family including:

- `Process_Y`
- `L3L1_Put8BitY`
- `Process_Shading`
- `Process_Contrast`
- `ExecuteContrast_11LUT8_7`
- `ExecuteContrast_11LUT8_2`
- `ExecuteContrast_11LUT8_3`
- `Process_Noise`
- `Process_Sharpness`
- `LoadLutArchiveL3`
- `LoadISODataL1`
- `CalculateNoiseParameter`

Therefore `Process_FPGA_Y` / `Process_FPGA_YCrCb` are **not valid Monochrom named-function trace targets**. They remain useful only as M9 colour-camera provenance for the BT.601 control formula.

This does not prove that no equivalent arithmetic could be inlined or implemented elsewhere. It does prove that the named M9 FPGA RGB->Y / YCbCr stages are absent from the Monochrom BF561 symbol topology and must not be promoted into the Monochrom source path without new evidence.

## 2. Architectural implication

The symbol topology is now consistent with a much simpler Monochrom BF561 image path:

```text
scalar / Y-family input
  -> scalar spatial processing
  -> 14-bit working signal
  -> Process_Contrast mode 0
  -> curve02
  -> 8-bit Y output
```

The already-closed signal-domain evidence strengthens this interpretation:

```text
Process_Shading:
  sample14 - pedestal
  * shading gain
  + pedestal
  clamp 0..16383

Process_Contrast mode 0:
  max(sample14 - pedestal, 0)
  >>> 3
  curve02[index]
  -> 8-bit output
```

This is still **not proof of the native CCD/FPGA producer**. The upstream producer of the scalar buffer remains the central open question.

## 3. SOURCE1E trace target

The trace is narrowed to four concrete questions.

### A. `Process_Y`

Recover:

- exact function address/size from the Monochrom imaging overlay;
- argument registers at entry;
- input/output pointer widths and strides;
- sample load/store widths;
- any pedestal, shift, clamp, LUT or arithmetic operation;
- caller/job-dispatch identity;
- relationship to `Process_Shading` and `Process_Contrast` buffers.

### B. `L3L1_Put8BitY`

Recover:

- source buffer domain;
- destination packing;
- whether it consumes post-contrast 8-bit Y or performs another conversion;
- its caller and ordering relative to `Process_Contrast`.

### C. scalar-buffer producer

Back-slice the buffer consumed by `Process_Y` / Shading / Contrast until the earliest producer that is visible in BF561/BF547/FPGA control flow.

Candidate descriptions must remain descriptive until proven:

- direct sensor intensity;
- FPGA scalar plane;
- CCD-preprocessed 14-bit plane;
- L3/L1 intermediate;
- another scalar representation.

### D. runtime processing-list evidence

`Run`-style dispatcher case order must not be mistaken for photographic pipeline order. Recover the actual job record / processing list if the Monochrom runtime uses the same dispatcher architecture as M9.

The goal is to establish real buffer lineage:

```text
producer -> Process_Y / Shading / Contrast -> L3L1_Put8BitY
```

rather than infer order from symbol names.

## 4. Xiaomi SOURCE1E consequence

If the firmware trace confirms that a single scalar intensity field exists before the Leica spatial/tone stages, the next Xiaomi counterfactual should move **before RGB demosaic weighting**.

Candidate controls, all using the same frozen Leica tone stage, are then:

1. current post-MHC M9-Y control;
2. current post-MHC XYZ-Y counterfactual;
3. a photosite-domain scalar reconstruction from the black-subtracted, physically lens-shaded Bayer plane;
4. a CFA-neutral / green-pair scalar estimator only if its construction is explicitly justified and logged.

Do not invent Leica spectral coefficients. The purpose is architectural matching, not aesthetic desaturation.

## 5. Frozen constraints

Keep unchanged while SOURCE1E is open:

- canonical Monochrom curve02;
- native mode-0 Contrast arithmetic;
- 14-bit `0..16383` Leica working coordinate;
- explicit source-adapter pedestal convention;
- physical Camera2 LensShadingMap policy;
- single RAW capture;
- DNG + high-quality JPEG;
- no HDR / temporal fusion;
- no TC20 render normalization;
- no M9 HSM / SAT stages / colour reconstruction;
- no source brightness tuning by eye.

## 6. Current evidence boundary

### Proven now

- Monochrom and M9 share the firmware family but diverge in the photographic executable/data path;
- the named M9 WB / ColorMatrix / FPGA-Y / FPGA-YCrCb BF561 stages are absent from the Monochrom bf0 symbol map;
- Monochrom retains `Process_Y`, `L3L1_Put8BitY`, Shading, Contrast, Noise and Sharpness;
- Shading and Contrast operate on the recovered scalar 14-bit coordinate;
- the downstream curve02 path is closed.

### Not yet proven

- exact `Process_Y` arithmetic;
- exact `Process_Y` input producer;
- native Monochrom CCD/FPGA sample semantics;
- whether Xiaomi should use direct Bayer-site reconstruction, and if so the best physically justified estimator;
- original noise/sharpness placement.

## 7. Immediate next executable work

Use locally extracted Leica M Monochrom `BF561/bf0` + the matching overlay `bf0.map` to extend the existing strict Blackfin tracing approach.

Do not write a broad permissive disassembler. Decode only the exact instruction forms present in `Process_Y` / `L3L1_Put8BitY`, assert the expected byte hashes/lengths, and fail visibly on drift.

Until those firmware bytes are available to the tracer, the correct project state is:

> SOURCE1D weighting track closed for the continuity scene; SOURCE1E topology narrowed; instruction-level `Process_Y` semantics still open.
