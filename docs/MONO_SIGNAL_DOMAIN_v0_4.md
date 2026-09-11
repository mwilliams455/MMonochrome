# M Monochrom 1.022 — signal domain / pedestal v0.4

Date: 2026-09-11
Branch: `research/mm-firmware-r0`

## Status

The native-resolution Monochrom tone stage now has a firmware-supported signal-domain model. The remaining Xiaomi-side problem is source reconstruction, not Leica tone arithmetic.

## 1. Shared runtime pedestal field

The Monochrom BF561 runtime context uses the signed word at `context + 128` as a shared signal pedestal / black-reference coordinate.

`Process_Contrast` receives this field as its pedestal argument for the native mode-0 path.

`Process_Shading` independently reads the same field:

```text
Process_Shading @ 0xFFA02718
R7 = W[context + 128](X)
```

The same runtime field therefore participates in multiple signal-domain operations and is not a creative brightness parameter.

## 2. Process_Shading proves the 14-bit working domain

The Monochrom `Process_Shading` loop performs pedestal-relative scaling:

```text
sample = int16(input)
d = sample - pedestal
gain = uint16(shading_gain)
scaled = ASR32(d * gain, 13)
result = pedestal + scaled
result = clamp(result, 0, 16383)
store uint16(result)
```

The executable explicitly clamps to:

```text
0 .. 16383 = 0x0000 .. 0x3FFF
```

Therefore the photographic working signal is a non-negative 14-bit coordinate carried in 16-bit storage.

The safest semantic label is:

```text
signal pedestal / black-reference coordinate
```

rather than asserting a source-level symbol name such as sensor black level.

## 3. Native Process_Contrast uses the same coordinate

The 100% JPEG setting is already proven to select `Process_Contrast` mode 0.

Mode 0 performs:

```text
sample = uint16(input)
v = sample - pedestal
v = max(v, 0)
index = v >>> 3
out8 = selected_curve[index]
```

The pedestal argument comes from the same runtime `context+128` field used by `Process_Shading`.

For normal ISO + sRGB + Standard:

```text
selected_curve = curve02
```

So the exact native-resolution tone operation is:

```text
out8 = curve02[max(uint16(sample14) - pedestal, 0) >>> 3]
```

This is an exact 14-bit-to-11-bit-to-8-bit Leica path:

```text
14-bit working signal
    ↓ subtract signal pedestal
non-negative signal above pedestal
    ↓ >>> 3
0..2047 LUT coordinate
    ↓ curve02
8-bit monochrome output
```

No floating normalization, interpolation, empirical exposure offset, or HDR-like lift is part of this stage.

## 4. Pedestal producer is dynamic, not a fixed tuning constant

`Set` writes the runtime pedestal at approximately:

```text
0xFEB11A12 -> W[context+128]
```

It is derived from runtime geometry/calibration quantities through integer multiply/divide/remainder arithmetic. It is not copied directly from the main PROCESS/LUTS payload and should not be replaced with an arbitrary photographic tuning value.

Exact upstream semantic naming and the native Leica numeric value for every operating state remain open.

For a Xiaomi port, the source adapter must therefore make its pedestal policy explicit rather than pretending a guessed constant is Leica-authentic.

## 5. First Xiaomi implementation policy

The Leica core should accept a 14-bit working signal and a separate pedestal:

```text
struct MonoSignal14 {
    uint16_t sample;      // 0..16383
    int16_t pedestal;     // explicit source-adapter coordinate
};
```

The first Android implementation should keep the source-sensor adaptation visibly separate:

```text
Xiaomi RAW
  -> black/white normalization
  -> lens shading correction
  -> provisional monochrome reconstruction
  -> map to Leica 14-bit working coordinate
  -> firmware-derived Monochrom mode-0 tone stage
  -> 8-bit grayscale JPEG
```

A synthetic Xiaomi pedestal of zero is acceptable only as an explicitly labelled source-adapter convention after Xiaomi black subtraction; it must not be described as the recovered native Leica pedestal value.

Because mode-0 Contrast subtracts the pedestal before the LUT coordinate is formed, the Leica tone mapping itself remains defined on `signal - pedestal`. This cleanly isolates later work on reproducing native Monochrom sensor/noise behavior from the already-closed tone curve arithmetic.

## 6. MONO1A APK gate

The minimum firmware truths required to start a controlled native-resolution APK are now closed:

- 100% resolution -> `Process_Contrast` mode 0: PROVEN
- normal ISO / sRGB / Standard -> curve02: PROVEN
- working signal range 0..16383: PROVEN
- shared signal pedestal at context+128: PROVEN
- native mode-0 arithmetic: PROVEN
- exact `>>>3` LUT coordinate: PROVEN
- 8-bit curve output: PROVEN

Therefore the research gate is **OPEN** for an implementation branch named:

```text
apk/mono1a-native
```

The first build must keep these limitations explicit:

1. Xiaomi Bayer -> pseudo-monochrome reconstruction is an approximation layer because the Leica sensor has no CFA.
2. Exact Leica pedestal producer semantics remain under investigation; the Xiaomi source adapter must log its chosen pedestal convention.
3. Noise/sharpening parity may remain deferred in MONO1A if those stages are disabled rather than replaced by arbitrary tuning.
4. The renderer must preserve high-quality JPEG output and must not trade visible quality for speed.

No Leica firmware bytes are committed to this repository.
