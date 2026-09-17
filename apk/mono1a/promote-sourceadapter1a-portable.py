#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: promote-sourceadapter1a-portable.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
R = root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
if not R.exists():
    raise SystemExit('missing '+str(R))


def one(s, a, b, label):
    n = s.count(a)
    if n != 1:
        raise SystemExit(f'{label}: anchor count={n}, expected 1')
    return s.replace(a, b, 1)


r = R.read_text()
if 'MONO1A_SOURCEADAPTER1A_PORTABLE' in r:
    raise SystemExit('SOURCEADAPTER1A PORTABLE already applied')
if 'MONO1A_RAWSCALAR1B_PROMOTED1A' not in r:
    raise SystemExit('SOURCEADAPTER1A requires RAWSCALAR1B promoted baseline')
if 'NATIVE_DNG_SENSOR_TO_XYZ_D50_Y_ROW' not in r:
    raise SystemExit('SOURCEADAPTER1A requires SOURCE1D native DNG XYZ-Y bridge')

# The former SOURCE1D auxiliary slot becomes the photographic output. Preserve
# the current fixed-Xiaomi D65 route as a same-RAW diagnostic control. This is a
# selection/ownership change only: source math, Leica curve02, sharpness, ISO,
# exposure and JPEG quality remain unchanged.
r = one(
    r,
    'stem + "_MONO_XYZY.jpg"',
    'stem + "_MONO_FIXED_D65_CONTROL.jpg"',
    'rename reused auxiliary slot to fixed-D65 control',
)
r = r.replace('source1dXyzYJpegPath', 'fixedD65ControlJpegPath')
r = r.replace('source1dXyzYJpegSaved', 'fixedD65ControlJpegSaved')
r = r.replace('source1dXyzYJpegError', 'fixedD65ControlJpegError')

r = one(
    r,
    'source1dXyzY.put("photographicOutputSelected", false);',
    'source1dXyzY.put("photographicOutputSelected", true);',
    'SOURCE1D selection flag',
)
r = one(
    r,
    'source1dXyzY.put("role", "counterfactual_scene_luminance_bridge_not_Leica_spectral_truth");',
    'source1dXyzY.put("role", "selected_portable_common_scene_luminance_bridge_not_Leica_spectral_truth");',
    'SOURCE1D selected role',
)

r = one(
    r,
    'rawScalar1B.put("photographicOutputSelected", true);',
    'rawScalar1B.put("photographicOutputSelected", false);',
    'fixed-D65 control selection flag',
)
r = one(
    r,
    'rawScalar1B.put("role", "selected_fixed_Xiaomi_camera_spectral_proxy_not_Leica_CCD_response");',
    'rawScalar1B.put("role", "diagnostic_fixed_Xiaomi_camera_spectral_proxy_not_portable_not_Leica_CCD_response");',
    'fixed-D65 diagnostic role',
)

r = one(
    r,
    'd.put("rawScalar1BPolicy", "promoted_primary_fixed_Xiaomi_spectral_proxy_no_per_shot_AWB_no_tone_or_exposure_change");',
    'd.put("rawScalar1BPolicy", "diagnostic_control_only_fixed_Xiaomi_spectral_proxy_not_portable");',
    'fixed-D65 policy',
)

r = one(
    r,
    'd.put("source1Revision", "MONO1A_RAWSCALAR1B_PROMOTED1A");',
    'd.put("source1Revision", "MONO1A_SOURCEADAPTER1A_PORTABLE");',
    'portable source revision',
)
r = one(
    r,
    'd.put("monochromPrimarySource", "RAWSCALAR1B_FIXED_D65");',
    'd.put("monochromPrimarySource", "SOURCE1D_NATIVE_DNG_XYZ_Y");',
    'portable primary source',
)
r = one(
    r,
    'd.put("monochromPrimarySourceAdapter", "fixed_Xiaomi_D65_camera_neutral_proxy");',
    'd.put("monochromPrimarySourceAdapter", "active_physical_sensor_Camera2_DNG_to_XYZ_D50_Y");',
    'portable source adapter telemetry',
)
r = one(
    r,
    'd.put("monochromPrimaryLeicaSpectralTruth", false);',
    'd.put("monochromPrimaryLeicaSpectralTruth", false);\n'
    '                d.put("monochromSourceManufacturerIndependent", true);\n'
    '                d.put("monochromSourceCameraIdUsedAsAestheticSelector", false);\n'
    '                d.put("monochromSourceFocalLengthUsedAsAestheticSelector", false);\n'
    '                d.put("monochromSourceCobaltRuntimeDependency", false);\n'
    '                d.put("monochromSourceHsmRuntimeDependency", false);\n'
    '                d.put("monochromSourceCalibrationAuthority", "active_physical_Camera2_DNG_metadata");',
    'portable invariants telemetry',
)

# Ownership swap after RAWSCALAR1B promotion:
#   current: primary=fixed-D65, source1cEqualRgbBitmap=SOURCE1D XYZ-Y
#   portable: primary=SOURCE1D XYZ-Y, source1cEqualRgbBitmap=fixed-D65 control
# M9-Y and RAWSCALAR1A controls remain in their existing slots.
r = one(
    r,
    'return new RenderCore(rawScalar1BBitmap, d, equalRgbBitmap, greenOnlyBitmap, rawScalar1ABitmap, monoBitmap);',
    'return new RenderCore(equalRgbBitmap, d, rawScalar1BBitmap, greenOnlyBitmap, rawScalar1ABitmap, monoBitmap);',
    'portable primary ownership swap',
)

r = one(
    r,
    'mmonochrome.mono1a.rawscalar1b.promoted1a.v1',
    'mmonochrome.mono1a.sourceadapter1a.portable.v1',
    'portable root schema',
)

# Root save telemetry must describe the newly selected output rather than the
# retained fixed-D65 control.
r = one(
    r,
    'diag.put("monochromPrimaryMode", "RAWSCALAR1B_FIXED_D65");',
    'diag.put("monochromPrimaryMode", "SOURCE1D_NATIVE_DNG_XYZ_Y");',
    'portable save telemetry mode',
)
r = one(
    r,
    'diag.put("monochromPrimarySpectralClaim", "fixed_Xiaomi_camera_spectral_proxy_not_Leica_CCD_QE_truth");',
    'diag.put("monochromPrimarySpectralClaim", "active_sensor_scene_luminance_bridge_not_Leica_CCD_QE_truth");\n'
    '            diag.put("monochromPortableSourceAdapter", true);\n'
    '            diag.put("monochromPortableSourceAdapterRevision", "MONO1A_SOURCEADAPTER1A_PORTABLE");',
    'portable save telemetry claim',
)

R.write_text(r)
print('MONO1A SOURCEADAPTER1A PORTABLE applied')
print(' - primary source: active physical Camera2/DNG sensor -> XYZ D50 Y')
print(' - fixed Xiaomi D65 route retained as diagnostic control only')
print(' - Leica target tone/sharpness/ISO/exposure/JPEG policy unchanged')
print(' - no Cobalt/HSM source role is introduced')
