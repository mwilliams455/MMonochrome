#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply-manualiso-preserve1b.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
console = root / 'circularbarlib/src/main/java/com/particlesdevs/photoncamera/circularbarlib/console/ManualModeConsoleImpl.java'
swipe = root / 'app/src/main/java/com/particlesdevs/photoncamera/control/Swipe.java'
iso_model = root / 'circularbarlib/src/main/java/com/particlesdevs/photoncamera/circularbarlib/control/models/IsoModel.java'
iso_expo = root / 'app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java'
param = root / 'app/src/main/java/com/particlesdevs/photoncamera/manual/ParamController.java'

for p in (console, swipe, iso_model, iso_expo, param):
    if not p.exists():
        raise SystemExit('missing ' + str(p))

def one(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: anchor count={n}, expected 1')
    return s.replace(old, new, 1)

# MANUALISO1B / PRESERVE1A
#
# Root cause closed by device evidence:
#   - MANUALISO1A made the UI values physical ISO correctly.
#   - Photon still reset ManualParamModel to Auto whenever the manual panel was hidden.
#   - SwipeDown then called retractAllKnobs(), which reset ISO/shutter/focus/EV models again.
#   - GenerateExpoPair therefore saw currentManISO == 0 and ran the normal auto allocator.
#
# This patch makes panel collapse a UI-only operation. Explicit resetAllValues() and
# model long-press/reset behavior remain available for an intentional return to Auto.
# The M Monochrom renderer, RAWSCALAR1B, curve02 and sharpness math are untouched.

c = console.read_text()
if 'MANUALISO1B_PRESERVE_PANEL' in c:
    raise SystemExit('MANUALISO1B already applied to ManualModeConsoleImpl')
old = '''    @Override\n    public void setPanelVisibility(boolean visible) {\n        manualModeModel.setManualPanelVisible(visible);\n        if (!visible) {\n            manualParamModel.reset();\n        }\n    }\n'''
new = '''    @Override\n    public void setPanelVisibility(boolean visible) {\n        manualModeModel.setManualPanelVisible(visible);\n        // MANUALISO1B_PRESERVE_PANEL: collapsing the manual panel is UI-only.\n        // Keep the selected ISO/shutter/focus/EV values live for capture.\n        // Intentional resets still use resetAllValues(), resetModel(), or app re-init.\n    }\n'''
c = one(c, old, new, 'ManualModeConsoleImpl panel preservation')
old = '''    @Override\n    public void retractAllKnobs() {\n        knobModel.setKnobVisible(false);\n        knobModel.setKnobResetCalled(true);\n        selectedModel = null;\n        if (mfModel != null)\n            mfModel.resetModel();\n        if (expoTimeModel != null)\n            expoTimeModel.resetModel();\n        if (isoModel != null)\n            isoModel.resetModel();\n        if (evModel != null)\n            evModel.resetModel();\n        manualModeModel.setCheckedTextViewId(-1);\n    }\n'''
new = '''    @Override\n    public void retractAllKnobs() {\n        // MANUALISO1B_PRESERVE_KNOBS: retract visual controls without forcing Auto.\n        // currentInfo and ManualParamModel values stay selected so reopening the panel\n        // and taking a picture both see the same manual state.\n        knobModel.setKnobVisible(false);\n        selectedModel = null;\n        manualModeModel.setCheckedTextViewId(-1);\n    }\n'''
c = one(c, old, new, 'ManualModeConsoleImpl knob preservation')
console.write_text(c)

s = swipe.read_text()
if 'MANUALISO1B_PRESERVE_SWIPE' in s:
    raise SystemExit('MANUALISO1B already applied to Swipe')
old = '''            captureController.reset3Aparams();\n            manualModeConsole.setPanelVisibility(false);\n            manualModeConsole.retractAllKnobs();\n'''
new = '''            // MANUALISO1B_PRESERVE_SWIPE: closing the panel must not silently\n            // reset Camera2 preview/manual state before the shutter is pressed.\n            manualModeConsole.setPanelVisibility(false);\n            manualModeConsole.retractAllKnobs();\n            captureController.getParamController().setupPreview();\n'''
s = one(s, old, new, 'SwipeDown manual-state preservation')
swipe.write_text(s)

i = iso_model.read_text()
if 'MANUALISO1B_TRACE_SELECTED' in i:
    raise SystemExit('MANUALISO1B already applied to IsoModel')
old = '''    public void onSelectedKnobItemChanged(KnobItemInfo knobItemInfo) {\n        currentInfo = knobItemInfo;\n        manualParamModel.setCurrentISOValue(knobItemInfo.value);\n    }\n'''
new = '''    public void onSelectedKnobItemChanged(KnobItemInfo knobItemInfo) {\n        currentInfo = knobItemInfo;\n        // MANUALISO1B_TRACE_SELECTED: log the exact physical value crossing the UI boundary.\n        Log.i("IsoModel", "MANUALISO1B selectedPhysicalIso=" + knobItemInfo.value);\n        manualParamModel.setCurrentISOValue(knobItemInfo.value);\n    }\n'''
i = one(i, old, new, 'IsoModel selected-value trace')
iso_model.write_text(i)

p = param.read_text()
if 'MANUALISO1B_TRACE_PARAM' in p:
    raise SystemExit('MANUALISO1B already applied to ParamController')
old = '''    public void setISO(int isoVal, double currentExposure) {\n        CaptureRequest.Builder builder = captureController.mPreviewRequestBuilder;\n'''
new = '''    public void setISO(int isoVal, double currentExposure) {\n        // MANUALISO1B_TRACE_PARAM: prove the model value survives into preview Camera2 state.\n        Log.i(TAG, "MANUALISO1B setISO isoVal=" + isoVal + " currentExposure=" + currentExposure);\n        CaptureRequest.Builder builder = captureController.mPreviewRequestBuilder;\n'''
p = one(p, old, new, 'ParamController manual ISO trace')
param.write_text(p)

e = iso_expo.read_text()
if 'MANUALISO1B_TRACE_ALLOCATOR' in e:
    raise SystemExit('MANUALISO1B already applied to IsoExpoSelector')
old = '''        double currentManExp = captureController.getParamController().getCurrentExposureValue();\n        double currentManISO = captureController.getParamController().getCurrentISOValue();\n\n        if (currentManExp != 0) {\n'''
new = '''        double currentManExp = captureController.getParamController().getCurrentExposureValue();\n        double currentManISO = captureController.getParamController().getCurrentISOValue();\n        // MANUALISO1B_TRACE_ALLOCATOR: this is the decisive boundary. A selected\n        // physical ISO 6400 should arrive here as 6400 before Photon normalizes it.\n        Log.i(TAG, "MANUALISO1B GenerateExpoPair step=" + step\n                + " currentManISO=" + currentManISO\n                + " currentManExp=" + currentManExp\n                + " sensorIsoLow=" + pair.isolow\n                + " previewIso=" + captureController.mPreviewIso\n                + " previewExposureNs=" + captureController.mPreviewExposureTime);\n\n        if (currentManExp != 0) {\n'''
e = one(e, old, new, 'IsoExpoSelector allocator trace')
iso_expo.write_text(e)

print('MANUALISO1B PRESERVE1A applied')
print('  panel collapse: preserves ManualParamModel values')
print('  knob retraction: visual only, no forced Auto reset')
print('  preview state: re-applied after collapse')
print('  trace: UI selection -> ParamController -> GenerateExpoPair')
print('  renderer/sharpness/tone: unchanged')
