#!/usr/bin/env python3
"""LEICAOUTPUTMODE1A: make Save control the Monochrom outputs and add independent original-sensor RAW toggle."""
from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET

if len(sys.argv)!=2: raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve();J=root/"app/src/main/java/com/particlesdevs/photoncamera"
pref_xml=root/"app/src/main/res/xml/preferences.xml"
keys_xml=root/"app/src/main/res/values/preference_keys.xml"
arrays_xml=root/"app/src/main/res/values/arrays.xml"
strings_xml=root/"app/src/main/res/values/strings.xml"
pref_java=J/"settings/PreferenceKeys.java"
settings_java=J/"api/Settings.java"
settingsbar=J/"ui/camera/viewmodel/SettingsBarEntryProvider.java"
renderer=J/"m9/render/M9R35Renderer.java"
primary_queue=J/"m9/render/M9PrimaryRenderQueue.java"
export=J/"m9/export/MonoDngExport1A.java"
gradle=root/"app/build.gradle"
for p in [pref_xml,keys_xml,arrays_xml,strings_xml,pref_java,settings_java,settingsbar,renderer,primary_queue,export,gradle]:
    if not p.is_file():raise SystemExit("LEICAOUTPUTMODE1A missing "+str(p))
for receipt in ["LEICAUICLEANUP1A_ISOLATION.json","LEICADISPLAYAIDS1A_ISOLATION.json"]:
    if not (root/receipt).is_file():raise SystemExit("LEICAOUTPUTMODE1A missing parent receipt "+receipt)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1:raise SystemExit(f"LEICAOUTPUTMODE1A {label} anchor count={n}")
    return s.replace(a,b,1)
def append_resource(path,fragment):
    s=path.read_text()
    first=fragment.splitlines()[0]
    if first in s:raise SystemExit("LEICAOUTPUTMODE1A resource already present "+str(path))
    path.write_text(one(s,"</resources>",fragment+"\n</resources>",path.name))

# Pixel/exposure math must stay frozen. Renderer orchestration may change only around
# output admission/encoding; native color, DNG pixel writer/plane and exposure are immutable.
frozen=[
 J/"m9/render/M9NativeColorCore.java",
 J/"m9/export/MonoDngWriter1A.java",J/"m9/export/MonoLinearPlane1A.java",
 J/"processing/parameters/IsoExpoSelector.java",J/"m9/exposure/MonoExposurePlan1A.java",
 J/"m9/preview/MonoGpuPreview2A.java",J/"ui/camera/views/viewfinder/MainRenderer.java",
 root/"app/src/main/cpp/m9color_jni.cpp",root/"app/src/main/assets/shaders/preview/main_fs.glsl",
 root/"app/src/main/assets/mono/mono_contrast_curves.bin",root/"app/src/main/assets/mono/mono_sharpness5.bin",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}

# ----- user-facing output model ----------------------------------------------
append_resource(keys_xml,'''    <string name="pref_mono_original_sensor_raw_key" translatable="false">pref_mono_original_sensor_raw_key</string>''')
append_resource(strings_xml,'''    <string name="mono_original_sensor_raw">Original Sensor RAW</string>
    <string name="mono_original_sensor_raw_summary">Also save the untouched Bayer/color DNG from the phone sensor</string>
    <string name="mono_dng_plus_jpeg">DNG + JPEG</string>
    <string name="mono_dng_only">DNG</string>''')

s=arrays_xml.read_text()
s=one(s,
'''    <string-array name="raw_mode_entries">
        <item>JPEG</item>
        <item>RAW + JPEG</item>
        <item>RAW</item>
    </string-array>''',
'''    <string-array name="raw_mode_entries">
        <item>JPEG</item>
        <item>DNG + JPEG</item>
        <item>DNG</item>
    </string-array>''',"Save labels")
arrays_xml.write_text(s)

