#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply-deviceport3a-rawstride.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
F = root/'app/src/main/java/com/particlesdevs/photoncamera/processing/ImageFrame.java'
S = root/'app/src/main/java/com/particlesdevs/photoncamera/processing/SaverImplementation.java'
CC = root/'app/src/main/java/com/particlesdevs/photoncamera/capture/CaptureController.java'
A = root/'app/src/main/java/com/particlesdevs/photoncamera/util/Allocator.java'
AC = root/'app/src/main/cpp/allocator.cpp'
for p in (F,S,CC,A,AC):
    if not p.exists(): raise SystemExit('DEVICEPORT3A missing '+str(p))

def one(text, old, new, label):
    n=text.count(old)
    if n != 1: raise SystemExit(f'DEVICEPORT3A {label}: anchor count={n}, expected 1')
    return text.replace(old,new,1)

f,s,cc,a,ac=(p.read_text() for p in (F,S,CC,A,AC))
if 'MONO_DEVICEPORT3A_RAWSTRIDE_PACK1A' in f:
    raise SystemExit('DEVICEPORT3A already applied')

# Standard still-capture path: RAW_SENSOR logical width is Image.getWidth().
# rowStride may include padding and must never be reinterpreted as extra pixels.
s=one(s,
'''import android.hardware.camera2.CameraCharacteristics;\n''',
'''import android.graphics.ImageFormat;\nimport android.hardware.camera2.CameraCharacteristics;\n''',
'Saver ImageFormat import')
s=one(s,
'''        if(image.getFormat() == 0x25){\n            width = image.getWidth();\n            height = image.getHeight();\n        } else {\n            width = image.getPlanes()[0].getRowStride() /\n                    image.getPlanes()[0].getPixelStride();\n            height = image.getHeight();\n        }\n''',
'''        if(image.getFormat() == 0x25){\n            width = image.getWidth();\n            height = image.getHeight();\n        } else if (image.getFormat() == ImageFormat.RAW_SENSOR) {\n            // MONO_DEVICEPORT3A_RAWSTRIDE_PACK1A: RAW_SENSOR width is logical image\n            // width. rowStride is transport layout and may include row padding.\n            width = image.getWidth();\n            height = image.getHeight();\n        } else {\n            width = image.getPlanes()[0].getRowStride() /\n                    image.getPlanes()[0].getPixelStride();\n            height = image.getHeight();\n        }\n''',
'Saver RAW_SENSOR logical width')

# ZSL bypasses SaverImplementation and constructs ImageFrame directly, so apply
# the same logical-width rule there. RAW10 and all non-RAW_SENSOR fallbacks stay intact.
cc=one(cc,
'''            int width = (img.getFormat() == ImageFormat.RAW10)\n                    ? img.getWidth()\n                    : (pixelStride > 0 ? rowStride / pixelStride : img.getWidth());\n''',
'''            int width = (img.getFormat() == ImageFormat.RAW10\n                    || img.getFormat() == ImageFormat.RAW_SENSOR)\n                    ? img.getWidth()\n                    : (pixelStride > 0 ? rowStride / pixelStride : img.getWidth());\n''',
'ZSL RAW_SENSOR logical width')

# Preserve the exact legacy allocator for already-tight RAW_SENSOR buffers. Only
# padded RAW16 rows take the new one-time de-stride path. Renderer/JNI stay packed-U16.
f=one(f,
'''        } else {\n            if(format == 0x25){\n                direct = Allocator.allocateAndCopyConvert(capacity, in, width, row_stride, shift);\n            } else {\n                direct = Allocator.allocateAndCopy(capacity, in, shift);\n            }\n        }\n''',
'''        } else {\n            if(format == 0x25){\n                direct = Allocator.allocateAndCopyConvert(capacity, in, width, row_stride, shift);\n            } else if (format == ImageFormat.RAW_SENSOR) {\n                final int packedRowBytes = Math.multiplyExact(width, 2);\n                if (row_stride < packedRowBytes) {\n                    throw new IllegalArgumentException("MONO DEVICEPORT3A RAW16 rowStride smaller than logical row");\n                }\n                if (row_stride == packedRowBytes) {\n                    // MONO_DEVICEPORT3A_RAWSTRIDE_PACK1A: exact legacy path for already-tight RAW16.\n                    direct = Allocator.allocateAndCopy(capacity, in, shift);\n                } else {\n                    direct = Allocator.allocateAndCopyRaw16Packed(capacity, in, width, row_stride, shift);\n                }\n            } else {\n                direct = Allocator.allocateAndCopy(capacity, in, shift);\n            }\n        }\n''',
'ImageFrame padded RAW16 dispatch')

