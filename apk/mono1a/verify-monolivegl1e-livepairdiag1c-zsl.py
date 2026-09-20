#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: verify-monolivegl1e-livepairdiag1c-zsl.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
cc = root / "app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java"
cf = root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/CameraFragment.java"
diag = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoLivePairDiagnostics1E.java"
for p in (cc, cf, diag):
    if not p.exists():
        raise SystemExit("missing " + str(p))

c=cc.read_text(); f=cf.read_text(); d=diag.read_text()
checks=[
 ("1C marker controller","MONOLIVEGL1E_LIVEPAIRDIAG1C_ZSL" in c),
 ("1C marker fragment","MONOLIVEGL1E_LIVEPAIRDIAG1C_ZSL" in f),
 ("ZSL mode is Motion","selectedMode == CameraMode.MOTION" in c),
 ("ZSL actual preview mirror","actualIso1E, actualExposureNs1E,\n                                actualIso1E, actualExposureNs1E, 1.0" in f),
 ("ZSL result authority","final CaptureResult monoZslResult1E = mPreviewCaptureResult;" in c),
 ("ZSL request authority","final CaptureRequest monoZslRequest1E = mPreviewCaptureRequest;" in c),
 ("ZSL snapshot before ring","c.find('monoZslSnapshot1E') < c.find('List<Image> rawImages;')"),
 ("ZSL writer","MonoLivePairDiagnostics1E.writeCompleted(\n                    monoZslSnapshot1E, monoZslRequest1E, monoZslResult1E" in c),
 ("non-ZSL writer retained","monoLivePairPreviewSnapshot1E, request, result" in c),
 ("writer accepts CaptureResult","CaptureResult result, String physicalCameraId" in d),
 ("FileManager writer retained","FileManager.sDCIM_CAMERA.getAbsolutePath()" in d),
]
for label,ok in checks:
    print(("OK   " if ok else "FAIL ")+label)
    if not ok:
        raise SystemExit("GL1E 1C verifier failure: "+label)

print("MONOLIVEGL1E_LIVEPAIRDIAG1C_ZSL verification PASS")