ANDROID="http://schemas.android.com/apk/res/android";APP="http://schemas.android.com/apk/res-auto"
ET.register_namespace("android",ANDROID);ET.register_namespace("app",APP);akey="{"+ANDROID+"}key"
tree=ET.parse(pref_xml);screen=tree.getroot()
cat=next((n for n in list(screen) if n.attrib.get(akey)=="@string/pref_category_monochrom_key"),None)
if cat is None:raise SystemExit("Leica category missing")
key="@string/pref_mono_original_sensor_raw_key"
if any(n.attrib.get(akey)==key for n in list(cat)):raise SystemExit("original RAW pref already present")
toggle=ET.Element("com.particlesdevs.photoncamera.ui.settings.custompreferences.ManagedSwitchPreference",{
    "{"+ANDROID+"}key":key,
    "{"+ANDROID+"}defaultValue":"false",
    "{"+ANDROID+"}layout":"@layout/preference_with_margin",
    "{"+ANDROID+"}title":"@string/mono_original_sensor_raw",
    "{"+ANDROID+"}summary":"@string/mono_original_sensor_raw_summary",
    "{"+ANDROID+"}icon":"@drawable/ic_raw",
})
children=list(cat)
anchor_idx=next((i for i,n in enumerate(children) if n.attrib.get(akey)=="@string/pref_mono_highlight_clipping_key"),len(children)-1)
cat.insert(anchor_idx+1,toggle)
ET.indent(tree,space="    ");tree.write(pref_xml,encoding="utf-8",xml_declaration=True)

# ----- PreferenceKeys owns the output semantics ------------------------------
s=pref_java.read_text()
s=one(s,"        COMMON_KEYS.add(Key.KEY_MONO_HIGHLIGHT_CLIPPING.mValue);\n",
      "        COMMON_KEYS.add(Key.KEY_MONO_HIGHLIGHT_CLIPPING.mValue);\n"
      "        COMMON_KEYS.add(Key.KEY_MONO_ORIGINAL_SENSOR_RAW.mValue);\n","original RAW global key")
s=one(s,"        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_HIGHLIGHT_CLIPPING, 0);\n",
      "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_HIGHLIGHT_CLIPPING, 0);\n"
      "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_ORIGINAL_SENSOR_RAW, false);\n","original RAW default")
# Replace generic "raw save" semantics: Save mode now means Monochrom output selection;
# the untouched Bayer DNG is controlled exclusively by the new toggle.
old='''    /** True when the current Save mode writes a DNG (RAW+JPEG, RAW). */
    public static boolean isRawSave() {
        int v = isSaveRaw();
        return v == 1 || v == 2;
    }
'''
new='''    /** Monochrom linear DNG requested by Save = DNG+JPEG or DNG. */
    public static boolean isMonoLinearDngRequested() {
        int v=isSaveRaw();
        return v==1||v==2;
    }

    /** Finished Monochrom JPEG requested by Save = JPEG or DNG+JPEG. */
    public static boolean isMonoJpegRequested() {
        int v=isSaveRaw();
        return v==0||v==1;
    }

    /** Independent advanced preservation of the untouched Bayer/color phone RAW. */
    public static boolean isMonoOriginalSensorRawEnabled() {
        return preferenceKeys.settingsManager.getBoolean(SCOPE_GLOBAL,Key.KEY_MONO_ORIGINAL_SENSOR_RAW);
    }
    public static void setMonoOriginalSensorRawEnabled(boolean value) {
        preferenceKeys.settingsManager.set(SCOPE_GLOBAL,Key.KEY_MONO_ORIGINAL_SENSOR_RAW,value);
    }

    /** Generic Photon RAW means original sensor RAW in this Monochrom build. */
    public static boolean isRawSave() {
        return isMonoOriginalSensorRawEnabled();
    }
'''
s=one(s,old,new,"separate Monochrom DNG from original sensor RAW")
s=one(s,"        KEY_MONO_HIGHLIGHT_CLIPPING(R.string.pref_mono_highlight_clipping_key),\n",
      "        KEY_MONO_HIGHLIGHT_CLIPPING(R.string.pref_mono_highlight_clipping_key),\n"
      "        KEY_MONO_ORIGINAL_SENSOR_RAW(R.string.pref_mono_original_sensor_raw_key),\n","original RAW enum")
pref_java.write_text(s)

# Prevent Photon's generic Hdrx RAW saver from interpreting the Monochrom Save mode
# as permission to emit an untouched Bayer DNG. The primary Monochrom queue owns that.
s=settings_java.read_text()
s=one(s,"        rawSaver = PreferenceKeys.isSaveRaw();\n",
      "        rawSaver = 0; // LEICAOUTPUTMODE1A original sensor RAW is owned by M9PrimaryRenderQueue toggle\n",
      "disable generic Photon RAW saver")
