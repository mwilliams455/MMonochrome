# LEICAEV1A

Implements the first-generation Leica M Monochrom **Exposure Compensation** range from the
project roadmap: **-3 EV to +3 EV in 1/3 EV increments**.

This deliberately uses one user control only: the existing manual EV wheel is converted to exact
Leica stop-domain values. The hidden generic Photon exposure-correction preference is forced to
zero so an old persisted value cannot silently become a second exposure adjustment.

Important semantics:

- EV is stored directly in photographic stops; it is not rounded through the phone vendor's
  Camera2 AE-compensation step or range.
- In the Monochrom path, Camera2 AE compensation remains zero.
- The user EV is added exactly once to the automatic Monochrom scene-placement EV at the shared
  physical ISO/shutter allocation seam.
- Nonzero user EV does **not** disable the low-key automatic placement logic.
- The same immutable plan drives the viewfinder and final capture.
- The Linear DNG changes because the sensor is actually captured at the compensated physical
  ISO/shutter plan, not because DNG pixels are brightened afterward.
- Changing EV immediately releases AE-L, since exposure compensation is an exposure-control change.
- Auto ISO Maximum and Slowest speed remain downstream constraints on the compensated plan.
- No HDR, post-render exposure rescue, JPEG tone changes, Contrast/Toning/Sharpness changes, or
  Linear DNG pixel-math changes are introduced.
