#!/usr/bin/env python3
"""LEICABRACKET1A: first-generation M Monochrom separate-frame automatic bracketing."""
from pathlib import Path
import hashlib,json,re,shutil,sys,xml.etree.ElementTree as ET

if len(sys.argv)!=2: raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
pref_xml=root/"app/src/main/res/xml/preferences.xml"
keys_xml=root/"app/src/main/res/values/preference_keys.xml"
arrays_xml=root/"app/src/main/res/values/arrays.xml"
strings_xml=root/"app/src/main/res/values/strings.xml"
pref_java=J/"settings/PreferenceKeys.java"
settingsbar=J/"ui/camera/viewmodel/SettingsBarEntryProvider.java"
ui=J/"ui/camera/CameraUIController.java"
fragment=J/"ui/camera/CameraFragment.java"
capture=J/"capture/CaptureController.java"
plan=J/"m9/exposure/MonoExposurePlan1A.java"
diag=J/"m9/exposure/MonoExposureDiagnostics1A.java"
helper=J/"m9/exposure/MonoBracket1H.java"
gradle=root/"app/build.gradle"

for p in [pref_xml,keys_xml,arrays_xml,strings_xml,pref_java,settingsbar,ui,fragment,capture,plan,diag,gradle]:
    if not p.is_file():raise SystemExit("LEICABRACKET1A missing "+str(p))
for receipt in ["LEICAEV1A_ISOLATION.json","LEICAAELOCK1A_ISOLATION.json",
                "LEICASLOWEST1A_ISOLATION.json","LEICAAUTOISO1A_ISOLATION.json"]:
    if not (root/receipt).is_file():raise SystemExit("LEICABRACKET1A missing parent receipt "+receipt)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1:raise SystemExit(f"LEICABRACKET1A {label} anchor count={n}")
    return s.replace(a,b,1)
def append_resource(path,fragment):
    s=path.read_text()
    if fragment.splitlines()[0] in s:raise SystemExit("resource already present "+str(path))
    path.write_text(one(s,"</resources>",fragment+"\n</resources>",path.name))

frozen=[
 J/"m9/render/M9R35Renderer.java",J/"m9/render/M9NativeColorCore.java",
 J/"m9/export/MonoDngExport1A.java",J/"m9/export/MonoDngWriter1A.java",
 J/"m9/export/MonoLinearPlane1A.java",J/"m9/preview/MonoGpuPreview2A.java",
 root/"app/src/main/cpp/m9color_jni.cpp",root/"app/src/main/assets/shaders/preview/main_fs.glsl",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}

helper.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(here/"MonoBracket1H.java",helper)

# ---- Leica setup UI ---------------------------------------------------------
append_resource(keys_xml,'''    <string name="pref_mono_bracket_frames_key" translatable="false">pref_mono_bracket_frames_key</string>
    <string name="pref_mono_bracket_sequence_key" translatable="false">pref_mono_bracket_sequence_key</string>
    <string name="pref_mono_bracket_step_key" translatable="false">pref_mono_bracket_step_key</string>''')
append_resource(strings_xml,'''    <string name="mono_bracket_frames">Bracketing frames</string>
    <string name="mono_bracket_frames_summary">First-generation Leica M Monochrom: 3, 5 or 7 separate exposures</string>
    <string name="mono_bracket_sequence">Bracketing sequence</string>
    <string name="mono_bracket_sequence_summary">Correct / over / under or under / correct / over</string>
    <string name="mono_bracket_step">Bracketing EV increment</string>
    <string name="mono_bracket_step_summary">0.5, 1, 1.5 or 2 EV; 7 frames are limited to 0.5 or 1 EV</string>
    <string name="mono_bracketing_off">Off</string>
    <string name="mono_bracketing_on">On</string>
    <string name="mono_bracket_aperture_priority_only">Bracketing requires automatic shutter (A mode)</string>
    <string name="mono_bracket_flash_blocked">Bracketing is unavailable while flash/torch is active</string>''')
append_resource(arrays_xml,'''    <string-array name="mono_bracket_frames_entries">
        <item>3</item><item>5</item><item>7</item>
    </string-array>
    <string-array name="mono_bracket_frames_values">
        <item>3</item><item>5</item><item>7</item>
    </string-array>
    <string-array name="mono_bracket_sequence_entries">
        <item>0 / + / −</item><item>− / 0 / +</item>
    </string-array>
    <string-array name="mono_bracket_sequence_values">
        <item>0</item><item>1</item>
    </string-array>
    <string-array name="mono_bracket_step_entries">
        <item>0.5 EV</item><item>1 EV</item><item>1.5 EV</item><item>2 EV</item>
    </string-array>
    <string-array name="mono_bracket_step_values">
        <item>1</item><item>2</item><item>3</item><item>4</item>
    </string-array>''')

