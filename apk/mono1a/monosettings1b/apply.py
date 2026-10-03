#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root = Path(sys.argv[1]).resolve()
layout = root / "app/src/main/res/layout/layout_main_topbar.xml"
gradle = root / "app/build.gradle"
J = root / "app/src/main/java/com/particlesdevs/photoncamera"
for p in (layout, gradle):
    if not p.is_file():
        raise SystemExit("MONOSETTINGS1B missing " + str(p))

frozen = [
    J / "m9/render/M9R35Renderer.java",
    J / "m9/export/MonoDngExport1A.java",
    J / "m9/export/MonoDngWriter1A.java",
    J / "m9/export/MonoLinearPlane1A.java",
    J / "m9/exposure/MonoPlacementAssist1D.java",
    J / "m9/preview/MonoTapMeter1A.java",
    J / "processing/parameters/IsoExpoSelector.java",
    J / "ui/camera/CameraFragment.java",
    J / "ui/camera/CameraUIController.java",
    root / "app/src/main/cpp/m9color_jni.cpp",
    root / "app/src/main/assets/mono/mono_curve02_gl2a.bin",
]
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
before = {str(p.relative_to(root)): sha(p) for p in frozen if p.exists()}

s = layout.read_text()
m = re.search(r'(<ImageButton\s+android:id="@\+id/settings_button"[\s\S]*?/>)', s)
if not m:
    raise SystemExit("MONOSETTINGS1B settings_button block missing")
block = m.group(1)
if 'app:layout_constraintStart_toEndOf="@id/flash_button"' not in block:
    raise SystemExit("MONOSETTINGS1B settings button is not to the right of flash")
if 'app:layout_constraintEnd_toEndOf="parent"' not in block:
    raise SystemExit("MONOSETTINGS1B settings button is not right-edge constrained")
if 'android:onClick="@{top_bar_click_listener}"' not in block:
    raise SystemExit("MONOSETTINGS1B settings click listener missing")
if 'android:visibility="gone"' in block:
    new_block = block.replace('android:visibility="gone"', 'android:visibility="visible"', 1)
elif 'android:visibility="visible"' in block:
    new_block = block
else:
    raise SystemExit("MONOSETTINGS1B settings visibility anchor missing")
s = s[:m.start(1)] + new_block + s[m.end(1):]
layout.write_text(s)

g = gradle.read_text()
m = re.search(r"versionName\s+'([^']+)'", g)
if not m:
    raise SystemExit("MONOSETTINGS1B versionName missing")
if "monosettings1b-topbarsettings1a" not in m.group(1):
    g = g[:m.start(1)] + m.group(1) + "-monosettings1b-topbarsettings1a" + g[m.end(1):]
gradle.write_text(g)

after = {str(p.relative_to(root)): sha(p) for p in frozen if p.exists()}
if before != after:
    changed = [k for k in before if before[k] != after.get(k)]
    raise SystemExit("MONOSETTINGS1B photographic seam changed: " + repr(changed))

proof = {
    "revision": "MONOSETTINGS1B_TOPBAR_SETTINGS1A",
    "parent": "MONOSETTINGS1A_LEICA_UI_CLEANUP",
    "settingsButtonVisible": True,
    "settingsButtonRightOfFlash": True,
    "settingsButtonRightEdge": True,
    "settingsClickPathUnchanged": True,
    "secureSessionGuardUnchanged": True,
    "renderChanged": False,
    "dngPixelMathChanged": False,
    "exposurePlacementChanged": False,
    "curve02Changed": False,
    "frozenPhotographicHashes": after,
}
(root / "MONOSETTINGS1B_ISOLATION.json").write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
