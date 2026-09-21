package com.particlesdevs.photoncamera.m9.export;

import android.content.Context;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
import androidx.documentfile.provider.DocumentFile;
import java.io.FileNotFoundException;
import java.io.IOException;
import java.util.*;

/** MONOOUTPUT1C_CURSORQUERY: one projected cursor, never listFiles/getName per child.
 * No document-ID path construction, provider-specific selection, or negative-result cache.
 * Partial/failed/ambiguous listings fail closed; absence is returned only after complete traversal.
 */
public final class MonoSafQuery1C {
    public static final String REVISION="MONOOUTPUT1C_CURSORQUERY";
    private static final String[] PROJECTION={DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,DocumentsContract.Document.COLUMN_MIME_TYPE,
            DocumentsContract.Document.COLUMN_SIZE};
    private MonoSafQuery1C() {}

    public static final class Entry {
        public final Uri uri; public final String id,name,mime; public final long size;
        private Entry(Uri uri,String id,String name,String mime,long size) {
            this.uri=uri;this.id=id;this.name=name;this.mime=mime;this.size=size;
        }
        public boolean isDirectory(){return DocumentsContract.Document.MIME_TYPE_DIR.equals(mime);}
    }
    public static final class Lookup {
        private final Map<String,Entry> hits; public final long rows,elapsedNs;
        Lookup(Map<String,Entry> hits,long rows,long elapsedNs) {
            this.hits=Collections.unmodifiableMap(new HashMap<>(hits));this.rows=rows;this.elapsedNs=elapsedNs;
        }
        public Entry get(String name){return hits.get(name);}
    }
    public static void validName(String name) throws IOException {
        if(name==null||name.isEmpty()||name.equals(".")||name.equals("..")||name.indexOf('/')>=0||name.indexOf('\0')>=0)
            throw new IOException("invalid_document_display_name");
    }
    public static Lookup find(Context context,DocumentFile parent,String... names) throws IOException {
        if(context==null||parent==null)throw new IOException("query_context_or_directory_missing");
        Set<String> wanted=new HashSet<>();for(String name:names){validName(name);wanted.add(name);}
        Uri parentUri=parent.getUri();
        if(!"content".equals(parentUri.getScheme()))throw new IOException("not_a_document_provider_uri");
        boolean tree=DocumentsContract.isTreeUri(parentUri);
        String parentId=DocumentsContract.getDocumentId(parentUri);
        Uri children=tree?DocumentsContract.buildChildDocumentsUriUsingTree(parentUri,parentId):
                DocumentsContract.buildChildDocumentsUri(parentUri.getAuthority(),parentId);
        Map<String,Entry> hits=new HashMap<>();long count=0,started=System.nanoTime();
        try(Cursor c=context.getContentResolver().query(children,PROJECTION.clone(),null,null,null)) {
            requireComplete(c);
            int[] columns=columns(c);
            while(c.moveToNext()) {
                count++;
                String id=required(c,columns[0]),name=required(c,columns[1]);
                // All rows supply identity/name in this one query. No per-row provider access.
                if(!wanted.contains(name))continue;
                String mime=required(c,columns[2]);long size=c.isNull(columns[3])?-1:c.getLong(columns[3]);
                Uri uri=tree?DocumentsContract.buildDocumentUriUsingTree(parentUri,id):
                        DocumentsContract.buildDocumentUri(parentUri.getAuthority(),id);
                Entry previous=hits.put(name,new Entry(uri,id,name,mime,size));
                if(previous!=null&&!previous.id.equals(id))throw new IOException("ambiguous_document_display_name:"+name);
            }
            // A lazy provider can change loading/error extras while its cursor is being traversed.
            requireComplete(c);
        } catch(SecurityException denied) {throw denied;}
        catch(IOException error) {throw error;}
        catch(RuntimeException error) {throw new IOException("document_children_query_failed",error);}
        return new Lookup(hits,count,System.nanoTime()-started);
    }
    /** A known returned URI is queried directly, not rediscovered by scanning its parent. */
    public static Entry read(Context context,Uri uri) throws IOException {
        if(uri==null)throw new IOException("provider_returned_null_uri");
        try(Cursor c=context.getContentResolver().query(uri,PROJECTION.clone(),null,null,null)) {
            requireComplete(c);int[] cols=columns(c);
            if(!c.moveToNext())throw new FileNotFoundException("document_metadata_missing:"+uri);
            String id=required(c,cols[0]),name=required(c,cols[1]),mime=required(c,cols[2]);
            long size=c.isNull(cols[3])?-1:c.getLong(cols[3]);
            if(!id.equals(DocumentsContract.getDocumentId(uri)))throw new IOException("document_id_mismatch");
            if(c.moveToNext())throw new IOException("ambiguous_single_document_metadata");
            requireComplete(c);return new Entry(uri,id,name,mime,size);
        } catch(SecurityException denied) {throw denied;}
        catch(IOException error) {throw error;}
        catch(RuntimeException error) {throw new IOException("document_metadata_query_failed",error);}
    }
    private static int[] columns(Cursor c) throws IOException {
        int[] cols=new int[PROJECTION.length];
        for(int i=0;i<cols.length;i++){cols[i]=c.getColumnIndex(PROJECTION[i]);if(cols[i]<0)throw new IOException("document_query_missing_column:"+PROJECTION[i]);}
        return cols;
    }
    private static String required(Cursor c,int col) throws IOException {
        String value=c.getString(col);if(value==null||value.isEmpty())throw new IOException("document_query_missing_identity");return value;
    }
    private static void requireComplete(Cursor c) throws IOException {
        if(c==null)throw new IOException("document_query_null_cursor");
        Bundle extras=c.getExtras();
        if(extras!=null&&(extras.getBoolean(DocumentsContract.EXTRA_LOADING,false)||extras.getString(DocumentsContract.EXTRA_ERROR)!=null))
            throw new IOException("document_query_incomplete_or_error");
    }
}
