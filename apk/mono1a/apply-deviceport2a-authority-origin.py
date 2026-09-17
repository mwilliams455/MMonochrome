#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply-deviceport2a-authority-origin.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
R = root / 'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
if not R.exists():
    raise SystemExit('DEVICEPORT2A missing renderer: ' + str(R))

s = R.read_text()
if 'MONO_DEVICEPORT2A_CFA_ORIGIN' in s:
    raise SystemExit('DEVICEPORT2A already applied')


def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f'DEVICEPORT2A {label}: anchor count={n}, expected 1')
    return text.replace(old, new, 1)

# CFAABSTRACT1B initially trusts Photon's Parameters.cfaPattern. For a portable
# physical-source path, active Camera2 characteristics are the authority whenever
# they report one of the four conventional Bayer mosaics. Photon is only a
# fail-closed fallback; camera IDs and lens labels never select a pattern.
old_gate = '''            // CFAABSTRACT1B: accept only the four conventional Bayer layouts.\n            // CFA=0 remains on the exact validated legacy RGGB implementation.\n            final int sourceCfaPattern = params.cfaPattern & 0xff;\n            if (!M9CfaResolver.isSupported(sourceCfaPattern)) {\n                throw new IllegalStateException("CFAABSTRACT1B unsupported Bayer CFA=" + sourceCfaPattern);\n            }\n'''
new_gate = '''            // MONO_DEVICEPORT2A_CFA_ORIGIN: physical Camera2 metadata is the\n            // source-lattice authority. Photon settings are fallback only and never\n            // a manufacturer/lens policy selector.\n            final int photonCfaPatternBeforeAuthority = params.cfaPattern & 0xff;\n            final Integer physicalCamera2CfaObj = characteristics != null\n                    ? characteristics.get(CameraCharacteristics.SENSOR_INFO_COLOR_FILTER_ARRANGEMENT)\n                    : null;\n            final int physicalCamera2CfaPattern = physicalCamera2CfaObj != null\n                    ? physicalCamera2CfaObj : -1;\n            final int sourceCfaPattern;\n            final String sourceCfaAuthority;\n            if (M9CfaResolver.isSupported(physicalCamera2CfaPattern)) {\n                sourceCfaPattern = physicalCamera2CfaPattern;\n                sourceCfaAuthority = "physical_camera2_characteristics";\n            } else if (M9CfaResolver.isSupported(photonCfaPatternBeforeAuthority)) {\n                sourceCfaPattern = photonCfaPatternBeforeAuthority;\n                sourceCfaAuthority = "photon_parameters_fail_closed_fallback";\n            } else {\n                throw new IllegalStateException(\n                        "MONO_DEVICEPORT2A no supported Bayer CFA; camera2="\n                                + physicalCamera2CfaPattern + "; photon="\n                                + photonCfaPatternBeforeAuthority);\n            }\n            params.cfaPattern = (byte)sourceCfaPattern;\n'''
s = one(s, old_gate, new_gate, 'physical CFA authority')

# CFAABSTRACT1B deliberately froze RAW origin to zero while proving the Bayer
# generalization. Resolve it from physical sensor geometry here. Ambiguous geometry
# fails closed because an incorrect origin changes both Bayer phase and LSM planes.
old_origin = '''        // DEVICEPORT1A deliberately did not infer RAW origin from active-array metadata.\n        // Current Xiaomi 15 Ultra full-frame RAW validation is origin0; keep this explicit.\n        final int sourceRawOriginX = 0;\n        final int sourceRawOriginY = 0;\n'''
new_origin = '''        final MonoSourceRawOrigin2A sourceRawOrigin = resolveMonoSourceRawOrigin2A(\n                nativeCharacteristics, width, height);\n        final int sourceRawOriginX = sourceRawOrigin.x;\n        final int sourceRawOriginY = sourceRawOrigin.y;\n'''
s = one(s, old_origin, new_origin, 'RAW origin authority')

# Insert the geometry resolver immediately before the shared render core.
anchor = '    private static RenderCore renderNativeProspectiveCore(ByteBuffer rawBuffer,\n'
if s.count(anchor) != 1:
    raise SystemExit('DEVICEPORT2A render core anchor missing/ambiguous')
