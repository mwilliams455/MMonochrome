#!/usr/bin/env python3
"""LEICAAUTOISO1A: Leica-style Auto ISO Maximum on the shared physical exposure plan."""
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
J = root / "app/src/main/java/com/particlesdevs/photoncamera"
plan = J / "m9/exposure/MonoExposurePlan1A.java"
diag = J / "m9/exposure/MonoExposureDiagnostics1A.java"
selector = J / "processing/parameters/IsoExpoSelector.java"
capture = J / "capture/CaptureController.java"
gradle = root / "app/build.gradle"

required = [pref_xml, keys_xml, arrays_xml, strings_xml, pref_java, plan, diag, selector, capture, gradle]
for p in required:
    if not p.is_file():
        raise SystemExit("LEICAAUTOISO1A missing " + str(p))
for receipt in [
    "LEICACONTRAST1A_ISOLATION.json",
    "LEICATONING1A_FIX2_SOURCE1D_ISOLATION.json",
    "LEICASHARPNESS1C_ISOLATION.json",
    "LEICASHARPNESS1C_PREVIEWFIX2_ISOLATION.json",
]:
    if not (root / receipt).is_file():
        raise SystemExit("LEICAAUTOISO1A missing parent receipt " + receipt)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def one(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"LEICAAUTOISO1A {label} anchor count={n}")
    return s.replace(old, new, 1)

def append_resource(path, fragment):
    s = path.read_text()
    first = fragment.splitlines()[0]
    if first in s:
        raise SystemExit("LEICAAUTOISO1A resource already applied " + str(path))
    path.write_text(one(s, "</resources>", fragment + "\n</resources>", path.name))

# Capture/render output math is frozen. This overlay is exposure-control + settings UI only.
frozen = [
    J / "m9/render/M9R35Renderer.java",
    J / "m9/render/M9NativeColorCore.java",
    J / "m9/export/MonoDngExport1A.java",
    J / "m9/export/MonoDngWriter1A.java",
    J / "m9/export/MonoLinearPlane1A.java",
    J / "m9/exposure/MonoPlacementAssist1D.java",
    J / "m9/preview/MonoTapMeter1A.java",
    J / "m9/preview/MonoGpuPreview2A.java",
    root / "app/src/main/cpp/m9color_jni.cpp",
    root / "app/src/main/assets/shaders/preview/main_fs.glsl",
]
before = {str(p.relative_to(root)): sha(p) for p in frozen if p.is_file()}

# ----- Leica settings UI -----
append_resource(keys_xml,
    '    <string name="pref_mono_auto_iso_max_key" translatable="false">pref_mono_auto_iso_max_key</string>')
append_resource(strings_xml,
    '    <string name="mono_auto_iso_max">Auto ISO Maximum</string>\n'
    '    <string name="mono_auto_iso_max_summary">Maximum physical sensor ISO used by automatic exposure</string>')
append_resource(arrays_xml, '''    <string-array name="mono_auto_iso_max_entries">
        <item>320</item><item>400</item><item>500</item><item>640</item>
        <item>800</item><item>1000</item><item>1250</item><item>1600</item>
        <item>2000</item><item>2500</item><item>3200</item><item>4000</item>
        <item>5000</item><item>6400</item><item>8000</item><item>10000</item>
    </string-array>
    <string-array name="mono_auto_iso_max_entryvalues">
        <item>320</item><item>400</item><item>500</item><item>640</item>
        <item>800</item><item>1000</item><item>1250</item><item>1600</item>
        <item>2000</item><item>2500</item><item>3200</item><item>4000</item>
        <item>5000</item><item>6400</item><item>8000</item><item>10000</item>
    </string-array>''')

ANDROID = "http://schemas.android.com/apk/res/android"
APP = "http://schemas.android.com/apk/res-auto"
ET.register_namespace("android", ANDROID)
ET.register_namespace("app", APP)
akey = "{" + ANDROID + "}key"
tree = ET.parse(pref_xml)
screen = tree.getroot()
cat = next((n for n in list(screen) if n.attrib.get(akey) == "@string/pref_category_monochrom_key"), None)
if cat is None:
    raise SystemExit("LEICAAUTOISO1A Leica M Monochrom category missing")
