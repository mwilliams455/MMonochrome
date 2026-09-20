# MONOLIVEGL1E1D — missing live-pair export

20 September 2026. Diagnostic transport only; no photographic adjustment.

## Evidence and correction

The user's IMG_20260920_154424_1789915464400_00 sample is PHOTO, not MOTION. The two diagnostic bundles contain the ordinary source/shading/capture/primary roles, but no MONO_LIVEPAIR record. The preceding Motion-only explanation was incomplete.

The successful GL1E1C assembled writer still called Files.write under FileManager.sDCIM_CAMERA. This did not adopt the M9DiagnosticBurstSpool path used by the JSONs that do export. Writer exceptions appeared only in logcat, not in exported JSON. No supplied logcat establishes the exact filesystem exception on the phone; old m9Build version strings also cannot establish the installed GL diagnostic revision.

The recorded preview AE was ISO 52 at 10 ms. The allocator, request and capture result were ISO 50 at 10.4 ms. All ISO*time products were 0.52 ISO-seconds and the exposure audit reported zero EV difference. This is cached metadata, not a measurement of the exact displayed GL frame, and does not prove tone parity or exclude all temporal differences.

## Change

Photo and ZSL callbacks now cache small immutable records in bounded memory instead of scheduling a public-file write behind processing. At the existing deferred capture-JSON export boundary, the saved RAW camera ID and timestamp are used for exact callback matching.

A <capture-stem>_MONO_LIVEPAIR.json sibling is staged through M9DiagnosticBurstSpool in the same folder as the real _M9.json. The normal capture JSON also embeds monoLivePair, making it available through its capture_metadata entry in M9_DIAGNOSTICS_BURST. The public fallback receives the enriched bytes too.

Missing callbacks, wrong timestamps and missing preview state generate explicit unavailable records. Private-spool failure retains an inline status/error. Private stage acceptance is not claimed to prove public export. No matched preview pixels are fabricated.

Marker: MONOLIVEGL1E_LIVEPAIRDIAG1D_SPOOL.
Legacy app name and version label unchanged.

## Verified build

Repository: mwilliams455/MMonochrome
Branch: research/monolivegl1e-livepairdiag1d-spool
Build commit: ac3354c9defc3acab3f4bc23f7a549e20cfc7f9f
Baseline: 43f9e059e340eb7dedaa60ae0b8f7e2b36888f2b
Actions run: 35518603986
Job: 106098670317
Result: successful build and artifact upload.

Seventeen host Java assertions passed using the actual helper and deferred store with mocked Android storage/logging. Eight unchanged-file SHA256 checks passed for the renderer, JNI, exposure allocator, saver, CameraFragment, MainRenderer, GLPreview and shader. The downloaded evidence source matches those proofs and the archived GL1E1C files where available.

APK artifact: 10607867021, MMonochrome-MONOLIVEGL1E-LIVEPAIRDIAG1D-SPOOL.
Evidence artifact: 10607802006, MMonochrome-MONOLIVEGL1E1D-EVIDENCE.
APK SHA256: bd8122a2a544ccb9669b46a9a311cab35d7018e9b0945ef89ef46116fde33890.
APK size: 115427878 bytes.
Downloaded APK hash matched its CI manifest. DEX contains the new marker, inline key, sidecar suffix and unavailable status.

## Device validation next

Phone-side file export is NOT yet validated. Install this successful 1D APK, take one Photo-mode shot and allow the existing export workers to finish. Inspect DCIM/PhotonCamera/Raw for the matching _MONO_LIVEPAIR.json, or provide the ordinary _M9.json/burst containing monoLivePair. The next record distinguishes absent exact callback data from storage-stage failure.

Do not tune GL1F midtones or JPEG exposure as part of this storage fix. The unsuffixed JPEG is the primary output; the suffix variants are diagnostic controls.
