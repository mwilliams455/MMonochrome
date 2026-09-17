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
need(r,'MONO_DEVICEPORT2B_BLACK_ORIGIN','revision')
need(r,'normalizeRawDirectOriginAware','origin-aware production dispatch')
need(r,'blackPlaneOrigin0','legacy origin0 dispatch guard')
need(r,'sourceBlackLevelPlaneOriginAware", true','telemetry')
need(r,'sensor_grid_2x2_row_major_with_RAW_origin_parity','plane rule')
need(n,'static native long normalizeRawDirectOriginAware','JNI declaration')
need(c,'Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_normalizeRawDirectOriginAware','JNI implementation')
need(c,'const int sensorPy=(y+originY)&1','sensor row parity')
need(c,'const int plane=sensorPy*2+((x+originX)&1)','sensor 2x2 plane')
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
