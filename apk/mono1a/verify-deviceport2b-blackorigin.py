#!/usr/bin/env python3
from pathlib import Path
import sys
if len(sys.argv)!=2: raise SystemExit('usage: verify-deviceport2b-blackorigin.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve()
R=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
N=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java'
C=root/'app/src/main/cpp/m9color_jni.cpp'
for p in (R,N,C):
    if not p.exists(): raise SystemExit('VERIFY missing '+str(p))
r,n,c=R.read_text(),N.read_text(),C.read_text()
def need(t,x,l):
    if x not in t: raise SystemExit('VERIFY missing '+l)
def forbid(t,x,l):
    if x in t: raise SystemExit('VERIFY forbidden '+l)
need(r,'MONO_DEVICEPORT2B_BLACK_ORIGIN','revision')
need(r,'normalizeRawDirectOriginAware','origin-aware production dispatch')
need(r,'blackPlaneOrigin0','legacy origin0 dispatch guard')
need(r,'sourceBlackLevelPlaneOriginAware\", true','telemetry')
need(r,'sensor_grid_2x2_row_major_with_RAW_origin_parity','plane rule')
need(n,'static native long normalizeRawDirectOriginAware','JNI declaration')
need(c,'Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_normalizeRawDirectOriginAware','JNI implementation')
need(c,'const int sensorPy=(y+originY)&1','sensor row parity')
need(c,'const int plane=sensorPy*2+((x+originX)&1)','sensor 2x2 plane')
# The generalized Bayer path must preserve Monochrom neutral MHC semantics. The
# pinned M9 portability helper's closure-sharp stage is foreign to this project and
# must not leak into the Monochrom source before its own frozen SHARPSTD1B stage.
need(c,'MONO_DEVICEPORT2B_MONOCHROM_CFA_NEUTRAL_PARITY','Monochrom generic CFA neutral parity marker')
need(c,'mhcNeutralGreenBayerPhase','phase-aware neutral green reconstruction')
need(c,'mhcPixelNeutralRbCompleteBayerPhase','phase-aware neutral RGB completion')
for token,label in (
    ('m9SharpSourceLeicaGreen14BayerPhase','foreign M9 CFA sharp helper'),
    ('m9SharpSourceRaw14At','foreign M9 sharp source accessor'),
    ('m9ClosureSharpIso160Standard','foreign M9 closure sharp stage'),
    ('m9ClosureQ14','foreign M9 closure Q14 helper'),
    ('m9ClosureClamp14','foreign M9 closure clamp helper'),
    ('m9ClosureQ16','foreign M9 closure Q16 helper')):
    forbid(c,token,label)
# Existing exact origin0 JNI must remain as a distinct unchanged route.
need(n,'static native long normalizeRawDirect(java.nio.ByteBuffer rawBuffer','legacy JNI declaration')
need(c,'Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_normalizeRawDirect(','legacy JNI implementation')
# Simple parity oracle: local origin shifts should rotate 2x2 plane indexes.
def planes(ox,oy): return [((y+oy)&1)*2+((x+ox)&1) for y in (0,1) for x in (0,1)]
if planes(0,0)!=[0,1,2,3]: raise SystemExit('origin0 plane oracle failed')
if planes(1,0)!=[1,0,3,2]: raise SystemExit('originX plane oracle failed')
if planes(0,1)!=[2,3,0,1]: raise SystemExit('originY plane oracle failed')
if planes(1,1)!=[3,2,1,0]: raise SystemExit('originXY plane oracle failed')
print('MONO DEVICEPORT2B black-origin verification OK')
print(' - Monochrom neutral MHC parity preserved; foreign M9 closure-sharp path absent')
