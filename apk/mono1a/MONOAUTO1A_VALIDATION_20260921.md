# MONOAUTO1A — implemented shared exposure-plan port

21 September 2026. First-stage implementation; not a claim that every M9 auto-exposure improvement is ported or phone-validated.

## Delivered build

- Build commit: 4702c1b4a3640aaecf20360440bb3f3a1f8c78f9.
- Branch: research/monoauto1a-exposureplan.
- Baseline: ed9487ce6f5e9411cbdf99968b77af660e180811, GL2B plus MONOOUTPUT1A.
- Successful Actions run: 35585056036; job 106286335852.
- APK artifact: 10631318961; full CI evidence artifact: 10632255153.
- APK: MMonochrome_MONOAUTO1A_EXPOSUREPLAN.apk.
- Version: 0.03-mmonochrome-gl2b-monoauto1a.
- SHA-256: ff43295e2c9fcaac24d3823ba3cc89d8c7186cd72b238cf81a5111bac5f8b5b9.
- Bytes: 115460985.

## Implemented

The M9 shared-plan architecture has been adapted to Monochrom Photo mode. An immutable physical-ISO exposure plan is used by the HUD, GPU exposure representation and still request. The existing eligible multi-field assist is evaluated prospectively and stored in that plan, not secretly recalculated or added again at capture. The current preferred allocation math remains in place.

User EV combines the settings EV and the manual dial's reported Camera2 step. The hardware preview is maintained as a neutral AE reference; EV is applied once in the planned exposure. Manual ISO and shutter are physical controls constrained by the active physical camera's advertised ranges. There is no 15 Ultra model restriction or hard-coded 15 Ultra analogue ceiling introduced here.

Plan validity includes camera, session/control epoch, observation age and current EV/manual/tripod/balance/metering controls. GL receives one immutable presentation object. The shutter prefers an eligible recent pre-shutter GL draw acknowledgement; missing-draw/current-control fallbacks are identified explicitly. A missing valid plan causes a retryable error rather than discarding user controls in favour of unrelated hardware AE.

This applies to ordinary Photo mode without dual-session operation, recording or active flash. Motion/ZSL and other capture routes retain their existing path. A GL acknowledgement is not proof that the Android compositor presented the exact pixels; preview simulation range and GL2B source/fallback limitations remain.

## Frozen photographic components

The complete still renderer, SOURCE1D luminance treatment, native rendering source, Monochrom curve02, fragment shader and monochrome-DNG exporter are unchanged. Existing GL2B curve-contract checks remain. MONOOUTPUT1A still retains the original phone DNG, exports the derived monochrome DNG, and keeps six comparison JPEGs disabled. No M9 colour/TC20 renderer or HDR path was imported.

Changed exposure decisions necessarily change captured data. Unchanged rendering math does not promise identical photographs after an exposure change.

## Validation

All Android compilation, host tests, packaged-file checks and uploads succeeded. New tests: 4,087 assertions, including 4,000 concurrent publication checks, using the real plan/store, modified IsoExpoSelector and actual ParamController with mocked Android/device dependencies. Checks include EV response, manual controls, camera/control invalidation, pre/post-shutter selection and no duplicate capture assist. The parent GL2B/SOURCE1D/DNG tests also passed.

GPU/native reference tests passed 57,344 synthetic pixel comparisons with maximum one output-code difference; all 24,576 full-path exposure-bracket comparisons were exact. These are host fixtures, not phone exposure or image-parity tests.

Downloaded APK SHA matched CI. All 18 packaged native libraries are byte-identical to delivered GL2B. Packaged shader/curve match exactly. All seven uploaded overlay files and 12 changed assembled files match the locally tested versions. CI sealed 889 unchanged source/resource files; local delivery rechecked the 888 present in the archive. The artifact uploader omitted one hidden cpp/deps/.gitignore entry, not a photographic source file.

## Diagnostics and next device gate

The existing normal capture/burst export now includes monoExposurePlan1A and exposureDecisionAuthority=MONOAUTO1A_EXPOSUREPLAN. Old Photon audit snapshots are marked as not the authoritative current allocation. The live-pair record identifies the selection reason, optional GL draw identity, actual request/result and recordedVsSharedPlanEv.

Test Photo Auto and explicit negative/positive EV, then a manual ISO/shutter pair, on main and telephoto. Supply the normal diagnostic bundle for request/result and selected-plan checks. No extra diagnostic filename is required.

## Explicitly not included

M9 GL2G energy-preserving allocation at sensor/automatic limits and Monochrom-adapted rendered-dark-scene Auto placement are separate next ports. allocation2GPorted and renderedDarkScenePlacementPorted remain false. No claim that deep-low-light brightening or the complete auto-exposure system is solved is made. No default-branch merge was performed.
