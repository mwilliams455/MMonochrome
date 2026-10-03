#!/usr/bin/env python3
"""Apply LEICATONING1A on top of LEICACONTRAST1A."""
from pathlib import Path
import hashlib, json, re, sys
import xml.etree.ElementTree as ET

if len(sys.argv) != 2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()

pref_xml=root/"app/src/main/res/xml/preferences.xml"
keys_xml=root/"app/src/main/res/values/preference_keys.xml"
arrays_xml=root/"app/src/main/res/values/arrays.xml"
strings_xml=root/"app/src/main/res/values/strings.xml"
pref_java=root/"app/src/main/java/com/particlesdevs/photoncamera/settings/PreferenceKeys.java"
renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
native_java=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java"
native_cpp=root/"app/src/main/cpp/m9color_jni.cpp"
preview_java=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java"
main_renderer=root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java"
shader=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
toning_java=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/MonoToning1A.java"
gradle=root/"app/build.gradle"

for p in [pref_xml,keys_xml,arrays_xml,strings_xml,pref_java,renderer,native_java,native_cpp,preview_java,main_renderer,shader,gradle]:
    if not p.is_file(): raise SystemExit("LEICATONING1A missing "+str(p))

if not (root/"LEICACONTRAST1A_ISOLATION.json").is_file():
    raise SystemExit("LEICATONING1A requires LEICACONTRAST1A parent")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"LEICATONING1A {label} anchor count={n}")
    return s.replace(a,b,1)
def append_resource(path,fragment):
    s=path.read_text()
    if fragment.splitlines()[0] in s: raise SystemExit("LEICATONING1A resource already applied "+str(path))
    path.write_text(one(s,"</resources>",fragment+"\n</resources>",path.name))

frozen=[
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngExport1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngWriter1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoLinearPlane1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/exposure/MonoPlacementAssist1D.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoTapMeter1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java",
]
before={str(p.relative_to(root)):sha(p) for p in frozen}

# Exact firmware-derived seven-state table from M Monochrom 1.022 PROCESS/LUTS.
toning_java.parent.mkdir(parents=True,exist_ok=True)
toning_java.write_text("""package com.particlesdevs.photoncamera.m9.render;

/** Leica M Monochrom 1.022 JPEG Toning state resolver. */
public final class MonoToning1A {
    public static final String REVISION="LEICATONING1A";
    public static final String[] HUE_LABELS={"Sepia","Cool","Selenium"};
    public static final String[] STRENGTH_LABELS={"Off","Weak","Strong"};
    public static final String[] STATE_LABELS={
        "Off","Sepia Weak","Sepia Strong","Cool Weak","Cool Strong","Selenium Weak","Selenium Strong"
    };
    // PROCESS/LUTS pair A follows Leica's YCrCb ordering: Cr first, Cb second.
    public static final int[] CR={128,130,131,127,126,128,128};
    public static final int[] CB={128,125,123,130,132,129,131};
    private MonoToning1A(){}

    public static int clampHue(int v){return v<0?0:(v>2?2:v);}
    public static int clampStrength(int v){return v<0?0:(v>2?2:v);}
    public static int state(int hue,int strength){
        int h=clampHue(hue), s=clampStrength(strength);
        return s==0?0:s+2*h;
    }
    public static int cr(int hue,int strength){return CR[state(hue,strength)];}
    public static int cb(int hue,int strength){return CB[state(hue,strength)];}
    public static String label(int hue,int strength){return STATE_LABELS[state(hue,strength)];}
}
""")

append_resource(keys_xml, """    <string name="pref_mono_toning_hue_key" translatable="false">pref_mono_toning_hue_key</string>
    <string name="pref_mono_toning_strength_key" translatable="false">pref_mono_toning_strength_key</string>""")
append_resource(strings_xml, """    <string name="mono_toning">Toning</string>
    <string name="mono_toning_summary">Leica M Monochrom JPEG hue</string>
    <string name="mono_toning_strength">Toning Strength</string>
    <string name="mono_toning_strength_summary">Off, Weak or Strong; JPEG and preview only</string>""")
