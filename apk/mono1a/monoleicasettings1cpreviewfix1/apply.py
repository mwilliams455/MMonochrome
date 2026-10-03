#!/usr/bin/env python3
"""LEICASHARPNESS1C_PREVIEWFIX1: keep Leica Sharpness in saved SOURCE1D JPEG, restore last-good Contrast+Toning preview."""
from pathlib import Path
import hashlib,json,re,sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
P=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java"
M=root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java"
S=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
R=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
N=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java"
C=root/"app/src/main/cpp/m9color_jni.cpp"
G=root/"app/build.gradle"
for p in (P,M,S,R,N,C,G):
    if not p.is_file(): raise SystemExit("PREVIEWFIX1 missing "+str(p))
if not (root/"LEICASHARPNESS1C_ISOLATION.json").is_file():
    raise SystemExit("PREVIEWFIX1 requires LEICASHARPNESS1C parent")

def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"PREVIEWFIX1 {label} anchor count={n}")
    return s.replace(a,b,1)
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

# Freeze still-photographic code while reverting only preview files.
still_before={str(p.relative_to(root)):sha(p) for p in (R,N,C)}

# ---- Shader: restore last known-good SOURCE1D + selected Contrast + Toning preview. ----
s=S.read_text()
for line in [
    "uniform highp isampler2D uMonoSharpLut1C;\n",
    "uniform bool uMonoSharpReady1C;\n",
    "uniform int uMonoSharpSelector1C;\n",
]:
    if line not in s: raise SystemExit("PREVIEWFIX1 shader sharp uniform missing: "+line.strip())
    s=s.replace(line,"",1)

start=s.find("float fallbackMono1C(vec3 oes) {")
end=s.find("void main() {",start)
if start<0 or end<0: raise SystemExit("PREVIEWFIX1 sharp shader block missing")
restore=r'''float monochrome(vec3 oes) {
    if (!uMonoSourceReady2A) {
        // Explicit approximate fallback; never apply sensor transforms to unchecked OES.
        return clamp(srgbCode(dot(srgbLinear(clamp(oes,0.0,1.0))*uMonoExposureScale1A,
                vec3(0.2126,0.7152,0.0722))),0.0,1.0);
    }
    vec3 linearRgb=vec3(inverseChannel(oes.r,0),inverseChannel(oes.g,1),inverseChannel(oes.b,2));
    vec3 sensor=uMonoInputToSensor2A*linearRgb;
    // ISP shading/demosaic are already present. Do not apply another RAW LensShadingMap.
    // Match the still weighted-kernel coordinate: uint16 camRGB -> rounded uint16 Y -> >>5.
    vec3 cam16=floor(clamp(sensor*uMonoExposureScale1A,0.0,1.0)*65535.0+0.5);
    float source16=floor(clamp(dot(cam16,uMonoSourceY2A),0.0,65535.0)+0.5);
    int index=int(source16)>>5;
    return texelFetch(uMonoCurve2A,ivec2(index,0),0).r;
}
'''
s=s[:start]+restore+s[end:]
s=one(s,"    float y=monochrome(uv);\n","    float y=monochrome(oes.rgb);\n","restore preview monochrome call")
S.write_text(s)

# ---- MainRenderer: remove experimental integer sharpness texture/uniform path. ----
m=M.read_text()
m=one(m,
"""    private int monoProgram2A, monoInverseTex2A, monoCurveTex2A;
    private int monoSharpTex1C,monoSharpReadyUniform1C,monoSharpSelectorUniform1C;
    private byte[] monoSharpBank1C; private int monoSharpBoundSelector1C=-1,monoSharpBoundSlot1C=-1;
""",
"""    private int monoProgram2A, monoInverseTex2A, monoCurveTex2A;
""","sharp preview fields")

m=one(m,
"""        monoProbeUniform2A=GLES20.glGetUniformLocation(program,"uMonoProbe2A");
        monoSharpReadyUniform1C=GLES20.glGetUniformLocation(program,"uMonoSharpReady1C");
        monoSharpSelectorUniform1C=GLES20.glGetUniformLocation(program,"uMonoSharpSelector1C");
        GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"uMonoSharpLut1C"),4);
""",
"""        monoProbeUniform2A=GLES20.glGetUniformLocation(program,"uMonoProbe2A");
""","sharp preview uniforms")

m=one(m,
"""        monoInverseTex2A=ids[0]; monoCurveTex2A=ids[1];
        int[] sharpId1C=new int[1]; GLES20.glGenTextures(1,sharpId1C,0); monoSharpTex1C=sharpId1C[0];
""",
"""        monoInverseTex2A=ids[0]; monoCurveTex2A=ids[1];
""","sharp preview texture allocation")

