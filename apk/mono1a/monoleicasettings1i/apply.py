#!/usr/bin/env python3
"""LEICATIMER1A: first-generation Leica M Monochrom self-timer Off / 2 s / 12 s."""
from pathlib import Path
import hashlib,json,re,sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
arrays=root/"app/src/main/res/values/arrays.xml"
strings=root/"app/src/main/res/values/strings.xml"
attrs=root/"app/src/main/res/values/attrs.xml"
settingsbar=J/"ui/camera/viewmodel/SettingsBarEntryProvider.java"
timerbutton=J/"ui/camera/views/TimerButton.java"
timerselector=root/"app/src/main/res/drawable/ic_timer.xml"
icon2=root/"app/src/main/res/drawable/ic_timer2s_mono.xml"
icon12=root/"app/src/main/res/drawable/ic_timer12s_mono.xml"
gradle=root/"app/build.gradle"

for p in [arrays,strings,attrs,settingsbar,timerbutton,timerselector,gradle]:
    if not p.is_file():raise SystemExit("LEICATIMER1A missing "+str(p))
for receipt in ["LEICABRACKET1B_ADMISSIONFIX1_ISOLATION.json","LEICABRACKET1A_ISOLATION.json"]:
    if not (root/receipt).is_file():raise SystemExit("LEICATIMER1A missing parent receipt "+receipt)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1:raise SystemExit(f"LEICATIMER1A {label} anchor count={n}")
    return s.replace(a,b,1)

# Photographic pipeline stays completely frozen: timer is UI scheduling only.
frozen=[
 J/"m9/render/M9R35Renderer.java",J/"m9/render/M9NativeColorCore.java",
 J/"m9/export/MonoDngWriter1A.java",J/"m9/export/MonoLinearPlane1A.java",
 J/"processing/parameters/IsoExpoSelector.java",J/"capture/CaptureController.java",
 J/"m9/exposure/MonoExposurePlan1A.java",J/"m9/preview/MonoGpuPreview2A.java",
 root/"app/src/main/cpp/m9color_jni.cpp",root/"app/src/main/assets/shaders/preview/main_fs.glsl",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}

# Physical countdown values.
s=arrays.read_text()
s=one(s,
'''    <integer-array name="countdowntimer_entryvalues">
        <item>0</item>
        <item>3</item>
        <item>10</item>
    </integer-array>''',
'''    <integer-array name="countdowntimer_entryvalues">
        <item>0</item>
        <item>2</item>
        <item>12</item>
    </integer-array>''',
"timer values 0/2/12")
arrays.write_text(s)

# New visible labels. Keep old strings for translation/source compatibility, but stop using them.
s=strings.read_text()
anchor='''    <string name="t_3s">3s</string>
    <string name="t_10s">10s</string>
'''
s=one(s,anchor,anchor+'''    <string name="t_2s">2s</string>
    <string name="t_12s">12s</string>
''',"timer labels")
strings.write_text(s)

# Rename drawable states so code now tells the truth about the timer semantics.
s=attrs.read_text()
s=one(s,
'''    <declare-styleable name="TimerButtonStates">
        <attr name="timer_off" format="boolean"/>
        <attr name="timer_3s" format="boolean"/>
        <attr name="timer_10s" format="boolean"/>
    </declare-styleable>''',
'''    <declare-styleable name="TimerButtonStates">
        <attr name="timer_off" format="boolean"/>
        <attr name="timer_2s" format="boolean"/>
        <attr name="timer_12s" format="boolean"/>
    </declare-styleable>''',
"timer drawable attrs")
attrs.write_text(s)

# Minimal monochrome timer icons with numerals 2 and 12.
icon2.write_text('''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#00000000" android:strokeColor="#FFFFFFFF"
        android:strokeWidth="1.8" android:strokeLineCap="round"
        android:pathData="M12,5 A8,8 0,1 1,11.99,5 M9.5,2.5 L14.5,2.5 M16.8,4.2 L18.3,2.7"/>
    <path android:fillColor="#00000000" android:strokeColor="#FFFFFFFF"
        android:strokeWidth="1.8" android:strokeLineCap="round" android:strokeLineJoin="round"
        android:pathData="M9.2,10 C9.2,8.8 10.2,8 11.8,8 C13.5,8 14.6,8.9 14.6,10.2 C14.6,11.5 13.6,12.3 12.3,13.2 L9.4,15.6 L14.8,15.6"/>
</vector>
''')
icon12.write_text('''<?xml version="1.0" encoding="utf-8"?>
<vector xmlns:android="http://schemas.android.com/apk/res/android"
    android:width="24dp" android:height="24dp"
    android:viewportWidth="24" android:viewportHeight="24">
    <path android:fillColor="#00000000" android:strokeColor="#FFFFFFFF"
        android:strokeWidth="1.8" android:strokeLineCap="round"
        android:pathData="M12,5 A8,8 0,1 1,11.99,5 M9.5,2.5 L14.5,2.5 M16.8,4.2 L18.3,2.7"/>
    <path android:fillColor="#00000000" android:strokeColor="#FFFFFFFF"
        android:strokeWidth="1.55" android:strokeLineCap="round" android:strokeLineJoin="round"
        android:pathData="M8.3,9 L9.7,8 L9.7,16 M11.4,10 C11.4,8.8 12.3,8 13.8,8 C15.3,8 16.3,8.9 16.3,10.1 C16.3,11.3 15.5,12 14.3,12.9 L11.6,15.4 L16.5,15.4"/>
</vector>
''')