append_resource(arrays_xml, """    <string-array name="mono_toning_hue_entries">
        <item>Sepia</item><item>Cool</item><item>Selenium</item>
    </string-array>
    <string-array name="mono_toning_hue_entryvalues">
        <item>0</item><item>1</item><item>2</item>
    </string-array>
    <string-array name="mono_toning_strength_entries">
        <item>Off</item><item>Weak</item><item>Strong</item>
    </string-array>
    <string-array name="mono_toning_strength_entryvalues">
        <item>0</item><item>1</item><item>2</item>
    </string-array>""")

ANDROID="http://schemas.android.com/apk/res/android"; APP="http://schemas.android.com/apk/res-auto"
ET.register_namespace("android",ANDROID);ET.register_namespace("app",APP)
akey="{"+ANDROID+"}key"
tree=ET.parse(pref_xml);screen=tree.getroot()
cat=next((n for n in list(screen) if n.attrib.get(akey)=="@string/pref_category_monochrom_key"),None)
if cat is None: raise SystemExit("LEICATONING1A Monochrom category missing")
for k in ("@string/pref_mono_toning_hue_key","@string/pref_mono_toning_strength_key"):
    if any(n.attrib.get(akey)==k for n in list(cat)): raise SystemExit("LEICATONING1A preference already present "+k)
ET.SubElement(cat,"ListPreference",{
    "{"+ANDROID+"}layout":"@layout/preference_with_margin",akey:"@string/pref_mono_toning_hue_key",
    "{"+ANDROID+"}title":"@string/mono_toning","{"+ANDROID+"}summary":"@string/mono_toning_summary",
    "{"+ANDROID+"}icon":"@drawable/ic_saturation","{"+ANDROID+"}entries":"@array/mono_toning_hue_entries",
    "{"+ANDROID+"}entryValues":"@array/mono_toning_hue_entryvalues","{"+ANDROID+"}defaultValue":"0",
    "{"+APP+"}useSimpleSummaryProvider":"true"})
ET.SubElement(cat,"ListPreference",{
    "{"+ANDROID+"}layout":"@layout/preference_with_margin",akey:"@string/pref_mono_toning_strength_key",
    "{"+ANDROID+"}title":"@string/mono_toning_strength","{"+ANDROID+"}summary":"@string/mono_toning_strength_summary",
    "{"+ANDROID+"}icon":"@drawable/ic_saturation","{"+ANDROID+"}entries":"@array/mono_toning_strength_entries",
    "{"+ANDROID+"}entryValues":"@array/mono_toning_strength_entryvalues","{"+ANDROID+"}defaultValue":"0",
    "{"+APP+"}useSimpleSummaryProvider":"true"})
ET.indent(tree,space="    ");tree.write(pref_xml,encoding="utf-8",xml_declaration=True)

# Preferences: Leica controls are global across lenses.
s=pref_java.read_text()
s=one(s,"        COMMON_KEYS.add(Key.KEY_MONO_CONTRAST.mValue);\n",
      "        COMMON_KEYS.add(Key.KEY_MONO_CONTRAST.mValue);\n"
      "        COMMON_KEYS.add(Key.KEY_MONO_TONING_HUE.mValue);\n"
      "        COMMON_KEYS.add(Key.KEY_MONO_TONING_STRENGTH.mValue);\n","global toning keys")
s=one(s,"        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_CONTRAST, 2); // Leica Standard\n",
      "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_CONTRAST, 2); // Leica Standard\n"
      "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_TONING_HUE, 0); // Sepia retained while Off\n"
      "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_TONING_STRENGTH, 0); // Off\n","toning defaults")
s=one(s,"    public static int getMonoContrastValue() {\n        int value = preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_CONTRAST);\n        return value < 0 ? 0 : (value > 4 ? 4 : value);\n    }\n",
      "    public static int getMonoContrastValue() {\n        int value = preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_CONTRAST);\n        return value < 0 ? 0 : (value > 4 ? 4 : value);\n    }\n\n"
      "    public static int getMonoToningHueValue() {\n        int value=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_TONING_HUE);\n        return value<0?0:(value>2?2:value);\n    }\n"
      "    public static int getMonoToningStrengthValue() {\n        int value=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_TONING_STRENGTH);\n        return value<0?0:(value>2?2:value);\n    }\n","toning getters")
