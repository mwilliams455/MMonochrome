#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply-manualiso-physical1a.py <PhotonCamera-root>')

root = Path(sys.argv[1]).resolve()
props = root / 'circularbarlib/src/main/java/com/particlesdevs/photoncamera/circularbarlib/camera/CameraProperties.java'
iso_model = root / 'circularbarlib/src/main/java/com/particlesdevs/photoncamera/circularbarlib/control/models/IsoModel.java'

for p in (props, iso_model):
    if not p.exists():
        raise SystemExit('missing ' + str(p))

def one(s, old, new, label):
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{label}: anchor count={n}, expected 1')
    return s.replace(old, new, 1)

# MANUALISO1A policy:
# - the manual dial is user-facing, so its labels/range/selected value are PHYSICAL ISO
# - Photon may continue to normalize ISO internally later in processing/parameters/IsoExpoSelector
# - ParamController.setISO() already passes ManualParamModel's ISO directly to Camera2,
#   therefore the knob value itself must be physical rather than ISO-100-normalized.

p = props.read_text()
if 'MANUALISO1A_PHYSICAL_RANGE' in p:
    raise SystemExit('MANUALISO1A already applied to CameraProperties')
old = '        this.isoRange = new Range<>(IsoExpoSelector.getISOLOWExt(cameraCharacteristics), IsoExpoSelector.getISOHIGHExt(cameraCharacteristics));\n'
new = '''        // MANUALISO1A_PHYSICAL_RANGE: the manual control must expose Camera2's real sensor ISO domain.\n        // Photon keeps its ISO-100 normalization inside the exposure selector, not in the UI range.\n        Range<Integer> physicalIsoRange = cameraCharacteristics.get(CameraCharacteristics.SENSOR_INFO_SENSITIVITY_RANGE);\n        this.isoRange = physicalIsoRange != null ? physicalIsoRange : new Range<>(100, 3200);\n'''
p = one(p, old, new, 'CameraProperties physical ISO range')
props.write_text(p)

i = iso_model.read_text()
if 'MANUALISO1A_PHYSICAL_VALUE' in i:
    raise SystemExit('MANUALISO1A already applied to IsoModel')
old = '            values.add((int) (val / IsoExpoSelector.getMPY(cameraCharacteristics)));\n'
new = '''            // MANUALISO1A_PHYSICAL_VALUE: label and selected value are the same physical ISO.\n            // GenerateExpoPair converts a manual physical ISO to Photon's normalized domain internally.\n            values.add(val);\n'''
i = one(i, old, new, 'IsoModel quarter-stop physical value')
old = '        values.add((int)((int)isohigh / IsoExpoSelector.getMPY(cameraCharacteristics)));\n'
new = '''        // MANUALISO1A_PHYSICAL_VALUE: preserve the physical sensor maximum as the selected value.\n        values.add((int) isohigh);\n'''
i = one(i, old, new, 'IsoModel max physical value')
iso_model.write_text(i)

print('MANUALISO1A applied')
print('  manual ISO range: physical SENSOR_INFO_SENSITIVITY_RANGE')
print('  manual ISO knob values: physical ISO, no UI-side ISO-100 normalization')
print('  Photon internal normalization: unchanged')
