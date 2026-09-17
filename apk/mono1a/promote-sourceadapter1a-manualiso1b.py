#!/usr/bin/env python3
from pathlib import Path
import sys
if len(sys.argv)!=2: raise SystemExit('usage: promote-sourceadapter1a-manualiso1b.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve()
R=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
if not R.exists(): raise SystemExit('missing '+str(R))

def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f'{label}: anchor count={n}, expected 1')
    return s.replace(a,b,1)

r=R.read_text()
if 'MONO1A_SOURCEADAPTER1A_MANUALISO1B_PORTABLE' in r:
    raise SystemExit('portable MANUALISO1B source adapter already applied')
if 'SHARPSTD1B_NORMISO' not in r or 'MONO1A_RAWSCALAR1B_PROMOTED1A' not in r:
    raise SystemExit('latest MANUALISO1B/SHARPSTD1B baseline prerequisites missing')

# The active physical Camera2/DNG XYZ-Y bridge becomes production.  This is a
# source-domain portability change only; target curve/sharpness/ISO math stays frozen.
r=one(r,
      'source1dXyzY.put("photographicOutputSelected", false);',
      'source1dXyzY.put("photographicOutputSelected", true);',
      'SOURCE1D selection')
r=one(r,
      'source1dXyzY.put("role", "counterfactual_scene_luminance_bridge_not_Leica_spectral_truth");',
      'source1dXyzY.put("role", "selected_portable_common_scene_luminance_bridge_not_Leica_spectral_truth");',
      'SOURCE1D role')
r=one(r,
      'd.put("source1dPolicy", "counterfactual_only_no_auto_selection_no_tone_or_exposure_change");',
      'd.put("source1dPolicy", "selected_portable_active_sensor_DNG_XYZ_Y_no_target_tone_or_exposure_change");',
      'SOURCE1D policy')
r=one(r,
      'rawScalar1B.put("photographicOutputSelected", true);',
      'rawScalar1B.put("photographicOutputSelected", false);',
      'fixed D65 selection')
r=one(r,
      'rawScalar1B.put("role", "selected_fixed_Xiaomi_camera_spectral_proxy_not_Leica_CCD_response");',
      'rawScalar1B.put("role", "diagnostic_D65_neutral_only_sensor_proxy_not_common_scene_normalized_not_Leica_CCD_response");',
      'fixed D65 role')
r=one(r,
      'd.put("rawScalar1BPolicy", "promoted_primary_fixed_Xiaomi_spectral_proxy_no_per_shot_AWB_no_tone_or_exposure_change");',
      'd.put("rawScalar1BPolicy", "diagnostic_control_only_D65_neutral_only_sensor_proxy_not_common_scene_normalized");',
      'fixed D65 policy')
r=one(r,
      'd.put("rawScalar1APolicy", "diagnostic_only_primary_RAWSCALAR1B_FIXED_D65");',
      'd.put("rawScalar1APolicy", "diagnostic_only_primary_SOURCE1D_NATIVE_DNG_XYZ_Y");',
      'raw scalar A policy')

# Sharpness experiments remain available as legacy fixed-D65 controls, but are
# no longer described as preserving the photographic primary.
r=r.replace('sharpStd1A.put("baselinePrimaryPreserved", true);',
            'sharpStd1A.put("legacyFixedD65ControlPreserved", true);')
r=r.replace('sharpStd1BNormIso.put("baselinePrimaryPreserved", true);',
            'sharpStd1BNormIso.put("legacyFixedD65ControlPreserved", true);')
r=one(r,
      'd.put("rawScalar1BSharpStdPolicy", "diagnostic_same_RAW_physicalISO_vs_PhotonISO100_bridge_AB_firmware_sharp_math_frozen");',
      'd.put("rawScalar1BSharpStdPolicy", "diagnostic_legacy_fixedD65_same_RAW_physicalISO_vs_PhotonISO100_bridge_AB_firmware_sharp_math_frozen");',
      'sharp diagnostic policy')

# Promote the already-rendered SOURCE1D bitmap. Reuse the old SOURCE1D auxiliary
# field for the former primary fixed-D65 bitmap so same-RAW comparison is retained.
r=one(r,
      'return new RenderCore(rawScalar1BBitmap, d, equalRgbBitmap, greenOnlyBitmap, rawScalar1ABitmap, monoBitmap, rawScalar1BSharpStdBitmap, rawScalar1BSharpStdNormIsoBitmap);',
      'return new RenderCore(equalRgbBitmap, d, rawScalar1BBitmap, greenOnlyBitmap, rawScalar1ABitmap, monoBitmap, rawScalar1BSharpStdBitmap, rawScalar1BSharpStdNormIsoBitmap);',
      'portable primary ownership swap')

# Rename the repurposed auxiliary slot so files/telemetry remain semantically true.
r=one(r, 'stem + "_MONO_XYZY.jpg"', 'stem + "_MONO_FIXED_D65_CONTROL.jpg"', 'fixed D65 filename')
r=r.replace('source1dXyzYJpegPath', 'fixedD65ControlJpegPath')
r=r.replace('source1dXyzYJpegSaved', 'fixedD65ControlJpegSaved')
r=r.replace('source1dXyzYJpegError', 'fixedD65ControlJpegError')

