# Next research target

Continue on `research/mm-firmware-r0` from `docs/LUT_SELECTOR_TRACE_v0_3.md`.

The Monochrom contrast/tone selector is now closed:

- `SetLutL3` generic 4-D flattening is decoded.
- `SetStructParameter` proves `i0=nContrast`, `i1=nColorSpace`, `i2=nSaturation`, `i3=(nIso==4)`.
- archive metadata is exactly `[60, 2048, 2, 5, 3, 2]`.
- the 60-curve bank is `5 contrast x 2 color spaces x 3 saturation states x 2 ISO paths`.
- the three saturation slices are byte-identical for this tone bank.
- the canonical 20-curve bank is the exact 60-bank collapse.
- BF547 proves `Standard=2`, `sRGB=0`, and `PULL 160=4`.
- normal ISO / sRGB / Standard therefore selects canonical curve `02`.

Next, trace the active Monochrom contrast consumer:

1. decode `Process_Contrast` at `0xFFA00B30` and its call from `Run`;
2. prove which `ExecuteContrast_11LUT8_7`, `_2`, or `_3` kernel is selected for the normal still/JPEG path;
3. recover exact input width/domain and LUT-index arithmetic;
4. recover interpolation, rounding/truncation and clamp behavior;
5. recover output width/domain;
6. place the stage relative to `Process_Y`, noise, shading and sharpness;
7. then return to `LoadISODataL1` and the 16 x 2 x 2050-word ISO-aligned bank.

Do not import the later M9 colour-path conclusion that contrast is fused into ColorMatrix: M Monochrom `Run` directly calls `Process_Contrast`.
