# Pipeline hypotheses

Status labels: **PROVEN**, **STRONG**, **OPEN**.

## H1 — Same firmware family

**PROVEN.** M Monochrom 1.022 and M9 1.216 share the same XOR key, PWAD family, multiple byte-identical payloads and a directly nested BF561 symbol map relationship.

## H2 — Monochrom is not "M9 colour, saturation = 0"

**STRONG.** Colour/WB/FPGA-YCrCb symbols are removed from the Monochrom BF0 map, while PROCESS/LUTS grows from 427,744 bytes (M9) to 562,940 bytes (Monochrom) and has a different structure.

## H3 — 60-curve bank is three-way replication of 20 tone curves

**STRONG, semantics still OPEN.** The bank is 60 × 2048 bytes but only 20 unique monotonic curves exist; each unique curve appears three times in a structured pattern. The final 20 × 2048 tail bank is exactly the unique set. This strongly resembles a three-component storage layout with equal Monochrom transforms.

## H4 — 32 × 2050-byte region is ISO-paired processing data

**STRONG for ISO alignment, OPEN for purpose.** There are 16 ISO values and 32 equally sized tables. The tables alternate signed negative and positive monotonic ramps. Consumer tracing must determine whether these are noise, correction, threshold or another stage.

## H5 — First Xiaomi renderer should avoid full RGB colour science

**OPEN implementation hypothesis.** The preferred first test should reconstruct a single high-quality luminance plane from Xiaomi Bayer RAW, then feed firmware-derived Monochrom tone/spatial stages. A conventional demosaic + Rec.601 desaturation should exist only as a control branch, not as the assumed final design.

## Research gate before Android

Do not begin a production Android renderer until H3/H4 consumer placement and `Process_Y` input/output semantics are substantially closed. Android capture infrastructure may be reused later without importing M9 photographic assumptions.