s=timerselector.read_text()
s=one(s,
'''        <item android:drawable="@drawable/ic_timer3s" app:timer_3s="true" />
        <item android:drawable="@drawable/ic_timer10s" app:timer_10s="true" />
''',
'''        <item android:drawable="@drawable/ic_timer2s_mono" app:timer_2s="true" />
        <item android:drawable="@drawable/ic_timer12s_mono" app:timer_12s="true" />
''',
"timer selector")
timerselector.write_text(s)

s=timerbutton.read_text()
s=one(s,
'''    private static final int[] STATE_TIMER_3S = {R.attr.timer_3s};
    private static final int[] STATE_TIMER_10S = {R.attr.timer_10s};
    private static final int[] STATE_TIMER_OFF = {R.attr.timer_off};
    private boolean timer_off;
    private boolean timer_3s;
    private boolean timer_10s;
''',
'''    private static final int[] STATE_TIMER_2S = {R.attr.timer_2s};
    private static final int[] STATE_TIMER_12S = {R.attr.timer_12s};
    private static final int[] STATE_TIMER_OFF = {R.attr.timer_off};
    private boolean timer_off;
    private boolean timer_2s;
    private boolean timer_12s;
''',
"timer button state fields")
s=one(s,
'''        if (timer_3s)
            mergeDrawableStates(drawableState, STATE_TIMER_3S);
        if (timer_10s)
            mergeDrawableStates(drawableState, STATE_TIMER_10S);
''',
'''        if (timer_2s)
            mergeDrawableStates(drawableState, STATE_TIMER_2S);
        if (timer_12s)
            mergeDrawableStates(drawableState, STATE_TIMER_12S);
''',
"timer button drawable states")
s=one(s,
'''        timer_off = false;
        timer_3s = false;
        timer_10s = false;
''',
'''        timer_off = false;
        timer_2s = false;
        timer_12s = false;
''',
"timer state reset")
s=one(s,
'''            case 1:
                timer_3s = true;
                break;
            case 2:
                timer_10s = true;
                break;
''',
'''            case 1:
                timer_2s = true;
                break;
            case 2:
                timer_12s = true;
                break;
''',
"timer state mapping")
timerbutton.write_text(s)

s=settingsbar.read_text()
s=one(s,
'''                SettingsBarButtonModel.newButtonModel(R.id.timer_off_button, R.drawable.ic_timeroff, R.string.off, 0, timerEntry),
                SettingsBarButtonModel.newButtonModel(R.id.timer3s_button, R.drawable.ic_timer3s, R.string.t_3s, 1, timerEntry),
                SettingsBarButtonModel.newButtonModel(R.id.timer10s_button, R.drawable.ic_timer10s, R.string.t_10s, 2, timerEntry)
''',
'''                SettingsBarButtonModel.newButtonModel(R.id.timer_off_button, R.drawable.ic_timeroff, R.string.off, 0, timerEntry),
                SettingsBarButtonModel.newButtonModel(R.id.timer3s_button, R.drawable.ic_timer2s_mono, R.string.t_2s, 1, timerEntry),
                SettingsBarButtonModel.newButtonModel(R.id.timer10s_button, R.drawable.ic_timer12s_mono, R.string.t_12s, 2, timerEntry)
''',
"settings bar timer choices")
settingsbar.write_text(s)

g=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m:raise SystemExit("LEICATIMER1A versionName missing")
if "leicatimer1a" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-leicatimer1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICATIMER1A changed photographic/runtime capture files "+repr(changed))

proof={
 "revision":"LEICATIMER1A",
 "cameraModel":"first_generation_Leica_M_Monochrom",
 "choicesSeconds":[0,2,12],
 "labels":["Off","2s","12s"],
 "defaultSeconds":0,
 "sameExistingCountdownScheduler":True,
 "shutterStartsAfterCountdown":True,
 "bracketingStartsAfterCountdown":True,
 "bracketTimerAppliedOnceToSeries":True,
 "captureControllerChanged":False,
 "exposurePlanChanged":False,
 "rendererChanged":False,
 "dngPixelMathChanged":False,
 "hdrMergeChanged":False,
 "frozenPhotographicHashes":after,
}
(root/"LEICATIMER1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