ANDROID="http://schemas.android.com/apk/res/android";APP="http://schemas.android.com/apk/res-auto"
ET.register_namespace("android",ANDROID);ET.register_namespace("app",APP)
akey="{"+ANDROID+"}key";tree=ET.parse(pref_xml);screen=tree.getroot()
cat=next((n for n in list(screen) if n.attrib.get(akey)=="@string/pref_category_monochrom_key"),None)
if cat is None:raise SystemExit("Monochrom category missing")
for key in ["@string/pref_mono_bracket_frames_key","@string/pref_mono_bracket_sequence_key","@string/pref_mono_bracket_step_key"]:
    if any(n.attrib.get(akey)==key for n in list(cat)):raise SystemExit("bracket pref already present "+key)
def listpref(key,title,summary,entries,values,default):
    return ET.Element("ListPreference",{
        "{"+ANDROID+"}layout":"@layout/preference_with_margin",akey:key,
        "{"+ANDROID+"}title":title,"{"+ANDROID+"}summary":summary,
        "{"+ANDROID+"}icon":"@drawable/ic_exposure","{"+ANDROID+"}entries":entries,
        "{"+ANDROID+"}entryValues":values,"{"+ANDROID+"}defaultValue":default,
        "{"+APP+"}useSimpleSummaryProvider":"true"})
children=list(cat)
slow_idx=next((i for i,n in enumerate(children) if n.attrib.get(akey)=="@string/pref_mono_slowest_speed_key"),len(children)-1)
cat.insert(slow_idx+1,listpref("@string/pref_mono_bracket_frames_key","@string/mono_bracket_frames",
    "@string/mono_bracket_frames_summary","@array/mono_bracket_frames_entries","@array/mono_bracket_frames_values","3"))
cat.insert(slow_idx+2,listpref("@string/pref_mono_bracket_sequence_key","@string/mono_bracket_sequence",
    "@string/mono_bracket_sequence_summary","@array/mono_bracket_sequence_entries","@array/mono_bracket_sequence_values","0"))
cat.insert(slow_idx+3,listpref("@string/pref_mono_bracket_step_key","@string/mono_bracket_step",
    "@string/mono_bracket_step_summary","@array/mono_bracket_step_entries","@array/mono_bracket_step_values","1"))
ET.indent(tree,space="    ");tree.write(pref_xml,encoding="utf-8",xml_declaration=True)

# ---- preference values ------------------------------------------------------
s=pref_java.read_text()
s=one(s,"        COMMON_KEYS.add(Key.KEY_MONO_SLOWEST_SPEED.mValue);\n",
      "        COMMON_KEYS.add(Key.KEY_MONO_SLOWEST_SPEED.mValue);\n"
      "        COMMON_KEYS.add(Key.KEY_MONO_BRACKET_FRAMES.mValue);\n"
      "        COMMON_KEYS.add(Key.KEY_MONO_BRACKET_SEQUENCE.mValue);\n"
      "        COMMON_KEYS.add(Key.KEY_MONO_BRACKET_STEP.mValue);\n","global bracket keys")
s=one(s,"        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_SLOWEST_SPEED, 0); // Lens dependent\n",
      "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_SLOWEST_SPEED, 0); // Lens dependent\n"
      "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_BRACKET_FRAMES, 3);\n"
      "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_BRACKET_SEQUENCE, 0);\n"
      "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_BRACKET_STEP, 1); // half-stop units = 0.5 EV\n",
      "bracket defaults")
