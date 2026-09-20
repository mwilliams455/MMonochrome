#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: verify-monolivegl1e-livepairdiag1b-filemanager.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
p = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoLivePairDiagnostics1E.java"
if not p.exists():
    raise SystemExit("diagnostic class missing")
s = p.read_text()

checks = [
    ("1B marker", "MONOLIVEGL1E_LIVEPAIRDIAG1B_FILEMANAGER" in s),
    ("Photon file authority", "FileManager.sDCIM_CAMERA.getAbsolutePath()" in s),
    ("NIO write", "Files.write(out, bytes)" in s),
    ("parent create", "Files.createDirectories(out.getParent())" in s),
    ("livepair filename", '"MONO_LIVEPAIR_" + pairId + "_" + sensorPart + ".json"' in s),
    ("GL1E schema retained", "mmonochrome.livepreview.gl1e.livepairdiag1a" in s),
]
for label, ok in checks:
    print(("OK   " if ok else "FAIL ") + label)
    if not ok:
        raise SystemExit("GL1E 1B verifier failure: " + label)

for forbidden in (
    'Environment.getExternalStorageDirectory()',
    'new FileOutputStream(out)',
):
    if forbidden in s:
        raise SystemExit("obsolete direct external writer retained: " + forbidden)

print("MONOLIVEGL1E_LIVEPAIRDIAG1B_FILEMANAGER verification PASS")
