#!/usr/bin/env python3
"""Apply LEICACONTRAST1A to an assembled modern Monochrom source tree."""
from pathlib import Path
import hashlib, json, re, sys
import xml.etree.ElementTree as ET

if len(sys.argv) != 2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root = Path(sys.argv[1]).resolve()

pref_xml = root / "app/src/main/res/xml/preferences.xml"
keys_xml = root / "app/src/main/res/values/preference_keys.xml"
arrays_xml = root / "app/src/main/res/values/arrays.xml"
strings_xml = root / "app/src/main/res/values/strings.xml"
pref_java = root / "app/src/main/java/com/particlesdevs/photoncamera/settings/PreferenceKeys.java"
renderer = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
native_java = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java"
native_cpp = root / "app/src/main/cpp/m9color_jni.cpp"
preview_java = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java"
main_renderer = root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java"
curve_inc = root / "app/src/main/cpp/mm_monochrom_contrast_curves.inc"
curve_asset = root / "app/src/main/assets/mono/mono_contrast_curves.bin"
curve_meta = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/render/MonoContrastCurves1A.java"
gradle = root / "app/build.gradle"
required = [pref_xml, keys_xml, arrays_xml, strings_xml, pref_java, renderer, native_java,
            native_cpp, preview_java, main_renderer, curve_inc, curve_asset, curve_meta, gradle]
for p in required:
    if not p.is_file():
        raise SystemExit("LEICACONTRAST1A missing " + str(p))

bank = curve_asset.read_bytes()
if len(bank) != 5 * 2048:
    raise SystemExit("LEICACONTRAST1A curve bank length mismatch")
standard = bank[2*2048:3*2048]
if hashlib.sha256(standard).hexdigest() != "7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752":
    raise SystemExit("LEICACONTRAST1A Standard curve02 mismatch")

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"LEICACONTRAST1A {label} anchor count={n}")
    return text.replace(old, new, 1)

def append_resource(path, fragment):
    s = path.read_text()
    if fragment.splitlines()[0] in s:
        raise SystemExit("LEICACONTRAST1A resource already applied: " + str(path))
    s = one(s, "</resources>", fragment + "\n</resources>", path.name)
    path.write_text(s)

# ----- resources / modern Settings UI -----
append_resource(keys_xml, """    <string name="pref_category_monochrom_key" translatable="false">pref_category_monochrom_key</string>
    <string name="pref_mono_contrast_key" translatable="false">pref_mono_contrast_key</string>""")

append_resource(strings_xml, """    <string name="leica_m_monochrom_settings">Leica M Monochrom</string>
    <string name="mono_contrast">Contrast</string>
    <string name="mono_contrast_summary">Original M Monochrom firmware tone curve</string>""")

append_resource(arrays_xml, """    <string-array name="mono_contrast_entries">
        <item>Low</item>
        <item>Medium low</item>
        <item>Standard</item>
        <item>Medium high</item>
        <item>High</item>
    </string-array>
    <string-array name="mono_contrast_entryvalues">
        <item>0</item>
        <item>1</item>
        <item>2</item>
        <item>3</item>
        <item>4</item>
    </string-array>""")

ANDROID = "http://schemas.android.com/apk/res/android"
APP = "http://schemas.android.com/apk/res-auto"
ET.register_namespace("android", ANDROID)
ET.register_namespace("app", APP)
akey = "{" + ANDROID + "}key"
tree = ET.parse(pref_xml)
screen = tree.getroot()
if any(n.attrib.get(akey) == "@string/pref_category_monochrom_key" for n in list(screen)):
    raise SystemExit("LEICACONTRAST1A preference category already present")
general_index = None
for i, node in enumerate(list(screen)):
    if node.attrib.get(akey) == "@string/pref_category_general_key":
        general_index = i
        break
if general_index is None:
    raise SystemExit("LEICACONTRAST1A General category missing")

cat = ET.Element("PreferenceCategory", {
    "{" + ANDROID + "}layout": "@layout/preference_category_layout",
    akey: "@string/pref_category_monochrom_key",
    "{" + ANDROID + "}title": "@string/leica_m_monochrom_settings",
})
ET.SubElement(cat, "ListPreference", {
    "{" + ANDROID + "}layout": "@layout/preference_with_margin",
    akey: "@string/pref_mono_contrast_key",
    "{" + ANDROID + "}title": "@string/mono_contrast",
    "{" + ANDROID + "}summary": "@string/mono_contrast_summary",
    "{" + ANDROID + "}icon": "@drawable/ic_gradient_black_24dp",
    "{" + ANDROID + "}entries": "@array/mono_contrast_entries",
    "{" + ANDROID + "}entryValues": "@array/mono_contrast_entryvalues",
    "{" + ANDROID + "}defaultValue": "2",
    "{" + APP + "}useSimpleSummaryProvider": "true",
})
screen.insert(general_index + 1, cat)
ET.indent(tree, space="    ")
tree.write(pref_xml, encoding="utf-8", xml_declaration=True)

