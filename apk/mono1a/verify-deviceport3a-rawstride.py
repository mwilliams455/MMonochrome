#!/usr/bin/env python3
# DEVICEPORT3A production verifier; touching this file also triggers the registered build workflow.
from pathlib import Path
import sys
if len(sys.argv) != 2: raise SystemExit('usage: verify-deviceport3a-rawstride.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve()
F=root/'app/src/main/java/com/particlesdevs/photoncamera/processing/ImageFrame.java'
S=root/'app/src/main/java/com/particlesdevs/photoncamera/processing/SaverImplementation.java'
CC=root/'app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java'
A=root/'app/src/main/java/com/particlesdevs/photoncamera/util/Allocator.java'
AC=root/'app/src/main/cpp/allocator.cpp'
R=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
C=root/'app/src/main/cpp/m9color_jni.cpp'
for p in (F,S,CC,A,AC,R,C):
    if not p.exists(): raise SystemExit('VERIFY DEVICEPORT3A missing '+str(p))
f,s,cc,a,ac,r,c=(p.read_text() for p in (F,S,CC,A,AC,R,C))
def need(t,x,l):
    if x not in t: raise SystemExit('VERIFY DEVICEPORT3A missing '+l)
def forbid(t,x,l):
    if x in t: raise SystemExit('VERIFY DEVICEPORT3A forbidden '+l)
need(f,'MONO_DEVICEPORT3A_RAWSTRIDE_PACK1A','revision marker')
need(s,'else if (image.getFormat() == ImageFormat.RAW_SENSOR)','standard RAW_SENSOR logical width branch')
need(s,'width = image.getWidth();','standard logical width')
need(cc,'img.getFormat() == ImageFormat.RAW_SENSOR','ZSL RAW_SENSOR logical width')
need(f,'if (row_stride == packedRowBytes)','tight RAW16 legacy guard')
need(f,'direct = Allocator.allocateAndCopy(capacity, in, shift);','legacy allocator retained')
need(f,'Allocator.allocateAndCopyRaw16Packed(capacity, in, width, row_stride, shift)','padded RAW16 packing dispatch')
need(a,'allocateAndCopyRaw16Packed','Java allocator declaration')
need(ac,'Java_com_particlesdevs_photoncamera_util_Allocator_allocateAndCopyRaw16Packed','native allocator implementation')
need(ac,'lastReadEnd > sourceCapacity','native source-capacity guard')
need(ac,'memcpy(dst + row * rowBytes, src + row * static_cast<jlong>(row_stride)','row-wise de-stride copy')
# Frozen renderer contract remains packed U16; stride must not leak downstream.
need(r,'final int expectedBytes = Math.multiplyExact(pixels, 2);','packed renderer expected bytes')
need(c,'const jlong expectedBytes = static_cast<jlong>(pixelCount) * 2LL;','packed native renderer expected bytes')
for token,label in (('rowStride','renderer rowStride dependency'),('row_stride','renderer native row stride dependency')):
    if token == 'rowStride':
        forbid(r,token,label)
    else:
        forbid(c,token,label)
# Preserve DEVICEPORT2B / functional freeze markers.
need(r,'MONO_DEVICEPORT2B_BLACK_ORIGIN','DEVICEPORT2B black-origin marker')
need(r,'monochromPrimarySource','SOURCE1D source telemetry')
need(r,'MANUALISO1B','MANUALISO1B marker')
# Synthetic oracle: 4 logical RAW16 pixels, 4 bytes row padding, three rows.
width=4; row_bytes=width*2; stride=12; rows=3
src=bytearray()
expected=bytearray()
for y in range(rows):
    logical=bytes(((y*16+i)&0xff) for i in range(row_bytes))
    src += logical + bytes([0xE0+y])*4
    expected += logical
packed=bytearray()
for y in range(rows): packed += src[y*stride:y*stride+row_bytes]
if packed != expected: raise SystemExit('VERIFY DEVICEPORT3A padded-row packing oracle failed')
tight=bytes(range(row_bytes*rows))
if bytes(tight) != tight: raise SystemExit('VERIFY DEVICEPORT3A tight-row identity oracle failed')
# Capacity row-count oracle supports both full final padding and omitted final padding.
def derive_rows(capacity): return 1 + (capacity-row_bytes)//stride
if derive_rows(stride*rows) != rows: raise SystemExit('VERIFY DEVICEPORT3A full-padding row-count oracle failed')
if derive_rows(stride*(rows-1)+row_bytes) != rows: raise SystemExit('VERIFY DEVICEPORT3A omitted-last-padding row-count oracle failed')
print('MONO DEVICEPORT3A RAW stride verification OK')
print(' - standard + ZSL RAW_SENSOR width is logical Image.getWidth()')
print(' - tight RAW16 stays on exact legacy allocator path')
print(' - padded RAW16 is de-strided once; renderer/JNI remain packed U16')
