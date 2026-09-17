#!/usr/bin/env python3
from pathlib import Path
import sys
if len(sys.argv)!=2: raise SystemExit('usage: verify-sourceadapter1b-cfa-geometry.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve()
R=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
N=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java'
C=root/'app/src/main/cpp/m9color_jni.cpp'
J=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9CfaResolver.java'
for p in (R,N,C,J):
    if not p.exists(): raise SystemExit('VERIFY missing '+str(p))
r,n,c,j=(p.read_text() for p in (R,N,C,J))

def need(text, token, label):
    if token not in text: raise SystemExit('VERIFY missing '+label+': '+token)
def forbid(text, token, label):
    if token in text: raise SystemExit('VERIFY forbidden '+label+': '+token)

# Latest functional baseline must survive portability.
need(r,'SHARPSTD1B_NORMISO','SHARPSTD1B baseline')
need(r,'MANUALISO1B','MANUALISO1B baseline marker')
need(r,'MONO1A_SOURCEADAPTER1A_MANUALISO1B_PORTABLE','portable source promotion')
need(r,'MONO1A_SOURCEADAPTER1B_CFA_GEOMETRY','portable geometry revision')
need(r,'monochromPrimarySource", "SOURCE1D_NATIVE_DNG_XYZ_Y','portable primary')
need(r,'monochromSourceCobaltRuntimeDependency", false','zero source Cobalt runtime dependency')
need(r,'monochromSourceHsmRuntimeDependency", false','zero source HSM runtime dependency')
need(r,'canonical_M_Monochrom_curve02_frozen','frozen target tone')

# Source authority / no device-role rendering.
need(r,'SENSOR_INFO_COLOR_FILTER_ARRANGEMENT','physical Camera2 CFA authority')
need(r,'physical_camera2_characteristics','CFA authority provenance')
need(r,'physicalCameraIdUsedAsSemanticRole", false','camera ID non-semantic')
need(r,'sourceFocalLengthUsedAsSemanticRole", false','focal length non-semantic')
forbid(r,'skipped_non_main_physical_camera','main-camera diagnostic gate')
forbid(r,'mainPhysicalCameraRequired','camera-2 requirement')
forbid(r,'main physical 2 requires RGGB','camera-2 RGGB requirement')
forbid(r,'if (params.cfaPattern != 0)','production RGGB-only gate')

# Geometry/origin and all four Bayer layouts.
for token in ('SENSOR_INFO_PIXEL_ARRAY_SIZE','SENSOR_INFO_PRE_CORRECTION_ACTIVE_ARRAY_SIZE','SENSOR_INFO_ACTIVE_ARRAY_SIZE',
              'raw_dimensions_match_full_pixel_array','raw_dimensions_match_pre_correction_active_array','raw_dimensions_match_active_array'):
    need(r,token,'RAW origin resolver')
need(r,'cannot prove RAW sensor origin','fail-closed geometry')
for pat in ('RGGB(0)','GRBG(1)','GBRG(2)','BGGR(3)'): need(j,pat,'Bayer '+pat)
need(j,'lensShadingChannelAt','semantic LensShadingMap channel resolver')

# Pixel path: legacy exact route plus generic phase-aware route.
need(n,'demosaicMhcRggb','legacy RGGB JNI')
need(n,'demosaicMhcBayer','generic Bayer JNI')
need(c,'Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_demosaicMhcRggb','legacy RGGB native')
need(c,'Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_demosaicMhcBayer','generic Bayer native')
need(c,'basePhaseX=(cfaPattern==1||cfaPattern==3)?1:0','CFA X phase')
need(c,'basePhaseY=(cfaPattern==2||cfaPattern==3)?1:0','CFA Y phase')
need(r,'applyNativeProspectiveGainMapBayer1B','CFA-aware source shading')
need(r,'M9CfaResolver.lensShadingChannelAt','semantic shading plane lookup')
need(r,'legacyRggbOrigin0','legacy exact-dispatch guard')
need(r,'legacyDiagnosticSkippedReason','nonlegacy legacy-diagnostic skip')

# Same RAW control remains, but is never the primary.
need(r,'fixedD65ControlJpegPath','D65 control retained')
need(r,'rawScalar1B.put("photographicOutputSelected", false)','D65 route not selected')
need(r,'source1dXyzY.put("photographicOutputSelected", true)','SOURCE1D selected')

# Pure host oracle for lattice/origin and Camera2 shading-channel semantics.
patterns={0:((0,0),(1,1)),1:((1,0),(0,1)),2:((0,1),(1,0)),3:((1,1),(0,0))}
# Represent pattern as RGGB base phase offsets, same algebra as native.
def phase(p,ox,oy):
    bx=1 if p in (1,3) else 0; by=1 if p in (2,3) else 0
    return ((bx+ox)&1,(by+oy)&1)
def site(p,x,y,ox=0,oy=0):
    px,py=phase(p,ox,oy); ex=((x+px)&1)==0; ey=((y+py)&1)==0
    if ey and ex:return 'R'
    if (not ey) and (not ex):return 'B'
    return 'G'
def phase_name(p,ox=0,oy=0): return ''.join(site(p,x,y,ox,oy) for y in (0,1) for x in (0,1))
expected={0:'RGGB',1:'GRBG',2:'GBRG',3:'BGGR'}
for p,name in expected.items():
    got=phase_name(p)
    if got!=name: raise SystemExit(f'VERIFY CFA oracle pattern {p}: {got} != {name}')
# Odd crop origins must rotate phase exactly, not retain marketing/source pattern labels.
if phase_name(0,1,0)!='GRBG' or phase_name(0,0,1)!='GBRG' or phase_name(0,1,1)!='BGGR':
    raise SystemExit('VERIFY origin parity oracle failed')
# Android LensShadingMap channels: R=0, green on even sensor row=1, green on odd row=2, B=3.
def shade_channel(p,x,y,ox=0,oy=0):
    s=site(p,x,y,ox,oy)
    if s=='R': return 0
    if s=='B': return 3
    return 1 if ((y+oy)&1)==0 else 2
for p in range(4):
    vals=[shade_channel(p,x,y) for y in (0,1) for x in (0,1)]
    if sorted(vals)!=[0,1,2,3]: raise SystemExit(f'VERIFY shading channel permutation failed p={p}: {vals}')

print('SOURCEADAPTER1B CFA/GEOMETRY verification OK')
print(' - SOURCE1D active-sensor DNG XYZ-Y remains primary')
print(' - SHARPSTD1B/MANUALISO1B baseline retained')
print(' - four Bayer patterns + origin parity covered')
print(' - semantic four-channel LensShadingMap lookup covered')
print(' - physical camera ID/focal length not rendering selectors')
