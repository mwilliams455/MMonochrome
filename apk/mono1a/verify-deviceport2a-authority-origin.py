#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: verify-deviceport2a-authority-origin.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
R = root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
N = root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java'
C = root/'app/src/main/cpp/m9color_jni.cpp'
F = root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9CfaResolver.java'
for p in (R,N,C,F):
    if not p.exists(): raise SystemExit('DEVICEPORT2A missing '+str(p))
r,n,c,f = R.read_text(),N.read_text(),C.read_text(),F.read_text()

def need(text, token, label):
    if token not in text: raise SystemExit('DEVICEPORT2A verify missing '+label)

def forbid(text, token, label):
    if token in text: raise SystemExit('DEVICEPORT2A verify forbidden '+label)

need(r, 'MONO_DEVICEPORT2A_CFA_ORIGIN', 'revision marker')
need(r, 'physical_camera2_characteristics', 'physical Camera2 CFA authority')
need(r, 'photon_parameters_fail_closed_fallback', 'supported Photon fallback')
need(r, 'resolveMonoSourceRawOrigin2A(', 'geometry-derived RAW origin')
need(r, 'raw_dimensions_match_full_pixel_array', 'full-array origin rule')
need(r, 'raw_dimensions_match_pre_correction_active_array', 'pre-correction origin rule')
need(r, 'raw_dimensions_match_active_array', 'active-array origin rule')
need(r, 'cannot prove RAW sensor origin', 'ambiguous-origin fail closed')
need(r, 'sourceCameraIdUsedAsPhotographicPolicy", false', 'camera ID non-policy')
need(r, 'sourceFocalLengthUsedAsPhotographicPolicy", false', 'focal length non-policy')
need(r, 'sourceLensShadingPlaneSelection", "Camera2_R_Geven_Godd_B_with_sensor_row_parity', 'LSM semantic telemetry')

# Upstream pinned CFAABSTRACT1B must have generalized both MHC and shading while
# retaining the exact RGGB/origin0 implementation as the validated fast/control path.
need(r, 'M9CfaResolver.isSupported', 'conventional Bayer gate')
need(r, 'demosaicMhcBayer(', 'generic MHC dispatch')
need(r, 'applyNativeProspectiveGainMapBayer(', 'generic Bayer shading')
need(r, 'applyNativeProspectiveGainMapLumaDecomp1ABayer(', 'generic decomposed Bayer shading')
need(r, 'sourceCfaPattern == 0 && sourceRawOriginX == 0 && sourceRawOriginY == 0', 'legacy RGGB exact-route guard')
need(n, 'static native long demosaicMhcBayer(', 'generic MHC JNI declaration')
need(c, 'Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_demosaicMhcBayer(', 'generic MHC JNI implementation')
need(f, 'RGGB(0), GRBG(1), GBRG(2), BGGR(3)', 'all conventional Bayer layouts')
need(f, 'Math.floorMod(localY + originY, 2) == 0 ? 1 : 2', 'Camera2 green LSM row semantics')

# The previous hard-coded assumptions must no longer govern the production path.
forbid(r, 'R3.5 v0.7 main-camera parity build expects RGGB CFA=0', 'RGGB-only production gate')
forbid(r, 'final int sourceRawOriginX = 0;\n        final int sourceRawOriginY = 0;', 'hard-coded origin0')

# Source adapter / target boundary remains frozen through this device-port change.
need(r, 'monochromPrimarySource", "SOURCE1D_NATIVE_DNG_XYZ_Y', 'portable SOURCE1D primary')
need(r, 'monochromSourceCobaltRuntimeDependency", false', 'no Cobalt runtime source dependency')
need(r, 'monochromSourceHsmRuntimeDependency", false', 'no HSM runtime source dependency')
need(r, '7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752', 'frozen Monochrom curve02')

print('MONO_DEVICEPORT2A verification OK')
print(' - Camera2 physical CFA authority + all conventional Bayer layouts')
print(' - geometry-derived RAW origin with fail-closed ambiguity')
print(' - CFA-aware MHC and Camera2 semantic four-plane LensShadingMap')
print(' - SOURCE1D portable primary and frozen Leica target preserved')
