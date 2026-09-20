#!/usr/bin/env python3
"""Apply controlled Monochrom preview to exact successful GL1E1D source, never still arithmetic."""
from pathlib import Path
import hashlib,json,re,sys
root=Path(sys.argv[1]).resolve(); here=Path(__file__).resolve().parent
java='app/src/main/java/com/particlesdevs/photoncamera/'
paths={
 'renderer':java+'m9/render/M9R35Renderer.java', 'native':'app/src/main/cpp/m9color_jni.cpp',
 'iso':java+'processing/parameters/IsoExpoSelector.java', 'saver':java+'processing/SaverImplementation.java',
 'fragment':java+'ui/camera/CameraFragment.java','gl':java+'ui/camera/views/viewfinder/GLPreview.java',
 'main':java+'ui/camera/views/viewfinder/MainRenderer.java','capture':java+'capture/CaptureController.java',
 'diag':java+'m9/preview/MonoLivePairDiagnostics1E.java','export':java+'m9/preview/MonoLivePairExport1D.java',
 'store':java+'m9/M9DeferredMetadataStore.java','spool':java+'m9/M9DiagnosticBurstSpool.java',
 'shader':'app/src/main/assets/shaders/preview/main_fs.glsl'}
def sha(b):return hashlib.sha256(b).hexdigest()
before={k:(root/p).read_bytes() for k,p in paths.items()}
expectedBaseline={'renderer': '594a6c489e3a692fe3c33bce014a4d8ed5cf1bc927c61bcaa99c73f64fa2b300', 'native': 'fdfa17bd9b4297fa8427e6c112d1afdb2e3c94acb2cc1fd2f2347c2a7730dfd0', 'iso': 'f031653a2f238b3c61815d9a6d975cd54d84f035c6ee41a8c5d2fe43faac2b2c', 'saver': '6d3446a5f71072c9cd43256cb3d970bb86f832f759968a80fca985b50ba3f077', 'fragment': '57a2a8180c643d1c84d4a5144b475ec0ea48cdc5bd48e195f419e66b25c3ea33', 'gl': 'b718d04ae7bee557930371225de774e2212560bbd5bf02984fc44b9bd4e3007d', 'main': 'f92df6e33e6bc79f5494179b7d9cc58edd5cee4a8eca840768d4d1515d645e97', 'capture': 'cb0759e8b4190084bf85e1478d556f0bb052896783add11795208f57a699b832', 'diag': 'bb67ad0a101e35146570f0d2412fc4f20d8728b52dffb9f1a78545d9dfb03fac', 'export': '913c9b45acd1a507c402776d6e4dbd4877c17d838d20c2591f98df8e06b68242', 'store': '303f82337019ffb58d28d6a765025b3fb0e535cbe116dfe9fba742f670878681', 'spool': 'cdf783171057231f5c7a05e21a62a562a34dbc59d7767398205086eccfe4978b', 'shader': 'da90bf513c62b4b4ea728f2ad6699b87c5e71b2a5c67e88c6a039e9fdbcc1c4c'}
for k,b in before.items():
 if sha(b)!=expectedBaseline[k]:raise SystemExit('Exact GL1E1D baseline mismatch: '+paths[k])
if b'MONOLIVEGL1D_TRIPAIR1A' not in before['shader'] or b'MONOLIVEGL1E_LIVEPAIRDIAG1D_SPOOL' not in before['export']:
 raise SystemExit('Expected GL1D visual + GL1E1D export baseline')
def one(s,a,b):
 if s.count(a)!=1:raise SystemExit('Expected exactly one anchor: '+a[:100]+' got '+str(s.count(a)))
 return s.replace(a,b,1)
