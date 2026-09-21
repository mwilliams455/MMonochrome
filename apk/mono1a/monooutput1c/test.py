#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,re
import numpy as np
import tifffile
from mocks import stubs
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
parent=Path(sys.argv[2]).resolve() if len(sys.argv)>2 else here.parent/'monooutput1b'
proof=json.loads((root/'MONOOUTPUT1C_ISOLATION.json').read_text())
for group in ['frozen','changed','new']:
    for rel,v in proof[group].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==(v['after'] if group=='changed' else v),rel
logs=[]
with tempfile.TemporaryDirectory() as d:
    d=Path(d);pkg='com/particlesdevs/photoncamera/m9/export'
    for rel,s in stubs.items():
        p=d/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
    for n in ['MonoDngSpool1B.java','MonoDngPublicWriter1B.java','MonoDngWriter1A.java','MonoLinearPlane1A.java','MonoSafQuery1C.java','MonoDiagnosticPublicWriter1C.java']:
        p=d/pkg/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((root/'app/src/main/java'/pkg/n).read_bytes())
    p=d/'com/particlesdevs/photoncamera/m9/M9DiagnosticBurstSpool.java'
    p.write_bytes((root/'app/src/main/java/com/particlesdevs/photoncamera/m9/M9DiagnosticBurstSpool.java').read_bytes())
    for n in ['SpoolTest.java','PublisherTest.java']:(d/pkg/n).write_bytes((parent/n).read_bytes())
    (d/pkg/'QueryExportTest.java').write_bytes((here/'QueryExportTest.java').read_bytes())
    subprocess.run(['javac','--release','17','-d',str(d/'classes')]+[str(p) for p in d.rglob('*.java')],check=True)
    for name in ['SpoolTest','PublisherTest','QueryExportTest']:
        p=subprocess.run(['java','-cp',str(d/'classes'),'com.particlesdevs.photoncamera.m9.export.'+name,str(d/name)],text=True,capture_output=True)
        print(p.stdout,end='');print(p.stderr,end='',file=sys.stderr);p.check_returncode();logs.append(p.stdout)
    reference=d/'SpoolTest/reference_12mp.dng';transport=d/'SpoolTest/transport_12mp.dng'
    assert reference.read_bytes()==transport.read_bytes()
    with tifffile.TiffFile(transport) as t:
        raw=t.pages[0].pages[0];samples=raw.asarray()
        assert samples.shape==(4096,3072) and samples.dtype==np.uint16
        assert int(raw.photometric)==34892 and raw.samplesperpixel==1
        assert 33422 not in raw.tags and 50721 not in raw.tags
    rows=np.arange(3072,dtype=np.int64)[:,None];cols=np.arange(4096,dtype=np.int64)[None,:]
    w=np.array([.65497077,.7578125,.042704627],np.float32).astype(float)
    expected=np.floor(((cols*13+rows*19)%65536*w[0]+(cols*17+rows*7)%65536*w[1]+(cols*23+rows*11)%65536*w[2])/sum(w)+.5).astype(np.uint16)
    assert np.array_equal(samples,np.rot90(expected,-1))
    report={'revision':'MONOOUTPUT1C_CURSORQUERY','status':'PASS','scope':'actual_query_publisher_durable_spool_and_diagnostic_spool_filesystem_Android_cursor_mocks_not_phone',
            'scenarios':sum(int(re.search(r'_PASS scenarios=(\d+)',s)[1]) for s in logs),
            'assertions':sum(int(re.search(r'assertions=(\d+)',s)[1]) for s in logs),
            'newQueryScenarios':int(re.search(r'_PASS scenarios=(\d+)',logs[-1])[1]),
            'newQueryAssertions':int(re.search(r'assertions=(\d+)',logs[-1])[1]),
            'exactDngSampleCount':int(samples.size),'byteIdenticalDngWriterOutput':True,
            'dngSha256':hashlib.sha256(transport.read_bytes()).hexdigest(),
            'largeDirectoryUnrelatedChildren':10000,'newDngChildQueries':2,'newDngKnownUriQueries':2,
            'newDiagnosticChildQueriesPerWrite':1,'newDiagnosticUpdateMetadataQueries':0,
            'legacyFindFileAndPerChildNameCalls':0,'negativeLookupCache':False,
            'frozenRuntimeFiles':len(proof['frozen']),'phoneSpeedValidated':False}
    (root/'MONOOUTPUT1C_TEST_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
