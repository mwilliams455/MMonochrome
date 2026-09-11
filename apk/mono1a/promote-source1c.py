#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: promote-source1c.py <apply-mono1a.py>")
p = Path(sys.argv[1])
t = p.read_text()

def replace_once(old, new, label):
    global t
    n = t.count(old)
    if n != 1:
        raise SystemExit(f"{label} anchor count={n}, expected 1")
    t = t.replace(old, new, 1)

# 1) RenderCore can carry two auxiliary diagnostic bitmaps without changing the
# normal primary bitmap/result contract used by all other renderer paths.
anchor = 'renderer.write_text(r)\n\nn = native.read_text()\n'
insert = r'''r = replace_once(
    r,
    """    private static final class RenderCore {
        final Bitmap bitmap;
        final JSONObject diagnostics;
        RenderCore(Bitmap bitmap, JSONObject diagnostics) {
            this.bitmap = bitmap;
            this.diagnostics = diagnostics;
        }
    }
""",
    """    private static final class RenderCore {
        final Bitmap bitmap;
        final JSONObject diagnostics;
        final Bitmap source1cEqualRgbBitmap;
        final Bitmap source1cGreenBitmap;
        RenderCore(Bitmap bitmap, JSONObject diagnostics) {
            this(bitmap, diagnostics, null, null);
        }
        RenderCore(Bitmap bitmap, JSONObject diagnostics,
                   Bitmap source1cEqualRgbBitmap, Bitmap source1cGreenBitmap) {
            this.bitmap = bitmap;
            this.diagnostics = diagnostics;
            this.source1cEqualRgbBitmap = source1cEqualRgbBitmap;
            this.source1cGreenBitmap = source1cGreenBitmap;
        }
    }
""",
    "SOURCE1C RenderCore auxiliary bitmaps",
)

# SOURCE1C saves the two visual counterfactuals only after the normal primary JPEG
# payload has succeeded. Auxiliary failure must never invalidate the primary photo.
r = replace_once(
    r,
    """            bitmap = null;
            if (!jpgSaved) throw new IllegalStateException(\"M9 JPEG payload save failed\");
            if (SAVE_PARITY_PNG && !pngSaved) throw new IllegalStateException(\"M9 parity PNG save failed\");

            long elapsedMs = (System.nanoTime() - started) / 1_000_000L;
""",
    """            bitmap = null;
            if (!jpgSaved) throw new IllegalStateException(\"M9 JPEG payload save failed\");
            if (SAVE_PARITY_PNG && !pngSaved) throw new IllegalStateException(\"M9 parity PNG save failed\");

            Path source1cEqualRgbPath = null;
            Path source1cGreenPath = null;
            boolean source1cEqualRgbSaved = false;
            boolean source1cGreenSaved = false;
            String source1cEqualRgbError = null;
            String source1cGreenError = null;
            if (out.source1cEqualRgbBitmap != null) {
                source1cEqualRgbPath = Paths.get(FileManager.sDCIM_CAMERA.getAbsolutePath(),
                        stem + \"_MONO_EQUALRGB.jpg\");
                try (OutputStream auxOut = Files.newOutputStream(source1cEqualRgbPath)) {
                    source1cEqualRgbSaved = out.source1cEqualRgbBitmap.compress(
                            Bitmap.CompressFormat.JPEG, JPEG_QUALITY, auxOut);
                    auxOut.flush();
                } catch (Throwable auxError) {
                    source1cEqualRgbError = auxError.toString();
                } finally {
                    if (!out.source1cEqualRgbBitmap.isRecycled()) out.source1cEqualRgbBitmap.recycle();
                }
            }
            if (out.source1cGreenBitmap != null) {
                source1cGreenPath = Paths.get(FileManager.sDCIM_CAMERA.getAbsolutePath(),
                        stem + \"_MONO_GREEN.jpg\");
                try (OutputStream auxOut = Files.newOutputStream(source1cGreenPath)) {
                    source1cGreenSaved = out.source1cGreenBitmap.compress(
                            Bitmap.CompressFormat.JPEG, JPEG_QUALITY, auxOut);
                    auxOut.flush();
                } catch (Throwable auxError) {
                    source1cGreenError = auxError.toString();
                } finally {
                    if (!out.source1cGreenBitmap.isRecycled()) out.source1cGreenBitmap.recycle();
                }
            }

            long elapsedMs = (System.nanoTime() - started) / 1_000_000L;
""",
    "SOURCE1C auxiliary JPEG save",
)

r = replace_once(
    r,
    '            diag.put("jpegPath", jpgPath.toString());\n',
    '''            diag.put("jpegPath", jpgPath.toString());
            diag.put("source1cVisualAbEnabled", true);
            diag.put("source1cControlJpegPath", jpgPath.toString());
            diag.put("source1cControlMode", "M9Y_Q14");
            if (source1cEqualRgbPath != null) {
                diag.put("source1cEqualRgbJpegPath", source1cEqualRgbPath.toString());
                diag.put("source1cEqualRgbJpegSaved", source1cEqualRgbSaved);
                if (source1cEqualRgbError != null) diag.put("source1cEqualRgbJpegError", source1cEqualRgbError);
            }
            if (source1cGreenPath != null) {
                diag.put("source1cGreenJpegPath", source1cGreenPath.toString());
                diag.put("source1cGreenJpegSaved", source1cGreenSaved);
                if (source1cGreenError != null) diag.put("source1cGreenJpegError", source1cGreenError);
            }
