# LEICADIAGNOSTICS1A

Adds a Leica M Monochrom **Diagnostics** switch, default **Off**.

- Off: normal shooting does not stage or publish development JSON sidecars. Any already-pending diagnostic public export is consumed without writing into the camera folder.
- On: preserves the existing diagnostic sidecar pipeline.
- The audited `M9DiagnosticBurstSpool` is diagnostic-only; no JPEG/DNG image storage is routed through it.
- The separate `MonoDngSpool1B` durable Monochrom-DNG recovery store is hash-frozen and untouched.
- JPEG finalization, exposure, renderer math, preview, output-mode semantics, derived DNG pixels, and Original Sensor RAW semantics are frozen.
