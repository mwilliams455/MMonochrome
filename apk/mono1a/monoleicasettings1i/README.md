# LEICATIMER1A

Replaces PhotonCamera's 0 / 3 / 10 second timer with the first-generation Leica M Monochrom
self-timer choices:

- Off
- 2 s
- 12 s

The existing countdown scheduler is reused; only the values, labels, state semantics and icons are
changed. No capture/exposure/render/DNG code is touched.

When Leica bracketing is enabled, the self-timer delays the **start of the bracket series once**.
The subsequent bracket frames continue automatically without another 2 s or 12 s delay.
