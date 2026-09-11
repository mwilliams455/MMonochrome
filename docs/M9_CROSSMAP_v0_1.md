# Leica M9 1.216 -> M Monochrom 1.022 cross-map v0.1

This document records what can be reused from the M9 reverse-engineering work and what must be treated as new.

## Reuse directly as architecture/provenance

- 1021-byte XOR encryption family and key.
- PWAD parser and nested archive model.
- BF561 LDR/map parsing mechanics.
- Fixed-width 32-byte symbol-map records.
- Core buffer/DMA/interpolation framework.
- `Process_Contrast` family naming and symbol addresses.
- `Process_Noise`, `Process_Shading`, `Process_Sharpness`, `Process_Y` symbol identities.
- `LoadLutArchiveL3`, `LoadISODataL1`, and related loader architecture.
- Android/PhotonCamera capture, native renderer, queueing, RAW ownership, JPEG/DNG output and diagnostics can later be reused as implementation infrastructure.

## Do not reuse photographically without proof

- M9 colour matrices.
- M9 WB path.
- M9 YCbCr/FPGA luma arithmetic.
- M9 contrast curve values.
- M9 ISO correction values.
- M9 noise/sharpness parameters.
- M9 exposure normalization targets.
- M9 sensor->working-space calibration.

## Key code-map fact

The complete Monochrom `bf0.map` is an exact byte substring of the M9 `bf0.map`, beginning at M9 map byte offset `0x3940`.

This means the M9 map already contains every Monochrom BF0 symbol/address/size record. The reverse-engineering problem is therefore no longer "discover the architecture"; it is "identify the Monochrom implementations and data consumers inside an architecture already mapped by the M9 project."

## M9-only colour-path symbols absent from Monochrom

The absence of `Process_WB`, `ExecuteColorMatrix_14FM1`, `Process_FPGA_YCrCb`, `SetMatrixL3`, RGB output helpers and related interpolation/difference functions materially narrows the target.

That makes the first practical port likely simpler than the colour M9 port, but the Xiaomi Bayer -> pseudo-monochrome input reconstruction remains a new problem and should not be hidden behind a normal RGB desaturation step.
