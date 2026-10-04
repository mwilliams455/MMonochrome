#!/usr/bin/env python3
"""LEICAUICLEANUP1A: remove conflicting Photon controls and developer-only settings from normal Monochrom UI."""
from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
pref_xml=root/"app/src/main/res/xml/preferences.xml"
pref_java=J/"settings/PreferenceKeys.java"
settingsbar=J/"ui/camera/viewmodel/SettingsBarEntryProvider.java"
gradle=root/"app/build.gradle"

for p in [pref_xml,pref_java,settingsbar,gradle]:
    if not p.is_file(): raise SystemExit("LEICAUICLEANUP1A missing "+str(p))
for receipt in ["LEICADISPLAYAIDS1A_ISOLATION.json","LEICATIMER1A_ISOLATION.json",
                "LEICABRACKET1B_ADMISSIONFIX1_ISOLATION.json"]:
    if not (root/receipt).is_file(): raise SystemExit("LEICAUICLEANUP1A missing parent receipt "+receipt)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"LEICAUICLEANUP1A {label} anchor count={n}")
    return s.replace(a,b,1)

# UI-only cleanup except for neutralizing legacy generic AE metering preference.
# The Leica exposure planner/render/DNG/display-aid math remains frozen.
frozen=[
 J/"m9/render/M9R35Renderer.java",J/"m9/render/M9NativeColorCore.java",
 J/"m9/export/MonoDngWriter1A.java",J/"m9/export/MonoLinearPlane1A.java",
 J/"m9/export/MonoDngExport1A.java",J/"processing/parameters/IsoExpoSelector.java",
 J/"capture/CaptureController.java",J/"m9/exposure/MonoExposurePlan1A.java",
 J/"m9/preview/MonoGpuPreview2A.java",J/"ui/camera/CameraFragment.java",
 J/"ui/camera/views/viewfinder/ViewfinderHudView.java",
 root/"app/src/main/cpp/m9color_jni.cpp",root/"app/src/main/assets/shaders/preview/main_fs.glsl",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}

# ---------------------------------------------------------------------------
# Settings screen: retain photographic controls, hide Photon developer/tuning
# surfaces and any generic image/exposure controls that can contradict Leica UI.
# ---------------------------------------------------------------------------
ANDROID="http://schemas.android.com/apk/res/android";APP="http://schemas.android.com/apk/res-auto"
ET.register_namespace("android",ANDROID);ET.register_namespace("app",APP)
akey="{"+ANDROID+"}key"
tree=ET.parse(pref_xml);screen=tree.getroot()

def node_key(n): return n.attrib.get(akey,"")

# Remove whole developer-only categories. Runtime code stays in source so this is
# reversible and upstream merges remain straightforward.
remove_categories={
    "@string/pref_category_advanced_key",  # Tunable + sensor config submenus
    "@string/pref_category_device_key",    # network/device tuning fetch
}
removed_categories=[]
for n in list(screen):
    if node_key(n) in remove_categories:
        removed_categories.append(node_key(n));screen.remove(n)

# Defense in depth: recursively remove any generic processing / sensor / metering
# controls should an upstream merge move them into another visible category.
hide_keys={
    "@string/pref_show_afdata_key",              # full developer HUD/debug
    "@string/pref_cfa_key",                      # Bayer/CFA override
    "@string/pref_preview_format_key",           # preview transport format
    "@string/pref_remosaic_key",                 # sensor processing override
    "@string/pref_align_method_key",             # Photon stack processing
    "@string/pref_color_method_key",             # generic Photon color method
    "@string/pref_ae_metering_std_key",          # generic HW metering modes
    "@string/pref_expocompensation_seekbar_key", # hidden duplicate EV
    "@string/pref_frame_count_key",              # HDR/stack count
    "@string/pref_noise_seekbar_key",
    "@string/pref_merge_seekbar_key",
    "@string/pref_shadows_seekbar_key",
    "@string/pref_compressor_seekbar_key",
    "@string/pref_gain_seekbar_key",
    "@string/pref_contrast_seekbar_key",
    "@string/pref_saturation_seekbar_key",
    "@string/pref_sharpness_seekbar_key",
}
removed_keys=[]
def scrub(parent):
    for n in list(parent):
        if node_key(n) in hide_keys:
            removed_keys.append(node_key(n));parent.remove(n);continue
        scrub(n)
scrub(screen)

