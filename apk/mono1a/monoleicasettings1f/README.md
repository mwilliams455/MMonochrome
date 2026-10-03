# LEICAAELOCK1A

Implements the roadmap's explicit **AE Lock** state while preserving the behavior of the
first-generation Leica M Monochrom's **metering memory lock**.

On the original camera, metering memory lock is available in aperture-priority mode:
meter the important subject, hold the shutter release at the metering pressure point, recompose,
and the shutter time no longer changes until the pressure point is released.

A phone has no physical half-press pressure point, so this port uses an explicit top-bar **AE-L**
toggle:

- tap AE-L once to freeze the currently selected physical ISO + shutter plan;
- recompose and/or focus without changing the locked exposure;
- take one or multiple pictures while the lock remains active;
- tap AE-L again to return to automatic exposure;
- camera close, app pause, or physical lens/session switch clears the lock;
- changing an actual exposure control also clears it;
- tap-to-exposure becomes focus-only while locked, preventing a new exposure subject from
  silently replacing the stored reading;
- an explicit manual shutter cannot be AE-locked because it is already manual exposure;
- manual ISO + automatic shutter can still use AE-L, matching aperture-priority semantics.

The preview continues to render from the same immutable Monochrom plan used for capture, so the
locked appearance is represented in the viewfinder rather than being a capture-only Camera2 flag.

No JPEG render math, Linear DNG math, Contrast, Toning, Sharpness or HDR behavior is changed.