# ----- PreferenceKeys: global Leica setting, default Standard -----
s = pref_java.read_text()
s = one(s,
    "        COMMON_KEYS.add(Key.KEY_SAVE_RAW.mValue);\n",
    "        COMMON_KEYS.add(Key.KEY_SAVE_RAW.mValue);\n"
    "        COMMON_KEYS.add(Key.KEY_MONO_CONTRAST.mValue);\n",
    "global Contrast key")
s = one(s,
    "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_AE_METERING_STD, -1); // Default to Off\n",
    "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_AE_METERING_STD, -1); // Default to Off\n"
    "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_CONTRAST, 2); // Leica Standard\n",
    "Contrast default")
s = one(s,
    """    public static float getContrastValue() {
        return preferenceKeys.settingsManager.getFloat(SCOPE_GLOBAL, Key.KEY_CONTRAST_SEEKBAR);
    }
""",
    """    public static float getContrastValue() {
        return preferenceKeys.settingsManager.getFloat(SCOPE_GLOBAL, Key.KEY_CONTRAST_SEEKBAR);
    }

    /** Leica M Monochrom Contrast enum: 0 Low .. 4 High; Standard = 2. */
    public static int getMonoContrastValue() {
        int value = preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_CONTRAST);
        return value < 0 ? 0 : (value > 4 ? 4 : value);
    }
""",
    "Contrast getter")
s = one(s,
    "        KEY_CONTRAST_SEEKBAR(R.string.pref_contrast_seekbar_key),\n",
    "        KEY_CONTRAST_SEEKBAR(R.string.pref_contrast_seekbar_key),\n"
    "        KEY_MONO_CONTRAST(R.string.pref_mono_contrast_key),\n",
    "Contrast enum key")
pref_java.write_text(s)

# ----- JNI production RAWSCALAR path -----
s = native_java.read_text()
s = one(s,
    """                                                                  float neutralR, float neutralG, float neutralB,
                                                                  double representationScale, long[] stats);
""",
    """                                                                  float neutralR, float neutralG, float neutralB,
                                                                  double representationScale, int contrastSelector,
                                                                  long[] stats);
""",
    "RAWSCALAR JNI declaration")
native_java.write_text(s)

s = renderer.read_text()
s = one(s,
    """        Bitmap rawScalar1ABitmap = null;
        Bitmap rawScalar1BBitmap = null;
""",
    """        final int monoContrast1A = MonoContrastCurves1A.clamp(
                com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoContrastValue());
        Bitmap rawScalar1ABitmap = null;
        Bitmap rawScalar1BBitmap = null;
""",
    "renderer Contrast selection")
s = one(s,
    "                    nativeShading.representationScale, rawScalar1AStats);\n",
    "                    nativeShading.representationScale, MonoContrastCurves1A.DEFAULT, rawScalar1AStats);\n",
    "RAWSCALAR diagnostic Standard")
s = one(s,
    "                    nativeShading.representationScale, rawScalar1BStats);\n",
    "                    nativeShading.representationScale, monoContrast1A, rawScalar1BStats);\n",
    "RAWSCALAR primary selected Contrast")
s = one(s,
    '                rawScalar1B.put("curve", "same_frozen_Monochrom_curve02");\n'
    '                rawScalar1B.put("curve02Sha256", "7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752");\n',
    '                rawScalar1B.put("curve", "firmware_normalISO_sRGB_curve0" + monoContrast1A);\n'
    '                rawScalar1B.put("contrastEnum", monoContrast1A);\n'
    '                rawScalar1B.put("contrastLabel", MonoContrastCurves1A.LABELS[monoContrast1A]);\n'
    '                rawScalar1B.put("contrastCurveSha256", MonoContrastCurves1A.SHA256[monoContrast1A]);\n'
    '                rawScalar1B.put("standardCurve02Sha256", MonoContrastCurves1A.SHA256[2]);\n',
    "RAWSCALAR Contrast diagnostics")
s = one(s,
    '                d.put("monochromTargetTone", "canonical_M_Monochrom_curve02_frozen");\n',
    '                d.put("monochromTargetTone", "firmware_normalISO_sRGB_curve0" + monoContrast1A);\n'
    '                d.put("monochromContrastEnum", monoContrast1A);\n'
    '                d.put("monochromContrastLabel", MonoContrastCurves1A.LABELS[monoContrast1A]);\n'
    '                d.put("monochromContrastCurveSha256", MonoContrastCurves1A.SHA256[monoContrast1A]);\n',
    "primary Contrast telemetry")