settings_java.write_text(s)

# ----- Quick Save selector is explicitly JPEG / DNG+JPEG / DNG ----------------
s=settingsbar.read_text()
# Delete the stale HEIC relabel refresh; HEIC is not a Monochrom output mode.
heic_block='''        if (PreferenceKeys.isHeicSave() != saveLabelsHeic) {
            // Toggle flipped since the buttons were built (e.g. changed in
            // Settings) — rebuild so JPEG/HEIC labels match. Views are
            // recreated from these models by addEntries().
            createSaveRawEntry();
        }
'''
if heic_block in s:s=s.replace(heic_block,"",1)
start=s.index("    private void  createSaveRawEntry() {") if "    private void  createSaveRawEntry() {" in s else s.index("    private void createSaveRawEntry() {")
brace=s.index("{",start);depth=0;end=None
for i in range(brace,len(s)):
    if s[i]=="{":depth+=1
    elif s[i]=="}":
        depth-=1
        if depth==0:end=i+1;break
if end is None:raise SystemExit("createSaveRawEntry end missing")
method='''    private void createSaveRawEntry() {
        saveLabelsHeic=false;
        saveRawEntry.addSettingsBarButtonModels(
                SettingsBarButtonModel.newButtonModel(R.id.raw_off_button, R.drawable.ic_raw_off, R.string.jpg_only, 0, saveRawEntry),
                SettingsBarButtonModel.newButtonModel(R.id.raw_on_button, R.drawable.ic_raw, R.string.mono_dng_plus_jpeg, 1, saveRawEntry),
                SettingsBarButtonModel.newButtonModel(R.id.raw_only_button, R.drawable.ic_raw, R.string.mono_dng_only, 2, saveRawEntry)
        );
    }'''
s=s[:start]+method+s[end:]
settingsbar.write_text(s)

# ----- Derived Monochrom DNG exporter: no allocation/admission in JPEG mode ----
s=export.read_text()
# Capture defensive gate.
capture_sig='''    public static Pending capture(Mat cameraRgb,int width,int height,int rotation,
            float[] weights,double representationScale) throws Exception {
'''
s=one(s,capture_sig,capture_sig+'''        if(!com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoLinearDngRequested())return null;
''',"derived DNG capture gate")
# Bracketing's non-notifying admission probe and ordinary shutter admission both bypass
# the durable DNG queue when Save=JPEG.
s=one(s,
'''    public static boolean canAdmitCapture1B() {
        startRecovery();MonoDngSpool1B s=store;
''',
'''    public static boolean canAdmitCapture1B() {
        if(!com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoLinearDngRequested())return true;
        startRecovery();MonoDngSpool1B s=store;
''',"non-notifying JPEG admission bypass")
s=one(s,
'''    public static boolean admitCapture1B() {
        startRecovery();MonoDngSpool1B s=store;
''',
'''    public static boolean admitCapture1B() {
        if(!com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoLinearDngRequested())return true;
        startRecovery();MonoDngSpool1B s=store;
''',"JPEG admission bypass")
submit_sig='''    public static JSONObject submit(Pending pending,Path originalDng,CaptureResult result,String cameraId) {
        JSONObject reply=new JSONObject();
'''
s=one(s,submit_sig,submit_sig+'''        if(!com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoLinearDngRequested()){
            note(reply,"status","monochrom_DNG_disabled_by_Save_mode");return reply;
        }
''',"derived DNG submit defense")
export.write_text(s)

# ----- Renderer: preserve exact photographic math, gate only output encoding ----
s=renderer.read_text()
s=one(s,
'''            if (MONO1A_ENABLED) {
                try {
                    NativeProspectiveSource monoDngSource1A = buildNativeProspectiveSource(
''',
'''            if (MONO1A_ENABLED && com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoLinearDngRequested()) {
                try {
                    NativeProspectiveSource monoDngSource1A = buildNativeProspectiveSource(
''',"skip linear DNG plane copy for JPEG-only")

