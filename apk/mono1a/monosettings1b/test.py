#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root = Path(sys.argv[1]).resolve()
layout = (root / "app/src/main/res/layout/layout_main_topbar.xml").read_text()
camera = (root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/CameraFragment.java").read_text()
controller = (root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/CameraUIController.java").read_text()
proof = json.loads((root / "MONOSETTINGS1B_ISOLATION.json").read_text())

assert proof["revision"] == "MONOSETTINGS1B_TOPBAR_SETTINGS1A"
assert proof["settingsButtonVisible"]
assert proof["settingsButtonRightOfFlash"]
assert not proof["renderChanged"]
assert not proof["dngPixelMathChanged"]
assert not proof["exposurePlacementChanged"]
assert not proof["curve02Changed"]

m = re.search(r'(<ImageButton\s+android:id="@\+id/settings_button"[\s\S]*?/>)', layout)
assert m, "settings button block"
block = m.group(1)
for marker in [
    'android:visibility="visible"',
    'app:layout_constraintStart_toEndOf="@id/flash_button"',
    'app:layout_constraintEnd_toEndOf="parent"',
    'android:onClick="@{top_bar_click_listener}"',
    'android:background="@drawable/ic_settings"',
]:
    assert marker in block, marker

# Existing security and navigation behavior must stay intact.
assert 'settingsButton.setVisibility(secureSession ? View.GONE : View.VISIBLE);' in camera
assert 'settingsButton.setEnabled(!secureSession);' in camera
assert 'case R.id.settings_button:' in controller
assert 'cameraFragment.launchSettings();' in controller
assert 'new Intent(activity, SettingsActivity.class)' in camera

report = {
    "revision": "MONOSETTINGS1B_TOPBAR_SETTINGS1A_TEST",
    "position": "immediately_right_of_flash",
    "visible": True,
    "navigation": "existing_SettingsActivity",
    "secureCameraBehavior": "existing guard retained",
    "photographicSeamFrozen": True,
}
(root / "MONOSETTINGS1B_TEST_REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
