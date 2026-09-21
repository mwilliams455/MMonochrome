#!/usr/bin/env python3
"""Lookup-only overlay on delivered MONOOUTPUT1B. Refuse nonidentical runtime baselines."""
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
java='app/src/main/java/com/particlesdevs/photoncamera/'
sha=lambda b:hashlib.sha256(b).hexdigest()
proof=json.loads((root/'MONOOUTPUT1B_ISOLATION.json').read_text())
for group in ['frozen','changed','new']:
    for rel,value in proof[group].items():
        h=value['after'] if group=='changed' else value
        if sha((root/rel).read_bytes())!=h:raise SystemExit('MONOOUTPUT1B baseline mismatch: '+rel)
before={str(p.relative_to(root)):sha(p.read_bytes()) for p in (root/'app/src/main').rglob('*') if p.is_file()}
changed={}
def one(s,a,b):
    if s.count(a)!=1:raise SystemExit('Expected exactly one anchor: '+repr(a[:100]))
    return s.replace(a,b,1)
def put(rel,s):
    p=root/rel;old=p.read_bytes();p.write_text(s)
    changed[rel]={'before':sha(old),'after':sha(p.read_bytes())}
rel=java+'m9/export/MonoDngPublicWriter1B.java'
old=(root/rel).read_text();new=(here/'MonoDngPublicWriter1B.java').read_text()
# Full direct transport and byte-copy/flush/close implementation must remain identical.
a='    private void viaDirect('
assert old[old.index(a):]==new[new.index(a):], 'direct writer changed'
put(rel,new)
rel=java+'m9/M9DiagnosticBurstSpool.java';s=(root/rel).read_text()
a=s.index('    private static boolean writePublic(');b=s.index('    public static JSONObject snapshotJson()',a)
oldwriter=s[a:b]
newwriter='''    private static boolean writePublic(Path path, byte[] bytes) {
        // MONOOUTPUT1C_CURSORQUERY: unchanged bytes through a projected SAF query.
        return com.particlesdevs.photoncamera.m9.export.MonoDiagnosticPublicWriter1C.write(
                PhotonCamera.getAppContext(), path, bytes);
    }

'''
s=s[:a]+newwriter+s[b:]
telemetry='''            o.put("publicLookup1C", com.particlesdevs.photoncamera.m9.export.MonoDiagnosticPublicWriter1C.snapshotJson());
'''
s=one(s,'            o.put("schema", SCHEMA);\n','            o.put("schema", SCHEMA);\n'+telemetry)
assert s.replace(newwriter,oldwriter,1).replace(telemetry,'',1)==(root/rel).read_text()
put(rel,s)
newfiles={}
for name in ['MonoSafQuery1C.java','MonoDiagnosticPublicWriter1C.java']:
    p=root/java/'m9/export'/name
    if p.exists():raise SystemExit('new class exists: '+name)
    p.write_bytes((here/name).read_bytes());newfiles[str(p.relative_to(root))]=sha(p.read_bytes())
rel='app/build.gradle';s=(root/rel).read_text()
put(rel,one(s,"versionName '0.04-mmonochrome-monoauto1a-output1b'","versionName '0.05-mmonochrome-monoauto1a-output1c'"))
frozen={rel:h for rel,h in before.items() if rel not in changed}
for rel,h in frozen.items():assert sha((root/rel).read_bytes())==h,rel
report={'revision':'MONOOUTPUT1C_CURSORQUERY','baselineCommit':'7531f8bc0fc6487d0eb1b83666a8c12472f8e13c',
        'changed':changed,'frozen':frozen,'new':newfiles,'diagnosticSpoolMinusPublicWriterAndTelemetryExact':True,
        'dngDirectCopyFlushCloseExact':True,'durableJobStorageAndRecoveryUnchanged':True,
        'stillRendererChanged':False,'exposurePlanChanged':False,'dngWriterOrPlaneChanged':False,'previewShaderChanged':False,
        'directoryAlgorithm':'fresh_projected_child_cursor_no_per_child_metadata_requests_no_negative_cache',
        'phoneExportSpeedValidated':False}
(root/'MONOOUTPUT1C_ISOLATION.json').write_text(json.dumps(report,indent=2)+'\n')
print('MONOOUTPUT1C applied: '+str(len(frozen))+' unchanged runtime files, '+str(len(changed))+' changes, '+str(len(newfiles))+' new files')
print('No photo, DNG samples, exposure, durable queue state or startup changes. Phone speed unvalidated.')
