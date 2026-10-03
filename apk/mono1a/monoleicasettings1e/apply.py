#!/usr/bin/env python3
"""LEICASLOWEST1A: first-generation Leica M Monochrom Auto ISO Slowest speed control."""
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
        raise SystemExit("LEICASLOWEST1A missing " + str(p))
for receipt in [
    "LEICAAUTOISO1A_ISOLATION.json",
    "LEICACONTRAST1A_ISOLATION.json",
    "LEICATONING1A_FIX2_SOURCE1D_ISOLATION.json",
    "LEICASHARPNESS1C_ISOLATION.json",
]:
    if not (root / receipt).is_file():
        raise SystemExit("LEICASLOWEST1A missing parent receipt " + receipt)

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def one(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f"LEICASLOWEST1A {label} anchor count={n}")
    return s.replace(old, new, 1)

def append_resource(path, fragment):
    s = path.read_text()
    first = fragment.splitlines()[0]
    if first in s:
        raise SystemExit("LEICASLOWEST1A resource already applied " + str(path))
    path.write_text(one(s, "</resources>", fragment + "\n</resources>", path.name))

# Render/output math remains frozen. This overlay changes exposure allocation + settings only.
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

# ----- Exact first-generation M Monochrom menu surface -----
# Original manual: Lens dependent (1/focal-length) or a fixed slowest speed
# from 1/125s through 1/8s in whole stops.
append_resource(keys_xml,
    '    <string name="pref_mono_slowest_speed_key" translatable="false">pref_mono_slowest_speed_key</string>')
append_resource(strings_xml,
    '    <string name="mono_slowest_speed">Slowest speed</string>\n'
    '    <string name="mono_slowest_speed_summary">Auto ISO shutter threshold</string>')
