#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, runpy, subprocess, sys, tempfile
import numpy as np
import tifffile

if len(sys.argv)!=2: raise SystemExit('usage: test.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
pkg='com/particlesdevs/photoncamera/m9/export'
proof=json.loads((root/'MONOSAVELOOKUP1A_ISOLATION.json').read_text())
for rel,sha in proof['frozenSourceHashes'].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==sha,rel
stubs=runpy.run_path(str(here.parent/'monooutput1c/mocks.py'))['stubs'].copy()
# The inherited resolver mock uses Objects.equals for opaque document IDs.
key='android/content/ContentResolver.java'
assert stubs[key].count('import java.io.*;')==1
stubs[key]=stubs[key].replace('import java.io.*;', 'import java.util.Objects; import java.io.*;', 1)
# Add the two public APIs used by the candidate; IDs remain opaque, not paths.
key='android/net/Uri.java'
anchor=' public String id(){return id;}'
assert stubs[key].count(anchor)==1
stubs[key]=stubs[key].replace(anchor,''' public static Uri parse(String s){
 int at=s.indexOf("/document/");if(at<0)throw new IllegalArgumentException("invalid_uri");
 String id=s.substring(at+10);return new Uri(pathOf(id),false,s.contains("/tree/"));
 }
'''+anchor)
key='android/provider/DocumentsContract.java'
anchor=' public static Uri renameDocument('
assert stubs[key].count(anchor)==1
stubs[key]=stubs[key].replace(anchor,''' public static boolean deleteDocument(ContentResolver r,Uri u)throws IOException {
  if(ContentResolver.denyWrite)throw new IOException("delete_permission_denied");
  return Files.deleteIfExists(u.path);
 }
'''+anchor)
results={}
with tempfile.TemporaryDirectory() as td:
    d=Path(td)
    for mode in ['baseline','candidate']:
        work=d/mode;work.mkdir()
        for rel,src in stubs.items():
            p=work/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(src)
        target=work/pkg;target.mkdir(parents=True,exist_ok=True)
        for name in ['MonoDngSpool1B.java','MonoDngPublicWriter1B.java','MonoDngWriter1A.java','MonoLinearPlane1A.java','MonoSafQuery1C.java']:
            source=root/'app/src/main/java'/pkg/name
            if mode=='baseline' and name=='MonoDngPublicWriter1B.java':
                source=here.parent/'monooutput1c'/name
            (target/name).write_bytes(source.read_bytes())
        (target/'SaveLookupTest.java').write_bytes((here/'SaveLookupTest.java').read_bytes())
        subprocess.run(['javac','--release','17','-d',str(work/'classes')]+[str(p) for p in work.rglob('*.java')],check=True)
        run=subprocess.run(['java','-cp',str(work/'classes'),'com.particlesdevs.photoncamera.m9.export.SaveLookupTest',str(work/'fixtures'),mode],text=True,capture_output=True)
        print(run.stdout,end='');print(run.stderr,end='',file=sys.stderr);run.check_returncode()
        text=run.stdout
        scans=re.search(r'SCAN_MEASUREMENT mode=\w+ childQueries=(\d+) childRows=(\d+)',text)
        counts=re.search(r'_PASS scenarios=(\d+) assertions=(\d+)',text)
        assert scans and counts
        results[mode]={'childQueries':int(scans[1]),'childRows':int(scans[2]),'scenarios':int(counts[1]),'assertions':int(counts[2])}
    reference=d/'candidate/fixtures/reference_12mp.dng'
    transported=d/'candidate/fixtures/transport_12mp.dng'
    assert reference.read_bytes()==transported.read_bytes()
    with tifffile.TiffFile(transported) as f:
        raw=f.pages[0].pages[0];samples=raw.asarray()
        assert samples.shape==(4096,3072) and samples.dtype==np.uint16
        assert int(raw.photometric)==34892 and raw.samplesperpixel==1
        assert 33422 not in raw.tags and 50721 not in raw.tags
    w=np.array([.65497077,.7578125,.042704627],np.float32).astype(float)
    cols=np.arange(4096,dtype=np.int64)[None,:]
    for start in range(0,3072,128):
        rows=np.arange(start,start+128,dtype=np.int64)[:,None]
        expected=np.floor(((cols*13+rows*19)%65536*w[0]+(cols*17+rows*7)%65536*w[1]+(cols*23+rows*11)%65536*w[2])/sum(w)+.5).astype(np.uint16)
        assert np.array_equal(samples[:,3072-start-128:3072-start],expected[::-1,:].T)
    assert results['baseline']['childQueries']==2
    assert results['candidate']['childQueries']==1
    report={'revision':'MONOOUTPUT1H_SAVELOOKUP1A','status':'PASS',
        'scope':'actual_publisher_and_durable_store_with_deterministic_Android_provider_mocks_not_phone',
        'comparison':results,'scenarios':sum(v['scenarios'] for v in results.values()),
        'assertions':sum(v['assertions'] for v in results.values()),
        'exactDngSampleCount':int(samples.size),'byteIdenticalDngWriterOutput':True,
        'syntheticDngSha256':hashlib.sha256(transported.read_bytes()).hexdigest(),
        'knownFinalRecoveryFullScans':0,'freshFinalCollisionCheckRetained':True,
        'unknownOrLegacyRecoveryFallbackRetained':True,'opaqueDocumentIds':True,
        'frozenSourceFileCount':proof['frozenSourceFileCount'],
        'photographicSettingsChanged':False,'diagnosticsStillEnabled':True,'phoneSpeedValidated':False}
    (root/'MONOSAVELOOKUP1A_TEST_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
