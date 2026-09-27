package com.particlesdevs.photoncamera.m9.export;

import android.content.Context;
import android.content.ContentResolver;
import android.os.Environment;
import androidx.documentfile.provider.DocumentFile;
import com.anggrayudi.storage.file.DocumentFileCompat;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicLong;

/** Actual publisher + durable job store; mock Android provider has deliberately opaque IDs. */
public final class SaveLookupTest {
    private static int assertions, scenarios;
    private static boolean baseline;
    private static final byte[] DATA = new byte[65539];
    static { new Random(731).nextBytes(DATA); }
    private static void yes(boolean b) { assertions++; if(!b)throw new AssertionError("check " + assertions); }
    private static void equal(Object a,Object b) { yes(Objects.equals(a,b)); }
    private static void pass(String s) { scenarios++; System.out.println("PASS " + s); }
    private static void reset() { ContentResolver.reset(); DocumentFile.reset(); DocumentFileCompat.enabled=true; }
    private static final class Env implements AutoCloseable {
        final Path base,root,out;
        final AtomicLong clock=new AtomicLong(1700000000000L);
        MonoDngSpool1B spool;
        Env(Path p)throws Exception {
            reset();base=p;root=p.resolve("private");out=p.resolve("public/Raw");
            Files.createDirectories(out);Environment.root=p.resolve("public").toFile();open();
        }
        void open()throws Exception {
            spool=new MonoDngSpool1B(root,MonoDngSpool1B.Policy.normal(),clock::get,()->10L<<30,
                    new MonoDngPublicWriter1B(new Context()),p->true);
            spool.recover();
        }
        void reopen()throws Exception { spool.close();clock.addAndGet(61000);open(); }
        void retry() { clock.addAndGet(61000);spool.pump(); }
        void stage(String name)throws Exception {
            spool.stage(output(name),"{}",DATA.length+512L,o->{o.write(DATA);return DATA.length;});
        }
        Path output(String name) { return out.resolve(name+"_MONO_LINEAR1A.dng"); }
        Properties props(String name) { return spool.snapshots().stream()
                .filter(p->output(name).toString().equals(p.getProperty("outputPath"))).findFirst().orElseThrow(); }
        Path job(String name)throws Exception {
            String id=MonoDngSpool1B.hashStream(new ByteArrayInputStream(output(name).toString()
                    .getBytes(java.nio.charset.StandardCharsets.UTF_8)),-1).substring(0,32);
            return root.resolve("job_"+id);
        }
        Path temp(String name) { return out.resolve(props(name).getProperty("temporaryName")); }
        void status(String name,String wanted) { equal(props(name).getProperty("status"),wanted); }
        void retained(String name)throws Exception { yes(Files.isRegularFile(job(name).resolve("payload.dng"))); }
        void exported(String name)throws Exception {
            status(name,"exported");equal(props(name).getProperty("publicReadbackVerified"),"true");
            equal(props(name).getProperty("privatePayloadReleased"),"true");
            yes(Arrays.equals(DATA,Files.readAllBytes(output(name))));
        }
        public void close()throws Exception { spool.close(); }
    }
    public static void main(String[] args)throws Exception {
        Path base=Paths.get(args[0]);Files.createDirectories(base);baseline=args.length>1&&args[1].equals("baseline");
        try(Env e=new Env(base.resolve("fresh"))) {
            ContentResolver.noiseRows=14000;e.stage("fresh");e.spool.pump();e.exported("fresh");
            equal(ContentResolver.childQueries,baseline?2:1);
            equal(e.props("fresh").getProperty("publicChildQueryCount"),baseline?"2":"1");
            yes(DocumentFile.legacyFindCalls==0 && DocumentFile.nameCalls==0);
            yes(ContentResolver.closedCursors==ContentResolver.openedCursors);
            if(!baseline)equal(e.props("fresh").getProperty("publicInitialQuerySkipped"),"true");
            System.out.println("SCAN_MEASUREMENT mode="+(baseline?"baseline":"candidate")
                    +" childQueries="+ContentResolver.childQueries
                    +" childRows="+e.props("fresh").getProperty("publicChildRowsScanned"));
            pass("fresh_save_14000_unrelated_rows_byte_identical");
        }
        if(baseline) {System.out.println("SAVELOOKUP_BASELINE_PASS scenarios="+scenarios+" assertions="+assertions);return;}
        try(Env e=new Env(base.resolve("conflict"))) {
            e.stage("conflict");Files.write(e.output("conflict"),new byte[]{7,8,9});
            e.spool.pump();e.status("conflict","publication_conflict_private_retained");e.retained("conflict");
            yes(Arrays.equals(new byte[]{7,8,9},Files.readAllBytes(e.output("conflict"))));
            equal(DocumentFile.renames,0);pass("existing_final_never_overwritten");
        }
        try(Env e=new Env(base.resolve("racing"))) {
            e.stage("racing");ContentResolver.conflictPath=e.output("racing");ContentResolver.conflictOnQuery=1;
            e.spool.pump();e.status("racing","publication_conflict_private_retained");e.retained("racing");
            equal(DocumentFile.renames,0);yes(Arrays.equals(new byte[]{7,8,9},Files.readAllBytes(e.output("racing"))));
            pass("fresh_final_query_detects_intervening_conflict");
        }
        try(Env e=new Env(base.resolve("same_final"))) {
            e.stage("same");Files.write(e.output("same"),DATA);e.spool.pump();e.exported("same");
            yes(!Files.exists(e.temp("same")));equal(e.props("same").getProperty("publicOwnedTemporaryRemoved"),"true");
            equal(DocumentFile.renames,0);pass("matching_existing_final_only_verified_owned_temp_removed");
        }
        try(Env e=new Env(base.resolve("partial_restart"))) {
            e.stage("partial");ContentResolver.failAfter=137;e.spool.pump();e.status("partial","publication_retry_pending");
            e.retained("partial");equal(Files.size(e.temp("partial")),137L);
            reset();e.reopen();e.spool.pump();e.exported("partial");
            equal(ContentResolver.childQueries,1);equal(e.props("partial").getProperty("publicKnownUriHits"),"1");
            equal(e.props("partial").getProperty("publicInitialQuerySkipped"),"true");
            pass("partial_write_reopens_bound_uri_after_store_restart");
        }
        try(Env e=new Env(base.resolve("rename_restart"))) {
            e.stage("rename");ContentResolver.failReadsAfterRename=1;e.spool.pump();
            e.status("rename","publication_retry_pending");e.retained("rename");yes(Files.exists(e.output("rename")));
            reset();e.reopen();e.spool.pump();e.exported("rename");
            equal(ContentResolver.childQueries,0);equal(ContentResolver.opens,0);
            equal(e.props("rename").getProperty("publicKnownUriHits"),"1");
            pass("verified_recorded_final_after_restart_needs_no_directory_scan_or_rewrite");
        }
        try(Env e=new Env(base.resolve("corrupt_known_final"))) {
            e.stage("bad");ContentResolver.failReadsAfterRename=1;e.spool.pump();e.retained("bad");
            byte[] changed=DATA.clone();changed[13]^=1;Files.write(e.output("bad"),changed);
            reset();e.reopen();e.spool.pump();e.status("bad","publication_conflict_private_retained");
            e.retained("bad");yes(Arrays.equals(changed,Files.readAllBytes(e.output("bad"))));
            equal(ContentResolver.opens,0);pass("known_final_same_length_corruption_rejected");
        }
        try(Env e=new Env(base.resolve("create_checkpoint_window"))) {
            e.stage("window");ContentResolver.nullCursor=true;e.spool.pump();
            e.status("window","publication_retry_pending");e.retained("window");yes(Files.exists(e.temp("window")));
            equal(e.props("window").getProperty("publicTemporaryUri",""),"");
            reset();e.reopen();e.spool.pump();e.exported("window");
            equal(ContentResolver.childQueries,2);equal(DocumentFile.creates,0);
            pass("created_temp_before_uri_checkpoint_recovers_by_full_lookup");
        }
        try(Env e=new Env(base.resolve("unknown_uri"))) {
            e.stage("unknown");ContentResolver.failAfter=137;e.spool.pump();e.spool.close();
            Properties p=MonoDngSpool1B.loadProperties(e.job("unknown").resolve("job.properties"));
            // A valid opaque URI whose provider metadata query returns no document.
            // The mock registry must know the ID; the backing file deliberately does not exist.
            Path missing=e.out.resolve("missing_provider_document");
            yes(!Files.exists(missing));
            p.setProperty("publicTemporaryUri",android.net.Uri.of(missing).toString());
            MonoDngSpool1B.saveProperties(e.job("unknown").resolve("job.properties"),p);
            reset();e.open();e.spool.pump();e.exported("unknown");
            equal(ContentResolver.childQueries,2);equal(DocumentFile.creates,0);
            equal(e.props("unknown").getProperty("publicKnownUriFallbacks"),"1");
            pass("unknown_recorded_uri_falls_back_without_assuming_absence");
        }
        try(Env e=new Env(base.resolve("parent_mismatch"))) {
            e.stage("parent");ContentResolver.failAfter=137;e.spool.pump();e.spool.close();
            Properties p=MonoDngSpool1B.loadProperties(e.job("parent").resolve("job.properties"));
            p.setProperty("publicLookupParentUri1H","other_parent");
            MonoDngSpool1B.saveProperties(e.job("parent").resolve("job.properties"),p);
            reset();e.open();e.spool.pump();e.exported("parent");
            equal(ContentResolver.childQueries,2);equal(e.props("parent").getProperty("publicKnownUriHits"),"0");
            pass("known_uri_cannot_cross_parent_binding");
        }
        try(Env e=new Env(base.resolve("close_error"))) {
            e.stage("close");ContentResolver.failCloses=1;e.spool.pump();e.status("close","publication_retry_pending");
            e.retained("close");reset();e.reopen();e.spool.pump();e.exported("close");
            equal(ContentResolver.opens,0);equal(ContentResolver.childQueries,1);
            equal(e.props("close").getProperty("publicTemporaryReused"),"true");pass("complete_temp_reused_after_close_error");
        }
        for(String fault:new String[]{"null","missing_column","loading","loading_after","denied","mid_cursor","readback","renamed_name","created_name"}) {
            try(Env e=new Env(base.resolve("fault_"+fault))) {
                e.stage("fault");
                if(fault.equals("null"))ContentResolver.nullCursor=true;
                if(fault.equals("missing_column"))ContentResolver.omitName=true;
                if(fault.equals("loading"))ContentResolver.loading=true;
                if(fault.equals("loading_after"))ContentResolver.loadingAfter=true;
                if(fault.equals("denied"))ContentResolver.queryDenied=true;
                if(fault.equals("mid_cursor")){ContentResolver.noiseRows=32;ContentResolver.throwAtRow=8;}
                if(fault.equals("readback"))ContentResolver.denyRead=true;
                if(fault.equals("renamed_name"))ContentResolver.alterRenameName=true;
                if(fault.equals("created_name"))ContentResolver.alterCreateName=true;
                e.spool.pump();e.status("fault","publication_retry_pending");e.retained("fault");
                yes(!"true".equals(e.props("fault").getProperty("publicReadbackVerified")));
                if(!fault.equals("renamed_name"))equal(DocumentFile.renames,0);
                equal(ContentResolver.openedCursors,ContentResolver.closedCursors);
                pass("fail_closed_"+fault);
            }
        }
        try(Env e=new Env(base.resolve("ambiguous"))) {
            e.stage("amb");Files.write(e.output("amb"),DATA);ContentResolver.duplicateName=e.output("amb").getFileName().toString();
            e.spool.pump();e.status("amb","publication_retry_pending");e.retained("amb");equal(DocumentFile.renames,0);
            pass("ambiguous_final_names_cannot_authorize_rename");
        }
        try(Env e=new Env(base.resolve("non_tree"))) {
            android.net.Uri.defaultTree=false;e.stage("notree");e.spool.pump();e.exported("notree");
            equal(ContentResolver.childQueries,1);pass("non_tree_opaque_provider_uri_supported");
        }
        try(Env e=new Env(base.resolve("direct"))) {
            DocumentFileCompat.enabled=false;e.stage("direct");e.spool.pump();e.exported("direct");
            equal(ContentResolver.childQueries,0);equal(e.props("direct").getProperty("publicTransport"),"direct_verified_temporary_rename");
            pass("direct_filesystem_transport_unchanged");
        }
        try(Env e=new Env(base.resolve("real_dng"))) {
            MonoLinearPlane1A plane=MonoLinearPlane1A.create(4096,3072,90,
                    new float[]{.65497077f,.7578125f,.042704627f},2.56,(row,rgb)->{
                for(int x=0;x<4096;x++){rgb[3*x]=(short)((x*13+row*19)&65535);
                    rgb[3*x+1]=(short)((x*17+row*7)&65535);rgb[3*x+2]=(short)((x*23+row*11)&65535);}
                return rgb.length;
            });
            MonoDngWriter1A.Metadata m=new MonoDngWriter1A.Metadata();
            m.make="SyntheticFixture";m.model="OpaqueProvider";m.iso=200;m.exposureNs=10000000;
            byte[] thumb={50,50,50};Path reference=base.resolve("reference_12mp.dng");long bytes;
            try(OutputStream o=Files.newOutputStream(reference)){bytes=MonoDngWriter1A.write(o,plane,m,1,1,thumb);}
            e.spool.stage(e.output("real"),"{}",26L<<20,o->MonoDngWriter1A.write(o,plane,m,1,1,thumb));
            e.spool.pump();e.status("real","exported");
            equal(Files.size(e.output("real")),bytes);
            equal(MonoDngSpool1B.hashFile(reference),MonoDngSpool1B.hashFile(e.output("real")));
            Files.copy(e.output("real"),base.resolve("transport_12mp.dng"));
            equal(ContentResolver.childQueries,1);pass("real_12mp_DNG_byte_identical_after_new_publication_path");
        }
        System.out.println("SAVELOOKUP_CANDIDATE_PASS scenarios="+scenarios+" assertions="+assertions);
    }
}
