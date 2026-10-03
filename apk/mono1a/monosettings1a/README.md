# MONOSETTINGS1A Leica UI cleanup

This stage is intentionally a settings-surface cleanup, not a photographic change.

## Hidden now
- Entire Photon video settings subtree.
- Frame-count / stacking control.
- Generic Photon JPEG NR and enhanced-processing controls.
- HDR/UltraHDR/HEIC and generic Photon sharpness, saturation, contrast, exposure-processing,
  shadow/compressor/noise/merge controls.
- CFA/alignment/color-method/preview-format engineering controls from the normal UI.
- Manual white-balance persistence, watermark, 16:9 presentation crop, round-edge mask, AF-data UI.
- Quad Bayer, binning, Photo EIS and FPS controls.

## Preserved
- Quad Bayer implementation and preference plumbing remain in source but are dormant/off.
- Binning implementation and preference plumbing remain in source but are dormant/off.
- JPEG / RAW+JPEG / RAW output selector remains.
- Horizon, grid, AF mode, focus peaking, lens controls, timer, flash, bracketing and AE metering remain.
- Advanced/tunable/sensor-configuration infrastructure remains available for development.

## Frozen
MONOSETTINGS1A must not change curve02, the Monochrom renderer, DNG pixel math,
or MONOTAPMETER1B exposure-placement behavior.

Leica-specific Contrast, Sharpness and Toning controls are deliberately not faked in this
cleanup stage. They should be added only when their firmware mapping/renderer wiring is
implemented and testable.