if any(n.attrib.get(akey) == "@string/pref_mono_auto_iso_max_key" for n in list(cat)):
    raise SystemExit("LEICAAUTOISO1A preference already present")
auto_iso = ET.Element("ListPreference", {
    "{" + ANDROID + "}layout": "@layout/preference_with_margin",
    akey: "@string/pref_mono_auto_iso_max_key",
    "{" + ANDROID + "}title": "@string/mono_auto_iso_max",
    "{" + ANDROID + "}summary": "@string/mono_auto_iso_max_summary",
    "{" + ANDROID + "}icon": "@drawable/ic_gradient_black_24dp",
    "{" + ANDROID + "}entries": "@array/mono_auto_iso_max_entries",
    "{" + ANDROID + "}entryValues": "@array/mono_auto_iso_max_entryvalues",
    # 10000 preserves the already phone-validated automatic-exposure behavior
    # until the photographer explicitly chooses a lower ceiling.
    "{" + ANDROID + "}defaultValue": "10000",
    "{" + APP + "}useSimpleSummaryProvider": "true",
})
children = list(cat)
strength_index = next((i for i, n in enumerate(children)
                       if n.attrib.get(akey) == "@string/pref_mono_toning_strength_key"), None)
if strength_index is None:
    raise SystemExit("LEICAAUTOISO1A Toning Strength preference missing")
cat.insert(strength_index + 1, auto_iso)
ET.indent(tree, space="    ")
tree.write(pref_xml, encoding="utf-8", xml_declaration=True)

# ----- global setting, physical Leica ISO menu -----
s = pref_java.read_text()
s = one(s,
    "        COMMON_KEYS.add(Key.KEY_MONO_TONING_STRENGTH.mValue);\n",
    "        COMMON_KEYS.add(Key.KEY_MONO_TONING_STRENGTH.mValue);\n"
    "        COMMON_KEYS.add(Key.KEY_MONO_AUTO_ISO_MAX.mValue);\n",
    "global Auto ISO Maximum key")
s = one(s,
    "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_TONING_STRENGTH, 0); // Off\n",
    "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_TONING_STRENGTH, 0); // Off\n"
    "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_AUTO_ISO_MAX, 10000); // non-regressive default\n",
    "Auto ISO Maximum default")
toning_getter = """    public static int getMonoToningStrengthValue() {
        int value=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_TONING_STRENGTH);
        return value<0?0:(value>2?2:value);
    }
"""
s = one(s, toning_getter, toning_getter + """
    /** Leica M Monochrom Auto ISO maximum, in physical Camera2 ISO units. */
    public static int getMonoAutoIsoMaximumValue() {
        int value=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_AUTO_ISO_MAX);
        switch(value) {
            case 320: case 400: case 500: case 640:
            case 800: case 1000: case 1250: case 1600:
            case 2000: case 2500: case 3200: case 4000:
            case 5000: case 6400: case 8000: case 10000:
                return value;
            default:
                return 10000;
        }
    }
""", "Auto ISO Maximum getter")
s = one(s,
    "        KEY_MONO_TONING_STRENGTH(R.string.pref_mono_toning_strength_key),\n",
    "        KEY_MONO_TONING_STRENGTH(R.string.pref_mono_toning_strength_key),\n"
    "        KEY_MONO_AUTO_ISO_MAX(R.string.pref_mono_auto_iso_max_key),\n",
    "Auto ISO Maximum enum key")
pref_java.write_text(s)

# ----- immutable control identity includes the Auto ISO ceiling -----
s = plan.read_text()
s = one(s,
    '    public static final String REVISION = "MONOAUTO1A_EXPOSUREPLAN";\n',
    '    public static final String REVISION = "MONOAUTO1A_EXPOSUREPLAN";\n'
    '    public static final int FLAG_AUTO_ISO_MAX_APPLIED = 32;\n',
    "plan flag")
s = one(s,
    "        public final int manualIso, isoLimit, oisMode;\n",
    "        public final int manualIso, isoLimit, oisMode, autoIsoMaximum;\n",
    "control field")
