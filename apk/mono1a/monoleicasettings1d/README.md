# LEICAAUTOISO1A

Adds the first-generation Leica M Monochrom-style **Auto ISO Maximum** control to the modern Monochrom settings.

- Menu: 320, 400, 500, 640, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000, 6400, 8000, 10000.
- Domain: physical Camera2 SENSOR_SENSITIVITY.
- The selected value is clamped to the active sensor's physical sensitivity range.
- Manual ISO remains authoritative.
- With automatic shutter, hitting the ceiling lengthens shutter to preserve exposure energy where the sensor exposure-time range allows it.
- With manual shutter + Auto ISO, shutter remains exact and ISO is capped.
- Changing the ceiling is part of the immutable shared-plan control identity, so stale preview/capture plans are invalidated.
- JPEG/DNG render math, Contrast, Toning and Sharpness are unchanged.
- Default is 10000 only to preserve the already phone-validated parent behavior until the user explicitly selects a lower ceiling; this is not a claim about the Leica factory default.