# Java declaration for the one-time capture-boundary de-strider.
a=one(a,
'''    public native static ByteBuffer allocateAndCopy(int capacity, ByteBuffer origin, int offset);\n''',
'''    public native static ByteBuffer allocateAndCopy(int capacity, ByteBuffer origin, int offset);\n    public native static ByteBuffer allocateAndCopyRaw16Packed(int capacity, ByteBuffer origin, int width, int row_stride, int offset);\n''',
'Allocator declaration')

# Native row packer. `capacity` is the requested source span (and preserves Photon's
# existing 16:9 crop contract); direct-buffer capacity is independently checked for
# the actual last logical pixel. Handles buffers with or without final-row padding.
marker='''extern "C"\nJNIEXPORT jobject JNICALL\nJava_com_particlesdevs_photoncamera_util_Allocator_allocateAndCopyConvert(JNIEnv *env, jclass clazz,\n'''
if ac.count(marker) != 1:
    raise SystemExit(f'DEVICEPORT3A allocator native anchor count={ac.count(marker)}, expected 1')
fn=r'''extern "C"
JNIEXPORT jobject JNICALL
Java_com_particlesdevs_photoncamera_util_Allocator_allocateAndCopyRaw16Packed(
        JNIEnv *env, jclass clazz, jint capacity, jobject originBuffer,
        jint width, jint row_stride, jint offset) {
    if (originBuffer == nullptr || width <= 0 || row_stride <= 0 || offset < 0 || capacity <= 0) {
        LOGD("MONO DEVICEPORT3A invalid RAW16 pack arguments");
        return nullptr;
    }
    const jlong rowBytes = static_cast<jlong>(width) * static_cast<jlong>(sizeof(uint16_t));
    if (row_stride < rowBytes || capacity < rowBytes) {
        LOGD("MONO DEVICEPORT3A RAW16 row/capacity too small: width=%d rowStride=%d capacity=%d",
             width, row_stride, capacity);
        return nullptr;
    }
    // Photon historically expresses a desired span as rowStride*height. Some HAL
    // buffers omit final-row padding, so derive rows from the last logical row rather
    // than requiring capacity to be an exact multiple of rowStride.
    const jlong rows = 1LL + (static_cast<jlong>(capacity) - rowBytes) / static_cast<jlong>(row_stride);
    const jlong outputSize = rowBytes * rows;
    const jlong sourceCapacity = env->GetDirectBufferCapacity(originBuffer);
    const jlong lastReadEnd = static_cast<jlong>(offset)
            + (rows - 1LL) * static_cast<jlong>(row_stride) + rowBytes;
    if (rows <= 0 || outputSize <= 0 || sourceCapacity < 0 || lastReadEnd > sourceCapacity) {
        LOGD("MONO DEVICEPORT3A RAW16 source span invalid: rows=%lld out=%lld end=%lld cap=%lld",
             static_cast<long long>(rows), static_cast<long long>(outputSize),
             static_cast<long long>(lastReadEnd), static_cast<long long>(sourceCapacity));
        return nullptr;
    }
    void* srcPtr = env->GetDirectBufferAddress(originBuffer);
    if (srcPtr == nullptr) {
        LOGD("MONO DEVICEPORT3A failed to get RAW16 direct buffer address");
        return nullptr;
    }
    void* allocation = malloc(static_cast<size_t>(outputSize));
    if (allocation == nullptr) {
        LOGD("MONO DEVICEPORT3A failed to allocate RAW16 packed buffer of %lld bytes",
             static_cast<long long>(outputSize));
        return nullptr;
    }
    const auto* src = reinterpret_cast<const uint8_t*>(srcPtr) + offset;
    auto* dst = static_cast<uint8_t*>(allocation);
    for (jlong row = 0; row < rows; ++row) {
        memcpy(dst + row * rowBytes, src + row * static_cast<jlong>(row_stride),
               static_cast<size_t>(rowBytes));
    }
    jobject buffer = env->NewDirectByteBuffer(allocation, outputSize);
    if (buffer == nullptr) {
        free(allocation);
        LOGD("MONO DEVICEPORT3A failed to create RAW16 packed ByteBuffer");
        return nullptr;
    }
    memoryCount += static_cast<long>(outputSize);
    LOGD("MONO DEVICEPORT3A RAW16 packed: width=%d rows=%lld rowStride=%d -> %lld bytes",
         width, static_cast<long long>(rows), row_stride, static_cast<long long>(outputSize));
    return buffer;
}

'''
ac=ac.replace(marker,fn+marker,1)

for p,text in ((F,f),(S,s),(CC,cc),(A,a),(AC,ac)):
    p.write_text(text)
print('MONO_DEVICEPORT3A_RAWSTRIDE_PACK1A applied')
print(' - RAW_SENSOR logical width now comes from Image.getWidth() in standard and ZSL capture')
print(' - tight RAW16 preserves exact legacy allocateAndCopy path')
print(' - padded RAW16 is packed once before the renderer; renderer/JNI contract unchanged')
