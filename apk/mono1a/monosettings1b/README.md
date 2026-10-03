# MONOSETTINGS1B — top-bar Settings button

Makes the existing Photon Settings gear visible in the main camera top bar.

The button already has the desired M9-style constraints:
- start constrained to the end of Flash;
- end constrained to the parent right edge;
- existing top-bar click listener opens SettingsActivity.

This patch changes only the button visibility from `gone` to `visible`.

The secure-camera guard remains unchanged: the camera fragment can still hide/disable
Settings when running from a locked secure-camera session.

No renderer, DNG, curve02 or exposure-placement code is changed.
