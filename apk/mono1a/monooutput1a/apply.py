#!/usr/bin/env python3
"""MONOOUTPUT1A: comparison bank off; derived linear DNG export; GL2A/capture/native frozen."""
from pathlib import Path
import hashlib,json,sys,re
root=Path(sys.argv[1]).resolve(); here=Path(__file__).resolve().parent
J='app/src/main/java/com/particlesdevs/photoncamera/'
rpath=root/J/'m9/render/M9R35Renderer.java'
s=rpath.read_text();before=s
expected='36b6356c2818dd459201777ddad4b225bbbb093b634da33ba25ead71ca79eeb0'
sha=lambda b:hashlib.sha256(b).hexdigest()
if sha(rpath.read_bytes())!=expected:raise SystemExit('MONOOUTPUT1A requires exact GL2A renderer')
frozen=[J+'capture/CaptureController.java',J+'ui/camera/CameraFragment.java',J+'ui/camera/views/viewfinder/MainRenderer.java',
 J+'ui/camera/views/viewfinder/GLPreview.java',J+'processing/parameters/IsoExpoSelector.java',J+'processing/SaverImplementation.java',
 J+'m9/preview/MonoGpuPreview2A.java',J+'m9/preview/MonoPreviewMath2A.java',J+'m9/preview/MonoLivePairDiagnostics1E.java',
 J+'m9/preview/MonoLivePairExport1D.java',J+'m9/M9DeferredMetadataStore.java',J+'m9/M9DiagnosticBurstSpool.java',
 'app/src/main/cpp/m9color_jni.cpp','app/src/main/assets/shaders/preview/main_fs.glsl','app/src/main/assets/mono/mono_curve02_gl2a.bin']
sealed={rel:sha((root/rel).read_bytes()) for rel in frozen}
changes=[]
def one(old,new,label):
 global s
 if s.count(old)!=1:raise SystemExit(label+': expected 1 anchor, got '+str(s.count(old)))
 s=s.replace(old,new,1);changes.append((old,new,label))
one('import android.graphics.Bitmap;', 'import android.graphics.Bitmap;\nimport com.particlesdevs.photoncamera.m9.export.MonoDngExport1A;', 'import')
one('        if (MONO1A_ENABLED) {\n            final int rawScalarRotation',
    '        if (MONO1A_ENABLED && MonoDngExport1A.comparisons()) {\n            final int rawScalarRotation','skip four Bayer controls before allocation')
one('        Mat meterCam16 = new Mat();\n        try {\n            long demosaicStartedNs = System.nanoTime();\n            long[] mhcStats = new long[2];',
'''        Mat meterCam16 = new Mat();
        MonoDngExport1A.Pending monoDngPending1A = null;
        String monoDngCopyError1A = null;
        try {
            long demosaicStartedNs = System.nanoTime();
            long[] mhcStats = new long[2];''','DNG local owned copy')
one('            // BASISHSM1E-SHADINGDOMAIN1A: restore the temporary Bayer transport scale',
'''            // MONOOUTPUT1A: tap the already-demosaiced transport BEFORE its uint16
            // range is restored/clipped for JPEG. The exporter only reads this Mat.
            if (MONO1A_ENABLED) {
                try {
                    NativeProspectiveSource monoDngSource1A = buildNativeProspectiveSource(
                            nativeCharacteristics, nativeCaptureResult);
                    monoDngPending1A = MonoDngExport1A.capture(cam16,width,height,cameraRotation,
                            new float[]{monoDngSource1A.sensorToXyzD50[3],monoDngSource1A.sensorToXyzD50[4],monoDngSource1A.sensorToXyzD50[5]},
                            applyNativeShading && nativeShading.applied ? nativeShading.representationScale : 1.0);
                } catch (Throwable exportCopyError) {
                    monoDngCopyError1A = exportCopyError.toString(); // Original RAW + JPEG remain authoritative.
                }
            }
            // BASISHSM1E-SHADINGDOMAIN1A: restore the temporary Bayer transport scale''','read only pre clip tap')
old='''                Bitmap monoBitmap = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888);
                long[] monoStats = new long[35];
                boolean monoOk = M9NativeColorCore.renderMonochrome1ADirectBitmap('''
