package com.particlesdevs.photoncamera.m9.export;

import android.content.Context;
import android.net.Uri;
import android.os.Environment;
import android.provider.DocumentsContract;
import androidx.documentfile.provider.DocumentFile;
import com.anggrayudi.storage.file.DocumentFileCompat;
import com.anggrayudi.storage.file.DocumentFileType;
import com.anggrayudi.storage.file.StorageId;
import java.io.*;
import java.nio.file.*;
import java.util.concurrent.atomic.AtomicLong;
import org.json.JSONObject;

/** Diagnostic-only publisher. Preserve upstream payload, scheduling and private staging.
 * One projected child query per SAF write; update known JSON URI in place, never delete first.
 * Successful close AND exact readback required. Failed publication retains upstream private stage.
 */
public final class MonoDiagnosticPublicWriter1C {
    private static final ThreadLocal<MonoDiagnosticPublicWriter1C> LANES=new ThreadLocal<>();
    private static final AtomicLong WRITES=new AtomicLong(),FAILURES=new AtomicLong(),QUERIES=new AtomicLong(),ROWS=new AtomicLong();
    private static final AtomicLong LAST_QUERY_NS=new AtomicLong(),MAX_QUERY_NS=new AtomicLong(),LAST_WRITE_NS=new AtomicLong();
    private static final AtomicLong REUSED=new AtomicLong(),CREATED=new AtomicLong(),DIRECT=new AtomicLong();
    private static volatile String lastError="";
    private final Context context;private DocumentFile cachedDirectory;private String cachedParent;
    public MonoDiagnosticPublicWriter1C(Context context){this.context=context.getApplicationContext();}

    public static boolean write(Context context,Path path,byte[] bytes) {
        long n=System.nanoTime();
        try {
            if(context==null||path==null||bytes==null)throw new IOException("diagnostic_context_path_or_payload_missing");
            Context app=context.getApplicationContext();
            MonoDiagnosticPublicWriter1C writer=LANES.get();
            if(writer==null||writer.context!=app){writer=new MonoDiagnosticPublicWriter1C(app);LANES.set(writer);}
            writer.persist(path,bytes);WRITES.incrementAndGet();lastError="";return true;
        }catch(Exception error){FAILURES.incrementAndGet();lastError=error.toString();return false;}
        finally{LAST_WRITE_NS.set(System.nanoTime()-n);}
    }
    /** Instance API also exercised directly by fault-injection tests. */
    public void persist(Path path,byte[] bytes)throws Exception {
        String name=path.getFileName().toString();MonoSafQuery1C.validName(name);
        DocumentFile parent=directory(path.getParent());
        if(parent==null||!"content".equals(parent.getUri().getScheme())) {
            // Same direct-path capability fallback, never a workaround for an uncertain SAF listing.
            Files.createDirectories(path.getParent());
            try(OutputStream out=Files.newOutputStream(path)){out.write(bytes);out.flush();}
            try(InputStream in=Files.newInputStream(path)){verify(in,bytes);}
            DIRECT.incrementAndGet();return;
        }
        long n=System.nanoTime();MonoSafQuery1C.Lookup query;
        QUERIES.incrementAndGet();
        try{query=MonoSafQuery1C.find(context,parent,name);ROWS.addAndGet(query.rows);}
        finally{long cost=System.nanoTime()-n;LAST_QUERY_NS.set(cost);MAX_QUERY_NS.accumulateAndGet(cost,Math::max);}
        MonoSafQuery1C.Entry entry=query.get(name);
        if(entry==null) {
            Uri created=DocumentsContract.createDocument(context.getContentResolver(),parent.getUri(),"application/json",name);
            entry=MonoSafQuery1C.read(context,created);
            if(!name.equals(entry.name))throw new IOException("provider_changed_diagnostic_name");
            CREATED.incrementAndGet();
        }else REUSED.incrementAndGet();
        if(entry.isDirectory())throw new IOException("diagnostic_name_is_directory");
        // rwt explicitly truncates: a shorter status must not retain bytes from the previous JSON.
        try(OutputStream out=context.getContentResolver().openOutputStream(entry.uri,"rwt")) {
            if(out==null)throw new IOException("diagnostic_output_stream_null");
            out.write(bytes);out.flush();
        }
        try(InputStream in=context.getContentResolver().openInputStream(entry.uri)) {
            if(in==null)throw new IOException("diagnostic_readback_stream_null");verify(in,bytes);
        }
    }
    private DocumentFile directory(Path parent)throws Exception {
        if(parent==null)throw new IOException("diagnostic_parent_missing");
        String absolute=parent.toString();
        if(absolute.equals(cachedParent)&&cachedDirectory!=null&&cachedDirectory.exists())return cachedDirectory;
        cachedDirectory=null;cachedParent=null;
        String root=Environment.getExternalStorageDirectory().getAbsolutePath();
        if(!absolute.startsWith(root+"/"))return null;
        DocumentFile dir=DocumentFileCompat.fromSimplePath(context,StorageId.PRIMARY,absolute.substring(root.length()+1),DocumentFileType.FOLDER,true);
        if(dir!=null&&dir.exists()){cachedParent=absolute;cachedDirectory=dir;return dir;}
        return null;
    }
    private static void verify(InputStream in,byte[] expected)throws IOException {
        byte[] block=new byte[65536];int offset=0,n;
        while((n=in.read(block))!=-1) {
            if(n>expected.length-offset)throw new IOException("diagnostic_readback_length");
            for(int i=0;i<n;i++)if(block[i]!=expected[offset+i])throw new IOException("diagnostic_readback_content");
            offset+=n;
        }
        if(offset!=expected.length)throw new IOException("diagnostic_readback_length");
    }
    public static JSONObject snapshotJson() {
        JSONObject o=new JSONObject();
        try {
            o.put("revision",MonoSafQuery1C.REVISION).put("strategy","fresh_projected_cursor_known_URI_write_and_readback");
            o.put("writes",WRITES.get()).put("failures",FAILURES.get()).put("childQueries",QUERIES.get()).put("childRowsScanned",ROWS.get());
            o.put("lastQueryMs",LAST_QUERY_NS.get()/1e6).put("maxQueryMs",MAX_QUERY_NS.get()/1e6).put("lastWriteMs",LAST_WRITE_NS.get()/1e6);
            o.put("existingUrisReused",REUSED.get()).put("createdDocuments",CREATED.get()).put("directWrites",DIRECT.get()).put("lastError",lastError);
        }catch(Exception ignored){}
        return o;
    }
}
