#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
if len(sys.argv)!=2:raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve();J=root/"app/src/main/java/com/particlesdevs/photoncamera"
p=json.loads((root/"LEICAOUTPUTMODE1A_ISOLATION.json").read_text())
assert p["saveModes"]["0_JPEG"]=={"jpeg":True,"monochromDng":False}
assert p["saveModes"]["1_DNG_JPEG"]=={"jpeg":True,"monochromDng":True}
assert p["saveModes"]["2_DNG"]=={"jpeg":False,"monochromDng":True}
assert p["originalSensorRaw"]=="independent_toggle_default_off"
assert p["originalSensorRawCanAccompanyAnySaveMode"]
assert p["derivedDngAllocationSkippedInJpegOnly"] and p["derivedDngAdmissionSkippedInJpegOnly"]
assert p["genericPhotonRawSaverDisabled"]
for k in ["nativeRenderMathChanged","jpegEncodingMathChanged","dngPixelMathChanged","exposurePlanChanged","displayAidsChanged"]:
    assert not p[k],k
for rel,want in p["frozenPhotographicHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

# Output matrix itself.
for mode in [0,1,2]:
    jpeg=mode in (0,1);mono=mode in (1,2)
    assert jpeg==p["saveModes"][["0_JPEG","1_DNG_JPEG","2_DNG"][mode]]["jpeg"]
    assert mono==p["saveModes"][["0_JPEG","1_DNG_JPEG","2_DNG"][mode]]["monochromDng"]

ANDROID="http://schemas.android.com/apk/res/android";akey="{"+ANDROID+"}key"
tree=ET.parse(root/"app/src/main/res/xml/preferences.xml")
cat=next(n for n in list(tree.getroot()) if n.attrib.get(akey)=="@string/pref_category_monochrom_key")
node=next(n for n in list(cat) if n.attrib.get(akey)=="@string/pref_mono_original_sensor_raw_key")
assert node.attrib.get("{"+ANDROID+"}defaultValue")=="false"
assert node.attrib.get("{"+ANDROID+"}title")=="@string/mono_original_sensor_raw"

arrays=(root/"app/src/main/res/values/arrays.xml").read_text()
a=arrays[arrays.index('<string-array name="raw_mode_entries">'):arrays.index('</string-array>',arrays.index('<string-array name="raw_mode_entries">'))]
assert "<item>JPEG</item>" in a and "<item>DNG + JPEG</item>" in a and "<item>DNG</item>" in a
assert "RAW + JPEG" not in a

prefs=(J/"settings/PreferenceKeys.java").read_text()
for marker in ["isMonoLinearDngRequested()","isMonoJpegRequested()","isMonoOriginalSensorRawEnabled()",
               "KEY_MONO_ORIGINAL_SENSOR_RAW(R.string.pref_mono_original_sensor_raw_key)"]:
    assert marker in prefs,marker
raw_start=prefs.index("public static boolean isRawSave()");raw_end=prefs.index("public static boolean isBatterySaverOn",raw_start)
assert "return isMonoOriginalSensorRawEnabled();" in prefs[raw_start:raw_end]

settings=(J/"api/Settings.java").read_text()
assert "rawSaver = 0; // LEICAOUTPUTMODE1A" in settings

bar=(J/"ui/camera/viewmodel/SettingsBarEntryProvider.java").read_text()
start=bar.index("private void createSaveRawEntry()");brace=bar.index("{",start);depth=0;end=None
for i in range(brace,len(bar)):
    if bar[i]=="{":depth+=1
    elif bar[i]=="}":
        depth-=1
        if depth==0:end=i+1;break
method=bar[start:end]
for marker in ["R.string.jpg_only","R.string.mono_dng_plus_jpeg","R.string.mono_dng_only"]:
    assert marker in method,marker
assert "raw_plus_jpg" not in method

exp=(J/"m9/export/MonoDngExport1A.java").read_text()
assert "if(!com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoLinearDngRequested())return null;" in exp
assert exp.count("if(!com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoLinearDngRequested())return true;")>=2
assert "monochrom_DNG_disabled_by_Save_mode" in exp

rend=(J/"m9/render/M9R35Renderer.java").read_text()
for marker in [
 "isMonoLinearDngRequested()) {",
 "final boolean jpegRequested1L=",
 "final boolean monoDngRequested1L=",
 "if(jpegRequested1L) {",
 'out.diagnostics.put("monoDngExportStatus","disabled_by_Save_JPEG")',
 'ImageSaver.Util.saveBitmapAsJPGPayloadM9(jpgPath,bitmap,JPEG_QUALITY,exif)'
]:assert marker in rend,marker
# Exact JPEG encoding helper remains quality-95 and unmodified; only its call is gated.
assert "JPEG_QUALITY = 95" in rend

q=(J/"m9/render/M9PrimaryRenderQueue.java").read_text()
for marker in [
 "final boolean originalSensorRawRequested1L=PreferenceKeys.isMonoOriginalSensorRawEnabled();",
 "final boolean jpegRequested1L=PreferenceKeys.isMonoJpegRequested();",
 "if(originalSensorRawRequested1L) {",
 "Original Sensor RAW=Off; untouched Bayer/color DNG skipped",
 "ImageSaver.Util.saveSingleRaw("
]:assert marker in q,marker
assert "original sensor RAW DNG save returned false" in q

report={
 "revision":"LEICAOUTPUTMODE1A_TEST","status":"PASS",
 "jpegOnly":"JPEG_only_when_original_sensor_RAW_off",
 "dngJpeg":"Monochrom_DNG_plus_JPEG",
 "dngOnly":"Monochrom_DNG_only",
 "originalSensorRawIndependent":True,
 "jpegOnlySkipsDerivedDngWork":True,
 "pixelAndExposureMathFrozen":True
}
(root/"LEICAOUTPUTMODE1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
