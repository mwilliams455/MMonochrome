# M Monochrom 1.022 — native contrast mode v0.3

Date: 2026-09-11
Branch: `research/mm-firmware-r0`

## Result

The full-resolution / 100% M Monochrom JPEG path uses `Process_Contrast` mode **0**.

This is now instruction/data-table supported rather than inferred from the apparent geometry of the five kernels.

## 1. BF547 identifies process-setting byte +5 as Resolution

The BF547 settings diagnostic reads the signed byte at processing-setting offset `+5` and uses it as an index into the JPEG resolution label table.

Relevant executable location:

```text
0x0004CE76: R1 = B[P5+5](X)
```

The four table entries resolve to:

```text
0 -> 100%
1 -> 75%
2 -> 50%
3 -> 25%
```

The `100%` string is at BF547 file offset `0xCC040` / runtime address `0x000EC040`; the remaining labels are adjacent in the settings string family.

Therefore:

```text
processing_setting.byte_5 = nResolution
0 = native / 100%
1 = 75%
2 = 50%
3 = 25%
```

## 2. BF561 copies byte +5 directly into the live contrast-mode field

`SetStructParameter` at `0xFEB11530` performs:

```text
0xFEB11588: R0 = B[P1+5](X)
0xFEB1158C: [P0+8] = R0
```

No translation or lookup occurs between the processing-setting byte and the live field.

`Run` later loads that field and supplies it directly to `Process_Contrast`.

Therefore:

```text
Process_Contrast.mode = processing_setting.nResolution
```

## 3. Process_Contrast mode dispatch

The already-decoded `Process_Contrast` implementation has five geometry branches:

```text
mode 0 -> inline one-sample / one-output path
mode 1 -> ExecuteContrast_11LUT8_7
mode 2 -> inline four-sample averaging path
mode 3 -> ExecuteContrast_11LUT8_3
mode 4 -> ExecuteContrast_11LUT8_2
```

For the 100% path, `nResolution=0`, so the active implementation is the inline one-to-one mode-0 path.

Its core tone operation is:

```text
sample = uint16(input)
v = sample - pedestal
v = max(v, 0)
index = v >>> 3
output = selected_curve[index]
```

For normal ISO + sRGB + Standard, the selected curve is already proven to be **curve02**.

Thus the first firmware-grounded native-resolution tone stage is:

```text
v = max(uint16(sample) - pedestal, 0)
out8 = curve02[v >>> 3]
```

## 4. Important correction: two different structures must not be conflated

A BF547 helper around file offset `0x496B4` also constructs fixed-width records and writes fields at offsets `+4/+5`. Those records are a different processing-job/transport descriptor family.

They are **not** the camera processing-setting structure read by BF547 diagnostics and consumed by BF561 `SetStructParameter` for `nIso`, `nContrast`, `nSaturation`, `nNoise`, `nColorSpace`, and `nResolution`.

Therefore no semantic name from the processing-setting record should be assigned to the `0x496B4` descriptor merely because field offsets coincide.

## 5. APK consequence

For a first main-camera 12 MP / native-resolution M Monochrom renderer, the resampling contrast kernels do not need to block implementation.

The required contrast path is mode 0 only.

Remaining high-priority renderer gates before freezing a photographic `MONO1A` implementation:

1. identify the producer/value/domain of the signed pedestal passed to `Process_Contrast`;
2. close the signal representation entering mode 0 sufficiently to map Xiaomi reconstructed monochrome into the Leica 0..2047 LUT coordinate without an empirical brightness fit;
3. preserve the proven curve02 selector and 100% mode-0 arithmetic;
4. keep noise/sharpness stages separable so the first APK can be clearly labelled if exact firmware parity there is deferred.

No Leica firmware bytes are committed to this repository.
