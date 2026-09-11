# Next research target

Continue on `research/mm-firmware-r0` from `docs/LUT_CONSUMER_TRACE_v0_2.md`.

The low-level arithmetic is now closed for:

- `SetLutL3`: generic 4-D LUT address flattening into descriptor `+0x30`.
- `LoadISODataL1`: `descriptor + 0x5C + 4*iso_slot` indexed lookup.

Next, trace descriptor population in BF561 `Set` / `LoadLutArchiveL3`:

1. back-slice the descriptor passed to `SetLutL3` at `0xFEB1168E`;
2. assign semantic names to `element_size`, `N0/N1/N2`, and `i0..i3`;
3. follow the `LoadISODataL1` return from call `0xFEB117A8` to its first consumer;
4. prove which `PROCESS/LUTS` archive offsets populate the runtime `+0x5C` ISO table;
5. connect that table to the 16 ISO anchors and the candidate 16×2×2050-word bank before implementing renderer behavior.

Do not select a Monochrom Standard curve or ISO correction table from shape alone.