# Replace only the post-render output transport boundary. The native bitmap is unchanged.
thumb='''            MonoDngExport1A.thumbnail(out.monoDngPending1A, bitmap);
'''
ti=s.index(thumb)
end_marker='''            if (SAVE_PARITY_PNG && !pngSaved) throw new IllegalStateException("M9 parity PNG save failed");'''
ei=s.index(end_marker,ti)
old_block=s[ti:ei]
new_block='''            MonoDngExport1A.thumbnail(out.monoDngPending1A, bitmap);
            final boolean jpegRequested1L=com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoJpegRequested();
            final boolean monoDngRequested1L=com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoLinearDngRequested();
            long jpegStartedNs=System.nanoTime();
            long jpegEncodeWriteElapsedMs=-1L;
            boolean jpgSaved=true;
            ImageSaver.Util.M9JpegSaveTiming jpegTiming=null;
            if(jpegRequested1L) {
                jpgSaved=ImageSaver.Util.saveBitmapAsJPGPayloadM9(jpgPath,bitmap,JPEG_QUALITY,exif);
                jpegEncodeWriteElapsedMs=(System.nanoTime()-jpegStartedNs)/1_000_000L;
                jpegTiming=ImageSaver.Util.consumeM9JpegSaveTiming();
                bitmap=null;
                if(!jpgSaved)throw new IllegalStateException("M9 JPEG payload save failed");
            } else {
                if(bitmap!=null&&!bitmap.isRecycled())bitmap.recycle();
                bitmap=null;
                jpgPath=null;
            }
            if(monoDngRequested1L) {
                out.diagnostics.put("monoDngExport",MonoDngExport1A.submit(
                        out.monoDngPending1A,dngPath,diagnosticCaptureResult1A,params.cameraID));
            } else {
                out.diagnostics.put("monoDngExportStatus","disabled_by_Save_JPEG");
            }
            out.monoDngPending1A=null;
'''
s=s[:ti]+new_block+s[ei:]
s=one(s,
'''            diag.put("jpegPath", jpgPath.toString());
''',
'''            diag.put("jpegRequested",jpegRequested1L);
            diag.put("monoLinearDngRequested",monoDngRequested1L);
            diag.put("originalSensorRawRequested",
                    com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoOriginalSensorRawEnabled());
            if(jpgPath!=null)diag.put("jpegPath",jpgPath.toString());
''',"conditional JPEG diagnostics")
s=one(s,
'''            Log.d(TAG, "R3.8-H25/TG1 PRIMARY2.4 COLORNATIVE2A render complete in " + elapsedMs + " ms: " + jpgPath);
            return new Result(true, jpgPath, SAVE_PARITY_PNG ? pngPath : null, null, diag, exif);
''',
'''            Log.d(TAG, "R3.8-H25/TG1 PRIMARY2.4 COLORNATIVE2A render complete in " + elapsedMs
                    + " ms; JPEG=" + (jpgPath!=null?jpgPath:"disabled") + "; monoDNG=" + monoDngRequested1L);
            return new Result(true,jpgPath,SAVE_PARITY_PNG?pngPath:null,null,diag,exif);
''',"renderer output completion log")
renderer.write_text(s)