slow_get='''    public static int getMonoSlowestSpeedValue() {
        int value=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_SLOWEST_SPEED);
        return value<0?0:(value>5?5:value);
    }
'''
s=one(s,slow_get,slow_get+'''
    public static int getMonoBracketFramesValue() {
        int value=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL,Key.KEY_MONO_BRACKET_FRAMES);
        return value==5?5:(value==7?7:3);
    }
    public static int getMonoBracketSequenceValue() {
        return preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL,Key.KEY_MONO_BRACKET_SEQUENCE)==1?1:0;
    }
    /** Half-stop units: 1=.5EV, 2=1EV, 3=1.5EV, 4=2EV. Leica limits 7 frames to <=1EV. */
    public static int getMonoBracketStepHalfStopsValue() {
        int step=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL,Key.KEY_MONO_BRACKET_STEP);
        step=Math.max(1,Math.min(4,step));
        if(getMonoBracketFramesValue()==7 && step>2) {
            step=2;
            preferenceKeys.settingsManager.set(SCOPE_GLOBAL,Key.KEY_MONO_BRACKET_STEP,step);
        }
        return step;
    }
''',"bracket getters")
s=one(s,"        KEY_MONO_SLOWEST_SPEED(R.string.pref_mono_slowest_speed_key),\n",
      "        KEY_MONO_SLOWEST_SPEED(R.string.pref_mono_slowest_speed_key),\n"
      "        KEY_MONO_BRACKET_FRAMES(R.string.pref_mono_bracket_frames_key),\n"
      "        KEY_MONO_BRACKET_SEQUENCE(R.string.pref_mono_bracket_sequence_key),\n"
      "        KEY_MONO_BRACKET_STEP(R.string.pref_mono_bracket_step_key),\n","bracket enum keys")
pref_java.write_text(s)

# ---- quick control is Leica Off/On, never Photon HDR bracketing -------------
s=settingsbar.read_text()
start=s.index("    private void createBracketingEntry() {");brace=s.index("{",start);depth=0;end=None
for i in range(brace,len(s)):
    if s[i]=="{":depth+=1
    elif s[i]=="}":
        depth-=1
        if depth==0:end=i+1;break
if end is None:raise SystemExit("bracketing method end missing")
method='''    private void createBracketingEntry() {
        bracketingEntry.addSettingsBarButtonModels(
                SettingsBarButtonModel.newButtonModel(R.id.bracketing_off_button, R.drawable.ic_exposure,
                        R.string.mono_bracketing_off, 0, bracketingEntry),
                SettingsBarButtonModel.newButtonModel(R.id.bracketing_normal_button, R.drawable.ic_exposure,
                        R.string.mono_bracketing_on, 1, bracketingEntry)
        );
    }'''
s=s[:start]+method+s[end:];settingsbar.write_text(s)

s=ui.read_text()
s=one(s,
'''                    case BRACKETING:
                        PreferenceKeys.setBracketingMode((Integer) value);
                        // Update HDR class to use the new bracketing mode
                        IsoExpoSelector.HDR = (Integer) value > 0;
                        break;
''',
'''                    case BRACKETING:
                        PreferenceKeys.setBracketingMode(((Integer)value)>0?1:0);
                        // Leica bracketing is separate saved exposures. Never route it into Photon's HDR stack.
                        IsoExpoSelector.HDR = false;
                        break;
''',"quick bracketing no HDR")
# Start a Leica series before the first ordinary one-frame capture.
s=one(s,
'''        this.shutterButton.setClickable(false);
        cameraFragment.captureController.takePicture();
''',
'''        this.shutterButton.setClickable(false);
        int bracket1H=cameraFragment.captureController.prepareMonoBracketSeries1H();
        if(bracket1H<0) {
            this.shutterButton.setActivated(true);
            this.shutterButton.setClickable(true);
            cameraFragment.showSnackBar(cameraFragment.getString(
                    bracket1H==-2?R.string.mono_bracket_flash_blocked:R.string.mono_bracket_aperture_priority_only));
            return;
        }
        cameraFragment.captureController.takePicture();
''',"start bracket at shutter")
ui.write_text(s)

# ---- plan carries bracket metadata without disturbing existing constructors --
s=plan.read_text()
s=one(s,"    public static final int FLAG_AE_LOCK_HELD = 256;\n",
      "    public static final int FLAG_AE_LOCK_HELD = 256;\n"
      "    public static final int FLAG_BRACKET_FRAME = 512;\n","bracket flag")
s=one(s,
'''    public final int observedIso, iso, postRawBoost, flags;
    public final double autoEv;
''',
'''    public final int observedIso, iso, postRawBoost, flags;
    public final double autoEv;
    public double bracketEv;
    public int bracketIndex, bracketCount;
''',"bracket plan fields")
# Parent overlays evolve the constructor validation body, so patch its stable signature/body
# rather than freezing an obsolete full method text.
ctor_sig='''    public MonoExposurePlan1A(long id, long epoch, long createdNs, long sensorTimestampNs,
            String cameraKey, Controls controls, int observedIso, long observedExposureNs,
            int iso, long exposureNs, int postRawBoost, double autoEv, String autoReason, int flags) {'''
