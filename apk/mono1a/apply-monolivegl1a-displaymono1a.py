#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply-monolivegl1a-displaymono1a.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
main_renderer = root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java"
gl_preview = root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/GLPreview.java"
camera_fragment = root / "app/src/main/java/com/particlesdevs/photoncamera/ui/camera/CameraFragment.java"
main_fs = root / "app/src/main/assets/shaders/preview/main_fs.glsl"

for p in (main_renderer, gl_preview, camera_fragment, main_fs):
    if not p.exists():
        raise SystemExit("MONOLIVEGL1A missing assembled file: " + str(p))

def one(text, old, new, label):
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"MONOLIVEGL1A {label}: expected 1 anchor, found {n}")
    return text.replace(old, new, 1)

# ---------------------------------------------------------------------------
# 1) Replace only Photon's display shader.
#    Input is already display-rendered OES sRGB, so do NOT apply sensor-domain
#    Camera2 matrices, SOURCE1D transforms, Cobalt/HSM, or RAW-domain tone.
# ---------------------------------------------------------------------------
shader = r'''#extension GL_OES_EGL_image_external_essl3 : require
precision highp float;

// MONOLIVEGL1A_DISPLAYMONO1A
uniform samplerExternalOES sTexture;
uniform vec2 resolution;
uniform bool enablePeak;
uniform bool mirror;
uniform float uMonoExposureScale1A;
out vec4 Output;
in vec2 texCoord;

vec3 srgbToLinearMono1A(vec3 c) {
    vec3 lo = c / 12.92;
    vec3 hi = pow((c + vec3(0.055)) / 1.055, vec3(2.4));
    return mix(lo, hi, step(vec3(0.04045), c));
}

float linearToSrgbMono1A(float x) {
    x = max(x, 0.0);
    if (x <= 0.0031308)
        return 12.92 * x;
    return 1.055 * pow(x, 1.0 / 2.4) - 0.055;
}

vec3 monoDisplayTransform1A(vec3 photonSrgb) {
    vec3 linear = srgbToLinearMono1A(clamp(photonSrgb, vec3(0.0), vec3(1.0)));

    // Preview-only exposure representation. This is target ISO*shutter divided
    // by the actual hardware preview ISO*shutter. The still allocator is not
    // changed by this shader.
    linear *= uMonoExposureScale1A;

    // DISPLAY DOMAIN ONLY. The authoritative still path derives monochrome from
    // SOURCE1D native DNG XYZ-Y; replaying that sensor transform onto OES would
    // double-process the already display-rendered preview. Rec.709 linear Y is
    // therefore only the live carrier; residual tone is calibrated separately.
    float y = dot(linear, vec3(0.2126, 0.7152, 0.0722));

    // DISPLAYMONO1A intentionally applies no guessed still-tone curve yet.
    // First device pairs will measure the display-domain residual against the
    // final Monochrom JPEG, following the validated M9 GL approach.
    float outY = clamp(y, 0.0, 1.0);
    float s = clamp(linearToSrgbMono1A(outY), 0.0, 1.0);
    return vec3(s);
}

void main() {
    vec2 uv = texCoord.xy;
    if (mirror)
        uv.y = 1.0 - uv.y;

    vec4 photonColor = texture(sTexture, uv);
    vec4 color = vec4(monoDisplayTransform1A(photonColor.rgb), 1.0);

    // Preserve Photon's focus-peaking UI, but avoid the 9-sample neighborhood
    // unless peaking is actually enabled.
    if (enablePeak) {
        vec2 size = resolution;
        vec4 avg = vec4(0.0);
        for (int i = -1; i <= 1; i++) {
            for (int j = -1; j <= 1; j++) {
                avg += texture(sTexture, uv + vec2(i * 2, j * 2) / size);
            }
        }
        avg /= 9.0;
        float diff = dot(abs(photonColor - avg), vec4(0.299, 0.587, 0.114, 0.0));
        float denoiseK = 0.05;
        float w = (diff * diff) / (denoiseK + (diff * diff));
        color = color + vec4(1.0, 0.0, 1.0, 0.0) * 32.0 * diff * w;
    }

    Output = color;
}
'''
main_fs.write_text(shader)

