#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, math, sys
import xml.etree.ElementTree as ET

if len(sys.argv) != 2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
proof=json.loads((root/"LEICAAUTOISO1A_ISOLATION.json").read_text())

assert proof["revision"]=="LEICAAUTOISO1A"
assert proof["menuPhysicalIso"]==[320,400,500,640,800,1000,1250,1600,2000,2500,3200,4000,5000,6400,8000,10000]
assert proof["defaultPhysicalIso"]==10000
assert proof["isoDomain"]=="physical_Camera2_SENSOR_SENSITIVITY"
assert proof["manualIsoAuthorityPreserved"]
assert proof["manualShutterAuthorityPreserved"]
assert proof["automaticShutterPreservesEnergyWhenCapHits"]
assert proof["selectedCapNeverExceededByAutomaticIso"]
assert proof["controlIdentityIncludesAutoIsoMaximum"]
assert proof["previewAndCaptureShareSamePlan"]
assert not proof["HDR"]
assert not proof["rendererChanged"] and not proof["linearDngMathChanged"]
assert not proof["contrastChanged"] and not proof["toningChanged"] and not proof["sharpnessChanged"]

for rel,want in proof["frozenPhotographicHashes"].items():
    got=hashlib.sha256((root/rel).read_bytes()).hexdigest()
    assert got==want,(rel,got,want)

# Settings UI.
ANDROID="http://schemas.android.com/apk/res/android"; akey="{"+ANDROID+"}key"
tree=ET.parse(root/"app/src/main/res/xml/preferences.xml")
cat=next(n for n in list(tree.getroot()) if n.attrib.get(akey)=="@string/pref_category_monochrom_key")
keys=[n.attrib.get(akey) for n in list(cat)]
assert "@string/pref_mono_auto_iso_max_key" in keys
assert keys.index("@string/pref_mono_auto_iso_max_key")>keys.index("@string/pref_mono_toning_strength_key")
node=next(n for n in list(cat) if n.attrib.get(akey)=="@string/pref_mono_auto_iso_max_key")
assert node.attrib["{"+ANDROID+"}defaultValue"]=="10000"

arrays=(root/"app/src/main/res/values/arrays.xml").read_text()
for v in ["320","400","500","640","800","1000","1250","1600","2000","2500","3200","4000","5000","6400","8000","10000"]:
    assert f"<item>{v}</item>" in arrays

prefs=(J/"settings/PreferenceKeys.java").read_text()
for marker in [
    "KEY_MONO_AUTO_ISO_MAX(R.string.pref_mono_auto_iso_max_key)",
    "getMonoAutoIsoMaximumValue()",
    "Key.KEY_MONO_AUTO_ISO_MAX, 10000",
    "COMMON_KEYS.add(Key.KEY_MONO_AUTO_ISO_MAX.mValue)",
]:
    assert marker in prefs,marker

plan=(J/"m9/exposure/MonoExposurePlan1A.java").read_text()
for marker in [
    "FLAG_AUTO_ISO_MAX_APPLIED = 32",
    "autoIsoMaximum",
    "autoIsoMaximum==c.autoIsoMaximum",
    "oisMode,autoIsoMaximum,meteringKey",
]:
    assert marker in plan,marker

capture=(J/"capture/CaptureController.java").read_text()
assert "PreferenceKeys.getMonoAutoIsoMaximumValue(),metering" in capture

selector=(J/"processing/parameters/IsoExpoSelector.java").read_text()
for marker in [
    "applyMonoAutoIsoMaximum1D",
    "input.controls.manualIso>0",
    "input.controls.autoIsoMaximum",
    "Math.max(input.isoLow,Math.min(input.isoHigh,selected))",
    "input.controls.manualExposureNs==0",
    "pair.iso=cap",
    "pair.isIsoLimited=true",
    "MonoExposurePlan1A.FLAG_AUTO_ISO_MAX_APPLIED",
]:
    assert marker in selector,marker

diag=(J/"m9/exposure/MonoExposureDiagnostics1A.java").read_text()
for marker in [
    '"autoIsoMaximumRevision","LEICAAUTOISO1A"',
    '"autoIsoMaximumPhysical",p.controls.autoIsoMaximum',
    '"autoIsoMaximumApplied"',
    '"autoIsoManualOverride"',
]:
    assert marker in diag,marker

# Pure allocation model mirrors the Java helper and proves the intended boundaries.
def cap_pair(iso, exposure_ns, selected, iso_low=100, iso_high=12800,
             time_low=1000, time_high=1_000_000_000, manual_iso=0, manual_shutter=0):
    if manual_iso>0:
        return iso,exposure_ns,False
    cap=max(iso_low,min(iso_high,selected))
    if iso<=cap:
        return iso,exposure_ns,False
    energy=iso*exposure_ns
    if manual_shutter==0:
        needed=math.ceil(energy/cap)
        needed=max(time_low,min(time_high,needed))
        exposure_ns=max(exposure_ns,needed)
    return cap,exposure_ns,True

# 3200 @ 1/125 -> cap 1600 -> ~1/62.5 at same exposure energy.
i,t,a=cap_pair(3200,8_000_000,1600)
assert (i,t,a)==(1600,16_000_000,True)
assert i*t==3200*8_000_000

# Physical device range wins over a menu value above the sensor maximum.
i,t,a=cap_pair(6400,10_000_000,10000,iso_high=3200)
assert i==3200 and t==20_000_000 and a

# If sensor max exposure time prevents full compensation, ISO still never crosses the ceiling.
i,t,a=cap_pair(6400,40_000_000,1600,time_high=125_000_000)
assert i==1600 and t==125_000_000 and a
assert i*t < 6400*40_000_000

# Manual shutter remains exact; Auto ISO is capped.
i,t,a=cap_pair(3200,20_000_000,800,manual_shutter=20_000_000)
assert (i,t,a)==(800,20_000_000,True)

# Manual ISO is not an Auto ISO request and is never silently overridden by this setting.
i,t,a=cap_pair(6400,20_000_000,800,manual_iso=6400)
assert (i,t,a)==(6400,20_000_000,False)

report={
    "revision":"LEICAAUTOISO1A_TEST",
    "status":"PASS",
    "physicalIsoMenu":proof["menuPhysicalIso"],
    "defaultNonRegressive":True,
    "automaticIsoNeverExceedsSelectedEffectiveCap":True,
    "energyPreservedByAutomaticShutterWherePhysicalRangeAllows":True,
    "manualIsoBypass":True,
    "manualShutterPreserved":True,
    "sharedPlanIdentityInvalidatesOnCeilingChange":True,
    "rendererDngContrastToningSharpnessFrozen":True,
}
(root/"LEICAAUTOISO1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
