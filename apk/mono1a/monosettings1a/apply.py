#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import re
import sys
import xml.etree.ElementTree as ET

if len(sys.argv) != 2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
pref = root / "app/src/main/res/xml/preferences.xml"
settings = root / "app/src/main/java/com/particlesdevs/photoncamera/api/Settings.java"
topbar = root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/viewmodel/SettingsBarEntryProvider.java"
gradle = root / "app/build.gradle"
for p in (pref, settings, topbar, gradle):
    if not p.is_file():
        raise SystemExit("MONOSETTINGS1A missing " + str(p))

J = root / "app/src/main/java/com/particlesdevs/photoncamera"
frozen = [
    J / "m9/render/M9R35Renderer.java",
    J / "m9/export/MonoDngExport1A.java",
    J / "m9/export/MonoDngWriter1A.java",
    J / "m9/export/MonoLinearPlane1A.java",
    J / "m9/exposure/MonoPlacementAssist1D.java",
    J / "m9/preview/MonoTapMeter1A.java",
    J / "processing/parameters/IsoExpoSelector.java",
    root / "app/src/main/cpp/m9color_jni.cpp",
    root / "app/src/main/assets/mono/mono_curve02_gl2a.bin",
]
def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

frozen_before = {str(p.relative_to(root)): sha(p) for p in frozen if p.exists()}

ANDROID = "http://schemas.android.com/apk/res/android"
APP = "http://schemas.android.com/apk/res-auto"
ET.register_namespace("android", ANDROID)
ET.register_namespace("app", APP)
akey = "{" + ANDROID + "}key"

tree = ET.parse(pref)
screen = tree.getroot()

def key(node):
    return node.attrib.get(akey, "")

def category(k):
    for node in list(screen):
        if key(node) == k:
            return node
    return None

general = category("@string/pref_category_general_key")
if general is None:
    raise SystemExit("MONOSETTINGS1A general category missing")

# Hide controls that are either non-Monochrom processing or deliberately dormant.
general_hide = {
    "@string/pref_wide169_key",
    "@string/pref_binning_key",
    "@string/pref_show_roundedge_key",
    "@string/pref_show_watermark_key",
    "@string/pref_show_afdata_key",
    "@string/pref_preserve_manual_wb_key",
}
for node in list(general):
    if key(node) in general_hide:
        general.remove(node)

# Retain the useful output selector and horizon control, but remove the generic
# Photon HDRX/tuning category around them.
hdrx = category("@string/pref_category_hdrx_key")
if hdrx is None:
    raise SystemExit("MONOSETTINGS1A HDRX category missing")
move_keys = {"@string/pref_save_raw_key", "@string/pref_horizon"}
moved = []
for node in list(hdrx):
    if key(node) in move_keys:
        hdrx.remove(node)
        general.append(node)
        moved.append(key(node))
if set(moved) != move_keys:
    raise SystemExit("MONOSETTINGS1A expected RAW + horizon controls not found: " + repr(moved))

# Entire sections that should not appear in the Monochrom still-camera UI.
remove_categories = {
    "@string/pref_category_video_shortcut_key",
    "@string/pref_category_photo_key",
    "@string/pref_category_jpg_key",
    "@string/pref_category_hdrx_key",
}
removed_categories = []
for node in list(screen):
    if key(node) in remove_categories:
        removed_categories.append(key(node))
        screen.remove(node)
remaining_categories = {key(node) for node in list(screen)}
still_visible = sorted(remove_categories.intersection(remaining_categories))
if still_visible:
    raise SystemExit("MONOSETTINGS1A categories still visible: " + repr(still_visible))

ET.indent(tree, space="    ")
tree.write(pref, encoding="utf-8", xml_declaration=True)

def replace_once(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"MONOSETTINGS1A {label} anchor count={n}")
    return text.replace(old, new, 1)

# Keep Quad Bayer / EIS / FPS implementation in source, but hide the top-bar
# entries in this Monochrom build. Quad can be exposed later when we implement
# and validate the remosaic path.
s = topbar.read_text()
for old, label in [
    ("        allEntries.add(quadEntry);\n", "hide Quad Bayer topbar"),
    ("        allEntries.add(eisEntry);\n", "hide EIS topbar"),
    ("        allEntries.add(fpsEntry);\n", "hide FPS topbar"),
]:
    s = replace_once(s, old, "", label)
topbar.write_text(s)