s=one(s,"        KEY_MONO_CONTRAST(R.string.pref_mono_contrast_key),\n",
      "        KEY_MONO_CONTRAST(R.string.pref_mono_contrast_key),\n"
      "        KEY_MONO_TONING_HUE(R.string.pref_mono_toning_hue_key),\n"
      "        KEY_MONO_TONING_STRENGTH(R.string.pref_mono_toning_strength_key),\n","toning enum keys")
pref_java.write_text(s)

# Renderer loads exact firmware Toning state, diagnostic control remains Off.
s=renderer.read_text()
s=one(s,
"""        final byte[] monoStandardCurve1A = MonoContrastCurves1A.loadCurve(MonoContrastCurves1A.DEFAULT);
        final byte[] monoSelectedCurve1A = MonoContrastCurves1A.loadCurve(monoContrast1A);
        Bitmap rawScalar1ABitmap = null;
""",
"""        final byte[] monoStandardCurve1A = MonoContrastCurves1A.loadCurve(MonoContrastCurves1A.DEFAULT);
        final byte[] monoSelectedCurve1A = MonoContrastCurves1A.loadCurve(monoContrast1A);
        final int monoToningHue1A=com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoToningHueValue();
        final int monoToningStrength1A=com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoToningStrengthValue();
        final int monoToningState1A=MonoToning1A.state(monoToningHue1A,monoToningStrength1A);
        final int monoToningCr1A=MonoToning1A.CR[monoToningState1A];
        final int monoToningCb1A=MonoToning1A.CB[monoToningState1A];
        Bitmap rawScalar1ABitmap = null;
""","renderer toning selection")
s=one(s,
"                    nativeShading.representationScale, monoStandardCurve1A, rawScalar1AStats);\n",
"                    nativeShading.representationScale, monoStandardCurve1A, 128, 128, rawScalar1AStats);\n",
"diagnostic toning off")
s=one(s,
"                    nativeShading.representationScale, monoSelectedCurve1A, rawScalar1BStats);\n",
"                    nativeShading.representationScale, monoSelectedCurve1A, monoToningCr1A, monoToningCb1A, rawScalar1BStats);\n",
"primary toning selected")
s=one(s,
'                rawScalar1B.put("standardCurve02Sha256", MonoContrastCurves1A.SHA256[2]);\n',
'                rawScalar1B.put("standardCurve02Sha256", MonoContrastCurves1A.SHA256[2]);\n'
'                rawScalar1B.put("toningState", monoToningState1A);\n'
'                rawScalar1B.put("toningLabel", MonoToning1A.STATE_LABELS[monoToningState1A]);\n'
'                rawScalar1B.put("toningCr", monoToningCr1A);\n'
'                rawScalar1B.put("toningCb", monoToningCb1A);\n'
'                rawScalar1B.put("toningDomain", "firmware_PROCESS_LUTS_YCrCb_chroma_pair");\n',
"raw scalar toning diagnostics")
s=one(s,
'                d.put("monochromContrastCurveSha256", MonoContrastCurves1A.SHA256[monoContrast1A]);\n',
'                d.put("monochromContrastCurveSha256", MonoContrastCurves1A.SHA256[monoContrast1A]);\n'
'                d.put("monochromToningState", monoToningState1A);\n'
'                d.put("monochromToningLabel", MonoToning1A.STATE_LABELS[monoToningState1A]);\n'
'                d.put("monochromToningCr", monoToningCr1A);\n'
'                d.put("monochromToningCb", monoToningCb1A);\n',
"root toning diagnostics")
renderer.write_text(s)

# JNI adds fixed firmware YCrCb chroma pair after the selected Leica tone curve.
s=native_java.read_text()
s=one(s,
"                                                                  double representationScale, byte[] contrastCurve,\n                                                                  long[] stats);\n",
"                                                                  double representationScale, byte[] contrastCurve,\n                                                                  int toningCr, int toningCb, long[] stats);\n",
"JNI toning declaration")
native_java.write_text(s)

