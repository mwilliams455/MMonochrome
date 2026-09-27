package com.particlesdevs.photoncamera.m9;

import android.content.Context;
import com.particlesdevs.photoncamera.app.PhotonCamera;
import java.lang.reflect.Field;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.Arrays;
import java.util.concurrent.ScheduledThreadPoolExecutor;
import org.json.JSONObject;

/** Actual diagnostic spool and purge code; Android context/public transport mocked. */
public final class ResetIsolationTest {
    private static int checks;
    private static void ok(boolean b,String why) {checks++;if(!b)throw new AssertionError(why);}
    private static final byte[] SENTINEL={1,4,9,16};
    private static void write(Path p)throws Exception {Files.createDirectories(p.getParent());Files.write(p,SENTINEL);}
    public static void main(String[] args)throws Exception {
        Path base=Paths.get(args[0]), files=base.resolve("files"), diag=files.resolve("m9diag_spool");
        Path publicDir=base.resolve("DCIM"), pending=files.resolve("mono_export_jobs/job_pending/payload.dng");
        Path prefs=files.resolve("preferences.xml"), photo=publicDir.resolve("photo.jpg"), dng=publicDir.resolve("photo.dng");
        Path publicJson=publicDir.resolve("old_diagnostic.json");
        boolean first=args[1].equals("first");
        Files.createDirectories(files);Files.createDirectories(publicDir);
        if(first) {
            write(diag.resolve("old.stage"));write(diag.resolve("old.stage.meta"));write(diag.resolve("another.stage"));
            write(pending);write(prefs);write(photo);write(dng);write(publicJson);
            write(files.resolve("mmonochrome_diag_spool_reset1a.done"));
        } else write(diag.resolve("between_restarts.stage"));
        PhotonCamera.context=new Context(files.toFile());
        try {
            byte[] payload="{\"fixture\":true}".getBytes(StandardCharsets.UTF_8);
            ok(M9DiagnosticBurstSpool.stage(publicDir.resolve(first?"fresh.json":"restart.json"),payload,"fixture"),"new diagnostic stages successfully");
            JSONObject t=M9DiagnosticBurstSpool.snapshotJson();
            ok(t.getBoolean("monoSpoolResetCompleted"),"reset completed");
            ok(t.getString("monoSpoolResetRevision").equals("MMONOSPOOLRESET1B_ONCE"),"new reset generation");
            ok(Files.isRegularFile(files.resolve("mmonochrome_diag_spool_reset1b.done")),"new persistent marker");
            if(first) {
                ok(t.getLong("monoSpoolResetDeletedFiles")==3,"only three old private diagnostic files removed");
                ok(t.getLong("monoSpoolResetDeletedBytes")==12,"purge byte count exact");
                ok(!Files.exists(diag.resolve("old.stage")),"old private stage removed");
                write(diag.resolve("after_first_reset.stage"));
                ok(M9DiagnosticBurstSpool.stage(publicDir.resolve("fresh_second.json"),payload,"fixture"),"second stage accepted");
                ok(Files.exists(diag.resolve("after_first_reset.stage")),"not purged twice in process");
            } else {
                ok(Files.exists(diag.resolve("after_first_reset.stage")),"fresh files survive next process");
                ok(Files.exists(diag.resolve("between_restarts.stage")),"persistent marker prevents another purge");
            }
            for(Path p:new Path[]{pending,prefs,photo,dng,publicJson})
                ok(Arrays.equals(SENTINEL,Files.readAllBytes(p)),"protected file byte-identical: "+p.getFileName());
            ok(t.getString("monoDngReceiptRecoveryRevision").equals("MONOOUTPUT1G_RECEIPTHYGIENE1A"),"receipt policy telemetry present");
            System.out.println("RESET1B actual-spool host test PASS mode="+args[1]+" checks="+checks);
        } finally {
            for(String name:new String[]{"BUNDLE_EXECUTOR","INDIVIDUAL_EXPORTER"}) {
                Field f=M9DiagnosticBurstSpool.class.getDeclaredField(name);f.setAccessible(true);
                ((ScheduledThreadPoolExecutor)f.get(null)).shutdownNow();
            }
        }
    }
}
