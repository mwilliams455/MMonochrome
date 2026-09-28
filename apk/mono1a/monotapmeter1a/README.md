# MONOTAPMETER1B_LOWKEYREAD1A_INTENTBOUNDARY1A

Parent: validated `research/monoauto1d1h-savelookup1a` head `8b9d7ade66c9772c654b8efb51a93768d312bfb7`.

This overlay adds tap-to-focus plus an explicit Monochrom exposure subject without changing the renderer, DNG math, curve02, SOURCE1D transform, MFM automatic no-tap policy, save lookup, or 1E shutter-boundary hygiene.

## Photographic rule

A tap is **subject intent**, not permission to normalize the subject to middle grey.

The exact selected patch is measured in the existing live `SOURCE1D / XYZ D50 Y before curve02` probe. The first policy is positive-only and deliberately low-key:

- median readability floor: SOURCE1D `0.050` (curve02 approximately 51/255)
- lower-quarter floor: SOURCE1D `0.015` (approximately 19/255)
- median appearance ceiling: SOURCE1D `0.065` (approximately 64/255)
- tap-specific positive cap: `+0.40 EV`
- normal automatic frame-placement reference remains `0.0876544` (approximately 83/255)

Therefore a tapped black/dark object is not forced toward the normal frame reference. If q25 is very dark, the appearance ceiling prevents that tail from dragging the subject median upward indefinitely.

The existing strict SOURCE1D q99.8 headroom and BROADTAIL05 sensor-RGB-max q99 budget remain global safety constraints. With a tap, explicit subject intent replaces only the MFM uncertainty about *what matters*; it does not bypass highlight physics. The existing physical ISO/shutter allocator remains the final authority.

No HDR, local relighting, post-capture rescue, or second exposure system is introduced. The output remains one global physical capture exposure.

## Interaction

- tap selects the exact on-screen patch and requests normal AF when the lens supports it
- the vendor AE tap region is neutralized while a Monochrom tap selection is active, preventing double counting
- tapping inside the yellow selected rectangle returns to Auto
- a new tap replaces the old generation
- selection lifetime is 15 seconds
- camera/session/view geometry/mirror/orientation change or preview pause clears selection
- fixed-focus/manual-focus use can still select an exposure subject
- manual ISO, manual shutter, user EV, and tripod bypass retain authority (`TAP PAUSED`)

## Freshness / successive capture

Selection may survive a shutter, but its measurement may not. The existing 1E shutter boundary is reused: a tap measurement at or before the last shutter is rejected, as are measurements older than 750 ms or from another selection generation/camera/session. A fresh post-shutter probe is required for the next photograph.

The tap selection generation is also included in the exposure-plan control identity. Selecting, replacing, clearing, or expiring a tap therefore invalidates any previously published plan before the shutter can reuse it. This closes the short pre-tap/stale-tap plan race while leaving the no-tap exposure mathematics unchanged.

## Viewfinder

The same shared exposure plan feeds preview and capture. The overlay shows the exact quantized patch rectangle and state such as `TAP 0.00`, `TAP +0.25`, `TAP +0.25 · LIMITED`, or `TAP +0.25 · LOW-KEY`.

`LIMITED` means global highlight or physical allocator limits prevented the requested lift. `LOW-KEY` means the Monochrom appearance ceiling deliberately stopped further brightening even though the selected lower tones asked for more.

## First phone validation

Use controlled Auto / Tap / Auto sequences for:

1. off-centre dark subject beside a bright window
2. already-readable subject
3. extreme window + dark subject
4. naturally dark object / black fabric
5. portrait and both landscape orientations
6. successive captures with the same selection, then a replacement tap
7. lens switch
8. manual ISO/shutter/user EV

The primary failure condition is not “tap did not make the subject bright.” It is either (a) the selected subject remains unnecessarily unreadable despite safe headroom, or (b) the tap makes the frame look generically bright and loses the dense Monochrom placement. This build is intentionally biased against (b).
