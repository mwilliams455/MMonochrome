# M Monochrom 1.022 firmware baseline v0.1

Date: 2026-09-11  
Target: original Leica M Monochrom (M9 generation)  
Source filename: `Mm-1_022.upm`

## Proven facts

### Source and decryption

- Encrypted firmware SHA-256: `53330385edfbfb9beeffa06645bffa2789e27dda614869107698919464f80ad8`
- Firmware size: 6,001,180 bytes.
- Encryption is a repeating XOR stream with period 1021 bytes.
- Recovered key SHA-256: `595c49ebabdaafcde7cc6cbd6aa7a37092d7c2ad4ca47d0d8bc57a04a5bed3a1`.
- That key hash is exactly the key previously recovered for Leica M9 firmware 1.216.
- Decrypted firmware SHA-256: `c9e14ee475408802c83774f37b19c85c57663d9840e8e4c2cfe80e14dec9a7ae`.
- Decrypted payload is a seven-lump Doom-style `PWAD`.
- The updater rules contain the Leica comment `Update fuer M9 mono`.

The key recovery in `tools/recover_mm_key.py` is independent of a stored key file. It uses the byte-identical M9/M Monochrom `BODY` component and the invariant

`C[i] XOR C[i+1021] = P[i] XOR P[i+1021]`

which cancels a repeating XOR key. The unique BODY match is at Monochrom offset `0x119350`.

### Outer PWAD

| Lump | Offset | Size | SHA-256 |
|---|---:|---:|---|
| RULES | `0x0000007c` | 3,044 | `fca961bb9b0ea5ed94b2a69b3cc47d00f68515c66c637a0fda45dafe3d3d5544` |
| LUTS | `0x00000c60` | 951,772 | `346289e9feb146133850aa023731c27644bc21c92a3ed69d6dc6241c5eb379c5` |
| BF561 | `0x000e923c` | 196,884 | `bac35e3ff2931e748f7f4917db410397fc74597d305f982d716abd47e606fe13` |
| BODY | `0x00119350` | 143,418 | `00295e22bf1c413a60c725635570b336f6df96be4a06af67ea8c006ff147f34b` |
| GUI | `0x0013c38c` | 3,647,672 | `1b11eb9971701a863e49f6a2266258646bd48de4b3a1ac0fb3efa3fcda39ab29` |
| FPGA | `0x004b6c44` | 150,176 | `c1d0c0d5e5233314c51dfb4dab973da3eda7920c20787c1be5a036bfe0fd5453` |
| BF547 | `0x004db6e4` | 908,080 | `8f82e5eb08c4933d821ce3df903a14846e300f940fee353514d37cda2c70b621` |

### Byte-identical M9 components

Compared with decrypted Leica M9 1.216:

- `BODY` is byte-identical.
- `GUI` is byte-identical.
- `LUTS/PROCESS/CREATE` is byte-identical.
- `LUTS/PROCESS/GAINMAP` is byte-identical (20,008 bytes).
- `LUTS/WBPARAM` is byte-identical (20,008 bytes).
- The individual `CCD` payloads `BLEMISH`, `WREF`, and `LIN` are byte-identical even though their enclosing PWAD differs.
- All three ICC payloads are byte-identical: ECI-RGB, sRGB IEC61966-2.1, Adobe RGB (1998).
- `BF561/bf1.map` is byte-identical (27,328 bytes).

The important differences are concentrated in `PROCESS/LUTS`, BF561 executable payloads, FPGA, BF547 and lens data.

## PROCESS/LUTS structure

Monochrom `PROCESS/LUTS`:

- size: **562,940 bytes**
- SHA-256: `dea370ecbf043da03a4af8a7d126d930caf8364f2c806e96a15b2dcb78fcab96`
- first 32-bit word: `3`
- header references offsets:
  `76, 152, 308, 1032, 1420, 67020, 67044, 67348, 190228, 190356, 504588, 504648, 520520, 520604, 520624, 521676, 521280, 521980`

### ISO list

At `0x98`:

- ISO count: **16**
- values: `320, 400, 500, 640, 800, 1000, 1250, 1600, 2000, 2500, 3200, 4000, 5000, 6400, 8000, 10000`

