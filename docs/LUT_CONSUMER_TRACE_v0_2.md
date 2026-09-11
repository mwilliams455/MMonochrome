# M Monochrom 1.022 — LUT consumer trace v0.2

Date: 2026-09-11
Branch: `research/mm-firmware-r0`
Firmware target: Leica M Monochrom 1.022

## Status

Two high-value BF561 helpers are now decoded to exact arithmetic semantics rather than inferred from table shape:

- `SetLutL3` at `0xFEB10E70`
- `LoadISODataL1` at `0xFEB11BF0`

The decoder is intentionally narrow and strict. It recognizes only the Blackfin forms present in these routines and fails if the firmware bytes drift from the expected instruction stream.

## 1. LoadISODataL1 — closed

Firmware bytes SHA-256:

`32c47c722ff3c947da899ca4f545d65ecebd4ec7b92b8ffc7288d783e2fc764f`

Exact decoded instruction semantics:

```text
P1 = R0
P0 = 0x5C
P2 = [P1]
P0 = P1 + P0
P0 = P0 + (P2 << 2)
R0 = [P0]
P0 = [FP-32]
RTS
```

Equivalent C-like expression:

```c
return *(uint32_t *)(descriptor + 0x5C + 4 * descriptor->iso_slot);
```

Therefore:

- descriptor word `+0x00` is the active ISO slot/index consumed by this helper;
- descriptor `+0x5C` begins a 32-bit per-ISO entry table;
- each ISO-slot entry is four bytes;
- this helper performs no image arithmetic and no interpolation: it is an indexed pointer/value lookup.

This gives a firm consumer-side anchor for connecting the 16-entry ISO list in `PROCESS/LUTS` to the runtime descriptor.

## 2. SetLutL3 — arithmetic closed

Firmware bytes SHA-256:

`7ebdb6b4b79499f40a1ae78d4ffcaf1b5ff03744172b721f7becb6d12c3630d8`

Exact decoded dataflow:

```text
R1 = f12
R0 = f44
R2 = f40
R0 = R0 * R1
R2 = R2 * R1
R3 = f8
R0 = R0 * R3
R3 = R3 * R2
R2 = f16
R2 = R2 * R0
R2 = R2 + R3
R0 = f32
R0 = R0 * R1
R0 = R2 + R0
R1 = f36
R0 = R0 + R1
R2 = f28
R1 = f24
R2 = R1 + R2
R1 = f4
R0 = R0 * R1
R0 = R2 + R0
f48 = R0
```

Closed formula:

```text
f48 = f24 + f28 + f4 * (
          f36
        + f12 * (
              f32
            + f8 * (
                  f40
                + f16 * f44
              )
          )
      )
```

The natural multidimensional-array interpretation is:

```text
resolved = base
         + element_size * [
               i0
             + N0 * (
                   i1
                 + N1 * (
                       i2
                     + N2 * i3
                   )
               )
           ]
```

with the descriptor mapping:

```text
+0x04  element_size
+0x08  N1
+0x0C  N0
+0x10  N2
+0x18  base component A
+0x1C  base component B
+0x20  i1
+0x24  i0
+0x28  i2
+0x2C  i3
+0x30  resolved offset/pointer
```

The exact arithmetic is proven. The semantic names of `N0/N1/N2` and `i0..i3` remain open until their population in `Set` / archive loading is traced.

## 3. M9 cross-generation comparison

The earlier M9 firmware investigation solved its 20-curve selector as:

```text
curve_index = 10*A + 5*B + nContrast
```

where:

```text
A = normal ISO / Pull 80 selector
B = sRGB / Adobe RGB selector
nContrast = 0..4
```

The M9 `SetLutL3` implementation is shorter, but decoding its arithmetic gives the same general model: a base plus a stride multiplied by a flattened selector expression.

This supports treating the longer Monochrom `SetLutL3` as the same architectural concept expanded to more dimensions, rather than as unrelated arithmetic.

It does **not** yet prove that the Monochrom dimensions have the same semantic labels as the M9 dimensions. In particular, the M Monochrom has no color-rendering requirement analogous to the M9 matrix path, so names must come from actual descriptor population.

## 4. PROCESS/LUTS metadata clue — open, not frozen

Near the canonical 20-curve bank, the Monochrom archive contains the compact sequence beginning at `0x7F19C`:

```text
0
2048
2
5
5
```

`2048` exactly matches the length of each 8-bit contrast/transfer curve, and the `2,5,5` values are compatible with dimension metadata for a structured LUT family.

This is a strong clue, but dimension assignment is **not yet closed**. The next proof step is to trace how `LoadLutArchiveL3` / `Set` copies archive metadata into the fields consumed by `SetLutL3`.

## 5. Immediate next trace

1. Trace the call at `Set + 0x82` (`0xFEB1168E`) into `SetLutL3` and recover the descriptor base passed in `R0`.
2. Back-slice stores into descriptor offsets `+0x04..+0x30` to name `element_size`, dimensions and indices.
3. Trace the call at `Set + 0x19C` (`0xFEB117A8`) into `LoadISODataL1` and identify how the returned ISO entry is consumed.
4. Connect the runtime `+0x5C` per-ISO table to the 16 ISO anchors and candidate 16×2×2050-word bank in `PROCESS/LUTS`.
5. Only after those links are proven should a curve number or ISO table be promoted into an offline renderer.

## Reproducibility

Run against locally extracted Leica firmware assets:

```bash
python tools/trace_lut_consumers.py \
  --ldr /path/to/bf0 \
  --map /path/to/bf0.map \
  --json
```

No Leica firmware bytes are stored in this repository.
