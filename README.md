# MMonochrome

Firmware-first research project to reproduce the photographic rendering behaviour of the original Leica M Monochrom (M9-generation) on the Xiaomi 15 Ultra, with an eventual Android/PhotonCamera-derived implementation.

## Current phase

`research/mm-firmware-r0`

The first target is Leica M Monochrom firmware 1.022. The project begins from the proven M9 research architecture, but treats Monochrom tone, luminance, ISO, noise, shading and sharpening behaviour as independent until firmware evidence proves equivalence.

## Rules

- Firmware-first: do not tune by visual guess when the firmware can answer the question.
- Preserve provenance: every extracted fact should be reproducible from a script plus a source hash.
- Do not commit Leica firmware or decrypted firmware binaries to this repository.
- Separate proven facts, strong inferences and open hypotheses.
- Build an offline reference renderer before Android integration.
- Reuse M9 Android/capture infrastructure only after the Monochrom photographic path is understood.

## Initial finding

Leica M Monochrom 1.022 belongs to the same firmware family as Leica M9 1.216. It uses the same 1021-byte repeating XOR stream, decrypts to the same seven-lump PWAD container family, and the updater rules identify the target as `M9 mono`.

See `docs/` and `tools/` on the research branch for the reproducible evidence.
