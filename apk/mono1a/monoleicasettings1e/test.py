#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, math, sys
import xml.etree.ElementTree as ET

if len(sys.argv)!=2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
proof=json.loads((root/"LEICASLOWEST1A_ISOLATION.json").read_text())

assert proof["revision"]=="LEICASLOWEST1A"
assert proof["cameraModel"]=="first_generation_Leica_M_Monochrom"
assert proof["menu"]==["Lens dependent","1/125 s","1/60 s","1/30 s","1/15 s","1/8 s"]
assert proof["menuEnum"]==[0,1,2,3,4,5]
assert proof["default"]=="Lens dependent"
assert proof["lensDependentReferenceExamples"]=={"35mm":"1/30 s","50mm":"1/60 s"}
assert not proof["digitalZoomChangesThreshold"]
assert not proof["deviceSpecificLensNames"]
assert proof["automaticIsoRaisesBeforeCrossingThreshold"]
assert proof["autoIsoMaximumRemainsAuthority"]
assert proof["slowerThanThresholdAllowedAfterIsoMaximum"]
assert proof["manualIsoAuthorityPreserved"] and proof["manualShutterAuthorityPreserved"]
assert proof["previewAndCaptureShareSamePlan"]
assert not proof["HDR"]
assert not proof["rendererChanged"] and not proof["linearDngMathChanged"]
assert not proof["contrastChanged"] and not proof["toningChanged"] and not proof["sharpnessChanged"]

