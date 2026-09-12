# M Monochrom AppendSettings / process-mask path — BF561 closed, BF547 producer next

Date: 2026-09-12

This note records a correction to the sharpness-forensics path. It separates what is now mechanically closed on BF561 from an earlier BF547 packet-alignment hypothesis that is no longer supported.

## 1. Closed BF561 receive path

The SportNet dispatch table is exact:

- command selector `0x04` -> `SPI_AppendSettings`
- table field2 = `0x25` = 37 bytes

`SPI_AppendSettings` at `0xffa03e74` receives a request pointer in `R0` and performs:

```text
R6 = R0
R6 += 7
R7 = FP - 37
memcpy(R7, R6, 37)
```

The local 37-byte buffer is therefore an exact copy of **request + 7**.

Its stack-frame arithmetic also closes three local-field reads without guessing:

- `SP + 0x3f` = local byte 4
- `SP + 0x40` = local byte 5
- `SP + 0x41` = local byte 6

When local byte 6 is zero, `SPI_AppendSettings` calls:

```text
IM_AppendItem(g_ProcessingList, local37)
```

`IM_AppendItem` allocates a 68-byte processing-list record and then performs:

```text
memcpy(record + 0, local37, 37)
```

No mask translation occurs in this step.

`IM_GetHead` later copies a complete 68-byte list record, and `IM_SetCurrentJob` copies all 17 words / 68 bytes verbatim into `g_CurrentProcessingSetti`.

`Run` begins by loading:

```text
R5 = [settings + 0]
```

and uses `R5` for its process-bit dispatch. In the closed dispatch region:

- bit 6 selects the Noise path
- bit 7 selects Sharpness
- bit 8 selects Contrast
- bit 9 selects Y

Therefore the first four bytes of the real SportNet `0x04` request payload are the process-mask u32 consumed by `Run`, without a BF561-side mask rewrite between receive and scheduling.

## 2. Correction: BF547 serializer 0x36ff4 is not proven to be that SportNet producer

A previous working hypothesis aligned BF547 object offset `+0x133` with SportNet payload byte zero because:

```text
0x133 - 0x12c = 7
```

That numerical alignment is **not sufficient evidence** and is now rejected as a process-mask mapping.

The BF547 routine at `0x36ff4` begins by copying four bytes from the fixed source `0x000eb440` into object `+0x12c`. The source starts with u32:

```text
0x31343133
```

The same 32-byte source window exists in the M9 control. This is protocol/object template material, not evidence of the BF561 SportNet `0x04` header.

The routine then writes object state to `+0x133..+0x150`. In particular:

```text
B[object + 0x133] = B[object + 0x35c]
```

The `+0x35c` field is initialized by the Monochrom constructor at `0x37a10`. Its 14 direct callsites show the caller supplying `R1 = 0,1,2,3,4,5,6` while stepping through seven objects of stride `0x57c`.

That makes the former interpretation untenable: this byte cannot simultaneously be the normal process-mask low byte required to control Sharpness bit 7 and Noise bit 6.

Additional evidence against treating `0x36ff4` as the AppendSettings producer:

- no direct CALL to `0x36ff4` was found;
- no literal u32 function pointer to `0x36ff4` was found;
- the split-immediate indirect-xref probe also found no construction/invocation of `0x36ff4`;
- the routine itself does not establish SportNet command selector `0x04` / payload length `0x25`.

Conclusion: **the BF547 `0x36ff4` serializer is no longer part of the asserted process-mask chain.** Its `+7` geometry was a false lead for this question.

## 3. Current exact boundary

Closed:

```text
real BF547 SportNet request
  -> command 0x04
  -> BF561 SPI_AppendSettings
  -> payload = request + 7, 37 bytes
  -> IM_AppendItem record[0:37]
  -> 68-byte processing record
  -> active processing settings
  -> Run mask u32
```

Not yet closed:

```text
normal Monochrom still/JPEG state
  -> BF547 process-settings structure
  -> SportNet command 0x04 request producer
```

The immediate research target is therefore the **BF547 SportNet client-side producer for command `0x04` with a 37-byte payload**, not the old `0x36ff4` object serializer.

## 4. Guardrail for Android work

Do not choose an incoming Sharpness border and do not promote the Android Standard sharpness experiment until the real BF547 command-0x04 payload has been located and its normal process mask / Noise setting are recovered.

The validated RAWSCALAR1B photographic baseline remains frozen.
