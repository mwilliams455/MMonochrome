# M Monochrom 1.022 — contrast LUT selector trace v0.3

Date: 2026-09-11  
Branch: `research/mm-firmware-r0`  
Target: original Leica M Monochrom firmware 1.022

## Status

The contrast/tone LUT family selection is now closed far enough to identify the firmware-authentic normal-ISO / sRGB / Standard curve without using curve shape as evidence.

The proof joins four independent layers:

1. BF561 `SetLutL3` flattening arithmetic;
2. BF561 `SetStructParameter` process-record field routing;
3. `PROCESS/LUTS` descriptor metadata and exact bank repetition;
4. BF547 menu records naming the enum values.

## 1. Runtime selector fields

`SetStructParameter` routes the process-setting record into the descriptor consumed by `SetLutL3` as follows:

```text
record +10 -> i0
record +14 -> i1
record +11 -> i2
record + 9 -> i3, where i3 = 1 iff value == 4, else 0
```

The BF547 diagnostic/process-field sequence names the same record positions:

```text
+9   nIso
+10  nContrast
+11  nSaturation
+12  nNoise
+14  nColorSpace
```

Therefore:

```text
i0 = nContrast
i1 = nColorSpace
i2 = nSaturation
i3 = (nIso == 4)
```

## 2. Archive descriptor dimensions

`LoadLutArchiveL3` copies a 24-byte descriptor block from `PROCESS/LUTS` into the runtime object later consumed by `SetLutL3`.

At `PROCESS/LUTS + 0x105CC`, those six 32-bit words are exactly:

```text
60
2048
2
5
3
2
```

Important boundary distinction:

- `0x105CC` is descriptor metadata;
- the actual 60-curve byte payload begins at `0x10714`.

Mapped onto the already-decoded `SetLutL3` fields:

```text
element_size = 2048
N0 = 5
N1 = 2
N2 = 3
outer i3 states = 2
```

The generic flattening rule is therefore:

```text
curve60 =
    nContrast
  + 5 * (
      nColorSpace
    + 2 * (
        nSaturation
      + 3 * isSpecialIso
      )
    )
```

or:

```text
curve60 = nContrast + 5*nColorSpace + 10*nSaturation + 30*isSpecialIso
```

This gives exactly:

```text
5 contrast states
x 2 color spaces
x 3 saturation states
x 2 ISO paths
= 60 curves
```

## 3. Saturation dimension is structurally present but tone-neutral

The 60-curve payload at `0x10714` contains only 20 unique 2048-byte curves.

Exact byte equality is:

```text
0  = 10 = 20
1  = 11 = 21
...
9  = 19 = 29

30 = 40 = 50
31 = 41 = 51
...
39 = 49 = 59
```

Thus all three `nSaturation` slices select byte-identical tone curves.

This does **not** mean `nSaturation` is an unused process setting globally. It means that in this particular Monochrom 2048-byte tone LUT family, saturation remains one dimension of Leica's generic selector infrastructure but does not alter the curve payload.

## 4. Canonical 20-curve bank is an exact collapse

The final 20 x 2048-byte bank at `0x7F6FC` equals exactly:

```text
60-bank[0..9]
+
60-bank[30..39]
```

Therefore the tone-only selector collapses to:

```text
curve20 = nContrast + 5*nColorSpace + 10*isSpecialIso
```

## 5. BF547 enum names close the remaining semantics

The Monochrom BF547 menu records prove the relevant values directly.

### Contrast

Five records at file offset `0xBE8CC`, stride 20 bytes:

```text
0 -> Low
1 -> Medium low
2 -> Standard
3 -> Medium high
4 -> High
```

Therefore:

```text
nContrast = 2 -> Standard
```

### Color space

Records at file offset `0xBF4CC`:

```text
0 -> sRGB
1 -> Adobe RGB
```

Therefore:

```text
nColorSpace = 0 -> sRGB
```

### Special ISO enum

The ISO menu records include:

```text
PULL 80  -> enum 1
PULL 160 -> enum 4
ISO 200  -> enum 5
ISO 250  -> enum 6
ISO 320  -> enum 7
...
```

BF561's special branch is specifically:

```text
nIso == 4
```

so on M Monochrom 1.022:

```text
isSpecialIso = isPull160
```

This must not be relabelled as M9 Pull80 merely because the M9 uses a homologous architecture.

## 6. Final canonical family map

After collapsing the byte-identical saturation slices:

| Curves | ISO path | Color space | Contrast |
|---|---|---|---|
| `00-04` | normal | sRGB | 0..4 |
| `05-09` | normal | Adobe RGB | 0..4 |
| `10-14` | Pull160 | sRGB | 0..4 |
| `15-19` | Pull160 | Adobe RGB | 0..4 |

For the target normal-ISO / sRGB / Standard JPEG path:

```text
nContrast = 2
nColorSpace = 0
isPull160 = 0

curve20 = 2
```

Therefore:

```text
normal ISO / sRGB / Standard = curve 02
```

This result is now firmware-supported from Monochrom 1.022 itself. It is no longer inherited from the M9 project or inferred from the middle member of a five-curve family.

## 7. Reproducibility

Run:

```bash
python tools/probe_curve_selector.py /path/to/mm-1_022.decrypted.upd
```

The verifier checks:

- canonical `PROCESS/LUTS` SHA-256;
- canonical BF547 SHA-256;
- descriptor `[60, 2048, 2, 5, 3, 2]`;
- all 60-bank saturation repetitions;
- exact 60 -> 20 bank collapse;
- Contrast menu enums;
- sRGB / Adobe RGB enums;
- Pull80 / Pull160 enum distinction.

No Leica firmware bytes are stored in the repository.

## 8. Next target

The selector question is no longer the blocker.

The next high-value question is the actual Monochrom contrast consumer:

```text
Run
  -> Process_Contrast
  -> ExecuteContrast_11LUT8_?
  -> selected 2048-byte curve
  -> output image coordinate
```

Recover exactly:

1. which `ExecuteContrast_11LUT8_7`, `_2`, or `_3` implementation is selected for the normal still/JPEG path;
2. input sample width and numerical domain;
3. exact LUT index calculation;
4. interpolation vs direct lookup;
5. rounding/truncation;
6. endpoint/clamp behavior;
7. output sample width/domain;
8. placement relative to `Process_Y`, noise, shading and sharpness.

Unlike the later M9 colour path, the Monochrom `Run` routine directly calls `Process_Contrast`, so the M9 conclusion that the selected curve is fused into ColorMatrix must not be transferred to this camera.