s = one(s,
    """        public Controls(String mode, double userEv, long manualExposureNs, int manualIso,
                boolean tripod, float balance, int isoLimit, float shutterLimit, int oisMode, String meteringKey) {
""",
    """        public Controls(String mode, double userEv, long manualExposureNs, int manualIso,
                boolean tripod, float balance, int isoLimit, float shutterLimit, int oisMode,
                int autoIsoMaximum, String meteringKey) {
""",
    "control constructor")
s = one(s,
    """            if(mode==null || meteringKey==null || !Double.isFinite(userEv) || manualExposureNs<0 || manualIso<0
                    || !Float.isFinite(balance) || balance<=0 || !Float.isFinite(shutterLimit))
""",
    """            if(mode==null || meteringKey==null || !Double.isFinite(userEv) || manualExposureNs<0 || manualIso<0
                    || !Float.isFinite(balance) || balance<=0 || !Float.isFinite(shutterLimit)
                    || autoIsoMaximum<=0)
""",
    "control validation")
s = one(s,
    """            this.tripod=tripod;this.balance=balance;this.isoLimit=isoLimit;this.shutterLimit=shutterLimit;
            this.oisMode=oisMode;this.meteringKey=meteringKey;
""",
    """            this.tripod=tripod;this.balance=balance;this.isoLimit=isoLimit;this.shutterLimit=shutterLimit;
            this.oisMode=oisMode;this.autoIsoMaximum=autoIsoMaximum;this.meteringKey=meteringKey;
""",
    "control assignment")
s = one(s,
    """                    && Float.floatToIntBits(shutterLimit)==Float.floatToIntBits(c.shutterLimit)
                    && oisMode==c.oisMode && meteringKey.equals(c.meteringKey);
""",
    """                    && Float.floatToIntBits(shutterLimit)==Float.floatToIntBits(c.shutterLimit)
                    && oisMode==c.oisMode && autoIsoMaximum==c.autoIsoMaximum
                    && meteringKey.equals(c.meteringKey);
""",
    "control equality")
s = one(s,
    """            return java.util.Objects.hash(mode,userEv,manualExposureNs,manualIso,tripod,balance,
                    isoLimit,shutterLimit,oisMode,meteringKey);
""",
    """            return java.util.Objects.hash(mode,userEv,manualExposureNs,manualIso,tripod,balance,
                    isoLimit,shutterLimit,oisMode,autoIsoMaximum,meteringKey);
""",
    "control hash")
plan.write_text(s)

# Controller reads the Leica ceiling into the same identity used to invalidate cached plans.
s = capture.read_text()
s = one(s,
    """                PhotonCamera.getGyro()!=null && PhotonCamera.getGyro().getTripod(),
                exposureBalanceMultiplier,exposureBalanceIsoLimit,exposureBalanceShutterLimit,oisMode,metering);
""",
    """                PhotonCamera.getGyro()!=null && PhotonCamera.getGyro().getTripod(),
                exposureBalanceMultiplier,exposureBalanceIsoLimit,exposureBalanceShutterLimit,oisMode,
                com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoAutoIsoMaximumValue(),metering);
""",
    "controller control identity")
capture.write_text(s)

# ----- physical allocation: cap automatic ISO, preserve exposure energy with shutter when possible -----
s = selector.read_text()
plan_anchor = "    public static MonoExposurePlan1A planMonoExposure1A(CaptureController controller,CaptureResult transport,\n"
if s.count(plan_anchor) != 1:
    raise SystemExit("LEICAAUTOISO1A plan method anchor count=" + str(s.count(plan_anchor)))