s=native_cpp.read_text()
s=one(s,
"""        jfloat neutralR, jfloat neutralG, jfloat neutralB, jdouble representationScale,
        jbyteArray contrastCurveArray, jlongArray statsArray) {
""",
"""        jfloat neutralR, jfloat neutralG, jfloat neutralB, jdouble representationScale,
        jbyteArray contrastCurveArray, jint toningCr, jint toningCb, jlongArray statsArray) {
""","native toning signature")
s=one(s,
"""    std::array<uint8_t,2048> contrastCurve{};
    for (size_t i=0;i<contrastCurve.size();++i) contrastCurve[i]=static_cast<uint8_t>(contrastBytes[i]);
    jboolean isCopy=JNI_FALSE;
""",
"""    std::array<uint8_t,2048> contrastCurve{};
    for (size_t i=0;i<contrastCurve.size();++i) contrastCurve[i]=static_cast<uint8_t>(contrastBytes[i]);
    const int cr=std::max(0,std::min(255,static_cast<int>(toningCr)));
    const int cb=std::max(0,std::min(255,static_cast<int>(toningCb)));
    const int dCr=cr-128,dCb=cb-128;
    auto roundShift16=[](int x)->int { return x>=0 ? ((x+32768)>>16) : -(((-x)+32768)>>16); };
    auto clamp8=[](int x)->uint8_t { return static_cast<uint8_t>(x<0?0:(x>255?255:x)); };
    jboolean isCopy=JNI_FALSE;
""","native toning constants")
s=one(s,
"int32_t idx=v>>3;if(idx>2047)idx=2047;const uint8_t yy=contrastCurve[static_cast<size_t>(idx)];if(yy>=250)near++;\n                    const size_t p=row+static_cast<size_t>(x);argb[p]=static_cast<jint>(0xff000000u|(uint32_t(yy)<<16)|(uint32_t(yy)<<8)|uint32_t(yy));",
"int32_t idx=v>>3;if(idx>2047)idx=2047;const uint8_t yy=contrastCurve[static_cast<size_t>(idx)];if(yy>=250)near++;\n"
"                    const uint8_t rr=clamp8(static_cast<int>(yy)+roundShift16(91881*dCr));\n"
"                    const uint8_t gg=clamp8(static_cast<int>(yy)-roundShift16(22554*dCb+46802*dCr));\n"
"                    const uint8_t bb=clamp8(static_cast<int>(yy)+roundShift16(116130*dCb));\n"
"                    const size_t p=row+static_cast<size_t>(x);argb[p]=static_cast<jint>(0xff000000u|(uint32_t(rr)<<16)|(uint32_t(gg)<<8)|uint32_t(bb));",
"native YCrCb tint")
native_cpp.write_text(s)

# Preview shader applies identical JFIF/BT.601 code-domain inverse transform.
s=shader.read_text()
s=one(s,
"uniform float uMonoExposureScale1A;\n",
"uniform float uMonoExposureScale1A;\n"
"uniform float uMonoToningCr1A;\n"
"uniform float uMonoToningCb1A;\n",
"shader toning uniforms")
s=one(s,
"""    vec4 color=vec4(vec3(y),1.0);
""",
"""    float dCr=(uMonoToningCr1A-128.0)/255.0;
    float dCb=(uMonoToningCb1A-128.0)/255.0;
    vec3 toned=clamp(vec3(
        y+1.402*dCr,
        y-0.714136*dCr-0.344136*dCb,
        y+1.772*dCb),0.0,1.0);
    vec4 color=vec4(toned,1.0);
""","shader toning transform")
shader.write_text(s)

# Bind preview uniforms from current Leica settings on every draw/bind.
s=main_renderer.read_text()
s=one(s,
"    private int monoReady2A, monoUndo2A, monoY2A, monoProbeUniform2A;\n",
"    private int monoReady2A, monoUndo2A, monoY2A, monoProbeUniform2A;\n"
"    private int monoToningCrUniform1A,monoToningCbUniform1A;\n",
"preview toning uniform fields")
s=one(s,
"        monoProbeUniform2A=GLES20.glGetUniformLocation(program,\"uMonoProbe2A\");\n",
"        monoProbeUniform2A=GLES20.glGetUniformLocation(program,\"uMonoProbe2A\");\n"
"        monoToningCrUniform1A=GLES20.glGetUniformLocation(program,\"uMonoToningCr1A\");\n"
"        monoToningCbUniform1A=GLES20.glGetUniformLocation(program,\"uMonoToningCb1A\");\n",
"preview toning uniform locations")
s=one(s,
"""        boundSourceReady2A=c.ready && monoCurveLoaded2A && boundContext2A==c;
        GLES20.glUniform1i(monoReady2A,boundSourceReady2A?1:0);
""",
"""        int toningHue1A=com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoToningHueValue();
        int toningStrength1A=com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoToningStrengthValue();
        int toningState1A=com.particlesdevs.photoncamera.m9.render.MonoToning1A.state(toningHue1A,toningStrength1A);
        int toningCr1A=com.particlesdevs.photoncamera.m9.render.MonoToning1A.CR[toningState1A];
        int toningCb1A=com.particlesdevs.photoncamera.m9.render.MonoToning1A.CB[toningState1A];
        GLES20.glUniform1f(monoToningCrUniform1A,(float)toningCr1A);
        GLES20.glUniform1f(monoToningCbUniform1A,(float)toningCb1A);
        com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.setLeicaToningSelection(
                toningState1A,toningCr1A,toningCb1A);
        boundSourceReady2A=c.ready && monoCurveLoaded2A && boundContext2A==c;
        GLES20.glUniform1i(monoReady2A,boundSourceReady2A?1:0);
""","preview toning selection")
main_renderer.write_text(s)

