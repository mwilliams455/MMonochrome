# SOURCE1E scalar architecture closure v0.1

Date: 2026-09-12
Target: Leica M Monochrom firmware 1.022
Branch: `research/source1e-processy`

## Decision

SOURCE1E closes the question of **where the authentic Monochrom photographic tone path expects its image signal** strongly enough to stop searching for a post-demosaic RGB/Y coefficient formula.

The canonical M Monochrom firmware is now directly evidenced as carrying its photographic image through a **16-bit scalar/word image domain upstream of the native contrast LUT**, with `Process_Y` occurring only after the 16-bit-to-8-bit contrast transition. The Xiaomi bridge should therefore move upstream of RGB colour rendering and construct a scalar image from the Bayer RAW before the frozen Leica contrast/curve stage.

This does **not** recover the spectral response of the Leica monochrome CCD. A Xiaomi Bayer-to-scalar adapter remains a sensor-translation problem and must be labelled as such.

## Hash-bound firmware evidence

### 1. `Process_Y` is downstream 8-bit Y handling, not the sensor scalar producer

Canonical routine:

- address `0xffa028e8`
- size `292`
- SHA-256 `f0694943391ab9b5c2cd75119d7bba5ff817fd5bbbaa2c6598a198cc97d7e22a`

Recovered behaviour: 8-bit Y raster/resolution handling and 8x8 packing. It does not generate the 14-bit photographic scalar from sensor data.

### 2. `Process_Contrast` is the native scalar-to-8-bit transition

Canonical routine:

- address `0xffa00b30`
- size `508`
- SHA-256 `790659b15a6655d60a750542c69f98eb22c66b300cdb8ad9e4077174aec6a47d`

Mode-0 core:

`out8 = curve[max(uint16(sample)-pedestal, 0) >>> 3]`

The frozen normal-ISO / sRGB / Standard curve is canonical `curve02`, 2048 bytes, SHA-256:

`7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752`

### 3. `Run` dispatches scalar processing before `Process_Y`

Canonical `Run`:

- address `0xffa01790`
- size `2444`
- SHA-256 `9a7aef3a340f4617b547accff61ed72ddb8b466cd5d01f0758542e0756fd58f0`

Verified enabled-stage ordering includes:

`Process_Shading -> ... -> Process_Noise -> Process_Sharpness -> Process_Contrast -> Process_Y`

The ordinary path's initial `L3L1_Get` uses selector 0, loading the first processing-context L3 scalar plane into the L1 16-bit working plane.

### 4. Raw image storage is a fixed-stride buffer bank

`IM_GetRawBuffer(index)` is verified as:

`index * 0x01450000`

where the stride is 21,299,200 bytes.

Two concrete bank addresses:

- slot 7: `0x08e30000`
- slot 8: `0x0a280000`

`IM_AppendItem` synthesizes its queued job record rather than accepting arbitrary RGB-image pointers:

- job `+0x2c = payload_byte_7 * 0x01450000`
- job `+0x30 = payload_byte_8 * 0x01450000`
- job `+0x28 = fixed slot 8`

`SetProcess` maps those fields into the processing context:

- context `+0x00 <- job+0x2c`
- context `+0x04 <- job+0x30`
- context `+0x0c/+0x10 <- job+0x28`

`InitInterpolation` reserves raw-buffer slot 7 at context `+0x08`.

### 5. The sensor transfer interface itself addresses this raw-buffer bank

`SPI_SetNextImage` converts its raw-buffer selector with `IM_GetRawBuffer`, then supplies that address to `Sensor_InitTransfer` before `Sensor_Enable`.

`Sensor_InitTransfer` writes the selected address into the sensor-transfer DMA address registers. Therefore the image-processing bank is not a late RGB construction: it is directly connected to the sensor-transfer plumbing.

The separate PPI path is explicitly `Memory2PPI`; its use of fixed slot 8 must not be mislabelled as sensor capture.

### 6. Native dual-output correction is pre-normal-processing and 16-bit scalar

Hash-bound CI verifies that the `Run` bit-10 special path invokes:

`CorrectionDualOutput @ 0xffa11c8c`

before returning to the ordinary `Run` path and before `InitL1MemoryProcessing` / the ordinary selector-0 `L3L1_Get`.

