# LEICAOUTPUTMODE1A

Separates the two meanings of "RAW" that were previously entangled.

## Save selector

The normal shooting **Save** selector now controls only the intended M Monochrom outputs:

- **JPEG** → processed Monochrom JPEG only
- **DNG + JPEG** → processed Monochrom JPEG + derived linear Monochrom DNG
- **DNG** → derived linear Monochrom DNG only

When **JPEG** is selected the linear-DNG plane is not copied, the durable DNG exporter is not
admitted, and no Monochrom DNG is generated.

## Original Sensor RAW

A separate Leica-settings toggle, **Original Sensor RAW**, defaults **Off**. When enabled it adds
the untouched Bayer/color DNG from the phone sensor to whichever Save mode is selected.

Examples:

- JPEG + Original Sensor RAW Off → 1 JPEG
- JPEG + Original Sensor RAW On → JPEG + untouched sensor DNG
- DNG + JPEG + Original Sensor RAW Off → Monochrom DNG + JPEG
- DNG + JPEG + Original Sensor RAW On → Monochrom DNG + JPEG + untouched sensor DNG
- DNG + Original Sensor RAW Off → Monochrom DNG only

Photographic rendering, JPEG quality/tone, derived-DNG sample math, exposure, preview and display
aids remain unchanged.
