# Next project target

Continue from `docs/LUT_SELECTOR_TRACE_v0_3.md`, `docs/NATIVE_CONTRAST_MODE_v0_3.md`, and `docs/MONO_SIGNAL_DOMAIN_v0_4.md`.

## Firmware truths now closed for the first native-resolution renderer

- normal ISO / sRGB / Standard -> canonical curve `02`;
- JPEG resolution `100%` -> `Process_Contrast` mode `0`;
- mode 0 is a one-sample / one-output path;
- Monochrom working signal range is `0..16383` in 16-bit storage;
- `context+128` is a shared signal pedestal / black-reference coordinate used by Shading and Contrast;
- native Contrast arithmetic is exactly:

```text
v = max(uint16(sample14) - pedestal, 0)
idx = v >>> 3
out8 = curve02[idx]
```

## MONO1A APK gate

The research gate is now **OPEN** for:

```text
apk/mono1a-native
```

The implementation objective is a controlled Xiaomi 15 Ultra main-camera 12 MP photo path:

```text
Xiaomi RAW
  -> source black/white normalization
  -> physical LensShadingMap correction
  -> high-quality provisional monochrome reconstruction
  -> explicit Xiaomi -> Leica 14-bit source adapter
  -> exact M Monochrom native mode-0 curve02 stage
  -> high-quality grayscale JPEG
  + untouched/normal project DNG save path
```

Do not block MONO1A on 75/50/25% resampling kernels or exact Leica noise/sharpness parity. If those stages are not closed, keep them disabled or inherited only where they do not change photographic pixels unexpectedly; do not invent tuning.

## Immediate implementation work

1. create `apk/mono1a-native`;
2. reuse the proven M9 PhotonCamera capture/queue/DNG/JPEG/native-library scaffolding without modifying the M9 production branch;
3. isolate a `MonoSourceAdapter` from the Leica core;
4. start with a high-quality demosaic-based linear luminance source adapter, clearly labelled provisional;
5. map source signal to the 14-bit Leica coordinate with an explicit/logged pedestal convention;
6. embed the extracted curve02 values as generated source data or reproducible build output, not Leica firmware blobs;
7. add diagnostics for source black/white levels, pedestal, 14-bit min/median/q99.8, LUT index min/median/q99.8, output clipping, ISO and exposure;
8. build an APK and validate ordinary daylight, indoor light, backlight, foliage/sky, people, and high ISO before enabling any extra detail/noise processing.

## Research continuing in parallel

- close the exact upstream producer semantics for the native Leica pedestal;
- decode the 16 x 2 x 2050-byte ISO-aligned bank and `LoadISODataL1` consumer;
- recover Monochrom noise/sharpening stages for later photographic parity;
- investigate a photosite-domain Xiaomi pseudo-monochrome reconstruction to reduce Bayer/demosaic character versus the first provisional adapter.

No HDR, no scene-specific exposure hacks, and no visual curve tuning.
