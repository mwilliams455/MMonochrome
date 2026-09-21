package com.particlesdevs.photoncamera.m9.export;

import android.content.*;
import android.net.Uri;
import androidx.documentfile.provider.DocumentFile;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import com.particlesdevs.photoncamera.m9.M9DiagnosticBurstSpool;
import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.lang.reflect.*;
import java.util.concurrent.*;

/** Real query/publisher/spool implementations; provider and cursor failure injection is mocked. */
public final class QueryExportTest {
    static int assertions,scenarios;
    static void yes(boolean x){assertions++;if(!x)throw new AssertionError("cursor export "+assertions);}
    static void pass(String s){scenarios++;System.out.println("PASS "+s);}
    static void pending(PublisherTest.Env e){yes(e.status().equals("publication_retry_pending"));yes(e.spool.admission().pendingJobs==1);yes(e.state().getProperty("privateStageComplete").equals("true"));}
    public static void main(String[] args)throws Exception {
        Path base=Paths.get(args[0]);
        try(PublisherTest.Env e=new PublisherTest.Env(base.resolve("many"))) {
            ContentResolver.noiseRows=10000;ContentResolver.reorder=true;e.stage();e.spool.pump();
            yes(e.status().equals("exported"));yes(Arrays.equals(PublisherTest.DATA,Files.readAllBytes(e.output)));
            yes(ContentResolver.childQueries==2);yes(ContentResolver.metadataQueries==2);
            yes(DocumentFile.legacyFindCalls==0);yes(DocumentFile.nameCalls==0);
            yes(ContentResolver.openedCursors==ContentResolver.closedCursors);
            yes(e.state().getProperty("publicChildQueryCount").equals("2"));
            yes(e.state().getProperty("publicChildRowsScanned").equals("20001"));
            yes(e.state().getProperty("publicMetadataQueryCount").equals("2"));
            yes(e.state().containsKey("publicInitialQueryMs")&&e.state().containsKey("publicConflictQueryMs"));
            yes(e.state().containsKey("publicCreateMetadataMs")&&e.state().containsKey("publicFinalMetadataMs"));
            pass("10000_unrelated_children_two_aggregate_queries_two_known_URI_queries_no_child_getName");
        }
        for(String failure:new String[]{"null","loading","loadingAfter","providerError","columns","midCursor","permission"}) {
            try(PublisherTest.Env e=new PublisherTest.Env(base.resolve(failure))) {
                e.stage();
                switch(failure) {
                    case "null":ContentResolver.nullCursor=true;break;
                    case "loading":ContentResolver.loading=true;break;
                    case "loadingAfter":ContentResolver.loadingAfter=true;break;
                    case "providerError":ContentResolver.errorExtra="backend incomplete";break;
                    case "columns":ContentResolver.omitName=true;break;
                    case "midCursor":ContentResolver.noiseRows=20;ContentResolver.throwAtRow=5;break;
                    case "permission":ContentResolver.queryDenied=true;break;
                }
                e.spool.pump();pending(e);yes(!Files.exists(e.output));yes(DocumentFile.creates==0);yes(ContentResolver.opens==0);
                yes(ContentResolver.openedCursors==ContentResolver.closedCursors);
                ContentResolver.nullCursor=ContentResolver.loading=ContentResolver.loadingAfter=ContentResolver.omitName=ContentResolver.queryDenied=false;
                ContentResolver.errorExtra=null;ContentResolver.throwAtRow=-1;e.retry();
                yes(e.status().equals("exported"));yes(Arrays.equals(PublisherTest.DATA,Files.readAllBytes(e.output)));
                pass("uncertain_"+failure+"_is_not_absence_private_retained_and_retry_succeeds");
            }
        }
        try(PublisherTest.Env e=new PublisherTest.Env(base.resolve("duplicate"))) {
            Files.write(e.output,PublisherTest.DATA);e.stage();ContentResolver.duplicateName=e.output.getFileName().toString();
            e.spool.pump();pending(e);yes(ContentResolver.opens==0);yes(DocumentFile.creates==0);
            yes(Arrays.equals(PublisherTest.DATA,Files.readAllBytes(e.output)));
            ContentResolver.duplicateName=null;e.retry();yes(e.status().equals("exported"));yes(ContentResolver.opens==0);
            pass("duplicate_display_names_rejected_no_overwrite_no_false_already_complete");
        }
        try(PublisherTest.Env e=new PublisherTest.Env(base.resolve("race"))) {
            e.stage();ContentResolver.conflictPath=e.output;ContentResolver.conflictOnQuery=2;e.spool.pump();
            yes(e.status().equals("publication_conflict_private_retained"));yes(Arrays.equals(new byte[]{7,8,9},Files.readAllBytes(e.output)));
            yes(DocumentFile.renames==0);yes(e.spool.admission().pendingJobs==1);
            pass("fresh_pre_rename_query_detects_new_conflict_not_stale_negative_cache");
        }
        for(boolean creation:new boolean[]{true,false}) {
            try(PublisherTest.Env e=new PublisherTest.Env(base.resolve("changedName"+creation))) {
                e.stage();ContentResolver.alterCreateName=creation;ContentResolver.alterRenameName=!creation;e.spool.pump();
                pending(e);yes(!Files.exists(e.output));yes(e.state().getProperty("publicWriteCompleted").equals("false"));
                pass("provider_"+(creation?"create":"rename")+"_changed_name_never_called_exported");
            }
        }
        try(PublisherTest.Env e=new PublisherTest.Env(base.resolve("nullsize"))) {
            ContentResolver.nullSize=true;e.stage();e.spool.pump();yes(e.status().equals("exported"));
            yes(e.state().getProperty("publicReadbackVerified").equals("true"));
            pass("null_provider_size_not_authority_exact_readback_still_required");
        }
        try(PublisherTest.Env e=new PublisherTest.Env(base.resolve("opaque"))) {
            Uri.defaultTree=false;String unusual="quoted' ü % file.json";Path p=e.output.getParent().resolve(unusual);Files.write(p,new byte[]{4});
            DocumentFile parent=new DocumentFile(p.getParent());MonoSafQuery1C.Lookup q=MonoSafQuery1C.find(e.context,parent,unusual,"absent.json");
            yes(q.get(unusual)!=null);yes(q.get("absent.json")==null);yes(q.get(unusual).id.startsWith("opaque:"));
            yes(!q.get(unusual).uri.tree);yes(Files.readAllBytes(q.get(unusual).uri.path)[0]==4);
            Files.write(p.getParent().resolve("absent.json"),new byte[]{3});
            yes(MonoSafQuery1C.find(e.context,parent,"absent.json").get("absent.json")!=null);
            pass("opaque_non_tree_IDs_unicode_quotes_percent_and_no_negative_cache");
        }
        try(PublisherTest.Env e=new PublisherTest.Env(base.resolve("diag"))) {
            Path p=e.output.getParent().resolve("capture_EXPORT.json");byte[] longer="{\"status\":\"staged_publication_pending\",\"longKey\":true}".getBytes("UTF-8"),shorter="{\"status\":\"exported\"}".getBytes("UTF-8");
            ContentResolver.noiseRows=10000;MonoDiagnosticPublicWriter1C w=new MonoDiagnosticPublicWriter1C(e.context);
            w.persist(p,longer);String id=new Uri(p).id();w.persist(p,shorter);
            yes(Arrays.equals(shorter,Files.readAllBytes(p)));yes(new Uri(p).id().equals(id));yes(DocumentFile.creates==1);
            yes(ContentResolver.childQueries==2);yes(ContentResolver.metadataQueries==1);yes(DocumentFile.legacyFindCalls==0);yes(DocumentFile.nameCalls==0);
            yes(ContentResolver.lastMode.equals("rwt"));yes(ContentResolver.openedCursors==ContentResolver.closedCursors);
            pass("large_directory_diagnostic_shorter_update_reuses_URI_and_truncates_without_delete");
        }
        try(PublisherTest.Env e=new PublisherTest.Env(base.resolve("diagfail"))) {
            Path p=e.output.getParent().resolve("capture.json");byte[] payload="{\"status\":\"exported\"}".getBytes("UTF-8");
            ContentResolver.nullCursor=true;yes(!MonoDiagnosticPublicWriter1C.write(e.context,p,payload));yes(!Files.exists(p));yes(ContentResolver.opens==0);
            ContentResolver.nullCursor=false;ContentResolver.failAfter=5;yes(!MonoDiagnosticPublicWriter1C.write(e.context,p,payload));
            yes(MonoDiagnosticPublicWriter1C.write(e.context,p,payload));yes(Arrays.equals(payload,Files.readAllBytes(p)));yes(DocumentFile.creates==1);
            ContentResolver.denyRead=true;yes(!MonoDiagnosticPublicWriter1C.write(e.context,p,payload));ContentResolver.denyRead=false;
            yes(MonoDiagnosticPublicWriter1C.write(e.context,p,payload));yes(Arrays.equals(payload,Files.readAllBytes(p)));
            pass("diagnostic_query_partial_write_and_readback_failures_are_visible_then_retryable");
        }
        try(PublisherTest.Env e=new PublisherTest.Env(base.resolve("realspool"))) {
            PhotonCamera.context=e.context;Path p=e.output.getParent().resolve("immutable.json");byte[] payload="{\"original\":\"unchanged\"}".getBytes("UTF-8");
            yes(M9DiagnosticBurstSpool.stage(p,payload,"test_role"));
            Field scheduled=M9DiagnosticBurstSpool.class.getDeclaredField("scheduledBundle");scheduled.setAccessible(true);((ScheduledFuture<?>)scheduled.get(null)).cancel(false);
            Field pending=M9DiagnosticBurstSpool.class.getDeclaredField("INDIVIDUAL_PENDING");pending.setAccessible(true);
            Map<?,?> map=(Map<?,?>)pending.get(null);Object entry=map.get(p.toString());yes(entry!=null);
            Field privatePath=entry.getClass().getDeclaredField("privatePath");privatePath.setAccessible(true);Path staged=(Path)privatePath.get(entry);
            Method export=M9DiagnosticBurstSpool.class.getDeclaredMethod("exportIndividual",entry.getClass());export.setAccessible(true);
            ContentResolver.loading=true;export.invoke(null,entry);yes(Files.exists(staged));yes(map.get(p.toString())==entry);yes(!Files.exists(p));
            ContentResolver.loading=false;export.invoke(null,entry);yes(!Files.exists(staged));yes(map.get(p.toString())==null);
            yes(Arrays.equals(payload,Files.readAllBytes(p)));yes(M9DiagnosticBurstSpool.snapshotJson().get("publicLookup1C")!=null);
            pass("actual_diagnostic_spool_keeps_private_payload_on_failed_lookup_deletes_only_after_verified_write");
        }
        System.out.println("MONOOUTPUT1C_QUERY_PASS scenarios="+scenarios+" assertions="+assertions+" Android_provider=filesystem_cursor_mock_phone_speed_not_validated");
    }
}