if s.count(ctor_sig)!=1: raise SystemExit("LEICABRACKET1A plan constructor signature count="+str(s.count(ctor_sig)))
cs=s.index(ctor_sig);cb=s.index("{",cs);depth=0;ce=None
for i in range(cb,len(s)):
    if s[i]=="{":depth+=1
    elif s[i]=="}":
        depth-=1
        if depth==0:
            ce=i+1;break
if ce is None:raise SystemExit("LEICABRACKET1A plan constructor end missing")
ctor=s[cs:ce]
assign='''        this.postRawBoost=postRawBoost; this.autoEv=autoEv; this.autoReason=autoReason; this.flags=flags;'''
if ctor.count(assign)!=1:raise SystemExit("LEICABRACKET1A constructor assignment anchor mismatch")
ctor=ctor.replace(assign,assign+'''
        this.bracketEv=0.0;this.bracketIndex=-1;this.bracketCount=0;''',1)
overload='''

    public MonoExposurePlan1A(long id, long epoch, long createdNs, long sensorTimestampNs,
            String cameraKey, Controls controls, int observedIso, long observedExposureNs,
            int iso, long exposureNs, int postRawBoost, double autoEv, String autoReason, int flags,
            double bracketEv,int bracketIndex,int bracketCount) {
        this(id,epoch,createdNs,sensorTimestampNs,cameraKey,controls,observedIso,observedExposureNs,
                iso,exposureNs,postRawBoost,autoEv,autoReason,flags);
        if(!Double.isFinite(bracketEv)||bracketIndex<-1||bracketCount<0)
            throw new IllegalArgumentException("invalid_monochrom_bracket_metadata");
        this.bracketEv=bracketEv;this.bracketIndex=bracketIndex;this.bracketCount=bracketCount;
    }'''
# Bracket metadata is constructor-only but need not be final because the overload delegates first.
s=s[:cs]+ctor+overload+s[ce:]
plan.write_text(s)

# ---- CaptureController series coordinator ----------------------------------
s=capture.read_text()
field_anchor='''    private volatile boolean monoAeLock1F;
    private MonoExposurePlan1A monoAeLockSourcePlan1F;
    private MonoExposurePlan1A.Controls monoAeLockControls1F;
    private String monoAeLockCamera1F="";
'''
fields=field_anchor+'''
    // LEICABRACKET1A: serial, separately saved one-frame captures. Never an HDR stack.
    private volatile boolean monoBracketActive1H;
    private boolean monoBracketAwaitingFinish1H;
    private double[] monoBracketOffsets1H;
    private int monoBracketIndex1H;
    private MonoExposurePlan1A monoBracketBasePlan1H;
    private MonoExposurePlan1A.Controls monoBracketBaseControls1H;
    private String monoBracketCamera1H="";
'''
s=one(s,field_anchor,fields,"bracket fields")