# Preview diagnostics.
s=preview_java.read_text()
s=one(s,
"    private static volatile String selectedContrastSha=CURVE_SHA;\n",
"    private static volatile String selectedContrastSha=CURVE_SHA;\n"
"    private static volatile int selectedToningState=0,selectedToningCr=128,selectedToningCb=128;\n",
"preview toning state")
s=one(s,
"""    public static void setLeicaContrastSelection(int selector, String sha256) {
        selectedContrast = selector < 0 ? 0 : (selector > 4 ? 4 : selector);
        selectedContrastSha = sha256 == null ? CURVE_SHA : sha256;
    }
""",
"""    public static void setLeicaContrastSelection(int selector, String sha256) {
        selectedContrast = selector < 0 ? 0 : (selector > 4 ? 4 : selector);
        selectedContrastSha = sha256 == null ? CURVE_SHA : sha256;
    }
    public static void setLeicaToningSelection(int state,int cr,int cb) {
        selectedToningState=state<0?0:(state>6?6:state);
        selectedToningCr=cr; selectedToningCb=cb;
    }
""","preview toning setter")
s=one(s,
'            o.put("leicaContrastCurveSha256",selectedContrastSha);\n',
'            o.put("leicaContrastCurveSha256",selectedContrastSha);\n'
'            o.put("leicaToningState",selectedToningState);\n'
'            o.put("leicaToningLabel",com.particlesdevs.photoncamera.m9.render.MonoToning1A.STATE_LABELS[selectedToningState]);\n'
'            o.put("leicaToningCr",selectedToningCr).put("leicaToningCb",selectedToningCb);\n',
"preview toning diagnostics")
preview_java.write_text(s)

# Identity.
s=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",s)
if not m: raise SystemExit("LEICATONING1A versionName missing")
if "leicatoning1a" not in m.group(1):
    s=s[:m.start(1)]+m.group(1)+"-leicatoning1a"+s[m.end(1):]
gradle.write_text(s)

after={str(p.relative_to(root)):sha(p) for p in frozen}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICATONING1A modified frozen DNG/exposure/tap files "+repr(changed))

proof={
 "revision":"LEICATONING1A",
 "firmware":"Leica M Monochrom 1.022",
 "hueMenu":["Sepia","Cool","Selenium"],
 "strengthMenu":["Off","Weak","Strong"],
 "stateFormula":"strength==0 ? 0 : strength + 2*hue",
 "stateLabels":["Off","Sepia Weak","Sepia Strong","Cool Weak","Cool Strong","Selenium Weak","Selenium Strong"],
 "Cr":[128,130,131,127,126,128,128],
 "Cb":[128,125,123,130,132,129,131],
 "processLutsOffset":"0x7f148",
 "processLutsSha256":"dea370ecbf043da03a4af8a7d126d930caf8364f2c806e96a15b2dcb78fcab96",
 "savedJpegToning":True,
 "livePreviewToning":True,
 "dngToning":False,
 "offBitExactGray":True,
 "conversion":"JFIF_BT601_YCrCb_code_domain_inverse",
 "genericPhotonSaturationUsed":False,
 "genericPhotonColorUsed":False,
 "contrastControlPreserved":True,
 "frozenPolicyHashes":after
}
(root/"LEICATONING1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
