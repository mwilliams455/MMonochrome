#!/usr/bin/env python3
from pathlib import Path
import json, math, subprocess, sys, tempfile

if len(sys.argv) != 2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
here = Path(__file__).resolve().parent

# Pure Java arithmetic gate.
with tempfile.TemporaryDirectory() as d:
    subprocess.run([
        "javac", "-d", d,
        str(here / "MonoPlacementMath1A.java"),
        str(here / "MonoPlacementMathHostTest.java")
    ], check=True)
    subprocess.run(["java", "-cp", d, "MonoPlacementMathHostTest"], check=True)

oracle = json.loads((here / "LEICA_TYP246_ORACLE.json").read_text())
target = 0.107 * (8192.0 / 10000.0)
assert abs(oracle["referenceTarget"] - target) < 1e-12
assert abs(oracle["globalMedianNormalizedToWhite"] - 329.0/3750.0) < 1e-15
assert abs(oracle["centerWeightedMedianNormalizedToWhite"] - 330.0/3750.0) < 1e-15
assert abs(oracle["globalMedianDeltaToReferenceEv"] -
           math.log(target/(329.0/3750.0), 2.0)) < 1e-12
assert abs(oracle["centerWeightedMedianDeltaToReferenceEv"] -
           math.log(target/(330.0/3750.0), 2.0)) < 1e-12
assert oracle["runtimeUse"].startswith("diagnostic_")

J = root / "app/src/main/java/com/particlesdevs/photoncamera"
renderer = (J / "m9/render/M9R35Renderer.java").read_text()
exporter = (J / "m9/export/MonoDngExport1A.java").read_text()
writer = (J / "m9/export/MonoDngWriter1A.java").read_text()
math_java = (J / "m9/export/MonoPlacementMath1A.java").read_text()
probe_java = (J / "m9/export/MonoPlacementProbe1A.java").read_text()
proof = json.loads((root / "MONOAUTO1C_PLACEMENTPROBE1A_ISOLATION.json").read_text())

for token in [
    "tail.uq99,tail.uq995,tail.uq998,tail.clipFraction"
]:
    assert token in renderer, token
assert "MonoPlacementProbe1A.REVISION" in exporter
assert "MonoPlacementProbe1A.evaluate(" in exporter
assert "MONOAUTO1C_PLACEMENTPROBE1A" in math_java
assert "diagnostic_only_no_exposure_mutation" in probe_java
assert "M9M10rMfmTest1A.snapshotJson()" in probe_java
assert "rawHeadroomTo0p95Ev" in probe_java
assert "referencePlacementDeltaEv" in probe_java
assert "sourceCenterWeightedMedian" in probe_java

# Parent DNG semantic fix stays present and no tone profile is introduced here.
assert "MONOOUTPUT1E_BASELINE_IFD0" in writer
assert "ProfileToneCurve" not in writer
assert "ProfileToneCurve" not in probe_java

# Explicit isolation assertions.
for key in [
    "captureExposureChanged", "jpegRenderChanged", "curve02Changed",
    "dngSamplesChanged", "baselineExposureChanged", "previewChanged",
    "sourceAdapterChanged"
]:
    assert proof[key] is False, key
assert abs(proof["referenceTarget"] - target) < 1e-12

report = {
    "status": "PASS",
    "revision": "MONOAUTO1C_PLACEMENTPROBE1A",
    "referenceTarget": target,
    "typ246GlobalMedian": 329.0/3750.0,
    "typ246CenterWeightedMedian": 330.0/3750.0,
    "typ246GlobalDeltaEv": math.log(target/(329.0/3750.0), 2.0),
    "typ246CenterWeightedDeltaEv": math.log(target/(330.0/3750.0), 2.0),
    "catPriorWeightedMedianExample": 0.067501776,
    "catPriorReferenceDeltaEv": math.log(target/0.067501776, 2.0),
    "phoneValidationRequired": True,
    "exposureMutation": False
}
(root / "MONOAUTO1C_PLACEMENTPROBE1A_TEST_REPORT.json").write_text(
    json.dumps(report, indent=2) + "\n")
print(json.dumps(report, indent=2))