def put(k,s): (root/paths[k]).write_text(s)
# SOURCE1D native luminance authority: additive read-only exporter; remove block -> exact original.
r=before['renderer'].decode(); anchor='    private static NativeProspectiveSource buildNativeProspectiveSource('
export='''    // MONOLIVEGL2A_Y_EXPORT_BEGIN
    public static float[] exportMonoPreviewY2A(CameraCharacteristics chars, CaptureResult result) throws Exception {
        float[] xyz=buildNativeProspectiveSource(chars,result).sensorToXyzD50;
        return new float[]{xyz[3],xyz[4],xyz[5]};
    }
    // MONOLIVEGL2A_Y_EXPORT_END

'''
put('renderer',one(r,anchor,export+anchor))
# Configure only repeating preview; still builders and allocator methods unchanged.
c=before['capture'].decode()
c=one(c,'            mPreviewCaptureRequest = request;\n','''            mPreviewCaptureRequest = request;
            // MONOLIVEGL2A_RESULT_OBSERVE: immutable result data only; reject an obsolete session.
            if (session == mCaptureSession) com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.observe(
                    mCameraCharacteristicsMap.get(physicalID),request,result,logicalID,physicalID);
''')
c=one(c,'                        VendorTagUtils.builderSessionApply(mPreviewRequestBuilder, false, useMaximumResolutionKey, physicalID);',
'''                        VendorTagUtils.builderSessionApply(mPreviewRequestBuilder, false, useMaximumResolutionKey, physicalID);
                        // MONOLIVEGL2A_REQUEST: only the live preview input response changes.
                        if (!mIsRecordingVideo) com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.configure(
                                mPreviewRequestBuilder,mCameraCharacteristicsMap.get(physicalID),logicalID,physicalID,true);''')
# Preserve manual UI rebuilds and avoid changing recording requests.
c=one(c,'            mCaptureSession.setRepeatingRequest(mPreviewInputRequest = mPreviewRequestBuilder.build(), mCaptureCallback, mBackgroundHandler);',
'''            if (!mIsRecordingVideo) com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.configure(
                    mPreviewRequestBuilder,mCameraCharacteristicsMap.get(physicalID),logicalID,physicalID,false);
            mCaptureSession.setRepeatingRequest(mPreviewInputRequest = mPreviewRequestBuilder.build(), mCaptureCallback, mBackgroundHandler);''')
put('capture',c)
m=before['main'].decode()
m=one(m,'    private int uTexRotateMatrix;',(here/'MainRenderer2A.inc').read_text()+'\n    private int uTexRotateMatrix;')
m=one(m,'        GLES20.glUseProgram(hProgram);','''        GLES20.glUseProgram(hProgram);
        GLES20.glDisable(GLES20.GL_DITHER);
        initMonoTextures2A(hProgram);''')
m=one(m,'        GLES20.glUniformMatrix4fv(uTexRotateMatrix, 1, false, mTexRotateMatrix, 0);\n        int peakEnabled = getPeakEnabled();',
'''        GLES20.glUseProgram(monoProgram2A);
        final float exposureForDraw2A=mMonoExposureScale1A;
        final boolean mirrorForDraw2A=mMirrorPreview;
        final com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.Binding binding2A=
                com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.bind(mSTexture.getTimestamp());
        bindMono2A(binding2A.context);
        GLES20.glUniform1i(monoProbeUniform2A,0);
        GLES20.glUniformMatrix4fv(uTexRotateMatrix, 1, false, mTexRotateMatrix, 0);
        int peakEnabled = getPeakEnabled();''')
m=one(m,'        GLES20.glUniform1i(mirror, mMirrorPreview ? 1 : 0);','        GLES20.glUniform1i(mirror, mirrorForDraw2A ? 1 : 0);')
m=one(m,'        GLES20.glUniform1f(uMonoExposureScale1A, mMonoExposureScale1A);','        GLES20.glUniform1f(uMonoExposureScale1A, exposureForDraw2A);')
m=one(m,'        // GLES20.glFlush();','''        long drawNs2A=android.os.SystemClock.elapsedRealtimeNanos();
        byte[] probe2A=probeMono2A(drawNs2A);
        com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.publish(binding2A,exposureForDraw2A,
                peakEnabled,mirrorForDraw2A,boundSourceReady2A,
                drawNs2A,probe2A,probeWidth2A,probeHeight2A,probeCostNs2A,probeError2A);
        // GLES20.glFlush();''')