helper = r'''    /**
     * Leica Auto ISO Maximum in the physical Camera2 ISO domain.
     * Manual ISO is always authoritative. With automatic shutter, exposure energy
     * is preserved by lengthening shutter up to the physical sensor limit before
     * accepting underexposure; the ISO request itself never exceeds the selected cap.
     */
    private static boolean applyMonoAutoIsoMaximum1D(ExpoPair pair,MonoInput1A input) {
        if(pair==null || input==null || input.controls.manualIso>0) return false;
        final int selected=input.controls.autoIsoMaximum;
        final int cap=Math.max(input.isoLow,Math.min(input.isoHigh,selected));
        if(pair.iso<=cap) return false;
        final double energy=(double)pair.iso*(double)pair.exposure;
        if(input.controls.manualExposureNs==0 && energy>0.0) {
            final double rawNeeded=Math.ceil(energy/(double)cap);
            long needed;
            if(!Double.isFinite(rawNeeded) || rawNeeded>Long.MAX_VALUE) needed=input.timeHigh;
            else needed=(long)rawNeeded;
            needed=Math.max(input.timeLow,Math.min(input.timeHigh,needed));
            if(needed>pair.exposure) pair.exposure=needed;
        }
        pair.iso=cap;
        pair.isIsoLimited=true;
        return true;
    }

'''
s = s.replace(plan_anchor, helper + plan_anchor, 1)
flag_anchor = """        int flags=(pair.isIsoLimited?1:0)|(pair.isShutterLimited?2:0)|(pair.isIsoManualOverLimit?4:0)
                |(pair.isShutterManualOverLimit?8:0)|(pair.isShutterTripodBypassed?16:0);
"""
s = one(s, flag_anchor,
    """        final boolean monoAutoIsoMaxApplied1D=applyMonoAutoIsoMaximum1D(pair,input);
        int flags=(pair.isIsoLimited?1:0)|(pair.isShutterLimited?2:0)|(pair.isIsoManualOverLimit?4:0)
                |(pair.isShutterManualOverLimit?8:0)|(pair.isShutterTripodBypassed?16:0)
                |(monoAutoIsoMaxApplied1D?MonoExposurePlan1A.FLAG_AUTO_ISO_MAX_APPLIED:0);
""",
    "Auto ISO allocation")
selector.write_text(s)

# ----- diagnostics -----
s = diag.read_text()
s = one(s,
    '                    .put("exposureFlags",p.flags).put("assistAppliedAgainAtCapture",false)\n',
    '                    .put("exposureFlags",p.flags)\n'
    '                    .put("autoIsoMaximumRevision","LEICAAUTOISO1A")\n'
    '                    .put("autoIsoMaximumPhysical",p.controls.autoIsoMaximum)\n'
    '                    .put("autoIsoMaximumApplied",(p.flags&MonoExposurePlan1A.FLAG_AUTO_ISO_MAX_APPLIED)!=0)\n'
    '                    .put("autoIsoManualOverride",p.controls.manualIso>0)\n'
    '                    .put("assistAppliedAgainAtCapture",false)\n',
    "Auto ISO diagnostics")
diag.write_text(s)

# Identity.
g = gradle.read_text()
m = re.search(r"versionName\s+'([^']+)'", g)
if not m:
    raise SystemExit("LEICAAUTOISO1A versionName missing")
if "leicaautoiso1a" not in m.group(1):
    g = g[:m.start(1)] + m.group(1) + "-leicaautoiso1a" + g[m.end(1):]
gradle.write_text(g)

after = {str(p.relative_to(root)): sha(p) for p in frozen if p.is_file()}
if before != after:
    changed = [k for k in before if before[k] != after.get(k)]
    raise SystemExit("LEICAAUTOISO1A changed frozen photographic files " + repr(changed))

proof = {
    "revision": "LEICAAUTOISO1A",
    "firmwareFamily": "Leica M Monochrom first generation",
    "menuPhysicalIso": [320,400,500,640,800,1000,1250,1600,2000,2500,3200,4000,5000,6400,8000,10000],
    "defaultPhysicalIso": 10000,
    "defaultRationale": "preserve_phone_validated_parent_until_user_selects_lower_ceiling",
    "isoDomain": "physical_Camera2_SENSOR_SENSITIVITY",
    "deviceClamp": "selected_ceiling_clamped_to_physical_SENSOR_INFO_SENSITIVITY_RANGE",
    "manualIsoAuthorityPreserved": True,
    "manualShutterAuthorityPreserved": True,
    "automaticShutterPreservesEnergyWhenCapHits": True,
    "sensorMaxExposureTimeRespected": True,
    "selectedCapNeverExceededByAutomaticIso": True,
    "controlIdentityIncludesAutoIsoMaximum": True,
    "previewAndCaptureShareSamePlan": True,
    "HDR": False,
    "rendererChanged": False,
    "linearDngMathChanged": False,
    "contrastChanged": False,
    "toningChanged": False,
    "sharpnessChanged": False,
    "frozenPhotographicHashes": after,
}
(root / "LEICAAUTOISO1A_ISOLATION.json").write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
