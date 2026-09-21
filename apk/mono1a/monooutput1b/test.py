#!/usr/bin/env python3
"""Real spool, writer and Android-facing publisher tests; Android provider is filesystem-mocked."""
from pathlib import Path
import hashlib,json,subprocess,sys,tempfile,re
import numpy as np
import tifffile
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
proof=json.loads((root/'MONOOUTPUT1B_ISOLATION.json').read_text())
for rel,h in proof['frozen'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==h,rel
for rel,h in proof['changed'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==h['after'],rel
for rel,h in proof['new'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==h,rel
stubs={
'android/net/Uri.java':'''package android.net;public final class Uri {public final java.nio.file.Path path;public Uri(java.nio.file.Path p){path=p;}public String toString(){return path.toUri().toString();}}''',
'android/os/Environment.java':'''package android.os;public class Environment {public static java.io.File root;public static java.io.File getExternalStorageDirectory(){return root;}}''',
'android/content/Context.java':'''package android.content;public class Context {private final ContentResolver r=new ContentResolver();public Context getApplicationContext(){return this;}public ContentResolver getContentResolver(){return r;}}''',
'android/content/ContentResolver.java':r'''package android.content;
import android.net.Uri;import java.io.*;import java.nio.file.*;import androidx.documentfile.provider.DocumentFile;
public class ContentResolver {
 public static int opens,reads,failAfter,failCloses,failReadsAfterRename;public static boolean denyRead,denyWrite;public static String lastMode;
 public static void reset(){opens=reads=failCloses=failReadsAfterRename=0;failAfter=-1;denyRead=denyWrite=false;lastMode="";}
 public OutputStream openOutputStream(Uri uri,String mode)throws IOException {
  lastMode=mode;if(denyWrite)throw new IOException("injected_permission_denied");opens++;
  OutputStream raw=Files.newOutputStream(uri.path);return new OutputStream(){long count;
   public void write(int b)throws IOException{write(new byte[]{(byte)b},0,1);}
   public void write(byte[] b,int off,int n)throws IOException {
    if(failAfter>=0&&count+n>failAfter){int partial=(int)Math.max(0,failAfter-count);raw.write(b,off,partial);failAfter=-1;throw new IOException("injected_partial_write");}
    raw.write(b,off,n);count+=n;
   }
   public void flush()throws IOException{raw.flush();}
   public void close()throws IOException{raw.close();if(failCloses>0){failCloses--;throw new IOException("injected_close_error");}}
  };
 }
 public InputStream openInputStream(Uri uri)throws IOException {
  if(denyRead)throw new IOException("injected_readback_denied");
  if(failReadsAfterRename>0&&DocumentFile.renames>0){failReadsAfterRename--;throw new IOException("injected_failure_after_rename");}
  reads++;return Files.newInputStream(uri.path);
 }
}''',
'androidx/documentfile/provider/DocumentFile.java':r'''package androidx.documentfile.provider;
import android.net.Uri;import java.nio.file.*;public class DocumentFile {
 public static int creates,renames,failRenames;private Path p;
 public DocumentFile(Path p){this.p=p;}public static void reset(){creates=renames=failRenames=0;}
 public boolean exists(){return Files.exists(p);}public String getName(){return p.getFileName().toString();}
 public Uri getUri(){return new Uri(p);}public long length(){try{return Files.size(p);}catch(Exception e){return 0;}}
 public DocumentFile findFile(String n){Path x=p.resolve(n);return Files.exists(x)?new DocumentFile(x):null;}
 public DocumentFile createFile(String mime,String n){try{Path x=p.resolve(n);Files.createFile(x);creates++;return new DocumentFile(x);}catch(Exception e){return null;}}
 public boolean renameTo(String n){if(failRenames>0){failRenames--;return false;}try{p=Files.move(p,p.resolveSibling(n));renames++;return true;}catch(Exception e){return false;}}
}''',
'com/anggrayudi/storage/file/DocumentFileType.java':'package com.anggrayudi.storage.file;public class DocumentFileType {public static final int FOLDER=1;}',
'com/anggrayudi/storage/file/StorageId.java':'package com.anggrayudi.storage.file;public class StorageId {public static final String PRIMARY="primary";}',
'com/anggrayudi/storage/file/DocumentFileCompat.java':r'''package com.anggrayudi.storage.file;import android.content.Context;import android.os.Environment;import androidx.documentfile.provider.DocumentFile;
public class DocumentFileCompat {public static boolean enabled=true;public static DocumentFile fromSimplePath(Context c,String s,String rel,int t,boolean create){if(!enabled)return null;return new DocumentFile(Environment.root.toPath().resolve(rel));}}'''
}
logs=[]
with tempfile.TemporaryDirectory() as temp:
    temp=Path(temp);pkg='com/particlesdevs/photoncamera/m9/export'
    for rel,s in stubs.items():p=temp/rel;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(s)
    for n in ['MonoDngSpool1B.java','MonoDngPublicWriter1B.java','MonoDngWriter1A.java','MonoLinearPlane1A.java']:
        p=temp/pkg/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes((root/'app/src/main/java'/pkg/n).read_bytes())
    for n in ['SpoolTest.java','PublisherTest.java']:(temp/pkg/n).write_bytes((here/n).read_bytes())
    subprocess.run(['javac','--release','17','-d',str(temp/'classes')]+[str(p) for p in temp.rglob('*.java')],check=True)
    for name in ['SpoolTest','PublisherTest']:
        p=subprocess.run(['java','-cp',str(temp/'classes'),'com.particlesdevs.photoncamera.m9.export.'+name,str(temp/name)],text=True,capture_output=True)
        print(p.stdout,end='');print(p.stderr,end='',file=sys.stderr);p.check_returncode();logs.append(p.stdout)
    reference=temp/'SpoolTest/reference_12mp.dng';transport=temp/'SpoolTest/transport_12mp.dng'
    assert reference.read_bytes()==transport.read_bytes()
    with tifffile.TiffFile(transport) as t:
        raw=t.pages[0].pages[0];samples=raw.asarray()
        assert samples.shape==(4096,3072) and samples.dtype==np.uint16
        assert int(raw.photometric)==34892 and raw.samplesperpixel==1
        assert 33422 not in raw.tags and 50721 not in raw.tags
    with tifffile.TiffFile(reference) as t:assert np.array_equal(samples,t.pages[0].pages[0].asarray())
    rows=np.arange(3072,dtype=np.int64)[:,None];cols=np.arange(4096,dtype=np.int64)[None,:]
    w=np.array([.65497077,.7578125,.042704627],np.float32).astype(float)
    expected=np.floor(((cols*13+rows*19)%65536*w[0]+(cols*17+rows*7)%65536*w[1]+(cols*23+rows*11)%65536*w[2])/sum(w)+.5).astype(np.uint16)
    expected=np.rot90(expected,-1)
    assert np.array_equal(samples,expected),'independent sample oracle'
    print('MONOOUTPUT1B DNG PASS 12582912 exact 16-bit samples; full file byte-identical')
    report={'revision':'MONOOUTPUT1B_DURABLE_EXPORT','status':'PASS','scope':'real_production_spool_and_public_writer_filesystem_Android_provider_mocks_not_phone',
            'scenarios':sum(int(re.search(r'_PASS scenarios=(\d+)',s)[1]) for s in logs),
            'assertions':sum(int(re.search(r'assertions=(\d+)',s)[1]) for s in logs),
            'exactDngSampleCount':int(samples.size),'byteIdenticalDngWriterOutput':True,'dngSha256':hashlib.sha256(transport.read_bytes()).hexdigest(),
            'frozenRuntimeFileCount':len(proof['frozen']),'phoneValidated':False}
    (root/'MONOOUTPUT1B_TEST_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
