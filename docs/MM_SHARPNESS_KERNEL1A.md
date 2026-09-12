# M Monochrom SHARPNESS KERNEL1A

Date: 2026-09-12  
Firmware: Leica M Monochrom 1.022  
Scope: firmware-derived JPEG sharpness core, before Android integration

## Firmware result

The M Monochrom sharpness stage is a 14-bit scalar-domain, ISO-dependent nonlinear unsharp-mask operation. It is not a conventional fixed-radius generic sharpening filter and should not be replaced by one.

The closed core is:

```text
1. select ISO-specific 2050-word signed detail LUT
2. select public sharpening enum 0..4
3. map enum + ISO to modifier code 0..12
4. modify the ISO LUT with exact integer gain and clamp
5. construct separable 3x3 Gaussian blur with stage-wise >>2
6. detail = source - blur
7. map signed detail through the modified centered LUT
8. source += correction
9. clamp source to 0..16383
```

## Public selector

Canonical BF547 menu:

```text
0 Off
1 Low
2 Standard
3 Medium high
4 High
```

Control ID is `0x1005`.

## Standard schedule

For the native Standard enum (`2`):

```text
ISO 320..640   code 8   descriptor 8   2.00x
ISO 800..4000  code 4   descriptor 4   1.00x
ISO 5000..6400 code 3   descriptor 3   0.75x
ISO 8000..10000 code 2  descriptor 2   0.50x
```

This strength schedule is independent of the ISO-dependent deadband already encoded in each base LUT row, so Leica reduces high-ISO sharpening in two ways: the row shape changes and the row amplitude is reduced.

## Exact modifier arithmetic

Descriptor values for codes 0..12:

```text
0, 1, 2, 3, 4, 5, 6, 7, 8, 10, 12, 13, 20
```

The loader does not simply multiply by a float. It parity-reduces the descriptor and uses one of three exact integer forms before clamping to signed 12-bit magnitude:

```text
code 1:  (x*1)  >> 2
code 2:  (x*1)  >> 1
code 3:  (x*3)  >> 2
code 4:  x
code 5:  (x*5)  >> 2
code 6:  (x*3)  >> 1
code 7:  (x*7)  >> 2
code 8:  x*2
code 9:  (x*5)  >> 1
code 10: x*3
code 11: (x*13) >> 2
code 12: x*5
```

then:

```text
modified = clamp(modified, -2048, +2048)
```

Blackfin `>>>` signed shift semantics must be reproduced exactly for negative values.

## Exact centered LUT mapping

After row modification:

```text
bound = 1024
center = &table[1024]
clipMag = -table[0]
```

For signed detail `d`:

```text
if d < -1024:
    correction = -clipMag
elif d > 1024:
    correction = +clipMag
else:
    correction = table[1024+d]
```

Indices `0..2048` are addressed. Index `2049`, the 2050th source value, is not read by this helper path.

## Exact Gaussian arithmetic

The Gaussian is separable and uses two distinct integer divisions.

Horizontal:

```text
h[x,y] = (src[x-1,y] + 2*src[x,y] + src[x+1,y]) >> 2
```

Vertical:

```text
blur[x,y] = (h[x,y-1] + 2*h[x,y] + h[x,y+1]) >> 2
```

This is not bit-equivalent to summing a 3x3 `[1 2 1]^T[1 2 1]` kernel and shifting once by four, because the horizontal `>>2` truncation occurs before the vertical pass.

## Detail reconstruction

```text
detail = src - blur
correction = LUT(detail)
out = clamp(src + correction, 0, 16383)
```

The `0x3fff` saturation in `UM_Gauss3LUT` proves that this stage operates in the native 14-bit scalar domain upstream of `Process_Contrast` / curve02.

## What is not yet declared closed

The arithmetic above is closed. Exact full-frame placement is still being traced:

- ABI mapping of source/temp/image dimensions into `UM_Gauss3LUT`;
- exact width versus stride distinction;
- first and last processed row/column;
- border behavior and whether untouched border samples are retained in-place;
- scratch allocation lifetime / pitch assumptions.

Those geometry details must be resolved before the Android path is changed.

## Evidence runs

```text
34686903518  MMonochrom-UM-GAUSS3LUT-PROBE1A
34687020931  MMonochrom-SHARPNESS-LUT-HELPER1A
34688023264  MMonochrom-SHARPNESS-MODIFIER1A
34688085825  MMonochrom-SHARPNESS-MENU1A
```

See also `docs/MM_SHARPNESS_LUTBANK1A.md`.