# Hidden features must also be dormant. This prevents an old persisted setting
# from silently remaining enabled after the control disappears.
s = settings.read_text()
s = replace_once(
    s,
    'public class Settings {\n    private final String TAG = "Settings";\n',
    'public class Settings {\n'
    '    public static final String MONO_SETTINGS_POLICY_REVISION = "MONOSETTINGS1A_LEICA_UI_CLEANUP";\n'
    '    private final String TAG = "Settings";\n',
    "settings revision marker",
)
replacements = [
    ("        frameCount = PreferenceKeys.getFrameCountValue();\n",
     "        frameCount = 1; // MONOSETTINGS1A single physical exposure\n",
     "single frame"),
    ("        enhancedProcess = PreferenceKeys.isEnhancedProcessionOn();\n",
     "        enhancedProcess = false; // MONOSETTINGS1A renderer owns processing\n",
     "enhanced processing off"),
    ("        watermark = PreferenceKeys.isShowWatermarkOn();\n",
     "        watermark = false; // MONOSETTINGS1A clean photographic output\n",
     "watermark off"),
    ("        aspect169 = PreferenceKeys.getBool(PreferenceKeys.Key.KEY_WIDE169);\n",
     "        aspect169 = false; // MONOSETTINGS1A native still aspect\n",
     "169 off"),
    ("        binning = PreferenceKeys.isBinningOn();\n",
     "        binning = false; // MONOSETTINGS1A retained in code, dormant until validated\n",
     "binning dormant"),
    ("        roundEdge = PreferenceKeys.isRoundEdgeOn();\n",
     "        roundEdge = false; // MONOSETTINGS1A no presentation crop/mask\n",
     "round edges off"),
    ("        hdrx = PreferenceKeys.isHdrxNrOn();\n",
     "        hdrx = false; // MONOSETTINGS1A no HDR/stacking\n",
     "HDR off"),
    ("        heicSave = PreferenceKeys.isHeicSave();\n",
     "        heicSave = false; // MONOSETTINGS1A JPEG/DNG output only\n",
     "HEIC off"),
    ("        eisPhoto = PreferenceKeys.isEisPhotoOn();\n",
     "        eisPhoto = false; // MONOSETTINGS1A hidden in still UI\n",
     "EIS off"),
    ("        QuadBayer = PreferenceKeys.isQuadBayerOn();\n",
     "        QuadBayer = false; // MONOSETTINGS1A code retained, feature dormant\n",
     "Quad dormant"),
    ("        fpsMode = PreferenceKeys.getFpsMode();\n",
     "        fpsMode = 0; // MONOSETTINGS1A video/FPS surface hidden\n",
     "FPS auto"),
    ("        hdrxNR = PreferenceKeys.isHdrxNrOn();\n",
     "        hdrxNR = false; // MONOSETTINGS1A no HDRX NR\n",
     "HDRX NR off"),
    ("        ultraHdr = PreferenceKeys.isUltraHdrOn();\n",
     "        ultraHdr = false; // MONOSETTINGS1A SDR Leica-style JPEG\n",
     "UltraHDR off"),
]
for old, new, label in replacements:
    s = replace_once(s, old, new, label)
settings.write_text(s)

g = gradle.read_text()
m = re.search(r"versionName\s+'([^']+)'", g)
if not m:
    raise SystemExit("MONOSETTINGS1A versionName missing")
g = g[:m.start(1)] + m.group(1) + "-monosettings1a-leicaui" + g[m.end(1):]
gradle.write_text(g)

frozen_after = {str(p.relative_to(root)): sha(p) for p in frozen if p.exists()}
if frozen_before != frozen_after:
    changed = [k for k in frozen_before if frozen_before[k] != frozen_after.get(k)]
    raise SystemExit("MONOSETTINGS1A photographic seam changed: " + repr(changed))

proof = {
    "revision": "MONOSETTINGS1A_LEICA_UI_CLEANUP",
    "parent": "MONOTAPMETER1B_LOWKEYREAD1A_INTENTBOUNDARY1A",
    "videoSettingsVisible": False,
    "binningCodeRetained": True,
    "binningVisible": False,
    "binningRuntimeEnabled": False,
    "quadBayerCodeRetained": True,
    "quadBayerVisible": False,
    "quadBayerRuntimeEnabled": False,
    "genericPhotonImageTuningVisible": False,
    "heicVisible": False,
    "ultraHdrVisible": False,
    "rawOutputSelectorRetained": True,
    "horizonRetained": True,
    "renderChanged": False,
    "dngPixelMathChanged": False,
    "exposurePlacementChanged": False,
    "curve02Changed": False,
    "frozenPhotographicHashes": frozen_after,
}
(root / "MONOSETTINGS1A_ISOLATION.json").write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
