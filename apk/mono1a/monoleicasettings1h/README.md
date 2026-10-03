# LEICABRACKET1A

First-generation Leica M Monochrom (2012) automatic exposure bracketing.

Recovered manual semantics:
- 3, 5 or 7 exposures.
- Sequences: 0 / + / − or − / 0 / +.
- EV increments: 0.5, 1, 1.5 or 2 EV.
- 7-frame series are limited to 0.5 or 1 EV.
- Aperture-priority only: exposure variation is performed with shutter speed.
- With Auto ISO, the ISO selected for the correct/base exposure is held for the whole series.
- Auto ISO Maximum and Slowest speed do not constrain the subsequent bracket shutters; the full physical shutter range is available.
- If an exposure lies outside the physical shutter range, the shutter is clamped and the requested number of files is still produced, so two frames can legitimately share the same exposure.
- Bracketing is unavailable with flash.
- The setup remains active until disabled.

Phone implementation:
- the existing quick Bracketing control is repurposed as Leica Off/On;
- frame count, sequence and increment live in the Leica Monochrom settings category;
- each exposure runs through the existing single-frame Monochrom pipeline and is completely rendered/saved before the next frame is captured;
- there is no HDR merge or stacking;
- existing user EV shifts the center of the bracket;
- AE-L may supply the center exposure.