# ----- Primary queue: untouched Bayer/color DNG is independent advanced toggle --
s=primary_queue.read_text()
if "import com.particlesdevs.photoncamera.settings.PreferenceKeys;" not in s:
    s=one(s,
'''import com.particlesdevs.photoncamera.processing.ProcessingEventsListener;
''',
'''import com.particlesdevs.photoncamera.processing.ProcessingEventsListener;
import com.particlesdevs.photoncamera.settings.PreferenceKeys;
''',"queue PreferenceKeys import")
# Capture output decisions once per shutter so a settings change cannot split a shot.
marker='''            String error = null;
            try {
'''
s=one(s,marker,'''            String error = null;
            final boolean originalSensorRawRequested1L=PreferenceKeys.isMonoOriginalSensorRawEnabled();
            final boolean jpegRequested1L=PreferenceKeys.isMonoJpegRequested();
            try {
''',"queue immutable output decisions")
old_jpeg='''                final Path jpegPath = renderResult != null ? renderResult.jpegPath : null;
                final boolean jpegPayloadSaved = renderResult != null && renderResult.success && jpegPath != null;
                M9JpegFinalizeQueue.Ticket jpegFinalizeTicket = null;
                if (jpegPayloadSaved) {
                    // PERF3F EXIFASYNC1A: publication moves with EXIF finalization. The renderer
                    // has already written the exact PERF3E JPEG payload; do not media-scan it here.
                    jpegFinalizeTicket = M9JpegFinalizeQueue.submit(
                            jpegPath, renderResult.jpegExifData, processingEventsListener);
                } else {
                    error = renderResult != null ? renderResult.error : "null renderer result";
                    Log.e(TAG, "PRIMARY2.5 EXIFASYNC1A M9 JPEG payload failed: " + error);
                }
'''
new_jpeg='''                final Path jpegPath=renderResult!=null?renderResult.jpegPath:null;
                final boolean jpegPayloadSaved=jpegRequested1L
                        && renderResult!=null&&renderResult.success&&jpegPath!=null;
                M9JpegFinalizeQueue.Ticket jpegFinalizeTicket=null;
                if(jpegRequested1L&&jpegPayloadSaved) {
                    // PERF3F EXIFASYNC1A: unchanged JPEG payload/finalization path.
                    jpegFinalizeTicket=M9JpegFinalizeQueue.submit(
                            jpegPath,renderResult.jpegExifData,processingEventsListener);
                } else if(jpegRequested1L) {
                    error=renderResult!=null?renderResult.error:"null renderer result";
                    Log.e(TAG,"LEICAOUTPUTMODE1A requested JPEG payload failed: "+error);
                } else {
                    Log.d(TAG,"LEICAOUTPUTMODE1A Save=DNG; JPEG encoding/publication intentionally skipped");
                }
'''
s=one(s,old_jpeg,new_jpeg,"queue JPEG requested semantics")

# Wrap the existing untouched DNG handoff without rewriting its proven persistence path.
start=s.index("                dngJob = new DngJob(")
end_token='''                    runDngAndFinalize(dngJob, false, true, fallbackCount, 0L);
                }
'''
end=s.index(end_token,start)+len(end_token)
handoff=s[start:end]
wrapped='''                if(originalSensorRawRequested1L) {
'''+handoff+'''                } else {
                    Log.d(TAG,"LEICAOUTPUTMODE1A Original Sensor RAW=Off; untouched Bayer/color DNG skipped");
                }
'''
s=s[:start]+wrapped+s[end:]
# Clarify the save itself is the original phone sensor DNG.
s=s.replace('"development DNG save returned false"','"original sensor RAW DNG save returned false"')
s=s.replace('"DNGASYNC1A development DNG save failed"','"DNGASYNC1A original sensor RAW DNG save failed"')
primary_queue.write_text(s)

g=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m:raise SystemExit("LEICAOUTPUTMODE1A versionName missing")
if "leicaoutputmode1a" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-leicaoutputmode1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICAOUTPUTMODE1A changed frozen photographic math "+repr(changed))

proof={
 "revision":"LEICAOUTPUTMODE1A",
 "saveModes":{
   "0_JPEG":{"jpeg":True,"monochromDng":False},
   "1_DNG_JPEG":{"jpeg":True,"monochromDng":True},
   "2_DNG":{"jpeg":False,"monochromDng":True}
 },
 "originalSensorRaw":"independent_toggle_default_off",
 "originalSensorRawMeaning":"untouched_phone_Bayer_or_color_DNG",
 "originalSensorRawCanAccompanyAnySaveMode":True,
 "jpegOnlyExpectedFiles":["processed_monochrom_JPEG"],
 "dngJpegExpectedFiles":["processed_monochrom_JPEG","derived_monochrom_linear_DNG"],
 "dngOnlyExpectedFiles":["derived_monochrom_linear_DNG"],
 "originalSensorRawAdds":"untouched_sensor_DNG",
 "derivedDngAllocationSkippedInJpegOnly":True,
 "derivedDngAdmissionSkippedInJpegOnly":True,
 "genericPhotonRawSaverDisabled":True,
 "nativeRenderMathChanged":False,
 "jpegEncodingMathChanged":False,
 "dngPixelMathChanged":False,
 "exposurePlanChanged":False,
 "displayAidsChanged":False,
 "frozenPhotographicHashes":after,
}
(root/"LEICAOUTPUTMODE1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