renderer.write_text(s)

s = native_cpp.read_text()
if '#include "mm_monochrom_contrast_curves.inc"' in s:
    raise SystemExit("LEICACONTRAST1A native include already present")
s = one(s,
    "// SOURCE1E RAWSCALAR1A. Xiaomi CFA-to-scalar adapter; not Leica CCD spectral truth.\n",
    '#include "mm_monochrom_contrast_curves.inc"\n\n'
    "// LEICACONTRAST1A selects only the firmware tone table; Process_Contrast mode remains native 100% mode 0.\n"
    "// SOURCE1E RAWSCALAR1A. Xiaomi CFA-to-scalar adapter; not Leica CCD spectral truth.\n",
    "native contrast include")
s = one(s,
    """        jfloat neutralR, jfloat neutralG, jfloat neutralB, jdouble representationScale,
        jlongArray statsArray) {
""",
    """        jfloat neutralR, jfloat neutralG, jfloat neutralB, jdouble representationScale,
        jint contrastSelector, jlongArray statsArray) {
""",
    "RAWSCALAR native signature")
s = one(s,
    """    const double invR=static_cast<double>(neutralG)/static_cast<double>(neutralR);
    const double invB=static_cast<double>(neutralG)/static_cast<double>(neutralB);
""",
    """    const int monoContrast=std::max(0,std::min(4,static_cast<int>(contrastSelector)));
    const uint8_t* contrastCurve=MM_MONO_CONTRAST_CURVES[monoContrast];
    const double invR=static_cast<double>(neutralG)/static_cast<double>(neutralR);
    const double invB=static_cast<double>(neutralG)/static_cast<double>(neutralB);
""",
    "RAWSCALAR contrast pointer")
s = one(s,
    "int32_t idx=v>>3;if(idx>2047)idx=2047;const uint8_t yy=MM_MONO1A_CURVE02[idx];if(yy>=250)near++;",
    "int32_t idx=v>>3;if(idx>2047)idx=2047;const uint8_t yy=contrastCurve[idx];if(yy>=250)near++;",
    "RAWSCALAR selected curve")
native_cpp.write_text(s)

# ----- live preview: same selected firmware curve, immediate preference response -----
s = preview_java.read_text()
s = one(s,
    '    public static final String CURVE_SHA="7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752";\n',
    '    public static final String CURVE_SHA="7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752";\n'
    '    private static volatile int selectedContrast=2;\n'
    '    private static volatile String selectedContrastSha=CURVE_SHA;\n',
    "preview Contrast evidence fields")
s = one(s,
    "    private MonoGpuPreview2A() {}\n",
    """    private MonoGpuPreview2A() {}

    public static void setLeicaContrastSelection(int selector, String sha256) {
        selectedContrast = selector < 0 ? 0 : (selector > 4 ? 4 : selector);
        selectedContrastSha = sha256 == null ? CURVE_SHA : sha256;
    }
""",
    "preview Contrast setter")
s = one(s,
    '            o.put("firmwareCurveEligible",ready).put("curve02Sha256",CURVE_SHA);\n',
    '            o.put("firmwareCurveEligible",ready).put("curve02Sha256",CURVE_SHA);\n'
    '            o.put("leicaContrastEnum",selectedContrast);\n'
    '            o.put("leicaContrastLabel",com.particlesdevs.photoncamera.m9.render.MonoContrastCurves1A.LABELS[selectedContrast]);\n'
    '            o.put("leicaContrastCurveSha256",selectedContrastSha);\n',
    "preview Contrast diagnostics")
preview_java.write_text(s)

s = main_renderer.read_text()
s = one(s,
    "    private int monoProgram2A, monoInverseTex2A, monoCurveTex2A;\n",
    "    private int monoProgram2A, monoInverseTex2A, monoCurveTex2A;\n"
    "    private byte[] monoContrastBank1A;\n"
    "    private int monoContrastSelector1A=-1;\n",
    "preview bank fields")

