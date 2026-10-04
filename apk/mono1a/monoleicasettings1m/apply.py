#!/usr/bin/env python3
"""LEICADIAGNOSTICS1A: user-controlled public diagnostic JSON output, default Off."""
from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET

if len(sys.argv)!=2: raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
pref_xml=root/"app/src/main/res/xml/preferences.xml"
keys_xml=root/"app/src/main/res/values/preference_keys.xml"
strings_xml=root/"app/src/main/res/values/strings.xml"
pref_java=J/"settings/PreferenceKeys.java"
diag_spool=J/"m9/M9DiagnosticBurstSpool.java"
diag_io=J/"m9/M9DiagnosticSidecarIO.java"
gradle=root/"app/build.gradle"
for p in [pref_xml,keys_xml,strings_xml,pref_java,diag_spool,diag_io,gradle]:
    if not p.is_file(): raise SystemExit("LEICADIAGNOSTICS1A missing "+str(p))
if not (root/"LEICAOUTPUTMODE1A_ISOLATION.json").is_file():
    raise SystemExit("LEICADIAGNOSTICS1A missing validated LEICAOUTPUTMODE1A parent receipt")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"LEICADIAGNOSTICS1A {label} anchor count={n}")
    return s.replace(a,b,1)
def append_resource(path,fragment):
    s=path.read_text()
    first=fragment.splitlines()[0].strip()
    if first in s: raise SystemExit("LEICADIAGNOSTICS1A resource already present "+str(path))
    path.write_text(one(s,"</resources>",fragment+"\n</resources>",path.name))

frozen=[
    J/"m9/render/M9R35Renderer.java",J/"m9/render/M9PrimaryRenderQueue.java",
    J/"m9/render/M9NativeColorCore.java",J/"m9/render/M9JpegFinalizeQueue.java",
    J/"m9/export/MonoDngExport1A.java",J/"m9/export/MonoDngSpool1B.java",
    J/"m9/export/MonoDngWriter1A.java",J/"m9/export/MonoLinearPlane1A.java",
    J/"m9/export/MonoDiagnosticPublicWriter1C.java",
    J/"processing/parameters/IsoExpoSelector.java",J/"capture/CaptureController.java",
    J/"m9/exposure/MonoExposurePlan1A.java",J/"m9/preview/MonoGpuPreview2A.java",
    J/"ui/camera/views/viewfinder/MainRenderer.java",
    root/"app/src/main/cpp/m9color_jni.cpp",
    root/"app/src/main/assets/shaders/preview/main_fs.glsl",
    root/"app/src/main/assets/mono/mono_contrast_curves.bin",
    root/"app/src/main/assets/mono/mono_sharpness5.bin",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}

append_resource(keys_xml,
'''    <string name="pref_mono_diagnostics_key" translatable="false">pref_mono_diagnostics_key</string>''')
append_resource(strings_xml,
'''    <string name="mono_diagnostics">Diagnostics</string>
    <string name="mono_diagnostics_summary">Publish development JSON sidecars with photographs</string>''')

ANDROID="http://schemas.android.com/apk/res/android";APP="http://schemas.android.com/apk/res-auto"
ET.register_namespace("android",ANDROID);ET.register_namespace("app",APP)
akey="{"+ANDROID+"}key"
tree=ET.parse(pref_xml);screen=tree.getroot()
cat=next((n for n in list(screen) if n.attrib.get(akey)=="@string/pref_category_monochrom_key"),None)
if cat is None: raise SystemExit("LEICADIAGNOSTICS1A Leica category missing")
diag_key="@string/pref_mono_diagnostics_key"
if any(n.attrib.get(akey)==diag_key for n in list(cat)):
    raise SystemExit("LEICADIAGNOSTICS1A Diagnostics preference already present")
toggle=ET.Element("com.particlesdevs.photoncamera.ui.settings.custompreferences.ManagedSwitchPreference",{
    "{"+ANDROID+"}key":diag_key,
    "{"+ANDROID+"}defaultValue":"false",
    "{"+ANDROID+"}layout":"@layout/preference_with_margin",
    "{"+ANDROID+"}title":"@string/mono_diagnostics",
    "{"+ANDROID+"}summary":"@string/mono_diagnostics_summary",
})
children=list(cat)
raw_idx=next((i for i,n in enumerate(children)
              if n.attrib.get(akey)=="@string/pref_mono_original_sensor_raw_key"),len(children)-1)
cat.insert(raw_idx+1,toggle)
ET.indent(tree,space="    ");tree.write(pref_xml,encoding="utf-8",xml_declaration=True)

