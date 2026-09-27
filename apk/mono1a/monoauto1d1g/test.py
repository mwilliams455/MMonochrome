#!/usr/bin/env python3
from pathlib import Path
import hashlib
import json
import subprocess
import sys
import tempfile

if len(sys.argv)!=3:
    raise SystemExit('usage: test.py <PhotonCamera-root> <org-json.jar>')
root=Path(sys.argv[1]).resolve()
jar=Path(sys.argv[2]).resolve()
if not jar.is_file():raise SystemExit('parent JSON host dependency missing')
here=Path(__file__).resolve().parent
J=root/'app/src/main/java/com/particlesdevs/photoncamera'
proof=json.loads((root/'MONORECEIPTHYGIENE1A_ISOLATION.json').read_text())
for rel,digest in proof['frozenSourceHashes'].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==digest,rel
store=(J/'m9/export/MonoDngSpool1B.java').read_text()
spool=(J/'m9/M9DiagnosticBurstSpool.java').read_text()
assert 'acknowledgedCompletion1G(j)' in store
assert 'for(Job j:ordered())emit(j,true);' not in store
assert 'mmonochrome_diag_spool_reset1b.done' in spool
assert 'MMONOSPOOLRESET1B_ONCE' in spool
assert proof['completedReceiptsRetainedForIdempotence']
assert proof['unfinishedDngRecoveryPreserved']
assert not proof['dngJobDirectoryPurged']
assert not proof['publicFilesDeleted']
assert not proof['exposurePolicyChanged']

with tempfile.TemporaryDirectory(prefix='mono-receipt1g-') as tmp:
    p=Path(tmp)
    sources={
        'com/particlesdevs/photoncamera/m9/export/MonoDngSpool1B.java':store,
        'com/particlesdevs/photoncamera/m9/M9DiagnosticBurstSpool.java':spool,
        'com/particlesdevs/photoncamera/m9/export/ReceiptRecoveryTest.java':(here/'ReceiptRecoveryTest.java').read_text(),
        'com/particlesdevs/photoncamera/m9/ResetIsolationTest.java':(here/'ResetIsolationTest.java').read_text(),
        'android/content/Context.java':'''package android.content;
public class Context {private final java.io.File files;
 public Context(java.io.File f){files=f;} public java.io.File getFilesDir(){return files;}}
''',
        'android/os/Process.java':'''package android.os;
public final class Process {public static final int THREAD_PRIORITY_BACKGROUND=10;
 public static void setThreadPriority(int p){}}
''',
        'com/particlesdevs/photoncamera/app/PhotonCamera.java':'''package com.particlesdevs.photoncamera.app;
public final class PhotonCamera {public static android.content.Context context;
 public static android.content.Context getAppContext(){return context;}}
''',
        'com/particlesdevs/photoncamera/util/Log.java':'''package com.particlesdevs.photoncamera.util;
public final class Log {public static void d(String t,String m){}
 public static void w(String t,String m){} public static void e(String t,String m){}
 public static void e(String t,String m,Throwable e){}}
''',
        'com/particlesdevs/photoncamera/util/SimpleStorageHelper.java':'''package com.particlesdevs.photoncamera.util;
public final class SimpleStorageHelper {}
''',
        'com/particlesdevs/photoncamera/m9/export/MonoDiagnosticPublicWriter1C.java':'''package com.particlesdevs.photoncamera.m9.export;
public final class MonoDiagnosticPublicWriter1C {
 public static boolean write(android.content.Context c,java.nio.file.Path p,byte[] b){return false;}
 public static org.json.JSONObject snapshotJson(){return new org.json.JSONObject();}}
'''
    }
    paths=[]
    for rel,source in sources.items():
        f=p/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_text(source);paths.append(str(f))
    subprocess.run(['javac','-cp',str(jar),'-d',str(p/'classes')]+paths,check=True)
    cp=str(p/'classes')+':'+str(jar)
    commands=[
        ['java','-cp',cp,'com.particlesdevs.photoncamera.m9.export.ReceiptRecoveryTest',str(p/'recovery')],
        ['java','-cp',cp,'com.particlesdevs.photoncamera.m9.ResetIsolationTest',str(p/'reset'),'first'],
        ['java','-cp',cp,'com.particlesdevs.photoncamera.m9.ResetIsolationTest',str(p/'reset'),'restart']
    ]
    output=[]
    for command in commands:
        result=subprocess.run(command,check=True,capture_output=True,text=True,timeout=60)
        print(result.stdout,end='');output.append(result.stdout)
report={
    'status':'PASS',
    'revision':'MONOOUTPUT1G_RECEIPTHYGIENE1A',
    'actualGeneratedStoreCompiled':True,
    'actualGeneratedDiagnosticSpoolCompiled':True,
    'realFilesystemRecoveryTest':True,
    'resetInTwoSeparateJavaProcessesTested':True,
    'androidContextAndPublicDiagnosticTransportMocked':True,
    'pendingDngBytesAndPublicPhotographsPreserved':True,
    'frozenSourceFileCount':proof['frozenSourceFileCount'],
    'hostOutput':output,
    'phoneValidationRequired':True
}
(root/'MONORECEIPTHYGIENE1A_TEST_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
