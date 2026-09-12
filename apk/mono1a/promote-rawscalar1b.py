#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: promote-rawscalar1b.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
R = root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
if not R.exists():
    raise SystemExit('missing '+str(R))


def one(s, a, b, label):
    n = s.count(a)
    if n != 1:
        raise SystemExit(f'{label}: anchor count={n}, expected 1')
    return s.replace(a, b, 1)


r = R.read_text()
if 'MONO1A_RAWSCALAR1B_PROMOTED1A' in r:
    raise SystemExit('RAWSCALAR1B PROMOTED1A already applied')
if 'RAWSCALAR1B_FIXED_D65' not in r:
    raise SystemExit('RAWSCALAR1B fixed-D65 prerequisite missing')
if 'mmonochrome.rawscalar1b.fixedd65.v1' not in r:
    raise SystemExit('RAWSCALAR1B fixed-D65 diagnostics prerequisite missing')

# Promotion changes selection/ownership only. The already validated fixed-D65
# RAWSCALAR1B bitmap becomes the normal primary JPEG payload. The previous
# M9-Y primary is retained in the existing final auxiliary bitmap slot as an
# explicit diagnostic control, avoiding a duplicate RAWSCALAR1B render or copy.
r = one(
    r,
    'stem + "_MONO_RAWSCALAR1B_D65.jpg"',
    'stem + "_MONO_M9Y_CONTROL.jpg"',
    'rename former RAWSCALAR1B auxiliary slot to M9-Y control',
)
r = one(r, 'diag.put("rawScalar1BJpegPath", rawScalar1BPath.toString());',
        'diag.put("m9YControlJpegPath", rawScalar1BPath.toString());',
        'M9-Y control path diagnostics')
r = one(r, 'diag.put("rawScalar1BJpegSaved", rawScalar1BSaved);',
        'diag.put("m9YControlJpegSaved", rawScalar1BSaved);',
        'M9-Y control save diagnostics')
r = one(r, 'diag.put("rawScalar1BJpegError", rawScalar1BError);',
        'diag.put("m9YControlJpegError", rawScalar1BError);',
        'M9-Y control error diagnostics')

# SOURCE1C introduced a historical control-path label that pointed at the
# primary JPEG while M9-Y was primary. Keep that telemetry semantically true
# after promotion by pointing it at the retained M9-Y auxiliary file instead.
r = one(
    r,
    'diag.put("source1cControlJpegPath", jpgPath.toString());',
    'if (rawScalar1BPath != null) diag.put("source1cControlJpegPath", rawScalar1BPath.toString());',
    'SOURCE1C control path after RAWSCALAR1B promotion',
)
r = one(
    r,
    'diag.put("source1cControlMode", "M9Y_Q14");',
    'diag.put("source1cControlMode", "M9Y_Q14_DIAGNOSTIC_ONLY");\n'
    '            diag.put("monochromPrimaryJpegPath", jpgPath.toString());\n'
    '            diag.put("monochromPrimaryMode", "RAWSCALAR1B_FIXED_D65");\n'
    '            diag.put("monochromPrimarySpectralClaim", "fixed_Xiaomi_camera_spectral_proxy_not_Leica_CCD_QE_truth");',
    'primary/control save telemetry',
)

# Update the embedded RAWSCALAR1B provenance. Nothing about the scalar math,
# MHC reconstruction, physical shading, Leica coordinate, pedestal or curve02
# is changed here.
r = one(
    r,
    'rawScalar1B.put("photographicOutputSelected", false);',
    'rawScalar1B.put("photographicOutputSelected", true);',
    'RAWSCALAR1B selection flag',
)
r = one(
    r,
    'rawScalar1B.put("role", "fixed_camera_spectral_proxy_test_not_Leica_CCD_response");',
    'rawScalar1B.put("role", "selected_fixed_Xiaomi_camera_spectral_proxy_not_Leica_CCD_response");',
    'RAWSCALAR1B selected role',
)
r = one(
    r,
    'd.put("rawScalar1APolicy", "diagnostic_only_primary_SOURCE1D_M9Y_unchanged");',
    'd.put("rawScalar1APolicy", "diagnostic_only_primary_RAWSCALAR1B_FIXED_D65");',
    'RAWSCALAR1A policy after promotion',
)
r = one(
    r,
    'd.put("rawScalar1BPolicy", "diagnostic_fixed_spectral_proxy_no_per_shot_AWB_no_tone_or_exposure_change");',
    'd.put("rawScalar1BPolicy", "promoted_primary_fixed_Xiaomi_spectral_proxy_no_per_shot_AWB_no_tone_or_exposure_change");\n'
    '                d.put("source1Revision", "MONO1A_RAWSCALAR1B_PROMOTED1A");\n'
    '                d.put("monochromPrimarySource", "RAWSCALAR1B_FIXED_D65");\n'
    '                d.put("monochromPrimarySourceAdapter", "fixed_Xiaomi_D65_camera_neutral_proxy");\n'
    '                d.put("monochromPrimaryLeicaSpectralTruth", false);\n'
    '                d.put("monochromTargetTone", "canonical_M_Monochrom_curve02_frozen");',
    'RAWSCALAR1B promoted policy',
)

# The decisive ownership swap. Primary now owns RAWSCALAR1B; the final aux slot
# owns the old M9-Y control. This deliberately avoids aliasing the same Bitmap in
# both slots, so the primary can be compressed/recycled normally before the
# diagnostic M9-Y control is written.
r = one(
    r,
    'return new RenderCore(monoBitmap, d, equalRgbBitmap, greenOnlyBitmap, rawScalar1ABitmap, rawScalar1BBitmap);',
    'return new RenderCore(rawScalar1BBitmap, d, equalRgbBitmap, greenOnlyBitmap, rawScalar1ABitmap, monoBitmap);',
    'RAWSCALAR1B primary ownership swap',
)

# Root schema now describes the promoted output. Counterfactual SOURCE1D/1A
# objects remain present and keep their own explicit diagnostic semantics.
r = one(
    r,
    'mmonochrome.mono1a.source1d.v1',
    'mmonochrome.mono1a.rawscalar1b.promoted1a.v1',
    'promoted root schema',
)

R.write_text(r)
print('MONO1A RAWSCALAR1B PROMOTED1A applied')
