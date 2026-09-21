# MONOOUTPUT1C_CURSORQUERY

Storage-lookup-only candidate on MONOOUTPUT1B commit 7531f8bc0fc6487d0eb1b83666a8c12472f8e13c. No phone speed claim before on-device validation.

The 13:04 device set staged four derived DNGs successfully but reported 46.996 seconds for the first public publication, of which 16.395 seconds were measured in the initial lookup. Payload copy/flush was only 43.98 ms. Diagnostic persistence was approximately 15.5 seconds. The first `findFile` was timed; attributing all remaining time to the other lookups is a hypothesis, not a measured breakdown.

## Change

Replace repeated DocumentFile.findFile calls with one projected ContentResolver child cursor returning document ID, display name, MIME and size together. DNG initial lookup finds final and temporary names together; a second fresh child query retains the pre-rename collision check. Creating and renaming use DocumentsContract and the returned opaque document URI. Metadata and bytes are verified through that known URI rather than a new parent scan. No negative lookup cache, assumed document-ID path format, provider-specific selection semantics or per-child metadata calls.

Normal diagnostic burst/individual writes use the same query helper. Existing JSON documents are opened with explicit truncation rather than deleted and recreated, and bytes are checked after close before the upstream private stage may be released. Scheduling and payload assembly are unchanged. The rare legacy M9DiagnosticSidecarIO private-stage-failure fallback and general SimpleStorageHelper remain unchanged.

Null, loading, errored, malformed or ambiguous cursors fail closed, leaving the durable DNG private payload available for retry. Complete traversal is still O(N) within one cursor, not a promised constant-time directory index. Provider-side cost and paging remain device-dependent. The final conflict check does not provide an atomic no-replace guarantee against an external actor racing the provider's rename; provider semantics are the same safety boundary as the parent.

## Boundaries

Only MonoDngPublicWriter1B.java, the public-writer method/telemetry in M9DiagnosticBurstSpool.java, and versionName change. Two helper classes are added. The full saved renderer, native code, curve, preview, MONOAUTO1A exposure logic, DNG writer/plane, durable spool schema/storage path and startup/admission hooks remain byte-identical. The direct DNG byte-copy/flush/close method bodies also remain identical.

Pending MONOOUTPUT1B jobs use the same private spool and filenames. Do not uninstall or clear app data to test the upgrade. Existing completed exports are not rewritten by the spool; pending old jobs can use the new lookup path when the app reopens.

## Evidence

Local Java tests: 41 storage scenarios / 347 assertions, including the parent's 24 / 214 and 17 new cursor/diagnostic scenarios / 133. Real production query/publisher/spool classes are run with filesystem-backed Android and cursor mocks. 10,000 unrelated directory rows yield two DNG child queries and two single-document queries, zero findFile/getName calls. One child query per diagnostic write; an update does not delete/recreate its existing document.

12,582,912 exact 16-bit samples in the unchanged DNG transport oracle; full file SHA256 71ed4fadfa3c4b5c01f67fa8abba378e6cbec090fa71d63cead735c57b80d286. This is not an on-phone Lightroom test. CI repeats all parent tests before the new overlay, then rebuilds Android and validates packaged markers/assets.

## Phone gate

Install over MONOOUTPUT1B, allow any pending jobs to resume, then take at least three Photo-mode shots without waiting for each derived export. Inspect terminal `exported`, `publicWriteCompleted`, `publicReadbackVerified`. Existing status revision remains MONOOUTPUT1B_DURABLE_EXPORT for job-schema compatibility; new attempts carry `publicationLookupRevision: MONOOUTPUT1C_CURSORQUERY`. Timings include publicInitialQueryMs, publicConflictQueryMs, publicCreateMetadataMs and publicFinalMetadataMs. Diagnostic bundles add `spoolTelemetryAtBundle.publicLookup1C`.

References: Android DocumentsContract child query, URI builders, returned rename URI and EXTRA_LOADING/EXTRA_ERROR contract; AndroidX DocumentFile.findFile / TreeDocumentFile.listFiles. Source references are implementation guidance, not evidence of Xiaomi provider speed.
