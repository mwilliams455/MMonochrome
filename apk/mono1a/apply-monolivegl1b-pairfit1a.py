#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply-monolivegl1b-pairfit1a.py <PhotonCamera-root>")

root=Path(sys.argv[1]).resolve()
fs=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
if not fs.exists():
    raise SystemExit("MONOLIVEGL1B shader missing")
s=fs.read_text()
if "MONOLIVEGL1A_DISPLAYMONO1A" not in s:
    raise SystemExit("MONOLIVEGL1B requires GL1A baseline")
if "MONOLIVEGL1B_PAIRFIT1A" in s:
    raise SystemExit("MONOLIVEGL1B already applied")

anchor="""vec3 monoDisplayTransform1A(vec3 photonSrgb) {
"""
insert=r'''// MONOLIVEGL1B_PAIRFIT1A
// Display-domain residual measured from the first aligned GL1A-preview/final-JPEG pair.
// The final still renderer is NOT sampled at runtime and remains authoritative.
// Control points are sRGB display luminance -> final JPEG display luminance.
float monoResidualTone1B(float x) {
    x = clamp(x, 0.0, 1.0);
    if (x <= 0.0625) return mix(0.000000, 0.013222, x / 0.0625);
    if (x <= 0.1250) return mix(0.013222, 0.024412, (x - 0.0625) / 0.0625);
    if (x <= 0.1875) return mix(0.024412, 0.033275, (x - 0.1250) / 0.0625);
    if (x <= 0.2500) return mix(0.033275, 0.045118, (x - 0.1875) / 0.0625);
    if (x <= 0.3125) return mix(0.045118, 0.056556, (x - 0.2500) / 0.0625);
    if (x <= 0.3750) return mix(0.056556, 0.070745, (x - 0.3125) / 0.0625);
    if (x <= 0.4375) return mix(0.070745, 0.089500, (x - 0.3750) / 0.0625);
    if (x <= 0.5000) return mix(0.089500, 0.110000, (x - 0.4375) / 0.0625);
    if (x <= 0.5625) return mix(0.110000, 0.140794, (x - 0.5000) / 0.0625);
    if (x <= 0.6250) return mix(0.140794, 0.213373, (x - 0.5625) / 0.0625);
    if (x <= 0.6875) return mix(0.213373, 0.309088, (x - 0.6250) / 0.0625);
    if (x <= 0.7500) return mix(0.309088, 0.405000, (x - 0.6875) / 0.0625);
    if (x <= 0.8125) return mix(0.405000, 0.536196, (x - 0.7500) / 0.0625);
    if (x <= 0.8750) return mix(0.536196, 0.710000, (x - 0.8125) / 0.0625);
    if (x <= 0.9375) return mix(0.710000, 0.933776, (x - 0.8750) / 0.0625);
    return mix(0.933776, 1.000000, (x - 0.9375) / 0.0625);
}

'''
if s.count(anchor)!=1:
    raise SystemExit("MONOLIVEGL1B transform anchor mismatch")
s=s.replace(anchor,insert+anchor,1)

old=r'''    // DISPLAYMONO1A intentionally applies no guessed still-tone curve yet.
    // First device pairs will measure the display-domain residual against the
    // final Monochrom JPEG, following the validated M9 GL approach.
    float outY = clamp(y, 0.0, 1.0);
    float s = clamp(linearToSrgbMono1A(outY), 0.0, 1.0);
    return vec3(s);
'''
new=r'''    // GL1B: convert the exposure-aligned linear carrier to display luminance,
    // then apply the measured display-domain residual. This is deliberately
    // AFTER exposure representation and does not replay RAW/source transforms.
    float carrierY = clamp(y, 0.0, 1.0);
    float carrierSrgb = clamp(linearToSrgbMono1A(carrierY), 0.0, 1.0);
    float finalLikeSrgb = monoResidualTone1B(carrierSrgb);
    return vec3(finalLikeSrgb);
'''
if s.count(old)!=1:
    raise SystemExit("MONOLIVEGL1B GL1A neutral-tone anchor mismatch")
s=s.replace(old,new,1)
fs.write_text(s)
print("MONOLIVEGL1B_PAIRFIT1A applied")
print(" - 17-point monotonic display-domain residual from aligned GL1A/JPEG pair")
print(" - exposure representation remains before residual tone")
print(" - SOURCE1D/RAWSCALAR/curve02/still renderer untouched")