new='''                Bitmap monoBitmap = MonoDngExport1A.comparisons()
                        ? Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888) : null;
                long[] monoStats = new long[35];
                boolean monoOk = !MonoDngExport1A.comparisons() || M9NativeColorCore.renderMonochrome1ADirectBitmap('''
one(old,new,'skip M9Y control allocation/kernel')
one('                Bitmap greenOnlyBitmap = Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888);',
'''                Bitmap greenOnlyBitmap = MonoDngExport1A.comparisons()
                        ? Bitmap.createBitmap(outW, outH, Bitmap.Config.ARGB_8888) : null;''','skip green allocation')
one('''                boolean greenOnlyOk = equalRgbOk && M9NativeColorCore.renderMonochrome1AVariantDirectBitmap(
                        cam16.dataAddr(), pixels, width, height, greenOnlyBitmap,
                        cameraRotation, NATIVE_COLOR_WORKERS,
                        MONO1A_SYNTHETIC_PEDESTAL14, 2);''',
'''                boolean greenOnlyOk = !MonoDngExport1A.comparisons() || (equalRgbOk && M9NativeColorCore.renderMonochrome1AVariantDirectBitmap(
                        cam16.dataAddr(), pixels, width, height, greenOnlyBitmap,
                        cameraRotation, NATIVE_COLOR_WORKERS,
                        MONO1A_SYNTHETIC_PEDESTAL14, 2));''','skip green kernel')
# Nullable diagnostic Bitmap cleanup only; do not modify primary cleanup.
one('                    if (!monoBitmap.isRecycled()) monoBitmap.recycle();\n                    if (!equalRgbBitmap.isRecycled()) equalRgbBitmap.recycle();\n                    if (!greenOnlyBitmap.isRecycled()) greenOnlyBitmap.recycle();',
'''                    if (monoBitmap != null && !monoBitmap.isRecycled()) monoBitmap.recycle();
                    if (!equalRgbBitmap.isRecycled()) equalRgbBitmap.recycle();
                    if (greenOnlyBitmap != null && !greenOnlyBitmap.isRecycled()) greenOnlyBitmap.recycle();''','nullable cleanup')
# Diagnostic rawscalar details dereference the D65-only calibration. Do not evaluate when disabled.
a=s.index('                JSONObject rawScalar1A = new JSONObject();');b=s.index('                d.put("rawScalar1BSharpStdPolicy",',a)
b=s.index('\n',b)+1
old=s[a:b]
new='                if (MonoDngExport1A.comparisons()) {\n'+old+'                }\n'
one(old,new,'skip control-only diagnostic dependencies')
old='''                return new RenderCore(equalRgbBitmap, d, rawScalar1BBitmap, greenOnlyBitmap, rawScalar1ABitmap, monoBitmap, rawScalar1BSharpStdBitmap, rawScalar1BSharpStdNormIsoBitmap);'''
new='''                // MONOOUTPUT1A: avoid reporting zero-filled, unmeasured control stats as primary evidence.
                d.put("outputRevision",MonoDngExport1A.REVISION);
                d.put("comparisonImagesEnabled",MonoDngExport1A.comparisons());
                d.put("source1cVisualAbRendered",MonoDngExport1A.comparisons());
                d.put("sourceAdapter","SOURCE1D_NATIVE_DNG_XYZ_Y");
                d.put("sourceLuma","native_sensorToXYZD50_Y_row_dot_cam16");
                d.put("sourceLumaProvenance","active_physical_Camera2_DNG_not_Leica_spectral_truth");
                if (!MonoDngExport1A.comparisons()) {
                    String[] unmeasured={"nativePixelCount","lutLowClampCount","lutHighIndexCount","nearWhiteOutputCount",
                            "nativeWorkerNsSum","nativeWorkersUsed","nativeMonoRenderNs","nativePedestal14Echo",
                            "sourceIndexQ50","sourceIndexQ90","sourceIndexQ95","sourceIndexQ99",
                            "curveOutputAtSourceQ50","curveOutputAtSourceQ90","curveOutputAtSourceQ95","curveOutputAtSourceQ99",
                            "curveOutputMeanControl","counterfactualEqualRgb","counterfactualGreenOnly"};
                    for(String key:unmeasured)d.remove(key);
                    d.put("comparisonMeasurements","not_run");
                    d.put("monochromSharpIsoBridgeDiagnosticsRetained","available_only_in_developer_comparison_build");
                }
                if(monoDngCopyError1A!=null)d.put("monoDngCopyError",monoDngCopyError1A);
                RenderCore result1A = new RenderCore(equalRgbBitmap, d, rawScalar1BBitmap, greenOnlyBitmap, rawScalar1ABitmap, monoBitmap, rawScalar1BSharpStdBitmap, rawScalar1BSharpStdNormIsoBitmap);
                result1A.monoDngPending1A=monoDngPending1A;
                return result1A;'''
