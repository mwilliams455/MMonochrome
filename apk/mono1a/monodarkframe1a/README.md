# MONODARKFRAME1A

First phone candidate for the first-generation M Monochrom long-exposure / BlackRef behavior.

## Leica firmware basis

The recovered M Monochrom 1.022 BF547 policy is:

`floor(exposure_us / 10) > threshold[temp_group][iso_bucket]`

For normal 20-39 C operation the effective first-generation menu thresholds are:

- ISO 320-1000: strictly above 0.250 s
- ISO 1250-4000: strictly above 0.125 s
- ISO 5000-10000: strictly above 0.066 s

The real camera dynamically selects a different table row from its internal sensor/control temperature.

## Android boundary

Standard Camera2 does not expose Leica's internal temperature or an application-controlled mechanical shutter. This candidate therefore uses the nominal 20-39 C Leica group and does **not** fake a second dark exposure.

For eligible captures it:

1. requests `STATISTICS_HOT_PIXEL_MAP_MODE` when supported;
2. uses valid per-frame `SENSOR_DYNAMIC_BLACK_LEVEL` on the derived Monochrom path;
3. if and only if the HAL explicitly reports `HOT_PIXEL_MODE_OFF`, repairs reported hot pixels using same-CFA two-pixel neighbours on the private normalized Bayer copy before demosaic.

It never forces `HOT_PIXEL_MODE`, never mutates the camera RAW ByteBuffer, never adds an artificial delay, and never uses HDR/stacking. Original Sensor RAW stays untouched. The processed Monochrom JPEG and derived Monochrom DNG share the corrected source.
