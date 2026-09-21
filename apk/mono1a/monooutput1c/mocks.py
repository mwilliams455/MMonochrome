"""Deterministic Android documents-provider stand-ins. IDs deliberately are opaque, not paths."""
stubs={
'android/net/Uri.java':r'''package android.net;
import java.nio.file.*;import java.util.*;
public final class Uri {
 public static boolean defaultTree=true;public final Path path;public final boolean children,tree;private final String id;
 private static final Map<Path,String> ids=new HashMap<>();private static final Map<String,Path> paths=new HashMap<>();
 public Uri(Path p){this(p,false,defaultTree);}
 public Uri(Path p,boolean children,boolean tree){this.path=p.toAbsolutePath().normalize();this.children=children;this.tree=tree;this.id=register(this.path);}
 public static synchronized String register(Path p){p=p.toAbsolutePath().normalize();if(!ids.containsKey(p)){String s="opaque:"+ids.size();ids.put(p,s);paths.put(s,p);}return ids.get(p);}
 public static synchronized Path pathOf(String id){Path p=paths.get(id);if(p==null)throw new IllegalArgumentException("unknown opaque id "+id);return p;}
 public String id(){return id;}public String getScheme(){return "content";}public String getAuthority(){return "mock.documents";}
 public String toString(){return "content://mock.documents/"+(tree?"tree/opaqueTree/":"")+"document/"+id+(children?"/children":"");}
}''',
'android/os/Bundle.java':r'''package android.os;import java.util.*;public class Bundle {
 public final Map<String,Object> map=new HashMap<>();public boolean getBoolean(String k,boolean d){Object v=map.get(k);return v==null?d:(Boolean)v;}
 public String getString(String k){return (String)map.get(k);}
}''',
'android/os/Environment.java':'package android.os;public class Environment {public static java.io.File root;public static java.io.File getExternalStorageDirectory(){return root;}}',
'android/os/Process.java':'package android.os;public class Process {public static final int THREAD_PRIORITY_BACKGROUND=10;public static void setThreadPriority(int p){}}',
'android/content/Context.java':r'''package android.content;public class Context {
 private final ContentResolver r=new ContentResolver();public Context getApplicationContext(){return this;}public ContentResolver getContentResolver(){return r;}
 public java.io.File getFilesDir(){java.io.File p=new java.io.File(android.os.Environment.root.getParentFile(),"appFiles");p.mkdirs();return p;}
}''',
'android/database/Cursor.java':r'''package android.database;import android.os.Bundle;
public interface Cursor extends java.io.Closeable {boolean moveToNext();int getColumnIndex(String name);String getString(int n);long getLong(int n);boolean isNull(int n);Bundle getExtras();void close();}''',
'android/provider/DocumentsContract.java':r'''package android.provider;
import android.content.*;import android.net.Uri;import java.io.*;import java.nio.file.*;import androidx.documentfile.provider.DocumentFile;
public class DocumentsContract {
 public static final String EXTRA_LOADING="loading",EXTRA_ERROR="error";
 public static class Document {public static final String COLUMN_DOCUMENT_ID="document_id",COLUMN_DISPLAY_NAME="_display_name",COLUMN_MIME_TYPE="mime_type",COLUMN_SIZE="_size",MIME_TYPE_DIR="vnd.android.document/directory";}
 public static boolean isTreeUri(Uri u){return u.tree;}public static String getDocumentId(Uri u){return u.id();}
 public static Uri buildChildDocumentsUriUsingTree(Uri u,String id){return new Uri(Uri.pathOf(id),true,true);}
 public static Uri buildChildDocumentsUri(String authority,String id){return new Uri(Uri.pathOf(id),true,false);}
 public static Uri buildDocumentUriUsingTree(Uri u,String id){return new Uri(Uri.pathOf(id),false,true);}
 public static Uri buildDocumentUri(String authority,String id){return new Uri(Uri.pathOf(id),false,false);}
 public static Uri createDocument(ContentResolver r,Uri parent,String mime,String name)throws IOException {
  if(ContentResolver.denyWrite)throw new IOException("create_permission_denied");
  DocumentFile f=new DocumentFile(parent.path).createFile(mime,ContentResolver.alterCreateName?name+".unexpected":name);
  if(f==null)throw new IOException("create_failed");return f.getUri();
 }
 public static Uri renameDocument(ContentResolver r,Uri u,String name)throws IOException {
  DocumentFile f=new DocumentFile(u.path);if(!f.renameTo(ContentResolver.alterRenameName?name+".unexpected":name))throw new IOException("rename_failed");return f.getUri();
 }
}''',
'android/content/ContentResolver.java':r'''package android.content;
import android.net.Uri;import android.os.Bundle;import android.database.Cursor;import android.provider.DocumentsContract;
import java.io.*;import java.nio.file.*;import java.util.*;import java.util.stream.*;import androidx.documentfile.provider.DocumentFile;
public class ContentResolver {
 public static int opens,reads,failAfter,failCloses,failReadsAfterRename;public static boolean denyRead,denyWrite;public static String lastMode;
 public static int childQueries,metadataQueries,closedCursors,openedCursors,noiseRows,throwAtRow,conflictOnQuery;
 public static boolean nullCursor,omitName,loading,loadingAfter,queryDenied,nullSize,reorder,alterCreateName,alterRenameName;
 public static String duplicateName,errorExtra;public static Path conflictPath;
 public static void reset(){opens=reads=failCloses=failReadsAfterRename=0;failAfter=-1;denyRead=denyWrite=false;lastMode="";
 childQueries=metadataQueries=closedCursors=openedCursors=noiseRows=conflictOnQuery=0;throwAtRow=-1;
 nullCursor=omitName=loading=loadingAfter=queryDenied=nullSize=reorder=alterCreateName=alterRenameName=false;duplicateName=errorExtra=null;conflictPath=null;Uri.defaultTree=true;}
 public OutputStream openOutputStream(Uri uri,String mode)throws IOException {
  lastMode=mode;if(denyWrite)throw new IOException("injected_permission_denied");opens++;
  OutputStream raw=Files.newOutputStream(uri.path);return new OutputStream(){long count;
   public void write(int b)throws IOException{write(new byte[]{(byte)b},0,1);}public void write(byte[] b,int off,int n)throws IOException {
    if(failAfter>=0&&count+n>failAfter){int partial=(int)Math.max(0,failAfter-count);raw.write(b,off,partial);failAfter=-1;throw new IOException("injected_partial_write");}
    raw.write(b,off,n);count+=n;}
   public void flush()throws IOException{raw.flush();}
   public void close()throws IOException{raw.close();if(failCloses>0){failCloses--;throw new IOException("injected_close_error");}}
  };
 }
 public InputStream openInputStream(Uri uri)throws IOException {
  if(denyRead)throw new IOException("injected_readback_denied");
  if(failReadsAfterRename>0&&DocumentFile.renames>0){failReadsAfterRename--;throw new IOException("injected_failure_after_rename");}
  reads++;return Files.newInputStream(uri.path);
 }
 public Cursor query(Uri uri,String[] projection,String selection,String[] args,String order) {
  if(selection!=null||args!=null)throw new AssertionError("provider selection not portable");
  if(uri.children)childQueries++;else metadataQueries++;
  if(queryDenied)throw new SecurityException("query_permission_denied");if(nullCursor)return null;
  List<String> cols=new ArrayList<>(Arrays.asList(projection));if(omitName)cols.remove("_display_name");if(reorder)Collections.reverse(cols);
  List<Map<String,Object>> rows=new ArrayList<>();
  try {
   if(uri.children) {
    if(conflictOnQuery==childQueries&&conflictPath!=null)Files.write(conflictPath,new byte[]{7,8,9});
    try(Stream<Path> files=Files.list(uri.path)){for(Path p:files.sorted().collect(Collectors.toList()))rows.add(row(p,p.getFileName().toString()));}
    for(int i=0;i<noiseRows;i++)rows.add(row(uri.path.resolve("__noise"+i),"noise_'_"+i+".json"));
    if(duplicateName!=null)rows.add(row(uri.path.resolve("__duplicateOtherId"),duplicateName));
   }else if(Files.exists(uri.path))rows.add(row(uri.path,uri.path.getFileName().toString()));
  }catch(IOException e){throw new IllegalStateException(e);}
  openedCursors++;return new Cursor(){int i=-1;boolean closed;
   public boolean moveToNext(){i++;if(throwAtRow>=0&&i==throwAtRow)throw new IllegalStateException("cursor_injected_mid_traversal_failure");return i<rows.size();}
   public int getColumnIndex(String s){return cols.indexOf(s);}private Object get(int col){return rows.get(i).get(cols.get(col));}
   public String getString(int col){Object x=get(col);return x==null?null:x.toString();}public long getLong(int col){return ((Number)get(col)).longValue();}public boolean isNull(int col){return get(col)==null;}
   public Bundle getExtras(){Bundle b=new Bundle();if(loading||(loadingAfter&&i>=rows.size()))b.map.put("loading",true);if(errorExtra!=null)b.map.put("error",errorExtra);return b;}
   public void close(){if(!closed){closed=true;closedCursors++;}}
  };
 }
 private static Map<String,Object> row(Path p,String name)throws IOException {
  Map<String,Object> m=new HashMap<>();m.put("document_id",Uri.register(p));m.put("_display_name",name);
  m.put("mime_type",Files.isDirectory(p)?DocumentsContract.Document.MIME_TYPE_DIR:"application/octet-stream");
  m.put("_size",nullSize?null:(Files.exists(p)&&!Files.isDirectory(p)?Files.size(p):0L));return m;
 }
}''',
'androidx/documentfile/provider/DocumentFile.java':r'''package androidx.documentfile.provider;
import android.net.Uri;import java.nio.file.*;
public class DocumentFile {
 public static int creates,renames,failRenames,legacyFindCalls,nameCalls;private Path p;
 public DocumentFile(Path p){this.p=p;}public static void reset(){creates=renames=failRenames=legacyFindCalls=nameCalls=0;}
 public boolean exists(){return Files.exists(p);}public String getName(){nameCalls++;return p.getFileName().toString();}
 public Uri getUri(){return new Uri(p);}public long length(){try{return Files.size(p);}catch(Exception e){return 0;}}
 public DocumentFile findFile(String n){legacyFindCalls++;throw new AssertionError("legacy per-child findFile is forbidden");}
 public DocumentFile createFile(String mime,String n){try{Path x=p.resolve(n);Files.createFile(x);creates++;return new DocumentFile(x);}catch(Exception e){return null;}}
 public boolean renameTo(String n){if(failRenames>0){failRenames--;return false;}try{p=Files.move(p,p.resolveSibling(n));renames++;return true;}catch(Exception e){return false;}}
}''',
'com/anggrayudi/storage/file/DocumentFileType.java':'package com.anggrayudi.storage.file;public class DocumentFileType {public static final int FOLDER=1;}',
'com/anggrayudi/storage/file/StorageId.java':'package com.anggrayudi.storage.file;public class StorageId {public static final String PRIMARY="primary";}',
'com/anggrayudi/storage/file/DocumentFileCompat.java':r'''package com.anggrayudi.storage.file;import android.content.Context;import android.os.Environment;import androidx.documentfile.provider.DocumentFile;
public class DocumentFileCompat {public static boolean enabled=true;public static DocumentFile fromSimplePath(Context c,String s,String rel,int t,boolean create){if(!enabled)return null;return new DocumentFile(Environment.root.toPath().resolve(rel));}}''',
'org/json/JSONObject.java':r'''package org.json;import java.util.*;public class JSONObject {
 private final Map<String,Object> m=new HashMap<>();public JSONObject(){}public JSONObject(String text){}
 public JSONObject put(String key,Object value){m.put(key,value);return this;}public Object get(String key){return m.get(key);}public long getLong(String key){return ((Number)m.get(key)).longValue();}
 public String toString(int i){return m.toString();}public String toString(){return m.toString();}
}''',
'org/json/JSONArray.java':'package org.json;public class JSONArray {public JSONArray put(Object x){return this;}}',
'com/particlesdevs/photoncamera/app/PhotonCamera.java':'package com.particlesdevs.photoncamera.app;import android.content.Context;public class PhotonCamera {public static Context context;public static Context getAppContext(){return context;}}',
'com/particlesdevs/photoncamera/util/Log.java':r'''package com.particlesdevs.photoncamera.util;public class Log {public static void d(String t,String m){}public static void w(String t,String m){}public static void e(String t,String m,Throwable e){}}''',
'com/particlesdevs/photoncamera/util/SimpleStorageHelper.java':'package com.particlesdevs.photoncamera.util;public class SimpleStorageHelper {}'
}
