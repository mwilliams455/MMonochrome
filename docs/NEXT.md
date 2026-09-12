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

## BF561 topology provenance gate

An old project handoff reported broad shared **symbol-like tokens** and included names such as `Process_FPGA_Y`, `Process_FPGA_YCrCb`, `Process_WB`, and `ExecuteColorMatrix_14FM1` in that shared vocabulary.

The later canonical fixed-record analysis reports a stricter and conflicting result for the Monochrom imaging `bf0.map`:

```text
Monochrom bf0.map = 13,440 bytes / 420 fixed records
entire Monochrom bf0.map occurs inside M9 bf0.map at offset 0x3940
```

Under that exact `(name,address,size)` comparison, the M9 WB/ColorMatrix/FPGA-Y/YCbCr records are absent from Monochrom `bf0`, while `Process_Y`, `L3L1_Put8BitY`, Shading, Contrast, Noise, and Sharpness remain.

The exact fixed-record/byte-containment result is the stronger basis for current `bf0` trace targeting, but the historical discrepancy must be reproduced rather than silently forgotten. Its cause is open.

`tools/trace_scalar_topology.py` now performs the required provenance rerun. Before instruction-level SOURCE1E work, run it against the original maps in strict mode. When both `bf1.map` files are available, include them as an explicit cross-check because the canonical baseline reports those maps byte-identical.

## Immediate research target — SOURCE1E

### Gate A — reproduce map provenance

```bash
python tools/trace_scalar_topology.py \
  --mono-map /path/to/mm/BF561/bf0.map \
  --m9-map /path/to/m9/BF561/bf0.map \
  --mono-bf1-map /path/to/mm/BF561/bf1.map \
  --m9-bf1-map /path/to/m9/BF561/bf1.map \
  --strict
```

Required pass conditions include:

- 13,440-byte / 420-record Monochrom `bf0.map`;
- exact containment in M9 `bf0.map` at `0x3940`;
- every Monochrom exact tuple present in M9;
- disputed M9 colour-path records absent from Monochrom `bf0` and present in M9 `bf0`;
- optional `bf1.map` pair byte-identical when supplied.

### Gate B — anchor exact function bytes

Once Gate A passes, do not begin disassembly from copied snippets or unpinned addresses. Extract exact routine slices and SHA-256 anchors first:

```bash
python tools/extract_source1e_targets.py \
  --mono-ldr /path/to/mm/BF561/bf0 \
  --mono-map /path/to/mm/BF561/bf0.map \
  --m9-ldr /path/to/m9/BF561/bf0 \
  --m9-map /path/to/m9/BF561/bf0.map \
  --out-dir /tmp/source1e-functions \
  --strict
```

The extractor pins address, size and SHA-256 for `Process_Y`, `L3L1_Put8BitY`, Shading, Contrast, Noise, Sharpness, `CalculateNoiseParameter`, `LoadISODataL1`, `LoadLutArchiveL3`, and `Run`. With M9 assets present it also records whether each same-named function is byte-identical across generations.

A byte-identical `Process_Y` would be useful provenance but would **not** by itself prove identical upstream sensor semantics. A different `Process_Y` would immediately identify a Monochrom-specific executable target.

### Gate C — recover scalar buffer lineage

With exact routine hashes pinned, the active named path is:

```text
native producer
  -> Process_Y / Process_Shading / Process_Contrast
  -> L3L1_Put8BitY
```

Then:

1. extend the existing strict small Blackfin decoder only for opcodes actually present in `Process_Y` and `L3L1_Put8BitY`;
2. recover entry arguments, pointers, sample widths, strides, arithmetic, shifts/clamps, and calls;
3. trace buffers backward to their producer and forward through Shading/Contrast/output;
4. recover runtime processing-list order rather than treating dispatcher case order as photographic order;
5. inspect BF547/FPGA only where buffer/control-flow evidence points there.

Do not claim native CCD/FPGA semantics until that producer/consumer chain is closed.

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

The immediate fidelity bottleneck is the native scalar producer. The immediate forensic sequence is now fixed:

```text
bf0 provenance rerun
  -> exact function address/size/SHA anchors
  -> narrow instruction decode
  -> buffer lineage
  -> photosite-domain Xiaomi counterfactual only if justified
```