# ---------------------------------------------------------------------------
# 2) MainRenderer uniform / setter.
# ---------------------------------------------------------------------------
mr = main_renderer.read_text()
if "MONOLIVEGL1A_DISPLAYMONO1A" in mr:
    raise SystemExit("MONOLIVEGL1A MainRenderer already patched")

field_anchor = """    private boolean mGLInit = false;
    private boolean mUpdateST = false;
    private volatile boolean mMirrorPreview;
"""
field_new = """    private boolean mGLInit = false;
    private boolean mUpdateST = false;
    private volatile boolean mMirrorPreview;

    // MONOLIVEGL1A_DISPLAYMONO1A
    private volatile float mMonoExposureScale1A = 1.0f;
"""
mr = one(mr, field_anchor, field_new, "renderer exposure field")

uniform_field_anchor = """    private int enablePeak;
    private int mirror;
"""
uniform_field_new = """    private int enablePeak;
    private int mirror;
    private int uMonoExposureScale1A;
"""
mr = one(mr, uniform_field_anchor, uniform_field_new, "renderer uniform field")

draw_anchor = """        GLES20.glUniform1i(enablePeak, peakEnabled);
        GLES20.glUniform1i(mirror, mMirrorPreview ? 1 : 0);

        GLES20.glVertexAttribPointer(vPosition, 2, GLES20.GL_FLOAT, false, 4 * 2, pVertex);
"""
draw_new = """        GLES20.glUniform1i(enablePeak, peakEnabled);
        GLES20.glUniform1i(mirror, mMirrorPreview ? 1 : 0);
        GLES20.glUniform1f(uMonoExposureScale1A, mMonoExposureScale1A);

        GLES20.glVertexAttribPointer(vPosition, 2, GLES20.GL_FLOAT, false, 4 * 2, pVertex);
"""
mr = one(mr, draw_anchor, draw_new, "renderer exposure upload")

surface_anchor = """        enablePeak = GLES20.glGetUniformLocation(hProgram, "enablePeak");
        mirror = GLES20.glGetUniformLocation(hProgram, "mirror");
        GLES20.glVertexAttribPointer(vPosition, 2, GLES20.GL_FLOAT, false, 4 * 2, pVertex);
"""
surface_new = """        enablePeak = GLES20.glGetUniformLocation(hProgram, "enablePeak");
        mirror = GLES20.glGetUniformLocation(hProgram, "mirror");
        uMonoExposureScale1A = GLES20.glGetUniformLocation(hProgram, "uMonoExposureScale1A");
        Log.d("MonoLiveGL1A", "MONOLIVEGL1A_DISPLAYMONO1A Photon OES display-domain preview active");
        GLES20.glVertexAttribPointer(vPosition, 2, GLES20.GL_FLOAT, false, 4 * 2, pVertex);
"""
mr = one(mr, surface_anchor, surface_new, "renderer exposure uniform location")

setter_anchor = """    public void setMirror(boolean mirrorPreview) {
        mMirrorPreview = mirrorPreview;
    }
"""
setter_new = """    public void setMonoExposureScale1A(float scale) {
        if (!Float.isFinite(scale) || scale <= 0.0f) scale = 1.0f;
        // Preview transport guard only: +/-4 EV. No capture mutation.
        mMonoExposureScale1A = Math.max(0.0625f, Math.min(16.0f, scale));
        mView.requestRender();
    }

    public void setMirror(boolean mirrorPreview) {
        mMirrorPreview = mirrorPreview;
    }
"""
mr = one(mr, setter_anchor, setter_new, "renderer exposure setter")
main_renderer.write_text(mr)