append_resource(arrays_xml, '''    <string-array name="mono_slowest_speed_entries">
        <item>Lens dependent</item>
        <item>1/125 s</item>
        <item>1/60 s</item>
        <item>1/30 s</item>
        <item>1/15 s</item>
        <item>1/8 s</item>
    </string-array>
    <string-array name="mono_slowest_speed_entryvalues">
        <item>0</item><item>1</item><item>2</item><item>3</item><item>4</item><item>5</item>
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
    raise SystemExit("LEICASLOWEST1A Leica M Monochrom category missing")
if any(n.attrib.get(akey) == "@string/pref_mono_slowest_speed_key" for n in list(cat)):
    raise SystemExit("LEICASLOWEST1A preference already present")
slow = ET.Element("ListPreference", {
    "{" + ANDROID + "}layout": "@layout/preference_with_margin",
    akey: "@string/pref_mono_slowest_speed_key",
    "{" + ANDROID + "}title": "@string/mono_slowest_speed",
    "{" + ANDROID + "}summary": "@string/mono_slowest_speed_summary",
    "{" + ANDROID + "}icon": "@drawable/ic_gradient_black_24dp",
    "{" + ANDROID + "}entries": "@array/mono_slowest_speed_entries",
    "{" + ANDROID + "}entryValues": "@array/mono_slowest_speed_entryvalues",
    # Lens dependent is the characteristic Leica 1/focal-length mode.
    "{" + ANDROID + "}defaultValue": "0",
    "{" + APP + "}useSimpleSummaryProvider": "true",
})
children = list(cat)
auto_iso_index = next((i for i, n in enumerate(children)
                       if n.attrib.get(akey) == "@string/pref_mono_auto_iso_max_key"), None)
if auto_iso_index is None:
    raise SystemExit("LEICASLOWEST1A Auto ISO Maximum preference missing")
cat.insert(auto_iso_index + 1, slow)
ET.indent(tree, space="    ")
tree.write(pref_xml, encoding="utf-8", xml_declaration=True)

# ----- preference plumbing -----
s = pref_java.read_text()
s = one(s,
    "        COMMON_KEYS.add(Key.KEY_MONO_AUTO_ISO_MAX.mValue);\n",
    "        COMMON_KEYS.add(Key.KEY_MONO_AUTO_ISO_MAX.mValue);\n"
    "        COMMON_KEYS.add(Key.KEY_MONO_SLOWEST_SPEED.mValue);\n",
    "global slowest speed key")
s = one(s,
    "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_AUTO_ISO_MAX, 10000); // non-regressive default\n",
    "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_AUTO_ISO_MAX, 10000); // non-regressive default\n"
    "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_SLOWEST_SPEED, 0); // Lens dependent\n",
    "slowest speed default")
autoiso_getter = """    public static int getMonoAutoIsoMaximumValue() {
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
"""
s = one(s, autoiso_getter, autoiso_getter + """
    /** First-generation Leica M Monochrom Slowest speed enum.
     * 0 Lens dependent (1/f), 1 1/125, 2 1/60, 3 1/30, 4 1/15, 5 1/8.
     */
    public static int getMonoSlowestSpeedValue() {
        int value=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_SLOWEST_SPEED);
        return value<0?0:(value>5?5:value);
    }
""", "slowest speed getter")
s = one(s,
    "        KEY_MONO_AUTO_ISO_MAX(R.string.pref_mono_auto_iso_max_key),\n",
    "        KEY_MONO_AUTO_ISO_MAX(R.string.pref_mono_auto_iso_max_key),\n"
    "        KEY_MONO_SLOWEST_SPEED(R.string.pref_mono_slowest_speed_key),\n",
    "slowest speed enum key")
pref_java.write_text(s)

# ----- immutable control identity: selected mode + resolved lens-specific threshold -----
s = plan.read_text()
s = one(s,
    "    public static final int FLAG_AUTO_ISO_MAX_APPLIED = 32;\n",
    "    public static final int FLAG_AUTO_ISO_MAX_APPLIED = 32;\n"
    "    public static final int FLAG_SLOWEST_SPEED_SHIFTED = 64;\n"
    "    public static final int FLAG_SLOWEST_SPEED_EXCEEDED_AT_ISO_MAX = 128;\n",
    "slowest flags")
s = one(s,
    "        public final int manualIso, isoLimit, oisMode, autoIsoMaximum;\n",
    "        public final int manualIso, isoLimit, oisMode, autoIsoMaximum, slowestSpeedMode, lensEquivalent35mmX10;\n"
    "        public final long slowestSpeedNs;\n",
    "control fields")
s = one(s,
    """                boolean tripod, float balance, int isoLimit, float shutterLimit, int oisMode,
                int autoIsoMaximum, String meteringKey) {
""",
    """                boolean tripod, float balance, int isoLimit, float shutterLimit, int oisMode,
                int autoIsoMaximum, int slowestSpeedMode, long slowestSpeedNs,
                int lensEquivalent35mmX10, String meteringKey) {
""",
    "control constructor")
s = one(s,
    """                    || !Float.isFinite(balance) || balance<=0 || !Float.isFinite(shutterLimit)
                    || autoIsoMaximum<=0)
""",
    """                    || !Float.isFinite(balance) || balance<=0 || !Float.isFinite(shutterLimit)
                    || autoIsoMaximum<=0 || slowestSpeedMode<0 || slowestSpeedMode>5
                    || slowestSpeedNs<=0 || lensEquivalent35mmX10<=0)
""",
    "control validation")
s = one(s,
    """            this.oisMode=oisMode;this.autoIsoMaximum=autoIsoMaximum;this.meteringKey=meteringKey;
""",
    """            this.oisMode=oisMode;this.autoIsoMaximum=autoIsoMaximum;
            this.slowestSpeedMode=slowestSpeedMode;this.slowestSpeedNs=slowestSpeedNs;
            this.lensEquivalent35mmX10=lensEquivalent35mmX10;this.meteringKey=meteringKey;
""",
    "control assignment")
s = one(s,
    """                    && oisMode==c.oisMode && autoIsoMaximum==c.autoIsoMaximum
                    && meteringKey.equals(c.meteringKey);
""",
    """                    && oisMode==c.oisMode && autoIsoMaximum==c.autoIsoMaximum
                    && slowestSpeedMode==c.slowestSpeedMode && slowestSpeedNs==c.slowestSpeedNs
                    && lensEquivalent35mmX10==c.lensEquivalent35mmX10
                    && meteringKey.equals(c.meteringKey);
""",
    "control equality")
s = one(s,
    """                    isoLimit,shutterLimit,oisMode,autoIsoMaximum,meteringKey);
""",
    """                    isoLimit,shutterLimit,oisMode,autoIsoMaximum,slowestSpeedMode,
                    slowestSpeedNs,lensEquivalent35mmX10,meteringKey);
""",
    "control hash")
plan.write_text(s)

# ----- resolve Lens dependent from the active physical lens, then include it in plan identity -----
s = selector.read_text()
autoiso_helper_anchor = "    /**\n     * Leica Auto ISO Maximum in the physical Camera2 ISO domain.\n"
if s.count(autoiso_helper_anchor) != 1:
    raise SystemExit("LEICASLOWEST1A Auto ISO helper anchor count=" + str(s.count(autoiso_helper_anchor)))
resolver = r'''    /**
     * Phone lenses are not full-frame M lenses, so use their 35mm-equivalent field
     * of view for Leica's Lens dependent 1/focal-length rule. The active physical
     * camera characteristics are used, not a Xiaomi/lens-name table and not digital zoom.
     */
    public static int monoEquivalentFocalLength35mmX10_1E(CameraCharacteristics chars) {
        if(chars!=null) {
            float[] focal=chars.get(CameraCharacteristics.LENS_INFO_AVAILABLE_FOCAL_LENGTHS);
            SizeF sensor=chars.get(CameraCharacteristics.SENSOR_INFO_PHYSICAL_SIZE);
            if(focal!=null&&focal.length>0&&focal[0]>0.0f&&sensor!=null&&sensor.getWidth()>0.0f) {
                double efl=(36.0/sensor.getWidth())*focal[0];
                if(Double.isFinite(efl)&&efl>0.0)
                    return Math.max(80,Math.min(2000,(int)Math.round(efl*10.0)));
            }
        }
        // Malformed HAL fallback only; normal devices expose focal length + physical size.
        return 350;
    }

    private static int nearestLeicaWholeStopDenominator1E(double focal35mm) {
        final int[] d={8,15,30,60,125};
        int best=d[0];
        double bestDistance=Math.abs(Math.log(focal35mm/best));
        for(int i=1;i<d.length;i++) {
            double distance=Math.abs(Math.log(focal35mm/d[i]));
            if(distance<bestDistance){bestDistance=distance;best=d[i];}
        }
        return best;
    }

    public static long resolveMonoSlowestSpeedNs1E(CameraCharacteristics chars,int mode) {
        switch(mode) {
            case 1:return ExposureIndex.sec/125;
            case 2:return ExposureIndex.sec/60;
            case 3:return ExposureIndex.sec/30;
            case 4:return ExposureIndex.sec/15;
            case 5:return ExposureIndex.sec/8;
            default:
                double focal35mm=monoEquivalentFocalLength35mmX10_1E(chars)/10.0;
                return ExposureIndex.sec/nearestLeicaWholeStopDenominator1E(focal35mm);
        }
    }

'''
s=s.replace(autoiso_helper_anchor,resolver+autoiso_helper_anchor,1)

# Apply slowest-speed semantics after the validated Auto ISO ceiling:
# raise automatic ISO when shutter would cross the selected threshold; once the
# maximum ISO is reached, permit a slower shutter rather than underexpose.
plan_anchor = "    public static MonoExposurePlan1A planMonoExposure1A(CaptureController controller,CaptureResult transport,\n"
if s.count(plan_anchor)!=1:
    raise SystemExit("LEICASLOWEST1A plan anchor count="+str(s.count(plan_anchor)))
slow_helper = r'''    private static int effectiveMonoAutoIsoCap1E(MonoInput1A input) {
        return Math.max(input.isoLow,Math.min(input.isoHigh,input.controls.autoIsoMaximum));
    }

    private static boolean applyMonoSlowestSpeed1E(ExpoPair pair,MonoInput1A input) {
        if(pair==null||input==null||input.controls.manualIso>0||input.controls.manualExposureNs>0)return false;
        long threshold=Math.max(input.timeLow,Math.min(input.timeHigh,input.controls.slowestSpeedNs));
        if(pair.exposure<=threshold)return false;
        int cap=effectiveMonoAutoIsoCap1E(input);
        if(pair.iso>=cap)return false;

        double energy=(double)pair.iso*(double)pair.exposure;
        if(!(energy>0.0)||!Double.isFinite(energy))return false;
        double rawNeededIso=Math.ceil(energy/(double)threshold);
        int neededIso=rawNeededIso>=Integer.MAX_VALUE?cap:(int)rawNeededIso;
        int targetIso=Math.max(pair.iso,Math.min(cap,neededIso));
        if(targetIso<=pair.iso)return false;

        double rawTime=Math.ceil(energy/(double)targetIso);
        long targetTime;
        if(!Double.isFinite(rawTime)||rawTime>Long.MAX_VALUE)targetTime=input.timeHigh;
        else targetTime=(long)rawTime;
        targetTime=Math.max(input.timeLow,Math.min(input.timeHigh,targetTime));

        pair.iso=targetIso;
        pair.exposure=targetTime;
        pair.isShutterLimited=true;
        return true;
    }

    private static boolean monoSlowestExceededAtIsoMax1E(ExpoPair pair,MonoInput1A input) {
        if(pair==null||input==null||input.controls.manualIso>0||input.controls.manualExposureNs>0)return false;
        long threshold=Math.max(input.timeLow,Math.min(input.timeHigh,input.controls.slowestSpeedNs));
        return pair.exposure>threshold && pair.iso>=effectiveMonoAutoIsoCap1E(input);
    }

'''
s=s.replace(plan_anchor,slow_helper+plan_anchor,1)

flag_anchor = """        final boolean monoAutoIsoMaxApplied1D=applyMonoAutoIsoMaximum1D(pair,input);
        int flags=(pair.isIsoLimited?1:0)|(pair.isShutterLimited?2:0)|(pair.isIsoManualOverLimit?4:0)
                |(pair.isShutterManualOverLimit?8:0)|(pair.isShutterTripodBypassed?16:0)
                |(monoAutoIsoMaxApplied1D?MonoExposurePlan1A.FLAG_AUTO_ISO_MAX_APPLIED:0);
"""
s = one(s, flag_anchor,
    """        final boolean monoAutoIsoMaxApplied1D=applyMonoAutoIsoMaximum1D(pair,input);
        final boolean monoSlowestSpeedShifted1E=applyMonoSlowestSpeed1E(pair,input);
        final boolean monoSlowestExceededAtIsoMax1E=monoSlowestExceededAtIsoMax1E(pair,input);
        int flags=(pair.isIsoLimited?1:0)|(pair.isShutterLimited?2:0)|(pair.isIsoManualOverLimit?4:0)
                |(pair.isShutterManualOverLimit?8:0)|(pair.isShutterTripodBypassed?16:0)
                |(monoAutoIsoMaxApplied1D?MonoExposurePlan1A.FLAG_AUTO_ISO_MAX_APPLIED:0)
                |(monoSlowestSpeedShifted1E?MonoExposurePlan1A.FLAG_SLOWEST_SPEED_SHIFTED:0)
                |(monoSlowestExceededAtIsoMax1E?MonoExposurePlan1A.FLAG_SLOWEST_SPEED_EXCEEDED_AT_ISO_MAX:0);
""",
    "slowest allocation")
selector.write_text(s)

s = capture.read_text()
old = """                exposureBalanceMultiplier,exposureBalanceIsoLimit,exposureBalanceShutterLimit,oisMode,
                com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoAutoIsoMaximumValue(),metering);
"""
new = """                exposureBalanceMultiplier,exposureBalanceIsoLimit,exposureBalanceShutterLimit,oisMode,
                com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoAutoIsoMaximumValue(),
                com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoSlowestSpeedValue(),
                IsoExpoSelector.resolveMonoSlowestSpeedNs1E(monoCharacteristics1A(),
                        com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoSlowestSpeedValue()),
                IsoExpoSelector.monoEquivalentFocalLength35mmX10_1E(monoCharacteristics1A()),metering);
"""
s = one(s, old, new, "controller slowest identity")
capture.write_text(s)

# ----- diagnostics -----
s = diag.read_text()
anchor = '                    .put("autoIsoManualOverride",p.controls.manualIso>0)\n'
if s.count(anchor)!=1:
    raise SystemExit("LEICASLOWEST1A diagnostic anchor count="+str(s.count(anchor)))
diag_block = anchor + (
    '                    .put("slowestSpeedRevision","LEICASLOWEST1A")\n'
    '                    .put("slowestSpeedMode",p.controls.slowestSpeedMode)\n'
    '                    .put("slowestSpeedResolvedNs",p.controls.slowestSpeedNs)\n'
    '                    .put("slowestSpeedLensEquivalent35mm",p.controls.lensEquivalent35mmX10/10.0)\n'
    '                    .put("slowestSpeedShifted",(p.flags&MonoExposurePlan1A.FLAG_SLOWEST_SPEED_SHIFTED)!=0)\n'
    '                    .put("slowestSpeedExceededAtIsoMax",(p.flags&MonoExposurePlan1A.FLAG_SLOWEST_SPEED_EXCEEDED_AT_ISO_MAX)!=0)\n'
)
s=s.replace(anchor,diag_block,1)
diag.write_text(s)

# Identity.
g=gradle.read_text()
m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("LEICASLOWEST1A versionName missing")
if "leicaslowest1a" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-leicaslowest1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICASLOWEST1A changed frozen photographic files "+repr(changed))

proof={
    "revision":"LEICASLOWEST1A",
    "cameraModel":"first_generation_Leica_M_Monochrom",
    "menu":["Lens dependent","1/125 s","1/60 s","1/30 s","1/15 s","1/8 s"],
    "menuEnum":[0,1,2,3,4,5],
    "default":"Lens dependent",
    "lensDependentRule":"1_over_35mm_equivalent_focal_length_rounded_to_nearest_original_whole_stop",
    "lensDependentReferenceExamples":{"35mm":"1/30 s","50mm":"1/60 s"},
    "phoneLensConversion":"active_physical_lens_to_35mm_equivalent_from_CameraCharacteristics",
    "digitalZoomChangesThreshold":False,
    "deviceSpecificLensNames":False,
    "automaticIsoRaisesBeforeCrossingThreshold":True,
    "autoIsoMaximumRemainsAuthority":True,
    "slowerThanThresholdAllowedAfterIsoMaximum":True,
    "manualIsoAuthorityPreserved":True,
    "manualShutterAuthorityPreserved":True,
    "previewAndCaptureShareSamePlan":True,
    "HDR":False,
    "rendererChanged":False,
    "linearDngMathChanged":False,
    "contrastChanged":False,
    "toningChanged":False,
    "sharpnessChanged":False,
    "frozenPhotographicHashes":after,
}
(root/"LEICASLOWEST1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
