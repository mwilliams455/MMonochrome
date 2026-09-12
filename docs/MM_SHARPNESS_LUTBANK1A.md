# M Monochrom SHARPNESS LUTBANK1A — KERNEL / STRENGTH CLOSED

Date: 2026-09-12  
Firmware: original Leica M Monochrom 1.022  
Research branch: `research/mm-sharpness-lutbank1a`

## Status

The original M Monochrom JPEG sharpness data path is now closed far beyond the earlier bank-classification hypothesis.

Firmware-direct evidence connects:

```text
Sharpening menu enum
-> raw selector 0..4
-> ISO slot 0..15
-> modifier code 0..12
-> exact modifier descriptor / integer scale
-> selected 2050-word ISO row
-> signed modified detail LUT
-> UM_Gauss3LUT
-> 14-bit scalar output
```

No generic sharpening model is required for the core arithmetic.

The remaining implementation gate is exact image argument / border placement around `UM_Gauss3LUT`, not the sharpening transfer function itself.

## Canonical ISO sharpness bank

`PROCESS/LUTS` contains the sharpness source bank at:

```text
0x58c .. 0x105cc
```

Geometry:

```text
16 ISO rows * 2050 signed int16 * 2 bytes = 65,600 bytes
```

ISO slots:

```text
0  320
1  400
2  500
3  640
4  800
5  1000
6  1250
7  1600
8  2000
9  2500
10 3200
11 4000
12 5000
13 6400
14 8000
15 10000
```

`LoadLutArchiveL3` establishes:

```text
sharp = ctx + 0x460
sharp+0x08 = PROCESS/LUTS + 0x58c
sharp+0x14 = 2050
sharp+0x0c = scratch destination
sharp+0x00 = sharpening selector
sharp+0x04 = ISO/selector modifier code
```

## Canonical Monochrom Sharpening menu — proven directly

A direct BF547 controller trace now proves the M Monochrom menu itself.

Descriptor:

```text
label       = Sharpening
control ID  = 0x1005
type        = 6
options ptr = 0xde604
```

Menu mapping:

```text
enum 0 -> Off
enum 1 -> Low
enum 2 -> Standard
enum 3 -> Medium high
enum 4 -> High
```

Therefore:

```text
M Monochrom Sharpening Standard = selector 2
```

This is no longer being borrowed from the M9; it is proven from M Monochrom 1.022 itself.

Menu proof:

- run: `34688085825`
- artifact: `MMonochrom-SHARPNESS-MENU1A`
- BF547 SHA-256: `8f82e5eb08c4933d821ce3df903a14846e300f940fee353514d37cda2c70b621`

## Selector x ISO modifier matrix — proven

The archive range immediately before the sharpness bank is exactly:

```text
0x410 .. 0x58c
= 0x17c bytes
= 5 rows * 19 uint32
```

The first 16 words of each 19-word row are the physical ISO modifier codes used by `Set`; the last three words are separate row metadata.

```text
Off / selector 0:
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0

Low / selector 1:
4 4 4 4 2 2 2 2 2 2 2 2 2 2 1 1

Standard / selector 2:
8 8 8 8 4 4 4 4 4 4 4 4 3 3 2 2

Medium high / selector 3:
11 11 11 11 8 8 8 8 8 8 8 7 6 5 4 3

High / selector 4:
12 12 12 12 11 11 11 11 11 11 11 10 9 8 7 6
```

Selector 0 always yields code 0. `LoadAndModifySharpnessDa` returns before row copy/modification for code <= 0, matching the proven public `Off` enum.

## Modifier descriptor table — exact values proven

The initial descriptor probe was misleading because each descriptor table straddles two adjacent LDR records: code 0 is the final two bytes of a zero-fill record and codes 1..12 begin in the next initialized record.

Reconstructing the BF0 load image across that boundary produces two mirrored tables with identical values.

Core A base:

```text
0xfeb001e8
```

Core B base:

```text
0xfeb030b0
```

Exact descriptor table:

```text
code : descriptor : rational scale
0    : 0          : disabled
1    : 1          : 0.25x
2    : 2          : 0.50x
3    : 3          : 0.75x
4    : 4          : 1.00x
5    : 5          : 1.25x
6    : 6          : 1.50x
7    : 7          : 1.75x
8    : 8          : 2.00x
9    : 10         : 2.50x
10   : 12         : 3.00x
11   : 13         : 3.25x
12   : 20         : 5.00x
```

The code intentionally reduces even descriptors before multiply/shift. Exact integer operations are therefore:

```text
code 1:  (x * 1)  >> 2
code 2:  (x * 1)  >> 1
code 3:  (x * 3)  >> 2
code 4:  (x * 1)  >> 0
code 5:  (x * 5)  >> 2
code 6:  (x * 3)  >> 1
code 7:  (x * 7)  >> 2
code 8:  (x * 2)  >> 0
code 9:  (x * 5)  >> 1
code 10: (x * 3)  >> 0
code 11: (x * 13) >> 2
code 12: (x * 5)  >> 0
```

followed by signed clamp:

```text
[-2048, +2048]
```

The rational scale is descriptor/4, but the exact reduced multiply/shift form must be retained because signed integer rounding differs across parity classes.

Modifier proof:

- run: `34688023264`
- artifact: `MMonochrom-SHARPNESS-MODIFIER1A`
- mirrored tables: identical
- descriptor sequence: `0,1,2,3,4,5,6,7,8,10,12,13,20`

## Standard sharpness strength vs ISO

Because Standard is now proven as selector 2, the native Standard schedule is exact:

```text
ISO 320  -> code 8 -> 2.00x
ISO 400  -> code 8 -> 2.00x
ISO 500  -> code 8 -> 2.00x
ISO 640  -> code 8 -> 2.00x
ISO 800  -> code 4 -> 1.00x
ISO 1000 -> code 4 -> 1.00x
ISO 1250 -> code 4 -> 1.00x
ISO 1600 -> code 4 -> 1.00x
ISO 2000 -> code 4 -> 1.00x
ISO 2500 -> code 4 -> 1.00x
ISO 3200 -> code 4 -> 1.00x
ISO 4000 -> code 4 -> 1.00x
ISO 5000 -> code 3 -> 0.75x
ISO 6400 -> code 3 -> 0.75x
ISO 8000 -> code 2 -> 0.50x
ISO 10000-> code 2 -> 0.50x
```

This confirms an explicit Leica policy of reducing detail correction as ISO rises.

## Row loading and modification

`LoadAndModifySharpnessDa` performs:

```text
count = 2050
src = PROCESS/LUTS + 0x58c + iso_slot * 4100
dst = scratch
DMAmemcpy(dst, src, 4100)
```

Then for every signed int16 LUT sample `x`:

```text
y = arithmetic_shift_right(x * multiplier(code), shift(code))
y = clamp(y, -2048, +2048)
```

The modified scratch row is what `Process_Sharpness` passes into `UM_Gauss3LUT`.

## 2050-word row semantics — helper path closed

`Process_Sharpness` computes:

```text
half = 2050 / 2 = 1025
bound = half - 1 = 1024
center_ptr = &table[1024]
clipMag = -table[0]
```

The small firmware helper named `LUT` is now disassembled exactly:

```text
LUT(detail, bound, clipMag, center_ptr):
    if -bound <= detail <= bound:
        return int16(center_ptr[detail])
    if detail > bound:
        return +clipMag
    return -clipMag
```

Therefore the in-range mapping is:

```text
correction = table[1024 + detail]
for detail in [-1024, +1024]
```

which addresses table indices:

```text
0 .. 2048
```

The 2050th word at index `2049` is not read by this LUT helper path. It should be treated as a trailing element unused by this consumer until evidence assigns a broader purpose.

The source rows' near-odd symmetry, ISO-dependent zero/deadband and approximately `-1024..+1025` span are therefore consistent with a centered nonlinear detail-transfer table, and that interpretation is now supported by the actual consumer arithmetic rather than shape alone.

## UM_Gauss3LUT arithmetic — core transfer closed

`UM_Gauss3LUT` performs a separable 3-tap Gaussian in two integer stages.

Horizontal stage:

```text
h = (left + 2*center + right) >> 2
```

Vertical stage on the horizontal temporary:

```text
blur = (top + 2*center + bottom) >> 2
```

The two shifts occur independently. A floating 3x3 Gaussian followed by one division is not bit-equivalent.

Then:

```text
detail = source - blur
correction = LUT(detail, 1024, -table[0], &table[1024])
out = source + correction
out = clamp(out, 0, 16383)
```

This proves the sharpness operation is in the 14-bit scalar image domain before the canonical 8-bit contrast curve.

`UM_Gauss3LUT` proof:

- run: `34686903518`
- artifact: `MMonochrom-UM-GAUSS3LUT-PROBE1A`

LUT-helper proof:

- run: `34687020931`
- artifact: `MMonochrom-SHARPNESS-LUT-HELPER1A`

## Closed native model

The central photographic operation can now be written as:

```text
selector = Sharpening enum 0..4
iso_slot = physical Leica ISO index 0..15
code = modifier_matrix[selector][iso_slot]

if code == 0:
    sharpness stage is disabled
else:
    base_table = sharpness_bank[iso_slot]
    table = exact_integer_scale_and_clamp(base_table, code)

    h = horizontal_[1,2,1]_over_4(source)
    blur = vertical_[1,2,1]_over_4(h)
    detail = source - blur

    if detail < -1024:
        correction = -(-table[0])
    elif detail > 1024:
        correction = -table[0]
    else:
        correction = table[1024 + detail]

    output = clamp14(source + correction)
```

## Remaining gate before Android A/B

Do **not** yet modify the validated RAWSCALAR1B Android path.

The transfer function, ISO schedule, public menu selector and 14-bit arithmetic are now sufficiently closed. The remaining firmware gate is narrower:

1. resolve `UM_Gauss3LUT` image argument mapping and exact processed rectangle/border behavior;
2. confirm how width/stride/height are supplied by `Process_Sharpness`;
3. build a host reference with exact border/stride semantics and frozen vectors;
4. only then create a controlled Standard-sharpness Android A/B on top of RAWSCALAR1B.

Canonical curve02, RAWSCALAR1B source bridge, LensShadingMap, MHC, JPEG quality, DNG persistence, capture policy and no-HDR rule remain frozen.