s=pref_java.read_text()
s=one(s,
'''        COMMON_KEYS.add(Key.KEY_MONO_ORIGINAL_SENSOR_RAW.mValue);
''',
'''        COMMON_KEYS.add(Key.KEY_MONO_ORIGINAL_SENSOR_RAW.mValue);
        COMMON_KEYS.add(Key.KEY_MONO_DIAGNOSTICS.mValue);
''',"Diagnostics global key")
s=one(s,
'''        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_ORIGINAL_SENSOR_RAW, false);
''',
'''        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_ORIGINAL_SENSOR_RAW, false);
        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_DIAGNOSTICS, false);
''',"Diagnostics default Off")
method_anchor='''    public static void setMonoOriginalSensorRawEnabled(boolean value) {
        preferenceKeys.settingsManager.set(SCOPE_GLOBAL,Key.KEY_MONO_ORIGINAL_SENSOR_RAW,value);
    }

'''
method_insert=method_anchor+'''    /** Public development JSON sidecars. Disabled for normal photography by default. */
    public static boolean isMonoDiagnosticsEnabled() {
        return preferenceKeys.settingsManager.getBoolean(SCOPE_GLOBAL,Key.KEY_MONO_DIAGNOSTICS);
    }
    public static void setMonoDiagnosticsEnabled(boolean value) {
        preferenceKeys.settingsManager.set(SCOPE_GLOBAL,Key.KEY_MONO_DIAGNOSTICS,value);
    }

'''
s=one(s,method_anchor,method_insert,"Diagnostics accessors")
s=one(s,
'''        KEY_MONO_ORIGINAL_SENSOR_RAW(R.string.pref_mono_original_sensor_raw_key),
''',
'''        KEY_MONO_ORIGINAL_SENSOR_RAW(R.string.pref_mono_original_sensor_raw_key),
        KEY_MONO_DIAGNOSTICS(R.string.pref_mono_diagnostics_key),
''',"Diagnostics enum key")
pref_java.write_text(s)

s=diag_spool.read_text()
s=one(s,
'''    public static boolean stage(Path publicPath, byte[] bytes, String role) {
        if (publicPath == null || bytes == null) return false;
''',
'''    private static boolean diagnosticsEnabled1A() {
        try {
            return com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoDiagnosticsEnabled();
        } catch (Throwable ignored) {
            return false;
        }
    }

    public static boolean stage(Path publicPath, byte[] bytes, String role) {
        if (publicPath == null || bytes == null) return false;
        if (!diagnosticsEnabled1A()) {
            Log.d(TAG, "LEICADIAGNOSTICS1A suppressed diagnostic stage role=" + role
                    + "; path=" + publicPath);
            return true; // handled: prevent legacy public fallback and private diagnostic buildup
        }
''',"diagnostic stage gate")
s=one(s,
'''    private static boolean writePublic(Path path, byte[] bytes) {
        // MONOOUTPUT1C_CURSORQUERY: unchanged bytes through a projected SAF query.
''',
'''    private static boolean writePublic(Path path, byte[] bytes) {
        if (!diagnosticsEnabled1A()) {
            Log.d(TAG, "LEICADIAGNOSTICS1A suppressed pending diagnostic public export path=" + path);
            return true; // consume any diagnostic staged before the user switched Diagnostics Off
        }
        // MONOOUTPUT1C_CURSORQUERY: unchanged bytes through a projected SAF query.
''',"pending public export gate")
diag_spool.write_text(s)

s=diag_io.read_text()
s=one(s,
'''    public static boolean persist(Path path, byte[] bytes, String role) {
        final long startedNs = System.nanoTime();
''',
'''    private static boolean diagnosticsEnabled1A() {
        try {
            return com.particlesdevs.photoncamera.settings.PreferenceKeys.isMonoDiagnosticsEnabled();
        } catch (Throwable ignored) {
            return false;
        }
    }

    public static boolean persist(Path path, byte[] bytes, String role) {
        if (!diagnosticsEnabled1A()) {
            Log.d(TAG, "LEICADIAGNOSTICS1A suppressed legacy diagnostic write role=" + role
                    + "; path=" + path);
            return true;
        }
        final long startedNs = System.nanoTime();
''',"legacy direct writer gate")
diag_io.write_text(s)

g=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("LEICADIAGNOSTICS1A versionName missing")
if "leicadiagnostics1a" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-leicadiagnostics1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICADIAGNOSTICS1A changed frozen photographic/durable files "+repr(changed))

proof={
    "revision":"LEICADIAGNOSTICS1A","diagnosticsSetting":"Off_On","default":"Off",
    "offBehavior":"no_public_or_private_development_JSON_staging; pending_public_diagnostics_consumed_without_export",
    "onBehavior":"existing_diagnostic_pipeline_unchanged",
    "publicDiagnosticGate":"M9DiagnosticBurstSpool.stage_and_writePublic",
    "legacyFallbackGate":"M9DiagnosticSidecarIO.persist",
    "knownPublicSidecars":["_M9.json","_M9_PRIMARY.json","_MONO_LIVEPAIR.json",
        "_M9_SOURCECAL1A.json","_M9_RAWSHADING1A.json",
        "_MONO_LINEAR1A_EXPORT.json","M9_DIAGNOSTICS_BURST_*.json"],
    "diagnosticSpoolPhotographicStorage":False,
    "privateMonoDngRecoveryPreserved":True,"jpegFinalizePreserved":True,
    "originalSensorRawSemanticsPreserved":True,"saveModeSemanticsPreserved":True,
    "exposurePlanChanged":False,"rendererMathChanged":False,
    "dngPixelMathChanged":False,"previewChanged":False,
    "frozenPhotographicAndDurabilityHashes":after,
}
(root/"LEICADIAGNOSTICS1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