`CorrectionDualOutput` iterates over processing-context L3 slot 0 (`context+0x00`) and slot 1 (`context+0x04`), DMA-loads the selected plane into the shared L1 16-bit working plane (`context+0x34`), invokes the native dual-output correction algorithm, and can DMA-write the corrected words back to the same selected L3 plane.

Active correction routines:

- `Process_DualOutputCorrec @ 0xffa11910`, size 890, SHA-256 `b5aedafcafe154e37791aa88f3daba3ce5cd4cc21ba41fdba6ca9efec59c2b86`
- `Process_DualOutputCorrec @ 0xffa00d30`, size 1198, SHA-256 `4d768941d48977a185cb29af572dea5f4192e73342b95d27d5254b947d2e6a69`

Both routines operate on 16-bit word samples. No RGB or YCrCb generation is involved in this verified segment.

CI run `34678038514` passed the strict dual-output scalar verifier with zero problems.

## Cross-generation control

The active M9 firmware has explicit colour-path routines including `Process_FPGA_YCrCb`, `Process_FPGA_Y`, colour-matrix and WB processing. The active Monochrom path investigated above instead remains scalar through its pre-contrast processing. M9 is used only as an architectural control; its Bayer luma coefficients are not Monochrom spectral truth.

## What SOURCE1E closes

The following hypotheses are closed for the Android photographic source adapter:

- Do not choose a final Monochrom source by tuning post-demosaic BT.601/M9 luma coefficients.
- Do not choose a final Monochrom source from a DNG XYZ-Y matrix and call it Leica-native behaviour.
- Do not treat `Process_Y` as the Monochrom sensor-luminance generator.
- Do not insert M9 HSM/SAT3/colour reconstruction into the Monochrom path.

The firmware-supported insertion point is a **scalar image before the frozen Leica 16-bit contrast stage**.

## What remains unknown

Firmware cannot make the Xiaomi Bayer CFA behave spectrally like the Leica monochrome CCD. Still unresolved:

- the Leica CCD spectral sensitivity curve;
- a unique physically correct mapping from Xiaomi R/G/B filtered photosites to that sensitivity;
- whether the two queued L3 planes correspond exactly to analog dual outputs, ping-pong image buffers, or another capture-specific pairing in every mode;
- whether the dual-output correction bit is enabled for every ordinary photographic capture.

These are explicit boundaries, not reasons to return to post-demosaic colour tuning.

## Android next experiment: RAWSCALAR1A

The next device experiment should be diagnostic and raw-domain:

1. Start from the same single Xiaomi RAW.
2. Perform black/white normalization and the physical Camera2 LensShadingMap exactly once, as in the current frozen source adapter.
3. Before MHC RGB demosaic, normalize Bayer photosite responses onto the captured-neutral axis using the same physical-camera neutral metadata already recorded by the build.
4. Spatially reconstruct one full-resolution scalar plane from those neutral-normalized Bayer observations. Any interpolation used here is a **Xiaomi CFA reconstruction mechanism**, not a Leica colour transform.
5. Map that scalar to Leica's `0..16383` working coordinate.
6. Apply the same frozen mode-0 pedestal/index arithmetic and canonical `curve02` with no TC20, HDR, HSM, SAT3, WB colour pipeline, or exposure retuning.
7. Save RAWSCALAR1A as a diagnostic auxiliary JPEG alongside the current primary/control outputs. Do not promote it until same-RAW photographic comparison supports promotion.

Recommended first estimator: neutral-normalize the raw CFA samples, use the existing high-quality MHC spatial reconstruction only as the Xiaomi CFA interpolation engine, and collapse the reconstructed neutral-axis channels with an equal scalar mean. This avoids re-introducing M9 luma or XYZ coefficients while retaining native resolution. It must be labelled `not_Leica_spectral_truth`.

## Promotion rule

RAWSCALAR1A can replace the provisional post-MHC M9-Y primary only after:

- same-RAW comparisons show no unacceptable resolution/texture regression;
- neutral scenes are free of CFA phase patterning;
- strongly coloured objects do not create obvious checker/lattice artifacts;
- highlights and dense shadows retain the frozen Monochrom tone behaviour;
- the diagnostic sidecar confirms that the source was formed before the colour pipeline and that `curve02` remained unchanged.

Until then, current SOURCE1D remains the installable control build and SOURCE1E remains a research closure plus diagnostic-development track.
