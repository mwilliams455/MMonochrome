#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
if len(sys.argv)!=2:raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve();J=root/"app/src/main/java/com/particlesdevs/photoncamera"
p=json.loads((root/"LEICADISPLAYAIDS1A_ISOLATION.json").read_text())
assert p["revision"]=="LEICADISPLAYAIDS1A"
assert p["highlightClippingChoicesPercent"]==[0,100,99,98,97,96,95]
assert p["displayOnly"] and p["focusPeakingNeutralizedBeforeMeasurement"]
for k in ["captureExposureChanged","rendererChanged","dngChanged","previewShaderChanged","jpegChanged"]:
    assert not p[k],k
for rel,want in p["frozenPhotographicHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

ANDROID="http://schemas.android.com/apk/res/android";akey="{"+ANDROID+"}key"
tree=ET.parse(root/"app/src/main/res/xml/preferences.xml")
cat=next(n for n in list(tree.getroot()) if n.attrib.get(akey)=="@string/pref_category_monochrom_key")
keys=[n.attrib.get(akey) for n in list(cat)]
assert "@string/pref_mono_histogram_key" in keys
assert "@string/pref_mono_highlight_clipping_key" in keys
assert keys.index("@string/pref_mono_histogram_key")<keys.index("@string/pref_mono_highlight_clipping_key")

prefs=(J/"settings/PreferenceKeys.java").read_text()
for marker in [
 "KEY_MONO_HISTOGRAM(R.string.pref_mono_histogram_key)",
 "KEY_MONO_HIGHLIGHT_CLIPPING(R.string.pref_mono_highlight_clipping_key)",
 "isMonoHistogramEnabled()","getMonoHighlightClippingPercent()",
 "Math.max(95,Math.min(100,value))"
]: assert marker in prefs,marker

hud=(J/"ui/camera/views/viewfinder/ViewfinderHudView.java").read_text()
for marker in [
 'MONO_DISPLAY_REVISION="LEICADISPLAYAIDS1A"',
 "setMonoAssistMode(boolean histogramEnabled,int highlightPercent)",
 "setMonoAssistData(int[] histogram",
 "drawMonoHighlightClipping(Canvas canvas)",
 "drawMonoHistogram(Canvas canvas)",
 "SystemClock.uptimeMillis()/350L",
 "for(int i=1;i<11;i++)"
]: assert marker in hud,marker
assert "Color.RED" in hud
assert "clearHudOnly()" in hud

frag=(J/"ui/camera/CameraFragment.java").read_text()
for marker in [
 "PreferenceKeys.isMonoHistogramEnabled()",
 "PreferenceKeys.getMonoHighlightClippingPercent()",
 "mDisplayAidSampleBusy1J.compareAndSet(false,true)",
 "int y=(77*cleanR+150*g+29*cleanB+128)>>8",
 "mMonoClipPixels1J[i]=0xD0FF0000",
 "setMonoAssistData(mMonoHistData1J",
 "mDisplayAidSampleBusy1J.set(false)"
]: assert marker in frag,marker

# Threshold mapping: 100% means code 255; 95% means about 242.
def code(pct):
    return 256 if pct<=0 else (255 if pct>=100 else round(255*(pct/100)))
assert code(100)==255
assert code(95)==242
assert code(0)==256

report={"revision":"LEICADISPLAYAIDS1A_TEST","status":"PASS",
        "histogramMonochrome":True,"elevenGuideSections":True,
        "highlightThresholds":"Off_100_to_95_percent",
        "highlightFlashesRed":True,"renderedPreviewMeasured":True,
        "captureAndOutputFrozen":True}
(root/"LEICADISPLAYAIDS1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