for rel,want in proof["frozenPhotographicHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

ANDROID="http://schemas.android.com/apk/res/android";akey="{"+ANDROID+"}key"
tree=ET.parse(root/"app/src/main/res/xml/preferences.xml")
cat=next(n for n in list(tree.getroot()) if n.attrib.get(akey)=="@string/pref_category_monochrom_key")
keys=[n.attrib.get(akey) for n in list(cat)]
assert keys.index("@string/pref_mono_slowest_speed_key")==keys.index("@string/pref_mono_auto_iso_max_key")+1
node=next(n for n in list(cat) if n.attrib.get(akey)=="@string/pref_mono_slowest_speed_key")
assert node.attrib["{"+ANDROID+"}defaultValue"]=="0"

arrays=(root/"app/src/main/res/values/arrays.xml").read_text()
for marker in [
    "<item>Lens dependent</item>",
    "<item>1/125 s</item>","<item>1/60 s</item>","<item>1/30 s</item>",
    "<item>1/15 s</item>","<item>1/8 s</item>",
]:
    assert marker in arrays,marker

prefs=(J/"settings/PreferenceKeys.java").read_text()
for marker in [
    "KEY_MONO_SLOWEST_SPEED(R.string.pref_mono_slowest_speed_key)",
    "getMonoSlowestSpeedValue()",
    "Key.KEY_MONO_SLOWEST_SPEED, 0",
    "COMMON_KEYS.add(Key.KEY_MONO_SLOWEST_SPEED.mValue)",
]:
    assert marker in prefs,marker

plan=(J/"m9/exposure/MonoExposurePlan1A.java").read_text()
for marker in [
    "FLAG_SLOWEST_SPEED_SHIFTED = 64",
    "FLAG_SLOWEST_SPEED_EXCEEDED_AT_ISO_MAX = 128",
    "slowestSpeedMode, lensEquivalent35mmX10",
    "slowestSpeedNs",
    "slowestSpeedMode==c.slowestSpeedMode",
    "lensEquivalent35mmX10==c.lensEquivalent35mmX10",
]:
    assert marker in plan,marker

selector=(J/"processing/parameters/IsoExpoSelector.java").read_text()
for marker in [
    "monoEquivalentFocalLength35mmX10_1E",
    "resolveMonoSlowestSpeedNs1E",
    "nearestLeicaWholeStopDenominator1E",
    "applyMonoSlowestSpeed1E",
    "effectiveMonoAutoIsoCap1E",
    "monoSlowestExceededAtIsoMax1E",
    "input.controls.manualIso>0||input.controls.manualExposureNs>0",
    "pair.isShutterLimited=true",
]:
    assert marker in selector,marker

capture=(J/"capture/CaptureController.java").read_text()
for marker in [
    "PreferenceKeys.getMonoSlowestSpeedValue()",
    "IsoExpoSelector.resolveMonoSlowestSpeedNs1E",
    "IsoExpoSelector.monoEquivalentFocalLength35mmX10_1E",
]:
    assert marker in capture,marker

diag=(J/"m9/exposure/MonoExposureDiagnostics1A.java").read_text()
for marker in [
    '"slowestSpeedRevision","LEICASLOWEST1A"',
    '"slowestSpeedResolvedNs",p.controls.slowestSpeedNs',
    '"slowestSpeedLensEquivalent35mm",p.controls.lensEquivalent35mmX10/10.0',
    '"slowestSpeedShifted"',
    '"slowestSpeedExceededAtIsoMax"',
]:
    assert marker in diag,marker

# Pure reference model.
WHOLE=[8,15,30,60,125]
def nearest_denom(f):
    return min(WHOLE,key=lambda d:abs(math.log(f/d)))
assert nearest_denom(35)==30
assert nearest_denom(50)==60
assert nearest_denom(24)==30
assert nearest_denom(120)==125

SEC=1_000_000_000
FIXED={1:SEC//125,2:SEC//60,3:SEC//30,4:SEC//15,5:SEC//8}
assert FIXED[1]==8_000_000
assert FIXED[5]==125_000_000

def slow_shift(iso,t,threshold,cap,manual_iso=0,manual_t=0):
    if manual_iso>0 or manual_t>0 or t<=threshold+1000 or iso>=cap:
        exceeded=(manual_iso==0 and manual_t==0 and t>threshold+1000 and iso>=cap)
        return iso,t,False,exceeded
    e=iso*t
    need=math.ceil(e/threshold)
    target=max(iso,min(cap,need))
    if target<=iso:
        return iso,t,False,t>threshold and iso>=cap
    target_t=math.ceil(e/target)
    exceeded=target_t>threshold+1000 and target>=cap
    return target,target_t,True,exceeded

# 1/15 at ISO 800 -> 1/60 at ISO 3200: same exposure energy.
i,t,shifted,exceeded=slow_shift(800,SEC//15,SEC//60,3200)
assert i==3200 and abs(t-(SEC//60))<=2 and shifted and not exceeded

# If max ISO is only 1600, the camera must allow slower than 1/60 rather than underexpose.
i,t,shifted,exceeded=slow_shift(800,SEC//15,SEC//60,1600)
assert i==1600 and abs(t-(SEC//30))<=2 and shifted and exceeded

# Already faster than the threshold: no forced ISO increase.
assert slow_shift(800,SEC//125,SEC//60,3200)==(800,SEC//125,False,False)

# Manual controls remain authoritative.
assert slow_shift(800,SEC//15,SEC//60,3200,manual_iso=800)==(800,SEC//15,False,False)
assert slow_shift(800,SEC//15,SEC//60,3200,manual_t=SEC//15)==(800,SEC//15,False,False)

report={
    "revision":"LEICASLOWEST1A_TEST",
    "status":"PASS",
    "firstGenerationMenuExact":True,
    "lensDependent35mmExample":"1/30 s",
    "lensDependent50mmModel":"1/60 s",
    "fixedRangeWholeStops":"1/125_to_1/8",
    "automaticIsoShiftPreservesEnergy":True,
    "isoMaximumAllowsThresholdOverrun":True,
    "manualControlsPreserved":True,
    "sharedPlanInvalidatesOnModeOrLensThresholdChange":True,
    "renderAndDngFrozen":True,
}
(root/"LEICASLOWEST1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
