#!/usr/bin/env python3
"""Storage-only overlay on exact MONOAUTO1A. No source, tone, exposure, or DNG-sample changes."""
from pathlib import Path
import hashlib,json,sys
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
java='app/src/main/java/com/particlesdevs/photoncamera/'
sha=lambda b:hashlib.sha256(b).hexdigest()
proof=json.loads((root/'MONOAUTO1A_ISOLATION.json').read_text())
for rel,h in proof['frozen'].items():
    if not (root/rel).exists() and rel=='app/src/main/cpp/deps/.gitignore' and '--artifact-subset' in sys.argv:
        print('Local artifact omits generated hidden deps/.gitignore; CI must check the full parent.')
        continue
    if sha((root/rel).read_bytes())!=h:raise SystemExit('MONOAUTO1A frozen baseline mismatch: '+rel)
for rel,pair in proof['changed'].items():
    if sha((root/rel).read_bytes())!=pair['after']:raise SystemExit('MONOAUTO1A changed baseline mismatch: '+rel)
# Protect all supplied runtime code and assets, not just a curated subset.
protected=[p for p in (root/'app/src/main').rglob('*') if p.is_file()]
before={str(p.relative_to(root)):sha(p.read_bytes()) for p in protected}
changed={}
def one(s,a,b):
    if s.count(a)!=1:raise SystemExit('Expected one anchor: '+repr(a[:80]))
    return s.replace(a,b,1)
def put(rel,text):
    p=root/rel;old=p.read_bytes();p.write_text(text)
    changed[rel]={'before':sha(old),'after':sha(p.read_bytes())}
rel=java+'m9/export/MonoDngExport1A.java';s=(root/rel).read_text()
a=s.index('    private static final ThreadPoolExecutor IO=');b=s.index('    private MonoDngExport1A(){}',a)
s=s[:a]+(here/'export_transport.inc').read_text()+s[b:]
a=s.index('    public static JSONObject submit(');b=s.index('    private static String stem(',a)
s=s[:a]+(here/'export_submit.inc').read_text()+s[b:]
for line in ['import java.util.concurrent.ArrayBlockingQueue;\n','import java.util.concurrent.ThreadPoolExecutor;\n','import java.util.concurrent.RejectedExecutionException;\n']:
    s=s.replace(line,'')
put(rel,s)
# App start resumes ready private jobs without waiting for another photograph.
rel=java+'app/PhotonCamera.java';s=(root/rel).read_text()
hook='\n        // MONOOUTPUT1B_STARTUP: asynchronous private-job recovery; no camera or pixel access.\n        com.particlesdevs.photoncamera.m9.export.MonoDngExport1A.startRecovery();\n'
s=one(s,'        SimpleStorageHelper.init(this);','        SimpleStorageHelper.init(this);'+hook);put(rel,s)
# Cached non-blocking admission. No disk/public I/O and no exposure choice on the UI thread.
rel=java+'capture/CaptureController.java';s=(root/rel).read_text()
hook2='''        // MONOOUTPUT1B_ADMISSION: keep bounded durable storage; do not silently drop derived RAW.
        if (!com.particlesdevs.photoncamera.m9.export.MonoDngExport1A.admitCapture1B()) return;
'''
anchor='''            Log.w(TAG, "takePicture(): camera not ready, ignoring shutter press");
            return;
        }
'''
s=one(s,anchor,anchor+hook2);put(rel,s)
for name in ['MonoDngSpool1B.java','MonoDngPublicWriter1B.java']:
    p=root/java/'m9/export'/name
    if p.exists():raise SystemExit('New class exists: '+name)
    p.write_bytes((here/name).read_bytes())
rel='app/build.gradle';s=(root/rel).read_text()
s=one(s,"versionName '0.03-mmonochrome-gl2b-monoauto1a'","versionName '0.04-mmonochrome-monoauto1a-output1b'");put(rel,s)
frozen={rel:h for rel,h in before.items() if rel not in changed}
for rel,h in frozen.items():assert sha((root/rel).read_bytes())==h,rel
assert sha((root/(java+'app/PhotonCamera.java')).read_text().replace(hook,'',1).encode())==before[java+'app/PhotonCamera.java']
assert sha((root/(java+'capture/CaptureController.java')).read_text().replace(hook2,'',1).encode())==before[java+'capture/CaptureController.java']
report={'revision':'MONOOUTPUT1B_DURABLE_EXPORT','baselineCommit':'c5d22ddda0528f29a87ee6437b708e6a2fa665fc','changed':changed,
        'frozen':frozen,'new':{java+'m9/export/'+n:sha((here/n).read_bytes()) for n in ['MonoDngSpool1B.java','MonoDngPublicWriter1B.java']},
        'captureControllerMinusAdmissionExact':True,'applicationMinusStartupHookExact':True,
        'stillRendererChanged':False,'sourceLuminanceChanged':False,'dngWriterOrPlaneChanged':False,
        'exposureAllocatorChanged':False,'previewShaderChanged':False,'phoneExportReliabilityValidated':False}
(root/'MONOOUTPUT1B_ISOLATION.json').write_text(json.dumps(report,indent=2)+'\n')
print('MONOOUTPUT1B applied; frozen runtime files:',len(frozen))
print('Complete still renderer, DNG writer/plane, GL shader, exposure logic unchanged.')
print('Private synchronous staging replaces lossy full-plane queue. Public verified publication is retryable.')
