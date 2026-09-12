# M Monochrom PROCESS SCHEDULE / NOISE BORDER1A

Date: 2026-09-12  
Firmware: original Leica M Monochrom 1.022  
Research branch: `research/mm-sharpness-lutbank1a`

## Status

The remaining scheduling/border gate ahead of a Standard-sharpness Android A/B is closed.

The full photographic processing path is:

```text
37-byte BF547 settings payload
-> 68-byte BF561 queued record
-> Task_TaskInterpolation
-> StartInterpolation / StartInterpolation_Jolos
-> SetProcess
-> SetStructParameter
-> Set
-> Run
```

The validated RAWSCALAR1B Android branch was not modified by this research.

## Runtime process-mask selection

`SetStructParameter(job, runtime)` maps queued job byte `job[4]` to `runtime+4`:

```text
job[4] == 2 -> runtime mode 0
job[4] == 3 -> runtime mode 1
job[4] == 0 -> runtime mode 2
```

`Set(runtime, parameter)` then maps `runtime+4` to the word consumed by `Run`:

```text
mode 0 -> 0x1407
mode 1 -> 0x17c7
mode 2 -> 0x0401
```

The closed `Run` dispatch assigns:

```text
bit 6 -> Noise
bit 7 -> Sharpness
bit 8 -> Contrast
bit 9 -> Y
```

Only mode 1 / mask `0x17c7` contains all four of Noise, Sharpness, Contrast and Y. Therefore the full JPEG processing record is type `3`, selecting runtime mode 1.

The full photographic stage order in the closed dispatch is:

```text
...
Noise
Sharpness
Contrast
Y
...
```

## `LoadLutArchiveL3` closes the Noise matrix source

Core A `LoadLutArchiveL3` at `0xfeb112b8` copies the archive section beginning at `PROCESS/LUTS + 0x134` into runtime `+0x18c` with length `0x2d4`:

```text
src = archive + header_offset[2] = archive + 0x134
dst = runtime + 0x18c
len = 0x2d4
```

Therefore archive/runtime offsets inside this copied section map exactly as:

```text
PROCESS/LUTS 0x140 -> runtime +0x198
```

`Set()` independently proves that `runtime+0x198` is the 5-row x 19-word Noise selector/ISO matrix used to produce `runtime+0x17c`.

This mapping has a positive structural control in the same loader:

```text
PROCESS/LUTS 0x408 section -> runtime +0x470
PROCESS/LUTS 0x410 matrix  -> runtime +0x478
```

and `runtime+0x478` is the already-proven Sharpness selector/ISO matrix. The extracted `0x410` Standard row exactly reproduces the previously proven Sharp schedule.

## Exact Noise selector x ISO matrix

At `PROCESS/LUTS 0x140`, the matrix is:

```text
5 selector rows x 19 uint32 words
```

For all five selector rows, the first 16 physical-ISO entries are:

```text
0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0
```

The final three row words are:

```text
1 1 -1
```

Thus the selector does not change the effective Noise mode for the 16 physical ISO slots in this firmware build.

## `Process_Noise` consequence

`Run` passes `runtime+0x178` as the Noise structure. `Process_Noise` reads its mode from structure `+4`, i.e. runtime `+0x17c`.

Closed mode/border behavior:

```text
mode 0 -> return / +0 border
mode 1 -> +2 border
mode 2 -> +4 border
mode 3 -> +2 border
```

Because every physical ISO slot selects mode `0`:

```text
Noise is dispatched by the full mask,
but performs no spatial Noise operation,
and contributes zero pixels to the valid-border accumulator.
```

## Exact Sharp incoming border

`Run` initializes the successful-path valid-border accumulator to `0`.

Noise leaves it at:

```text
Bin = 0
```

`Process_Sharpness` then adds exactly `+2` and calls `UM_Gauss3LUT` with:

```text
B = 2
```

Therefore Standard sharpness processes:

```text
x = 2 .. W-3
y = 2 .. H-3
```

and leaves the outer two pixels on every side unchanged by Sharpness.

No +4 or +6 border hypothesis remains for the normal Monochrom Standard photographic path.

## Implementation gate

The remaining pre-Android task is mechanical rather than forensic:

1. run a canonical host oracle using the real 16-row Sharp bank;
2. freeze deterministic vectors/hashes for exact modifier, two-pass Gaussian, LUT-helper, clamp and `B=2` geometry;
3. create a controlled RAWSCALAR1B + Standard-Sharp A/B without changing the promoted RAWSCALAR1B output.

Frozen production constraints remain unchanged: canonical curve02, RAWSCALAR1B fixed-D65 source bridge, LensShadingMap, MHC, JPEG quality, DNG persistence, capture/exposure policy, no HDR, no temporal fusion and no colour reconstruction.
