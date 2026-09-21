package com.particlesdevs.photoncamera.m9.export;
import android.content.*;
import android.os.Environment;
import androidx.documentfile.provider.DocumentFile;
import com.anggrayudi.storage.file.DocumentFileCompat;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.*;

/** Executes the actual Android-facing writer with filesystem-backed provider mocks. */
public final class PublisherTest {
    static int assertions,scenarios;
    static void yes(boolean v){assertions++;if(!v)throw new AssertionError("publisher "+assertions);}
    static final byte[] DATA=new byte[100003];static{new Random(211).nextBytes(DATA);}
    static final class Env implements AutoCloseable {
        final Path dir,root,output;final Context context;final AtomicLong clock=new AtomicLong(1700000000000L);
        MonoDngSpool1B spool;
        Env(Path dir)throws Exception {
            this.dir=dir;root=dir.resolve("private");Environment.root=dir.resolve("external").toFile();
            output=Environment.root.toPath().resolve("DCIM/PhotonCamera/Raw/image_MONO_LINEAR1A.dng");Files.createDirectories(output.getParent());
            context=new Context();ContentResolver.reset();DocumentFile.reset();DocumentFileCompat.enabled=true;open();
        }
        void open()throws Exception {
            spool=new MonoDngSpool1B(root,MonoDngSpool1B.Policy.normal(),clock::get,()->10L<<30,
                    new MonoDngPublicWriter1B(context),p->true);spool.recover();
        }
        void stage()throws Exception{spool.stage(output,"{}",DATA.length+1000L,o->{o.write(DATA);return DATA.length;});}
        Properties state(){return spool.snapshots().get(0);}
        String status(){return state().getProperty("status");}
        void retry(){clock.addAndGet(60001);spool.pump();}
        public void close()throws Exception{spool.close();}
    }
    static void pass(String name){scenarios++;System.out.println("PASS "+name);}
    public static void main(String[] args)throws Exception {
        Path base=Paths.get(args[0]);
        try(Env e=new Env(base.resolve("saf"))) {
            e.stage();e.spool.pump();yes(e.status().equals("exported"));yes(Arrays.equals(DATA,Files.readAllBytes(e.output)));
            yes(ContentResolver.opens==1);yes(DocumentFile.creates==1);yes(DocumentFile.renames==1);
            yes(ContentResolver.lastMode.equals("rwt"));yes(e.state().getProperty("publicTransport").startsWith("SAF_"));
            yes(e.state().containsKey("publicResolveMs"));yes(e.state().containsKey("publicCopyAndFlushMs"));
            yes(e.state().containsKey("publicCloseMs"));yes(e.state().containsKey("publicFinalVerifyMs"));
            pass("actual_SAF_writer_verified_temporary_rename_and_final_readback");
        }
        try(Env e=new Env(base.resolve("partial"))) {
            e.stage();ContentResolver.failAfter=137;e.spool.pump();yes(e.status().equals("publication_retry_pending"));yes(!Files.exists(e.output));
            yes(e.state().getProperty("publicWriteCompleted").equals("false"));yes(DocumentFile.creates==1);
            e.retry();yes(e.status().equals("exported"));yes(DocumentFile.creates==1);yes(ContentResolver.opens==2);
            yes(Arrays.equals(DATA,Files.readAllBytes(e.output)));pass("actual_SAF_partial_write_reuses_same_temporary_file");
        }
        try(Env e=new Env(base.resolve("close"))) {
            e.stage();ContentResolver.failCloses=1;e.spool.pump();yes(e.status().equals("publication_retry_pending"));yes(!Files.exists(e.output));
            e.retry();yes(e.status().equals("exported"));yes(ContentResolver.opens==1);yes(e.state().getProperty("publicTemporaryReused").equals("true"));
            pass("close_failure_never_reported_as_success_then_verified_temporary_reused");
        }
        try(Env e=new Env(base.resolve("permission"))) {
            e.stage();ContentResolver.denyWrite=true;e.spool.pump();yes(e.status().equals("publication_retry_pending"));
            yes(!Files.exists(e.output));e.spool.close();ContentResolver.denyWrite=false;e.open();e.spool.pump();
            yes(e.status().equals("exported"));yes(Arrays.equals(DATA,Files.readAllBytes(e.output)));
            yes(DocumentFile.creates==1);pass("permission_loss_retry_survives_store_restart");
        }
        try(Env e=new Env(base.resolve("rename"))) {
            e.stage();DocumentFile.failRenames=1;e.spool.pump();yes(e.status().equals("publication_retry_pending"));yes(!Files.exists(e.output));
            e.retry();yes(e.status().equals("exported"));yes(ContentResolver.opens==1);yes(DocumentFile.creates==1);
            pass("rename_failure_retains_verified_payload_and_retries_without_reencoding");
        }
        try(Env e=new Env(base.resolve("after_rename"))) {
            e.stage();ContentResolver.failReadsAfterRename=1;e.spool.pump();yes(Files.exists(e.output));yes(e.status().equals("publication_retry_pending"));
            int opened=ContentResolver.opens,created=DocumentFile.creates;e.spool.close();e.open();e.spool.pump();
            yes(e.status().equals("exported"));yes(ContentResolver.opens==opened);yes(DocumentFile.creates==created);
            yes(e.state().getProperty("publicAlreadyComplete").equals("true"));pass("restart_after_rename_before_receipt_recognizes_exact_final_file");
        }
        try(Env e=new Env(base.resolve("conflict"))) {
            byte[] other={7,8,9};Files.write(e.output,other);e.stage();e.spool.pump();
            yes(e.status().equals("publication_conflict_private_retained"));yes(Arrays.equals(other,Files.readAllBytes(e.output)));
            yes(ContentResolver.opens==0);yes(e.spool.admission().pendingJobs==1);pass("preexisting_different_final_never_deleted_or_overwritten");
        }
        try(Env e=new Env(base.resolve("direct"))) {
            DocumentFileCompat.enabled=false;e.stage();e.spool.pump();yes(e.status().equals("exported"));
            yes(e.state().getProperty("publicTransport").startsWith("direct_"));yes(Arrays.equals(DATA,Files.readAllBytes(e.output)));
            yes(ContentResolver.opens==0);pass("direct_path_fallback_verified_and_no_replacement");
        }
        try(Env e=new Env(base.resolve("blocked_readback"))) {
            e.stage();ContentResolver.denyRead=true;e.spool.pump();yes(e.status().equals("publication_retry_pending"));yes(!Files.exists(e.output));
            ContentResolver.denyRead=false;e.retry();yes(e.status().equals("exported"));yes(ContentResolver.opens==1);
            pass("unverifiable_public_file_is_not_called_exported");
        }
        System.out.println("MONOOUTPUT1B_PUBLISHER_PASS scenarios="+scenarios+" assertions="+assertions+" Android_provider=filesystem_mock");
    }
}
