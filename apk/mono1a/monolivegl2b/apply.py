#!/usr/bin/env python3
"""Preview-only GL2F curve-contract port plus bounded pre-shutter diagnostic history."""
from pathlib import Path
import hashlib, json, sys
root=Path(sys.argv[1]).resolve()
java='app/src/main/java/com/particlesdevs/photoncamera/'
prefix=java+'m9/preview/'
proof=json.loads((root/'MONOOUTPUT1A_ISOLATION.json').read_text())
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
# Start from the exact delivered MONOOUTPUT1A, not an unverified branch reconstruction.
for rel,h in proof['frozenFiles'].items():
    if sha(root/rel)!=h: raise SystemExit('MONOOUTPUT1A baseline mismatch: '+rel)
if sha(root/(java+'m9/render/M9R35Renderer.java'))!=proof['rendererAfter']:
    raise SystemExit('MONOOUTPUT1A renderer mismatch')
paths=[prefix+n for n in ('MonoPreviewMath2A.java','MonoGpuPreview2A.java','MonoLivePairDiagnostics1E.java','MonoLivePairExport1D.java')]+['app/build.gradle']
original={rel:(root/rel).read_text() for rel in paths}
frozen=set(proof['frozenFiles'])-set(paths)
frozen.add(java+'m9/render/M9R35Renderer.java')
frozen.update(java+'m9/export/'+n for n in ('MonoDngExport1A.java','MonoDngWriter1A.java','MonoLinearPlane1A.java'))
frozen={rel:sha(root/rel) for rel in sorted(frozen)}
def one(s,a,b):
    if s.count(a)!=1: raise SystemExit('Expected one anchor: '+repr(a[:100]))
    return s.replace(a,b,1)
math=original[prefix+'MonoPreviewMath2A.java']
math=one(math,'''            double s = (double) i / (n - 1);
            a[i * 2] = (float) decode(s); a[i * 2 + 1] = (float) s;''','''            // MONOLIVEGL2B: same sRGB meaning, uniform linear-input positions.
            double x = (double) i / (n - 1);
            a[i * 2] = (float) x;
            a[i * 2 + 1] = (float) (x <= .0031308 ? 12.92*x : 1.055*Math.pow(x,1.0/2.4)-.055);''')
math=one(math,'    public static boolean validCurve(float[] c) {','''    /** Exact maximum vertical difference of piecewise-linear curves: union of knots. */
    public static double curveOutputError(float[] requested, float[] reported) {
        if (!validCurve(requested) || !validCurve(reported)) return Double.POSITIVE_INFINITY;
        double error=0;
        for(float[] knots:new float[][]{requested,reported}) for(int i=0;i<knots.length;i+=2)
            error=Math.max(error,Math.abs(curveOutput(requested,knots[i])-curveOutput(reported,knots[i])));
        return error;
    }
    public static double curveOutput(float[] c,double x) {
        if(x<=0) return 0; if(x>=1) return 1;
        for(int i=2;i<c.length;i+=2) if(x<=c[i])
            return c[i-1]+(c[i+1]-c[i-1])*(x-c[i-2])/(c[i]-c[i-2]);
        return 1;
    }
    public static boolean validCurve(float[] c) {''')
gpu=original[prefix+'MonoGpuPreview2A.java']
gpu=one(gpu,'import java.util.Arrays;','import java.util.Arrays;\nimport java.util.ArrayDeque;\nimport java.util.Iterator;')
gpu=one(gpu,'public static final String REVISION="MONOLIVEGL2A_CONTROLLEDOES";','''public static final String REVISION="MONOLIVEGL2B_CURVECONTRACT";
    private static final double MAX_CURVE_ERROR=3.0/255.0;
    private static long activeSession;
    private static final ArrayDeque<Draw> DRAWS=new ArrayDeque<>();
    private static final ArrayDeque<Draw> PROBES=new ArrayDeque<>();''')
