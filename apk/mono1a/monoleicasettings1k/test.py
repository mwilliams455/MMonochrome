#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET

if len(sys.argv)!=2:raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve();J=root/"app/src/main/java/com/particlesdevs/photoncamera"
p=json.loads((root/"LEICAUICLEANUP1A_ISOLATION.json").read_text())
assert p["revision"]=="LEICAUICLEANUP1A"
assert not p["developerAdvancedVisible"] and not p["sensorConfigVisible"]
assert not p["deviceTuningFetchVisible"] and not p["genericAeMeteringVisible"]
assert p["genericAeMeteringRuntime"]=="forced_neutral_default_-1"
assert not p["genericPhotonImageTuningVisible"] and not p["genericDebugHudVisible"]
assert p["quickSettingsVisible"]==["Flash","Self timer","Save","Grid","Bracketing"]
assert not p["quickBatterySaverVisible"]
assert p["batterySaverStillAvailableInGeneralSettings"]
assert p["saveQuickTitle"]=="Save"
for k in ["leicaCategoryPreserved","themePreserved","backupRestorePreserved","aboutPreserved","generalSettingsPreserved"]:
    assert p[k],k
for k in ["exposurePlanChanged","rendererChanged","dngChanged","displayAidsChanged","previewShaderChanged"]:
    assert not p[k],k
for rel,want in p["frozenPhotographicHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

ANDROID="http://schemas.android.com/apk/res/android";akey="{"+ANDROID+"}key"
tree=ET.parse(root/"app/src/main/res/xml/preferences.xml");screen=tree.getroot()
keys=[]
def collect(n):
    k=n.attrib.get(akey,"")
    if k:keys.append(k)
    for c in list(n):collect(c)
collect(screen)

for forbidden in [
 "@string/pref_category_advanced_key","@string/pref_category_device_key",
 "@string/pref_show_afdata_key","@string/pref_cfa_key","@string/pref_preview_format_key",
 "@string/pref_remosaic_key","@string/pref_align_method_key","@string/pref_color_method_key",
 "@string/pref_ae_metering_std_key","@string/pref_expocompensation_seekbar_key",
 "@string/pref_frame_count_key","@string/pref_noise_seekbar_key","@string/pref_merge_seekbar_key",
 "@string/pref_shadows_seekbar_key","@string/pref_compressor_seekbar_key",
 "@string/pref_gain_seekbar_key","@string/pref_contrast_seekbar_key",
 "@string/pref_saturation_seekbar_key","@string/pref_sharpness_seekbar_key"
]: assert forbidden not in keys,forbidden

for retained in [
 "@string/pref_category_general_key","@string/pref_category_monochrom_key",
 "@string/pref_theme_category_key","@string/pref_category_backup_restore","@string/pref_category_about_key"
]: assert retained in keys,retained

bar=(J/"ui/camera/viewmodel/SettingsBarEntryProvider.java").read_text()
ctor=bar[bar.index("public SettingsBarEntryProvider()"):bar.index("public void createEntries()")]
for visible in [
 "allEntries.add(flashEntry);","allEntries.add(timerEntry);","allEntries.add(saveRawEntry);",
 "allEntries.add(gridEntry);","allEntries.add(bracketingEntry);"
]: assert visible in ctor,visible
for hidden in ["allEntries.add(batterySaverEntry);","allEntries.add(aeMeteringStdEntry);",
               "allEntries.add(quadEntry);","allEntries.add(eisEntry);","allEntries.add(fpsEntry);"]:
    assert hidden not in ctor,hidden
assert "R.id.saveraw_entry_layout, R.string.raw, SettingType.RAW" in bar

prefs=(J/"settings/PreferenceKeys.java").read_text()
start=prefs.index("public static int getAeMeteringStd()")
end=prefs.index("public static void setAeMeteringStd",start)
method=prefs[start:end]
assert "return -1;" in method
assert "getInteger(SCOPE_GLOBAL, Key.KEY_AE_METERING_STD)" not in method

report={
 "revision":"LEICAUICLEANUP1A_TEST",
 "status":"PASS",
 "shootingBar":"Flash_Timer_Save_Grid_Bracketing",
 "genericAeMeteringHiddenAndNeutral":True,
 "developerSensorTuningHidden":True,
 "genericPhotonProcessingControlsHidden":True,
 "photographicPipelineFrozen":True
}
(root/"LEICAUICLEANUP1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