# Core Monochrom telemetry now describes the selected scene-normalized path, not the M9Y control.
r=one(r, 'd.put("sourceStage", "physical_Camera2_gainmap_then_MHC_live_neutral_then_M9Y_control_then_Leica14");',
      'd.put("sourceStage", "physical_Camera2_gainmap_then_MHC_live_neutral_then_active_DNG_XYZ_D50_Y_then_Leica14");', 'core source stage')
r=one(r, 'd.put("sourceCalibrationNativeTransformApplied", false);',
      'd.put("sourceCalibrationNativeTransformApplied", true);', 'core source transform telemetry')
r=one(r, 'd.put("sourceCalibrationRole", "not_in_MONO1A_pixel_path_capture_audit_only");',
      'd.put("sourceCalibrationRole", "active_physical_Camera2_DNG_scene_normalization_for_SOURCE1D");', 'core source calibration role')

# Top-level saved-output telemetry must follow the ownership swap as well.
r=one(r, 'diag.put("monochromPrimaryMode", "RAWSCALAR1B_FIXED_D65");',
      'diag.put("monochromPrimaryMode", "SOURCE1D_NATIVE_DNG_XYZ_Y");', 'saved primary mode')
r=one(r, 'diag.put("monochromPrimarySpectralClaim", "fixed_Xiaomi_camera_spectral_proxy_not_Leica_CCD_QE_truth");',
      'diag.put("monochromPrimarySpectralClaim", "active_sensor_DNG_XYZ_Y_common_scene_bridge_not_Leica_CCD_QE_truth");', 'saved primary spectral claim')
r=one(r, 'diag.put("sourceCalibrationNativeTransformApplied", false);',
      'diag.put("sourceCalibrationNativeTransformApplied", true);', 'source calibration applied telemetry')
r=one(r, 'diag.put("sourceCalibrationAuditRole", "capture_metadata_audit_only_not_MONO1A_pixel_path");',
      'diag.put("sourceCalibrationAuditRole", "capture_metadata_provenance_for_active_DNG_source_transform_used_by_SOURCE1D");', 'source calibration role telemetry')
r=one(r, 'd.put("sourceAdapterProvider", "Xiaomi_Camera2_physical_gainmap_plus_MHC_live_neutral");',
      'd.put("sourceAdapterProvider", "active_physical_Camera2_DNG_gainmap_plus_MHC_live_neutral_plus_XYZ_Y");', 'portable provider label')
r=one(r, 'd.put("pedestalPolicy", "Xiaomi_black_subtracted_source_adapter_zero_not_native_Leica_value");',
      'd.put("pedestalPolicy", "physical_Camera2_black_subtracted_source_adapter_zero_not_native_Leica_value");', 'portable pedestal label')

# Root-level contract/telemetry.  Manual ISO and target stages are explicitly retained.
r=one(r,
      'd.put("schema", "mmonochrome.mono1a.rawscalar1b.promoted1a.v1");',
      'd.put("schema", "mmonochrome.mono1a.sourceadapter1a.manualiso1b.portable.v1");',
      'portable root schema')
old='''                d.put("source1Revision", "MONO1A_RAWSCALAR1B_PROMOTED1A_SHARPSTD1B_ISOBRIDGEAB1A");
                d.put("monochromPrimarySource", "RAWSCALAR1B_FIXED_D65");
                d.put("monochromPrimarySourceAdapter", "fixed_Xiaomi_D65_camera_neutral_proxy");
                d.put("monochromPrimaryLeicaSpectralTruth", false);
                d.put("monochromTargetTone", "canonical_M_Monochrom_curve02_frozen");
'''
new='''                d.put("source1Revision", "MONO1A_SOURCEADAPTER1A_MANUALISO1B_PORTABLE");
                d.put("monochromPrimarySource", "SOURCE1D_NATIVE_DNG_XYZ_Y");
                d.put("monochromPrimarySourceAdapter", "active_physical_sensor_Camera2_DNG_to_XYZ_D50_Y");
                d.put("monochromPrimaryLeicaSpectralTruth", false);
                d.put("monochromSourceManufacturerIndependent", true);
                d.put("monochromSourceCameraIdUsedAsAestheticSelector", false);
                d.put("monochromSourceFocalLengthUsedAsAestheticSelector", false);
                d.put("monochromSourceCobaltRuntimeDependency", false);
                d.put("monochromSourceHsmRuntimeDependency", false);
                d.put("monochromSourceCalibrationAuthority", "active_physical_Camera2_DNG_metadata");
                d.put("monochromManualIsoBaselineRetained", "MANUALISO1B");
                d.put("monochromSharpIsoBridgeDiagnosticsRetained", "SHARPSTD1B_ISOBRIDGEAB1A");
                d.put("monochromTargetTone", "canonical_M_Monochrom_curve02_frozen");
'''
r=one(r,old,new,'root portable telemetry')
R.write_text(r)
print('MONO1A SOURCEADAPTER1A MANUALISO1B PORTABLE applied')
print(' - active physical Camera2/DNG XYZ-Y promoted to primary')
print(' - D65-neutral-only legacy route retained as same-RAW diagnostic control')
print(' - SHARPSTD1B/MANUALISO1B code retained; target tone/exposure untouched')