# Correct EXTERNAL_OES parameter target; these four calls were previously targeting GL_TEXTURE_2D.
start=m.index('    private void initTex() {');end=m.index('    public synchronized void onFrameAvailable',start)
part=m[start:end].replace('glTexParameteri(GLES30.GL_TEXTURE_2D','glTexParameteri(GLES11Ext.GL_TEXTURE_EXTERNAL_OES')
m=m[:start]+part+m[end:]
put('main',m)
# Preserve actual cached exposure fields but replace the obsolete curve claim with atomic GL draw evidence.
d=before['diag'].decode();d=d.replace('public static final String VISUAL = "MONOLIVEGL1D_TRIPAIR1A";','public static final String VISUAL = "MONOLIVEGL2A_CONTROLLEDOES";')
a=d.index('            JSONObject tone = new JSONObject();');b=d.index('            o.put("previewTone", tone);',a)+len('            o.put("previewTone", tone);')
d=d[:a]+'''            o.put("previewTone",new JSONObject().put("revision",VISUAL).put("fittedResidualApplied",false)
                    .put("curve02Sha256",MonoGpuPreview2A.CURVE_SHA));
            o.put("previewSource2A",MonoGpuPreview2A.snapshot(shutterElapsedNs));'''+d[b:]
put('diag',d)
e=before['export'].decode();e=one(e,'            pair.put("toneOrExposureChanged", false);','''            pair.put("toneOrExposureChanged", true); // Preview algorithm changes from GL1D, not still output.
            pair.put("diagnosticExportMutatesToneOrExposure", false);
            pair.put("previewImplementationRevision", "MONOLIVEGL2A_CONTROLLEDOES");
            pair.put("stillRendererChanged", false);
            pair.put("displayFramebufferSampled", false);
            pair.put("shaderProbeEvidence", "previewSource2A.pairedProbe_if_available");''')
put('export',e)
put('shader',(here/'main_fs.glsl').read_text())
for name in ['MonoPreviewMath2A.java','MonoGpuPreview2A.java']:
 p=root/java/'m9/preview'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((here/name).read_bytes())
# Firmware bytes copied from the actual frozen native array, never M9 curve or fitted knots.
body=re.search(r'MM_MONO1A_CURVE02\s*\[\s*2048\s*\]\s*=\s*\{(.*?)\}',before['native'].decode(),re.S)
if not body:raise SystemExit('Monochrom native curve array missing')
nums=re.findall(r'0x[0-9a-fA-F]+|\d+',body[1]);curve=bytes(int(v,0) for v in nums)
expected='7a7ccd9021cf9881384b733236fe249d2088358705d8db282687e943aa990752'
if len(curve)!=2048 or sha(curve)!=expected:raise SystemExit('Monochrom curve hash mismatch')
p=root/'app/src/main/assets/mono/mono_curve02_gl2a.bin';p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(curve)
# Only static labels change; not versionCode, signing, package or exposure values.
gradle=root/'app/build.gradle'
if gradle.exists():
 s=gradle.read_text();s,n=re.subn(r"versionName\s+'([^']*)'",lambda m:"versionName '"+m[1]+"-monolivegl2a'",s,count=1)
 if n!=1:raise SystemExit('versionName anchor')
 gradle.write_text(s)
frozen=['native','iso','saver','fragment','gl','store','spool']
proof={'revision':'MONOLIVEGL2A_CONTROLLEDOES','curveSha256':sha(curve),'frozen':{},'changed':{}}
for k in frozen:
 after=(root/paths[k]).read_bytes();assert after==before[k],k;proof['frozen'][paths[k]]=sha(after)
clean=(root/paths['renderer']).read_text().replace(export,'',1)
assert clean.encode()==before['renderer'],'native still renderer changed outside additive exporter'
proof['rendererMinusReadOnlyExporter']=sha(clean.encode())
for k in paths:
 after=(root/paths[k]).read_bytes()
 if after!=before[k]:proof['changed'][paths[k]]={'before':sha(before[k]),'after':sha(after)}
(root/'MONOLIVEGL2A_ISOLATION.json').write_text(json.dumps(proof,indent=2)+'\n')
print('MONOLIVEGL2A applied: controlled preview source, SOURCE1D + exact Monochrom curve, 1Hz paired probe')
print('7 untouched-file hashes + renderer stripped-exporter exact identity passed')
print('Auto policy code frozen; input YUV statistics can change. Phone parity NOT validated.')