### ISO-aligned paired LUT region

`0x058c..0x105cc` is exactly 65,600 bytes, which is **32 × 2,050 bytes**. This aligns naturally with 16 ISO entries × 2 tables per ISO. Interpreted as signed 16-bit data, the blocks form monotonic negative/positive ramps. Their exact photographic role is not assigned yet.

### 60-curve bank

`0x10714..0x2e714` is exactly **60 × 2,048 bytes**.

All 60 items are monotonic 8-bit transfer curves, but there are only **20 unique curves**. Their repetition pattern is:

- curves 0-9 repeated at 10-19 and 20-29;
- curves 30-39 repeated at 40-49 and 50-59.

This is strong evidence for a three-way replicated processing structure, consistent with reuse of infrastructure designed for three components/channels, but channel semantics remain a hypothesis until consumer code is closed.

### Canonical 20-curve tail bank

The final 40,960 bytes, starting at `0x7f6fc`, are exactly **20 × 2,048-byte curves**. Those 20 curves are exactly the 20 unique curves represented in the earlier 60-curve bank.

This is one of the highest-priority consumer traces because it likely exposes the Monochrom tone/contrast family directly.

### Shared 15,872-byte table

At `0x7b348`, the following **15,872 bytes are byte-identical to the M9 PROCESS/LUTS final major table payload**. The preceding 60-byte header differs slightly between M9 and Monochrom. This shared payload is likely a non-colour/spatial processing asset, but no semantic label is assigned until its consumer is proven.

## BF561 cross-generation result

`BF561/bf0.map` in Monochrom is 13,440 bytes / 420 fixed-width records.

The entire file occurs byte-for-byte inside the M9 `bf0.map` at offset `0x3940` (14,656 decimal). Every Monochrom symbol/address/size tuple therefore exists exactly in the M9 map.

M9-only symbols removed from the Monochrom map include:

- `ExecuteColorMatrix_14FM1`
- `Process_WB`
- `Process_FPGA_Y`
- `Process_FPGA_YCrCb`
- `SetMatrixL3`
- `LoadLutDataL3`
- `L3L1_Put16BitRGB`
- `L3L1_Put3rgb`
- `L3L1_Put3yycrcb`
- `Process_DNGNoise`
- colour interpolation/difference helpers

Monochrom retains the core photographic/spatial path, including:

- `Process_Contrast`
- `ExecuteContrast_11LUT8_7`
- `ExecuteContrast_11LUT8_2`
- `ExecuteContrast_11LUT8_3`
- `Process_Noise`
- `Process_Shading`
- `Process_Sharpness`
- `Process_Y`
- `L3L1_Put8BitY`
- `LoadLutArchiveL3`
- `LoadISODataL1`
- `CalculateNoiseParameter`

## Interpretation

### Proven

The M Monochrom 1.022 firmware is not merely from the same era as the M9. It is directly derived from the same software architecture, encryption family, PWAD organization and BF561 symbol universe.

### Strong inference

The Monochrom-specific photographic identity is likely concentrated in:

1. the revised `PROCESS/LUTS` archive;
2. the reduced/changed BF561 executable path;
3. Monochrom-specific FPGA and BF547 behaviour;
4. its different sensor/input domain.

### Not yet proven

- Exact input domain of `Process_Y`.
- Whether the 20 unique 2048-entry curves are contrast settings, transfer curves, or another stage.
- Exact meaning of the two 2050-byte LUTs per ISO.
- Placement/order of tone, noise, shading and sharpening.
- How to reconstruct a Xiaomi Bayer RAW into the closest practical equivalent of the Leica monochrome sensor signal.

## Next research block

1. Trace `LoadLutArchiveL3` field-by-field against the 1.022 header offsets.
2. Determine which header offsets feed `Process_Contrast`, `Process_Y`, `Process_Noise`, `Process_Shading`, and `Process_Sharpness`.
3. Close the 20-curve consumer and selector arithmetic.
4. Close ISO selection for the 32 × 2050-byte paired region.
5. Only then design the first offline Xiaomi RAW -> Monochrom reference renderer.
