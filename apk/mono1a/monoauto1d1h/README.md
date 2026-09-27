# MONOOUTPUT1H_SAVELOOKUP1A

Parent: `b738ecc5738b0c5a7bb84b8d584c60f439d9e23e` (1G receipt hygiene).
This is a storage-only validation candidate, not a new photographic calibration.

## Save path

The 1G publisher performs a complete child-directory query before temporary creation,
then another fresh complete query immediately before the final rename.

1H removes the first query ONLY for a genuinely new durable job: first publication
attempt, not recovered, no previously recorded public URI, and the existing strict
UUID temporary-name format. It creates that temporary document through the provider,
checks its returned name/type, copies and verifies the payload, and retains the fresh
full-directory final-name collision check before any rename. An existing final is
never opened for writing. Matching final bytes are accepted; different bytes retain
private recovery data as a conflict. When a matching final already exists, only this
job's separately hash-verified temporary duplicate can be removed.

For recovery, positive URI hints are bound to the exact resolved parent URI. Each hint
is queried afresh and its name/identity checked; final bytes are hash-verified. Unknown,
missing, invalid or legacy hints fall back to the original complete recovery lookup.
Permission errors are not treated as absence. No negative-result cache, document-ID
path guessing, provider-specific SQL selection, manufacturer name or camera ID is used.

Expected work, not a phone-speed claim:

* New successful SAF save: one full folder scan instead of two.
* Recovery with a valid recorded temporary URI: one final collision scan.
* Recovery with a verified recorded final URI: zero full folder scans or rewrites.
* Legacy/uncertain recovery: original full-query safety fallback; two scans may remain.

This does not eliminate the remaining fresh final-name scan. It also does not change
routine diagnostic-sidecar publication, which can still have directory lookup cost.
The copied-byte, temporary checksum, final checksum, private fsync, collision and
restart safeguards remain. Exposure, renderer, DNG encoding and preview sources are
hash-frozen by the overlay. Synthetic test fixtures contain no user photographs.

## Diagnostics release contract (agreed target; NOT switched on by 1H)

During current camera/save-path validation, keep the existing detailed diagnostics.
Do not remove evidence while evaluating this storage-only change.

The eventual release default is normal successful photography without per-shot public
JSON sidecars, audit files or diagnostic bundles. Skip diagnostic-only calculations
and JSON construction at their producers, rather than doing all the work and dropping
the files at the end. This requires an explicit producer/call-site audit and an image
and exposure parity test; changing a shared diagnostic-named class blindly is unsafe.

The following are operational data and must not be disabled with logging: live
SOURCE1D measurements, MFM decisions, highlight guards, renderer inputs, embedded image
metadata, and the minimal bounded private durable state needed to resume unfinished
DNG saves and prevent duplicate export.

Real capture/render/save failures, integrity failures and detected crashes should
produce compact, bounded local fault reports with repeat deduplication. A zero EV
assist, a dark scene or deliberately clipped highlights is not by itself a technical
failure. Reports should not automatically upload images or personal information.
Detailed troubleshooting should be explicitly enabled, time/session bounded, and
exportable as one user-selected report. Photographs are included only by deliberate
user action. Public historical files are not silently deleted by a logging switch.

Separate future validation gate: diagnostics on/off must produce unchanged exposure
decisions, identical render/DNG output for the same inputs, and identical successful
and interrupted-save recovery behaviour. Fault reporting must still work in the
normal mode without recreating a large success-file backlog.

## Validation

`apply.py` changes only the assembled `MonoDngPublicWriter1B.java` and version label.
`test.py` compiles the actual publisher/store with deterministic Android provider mocks
using opaque document IDs; compares baseline/candidate scan counts with 14,000 unrelated
entries; exercises collisions, failures, recorded-URI recovery, legacy fallback and
permission errors; checks byte identity and every sample in a synthetic 12 MP DNG.
The inherited parent tests run before this overlay. A full Android build remains
required. Device speed and real provider behaviour require phone validation.

Phone sequence: two new photographs, allow saving, restart, then take another. Examine
`publicationLookupRevision`, `publicInitialQuerySkipped`, `publicChildQueryCount`,
`publicChildRowsScanned`, `publicKnownUriHits`, `publicKnownUriFallbacks`, final status and
readback verification. Existing unfinished jobs are allowed to take the legacy route.

API references reviewed for storage design:
https://developer.android.com/reference/android/provider/DocumentsContract
https://developer.android.com/reference/android/content/ContentResolver
