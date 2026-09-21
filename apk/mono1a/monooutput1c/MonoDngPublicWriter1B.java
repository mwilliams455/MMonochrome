package com.particlesdevs.photoncamera.m9.export;

import android.content.Context;
import android.os.Environment;
import android.net.Uri;
import android.provider.DocumentsContract;
import androidx.documentfile.provider.DocumentFile;
import com.anggrayudi.storage.file.DocumentFileCompat;
import com.anggrayudi.storage.file.DocumentFileType;
import com.anggrayudi.storage.file.StorageId;
import java.io.*;
import java.nio.file.*;

/** One publication lane, using a unique temporary sibling and verified final bytes.
 * Never deletes/replaces a pre-existing final file with different contents. The private payload
 * remains authoritative through permission loss, provider errors, partial writes and restarts.
 */
public final class MonoDngPublicWriter1B implements MonoDngSpool1B.Publisher {
    private final Context context;
    private String cachedParent;
    private DocumentFile cachedDirectory;
    public MonoDngPublicWriter1B(Context context){this.context=context.getApplicationContext();}
    @Override public void publish(MonoDngSpool1B.Job job)throws Exception {
        long start=System.nanoTime();
        job.checkpoint("publicationLookupRevision",MonoSafQuery1C.REVISION,
                "publicChildQueryCount","0","publicChildRowsScanned","0","publicMetadataQueryCount","0",
                "publicLookupStrategy","fresh_projected_cursor_no_per_child_metadata_queries",
                "currentOperation","resolve_public_directory");
        DocumentFile directory=directory(job.output().getParent());job.metric("publicResolveMs",start);
        if(directory!=null&&"content".equals(directory.getUri().getScheme())){job.checkpoint("publicTransport","SAF_cursor_query_verified_temporary_rename");viaSaf(job,directory);}
        else {job.checkpoint("publicTransport","direct_verified_temporary_rename");viaDirect(job);}
    }
    private DocumentFile directory(Path parent) throws Exception {
        if(parent==null)throw new IOException("public_parent_missing");
        String absolute=parent.toString();
        if(absolute.equals(cachedParent)&&cachedDirectory!=null&&cachedDirectory.exists())return cachedDirectory;
        cachedParent=null;cachedDirectory=null;
        String root=Environment.getExternalStorageDirectory().getAbsolutePath();
        if(!absolute.startsWith(root+"/"))return null;
        String relative=absolute.substring(root.length()+1);
        DocumentFile folder=DocumentFileCompat.fromSimplePath(context,StorageId.PRIMARY,relative,DocumentFileType.FOLDER,true);
        if(folder!=null&&folder.exists()){cachedParent=absolute;cachedDirectory=folder;return folder;}
        return null;
    }
    private MonoSafQuery1C.Lookup lookup(MonoDngSpool1B.Job j,DocumentFile parent,String prefix,String... names)throws Exception {
        long n=System.nanoTime();
        j.checkpoint("currentOperation",prefix,"publicChildQueryCount",Long.toString(j.number("publicChildQueryCount",0)+1));
        try {
            MonoSafQuery1C.Lookup q=MonoSafQuery1C.find(context,parent,names);
            j.checkpoint(prefix+"Rows",Long.toString(q.rows),"publicChildRowsScanned",Long.toString(j.number("publicChildRowsScanned",0)+q.rows));
            return q;
        } finally {j.metric(prefix+"Ms",n);}
    }
    private MonoSafQuery1C.Entry metadata(MonoDngSpool1B.Job j,Uri uri,String prefix)throws Exception {
        long n=System.nanoTime();
        j.checkpoint("currentOperation",prefix,"publicMetadataQueryCount",Long.toString(j.number("publicMetadataQueryCount",0)+1));
        try{return MonoSafQuery1C.read(context,uri);}finally{j.metric(prefix+"Ms",n);}
    }
    private void viaSaf(MonoDngSpool1B.Job j,DocumentFile parent)throws Exception {
        String name=j.output().getFileName().toString(),temporary=j.get("temporaryName");
        long n=System.nanoTime();
        // One complete query returns both exact names. Never cache a negative result.
        MonoSafQuery1C.Lookup initial=lookup(j,parent,"publicInitialQuery",name,temporary);
        j.metric("publicLookupMs",n);
        MonoSafQuery1C.Entry existing=initial.get(name),temp=initial.get(temporary);
        if(existing!=null) {
            if(existing.isDirectory()||!matches(existing.uri,j))throw new MonoDngSpool1B.Conflict("existing_final_DNG_differs_private_copy_retained");
            j.checkpoint("publicFinalUri",existing.uri.toString(),"publicAlreadyComplete","true");return;
        }
        if(temp==null) {
            n=System.nanoTime();j.checkpoint("currentOperation","create_public_temporary");
            Uri created=DocumentsContract.createDocument(context.getContentResolver(),parent.getUri(),"application/octet-stream",temporary);
            j.metric("publicCreateMs",n);
            temp=metadata(j,created,"publicCreateMetadata");
            if(!temporary.equals(temp.name)||temp.isDirectory())throw new IOException("provider_changed_temporary_name_or_type");
        } else if(temp.isDirectory())throw new MonoDngSpool1B.Conflict("temporary_name_is_directory_private_retained");
        j.checkpoint("publicTemporaryUri",temp.uri.toString());
        // Size is only a hint; verified bytes remain authoritative.
        boolean complete=temp.size==j.number("stagedBytes",-1)&&matches(temp.uri,j);
        if(!complete) {
            n=System.nanoTime();j.checkpoint("currentOperation","open_public_temporary");
            OutputStream out=context.getContentResolver().openOutputStream(temp.uri,"rwt");
            if(out==null)throw new IOException("public_temporary_stream_null");
            try{j.metric("publicOpenMs",n);writeAndClose(j,out);}catch(Exception e){try{out.close();}catch(Exception close){e.addSuppressed(close);}throw e;}
        } else j.checkpoint("publicTemporaryReused","true");
        n=System.nanoTime();j.checkpoint("currentOperation","verify_public_temporary");
        if(!matches(temp.uri,j))throw new IOException("public_temporary_hash_mismatch");j.metric("publicVerifyMs",n);
        // Fresh full query before rename: do not weaken the previous conflict check for speed.
        existing=lookup(j,parent,"publicConflictQuery",name).get(name);
        if(existing!=null) {
            if(existing.isDirectory()||!matches(existing.uri,j))throw new MonoDngSpool1B.Conflict("final_DNG_created_during_publication_private_retained");
            j.checkpoint("publicFinalUri",existing.uri.toString(),"publicAlreadyComplete","true");return;
        }
        n=System.nanoTime();j.checkpoint("currentOperation","rename_public_temporary");
        Uri finalUri=DocumentsContract.renameDocument(context.getContentResolver(),temp.uri,name);
        j.metric("publicRenameMs",n);
        MonoSafQuery1C.Entry finalDoc=metadata(j,finalUri,"publicFinalMetadata");
        if(!name.equals(finalDoc.name)||finalDoc.isDirectory())throw new IOException("provider_changed_final_name_or_type");
        j.checkpoint("publicFinalUri",finalDoc.uri.toString(),"publicFilenameVerified","true");
        n=System.nanoTime();j.checkpoint("currentOperation","verify_final_public_DNG");
        if(!matches(finalDoc.uri,j))throw new IOException("public_final_hash_mismatch");j.metric("publicFinalVerifyMs",n);
    }
    private boolean matches(Uri uri,MonoDngSpool1B.Job j)throws Exception {
        try(InputStream in=context.getContentResolver().openInputStream(uri)) {
            if(in==null)throw new IOException("public_verification_stream_null");
            try{return MonoDngSpool1B.hashStream(in,j.number("stagedBytes",-1)).equals(j.get("payloadSha256"));}
            catch(IOException e){if(e.getMessage()!=null&&e.getMessage().startsWith("public_length_"))return false;throw e;}
        }
    }
    private void viaDirect(MonoDngSpool1B.Job j)throws Exception {
        Path output=j.output();Files.createDirectories(output.getParent());
        if(Files.exists(output)) {
            if(!matches(output,j))throw new MonoDngSpool1B.Conflict("existing_final_DNG_differs_private_copy_retained");
            j.checkpoint("publicAlreadyComplete","true");return;
        }
        Path temp=output.resolveSibling(j.get("temporaryName"));
        if(!Files.exists(temp)||!matches(temp,j)) {
            long n=System.nanoTime();j.checkpoint("currentOperation","open_public_temporary");
            FileOutputStream out=new FileOutputStream(temp.toFile());
            try {j.metric("publicOpenMs",n);writeAndClose(j,out);}catch(Exception e){try{out.close();}catch(Exception close){e.addSuppressed(close);}throw e;}
        } else j.checkpoint("publicTemporaryReused","true");
        long n=System.nanoTime();j.checkpoint("currentOperation","verify_public_temporary");
        if(!matches(temp,j))throw new IOException("public_temporary_hash_mismatch");j.metric("publicVerifyMs",n);
        j.checkpoint("currentOperation","rename_public_temporary");n=System.nanoTime();
        // No REPLACE_EXISTING: never clobber another file. Same-directory move, not a rewrite.
        try{Files.move(temp,output);}catch(FileAlreadyExistsException e){
            if(!matches(output,j))throw new MonoDngSpool1B.Conflict("final_DNG_created_during_publication_private_retained");
        }
        j.metric("publicRenameMs",n);n=System.nanoTime();j.checkpoint("currentOperation","verify_final_public_DNG");
        if(!matches(output,j))throw new IOException("public_final_hash_mismatch");j.metric("publicFinalVerifyMs",n);
    }
    private boolean matches(Path file,MonoDngSpool1B.Job j)throws IOException {
        return Files.size(file)==j.number("stagedBytes",-1)&&MonoDngSpool1B.hashFile(file).equals(j.get("payloadSha256"));
    }
    private static void writeAndClose(MonoDngSpool1B.Job j,OutputStream out)throws Exception {
        Exception failure=null;long start=System.nanoTime();
        try {
            j.checkpoint("currentOperation","copy_public_payload");
            long count=0;byte[] block=new byte[65536];
            try(InputStream in=Files.newInputStream(j.payload())){int n;while((n=in.read(block))!=-1){out.write(block,0,n);count+=n;}}
            if(count!=j.number("stagedBytes",-1))throw new IOException("public_copy_length_mismatch");
            out.flush();if(out instanceof FileOutputStream)((FileOutputStream)out).getFD().sync();
            j.metric("publicCopyAndFlushMs",start);j.checkpoint("currentOperation","close_public_stream");
        }catch(Exception e){failure=e;throw e;}
        finally {
            long closing=System.nanoTime();
            try{out.close();}catch(Exception e){if(failure!=null)failure.addSuppressed(e);else throw e;}
            finally{try{j.metric("publicCloseMs",closing);}catch(Exception e){if(failure!=null)failure.addSuppressed(e);else throw e;}}
        }
    }
}
