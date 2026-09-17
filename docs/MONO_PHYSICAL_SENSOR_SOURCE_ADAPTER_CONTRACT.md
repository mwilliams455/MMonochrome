# M Monochrom Physical-Sensor Source Adapter Contract

Date: 2026-09-17
Reference architecture: M9 `research/sourceadapter-rescue1a-targethsm-perf1a`

## Goal

Make the M Monochrom renderer portable across RAW-capable smartphone cameras and manufacturers without selecting photographic behaviour by phone model, manufacturer, marketing lens name, zoom label, camera ID, or focal-length class.

The unit of adaptation is the **physical RAW source**.

## Pipeline boundary

```text
physical RAW buffer
  -> PhysicalRawDescriptor
  -> RawGeometryCfa
  -> BlackWhiteNormalize
  -> SourceShadingNormalize
  -> SourceSpectral/LuminanceNormalize
  -> CommonMonoSceneFrame
  -> one shared M Monochrom target renderer
```

Everything before `CommonMonoSceneFrame` may vary only when justified by physical source evidence. Everything after `CommonMonoSceneFrame` must be identical for every supported source.

## Important difference from the colour M9 project

The M9 production path can normalize each Bayer source into a common scene-referred colour frame using Camera2/DNG colour metadata, then apply one shared Leica colour target renderer.

The M Monochrom target has no Bayer colour filter array. A smartphone Bayer sensor therefore requires a source-domain spectral/luminance bridge before the Leica monochrome target stages. That bridge is a source-normalization problem and must not be confused with Leica target rendering.

The current `M9Y` weighted RGB conversion is retained as a frozen historical/control route only. It is not a manufacturer-independent physical source contract.

A physically grounded portable route should be expressed from the active source's Camera2/DNG calibration (for example a normalized Camera-to-XYZ D50 Y response where proven), with explicit provenance and validation. It must not contain Xiaomi-specific coefficients or Cobalt-derived HSM/CM/FM data.

## Cobalt/HSM rule

Production Monochrom rendering must have **zero runtime dependency on Cobalt CM/FM/HSM tables**.

Cobalt-derived data may remain only in clearly isolated forensic/reference code and must never select or alter production pixels.

Leica firmware-derived target assets that are genuinely part of the M Monochrom target pipeline (for example the validated Monochrom curve/sharpness data) remain target assets and are not source calibration.

## PhysicalRawDescriptor

The active source descriptor should carry, with provenance/confidence where applicable:

1. RAW width/height
2. row stride, pixel stride, buffer packing/capacity
3. active-array and pre-correction active-array geometry
4. RAW buffer/crop origin and whether origin is proven
5. Camera2 CFA and resolved Bayer phase at the actual RAW origin
6. static/dynamic black level and plane ordering
7. static/dynamic white level
8. LensShadingMap geometry/values and whether shading is already applied
9. Camera2/DNG calibration transforms, color matrices and forward matrices
10. reference illuminants and live/as-shot neutral
11. ISO/sensitivity/analogue-digital gain evidence
12. sensor noise metadata where available
13. evidence of vendor scaling, nonlinear RAW, PDAF masking, remosaic/binning or baked preprocessing
14. physical camera identity as provenance only
15. focal length/aperture as provenance/optical metadata only

Unknown values must remain unknown rather than inheriting assumptions from another module.

## CFA and geometry rule

All four conventional Bayer layouts (RGGB, GRBG, GBRG, BGGR) must be resolved from active Camera2 metadata. Lens-shading channel selection must follow the sensor lattice and actual RAW origin. No `RGGB-only`, `4096-wide`, or main-camera geometry assumption may survive in the portable source path.

Unsupported/non-Bayer sources fail closed until explicitly implemented.

## Source shading rule

Use the live Camera2 LensShadingMap as source metadata. Preserve four-channel Bayer semantics, interpolate in the map's physical geometry, and apply correction exactly once. If buffer-to-active-array geometry or already-applied semantics are unproven, do not silently invent a correction.

Manufacturer, camera ID, focal-length class and zoom label must never substitute for live source metadata.

## Source spectral/luminance normalization

The source bridge must answer only: "what manufacturer-independent scene signal should this Bayer source hand to the monochrome target?"

Candidate production route:

1. demosaic/linear source RGB using the active CFA and source geometry;
2. use active Camera2/DNG calibration to derive a source-specific scene transform in a defined common space;
3. derive the common monochrome scene signal from that normalized representation;
4. hand a defined linear `CommonMonoSceneFrame` to the Leica target stages.

The existing SOURCE1D/XYZ-Y experiment is useful evidence because it already derives a Y-row from the active DNG source transform. It should be generalized and validated rather than keyed to Xiaomi.

## CommonMonoSceneFrame

Must define and test:

- linearity
- numeric range and clipping policy
- neutral/exposure scale semantics
- black-floor semantics
- spectral/luminance definition
- treatment of negative transform results
- expected signal/noise semantics
- geometry/orientation handed to the target renderer
- source shading normalization status

## Selection policy

Source adaptation is selected from physical RAW characteristics and measured source behaviour.

Camera ID may locate the active CameraCharacteristics object but must never be an aesthetic selector. Focal length/zoom labels must not select tone, contrast, sharpness, curve, or source coefficients.

## Frozen target invariant

The validated M Monochrom target stages remain shared and source-independent, including firmware-derived tone/curve behaviour, validated sharpness behaviour, ISO-domain behaviour, and other proven Leica target stages.

Portability work must not change those stages unless a separate firmware-forensics result justifies it.

## Non-negotiable invariant

**Physical-sensor-specific before common monochrome scene space. Leica M Monochrom-specific after common monochrome scene space.**

A new phone or lens/module should be supportable by satisfying the source contract without changing the Leica target renderer.