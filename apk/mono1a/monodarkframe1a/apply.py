#!/usr/bin/env python3
"""MONODARKFRAME1A: Leica-derived long-exposure correction for derived Monochrom outputs."""
from pathlib import Path
import hashlib,json,re,shutil,sys

if len(sys.argv)!=2: raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
controller=J/"capture/CaptureController.java"
renderer=J/"m9/render/M9R35Renderer.java"
helper_src=Path(__file__).with_name("MonoDarkFrame1A.java")
helper_dst=J/"m9/render/MonoDarkFrame1A.java"
gradle=root/"app/build.gradle"
for p in [controller,renderer,helper_src,gradle]:
    if not p.is_file(): raise SystemExit("MONODARKFRAME1A missing "+str(p))
if not (root/"LEICADIAGNOSTICS1A_ISOLATION.json").is_file():
    raise SystemExit("MONODARKFRAME1A missing validated LEICADIAGNOSTICS1A parent")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"MONODARKFRAME1A {label} anchor count={n}")
    return s.replace(a,b,1)

def one_after(s,marker,a,b,label):
    start=s.find(marker)
    if start<0: raise SystemExit(f"MONODARKFRAME1A {label} scope marker missing")
    tail=s[start:]
    n=tail.count(a)
    if n!=1: raise SystemExit(f"MONODARKFRAME1A {label} scoped anchor count={n}")
    return s[:start]+tail.replace(a,b,1)

# Freeze storage/output ownership and every existing Leica look/exposure component.
# Only still-request metadata and the private derived render copy may change.
frozen=[
    J/"m9/render/M9PrimaryRenderQueue.java",
    J/"m9/render/M9NativeColorCore.java",
    J/"m9/render/M9JpegFinalizeQueue.java",
    J/"m9/export/MonoDngExport1A.java",
    J/"m9/export/MonoDngSpool1B.java",
    J/"m9/export/MonoDngWriter1A.java",
    J/"m9/export/MonoLinearPlane1A.java",
    J/"m9/exposure/MonoExposurePlan1A.java",
    J/"processing/parameters/IsoExpoSelector.java",
    J/"m9/preview/MonoGpuPreview2A.java",
    J/"settings/PreferenceKeys.java",
    J/"m9/M9DiagnosticBurstSpool.java",
    J/"m9/M9DiagnosticSidecarIO.java",
    root/"app/src/main/cpp/m9color_jni.cpp",
    root/"app/src/main/assets/shaders/preview/main_fs.glsl",
    root/"app/src/main/assets/mono/mono_contrast_curves.bin",
    root/"app/src/main/assets/mono/mono_sharpness5.bin",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}

# Install the helper into the reconstructed Android tree.
if helper_dst.exists(): raise SystemExit("MONODARKFRAME1A helper already exists")
helper_dst.parent.mkdir(parents=True,exist_ok=True)
shutil.copyfile(helper_src,helper_dst)

# Request only the standard hot-pixel MAP for Leica-eligible exposures.
# Never select HOT_PIXEL_MODE, because that could change the untouched sensor RAW.
s=controller.read_text()
s=one(s,
'''import com.particlesdevs.photoncamera.m9.exposure.MonoBracket1H;
''',
'''import com.particlesdevs.photoncamera.m9.exposure.MonoBracket1H;
import com.particlesdevs.photoncamera.m9.render.MonoDarkFrame1A;
''',"CaptureController helper import")

s=one(s,
'''                    if(!PhotonCamera.getSettings().selectedMode.equals(CameraMode.RAWVIDEO))
                        IsoExpoSelector.setMonoPlannedExpo1A(captureBuilder, i, this, monoCapturePlan1A);
                    else {
''',
'''                    if(!PhotonCamera.getSettings().selectedMode.equals(CameraMode.RAWVIDEO)) {
                        IsoExpoSelector.setMonoPlannedExpo1A(captureBuilder, i, this, monoCapturePlan1A);
                        MonoDarkFrame1A.configureCaptureRequest(
                                captureBuilder, getOpenDeviceCharacteristics());
                    } else {
''',"single-frame hot-pixel map request")

s=one(s,
'''                    IsoExpoSelector.setMonoPlannedExpo1A(captureBuilder, i, this, monoCapturePlan1A);
                    times[i] = IsoExpoSelector.lastSelectedExposure;
''',
'''                    IsoExpoSelector.setMonoPlannedExpo1A(captureBuilder, i, this, monoCapturePlan1A);
                    MonoDarkFrame1A.configureCaptureRequest(
                            captureBuilder, getOpenDeviceCharacteristics());
                    times[i] = IsoExpoSelector.lastSelectedExposure;
''',"burst/bracket hot-pixel map request")
controller.write_text(s)

