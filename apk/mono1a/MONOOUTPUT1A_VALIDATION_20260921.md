# MONOOUTPUT1A — output cleanup and editable monochrome DNG

21 September 2026. Validation build, not yet validated in Lightroom or on the phone.

## Scope and output

Continue from device-independent MONOLIVEGL2A. The viewfinder, SOURCE1D primary JPEG arithmetic, native Monochrom curve, exposure allocation and original phone RAW saving remain unchanged. The six comparison images are disabled at allocation/render gates, not merely hidden after saving.

Intended image files during validation:

- `IMG_<capture>.jpg`: selected SOURCE1D primary photograph.
- `IMG_<capture>.dng`: original Bayer phone RAW, retained as backup.
- `IMG_<capture>_MONO_LINEAR1A.dng`: new single-channel 16-bit derived monochrome DNG.

JSON diagnostics remain. Existing older files are not deleted. `MonoDngExport1A.COMPARISON_IMAGES=false` is a developer source switch, not a new user-facing settings option.

## DNG provenance and editing

The export copies the MHC camera-RGB16 buffer before the temporary shading transport scale is restored/clipped and before the JPEG curve/output processing. Luminance weights come from the active physical camera's native DNG XYZ-D50 Y row. This is not an eight-bit JPEG placed in a DNG container and not RAW reconstructed from the viewfinder.

Storage uses a conservative metadata-derived range, not scene-max auto normalization. BaselineExposure supplies a reversible storage-scale hint. Samples remain linear; the colour-to-monochrome mix and Bayer interpolation are committed. Negative luminance is clamped and counted. Previously clipped source information cannot be recovered. Original Bayer RAW stays untouched.

The DNG stores uncompressed uint16 single-channel LinearRaw, PhotometricInterpretation 34892, SamplesPerPixel 1, black 0, white 65535, oriented pixels, actual source-device identity and capture metadata. No CFA tags or colour matrices are attached to the monochrome plane. A small RGB thumbnail carries the primary JPEG appearance. The underlying samples have no baked Monochrom display curve or output sharpening. A matching default tone profile has NOT been implemented in this version, so an editor's developed appearance may differ from its thumbnail/JPEG.

Approximately 25 MB of image samples are stored for 12MP. Sixteen-bit storage preserves calculated precision; it does not create additional sensor information. No Cobalt adapter, HSM, HDR, manufacturer whitelist or new device-model appearance rule is added. Existing RAW and camera-driver requirements still apply.

## Ownership and storage

The exporter owns a new short luminance plane and a copied thumbnail, never the camera Image, source Mat or primary Bitmap in its background worker. One export worker plus one queued slot is allowed. Queue-full and export failures are diagnosed; the original RAW remains. Copying the plane adds some synchronous render-worker work, so speed improvement is not assumed.

DNG output is privately staged and length-checked, then copied using the Photon storage helper with a direct-stream fallback. Public copying is NOT atomic. Failed private stages are retained with diagnostics, within a bounded pending-file limit. No original or prior failed stage is silently deleted.

Final status is staged in the working burst spool as `monochrome_dng_export`, also eventually `_MONO_LINEAR1A_EXPORT.json`. Primary diagnostics include `monoDngExport` submission state. A queued status is not proof of public export completion.

## Isolation

Fifteen files remain byte-identical: CaptureController, IsoExpoSelector, SaverImplementation, CameraFragment, GLPreview, MainRenderer, GL2A source/math classes, live-pair classes, metadata store/spool, native m9color_jni.cpp, GL2A shader and Monochrom curve bytes. The renderer has an explicit reversible edit list; reversing it reproduces the exact GL2A renderer. The selected weighted native call is separately hash-checked and unchanged.

The prospective capture-assist mismatch identified in the 19:21 test pair is deliberately not fixed here. GL2A preview/exposure logic remains frozen to isolate the export change.

## Completed build and tests

Branch: `research/monooutput1a-linear-dng`.
APK build commit: `4bd3ea47885cb2c1f8f358ac407ebb77b095d6a2`.
Parent: `6c44897e68c801ce3d1bd8593ddcbbac47cbfa8e`.
Actions run: `35571999872`; job `106245387942`; all steps succeeded.
APK artifact: `10625864613`; evidence artifact: `10626432701`.
APK name: `MMonochrome_MONOOUTPUT1A_LINEAR_DNG.apk`.
SHA-256: `1d9b31503f1232d6ca135e3b13bee30ac8d6667d1966ef3e18d6bee6dfdd3cae`.
APK bytes: 115444613.

17 synthetic fixtures passed independent TIFF exact-sample checks: 12,817,196 samples. Five realistically sized fixtures passed LibRaw sample identity and automatic single-channel monochrome development, including 12MP: 12,779,520 samples. No colour-count override or forced B&W preset was used. ExifTool reported `Validate: OK` for all 17 fixtures. Readers: tifffile 2026.9.20, rawpy 0.27.1, LibRaw 0.22.1. Java executed 25,634,475 mostly per-pixel assertions, not that many distinct test cases.

The tests cover odd/tiny dimensions, rotations, source-weight rows, representation scales, black/high values, >nominal-white headroom, source ownership and invalid inputs. rawpy reports no-filter monochrome as a 1x1 pattern containing LibRaw COLOR sentinel 6, not None. The first reader test failures were incorrect test expectations; the file format was not changed to force a reader result.

All GL2A parent math/state/GPU checks passed again. Android compilation and packaged shader/curve/DEX checks passed. Downloaded APK checksum, 15 frozen source hashes, six new overlay source/test files and renderer hash matched evidence. All 18 packaged native libraries matched the delivered GL2A APK byte-for-byte. APK signing certificate also matched. The downloaded small synthetic DNG was independently reread and matched its U16 reference exactly.

These are host and synthetic-file validations. Phone export, UI behavior, speed and Lightroom import/editing are not yet validated. Adobe dng_validate SDK was not run. There is no source photographic DNG in the current mounted uploads; JPEGs/JSONs are not used as substitutes for a real RAW export regression.

## Next device gate

One normal Photo-mode image is sufficient initially. Confirm one primary JPEG, original `.dng`, and `_MONO_LINEAR1A.dng`, without six new comparison JPEGs. Let background export complete. Open the derived file in Lightroom, check monochrome interpretation and orientation, and adjust exposure/shadows/highlights. Send that derived DNG plus its normal diagnostic burst. Retain the original RAW until the new export is validated. Daylight is not required for this output-format test.

## Primary references consulted

Adobe DNG 1.7.1 specification: LinearRaw raw IFD, monochrome metadata, BaselineExposure and thumbnail definitions.
https://helpx.adobe.com/content/dam/help/en/camera-raw/digital-negative/jcr_content/root/content/flex/items/position-par/download_section_733958301/download-1/DNG_Spec_1_7_1_0.pdf

LibRaw `metadata/tiff.cpp`, `metadata/identify.cpp`, `libraw/libraw.h`, and rawpy `_rawpy.pyx` for no-filter monochrome interpretation.
https://github.com/LibRaw/LibRaw
https://github.com/letmaik/rawpy