gpu=one(gpu,'            lastDraw=null; lastProbe=null;','            lastDraw=null; lastProbe=null; DRAWS.clear(); PROBES.clear(); activeSession++;')
gpu=one(gpu,'        String key=System.identityHashCode(chars)+"|"+tone+"|"+transform+"|"+gains+"|"+Arrays.toString(neutral)+"|"+boost;','''        TonemapCurve requestTone=request.get(CaptureRequest.TONEMAP_CURVE);
        Integer maxPoints=chars.get(CameraCharacteristics.TONEMAP_MAX_CURVE_POINTS);
        if(requestTone==null || maxPoints==null || maxPoints<16)
            return Context.fallback("controlled_curve_request_unavailable");
        String key=System.identityHashCode(chars)+"|"+maxPoints+"|"+requestTone+"|"+tone+"|"+transform+"|"+gains+"|"+Arrays.toString(neutral)+"|"+boost;''')
gpu=one(gpu,'        Rational[] elements=new Rational[9]; transform.copyElements(elements,0);','''        float[] expected=MonoPreviewMath2A.srgbCurve(maxPoints);
        float[][] requestedCurves=new float[3][];
        double error=0, requestError=0;
        for(int c=0;c<3;c++) {
            requestedCurves[c]=new float[requestTone.getPointCount(c)*2];
            requestTone.copyColorCurve(c,requestedCurves[c],0);
            requestError=Math.max(requestError,MonoPreviewMath2A.curveOutputError(expected,requestedCurves[c]));
            error=Math.max(error,MonoPreviewMath2A.curveOutputError(requestedCurves[c],curves[c]));
        }
        Context rejected=null;
        if(requestError>MAX_CURVE_ERROR) rejected=Context.fallback("unexpected_preview_curve_request");
        else if(error>MAX_CURVE_ERROR) rejected=Context.fallback("reported_curve_disagrees_with_request");
        if(rejected!=null) {
            rejected.curveEvidence=curveEvidence(requestedCurves,curves,error,requestError);
            cachedKey=key; cachedContext=rejected; return rejected;
        }
        Rational[] elements=new Rational[9]; transform.copyElements(elements,0);''')
gpu=one(gpu,'        cachedKey=key; cachedContext=out; return out;','''        out.curveEvidence=curveEvidence(requestedCurves,curves,error,requestError);
        cachedKey=key; cachedContext=out; return out;''')
gpu=one(gpu,'    public static synchronized Binding bind(long textureTimestampNs) {','''    private static String curveEvidence(float[][] requested,float[][] reported,double error,double requestError) throws Exception {
        JSONObject o=new JSONObject(); JSONArray a=new JSONArray(),b=new JSONArray();
        for(float[] c:requested) a.put(new JSONArray(c));
        for(float[] c:reported) b.put(new JSONArray(c));
        o.put("revision",REVISION).put("requestedCurves",a).put("reportedCurves",b);
        o.put("requestSampling","uniform_linear_input_srgb_output");
        o.put("maxOutputError",Double.isFinite(error)?error:JSONObject.NULL);
        o.put("requestVsConfiguredError",Double.isFinite(requestError)?requestError:JSONObject.NULL);
        o.put("allowedOutputError",MAX_CURVE_ERROR);
        o.put("agrees",error<=MAX_CURVE_ERROR && requestError<=MAX_CURVE_ERROR);
        o.put("mismatchPolicy","existing_monochrome_OES_fallback_not_target_parity");
        o.put("pixelParityProven",false); return o.toString();
    }
    public static synchronized Binding bind(long textureTimestampNs) {''')
gpu=one(gpu,'    public static void publish(Binding binding,','    public static synchronized void publish(Binding binding,')
gpu=one(gpu,'        lastDraw=d;\n        if(probe!=null) lastProbe=d;','''        // SHUTTERHISTORY2B: a just-published post-shutter draw must not erase its predecessor.
        if(!binding.frame.camera.equals(activeCamera) || binding.sessionId!=activeSession) return;
        lastDraw=d; DRAWS.addLast(d); while(DRAWS.size()>32) DRAWS.removeFirst();
        if(probe!=null) { lastProbe=d; PROBES.addLast(d); while(PROBES.size()>4) PROBES.removeFirst(); }''')
