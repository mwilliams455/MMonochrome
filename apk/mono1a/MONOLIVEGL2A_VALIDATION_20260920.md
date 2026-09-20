# MONOLIVEGL2A — controlled source, native Monochrom GPU target

20 September 2026. Research candidate, NOT phone pixel-parity validated.

The ordinary-light holdout invalidated the fixed GL1D three-scene residual as a general preview model. This candidate removes that active residual rather than trim it again. Reference architecture: M9Camera_refresh 87f0b766df071b649f1dc205ac6ab22fc11eb7a2 (itself a candidate needing device validation). Monochrom does not import that camera's target colour, HSM, SAT2, TG1, TC20 or firmware tone curve.

## Actual implementation

Repeating preview requests capability-gated CONTRAST_CURVE with up to 64 sRGB-like points; AE/AWB policy is retained. The actual returned monotonic per-channel curves, colour transform, WB gains and post-RAW boost are inverted to reconstruct approximate sensor RGB. A read-only exporter returns the exact native SOURCE1D XYZ-D50 Y row from the production builder. The shader applies the existing exposure multiplier, uint16 coordinate rounding/clipping and the actual 2048-byte M Monochrom curve02 extracted from the frozen JNI array.

Curve SHA256: 7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752.

No fitted residual, device-name appearance branch, extra RAW stream, CPU RAW-rendering loop, second LensShadingMap multiplication, HDR or Cobalt adapter is added. Unsupported/incomplete/noninvertible metadata uses an explicitly reported exposure-aware monochrome OES approximation. Controlled metadata is not proof of actual HAL pixel behavior; ISP demosaic/shading/gamut clipping remain limitations.

Immutable draw bindings retain source context, actual uniform exposure, OES timestamp and result timestamps. Exact physical/transport matches are distinguished from recent-metadata fallback. A 48x64 or 64x48 probe, at most once/second, packs incoming OES RGB and outgoing monochrome code from the same texture and shader. The probe is not a compositor screenshot or sampled RAW; it has explicit age and readback cost. GPU readback can hitch and phone cadence remains unvalidated.

New evidence lives under monoLivePair.previewSource2A, including draw.source2A readiness and targetShaderEnabled. The existing successful burst export is retained; a separate live-pair file is not required.

## Preserved boundaries

JNI, allocator, saver, CameraFragment, GLPreview, deferred metadata store and diagnostic spool are byte-identical. Removing the marked read-only exporter restores the entire parent M9R35Renderer byte-for-byte. The full captureStillPicture, triggerZslCapture and takePicture method bodies are also unchanged in downloaded assembled source. No still-tone or exposure-offset fix is applied.

The incoming preview response changes, so the YUV statistics used by the existing auto logic can change. Frozen policy arithmetic is NOT a promise of identical Auto ISO/shutter results. Histogram overlays were not independently revalidated.

## Verified build and tests

Branch: research/monolivegl2a-controlledoes.
Build commit: 4a13aaf385b89fe2cbfce953e927d18f37fdc0e8.
Baseline: 4a5ee7a67f1e8169a784be071534c97549aa6012 / GL1E1D.
Actions run: 35522715749; job: 106109457181. All steps succeeded, including Android compilation and packaged asset/DEX checks.
APK artifact: 10608683387. Evidence artifact: 10608568587.
APK SHA256: 843f65e180a30a76b18da5089a9b39b516317542cbda66838227b4bfcb6daf13.
APK bytes: 115444605.

Math: 141085 assertions, primarily exhaustive scalar-coordinate checks plus inverse transport and matrix/WB/boost order. Real metadata/binding class with mocked Android/JSON: 39 assertions, including missing physical metadata, unsupported controls, immutable context, stale/future snapshots and camera switching.

Mesa GLES3 executed the production fragment shader with external input replaced only by a synthetic 2D sampler; a separate injection isolates its scalar stage. Reference C++ body and firmware bytes are extracted from the unchanged SOURCE1D JNI kernel. CI: 57344 synthetic pixel comparisons, maximum one output-code difference (one generic-weight scalar vector); all 24576 full-path exposure-bracket comparisons equal. Probe RGB/alpha matched source/separate target output exactly. Controlled and fallback exposure brackets were monotonic. These are synthetic host tests, NOT camera/phone parity tests.

Downloaded APK matched CI checksum; its exact shader and Monochrom curve matched assembled evidence and DEX markers. All eight uploaded overlay source/test files matched locally tested files. Downloaded source matched seven frozen-file hashes and changed-file manifest.

Inspection of the exact scaffold found no active preview tone/gain change in Camera2ApiAutoFix.applyPrev. VendorTagUtils applies client-name and optional tunables before the new configuration. This does not establish private HAL behavior.

## Next device gate

Test ordinary lighting first, then the backlit window, with the new APK and normal initial settings. Provide a viewfinder screenshot, immediate unsuffixed JPEG and corresponding ordinary burst bundle; note flicker or periodic hitch. Inspect reported source readiness and same-texture input/output before changing any appearance math. Old screenshots cannot validate a HAL input mode they did not use. No default-branch merge and no claim the holdout is solved until device evidence supports it.
