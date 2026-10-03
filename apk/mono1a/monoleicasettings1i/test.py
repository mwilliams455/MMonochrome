#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
if len(sys.argv)!=2:raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve();J=root/"app/src/main/java/com/particlesdevs/photoncamera"
p=json.loads((root/"LEICATIMER1A_ISOLATION.json").read_text())
assert p["choicesSeconds"]==[0,2,12]
assert p["labels"]==["Off","2s","12s"]
assert p["defaultSeconds"]==0
for k in ["sameExistingCountdownScheduler","shutterStartsAfterCountdown",
          "bracketingStartsAfterCountdown","bracketTimerAppliedOnceToSeries"]:
    assert p[k],k
assert not p["captureControllerChanged"] and not p["exposurePlanChanged"]
assert not p["rendererChanged"] and not p["dngPixelMathChanged"]
for rel,want in p["frozenPhotographicHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

arrays=(root/"app/src/main/res/values/arrays.xml").read_text()
block=arrays[arrays.index('<integer-array name="countdowntimer_entryvalues">'):
             arrays.index('</integer-array>',arrays.index('<integer-array name="countdowntimer_entryvalues">'))]
assert "<item>0</item>" in block and "<item>2</item>" in block and "<item>12</item>" in block
assert "<item>3</item>" not in block and "<item>10</item>" not in block

strings=(root/"app/src/main/res/values/strings.xml").read_text()
assert '<string name="t_2s">2s</string>' in strings
assert '<string name="t_12s">12s</string>' in strings

attrs=(root/"app/src/main/res/values/attrs.xml").read_text()
assert 'name="timer_2s"' in attrs and 'name="timer_12s"' in attrs
timer=(J/"ui/camera/views/TimerButton.java").read_text()
for marker in ["STATE_TIMER_2S","STATE_TIMER_12S","timer_2s = true","timer_12s = true"]:
    assert marker in timer,marker
assert "STATE_TIMER_3S" not in timer and "STATE_TIMER_10S" not in timer

selector=(root/"app/src/main/res/drawable/ic_timer.xml").read_text()
assert '@drawable/ic_timer2s_mono' in selector and 'app:timer_2s="true"' in selector
assert '@drawable/ic_timer12s_mono' in selector and 'app:timer_12s="true"' in selector
assert (root/"app/src/main/res/drawable/ic_timer2s_mono.xml").is_file()
assert (root/"app/src/main/res/drawable/ic_timer12s_mono.xml").is_file()

bar=(J/"ui/camera/viewmodel/SettingsBarEntryProvider.java").read_text()
start=bar.index("private void createTimerEntry()")
brace=bar.index("{",start);depth=0;end=None
for i in range(brace,len(bar)):
    if bar[i]=="{":depth+=1
    elif bar[i]=="}":
        depth-=1
        if depth==0:
            end=i+1;break
assert end is not None
method=bar[start:end]
assert "R.string.t_2s" in method and "R.string.t_12s" in method
assert "R.string.t_3s" not in method and "R.string.t_10s" not in method

ui=(J/"ui/camera/CameraUIController.java").read_text()
# Existing scheduler reads the actual seconds from countdowntimer_entryvalues and multiplies by 1000.
assert "getTimerValue(this.shutterButton.getContext()) * 1000L" in ui
# Bracketing preparation occurs only after timer completion, therefore timer is one delay before the whole series.
finish=ui[ui.index("private void onTimerFinished()"):ui.index("@Override",ui.index("private void onTimerFinished()"))]
assert finish.index("prepareMonoBracketSeries1H()") < finish.index("captureController.takePicture()")

report={"revision":"LEICATIMER1A_TEST","status":"PASS",
        "choices":"Off_2s_12s","existingSchedulerReused":True,
        "bracketSeriesDelayedOnceBeforeFrame1":True,
        "photographicPipelineFrozen":True}
(root/"LEICATIMER1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