gpu=one(gpu,'    public static synchronized JSONObject snapshot(long shutterElapsedNs) {','''    private static Draw before(ArrayDeque<Draw> history,long shutter,long maxAge) {
        for(Iterator<Draw> it=history.descendingIterator();it.hasNext();) {
            Draw d=it.next();
            if(d.binding.frame.camera.equals(activeCamera) && d.binding.sessionId==activeSession && d.elapsedNs<=shutter && shutter-d.elapsedNs<=maxAge) return d;
        }
        return null;
    }
    public static synchronized JSONObject snapshot(long shutterElapsedNs) {''')
gpu=one(gpu,'''            Draw d=lastDraw;
            if(d==null || !d.binding.frame.camera.equals(activeCamera) || d.elapsedNs>shutterElapsedNs ||
                    shutterElapsedNs-d.elapsedNs>500000000L) {
                out.put("status","unavailable_recent_pre_shutter_draw"); return out;
            }
            out.put("status","draw_recorded").put("draw",d.json(false));
            out.put("drawAgeMsAtShutter",(shutterElapsedNs-d.elapsedNs)/1e6);
            Draw p=lastProbe;
            if(p!=null && p.binding.frame.camera.equals(activeCamera) && p.elapsedNs<=shutterElapsedNs &&
                    shutterElapsedNs-p.elapsedNs<=2000000000L) {''','''            out.put("diagnosticHistoryRevision","SHUTTERHISTORY2B");
            out.put("drawHistoryCount",DRAWS.size()).put("probeHistoryCount",PROBES.size());
            Draw d=before(DRAWS,shutterElapsedNs,500000000L);
            if(d==null) out.put("status","unavailable_recent_pre_shutter_draw");
            else {
                out.put("status","draw_recorded").put("draw",d.json(false));
                out.put("drawAgeMsAtShutter",(shutterElapsedNs-d.elapsedNs)/1e6);
            }
            // An eligible older probe is useful even when the shutter draw is unavailable.
            Draw p=before(PROBES,shutterElapsedNs,2000000000L);
            if(p!=null) {''')
gpu=one(gpu,'p.binding.sequence==d.binding.sequence','d!=null && p.binding.sequence==d.binding.sequence')
gpu=one(gpu,'public final long textureTimestampNs,sequence;', 'public final long textureTimestampNs,sequence,sessionId;')
gpu=one(gpu,'exact=e;sequence=seq;}', 'exact=e;sequence=seq;sessionId=activeSession;}')
gpu=one(gpu,'        private final int boost;','''        private final int boost;
        // Serialized once before publication; consumers receive a freshly parsed object.
        private String curveEvidence;''')
gpu=one(gpu,'ready=true; reason="controlled_input_reported_not_device_pixel_validated";','ready=true; reason="controlled_curve_agrees_not_device_pixel_validated";')
gpu=one(gpu,'            o.put("ready",ready).put("reason",reason).put("fittedResidualApplied",false);','''            o.put("ready",ready).put("reason",reason).put("fittedResidualApplied",false);
            o.put("curveContract2B",curveEvidence==null?JSONObject.NULL:new JSONObject(curveEvidence));''')
changed={prefix+'MonoPreviewMath2A.java':math,prefix+'MonoGpuPreview2A.java':gpu}
for name in ('MonoLivePairDiagnostics1E.java','MonoLivePairExport1D.java'):
    changed[prefix+name]=original[prefix+name].replace('MONOLIVEGL2A_CONTROLLEDOES','MONOLIVEGL2B_CURVECONTRACT')
changed['app/build.gradle']=one(original['app/build.gradle'],"versionName '0.01-mmonochrome-mono1a-native-monolivegl2a-monooutput1a'","versionName '0.02-mmonochrome-gl2b-monooutput1a'")
for rel,text in changed.items(): (root/rel).write_text(text)
for rel,h in frozen.items():
    if sha(root/rel)!=h: raise SystemExit('Frozen file changed: '+rel)
report={'revision':'MONOLIVEGL2B_CURVECONTRACT','changed':{r:{'before':hashlib.sha256(original[r].encode()).hexdigest(),'after':sha(root/r)} for r in changed},'frozen':frozen,'stillRendererByteIdentical':True,'shaderByteIdentical':True,'dngExporterByteIdentical':True,'exposureAllocatorByteIdentical':True,'previewInputResponseMayChangeAutoStatistics':True,'deviceHazeFixValidated':False}
(root/'MONOLIVEGL2B_ISOLATION.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
