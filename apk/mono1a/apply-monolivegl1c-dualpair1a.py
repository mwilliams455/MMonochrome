#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply-monolivegl1c-dualpair1a.py <PhotonCamera-root>")

root=Path(sys.argv[1]).resolve()
fs=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
if not fs.exists():
    raise SystemExit("MONOLIVEGL1C shader missing")
s=fs.read_text()
if "MONOLIVEGL1B_PAIRFIT1A" not in s:
    raise SystemExit("MONOLIVEGL1C requires GL1B baseline")
if "MONOLIVEGL1C_DUALPAIR1A" in s:
    raise SystemExit("MONOLIVEGL1C already applied")

start=s.find("// MONOLIVEGL1B_PAIRFIT1A")
end=s.find("\nvec3 monoDisplayTransform1A", start)
if start < 0 or end < 0:
    raise SystemExit("MONOLIVEGL1C GL1B residual block not found")

new=r'''// MONOLIVEGL1B_PAIRFIT1A
// MONOLIVEGL1C_DUALPAIR1A
// Scene-balanced display-domain residual reconstructed from two independent
// carrier->final pairs:
//   - Xiaomi 15 Ultra GL1A preview vs frozen Monochrom JPEG
//   - Xiaomi 17 Ultra GL1B preview inverted through the exact GL1B monotonic map
//     back to its GL1A-equivalent carrier, then compared to frozen Monochrom JPEG.
//
// Each scene contributes one median target at each 1/16 carrier knot so the
// large dark region in either photograph cannot dominate merely by pixel count.
// No manufacturer/camera-id branch is used. This remains display-domain only.
float monoResidualTone1B(float x) {
    x = clamp(x, 0.0, 1.0);
    if (x <= 0.0625) return mix(0.000000, 0.011765, x / 0.0625);
    if (x <= 0.1250) return mix(0.011765, 0.025490, (x - 0.0625) / 0.0625);
    if (x <= 0.1875) return mix(0.025490, 0.035294, (x - 0.1250) / 0.0625);
    if (x <= 0.2500) return mix(0.035294, 0.050980, (x - 0.1875) / 0.0625);
    if (x <= 0.3125) return mix(0.050980, 0.066667, (x - 0.2500) / 0.0625);
    if (x <= 0.3750) return mix(0.066667, 0.082353, (x - 0.3125) / 0.0625);
    if (x <= 0.4375) return mix(0.082353, 0.100000, (x - 0.3750) / 0.0625);
    if (x <= 0.5000) return mix(0.100000, 0.119608, (x - 0.4375) / 0.0625);
    if (x <= 0.5625) return mix(0.119608, 0.150980, (x - 0.5000) / 0.0625);
    if (x <= 0.6250) return mix(0.150980, 0.205882, (x - 0.5625) / 0.0625);
    if (x <= 0.6875) return mix(0.205882, 0.276471, (x - 0.6250) / 0.0625);
    if (x <= 0.7500) return mix(0.276471, 0.372549, (x - 0.6875) / 0.0625);
    if (x <= 0.8125) return mix(0.372549, 0.537255, (x - 0.7500) / 0.0625);
    if (x <= 0.8750) return mix(0.537255, 0.752941, (x - 0.8125) / 0.0625);
    if (x <= 0.9375) return mix(0.752941, 0.884314, (x - 0.8750) / 0.0625);
    return mix(0.884314, 1.000000, (x - 0.9375) / 0.0625);
}
'''
s=s[:start]+new+s[end:]
fs.write_text(s)
print("MONOLIVEGL1C_DUALPAIR1A applied")
print(" - common 17-knot scene-balanced residual from 15U + 17U")
print(" - no device/manufacturer branch")
print(" - GL1A exposure representation retained")
print(" - frozen still path untouched")