method_anchor='''    public boolean isMonoAeLock1F() { return monoAeLock1F; }
'''
methods=r'''    public boolean isMonoBracketActive1H(){return monoBracketActive1H;}

    private synchronized void clearMonoBracket1H(String reason) {
        monoBracketActive1H=false;monoBracketAwaitingFinish1H=false;
        monoBracketOffsets1H=null;monoBracketIndex1H=0;monoBracketBasePlan1H=null;
        monoBracketBaseControls1H=null;monoBracketCamera1H="";
        monoExposureStore1A.invalidate();
    }

    /**
     * Returns 0 for ordinary single capture, positive frame count when a Leica
     * series was armed, -1 for manual-shutter/A-mode violation, -2 for flash/torch.
     */
    public synchronized int prepareMonoBracketSeries1H() {
        if(PreferenceKeys.getBracketingMode()<=0)return 0;
        if(!useMonoExposurePlan1A()||PhotonCamera.getSettings().selectedMode!=CameraMode.PHOTO)return -1;
        MonoExposurePlan1A.Controls controls=monoControls1A();
        if(controls.manualExposureNs>0)return -1;
        if(PreferenceKeys.getAeMode()!=1||mFlashed)return -2;
        String camera=monoCameraKey1A();
        long now=SystemClock.elapsedRealtimeNanos();
        monoExposureStore1A.context(camera,controls);
        MonoExposurePlan1A base=monoExposureStore1A.latest(now);
        if(base==null)base=updateMonoExposurePlan1A(mPreviewCaptureResult);
        if(base==null)return -1;
        int frames=PreferenceKeys.getMonoBracketFramesValue();
        int seq=PreferenceKeys.getMonoBracketSequenceValue();
        int half=PreferenceKeys.getMonoBracketStepHalfStopsValue();
        monoBracketOffsets1H=MonoBracket1H.offsets(frames,seq,half);
        monoBracketIndex1H=0;monoBracketBasePlan1H=base;monoBracketBaseControls1H=controls;
        monoBracketCamera1H=camera;monoBracketActive1H=true;monoBracketAwaitingFinish1H=false;
        monoExposureStore1A.invalidate();
        Log.i(TAG,"LEICABRACKET1A armed frames="+frames+" seq="+seq+" halfStops="+half
                +" baseISO="+base.iso+" baseT="+base.exposureNs);
        return frames;
    }

    private synchronized MonoExposurePlan1A projectMonoBracket1H(CaptureResult observation,
            String camera,long token,MonoExposurePlan1A.Controls controls) {
        if(!monoBracketActive1H||monoBracketBasePlan1H==null||monoBracketOffsets1H==null
                ||monoBracketIndex1H<0||monoBracketIndex1H>=monoBracketOffsets1H.length)return null;
        if(!camera.equals(monoBracketCamera1H)||monoBracketBaseControls1H==null
                ||!monoBracketBaseControls1H.aeLockCompatible(controls)) {
            clearMonoBracket1H("context_change");return null;
        }
        Integer oi=observation==null?null:observation.get(CaptureResult.SENSOR_SENSITIVITY);
        Long ot=observation==null?null:observation.get(CaptureResult.SENSOR_EXPOSURE_TIME);
        Long ts=observation==null?null:observation.get(CaptureResult.SENSOR_TIMESTAMP);
        Integer boost=observation==null?null:observation.get(CaptureResult.CONTROL_POST_RAW_SENSITIVITY_BOOST);
        if(oi==null||oi<=0||ot==null||ot<=0)return null;
        double offset=monoBracketOffsets1H[monoBracketIndex1H];
        long targetT=MonoBracket1H.bracketExposureNs(monoBracketBasePlan1H.exposureNs,offset,monoCharacteristics1A());
        long now=SystemClock.elapsedRealtimeNanos();
        return new MonoExposurePlan1A(now,token,now,ts==null?-1:ts,camera,controls,
                oi,ot,monoBracketBasePlan1H.iso,targetT,boost==null||boost<=0?100:boost,
                monoBracketBasePlan1H.autoEv,"leica_bracket_frame",
                monoBracketBasePlan1H.flags|MonoExposurePlan1A.FLAG_BRACKET_FRAME,
                offset,monoBracketIndex1H,monoBracketOffsets1H.length);
    }

    /** Called once per processing completion. True means another separately saved frame is due. */
    public synchronized boolean advanceMonoBracketAfterProcessing1H() {
        if(!monoBracketActive1H||!monoBracketAwaitingFinish1H)return false;
        monoBracketAwaitingFinish1H=false;
        if(monoBracketOffsets1H!=null && monoBracketIndex1H+1<monoBracketOffsets1H.length) {
            monoBracketIndex1H++;
            monoExposureStore1A.invalidate();
            return true;
        }
        clearMonoBracket1H("series_complete");
        return false;
    }

    public synchronized void abortMonoBracket1H(){clearMonoBracket1H("aborted");}

'''+method_anchor
s=one(s,method_anchor,methods,"bracket coordinator methods")

# Bracket plan takes precedence over AE-L projection once series has been armed.
old_plan='''        MonoExposurePlan1A plan=monoAeLock1F
                ?projectMonoAeLock1F(observation,camera,token,controls)
                :IsoExpoSelector.planMonoExposure1A(this,observation,camera,token,controls);
'''
new_plan='''        MonoExposurePlan1A plan=monoBracketActive1H
                ?projectMonoBracket1H(observation,camera,token,controls)
                :(monoAeLock1F
                    ?projectMonoAeLock1F(observation,camera,token,controls)
                    :IsoExpoSelector.planMonoExposure1A(this,observation,camera,token,controls));
'''
s=one(s,old_plan,new_plan,"bracket projection priority")

