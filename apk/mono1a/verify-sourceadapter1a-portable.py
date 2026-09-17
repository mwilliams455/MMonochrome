#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: verify-sourceadapter1a-portable.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
R = root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
N = root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java'
C = root/'app/src/main/cpp/m9color_jni.cpp'
for p in (R, N, C):
    if not p.exists():
        raise SystemExit('missing '+str(p))

r = R.read_text()
n = N.read_text()
c = C.read_text()

required_renderer = [
    'MONO1A_SOURCEADAPTER1A_PORTABLE',
    'SOURCE1D_NATIVE_DNG_XYZ_Y',
    'NATIVE_DNG_SENSOR_TO_XYZ_D50_Y_ROW',
    'active_physical_sensor_Camera2_DNG_to_XYZ_D50_Y',
    'monochromSourceManufacturerIndependent", true',
    'monochromSourceCameraIdUsedAsAestheticSelector", false',
    'monochromSourceFocalLengthUsedAsAestheticSelector", false',
    'monochromSourceCobaltRuntimeDependency", false',
    'monochromSourceHsmRuntimeDependency", false',
    'active_physical_Camera2_DNG_metadata',
    'source1dXyzY.put("photographicOutputSelected", true)',
    'rawScalar1B.put("photographicOutputSelected", false)',
    'diagnostic_fixed_Xiaomi_camera_spectral_proxy_not_portable',
    'return new RenderCore(equalRgbBitmap, d, rawScalar1BBitmap, greenOnlyBitmap, rawScalar1ABitmap, monoBitmap);',
]
for token in required_renderer:
    if token not in r:
        raise SystemExit('SOURCEADAPTER1A missing renderer invariant: '+token)

required_native = [
    'renderMonochrome1AWeightedDirectBitmap',
]
for token in required_native:
    if token not in n or token not in c:
        raise SystemExit('SOURCEADAPTER1A missing native weighted bridge: '+token)

# Reject accidental promotion of the known phone-specific spectral proxy.
forbidden_selected = [
    'monochromPrimarySource", "RAWSCALAR1B_FIXED_D65"',
    'monochromPrimarySourceAdapter", "fixed_Xiaomi_D65_camera_neutral_proxy"',
    'rawScalar1B.put("photographicOutputSelected", true)',
]
for token in forbidden_selected:
    if token in r:
        raise SystemExit('SOURCEADAPTER1A phone-specific primary survived: '+token)

# The selected source must be derived from active source calibration, not from a
# Cobalt/Adobe HSM. References may still exist elsewhere in the inherited M9
# scaffold, so verify the selected Monochrom source block itself has no such role.
start = r.find('JSONObject source1dXyzY = new JSONObject();')
end = r.find('d.put("source1dXyzY", source1dXyzY);', start)
if start < 0 or end < 0:
    raise SystemExit('SOURCEADAPTER1A source1d diagnostics block missing')
selected_block = r[start:end]
for bad in ('Cobalt', 'ProfileHueSatMap', 'applyHsm', 'fixed_Xiaomi_D65'):
    if bad in selected_block:
        raise SystemExit('SOURCEADAPTER1A forbidden selected-source dependency: '+bad)

# Preserve the Leica target asset checksum and target/source separation.
if '7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752' not in r:
    raise SystemExit('SOURCEADAPTER1A frozen Monochrom curve02 provenance missing')

print('SOURCEADAPTER1A PORTABLE verification OK')
print(' primary = active physical Camera2/DNG -> XYZ D50 Y common monochrome scene signal')
print(' fixed Xiaomi D65 proxy = diagnostic only')
print(' selected source = no Cobalt/HSM role')
print(' Leica target curve = frozen and source-independent')