''',
    "SOURCE1C auxiliary JPEG diagnostics",
)

renderer.write_text(r)

n = native.read_text()
'''
replace_once(anchor, insert + '\n', 'insert SOURCE1C renderer patches')

# 2) Create both counterfactual bitmaps from the exact same post-MHC cam16 buffer.
replace_once(
    '''                if (!monoOk) {
                    if (!monoBitmap.isRecycled()) monoBitmap.recycle();
                    throw new IllegalStateException("MONO1A native direct Bitmap render failed");
                }
                JSONObject d = new JSONObject();
''',
    '''                if (!monoOk) {
                    if (!monoBitmap.isRecycled()) monoBitmap.recycle();
                    throw new IllegalStateException("MONO1A native direct Bitmap render failed");
                }
                Bitmap equalRgbBitmap = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888);
                Bitmap greenOnlyBitmap = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888);
                boolean equalRgbOk = M9NativeColorCore.renderMonochrome1AVariantDirectBitmap(
                        cam16.dataAddr(), pixels, width, height, equalRgbBitmap,
                        cameraRotation, NATIVE_COLOR_WORKERS,
                        MONO1A_SYNTHETIC_PEDESTAL14, 1);
                boolean greenOnlyOk = equalRgbOk && M9NativeColorCore.renderMonochrome1AVariantDirectBitmap(
                        cam16.dataAddr(), pixels, width, height, greenOnlyBitmap,
                        cameraRotation, NATIVE_COLOR_WORKERS,
                        MONO1A_SYNTHETIC_PEDESTAL14, 2);
                if (!equalRgbOk || !greenOnlyOk) {
                    if (!monoBitmap.isRecycled()) monoBitmap.recycle();
                    if (!equalRgbBitmap.isRecycled()) equalRgbBitmap.recycle();
                    if (!greenOnlyBitmap.isRecycled()) greenOnlyBitmap.recycle();
                    throw new IllegalStateException("MONO1A SOURCE1C auxiliary Bitmap render failed");
                }
                JSONObject d = new JSONObject();
''',
    'SOURCE1C same-buffer visual renders')

replace_once(
    '                d.put("counterfactualGreenOnly", greenOnly);\n                return new RenderCore(monoBitmap, d);\n',
    '''                d.put("counterfactualGreenOnly", greenOnly);
                d.put("source1cVisualAbRendered", true);
                d.put("source1cVisualAbPolicy", "same_post_MHC_cam16_same_curve02_no_auto_selection");
                d.put("source1cEqualRgbMode", "((R+G+B)/3)>>>2_to_Leica14_then_curve02");
                d.put("source1cGreenMode", "G>>>2_to_Leica14_then_curve02");
                return new RenderCore(monoBitmap, d, equalRgbBitmap, greenOnlyBitmap);
''',
    'SOURCE1C RenderCore return')

# 3) Add a native entry point for a selected visual counterfactual. It intentionally
# has no diagnostics/statistics output and cannot become the selected primary JPEG.
replace_once(
    '''                                                         int pedestal14,
                                                         long[] stats);
"""
''',
    '''                                                         int pedestal14,
                                                         long[] stats);

    /** SOURCE1C visual counterfactual only. mode 1=equal RGB, 2=green-only. */
    static native boolean renderMonochrome1AVariantDirectBitmap(long camAddress,
                                                                int pixelCount,
                                                                int width,
                                                                int sourceHeight,
                                                                android.graphics.Bitmap bitmap,
                                                                int cameraRotation,
                                                                int workers,
                                                                int pedestal14,
                                                                int sourceMode);
"""
''',
    'SOURCE1C native declaration')