one(old,new,'owned pending attaches to render')
one('        final Bitmap rawScalar1BSharpStdNormIsoBitmap;','        final Bitmap rawScalar1BSharpStdNormIsoBitmap;\n        MonoDngExport1A.Pending monoDngPending1A;','render owned export')
one('            long jpegStartedNs = System.nanoTime();',
'''            // Thumbnail is a small independent copy; never retain/recycle the primary bitmap in an export worker.
            MonoDngExport1A.thumbnail(out.monoDngPending1A, bitmap);
            long jpegStartedNs = System.nanoTime();''','DNG thumbnail before JPEG consumes bitmap')
one('            if (!jpgSaved) throw new IllegalStateException("M9 JPEG payload save failed");',
'''            if (!jpgSaved) throw new IllegalStateException("M9 JPEG payload save failed");
            out.diagnostics.put("monoDngExport",MonoDngExport1A.submit(
                    out.monoDngPending1A,dngPath,diagnosticCaptureResult1A,params.cameraID));
            out.monoDngPending1A=null;''','submit after successful JPEG')
one('            diag.put("source1cVisualAbEnabled", true);','            diag.put("source1cVisualAbEnabled", MonoDngExport1A.comparisons());','truthful export gate')
one('        d.put("sourceTransformFamily", "provisional_Bayer_to_monochrome_M9Y_control");',
'        d.put("sourceTransformFamily", "active_physical_Camera2_DNG_to_XYZ_D50_Y");','correct inherited metadata label')
one('        d.put("pipeline", "black_white_normalize -> physical Camera2 LensShadingMap -> DEMOSAICMHCNEUTRAL1A -> provisional M9Y scalar -> Leica14 mode0 -> M Monochrom 1.022 curve02");',
'        d.put("pipeline", "black_white_normalize -> physical Camera2 LensShadingMap -> DEMOSAICMHCNEUTRAL1A -> SOURCE1D_XYZ_D50_Y -> Leica14 mode0 -> M Monochrom 1.022 curve02");','correct pipeline label')
# Exact primary native-call text must still occur once and be byte-identical.
pattern=r'                boolean equalRgbOk = M9NativeColorCore.renderMonochrome1AWeightedDirectBitmap\(.*?\);'
primary=re.search(pattern,before,re.S)[0]
assert s.count(primary)==1,'primary native call changed'
# Reversing only this declared edit list must reproduce the parent renderer exactly.
undo=s
for old,new,label in reversed(changes):
 if undo.count(new)!=1:raise SystemExit('reversible proof failed '+label)
 undo=undo.replace(new,old,1)
assert undo==before,'undeclared change'
rpath.write_text(s)
for name in ['MonoLinearPlane1A.java','MonoDngWriter1A.java','MonoDngExport1A.java']:
 target=root/J/'m9/export'/name;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes((here/name).read_bytes())
for rel,h in sealed.items():assert sha((root/rel).read_bytes())==h,rel
proof={'revision':'MONOOUTPUT1A_LINEAR_DNG','frozenFiles':sealed,'rendererBefore':sha(before.encode()),
 'rendererAfter':sha(s.encode()),'declaredReversibleEdits':[label for a,b,label in changes],
 'primaryNativeCallSha256':sha(primary.encode()),'primaryNativeKernelByteIdentical':True,
 'comparisonBankEnabledByDefault':False,'originalRawSavingUnchanged':True,'previewAndExposurePolicyUnchanged':True,
 'devicePortabilityNoNewModelGate':True,'derivedDngLightroomValidated':False}
(root/'MONOOUTPUT1A_ISOLATION.json').write_text(json.dumps(proof,indent=2)+'\n')
g=root/'app/build.gradle';g.write_text(g.read_text().replace('-monolivegl2a\'','-monolivegl2a-monooutput1a\''))
print(json.dumps(proof,indent=2))