# ---------------------------------------------------------------------------
# 3) GLPreview bridge.
# ---------------------------------------------------------------------------
gp = gl_preview.read_text()
mirror_anchor = """    public void setMirror(boolean mirror) {
        mRenderer.setMirror(mirror);
        requestRender();
    }
"""
mirror_new = mirror_anchor + """
    /** MONOLIVEGL1A: intended still energy / actual hardware-preview energy. */
    public void setMonoExposureScale1A(float scale) {
        if (mRenderer != null) {
            mRenderer.setMonoExposureScale1A(scale);
        }
    }
"""
gp = one(gp, mirror_anchor, mirror_new, "GLPreview exposure bridge")
gl_preview.write_text(gp)

# ---------------------------------------------------------------------------
# 4) CameraFragment: represent the same current non-ZSL IsoExpoSelector target
#    in the OES preview. This is PREVIEW ONLY; capture still recomputes through
#    the frozen allocator at shutter time.
# ---------------------------------------------------------------------------
cf = camera_fragment.read_text()
field_anchor = """    private long lastHudUpdateTime = 0;
"""
field_new = """    // MONOLIVEGL1A_DISPLAYMONO1A
    private long lastMonoPreviewExposureUpdateMs1A = 0L;

    private long lastHudUpdateTime = 0;
"""
cf = one(cf, field_anchor, field_new, "CameraFragment throttle field")

method_anchor = """    @SuppressLint("DefaultLocale")
    private void updateScreenLog(CaptureResult result) {
        surfaceView.post(() -> {
"""
method_new = r'''    @SuppressLint("DefaultLocale")
    private void updateScreenLog(CaptureResult result) {
        // MONOLIVEGL1A_DISPLAYMONO1A
        // Photon OES is hardware-AE display imagery. Non-ZSL still capture is
        // allocated by IsoExpoSelector. Represent that current intended energy
        // in linear display space without changing the still capture path.
        if (textureView != null && captureController != null && result != null) {
            try {
                if (captureController.isZslMode()) {
                    textureView.setMonoExposureScale1A(1.0f);
                } else {
                    long nowMono1A = android.os.SystemClock.uptimeMillis();
                    if (nowMono1A - lastMonoPreviewExposureUpdateMs1A >= 50L) {
                        lastMonoPreviewExposureUpdateMs1A = nowMono1A;
                        Long actualExposureNs1A = result.get(CaptureResult.SENSOR_EXPOSURE_TIME);
                        Integer actualIso1A = result.get(CaptureResult.SENSOR_SENSITIVITY);
                        IsoExpoSelector.ExpoPair intended1A =
                                IsoExpoSelector.GenerateExpoPair(-1, captureController);
                        if (actualExposureNs1A != null && actualExposureNs1A > 0L
                                && actualIso1A != null && actualIso1A > 0
                                && intended1A != null
                                && intended1A.exposure > 0L && intended1A.iso > 0) {
                            double actualEnergy1A =
                                    (double) actualExposureNs1A * (double) actualIso1A;
                            double intendedEnergy1A =
                                    (double) intended1A.exposure * (double) intended1A.iso;
                            double scale1A = intendedEnergy1A / actualEnergy1A;
                            if (Double.isFinite(scale1A) && scale1A > 0.0) {
                                textureView.setMonoExposureScale1A((float) scale1A);
                            }
                        }
                    }
                }
            } catch (Throwable t) {
                Log.w(TAG, "MONOLIVEGL1A exposure representation failed: " + t);
            }
        }
        surfaceView.post(() -> {
'''
cf = one(cf, method_anchor, method_new, "CameraFragment exposure representation")
camera_fragment.write_text(cf)

print("MONOLIVEGL1A_DISPLAYMONO1A applied")
print(" - Photon OES remains the live carrier")
print(" - non-ZSL intended ISO*shutter is represented in linear display space")
print(" - OES is converted to linear Rec.709 luminance and shown monochrome")
print(" - no guessed still-tone curve is applied yet")
print(" - capture allocator, SOURCE1D, RAW/JPEG renderer and DEVICEPORT3A are untouched")
