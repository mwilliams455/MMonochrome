#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: verify-monolivegl1a-displaymono1a.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
paths = {
    "main": root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java",
    "glpreview": root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/GLPreview.java",
    "fragment": root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/CameraFragment.java",
    "shader": root / "app/src/main/assets/shaders/preview/main_fs.glsl",
    "renderer": root / "app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java",
    "iso": root / "app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java",
}
for n,p in paths.items():
    if not p.exists():
        raise SystemExit(f"MONOLIVEGL1A missing {n}: {p}")

mr=paths["main"].read_text()
gp=paths["glpreview"].read_text()
cf=paths["fragment"].read_text()
fs=paths["shader"].read_text()
rr=paths["renderer"].read_text()
iso=paths["iso"].read_text()

checks = [
    ("shader marker", "MONOLIVEGL1A_DISPLAYMONO1A" in fs),
    ("OES carrier", "samplerExternalOES sTexture" in fs and "texture(sTexture, uv)" in fs),
    ("sRGB linearization", "srgbToLinearMono1A" in fs),
    ("intended exposure uniform", "uMonoExposureScale1A" in fs and "linear *= uMonoExposureScale1A" in fs),
    ("linear luminance", "vec3(0.2126, 0.7152, 0.0722)" in fs),
    ("monochrome output", "return vec3(s);" in fs),
    ("no guessed tone", "DISPLAYMONO1A intentionally applies no guessed still-tone curve yet" in fs),
    ("focus peak conditional", "if (enablePeak)" in fs),
    ("renderer setter", "setMonoExposureScale1A(float scale)" in mr),
    ("GLPreview bridge", "setMonoExposureScale1A(float scale)" in gp),
    ("current intended pair", "IsoExpoSelector.GenerateExpoPair(-1, captureController)" in cf),
    ("actual preview exposure", "CaptureResult.SENSOR_EXPOSURE_TIME" in cf and "CaptureResult.SENSOR_SENSITIVITY" in cf),
    ("energy ratio", "intendedEnergy1A / actualEnergy1A" in cf),
    ("ZSL identity", "textureView.setMonoExposureScale1A(1.0f)" in cf),
    ("manual ISO retained", "MANUALISO1B GenerateExpoPair" in iso),
    ("SOURCE1D retained", "MONO1A_SOURCEADAPTER1A_MANUALISO1B_PORTABLE" in rr),
]
for label, ok in checks:
    print(("OK   " if ok else "FAIL ") + label)
    if not ok:
        raise SystemExit("MONOLIVEGL1A contract failure: " + label)

# The active shader must remain display-domain only.
for forbidden in (
    "sourceToM9Target",
    "sat2M9",
    "tungstenGuard",
    "curve02M9",
    "M9TargetFirmwareCalibration",
    "ColorMatrix",
    "ForwardMatrix",
    "Cobalt",
    "HSM",
):
    ok = forbidden not in fs
    print(("OK   " if ok else "FAIL ") + "shader excludes " + forbidden)
    if not ok:
        raise SystemExit("MONOLIVEGL1A sensor/still operation leaked into preview shader: " + forbidden)

# Capture allocator must not be patched by MONOLIVEGL1A.
cc = root / "app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java"
cct = cc.read_text()
if "MONOLIVEGL1A" in cct:
    raise SystemExit("MONOLIVEGL1A must not mutate CaptureController in baseline build")

print("MONOLIVEGL1A_DISPLAYMONO1A verification PASS")
print(" - fast Photon OES display path")
print(" - intended exposure represented live")
print(" - monochrome display-domain carrier")
print(" - authoritative still path untouched")