# 4) Append a compact native visual renderer. It reuses the exact firmware LUT and
# orientation helper and differs from control only in the scalar source coordinate.
replace_once(
    '''    env->SetLongArrayRegion(statsArray, 0, 35, stats);
    return env->ExceptionCheck() ? JNI_FALSE : JNI_TRUE;
}
'''.replace('__CURVE_VALUES__', '__CURVE_VALUES__'),
    '''    env->SetLongArrayRegion(statsArray, 0, 35, stats);
    return env->ExceptionCheck() ? JNI_FALSE : JNI_TRUE;
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1AVariantDirectBitmap(
        JNIEnv* env, jclass,
        jlong camAddress,
        jint pixelCount,
        jint width,
        jint sourceHeight,
        jobject bitmap,
        jint cameraRotation,
        jint workers,
        jint pedestal14,
        jint sourceMode) {
    const auto* cam = reinterpret_cast<const jshort*>(static_cast<uintptr_t>(camAddress));
    if (!cam || !bitmap || width <= 0 || sourceHeight <= 0
            || pixelCount != width * sourceHeight || workers <= 0
            || pedestal14 < 0 || pedestal14 > 16383
            || (sourceMode != 1 && sourceMode != 2)) {
        throwIllegalArgument(env, "Invalid MONO1A SOURCE1C variant arguments");
        return JNI_FALSE;
    }
    int rotation = cameraRotation % 360;
    if (rotation < 0) rotation += 360;
    const uint32_t expectedWidth = static_cast<uint32_t>(
            (rotation == 90 || rotation == 270) ? sourceHeight : width);
    const uint32_t expectedHeight = static_cast<uint32_t>(
            (rotation == 90 || rotation == 270) ? width : sourceHeight);
    AndroidBitmapInfo info{};
    if (AndroidBitmap_getInfo(env, bitmap, &info) != ANDROID_BITMAP_RESULT_SUCCESS
            || info.format != ANDROID_BITMAP_FORMAT_RGBA_8888
            || info.width != expectedWidth || info.height != expectedHeight
            || info.stride < expectedWidth * 4u) return JNI_FALSE;
    void* rawPixels = nullptr;
    if (AndroidBitmap_lockPixels(env, bitmap, &rawPixels) != ANDROID_BITMAP_RESULT_SUCCESS
            || rawPixels == nullptr) return JNI_FALSE;

    std::vector<jint> argb(static_cast<size_t>(pixelCount));
    const int workerCount = std::max(1, std::min(static_cast<int>(workers), sourceHeight));
    std::vector<std::thread> threads;
    threads.reserve(static_cast<size_t>(workerCount));
    auto* bitmapBase = static_cast<uint8_t*>(rawPixels);
    for (int worker = 0; worker < workerCount; ++worker) {
        const int y0 = (sourceHeight * worker) / workerCount;
        const int y1 = (sourceHeight * (worker + 1)) / workerCount;
        threads.emplace_back([&, y0, y1]() {
            for (int y = y0; y < y1; ++y) {
                const size_t row = static_cast<size_t>(y) * static_cast<size_t>(width);
                for (int x = 0; x < width; ++x) {
                    const size_t p = row + static_cast<size_t>(x);
                    const size_t ci = p * 3u;
                    const uint32_t r = u16(cam[ci]);
                    const uint32_t g = u16(cam[ci + 1]);
                    const uint32_t b = u16(cam[ci + 2]);
                    const uint32_t source16 = sourceMode == 1 ? ((r + g + b) / 3u) : g;
                    const int32_t sample14 = static_cast<int32_t>(
                            std::min<uint32_t>(16383u, source16 >> 2));
                    int32_t v = sample14 - static_cast<int32_t>(pedestal14);
                    if (v < 0) v = 0;
                    int32_t idx = v >> 3;
                    if (idx > 2047) idx = 2047;
                    const uint8_t yy = MM_MONO1A_CURVE02[idx];
                    argb[p] = static_cast<jint>(0xff000000u
                            | (static_cast<uint32_t>(yy) << 16)
                            | (static_cast<uint32_t>(yy) << 8)
                            | static_cast<uint32_t>(yy));
                }
            }
            writeCompletedSubrangeToBitmap(argb.data(), bitmapBase, info.stride,
                    sourceHeight, width, 0, sourceHeight, y0, y1, cameraRotation);
        });
    }
    for (auto& thread : threads) thread.join();
    const int unlockResult = AndroidBitmap_unlockPixels(env, bitmap);
    return unlockResult == ANDROID_BITMAP_RESULT_SUCCESS && !env->ExceptionCheck()
            ? JNI_TRUE : JNI_FALSE;
}
''',
    'SOURCE1C native visual renderer')

# Authoritative revision/schema labels. Photographic control source remains M9-Y.
t = t.replace('MONO1A_SOURCE1B', 'MONO1A_SOURCE1C')
t = t.replace('mmonochrome.mono1a.source1b.v1', 'mmonochrome.mono1a.source1c.v1')

p.write_text(t)
print('MONO1A SOURCE1C visual A/B promoted')