# Mark exactly one processing completion as belonging to each serial bracket frame.
take_anchor='''    public void takePicture() {
        if (mPreviewRequestBuilder == null || mCaptureSession == null) {
'''
s=one(s,take_anchor,'''    public void takePicture() {
        if(monoBracketActive1H) {
            synchronized(this){monoBracketAwaitingFinish1H=true;}
        }
        if (mPreviewRequestBuilder == null || mCaptureSession == null) {
''',"mark bracket capture")
# Camera close aborts any pending series.
s=one(s,
'''    public void closeCamera() {
        clearMonoAeLockFields1F("camera_close");
''',
'''    public void closeCamera() {
        clearMonoBracket1H("camera_close");
        clearMonoAeLockFields1F("camera_close");
''',"camera close abort")
capture.write_text(s)

# ---- CameraFragment serializes full save/render before taking next exposure --
s=fragment.read_text()
old_finish='''        public void onProcessingFinished(Object obj) {
            logD("onProcessingFinished: " + obj);
            mCameraUIView.setProcessingProgressBarIndeterminate(false);
            mCameraUIView.activateShutterButton(true);
            mCameraUIView.lockUIForBurst(false);
            stopNotification();

        }
'''
new_finish='''        public void onProcessingFinished(Object obj) {
            logD("onProcessingFinished: " + obj);
            if(captureController!=null && captureController.advanceMonoBracketAfterProcessing1H()) {
                // Separate files, never stacking: wait until the preceding JPEG/DNG job has
                // completed, then trigger the next physical shutter request.
                textureView.postDelayed(() -> {
                    if(captureController!=null && captureController.isMonoBracketActive1H())
                        captureController.takePicture();
                },120);
                return;
            }
            mCameraUIView.setProcessingProgressBarIndeterminate(false);
            mCameraUIView.activateShutterButton(true);
            mCameraUIView.lockUIForBurst(false);
            stopNotification();

        }
'''
s=one(s,old_finish,new_finish,"serial next bracket after processing")
s=one(s,
'''        public void onProcessingError(Object obj) {
            if (obj instanceof String)
                showToast((String) obj);
''',
'''        public void onProcessingError(Object obj) {
            if(captureController!=null)captureController.abortMonoBracket1H();
            if (obj instanceof String)
                showToast((String) obj);
''',"abort bracket on error")
fragment.write_text(s)

# ---- diagnostics ------------------------------------------------------------
s=diag.read_text()
anchor='''                    .put("automaticPlacementStillEligibleWithUserEv",true)
'''
s=one(s,anchor,anchor+'''                    .put("bracketingRevision","LEICABRACKET1A")
                    .put("bracketingFrame",(p.flags&MonoExposurePlan1A.FLAG_BRACKET_FRAME)!=0)
                    .put("bracketingOffsetEv",p.bracketEv)
                    .put("bracketingIndex",p.bracketIndex)
                    .put("bracketingCount",p.bracketCount)
                    .put("bracketingIsoHeldAcrossSeries",(p.flags&MonoExposurePlan1A.FLAG_BRACKET_FRAME)!=0)
                    .put("bracketingSeparateFiles",true)
                    .put("bracketingHdrMerge",false)
''',"bracket diagnostics")
diag.write_text(s)

g=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m:raise SystemExit("versionName missing")
if "leicabracket1a" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-leicabracket1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICABRACKET1A changed frozen image-output files "+repr(changed))

proof={
 "revision":"LEICABRACKET1A",
 "cameraModel":"first_generation_Leica_M_Monochrom_2012",
 "frames":[3,5,7],
 "sequences":["0/+/-","-/0/+"],
 "stepsEv":[0.5,1.0,1.5,2.0],
 "sevenFrameAllowedStepsEv":[0.5,1.0],
 "aperturePriorityOnly":True,
 "flashBlocked":True,
 "seriesIsoRule":"correct_exposure_base_plan_ISO_held_for_all_frames",
 "autoIsoMaxIgnoredAfterBaseIsoChosen":True,
 "slowestSpeedIgnoredAfterBaseIsoChosen":True,
 "fullPhysicalShutterRangeUsed":True,
 "exposureLimitBehavior":"clamp_each_required_shutter_and_still_take_all_frames",
 "eachFrameSeparatelyRenderedAndSaved":True,
 "hdrMerge":False,
 "stacking":False,
 "userEvShiftsSeriesCenter":True,
 "aeLockMaySupplySeriesCenter":True,
 "settingsPersistUntilDisabled":True,
 "rendererChanged":False,"linearDngMathChanged":False,
 "contrastChanged":False,"toningChanged":False,"sharpnessChanged":False,
 "frozenImageOutputHashes":after,
}
(root/"LEICABRACKET1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