old_loader = '''        try(java.io.InputStream in=mView.getContext().getAssets().open("mono/mono_curve02_gl2a.bin")) {
            byte[] data=new byte[2048]; int offset=0,n;
            while(offset<data.length && (n=in.read(data,offset,data.length-offset))>0) offset+=n;
            if(offset!=2048 || in.read()!=-1) throw new java.io.IOException("curve_length");
            byte[] hash=java.security.MessageDigest.getInstance("SHA-256").digest(data);
            StringBuilder text=new StringBuilder(); for(byte b:hash) text.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
            if(!text.toString().equals(com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.CURVE_SHA))
                throw new java.io.IOException("curve_checksum");
            ByteBuffer bytes=ByteBuffer.allocateDirect(2048); bytes.put(data).position(0);
            GLES30.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES30.GL_R8,2048,1,0,GLES30.GL_RED,
                    GLES20.GL_UNSIGNED_BYTE,bytes);
            int curveError=GLES20.glGetError();
            if(curveError!=GLES20.GL_NO_ERROR) throw new java.io.IOException("curve_GL_error_"+curveError);
            monoCurveLoaded2A=true;
        } catch(Exception e) { Log.e("MonoGL2A","curve unavailable: "+e); }
'''
new_loader = '''        try(java.io.InputStream in=mView.getContext().getAssets().open("mono/mono_contrast_curves.bin")) {
            byte[] data=new byte[5*2048]; int offset=0,n;
            while(offset<data.length && (n=in.read(data,offset,data.length-offset))>0) offset+=n;
            if(offset!=data.length || in.read()!=-1) throw new java.io.IOException("contrast_bank_length");
            byte[] hash=java.security.MessageDigest.getInstance("SHA-256").digest(data);
            StringBuilder text=new StringBuilder(); for(byte b:hash) text.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
            if(!text.toString().equals(com.particlesdevs.photoncamera.m9.render.MonoContrastCurves1A.BANK_SHA256))
                throw new java.io.IOException("contrast_bank_checksum");
            monoContrastBank1A=data;
            monoContrastSelector1A=-1;
        } catch(Exception e) { monoContrastBank1A=null; Log.e("MonoGL2A","contrast bank unavailable: "+e); }
'''
s = one(s, old_loader, new_loader, "preview curve loader")

old_ready = '''        boundSourceReady2A=c.ready && monoCurveLoaded2A && boundContext2A==c;
        GLES20.glUniform1i(monoReady2A,boundSourceReady2A?1:0);
        GLES20.glActiveTexture(GLES20.GL_TEXTURE2); GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,monoCurveTex2A);
'''
new_ready = '''        GLES20.glActiveTexture(GLES20.GL_TEXTURE2); GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,monoCurveTex2A);
        int selectedContrast1A=com.particlesdevs.photoncamera.m9.render.MonoContrastCurves1A.clamp(
                com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoContrastValue());
        if(monoContrastBank1A!=null && selectedContrast1A!=monoContrastSelector1A) {
            ByteBuffer bytes=ByteBuffer.allocateDirect(2048);
            bytes.put(monoContrastBank1A,selectedContrast1A*2048,2048).position(0);
            GLES30.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES30.GL_R8,2048,1,0,GLES30.GL_RED,
                    GLES20.GL_UNSIGNED_BYTE,bytes);
            int curveError=GLES20.glGetError();
            if(curveError==GLES20.GL_NO_ERROR) {
                monoContrastSelector1A=selectedContrast1A;
                monoCurveLoaded2A=true;
                com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.setLeicaContrastSelection(
                        selectedContrast1A,
                        com.particlesdevs.photoncamera.m9.render.MonoContrastCurves1A.SHA256[selectedContrast1A]);
            } else {
                monoCurveLoaded2A=false;
                probeError2A="contrast_curve_GL_error_"+curveError;
            }
        }
        boundSourceReady2A=c.ready && monoCurveLoaded2A && boundContext2A==c;
        GLES20.glUniform1i(monoReady2A,boundSourceReady2A?1:0);
'''
s = one(s, old_ready, new_ready, "preview selected Contrast upload")
main_renderer.write_text(s)

# Build identity only.
s = gradle.read_text()
m = re.search(r"versionName\s+'([^']+)'", s)
if not m:
    raise SystemExit("LEICACONTRAST1A versionName missing")
if "leicacontrast1a" not in m.group(1):
    s = s[:m.start(1)] + m.group(1) + "-leicacontrast1a" + s[m.end(1):]
gradle.write_text(s)

proof = {
    "revision": "LEICACONTRAST1A",
    "target": "Leica M Monochrom 1.022",
    "menu": ["Low", "Medium low", "Standard", "Medium high", "High"],
    "menuEnum": [0,1,2,3,4],
    "default": 2,
    "processContrastMode": 0,
    "processContrastModeMeaning": "native_100_percent_resolution",
    "selector": "normal_ISO_sRGB_curve_index_equals_nContrast",
    "firmwareCurveBankBytes": len(bank),
    "firmwareCurveBankSha256": hashlib.sha256(bank).hexdigest(),
    "standardCurve02Sha256": hashlib.sha256(standard).hexdigest(),
    "jpegUsesSelectedCurve": True,
    "previewUsesSelectedCurve": True,
    "dngToneChanged": False,
    "genericPhotonContrastUsed": False,
    "sharpnessChanged": False,
    "toningChanged": False,
}
(root / "LEICACONTRAST1A_ISOLATION.json").write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
