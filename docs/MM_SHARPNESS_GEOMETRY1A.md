# M Monochrom SHARPNESS GEOMETRY1A

Date: 2026-09-12  
Firmware: Leica M Monochrom 1.022  
Evidence run: `34688169699` (`MMonochrom-SHARPNESS-GEOMETRY1A`)

## Status

The image geometry around `Run -> Process_Sharpness -> UM_Gauss3LUT` is now closed sufficiently for a bit-faithful host reference.

The sharpening transfer was already closed separately. This note closes the image pointer, scratch pointer, width/height, accumulated valid-border state and the exact processed rectangle.

## Process_Sharpness call from Run

Core A call site:

```text
0xffa01cd4 -> 0xffa0287c Process_Sharpness
```

The call arguments reduce to:

```text
R0 = working width
R1 = working height
R2 = [processing + 0x34] = in-place uint16 image buffer
arg3 = [processing + 0x38] = uint16 Gaussian scratch buffer
arg4 = ctx + 0x460 = sharpness structure
arg5 = &valid_border
arg6 = [processing + 0x44] = forwarded prototype field; not consumed by UM_Gauss3LUT body
```

The width and height values are the same working dimensions used throughout `Run`; they can include the firmware's current tile/edge adjustment before the stage is invoked.

The sharpness structure pointer is constructed directly as:

```text
ctx + 0x460
```

which is the same structure whose LUT-bank fields were closed in `MM_SHARPNESS_LUTBANK1A.md`.

## Valid-border accumulator

`Run` initializes its local valid-border value to zero on the successful processing path.

It passes the address of that local value into scalar processing stages. `Process_Sharpness` performs exactly:

```text
border = *border_ptr
border += 2
*border_ptr = border
```

and passes the updated value into `UM_Gauss3LUT`.

Therefore the sharpness stage contributes exactly **+2 pixels per side** to the pipeline's accumulated invalid/untouched border.

This conclusion is direct Monochrom firmware evidence; it is not imported from the M9 reference.

## UM_Gauss3LUT ABI

The effective arguments used by the body are:

```text
UM_Gauss3LUT(
    uint16 width,          // R0.L
    uint16 height,         // R1.L
    uint16 *image,         // R2, read/write in place
    uint16 *scratch,       // first stack arg
    int border,            // accumulated border after +2
    int lut_bound,         // 1024
    int clip_magnitude,    // -table[0]
    int16 *lut_center,     // &table[1024]
    ...                    // one forwarded argument is not consumed by this body
)
```

`image` is both source and destination. `scratch` stores the horizontal Gaussian pass.

## Exact horizontal rectangle

Let:

```text
W = width
H = height
B = border
```

The first pass derives:

```text
interior_width = W - 2*B
horizontal_rows = H - 2*B + 2
start_index = (B - 1)*W + B
```

It therefore computes horizontal `[1,2,1]/4` values for:

```text
x = B .. W-B-1
y = B-1 .. H-B
```

using source neighbours `x-1, x, x+1`, and writes those values to the same coordinates in the scratch buffer.

For each output:

```text
scratch[y,x] = (image[y,x-1] + 2*image[y,x] + image[y,x+1]) >> 2
```

The per-row pointer correction is `2*B` pixels after the interior loop, which restores the physical row pitch to exactly `W` pixels.

## Exact vertical/detail rectangle

The second pass starts at:

```text
start_index = B*W + B
```

and iterates:

```text
x = B .. W-B-1
y = B .. H-B-1
```

For each pixel:

```text
blur = (scratch[y-1,x] + 2*scratch[y,x] + scratch[y+1,x]) >> 2
detail = image[y,x] - blur
correction = LUT(detail, 1024, clip_magnitude, lut_center)
image[y,x] = clamp(image[y,x] + correction, 0, 16383)
```

The image is modified in place only inside that rectangle.

## Border behavior

Pixels outside:

```text
[B, W-B) x [B, H-B)
```

are not written by `UM_Gauss3LUT` and remain unchanged by this stage.

If the incoming pipeline border is `Bin`, then:

```text
B = Bin + 2
```

so sharpness adds two untouched pixels on every side beyond the already-invalid incoming border.

No mirror, replicate or synthetic padding is introduced by this routine.

## Empty/small-region guards

The horizontal pass is skipped if its derived interior dimensions are non-positive. The final vertical/detail pass likewise checks the derived interior width/height before entering the loops.

A host implementation must therefore preserve the input unchanged when the effective region is empty rather than trying to synthesize edge samples.

## Implementation consequence

The Monochrom sharpness kernel is now closed in both **transfer arithmetic** and **image geometry**. The next gate is a canonical host oracle + frozen reference vectors using the actual 16-row Monochrom bank. Only after that oracle passes should a Standard-sharpness Android A/B branch be created from the validated RAWSCALAR1B branch.

The validated RAWSCALAR1B Android branch itself remains untouched.