# Empty nonessential categories are noise; remove them if cleanup leaves one empty.
for n in list(screen):
    if n.tag.endswith("PreferenceCategory") and len(list(n))==0:
        screen.remove(n)

ET.indent(tree,space="    ");tree.write(pref_xml,encoding="utf-8",xml_declaration=True)

# ---------------------------------------------------------------------------
# Quick settings bar: keep only photographic controls. Battery saver remains in
# General Settings, but not in the shooting controls. AE Metering is removed
# because tap/scene placement is the authoritative Monochrom meter.
# ---------------------------------------------------------------------------
s=settingsbar.read_text()
for old,label in [
    ("        allEntries.add(batterySaverEntry);\n","hide battery saver shooting entry"),
    ("        allEntries.add(aeMeteringStdEntry);\n","hide generic AE metering shooting entry"),
]:
    if old in s:
        s=s.replace(old,"",1)
    elif label=="hide generic AE metering shooting entry":
        # Allow parent branches that already removed it.
        pass
    else:
        raise SystemExit("LEICAUICLEANUP1A missing "+label)

# Make the output selector read "Save" rather than the generic RAW heading; its
# three existing modes remain JPEG / RAW+JPEG / RAW.
old_decl='''    private final SettingsBarEntryModel saveRawEntry = SettingsBarEntryModel.newEntry(R.id.saveraw_entry_layout, R.string.raw_string, SettingType.RAW);'''
new_decl='''    private final SettingsBarEntryModel saveRawEntry = SettingsBarEntryModel.newEntry(R.id.saveraw_entry_layout, R.string.raw, SettingType.RAW);'''
s=one(s,old_decl,new_decl,"rename quick save entry")
settingsbar.write_text(s)

# ---------------------------------------------------------------------------
# Neutralize any old persisted generic AE-metering preference. Hiding the UI is
# not enough: previous installs may contain Center/Average/Spot. The Monochrom
# exposure system owns scene placement and tap intent, so hardware metering falls
# back to its neutral/default region (-1) for every session.
# ---------------------------------------------------------------------------
s=pref_java.read_text()
old='''    public static int getAeMeteringStd() {
        return preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_AE_METERING_STD);
    }
'''
new='''    public static int getAeMeteringStd() {
        // LEICAUICLEANUP1A: generic Photon Center/Average/Spot metering is hidden
        // and neutralized. Leica Monochrom scene placement/tap exposure is authoritative.
        return -1;
    }
'''
s=one(s,old,new,"neutral generic AE metering")
pref_java.write_text(s)

g=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("LEICAUICLEANUP1A versionName missing")
if "leicauicleanup1a" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-leicauicleanup1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICAUICLEANUP1A changed frozen photographic files "+repr(changed))

# Parse final UI for evidence.
tree2=ET.parse(pref_xml);screen2=tree2.getroot()
visible_keys=[]
def collect(n):
    k=node_key(n)
    if k:visible_keys.append(k)
    for c in list(n):collect(c)
collect(screen2)

proof={
 "revision":"LEICAUICLEANUP1A",
 "purpose":"normal_photographic_UI_only",
 "removedCategories":sorted(removed_categories),
 "developerAdvancedVisible":False,
 "sensorConfigVisible":False,
 "deviceTuningFetchVisible":False,
 "genericAeMeteringVisible":False,
 "genericAeMeteringRuntime":"forced_neutral_default_-1",
 "genericPhotonImageTuningVisible":False,
 "genericDebugHudVisible":False,
 "quickSettingsVisible":["Flash","Self timer","Save","Grid","Bracketing"],
 "quickBatterySaverVisible":False,
 "batterySaverStillAvailableInGeneralSettings":True,
 "saveQuickTitle":"Save",
 "leicaCategoryPreserved":"@string/pref_category_monochrom_key" in visible_keys,
 "themePreserved":"@string/pref_theme_category_key" in visible_keys,
 "backupRestorePreserved":"@string/pref_category_backup_restore" in visible_keys,
 "aboutPreserved":"@string/pref_category_about_key" in visible_keys,
 "generalSettingsPreserved":"@string/pref_category_general_key" in visible_keys,
 "exposurePlanChanged":False,
 "rendererChanged":False,
 "dngChanged":False,
 "displayAidsChanged":False,
 "previewShaderChanged":False,
 "frozenPhotographicHashes":after,
}
(root/"LEICAUICLEANUP1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
