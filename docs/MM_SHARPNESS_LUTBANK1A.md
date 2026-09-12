# M Monochrom SHARPNESS LUTBANK1A

Date: 2026-09-12
Firmware: original Leica M Monochrom 1.022
Research branch: `research/mm-sharpness-lutbank1a`

## Status

The canonical `PROCESS/LUTS` range `0x58c..0x105cc` is now directly supported as the original M Monochrom ISO-indexed **sharpness source bank**.

This is stronger than the earlier geometric/cross-camera hypothesis. The archive header, runtime pointer construction, ISO row loader, sharpness scratch buffer, `Process_Sharpness`, and `UM_Gauss3LUT` call chain now connect without needing a visual guess.

This does **not** yet prove the complete arithmetic performed inside `UM_Gauss3LUT`, the exact meaning of every one of the 2050 signed values, or final photographic ordering relative to every other processing branch.

## Canonical bank geometry

The M Monochrom `PROCESS/LUTS` payload has:

- ISO count at archive `0x98`: `16`;
- ISO sequence: `320, 400, 500, 640, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000, 6400, 8000, 10000`;
- candidate bank start: `0x58c`;
- candidate bank end: `0x105cc`;
- bank size: `65,600` bytes;
- row count: `16`;
- values per row: `2050` signed int16;
- bytes per row: `4100`.

Therefore:

```text
0x105cc - 0x58c
= 65600 bytes
= 16 * 2050 * 2
```

All 16 rows are distinct.

A separate M9 firmware proof established that its known Sharp bank also uses 2050 signed-int16 values per ISO row. Cross-camera row-shape correlations between the Monochrom candidate bank and the M9 proven Sharp bank are approximately `0.9997..0.999999`, which was strong supporting evidence before the direct consumer trace was closed.

Geometry workflow:

- run: `34686147012`
- artifact: `MMonochrom-LUTBANK-GEOMETRY1A`

## Archive -> runtime sharpness structure

`LoadLutArchiveL3` copies the first `0x4c` bytes of the archive into its static header structure.

Two canonical header fields matter directly:

```text
archive header +0x10 = 0x408
archive header +0x14 = 0x58c
```

The function uses header `+0x10` as a source offset for a `0x184`-byte copy into runtime `ctx+0x470`.

Canonical archive value:

```text
*(uint32 *)(archive + 0x40c) = 2050
```

lands at:

```text
ctx + 0x474
```

The function also computes:

```text
ctx + 0x468 = archive_base + 0x58c
```

The runtime sharpness structure can therefore be expressed as:

```text
sharp = ctx + 0x460
```

with the currently closed fields:

```text
sharp+0x00 = sharpness selector copied by SetStructParameter
sharp+0x04 = per-selector/per-ISO modifier code selected by Set
sharp+0x08 = archive source bank base = PROCESS/LUTS + 0x58c
sharp+0x0c = destination scratch buffer
sharp+0x14 = row count = 2050
sharp+0x18... = modifier lookup-table area used by Set
```

## ISO indexing

`LoadISODataL1` is **not** the 2050-word row copier.

Its compact implementation selects a small ISO-indexed 32-bit value at approximately:

```text
base + 0x5c + 4*index
```

and stores its low word at structure `+0x04`.

The sharpness source-row copier is `LoadAndModifySharpnessDa`.

`SetStructParameter` maps the relevant input setting onto runtime `ctx+0x7c`, which is bounded to `0..15` for the normal path and therefore matches the 16 physical ISO rows. One special input case takes a separate branch; exact external-enum naming remains outside this closure.

## Per-selector/per-ISO modifier selection

`Set` derives the value later read as `sharp+0x04` from both the sharpness selector and ISO slot.

The traced address arithmetic reduces to:

```text
m = *(sharp+0x00)
i = *(ctx+0x7c)
modifier_code = *(uint32 *)(ctx + 0x478 + 76*m + 4*i)
*(sharp+0x04) = modifier_code
```

`LoadAndModifySharpnessDa` accepts modifier codes `1..12`. Values outside that interval return before the source-row copy. Code `0` is therefore a disabled/no-load state at this loader boundary, but this alone does not assign the exact public UI label.

## Direct source-row consumer

For core A, `LoadAndModifySharpnessDa` is at `0xffa12f20`.

The function performs the equivalent of:

```text
count = *(sharp+0x14)
row_offset_bytes = iso_slot * count * 2
src = *(sharp+0x08) + row_offset_bytes
dst = *(sharp+0x0c)
DMAmemcpy(dst, src, count*2)
```

With the canonical values this becomes:

```text
count = 2050
row bytes = 4100
src = PROCESS/LUTS + 0x58c + iso_slot*4100
```

The copied signed-int16 row is then modified in place using the selected modifier descriptor. The traced loop performs signed multiply/shift arithmetic and clamps each value to:

```text
[-2048, +2048]
```

The mirrored core follows the same structure.

Consumer-trace run:

- run: `34686656586`
- derived artifact contains the direct call and field evidence.

## Run -> loader -> Process_Sharpness

`Run` directly invokes the row loader.

Core A:

```text
R0 = ctx + 0x460
R1 = [ctx + 0x7c]
CALL LoadAndModifySharpnessDa
```

Later in `Run`, `Process_Sharpness` is called and receives the same `sharp = ctx+0x460` structure through the caller stack.

`Process_Sharpness` reads:

```text
count = [sharp+0x14]
table = [sharp+0x0c]
modifier = [sharp+0x04]
```

The table pointer is therefore the scratch buffer populated from the selected `PROCESS/LUTS + 0x58c` ISO row.

`Process_Sharpness` then calls the named firmware routine:

```text
UM_Gauss3LUT
```

Core A call:

```text
0xffa028e2 -> 0xffa12fcc  UM_Gauss3LUT
```

Core B has the mirrored call to its corresponding `UM_Gauss3LUT` instance.

This closes the source-bank classification:

```text
PROCESS/LUTS
  header +0x14 = 0x58c
  header +0x10 -> metadata block containing count 2050
        |
LoadLutArchiveL3
        |
sharp+0x08 = archive + 0x58c
sharp+0x14 = 2050
        |
SetStructParameter / Set
  ISO slot + sharpness selector -> modifier code
        |
Run
        |
LoadAndModifySharpnessDa
  selected 4100-byte ISO row -> scratch
  signed scale/shift, clamp [-2048,+2048]
        |
Run
        |
Process_Sharpness
  reads scratch + count
        |
UM_Gauss3LUT
```

## 2050-word structure: next unresolved detail

`Process_Sharpness` derives a half-count coordinate from `2050`:

```text
2050 / 2 = 1025
```

and computes a table pointer reaching word index `1024` before calling `UM_Gauss3LUT`.

That is strong evidence that the 2050-word row has an internal two-part / half-row structure, but **the exact interpretation is not yet proven**. It must be resolved from `UM_Gauss3LUT` itself rather than named by analogy.

## Current project consequence

The Android RAWSCALAR1B source bridge and canonical Monochrom curve02 remain frozen.

No sharpness LUT has been added to the Android photographic path yet. Firmware research must first close:

1. `UM_Gauss3LUT` input/output arguments;
2. exact use of the 2050-word row and the 1025-word half coordinate;
3. integer widths, signedness, rounding and saturation;
4. placement/branch conditions needed to reproduce the native operation without importing M9 assumptions.

Only after those are closed should a firmware-derived Monochrom sharpness stage be considered for an Android A/B implementation.
