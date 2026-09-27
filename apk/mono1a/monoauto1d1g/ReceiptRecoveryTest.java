package com.particlesdevs.photoncamera.m9.export;

import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.atomic.AtomicInteger;

/** Real durable spool + real filesystem; only the public publisher is a host adapter. */
public final class ReceiptRecoveryTest {
    private static int checks;
    private static final byte[] DATA = "synthetic-dng-transport-bytes".getBytes(StandardCharsets.UTF_8);
    private static void ok(boolean b,String why) {
        checks++;
        if(!b) throw new AssertionError(why);
    }
    private static final class Env implements AutoCloseable {
        final Path root, out;
        final List<Properties> events = new ArrayList<>();
        final AtomicInteger writes = new AtomicInteger();
        boolean listenerAccepts=true, failPublish=false;
        MonoDngSpool1B store;
        Env(Path base)throws Exception {
            root=base.resolve("private");out=base.resolve("public");
            Files.createDirectories(out);open();
        }
        void open()throws Exception {
            store=new MonoDngSpool1B(root,MonoDngSpool1B.Policy.normal(),
                    ()->1700000000000L,()->8L<<30,j->{
                if(failPublish)throw new IOException("synthetic_public_transport_failure");
                if(Files.exists(j.output())) {
                    if(!MonoDngSpool1B.hashFile(j.output()).equals(j.get("payloadSha256")))
                        throw new MonoDngSpool1B.Conflict("synthetic_existing_file_conflict");
                } else {
                    Files.copy(j.payload(),j.output());writes.incrementAndGet();
                }
                if(!MonoDngSpool1B.hashFile(j.output()).equals(j.get("payloadSha256")))
                    throw new IOException("host_readback_mismatch");
            },p->{events.add(p);return listenerAccepts;});
            store.recover();
        }
        void reopen()throws Exception {store.close();events.clear();open();}
        Properties stage(String name)throws Exception {
            return store.stage(out.resolve(name+"_MONO_LINEAR1A.dng"),"{}",1024,
                    o->{o.write(DATA);return DATA.length;});
        }
        Properties receipt(String name) {
            return store.snapshots().stream().filter(p->p.getProperty("outputPath","")
                    .endsWith(name+"_MONO_LINEAR1A.dng")).findFirst().orElseThrow();
        }
        Path job(String name)throws Exception {
            try(DirectoryStream<Path> ds=Files.newDirectoryStream(root,"job_*")) {
                for(Path d:ds) {
                    Properties p=MonoDngSpool1B.loadProperties(d.resolve("job.properties"));
                    if(p.getProperty("outputPath","").endsWith(name+"_MONO_LINEAR1A.dng"))return d;
                }
            }
            throw new AssertionError("job missing");
        }
        void set(String name,String key,String value)throws Exception {
            Path file=job(name).resolve("job.properties");
            Properties p=MonoDngSpool1B.loadProperties(file);
            if(value==null)p.remove(key);else p.setProperty(key,value);
            MonoDngSpool1B.saveProperties(file,p);
        }
        public void close()throws Exception{store.close();}
    }
    public static void main(String[] args)throws Exception {
        Path base=Paths.get(args[0]);Files.createDirectories(base);
        try(Env e=new Env(base.resolve("completed"))) {
            for(int i=0;i<12;i++){e.stage("done"+i);e.store.pump();}
            ok(e.writes.get()==12,"all synthetic files published");
            long before=MonoDngSpool1B.suppressedRecoveryReceipts1G();
            e.reopen();
            ok(e.events.isEmpty(),"acknowledged completions not restaged on restart");
            ok(MonoDngSpool1B.suppressedRecoveryReceipts1G()-before==12,"suppression count exact");
            ok(e.store.snapshots().size()==12,"receipts retained for idempotence");
            ok(e.store.admission().pendingJobs==0,"completed receipts are not pending photos");
            AtomicInteger encode=new AtomicInteger();
            e.store.stage(e.out.resolve("done0_MONO_LINEAR1A.dng"),"{}",1024,
                    o->{encode.incrementAndGet();throw new IOException("must_not_encode");});
            e.store.pump();
            ok(encode.get()==0&&e.writes.get()==12,"duplicate submission remains idempotent");
            for(int i=0;i<12;i++)ok(Arrays.equals(DATA,Files.readAllBytes(e.out.resolve("done"+i+"_MONO_LINEAR1A.dng"))),"published bytes unchanged");
            e.reopen();ok(e.events.isEmpty(),"second restart stays quiet");
        }
        try(Env e=new Env(base.resolve("unacknowledged"))) {
            e.listenerAccepts=false;e.stage("a");e.store.pump();
            ok("exported".equals(e.receipt("a").getProperty("status")),"image completes despite diagnostic failure");
            e.listenerAccepts=true;e.reopen();
            ok(e.events.size()==1,"unacknowledged completion re-emitted once");
            ok("exported".equals(e.events.get(0).getProperty("status")),"completion status preserved");
            e.reopen();ok(e.events.isEmpty(),"acknowledged retry not replayed again");
        }
        try(Env e=new Env(base.resolve("pending"))) {
            e.stage("a");Path payload=e.job("a").resolve("payload.dng");String hash=MonoDngSpool1B.hashFile(payload);
            e.reopen();
            ok(e.events.size()==1,"pending job recovery still emits");
            ok("staged_publication_pending".equals(e.receipt("a").getProperty("status")),"pending job preserved");
            ok(Files.exists(payload)&&hash.equals(MonoDngSpool1B.hashFile(payload)),"pending pixels retained exactly");
            e.store.pump();ok(e.writes.get()==1,"pending DNG resumes and publishes");
            ok(Arrays.equals(DATA,Files.readAllBytes(e.out.resolve("a_MONO_LINEAR1A.dng"))),"resumed DNG byte equality");
        }
        try(Env e=new Env(base.resolve("failure"))) {
            e.failPublish=true;e.stage("a");e.store.pump();e.reopen();
            ok(e.events.size()==1,"failed publication is not hidden");
            ok("publication_retry_pending".equals(e.receipt("a").getProperty("status")),"retry state preserved");
            ok(Files.isRegularFile(e.job("a").resolve("payload.dng")),"failed job keeps payload");
            e.failPublish=false;e.store.pump();ok(e.writes.get()==1,"retry completes after recovery");
        }
        try(Env e=new Env(base.resolve("conflict"))) {
            e.stage("a");Files.write(e.out.resolve("a_MONO_LINEAR1A.dng"),new byte[]{1});e.store.pump();e.reopen();
            ok(e.events.size()==1,"conflict record still visible");
            ok("publication_conflict_private_retained".equals(e.receipt("a").getProperty("status")),"conflict remains explicit");
            ok(Files.isRegularFile(e.job("a").resolve("payload.dng")),"conflicting unpublished pixels retained");
            ok(Arrays.equals(new byte[]{1},Files.readAllBytes(e.out.resolve("a_MONO_LINEAR1A.dng"))),"existing public file never overwritten");
        }
        for(String key:new String[]{"publicWriteCompleted","publicReadbackVerified","reportedSequence","statusSequence"}) {
            try(Env e=new Env(base.resolve("missing_"+key))) {
                e.stage("a");e.store.pump();e.store.close();e.set("a",key,null);e.events.clear();e.open();
                ok(e.events.size()==1,"missing proof must not suppress: "+key);
            }
        }
        try(Env e=new Env(base.resolve("corrupt"))) {
            e.stage("a");Files.write(e.job("a").resolve("payload.dng"),new byte[]{3});e.reopen();e.store.pump();
            ok("private_stage_corrupt_original_RAW_retained".equals(e.receipt("a").getProperty("status")),"integrity check remains active");
            ok(e.writes.get()==0,"corruption not published");
            ok(Files.exists(e.job("a").resolve("payload.dng")),"corrupt payload retained for diagnosis");
        }
        System.out.println("RECEIPTHYGIENE1A real-filesystem tests PASS checks="+checks);
    }
}