helper = r'''    private static final class MonoSourceRawOrigin2A {
        final int x;
        final int y;
        final String evidence;
        MonoSourceRawOrigin2A(int x, int y, String evidence) {
            this.x = x;
            this.y = y;
            this.evidence = evidence;
        }
    }

    private static MonoSourceRawOrigin2A resolveMonoSourceRawOrigin2A(
            CameraCharacteristics characteristics, int rawWidth, int rawHeight) {
        if (characteristics == null) {
            throw new IllegalStateException(
                    "MONO_DEVICEPORT2A requires active physical CameraCharacteristics");
        }
        android.util.Size pixel = characteristics.get(
                CameraCharacteristics.SENSOR_INFO_PIXEL_ARRAY_SIZE);
        android.graphics.Rect pre = characteristics.get(
                CameraCharacteristics.SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE);
        android.graphics.Rect active = characteristics.get(
                CameraCharacteristics.SENSOR_INFO_ACTIVE_ARRAY_SIZE);

        if (pixel != null && rawWidth == pixel.getWidth() && rawHeight == pixel.getHeight()) {
            return new MonoSourceRawOrigin2A(0, 0, "raw_dimensions_match_full_pixel_array");
        }
        if (pre != null && rawWidth == pre.width() && rawHeight == pre.height()) {
            return new MonoSourceRawOrigin2A(pre.left, pre.top,
                    "raw_dimensions_match_pre_correction_active_array");
        }
        if (active != null && rawWidth == active.width() && rawHeight == active.height()) {
            return new MonoSourceRawOrigin2A(active.left, active.top,
                    "raw_dimensions_match_active_array");
        }
        throw new IllegalStateException(
                "MONO_DEVICEPORT2A cannot prove RAW sensor origin for "
                        + rawWidth + "x" + rawHeight
                        + "; pixel=" + (pixel != null
                                ? pixel.getWidth() + "x" + pixel.getHeight() : "null")
                        + "; pre=" + (pre != null
                                ? pre.left + "," + pre.top + ":" + pre.width() + "x" + pre.height() : "null")
                        + "; active=" + (active != null
                                ? active.left + "," + active.top + ":" + active.width() + "x" + active.height() : "null"));
    }

'''
s = s.replace(anchor, helper + anchor, 1)

# Add top-level authority telemetry after the render returns. This records why the
# lattice was selected without making physical ID/topology a target-render selector.
render_call_tail = '''                    encodedBlack, params.whiteLevel, params.whitePoint, cameraRotation, 0.0,\n                    characteristics, diagnosticCaptureResult1A, sourceCfaPattern);\n'''
if s.count(render_call_tail) != 1:
    raise SystemExit('DEVICEPORT2A primary call tail missing/ambiguous')
telemetry = '''            out.diagnostics.put("monoDevicePortRevision", "MONO_DEVICEPORT2A_CFA_ORIGIN");\n            out.diagnostics.put("sourceCfaAuthority", sourceCfaAuthority);\n            out.diagnostics.put("sourceCamera2CfaPattern", physicalCamera2CfaPattern);\n            out.diagnostics.put("sourcePhotonCfaBeforeAuthority", photonCfaPatternBeforeAuthority);\n            out.diagnostics.put("sourceResolvedCfaPattern", sourceCfaPattern);\n            out.diagnostics.put("sourceCameraIdUsedAsPhotographicPolicy", false);\n            out.diagnostics.put("sourceFocalLengthUsedAsPhotographicPolicy", false);\n'''
s = s.replace(render_call_tail, render_call_tail + telemetry, 1)

# Add origin evidence to the per-core diagnostics at a stable source-domain point.
diag_anchor = '        d.put("nativeSourceInputHeight", height);\n'
if s.count(diag_anchor) != 1:
    # Older scaffold may not have this exact field; use the target-independent source flag.
    diag_anchor = '        d.put("nativeSourceProduction1A", true);\n'
if s.count(diag_anchor) != 1:
    raise SystemExit('DEVICEPORT2A source diagnostics anchor missing/ambiguous')
origin_diag = '''        d.put("sourceRawOriginX", sourceRawOriginX);\n        d.put("sourceRawOriginY", sourceRawOriginY);\n        d.put("sourceRawOriginEvidence", sourceRawOrigin.evidence);\n        d.put("sourceRawOriginDerivedFromPhysicalGeometry", true);\n        d.put("sourceLensShadingPlaneSelection", "Camera2_R_Geven_Godd_B_with_sensor_row_parity");\n'''
s = s.replace(diag_anchor, diag_anchor + origin_diag, 1)

R.write_text(s)
print('MONO_DEVICEPORT2A_CFA_ORIGIN applied')
print(' - physical Camera2 CFA is authoritative with supported Photon fallback')
print(' - RAW origin derived from pixel/pre-correction/active-array geometry')
print(' - arbitrary conventional Bayer phase feeds MHC and LensShadingMap dispatch')
print(' - ambiguous geometry and unsupported CFA fail closed')