sharp_asset_start=m.find("        GLES20.glActiveTexture(GLES20.GL_TEXTURE4);\n        texture2A(monoSharpTex1C,GLES20.GL_NEAREST);")
sharp_asset_end=m.find("        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);\n    }",sharp_asset_start)
if sharp_asset_start<0 or sharp_asset_end<0: raise SystemExit("PREVIEWFIX1 sharp asset block missing")
# Keep the normal restore-to-texture0 + method closing.
m=m[:sharp_asset_start]+m[sharp_asset_end:]

bind_start=m.find("        int sharpSelector1C=com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.clampSelector(")
bind_end=m.find("        int toningHue1A=com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoToningHueValue();",bind_start)
if bind_start<0 or bind_end<0: raise SystemExit("PREVIEWFIX1 sharp bind block missing")
m=m[:bind_start]+m[bind_end:]
M.write_text(m)

# ---- Preview diagnostics/helper: remove experimental sharpness-preview state only. ----
p=P.read_text()
p=p.replace("import com.particlesdevs.photoncamera.m9.render.MonoSharpness1C;\n","",1)
p=one(p,
"""    private static volatile Draw lastProbe;
    private static volatile int latestPhysicalIso1C=320;
    private static volatile int selectedSharpSelector1C=2,selectedSharpIso1C=320,selectedSharpCode1C=8;
""",
"""    private static volatile Draw lastProbe;
""","preview sharp state")

p=one(p,
"""            Integer physicalIso1C=physical==null?null:physical.get(CaptureResult.SENSOR_SENSITIVITY);
            if(physicalIso1C!=null&&physicalIso1C>0) latestPhysicalIso1C=physicalIso1C;
            Frame f=new Frame(camera,physicalId,physical,request,context,
""",
"""            Frame f=new Frame(camera,physicalId,physical,request,context,
""","preview physical ISO observation")

p=one(p,
"""    public static int latestPhysicalIso1C(){return latestPhysicalIso1C;}
    public static void setLeicaSharpnessSelection1C(int selector,int iso,int code){
        selectedSharpSelector1C=MonoSharpness1C.clampSelector(selector);
        selectedSharpIso1C=iso;selectedSharpCode1C=code;
    }

    public static synchronized JSONObject snapshot(long shutterElapsedNs) {
""",
"""    public static synchronized JSONObject snapshot(long shutterElapsedNs) {
""","preview sharp methods")

for line in [
'            o.put("leicaSharpnessEnum",selectedSharpSelector1C);\n',
'            o.put("leicaSharpnessLabel",MonoSharpness1C.LABELS[selectedSharpSelector1C]);\n',
'            o.put("leicaSharpnessPhysicalIso",selectedSharpIso1C);\n',
'            o.put("leicaSharpnessModifierCode",selectedSharpCode1C);\n',
]:
    if line not in p: raise SystemExit("PREVIEWFIX1 sharp telemetry line missing: "+line.strip())
    p=p.replace(line,"",1)
P.write_text(p)

# Identity.
g=G.read_text(); mm=re.search(r"versionName\s+'([^']+)'",g)
if not mm: raise SystemExit("PREVIEWFIX1 versionName missing")
if "previewfix1" not in mm.group(1):
    g=g[:mm.start(1)]+mm.group(1)+"-previewfix1"+g[mm.end(1):]
G.write_text(g)

still_after={str(p.relative_to(root)):sha(p) for p in (R,N,C)}
if still_before!=still_after:
    raise SystemExit("PREVIEWFIX1 modified still SOURCE1D/JNI code")

sharp=json.loads((root/"LEICASHARPNESS1C_ISOLATION.json").read_text())
proof={
 "revision":"LEICASHARPNESS1C_PREVIEWFIX1",
 "rootCauseClass":"experimental_live_preview_sharpness_GLSL_integer_texture_path_caused_black_viewfinder_on_phone",
 "savedJpegSharpnessPreserved":True,
 "savedJpegSharpnessMenu":sharp["menu"],
 "savedJpegSharpnessDefault":sharp["default"],
 "source1dPrimarySharpnessPreserved":sharp["source1dPrimaryUsesSharpness"],
 "previewSharpnessTemporarilyDisabled":True,
 "previewRestoredTo":"last_known_good_SOURCE1D_plus_Contrast_plus_Toning",
 "previewContrastPreserved":True,
 "previewToningPreserved":True,
 "linearDngSharpnessChanged":False,
 "stillSourceHashes":still_after
}
(root/"LEICASHARPNESS1C_PREVIEWFIX1_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
