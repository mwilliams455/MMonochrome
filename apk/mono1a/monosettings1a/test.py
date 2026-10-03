#!/usr/bin/env python3
from pathlib import Path
import json
import sys
import xml.etree.ElementTree as ET

if len(sys.argv) != 2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root = Path(sys.argv[1]).resolve()
pref = root / "app/src/main/res/xml/preferences.xml"
settings = root / "app/src/main/java/com/particlesdevs/photoncamera/api/Settings.java"
topbar = root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/viewmodel/SettingsBarEntryProvider.java"
proof = json.loads((root / "MONOSETTINGS1A_ISOLATION.json").read_text())

assert proof["revision"] == "MONOSETTINGS1A_LEICA_UI_CLEANUP"
assert not proof["videoSettingsVisible"]
assert proof["binningCodeRetained"] and not proof["binningVisible"] and not proof["binningRuntimeEnabled"]
assert proof["quadBayerCodeRetained"] and not proof["quadBayerVisible"] and not proof["quadBayerRuntimeEnabled"]
assert not proof["renderChanged"] and not proof["dngPixelMathChanged"]
assert not proof["exposurePlacementChanged"] and not proof["curve02Changed"]

ANDROID = "http://schemas.android.com/apk/res/android"
akey = "{" + ANDROID + "}key"
tree = ET.parse(pref)
keys = []
for node in tree.getroot().iter():
    k = node.attrib.get(akey)
    if k:
        keys.append(k)

absent = {
    "@string/pref_category_video_shortcut_key",
    "@string/pref_category_photo_key",
    "@string/pref_category_jpg_key",
    "@string/pref_category_hdrx_key",
    "@string/pref_wide169_key",
    "@string/pref_binning_key",
    "@string/pref_show_roundedge_key",
    "@string/pref_show_watermark_key",
    "@string/pref_show_afdata_key",
    "@string/pref_preserve_manual_wb_key",
    "@string/pref_frame_count_key",
    "@string/pref_enable_system_nr_key",
    "@string/pref_disable_aligning_key",
    "@string/pref_chroma_nr_seekbar_key",
    "@string/pref_luma_nr_seekbar_key",
    "@string/pref_enhanced_processing_key",
    "@string/pref_save_heic_key",
    "@string/pref_ultrahdr_key",
    "@string/pref_hdrx_nr_key",
    "@string/pref_sharpness_seekbar_key",
    "@string/pref_saturation_seekbar_key",
    "@string/pref_contrast_seekbar_key",
    "@string/pref_expocompensation_seekbar_key",
    "@string/pref_noise_seekbar_key",
    "@string/pref_merge_seekbar_key",
    "@string/pref_shadows_seekbar_key",
    "@string/pref_compressor_seekbar_key",
    "@string/pref_cfa_key",
    "@string/pref_align_method_key",
    "@string/pref_color_method_key",
    "@string/pref_preview_format_key",
}
for k in absent:
    assert k not in keys, k

for k in ["@string/pref_save_raw_key", "@string/pref_horizon", "@string/pref_af_mode_key",
          "@string/pref_peak_method_key", "@string/pref_show_grid_key"]:
    assert k in keys, k

tb = topbar.read_text()
assert "private final SettingsBarEntryModel quadEntry" in tb
assert "createQuadBayerEntry();" in tb
assert "allEntries.add(quadEntry);" not in tb
assert "allEntries.add(eisEntry);" not in tb
assert "allEntries.add(fpsEntry);" not in tb
for retained in ["allEntries.add(saveRawEntry);", "allEntries.add(bracketingEntry);",
                 "allEntries.add(aeMeteringStdEntry);", "allEntries.add(timerEntry);",
                 "allEntries.add(gridEntry);"]:
    assert retained in tb, retained

s = settings.read_text()
for marker in [
    'MONO_SETTINGS_POLICY_REVISION = "MONOSETTINGS1A_LEICA_UI_CLEANUP"',
    "frameCount = 1;",
    "binning = false;",
    "QuadBayer = false;",
    "heicSave = false;",
    "hdrx = false;",
    "hdrxNR = false;",
    "ultraHdr = false;",
    "watermark = false;",
    "aspect169 = false;",
]:
    assert marker in s, marker

report = {
    "revision": "MONOSETTINGS1A_LEICA_UI_CLEANUP_TEST",
    "visiblePreferenceKeys": keys,
    "topBarHidden": ["Quad Bayer", "Photo EIS", "FPS"],
    "topBarRetained": ["Flash", "Timer", "JPEG/DNG output", "Grid", "Battery saver", "Bracketing", "AE metering"],
    "dormantRetainedCode": ["Binning", "Quad Bayer"],
    "photographicSeamFrozen": True,
}
(root / "MONOSETTINGS1A_TEST_REPORT.json").write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
