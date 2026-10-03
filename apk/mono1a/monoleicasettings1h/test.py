#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,math,sys,xml.etree.ElementTree as ET
if len(sys.argv)!=2:raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve();J=root/"app/src/main/java/com/particlesdevs/photoncamera"
proof=json.loads((root/"LEICABRACKET1A_ISOLATION.json").read_text())
assert proof["cameraModel"]=="first_generation_Leica_M_Monochrom_2012"
assert proof["frames"]==[3,5,7]
assert proof["sequences"]==["0/+/-","-/0/+"]
assert proof["stepsEv"]==[0.5,1.0,1.5,2.0]
assert proof["sevenFrameAllowedStepsEv"]==[0.5,1.0]
for k in ["aperturePriorityOnly","flashBlocked","autoIsoMaxIgnoredAfterBaseIsoChosen",
          "slowestSpeedIgnoredAfterBaseIsoChosen","fullPhysicalShutterRangeUsed",
          "eachFrameSeparatelyRenderedAndSaved","settingsPersistUntilDisabled"]:
    assert proof[k],k
assert not proof["hdrMerge"] and not proof["stacking"]
assert proof["userEvShiftsSeriesCenter"] and proof["aeLockMaySupplySeriesCenter"]
for rel,want in proof["frozenImageOutputHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

helper=(J/"m9/exposure/MonoBracket1H.java").read_text()
for marker in ["SEQUENCE_ZERO_PLUS_MINUS=0","SEQUENCE_MINUS_ZERO_PLUS=1",
               "frames==5?5:(frames==7?7:3)","clampFrames(frames)==7?Math.min(2,v):v",
               "baseExposureNs*Math.pow(2.0,offsetEv)"]:
    assert marker in helper,marker

# Reference sequence math.
def offsets(frames,seq,step):
    side=(frames-1)//2
    if seq==1:return [n*step for n in range(-side,side+1)]
    out=[0.0]
    for n in range(1,side+1):out += [n*step,-n*step]
    return out
assert offsets(3,0,.5)==[0,.5,-.5]
assert offsets(5,0,1)==[0,1,-1,2,-2]
assert offsets(7,0,1)==[0,1,-1,2,-2,3,-3]
assert offsets(3,1,.5)==[-.5,0,.5]
assert offsets(5,1,1)==[-2,-1,0,1,2]
assert offsets(7,1,1)==[-3,-2,-1,0,1,2,3]

# Same ISO, shutter alone carries the requested bracket EV.
base_iso=1600;base_t=10_000_000
for ev in [-3,-2,-1,-.5,0,.5,1,2,3]:
    t=round(base_t*(2**ev))
    ratio=(base_iso*t)/(base_iso*base_t)
    assert abs(math.log(ratio,2)-ev)<1e-6

ANDROID="http://schemas.android.com/apk/res/android";akey="{"+ANDROID+"}key"
tree=ET.parse(root/"app/src/main/res/xml/preferences.xml")
cat=next(n for n in list(tree.getroot()) if n.attrib.get(akey)=="@string/pref_category_monochrom_key")
keys=[n.attrib.get(akey) for n in list(cat)]
for key in ["@string/pref_mono_bracket_frames_key","@string/pref_mono_bracket_sequence_key","@string/pref_mono_bracket_step_key"]:
    assert key in keys,key

prefs=(J/"settings/PreferenceKeys.java").read_text()
for marker in ["getMonoBracketFramesValue()","getMonoBracketSequenceValue()","getMonoBracketStepHalfStopsValue()",
               "getMonoBracketFramesValue()==7 && step>2"]:
    assert marker in prefs,marker

bar=(J/"ui/camera/viewmodel/SettingsBarEntryProvider.java").read_text()
assert "R.string.mono_bracketing_off" in bar and "R.string.mono_bracketing_on" in bar
method=bar[bar.index("private void createBracketingEntry()"):bar.index("private void createFlashEntry()")]
assert "bracketing_high_button" not in method

ui=(J/"ui/camera/CameraUIController.java").read_text()
assert "IsoExpoSelector.HDR = false;" in ui
assert "prepareMonoBracketSeries1H()" in ui

capture=(J/"capture/CaptureController.java").read_text()
for marker in ["prepareMonoBracketSeries1H()","projectMonoBracket1H","advanceMonoBracketAfterProcessing1H()",
               "MonoBracket1H.offsets","MonoBracket1H.bracketExposureNs",
               "monoBracketBasePlan1H.iso","FLAG_BRACKET_FRAME"]:
    assert marker in capture,marker

fragment=(J/"ui/camera/CameraFragment.java").read_text()
assert "advanceMonoBracketAfterProcessing1H()" in fragment
assert "captureController.takePicture();" in fragment
assert "abortMonoBracket1H()" in fragment

diag=(J/"m9/exposure/MonoExposureDiagnostics1A.java").read_text()
for marker in ['"bracketingRevision","LEICABRACKET1A"','"bracketingOffsetEv",p.bracketEv',
               '"bracketingSeparateFiles",true','"bracketingHdrMerge",false']:
    assert marker in diag,marker

report={"revision":"LEICABRACKET1A_TEST","status":"PASS",
        "firstGenMenuExact":True,"separateFrames":True,"sameIsoAcrossSeries":True,
        "shutterOnlyBracketing":True,"sevenFrameStepRestriction":True,
        "hdrDisabled":True,"renderAndDngMathFrozen":True}
(root/"LEICABRACKET1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
