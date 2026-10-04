# LEICAUICLEANUP1A

Cleans the normal M Monochrom UI now that the Leica photographic controls are implemented.

### Shooting settings bar
Retains only:
- Flash
- Self timer
- Save (JPEG / RAW+JPEG / RAW)
- Grid
- Bracketing

Battery Saver is still available in General Settings but is no longer presented as a photographic
shooting control. Generic Photon AE Metering is removed from the shooting bar.

### Settings screen
Removes the normal-user surfaces for:
- generic Photon AE Metering
- duplicate generic Exposure Compensation and processing/tuning sliders
- CFA/Bayer override
- Preview Format
- Remosaic / align / generic color-method controls
- full developer HUD/debug
- Tunable Settings
- Sensor Configurations
- Device configuration fetch

The code behind developer features remains in source; it is only removed from the normal
photographic UI.

Legacy Center/Average/Spot metering values are also neutralized at runtime. The Monochrom
scene-placement/tap-exposure system remains the only metering authority.

No renderer, DNG, exposure-plan, display-aid or preview-shader math changes are made.