# Derived-render correction. Per-frame dynamic black is used only after the Leica
# threshold is crossed. The normalized Bayer private copy may receive mapped
# hot-pixel repair before demosaic; the original camera ByteBuffer is read-only.
s=renderer.read_text()
s=one(s,
'''            long setupElapsedMs = (System.nanoTime() - setupStartedNs) / 1_000_000L;
            long renderCoreStartedNs = System.nanoTime();
''',
'''            MonoDarkFrame1A.BlackResolution monoDarkBlack1A =
                    MonoDarkFrame1A.resolveBlackLevels(
                            encodedBlack, diagnosticCaptureResult1A, iso, exposureTimeNs);
            encodedBlack = monoDarkBlack1A.levels;

            long setupElapsedMs = (System.nanoTime() - setupStartedNs) / 1_000_000L;
            long renderCoreStartedNs = System.nanoTime();
''',"dynamic black resolution")

s=one(s,
'''            out.diagnostics.put("monoDevicePortRevision", "MONO_DEVICEPORT2A_CFA_ORIGIN");
''',
'''            out.diagnostics.put("monoDarkFrameBlackLevel1A", monoDarkBlack1A.toJson());
            out.diagnostics.put("monoDevicePortRevision", "MONO_DEVICEPORT2A_CFA_ORIGIN");
''',"dynamic black diagnostics")

s=one_after(s,"    private static RenderCore renderNativeProspectiveCore(",
'''        nativeNormalizeWorkersUsed = normalizeStats[2];

        long[][] rawCounts = new long[4][wl];
''',
'''        nativeNormalizeWorkersUsed = normalizeStats[2];

        MonoDarkFrame1A.CorrectionStats monoDarkCorrection1A =
                MonoDarkFrame1A.correctNormalizedHotPixels(
                        norm16, width, height, sourceRawOriginX, sourceRawOriginY,
                        wl, rawCountsFlat, nativeCaptureResult);

        long[][] rawCounts = new long[4][wl];
''',"private normalized hot-pixel correction")

s=one_after(s,"    private static RenderCore renderNativeProspectiveCore(",
'''            d.put("blackLevelB", black != null && black.length >= 4 ? black[3] : 64.0);
            d.put("neutralR", neutralF[0]);
''',
'''            d.put("blackLevelB", black != null && black.length >= 4 ? black[3] : 64.0);
            d.put("monoDarkFrameCorrection1A", monoDarkCorrection1A.toJson());
            d.put("neutralR", neutralF[0]);
''',"correction diagnostics")
renderer.write_text(s)

g=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("MONODARKFRAME1A versionName missing")
if "monodarkframe1a" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-monodarkframe1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("MONODARKFRAME1A changed frozen ownership/look files "+repr(changed))

proof={
 "revision":"MONODARKFRAME1A",
 "leicaFirmware":"M_Monochrom_1.022",
 "leicaDecisionRecovered":True,
 "firmwareDecision":"floor(exposure_us/10) > threshold[temp_group][iso_bucket]",
 "androidTemperaturePolicy":"nominal_Leica_group2_20_39C_because_standard_Camera2_has_no_matching_sensor_control_temperature",
 "nominalThresholdsNs":{"ISO_320_1000":250000000,"ISO_1250_4000":125000000,"ISO_5000_10000":66000000},
 "strictGreaterThan":True,
 "captureRequestChange":"STATISTICS_HOT_PIXEL_MAP_MODE_only_when_supported_and_eligible",
 "hotPixelModeForced":False,
 "dynamicBlack":"SENSOR_DYNAMIC_BLACK_LEVEL_on_eligible_derived_path_when_valid",
 "hotPixelCorrection":"only_when_CaptureResult_HOT_PIXEL_MODE_explicitly_OFF",
 "hotPixelInterpolation":"same_CFA_plusminus2_median_private_normalized_copy",
 "originalRawBufferMutated":False,
 "secondExposure":False,
 "artificialDelay":False,
 "hdrOrStacking":False,
 "originalSensorRawPathChanged":False,
 "derivedMonoDngAndJpegShareCorrectedSource":True,
 "deviceVendorPolicy":False,
 "frozenHashes":after,
}
(root/"MONODARKFRAME1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
