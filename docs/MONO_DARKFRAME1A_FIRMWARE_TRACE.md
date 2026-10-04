# M Monochrom 1.022 — DARKFRAME1A firmware trace

Date: 4 October 2026  
Target: original Leica M Monochrom (M9 generation), firmware 1.022  
Status: Black-reference acquisition decision substantially closed

## What is proven from the canonical firmware

The BF547 control firmware contains a distinct black-reference acquisition
state machine. It is not merely a JPEG noise-reduction flag.

Observed capture states and diagnostics include:

- `DarkCalib`
- `DarkCalibDone`
- a per-buffer `BlackRef` state with `No`, `Yes`, `IsBlackRef`, and
  `UnusedBlackRef`
- an internal `BLR` file type alongside `RAW`, `DNG`, and `JPG`

The normal-capture path calls a predicate at BF547 runtime address
`0x3819C`. When the predicate is true, the normal buffer is marked
`BlackRef=Yes` and a linked black-reference acquisition is scheduled. The
black-reference buffer is marked `IsBlackRef`.

The black-reference setup copies the source capture's ISO code into the linked
black-reference buffer. Therefore same-ISO black-reference acquisition is
firmware-proven.

## Exposure-time domain

The predicate reconstructs the signed APEX shutter value and calls the
firmware's APEX-to-time conversion. The resulting value is exposure duration
in microseconds. The caller then performs an unsigned 64-bit division by 10
and compares the quotient to a threshold table.

Equivalent decision:

```text
black_ref = floor(exposure_us / 10) > threshold[temp_group][iso_bucket]
```

The comparison is strict.

## ISO selector

The capture buffer stores an index into the canonical 26-slot ISO table:

`64, 80, 100, 125, 160, 200, 250, 320, 400, 500, 640, 800, 1000, 1250,
1600, 2000, 2500, 3200, 4000, 5000, 6400, 8000, 10000, 12800, 16000, 20000`

For the normal first-generation M Monochrom menu range:

| ISO | Firmware bucket |
|---|---:|
| 320–1000 | 0 |
| 1250–4000 | 1 |
| 5000–10000 | 2 |

## Temperature selector

A capture field consumed by the predicate is also writable through a firmware
debug/control command that reports **Dual Output Temperature**. The normal
selector uses:

| Temperature | Group |
|---|---:|
| <= 19 °C | 1 |
| 20–39 °C | 2 |
| >= 40 °C | 3 |

This is why Leica's user documentation describes the dark-frame onset only as
approximately a shutter speed and notes that the exact point depends on other
settings.

## Recovered threshold table

Raw BF547 table, before multiplying by the caller's 10-microsecond comparison
scale:

```text
group 0: 100000  50000  25000  12500  6600
group 1:  50000  25000   6600   3330   800
group 2:  25000  12500   6600   1660   400
group 3:   6600   3330   1660    400   100
```

Normal first-generation M Monochrom thresholds are therefore:

| Sensor/control temperature | ISO 320–1000 | ISO 1250–4000 | ISO 5000–10000 |
|---|---:|---:|---:|
| <=19 °C | >0.500 s | >0.250 s | >0.066 s |
| 20–39 °C | >0.250 s | >0.125 s | >0.066 s |
| >=40 °C | >0.066 s | >0.0333 s | >0.0166 s |

The extra group 0 and higher ISO buckets are retained in the firmware model but
are not promoted into the normal M Monochrom policy without a proven selector.

## What the firmware does not yet independently close

The firmware proves a distinct linked black-reference acquisition, same ISO,
the dynamic threshold selector, and a BLR image/file state. Leica's published
camera documentation describes the second shutter-closed exposure as
approximately the same duration as the original exposure.

The exact equal-duration timing assignment has not yet been independently
closed from the BF547 call graph, so that point remains manual-supported rather
than firmware-proven.

## Android implementation boundary

A normal Android phone has no application-controlled mechanical shutter that
can guarantee a true same-duration, light-blocked second exposure. Taking a
second ordinary Camera2 RAW would contain scene light and is therefore not a
valid Leica black reference.

The Android implementation must not fake this with:

- a second illuminated exposure;
- HDR or exposure stacking;
- an artificial equal-duration delay;
- Xiaomi-specific sensor-temperature/vendor logic.

Any phone implementation should instead be described as a purpose-equivalent
long-exposure correction and must keep Original Sensor RAW untouched.

The accompanying `tools/mono_darkframe_policy.py` is the canonical recovered
Leica decision model. It does not itself define the Android approximation.
