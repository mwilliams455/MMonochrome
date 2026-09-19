#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply-monolivegl1d-tripair1a.py <PhotonCamera-root>")

root=Path(sys.argv[1]).resolve()
fs=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
if not fs.exists():
    raise SystemExit("MONOLIVEGL1D shader missing")
s=fs.read_text()
if "MONOLIVEGL1C_DUALPAIR1A" not in s:
    raise SystemExit("MONOLIVEGL1D requires GL1C baseline")
if "MONOLIVEGL1D_TRIPAIR1A" in s:
    raise SystemExit("MONOLIVEGL1D already applied")

start=s.find("// MONOLIVEGL1B_PAIRFIT1A")
end=s.find("\nvec3 monoDisplayTransform1A", start)
if start < 0 or end < 0:
    raise SystemExit("MONOLIVEGL1D residual block not found")

new=r'''// MONOLIVEGL1B_PAIRFIT1A
// MONOLIVEGL1C_DUALPAIR1A
// MONOLIVEGL1D_TRIPAIR1A
// Scene-balanced common residual from three independent preview/final pairs.
// Earlier GL transforms are inverted back to the same GL1A-equivalent Photon
// carrier before fitting. Each scene contributes one median target per 1/16
// carrier knot; no scene is weighted by pixel count and no device branch exists.
float monoResidualTone1B(float x) {
    x = clamp(x, 0.0, 1.0);
    if (x <= 0.0625) return mix(0.000000, 0.011765, x / 0.0625);
    if (x <= 0.1250) return mix(0.011765, 0.026144, (x - 0.0625) / 0.0625);
    if (x <= 0.1875) return mix(0.026144, 0.039216, (x - 0.1250) / 0.0625);
    if (x <= 0.2500) return mix(0.039216, 0.050980, (x - 0.1875) / 0.0625);
    if (x <= 0.3125) return mix(0.050980, 0.067974, (x - 0.2500) / 0.0625);
    if (x <= 0.3750) return mix(0.067974, 0.083660, (x - 0.3125) / 0.0625);
    if (x <= 0.4375) return mix(0.083660, 0.103268, (x - 0.3750) / 0.0625);
    if (x <= 0.5000) return mix(0.103268, 0.121569, (x - 0.4375) / 0.0625);
    if (x <= 0.5625) return mix(0.121569, 0.151634, (x - 0.5000) / 0.0625);
    if (x <= 0.6250) return mix(0.151634, 0.206536, (x - 0.5625) / 0.0625);
    if (x <= 0.6875) return mix(0.206536, 0.278431, (x - 0.6250) / 0.0625);
    if (x <= 0.7500) return mix(0.278431, 0.380392, (x - 0.6875) / 0.0625);
    if (x <= 0.8125) return mix(0.380392, 0.522876, (x - 0.7500) / 0.0625);
    if (x <= 0.8750) return mix(0.522876, 0.701961, (x - 0.8125) / 0.0625);
    if (x <= 0.9375) return mix(0.701961, 0.862745, (x - 0.8750) / 0.0625);
    return mix(0.862745, 1.000000, (x - 0.9375) / 0.0625);
}
'''
s=s[:start]+new+s[end:]
fs.write_text(s)
print("MONOLIVEGL1D_TRIPAIR1A applied")
print(" - common 17-knot scene-balanced residual from three aligned pairs")
print(" - upper-mid/highlight correction reduced vs GL1C")
print(" - no device/manufacturer branch")
print(" - frozen still path untouched")
