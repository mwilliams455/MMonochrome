# LEICASLOWEST1A

Implements the **first-generation Leica M Monochrom** Auto ISO **Slowest speed** control.

The original camera exposes:
- Lens dependent — ISO begins rising when shutter would cross the 1/focal-length threshold.
- Fixed slowest speeds: 1/125 s, 1/60 s, 1/30 s, 1/15 s, 1/8 s.

For Android phones, Lens dependent converts the active physical camera's focal length/sensor width to a 35mm-equivalent focal length, then applies the original 1/f rule. It is device/lens independent and does not use Xiaomi-specific lens names.

Interaction with Auto ISO Maximum:
- before the slowest-speed threshold is crossed, the existing exposure plan is left alone;
- when the threshold would be crossed, ISO is raised to preserve exposure energy;
- ISO never exceeds the selected Auto ISO Maximum;
- after that maximum is reached, shutter is allowed to become slower than the threshold rather than deliberately underexposing;
- manual ISO and manual shutter remain authoritative.

JPEG rendering, Contrast, Toning, Sharpness, Linear DNG math and HDR policy are unchanged.
