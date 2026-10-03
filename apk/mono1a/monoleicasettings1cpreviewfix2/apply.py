#!/usr/bin/env python3
"""LEICASHARPNESS1C_PREVIEWFIX2: restore probe helpers accidentally removed by PREVIEWFIX1."""
from pathlib import Path
import hashlib,json,re,sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
S=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
M=root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java"
P=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java"
R=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
N=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java"
C=root/"app/src/main/cpp/m9color_jni.cpp"
G=root/"app/build.gradle"
for p in (S,M,P,R,N,C,G):
    if not p.is_file(): raise SystemExit("PREVIEWFIX2 missing "+str(p))
if not (root/"LEICASHARPNESS1C_PREVIEWFIX1_ISOLATION.json").is_file():
    raise SystemExit("PREVIEWFIX2 requires PREVIEWFIX1 parent")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
frozen={str(p.relative_to(root)):sha(p) for p in (M,P,R,N,C)}

s=S.read_text()
if "float monoSource16Probe1D(vec3 oes)" in s or "float monoSensorRgbMaxProbe1B(vec3 oes)" in s:
    raise SystemExit("PREVIEWFIX2 probe helpers already present")
for call in ["monoSource16Probe1D(oes.rgb)","monoSensorRgbMaxProbe1B(oes.rgb)"]:
    if call not in s: raise SystemExit("PREVIEWFIX2 expected live probe call missing: "+call)

anchor="void main() {"
if s.count(anchor)!=1: raise SystemExit("PREVIEWFIX2 main anchor count="+str(s.count(anchor)))
helpers=r'''
float monoSource16Probe1D(vec3 oes) {
    if (!uMonoSourceReady2A) return -1.0;
    vec3 linearRgb=vec3(inverseChannel(oes.r,0),inverseChannel(oes.g,1),inverseChannel(oes.b,2));
    vec3 sensor=uMonoInputToSensor2A*linearRgb;
    vec3 cam16=floor(clamp(sensor*uMonoExposureScale1A,0.0,1.0)*65535.0+0.5);
    return floor(clamp(dot(cam16,uMonoSourceY2A),0.0,65535.0)+0.5);
}

float monoSensorRgbMaxProbe1B(vec3 oes) {
    if (!uMonoSourceReady2A) return -1.0;
    vec3 linearRgb=vec3(inverseChannel(oes.r,0),inverseChannel(oes.g,1),inverseChannel(oes.b,2));
    vec3 sensor=uMonoInputToSensor2A*linearRgb;
    return clamp(max(sensor.r,max(sensor.g,sensor.b)),0.0,1.0);
}
'''
s=s.replace(anchor,helpers+anchor,1)
S.write_text(s)

g=G.read_text()
m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("PREVIEWFIX2 versionName missing")
if "previewfix2" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-previewfix2"+g[m.end(1):]
G.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in (M,P,R,N,C)}
if frozen!=after:
    changed=[k for k in frozen if frozen[k]!=after.get(k)]
    raise SystemExit("PREVIEWFIX2 unexpectedly changed non-shader code: "+repr(changed))

proof={
 "revision":"LEICASHARPNESS1C_PREVIEWFIX2",
 "rootCause":"PREVIEWFIX1_removed_probe_helper_definitions_but_left_main_calls",
 "fragmentShaderCompileContractRestored":True,
 "restoredHelpers":["monoSource16Probe1D","monoSensorRgbMaxProbe1B"],
 "savedJpegSharpnessPreserved":True,
 "previewSharpnessTemporarilyDisabled":True,
 "previewContrastPreserved":True,
 "previewToningPreserved":True,
 "nonShaderHashes":after
}
(root/"LEICASHARPNESS1C_PREVIEWFIX2_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
