#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,re,sys
if len(sys.argv)!=2: raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1])
p=json.loads((root/"LEICASHARPNESS1C_PREVIEWFIX2_ISOLATION.json").read_text())
assert p["revision"]=="LEICASHARPNESS1C_PREVIEWFIX2"
assert p["fragmentShaderCompileContractRestored"]
assert p["savedJpegSharpnessPreserved"]
assert p["previewSharpnessTemporarilyDisabled"]
assert p["previewContrastPreserved"] and p["previewToningPreserved"]

s=(root/"app/src/main/assets/shaders/preview/main_fs.glsl").read_text()
assert s.count("float monoSource16Probe1D(vec3 oes)") == 1
assert s.count("float monoSensorRgbMaxProbe1B(vec3 oes)") == 1
assert s.count("monoSource16Probe1D(oes.rgb)") == 1
assert s.count("monoSensorRgbMaxProbe1B(oes.rgb)") == 1
# PREVIEWFIX1 contract remains: no experimental sharpness GLSL path.
for forbidden in ["uMonoSharpLut1C","uMonoSharpReady1C","uMonoSharpSelector1C","sharpSource14At1C","source14At1C","fallbackMono1C"]:
    assert forbidden not in s,forbidden
for required in ["float monochrome(vec3 oes)","float y=monochrome(oes.rgb);","uMonoCurve2A","uMonoToningCr1A","uMonoToningCb1A"]:
    assert required in s,required
# Every helper called by the probe block is defined before main.
main=s.index("void main() {")
assert s.index("float monoSource16Probe1D(vec3 oes)") < main
assert s.index("float monoSensorRgbMaxProbe1B(vec3 oes)") < main

for rel,want in p["nonShaderHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel

sharp=json.loads((root/"LEICASHARPNESS1C_ISOLATION.json").read_text())
assert sharp["menu"]==["Off","Low","Standard","Medium high","High"]
assert sharp["source1dPrimaryUsesSharpness"]
preview1=json.loads((root/"LEICASHARPNESS1C_PREVIEWFIX1_ISOLATION.json").read_text())
assert preview1["savedJpegSharpnessPreserved"] and preview1["previewSharpnessTemporarilyDisabled"]
report={
 "revision":"LEICASHARPNESS1C_PREVIEWFIX2_TEST",
 "status":"PASS",
 "probeHelpersDefinedAndCalled":True,
 "savedSharpnessUntouched":True,
 "previewRestoredToContrastToning":True
}
(root/"LEICASHARPNESS1C_PREVIEWFIX2_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
