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

## 1. BF561 provenance correction — old handoff vs canonical fixed-record result

There is an explicit contradiction in the research record and it must not be hidden.

The earlier v1.00 handoff described a broad comparison in terms of **"symbol-like tokens"** and reported 299 Monochrom tokens, 300 M9 tokens, 299 common. That note listed names such as:

- `Process_WB`
- `ExecuteColorMatrix_14FM1`
- `Process_FPGA_Y`
- `Process_FPGA_YCrCb`
- `SetMatrixL3`
- `LoadLutDataL3`
- `L3L1_Put3yycrcb`
- `Process_DNGNoise`

as shared processing vocabulary.

The later canonical `docs/FIRMWARE_BASELINE_v0_1.md` used a stricter representation: `BF561/bf0.map` is parsed as 32-byte fixed records containing a 24-byte symbol name plus exact address and size. Its result is:

```text
Monochrom bf0.map size        = 13,440 bytes
Monochrom fixed records       = 420
Monochrom map in M9 bf0.map   = exact byte substring at 0x3940
```

Every exact Monochrom `(name,address,size)` record is therefore present in M9, but the following M9 `bf0` records are absent from Monochrom `bf0`:

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

The repository's `tools/compare_m9_mm.py` implements this exact fixed-record and byte-substring comparison. For SOURCE1E, **that result outranks the earlier broad token inventory** because it identifies the exact active `bf0.map` records rather than merely observing symbol-like strings somewhere in a larger data set.

The reason the older token inventory saw those names is **not yet proven**. A plausible explanation is that it mixed another BF561 overlay/map or broader firmware strings into the inventory; notably, Monochrom and M9 `bf1.map` are byte-identical. This remains a hypothesis until the original firmware/map files are rerun through both methods.

`tools/trace_scalar_topology.py` has therefore been hardened to reproduce the canonical evidence when the maps are available. In strict mode it now checks:

- Monochrom `bf0.map` size = 13,440 bytes;
- Monochrom fixed-record count = 420;
- exact Monochrom-map byte containment in M9 `bf0.map` at `0x3940`;
- exact `(name,address,size)` tuple containment;
- canonical M9 `bf0.map` SHA-256 from the existing checkpoint;
- presence/absence of the disputed colour-path records;
- optional Monochrom/M9 `bf1.map` byte identity and disputed-name presence there.

Until that rerun is possible, the correct wording is:

> The earlier shared-token claim is superseded for `bf0` trace targeting by the stricter fixed-record result, while the historical discrepancy itself remains open for provenance diagnosis.

## 2. Current Monochrom bf0 trace target

The canonical fixed-record result retains the scalar/spatial family including:

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

Therefore `Process_FPGA_Y` / `Process_FPGA_YCrCb` are **not current Monochrom `bf0` named-function trace targets**. They remain useful as M9 colour-camera provenance for the BT.601 control formula.

This does not prove that no equivalent arithmetic could be inlined, implemented in BF547/FPGA, or exposed through another overlay. It only closes the named-symbol question for the canonical Monochrom `bf0` map if the fixed-record evidence is reproduced.

## 3. Architectural implication

The current `bf0` topology is consistent with a simpler Monochrom image path:

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

## 4. SOURCE1E instruction trace

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

Back-slice the buffer consumed by `Process_Y` / Shading / Contrast until the earliest producer visible in BF561/BF547/FPGA control flow.

Candidate descriptions must remain descriptive until proven:

- direct sensor intensity;
- FPGA scalar plane;
- CCD-preprocessed 14-bit plane;
- L3/L1 intermediate;
- another scalar representation.

### D. runtime processing-list evidence

`Run`-style dispatcher case order must not be mistaken for photographic pipeline order. The M9 investigation already established that overlay maps can contain alternate/overlapping L1 mappings and that `Run` dispatches jobs from a runtime processing list. SOURCE1E must therefore establish actual buffer lineage and job-record ordering rather than read a pipeline from symbol/case order.

Target evidence:

```text
producer
  -> Process_Y / Process_Shading / Process_Contrast
  -> L3L1_Put8BitY
```

## 5. Xiaomi SOURCE1E consequence

If the firmware trace confirms that a single scalar intensity field exists before the Leica spatial/tone stages, the next Xiaomi counterfactual should move **before RGB demosaic weighting**.

Candidate controls, all using the same frozen Leica tone stage:

1. current post-MHC M9-Y control;
2. current post-MHC XYZ-Y counterfactual;
3. a photosite-domain scalar reconstruction from the black-subtracted, physically lens-shaded Bayer plane;
4. a CFA-neutral / green-pair scalar estimator only if its construction is explicitly justified and logged.

Do not invent Leica spectral coefficients. The purpose is architectural matching, not aesthetic desaturation.

## 6. Frozen constraints

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

## 7. Evidence boundary

### Proven/recovered in the current research record

- Monochrom and M9 share the firmware family but diverge in photographic executable/data behavior;
- the downstream scalar 14-bit Shading/Contrast coordinate is recovered;
- the canonical curve02 path is closed;
- SOURCE1D continuity-scene RGB weighting differences are overwhelmingly affine/global;
- the canonical fixed-record analysis reports the named M9 colour path absent from Monochrom `bf0`, with Monochrom `bf0` embedded exactly in M9 `bf0` at `0x3940`.

### Must be reproduced when the firmware/maps are available again

- the canonical `bf0` fixed-record/subsequence result, because an older broad-token handoff conflicts with it;
- whether `bf1.map` or another overlay/source explains the old shared-token inventory.

### Still open

- exact `Process_Y` arithmetic;
- exact `Process_Y` input producer;
- native Monochrom CCD/FPGA sample semantics;
- whether Xiaomi should use direct Bayer-site reconstruction, and if so the best physically justified estimator;
- original noise/sharpness placement.

## 8. Immediate executable work

When the extracted firmware assets are available, run the hardened topology check first:

```bash
python tools/trace_scalar_topology.py \
  --mono-map /path/to/mm/BF561/bf0.map \
  --m9-map /path/to/m9/BF561/bf0.map \
  --mono-bf1-map /path/to/mm/BF561/bf1.map \
  --m9-bf1-map /path/to/m9/BF561/bf1.map \
  --strict
```

Only after that provenance check passes should the instruction decoder be extended for `Process_Y` and `L3L1_Put8BitY`.

Do not write a broad permissive disassembler. Decode only instruction forms present in those routines, assert exact byte hashes/lengths, and fail visibly on drift.

Until those firmware bytes are available to the tracer, the correct state is:

> SOURCE1D weighting track closed for the continuity scene; SOURCE1E `bf0` target narrowed by stricter evidence; old token-vs-record discrepancy explicitly recorded; instruction-level `Process_Y` semantics still open.
