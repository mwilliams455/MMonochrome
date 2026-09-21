package com.particlesdevs.photoncamera.m9.export;

import java.io.*;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;

public final class SpoolTest {
    static int assertions,scenarios;
    static final byte[] DATA=new byte[65539];
    static {new Random(731).nextBytes(DATA);}
    static void yes(boolean b){assertions++;if(!b)throw new AssertionError("assertion "+assertions);}
    static void equal(Object a,Object b){yes(Objects.equals(a,b));}
    static void scenario(String s){scenarios++;System.out.println("PASS "+s);}
    static final class Env implements AutoCloseable {
        final Path root,out;final AtomicLong time=new AtomicLong(1700000000000L),free=new AtomicLong(10L<<30);
        final List<Properties> events=new CopyOnWriteArrayList<>();final AtomicBoolean listenerOn=new AtomicBoolean(true);
        final AtomicInteger writes=new AtomicInteger();MonoDngSpool1B spool;
        Env(Path path,MonoDngSpool1B.Publisher custom)throws Exception {
            root=path.resolve("private");out=path.resolve("public");Files.createDirectories(out);
            open(custom,new MonoDngSpool1B.Policy(20,24,64,512L<<20,1024L<<20,16L<<20));
        }
        void open(MonoDngSpool1B.Publisher custom,MonoDngSpool1B.Policy policy)throws Exception {
            spool=new MonoDngSpool1B(root,policy,time::get,free::get,custom==null?j->{
                if(Files.exists(j.output())) {
                    if(!MonoDngSpool1B.hashFile(j.output()).equals(j.get("payloadSha256")))throw new MonoDngSpool1B.Conflict("existing_final_differs");
                    return;
                }
                Files.copy(j.payload(),j.output());writes.incrementAndGet();
                yes(MonoDngSpool1B.hashFile(j.output()).equals(j.get("payloadSha256")));
            }:custom,p->{events.add(p);return listenerOn.get();});spool.recover();
        }
        Properties stage(String s)throws Exception{return spool.stage(out.resolve(s+"_MONO_LINEAR1A.dng"),"{}",DATA.length+512L,o->{o.write(DATA);return DATA.length;});}
        Properties latest(String s){return spool.snapshots().stream().filter(p->p.getProperty("outputPath","").endsWith(s+"_MONO_LINEAR1A.dng")).findFirst().orElseThrow();}
        void status(String s,String state){equal(latest(s).getProperty("status"),state);}
        Path job(String s)throws Exception{return root.resolve("job_"+id(out.resolve(s+"_MONO_LINEAR1A.dng")));}
        public void close()throws Exception{spool.close();}
    }
    static String id(Path path)throws Exception {
        byte[] b=java.security.MessageDigest.getInstance("SHA-256").digest(path.toString().getBytes(java.nio.charset.StandardCharsets.UTF_8));
        StringBuilder s=new StringBuilder();for(byte v:b)s.append(String.format(Locale.ROOT,"%02x",v&255));return s.substring(0,32);
    }
    public static void main(String[] args)throws Exception {
        Path base=Paths.get(args[0]);Files.createDirectories(base);
        // Reproduce the exact old executor-capacity failure deterministically, without timed sleeps.
        CountDownLatch oldEntered=new CountDownLatch(1),oldRelease=new CountDownLatch(1);
        ThreadPoolExecutor old=new ThreadPoolExecutor(1,1,0,TimeUnit.MILLISECONDS,new ArrayBlockingQueue<>(1),new ThreadPoolExecutor.AbortPolicy());
        old.execute(()->{oldEntered.countDown();try{oldRelease.await();}catch(InterruptedException e){Thread.currentThread().interrupt();}});
        yes(oldEntered.await(2,TimeUnit.SECONDS));old.execute(()->{});boolean rejected=false;
        try{old.execute(()->{});}catch(RejectedExecutionException expected){rejected=true;}
        yes(rejected);oldRelease.countDown();old.shutdown();yes(old.awaitTermination(2,TimeUnit.SECONDS));scenario("legacy_one_active_one_waiting_drops_third_reproduced");

        CountDownLatch entered=new CountDownLatch(1),release=new CountDownLatch(1);AtomicInteger copies=new AtomicInteger();
        try(Env e=new Env(base.resolve("slow"),j->{
            if(copies.getAndIncrement()==0){entered.countDown();if(!release.await(5,TimeUnit.SECONDS))throw new IOException("test_timeout");}
            Files.copy(j.payload(),j.output());yes(MonoDngSpool1B.hashFile(j.output()).equals(j.get("payloadSha256")));
        })) {
            e.stage("a");ExecutorService worker=Executors.newSingleThreadExecutor();Future<?> pump=worker.submit(e.spool::pump);
            try {
                yes(entered.await(2,TimeUnit.SECONDS));
                // These must complete while public I/O is STILL blocked.
                e.stage("b");e.stage("c");yes(e.spool.admission().pendingJobs==3);
                e.status("b","staged_publication_pending");e.status("c","staged_publication_pending");
                yes(Files.size(e.job("c").resolve("payload.dng"))==DATA.length);
            }finally{release.countDown();pump.get(5,TimeUnit.SECONDS);worker.shutdownNow();}
            e.spool.pump();for(String s:new String[]{"a","b","c"}){e.status(s,"exported");yes(Arrays.equals(DATA,Files.readAllBytes(e.out.resolve(s+"_MONO_LINEAR1A.dng"))));}
            yes(e.spool.admission().pendingJobs==0);yes(e.spool.admission().allowed);scenario("three_private_stages_survive_blocked_public_lane");
        }
        AtomicInteger tries=new AtomicInteger();
        try(Env e=new Env(base.resolve("retry"),j->{
            Path tmp=j.output().resolveSibling(j.get("temporaryName"));
            if(tries.incrementAndGet()==1){Files.write(tmp,Arrays.copyOf(DATA,137));throw new IOException("injected_partial_public_write");}
            Files.copy(j.payload(),tmp,StandardCopyOption.REPLACE_EXISTING);Files.move(tmp,j.output());
            yes(MonoDngSpool1B.hashFile(j.output()).equals(j.get("payloadSha256")));
        })) {
            e.stage("a");e.spool.pump();e.status("a","publication_retry_pending");yes(Files.exists(e.job("a").resolve("payload.dng")));
            yes(!Files.exists(e.out.resolve("a_MONO_LINEAR1A.dng")));e.spool.pump();yes(tries.get()==1);
            e.time.addAndGet(1000);e.spool.pump();e.status("a","exported");yes(tries.get()==2);
            equal(e.latest("a").getProperty("publicReadbackVerified"),"true");scenario("partial_write_retained_backoff_retry_completes");
        }
        try(Env e=new Env(base.resolve("restart"),null)) {
            e.stage("a");e.spool.close();e.open(null,MonoDngSpool1B.Policy.normal());
            e.status("a","staged_publication_pending");equal(e.latest("a").getProperty("recoveredAfterRestart"),"true");
            e.spool.pump();e.status("a","exported");yes(e.writes.get()==1);e.spool.close();e.open(null,MonoDngSpool1B.Policy.normal());
            e.spool.pump();yes(e.writes.get()==1);e.status("a","exported");scenario("restart_recovers_pending_without_duplicate_complete_export");
        }
        try(Env e=new Env(base.resolve("commit_window"),j->{Files.copy(j.payload(),j.output());throw new IOException("process_dies_after_final_file_before_receipt");})) {
            e.stage("a");e.spool.pump();e.status("a","publication_retry_pending");e.spool.close();e.open(null,MonoDngSpool1B.Policy.normal());
            e.spool.pump();e.status("a","exported");yes(e.writes.get()==0);scenario("already_published_file_verified_after_restart_not_overwritten");
        }
        try(Env e=new Env(base.resolve("sealed_window"),null)) {
            e.stage("a");e.spool.close();Path dir=e.job("a");Properties p=MonoDngSpool1B.loadProperties(dir.resolve("job.properties"));
            p.setProperty("status","stage_sealed");MonoDngSpool1B.saveProperties(dir.resolve("job.properties"),p);
            Files.move(dir.resolve("payload.dng"),dir.resolve("payload.part"));e.open(null,MonoDngSpool1B.Policy.normal());
            e.status("a","staged_publication_pending");e.spool.pump();e.status("a","exported");scenario("sealed_part_commit_window_recovered_exactly");
        }
        try(Env e=new Env(base.resolve("interrupted"),null)) {
            e.stage("a");e.spool.close();Path dir=e.job("a");Properties p=MonoDngSpool1B.loadProperties(dir.resolve("job.properties"));
            p.setProperty("status","staging");MonoDngSpool1B.saveProperties(dir.resolve("job.properties"),p);
            Files.move(dir.resolve("payload.dng"),dir.resolve("payload.part"));Files.write(dir.resolve("payload.part"),new byte[]{1,2});
            e.open(null,MonoDngSpool1B.Policy.normal());e.status("a","interrupted_private_stage_original_RAW_retained");
            e.spool.pump();yes(e.writes.get()==0);yes(Files.exists(dir.resolve("payload.part")));scenario("unsealed_interrupted_stage_not_misrepresented_as_exported");
        }
        try(Env e=new Env(base.resolve("corrupt"),null)) {
            e.stage("a");byte[] wrong=DATA.clone();wrong[0]^=1;Files.write(e.job("a").resolve("payload.dng"),wrong);
            e.spool.pump();e.status("a","private_stage_corrupt_original_RAW_retained");yes(e.writes.get()==0);
            yes(Files.exists(e.job("a").resolve("payload.dng")));scenario("same_length_corruption_detected_before_publication");
        }
        try(Env e=new Env(base.resolve("capacity"),null)) {
            e.spool.close();e.open(null,new MonoDngSpool1B.Policy(2,4,1,1L<<20,2L<<20,16L<<20));
            e.stage("a");yes(e.spool.admission().allowed);e.stage("b");yes(!e.spool.admission().allowed);
            e.stage("c");e.stage("d");boolean full=false;try{e.stage("e");}catch(MonoDngSpool1B.Capacity x){full=true;}yes(full);
            yes(e.spool.admission().pendingJobs==4);e.spool.pump();yes(e.spool.admission().allowed);yes(e.spool.snapshots().size()==1);
            for(String s:new String[]{"a","b","c","d"})yes(Files.exists(e.out.resolve(s+"_MONO_LINEAR1A.dng")));
            e.free.set(1);e.spool.refreshAdmission();yes(!e.spool.admission().allowed);scenario("soft_admission_hard_bound_completed_receipt_cleanup_low_space");
        }
        try(Env e=new Env(base.resolve("duplicate"),null)) {
            e.stage("a");AtomicInteger encodes=new AtomicInteger();e.spool.stage(e.out.resolve("a_MONO_LINEAR1A.dng"),"{}",DATA.length+1,o->{encodes.incrementAndGet();throw new IOException();});
            yes(encodes.get()==0);yes(e.spool.snapshots().size()==1);e.spool.pump();yes(e.writes.get()==1);scenario("duplicate_submit_is_idempotent");
        }
        try(Env e=new Env(base.resolve("encoder_error"),null)) {
            boolean failed=false;try{e.spool.stage(e.out.resolve("a_MONO_LINEAR1A.dng"),"{}",10000,o->{o.write(new byte[10]);return 11;});}catch(IOException x){failed=true;}
            yes(failed);e.status("a","private_stage_failed_original_RAW_retained");e.spool.pump();yes(e.writes.get()==0);
            failed=false;try{e.spool.stage(e.out.resolve("b_MONO_LINEAR1A.dng"),"{}",10,o->{o.write(new byte[11]);return 11;});}catch(IOException x){failed=true;}
            yes(failed);e.status("b","private_stage_failed_original_RAW_retained");scenario("encoder_length_and_reservation_bounds_fail_explicitly");
        }
        try(Env e=new Env(base.resolve("diagnostic"),null)) {
            e.listenerOn.set(false);e.stage("a");e.spool.pump();e.status("a","exported");yes(!Files.exists(e.job("a").resolve("payload.dng")));
            int oldEvents=e.events.size();e.listenerOn.set(true);e.spool.pump();yes(e.events.size()>oldEvents);
            equal(e.latest("a").getProperty("reportedSequence"),e.latest("a").getProperty("statusSequence"));scenario("diagnostic_delivery_failure_does_not_lose_export_receipt");
        }
        try(Env e=new Env(base.resolve("concurrent"),null)) {
            ExecutorService threads=Executors.newFixedThreadPool(6);List<Future<?>> futures=new ArrayList<>();
            try{for(int i=0;i<12;i++){final String name="image"+i;futures.add(threads.submit(()->{try{e.stage(name);}catch(Exception x){throw new RuntimeException(x);}}));}
                for(Future<?> f:futures)f.get(10,TimeUnit.SECONDS);
            }finally{threads.shutdownNow();}
            yes(e.spool.snapshots().size()==12);e.spool.pump();yes(e.writes.get()==12);for(Properties p:e.spool.snapshots())equal(p.getProperty("status"),"exported");
            boolean locked=false;try {new Env(base.resolve("concurrent"),null);}catch(IOException expected){locked=true;}yes(locked);scenario("concurrent_staging_and_exclusive_store_ownership");
        }
        for(long i=1;i<30;i++){long delay=MonoDngSpool1B.retryDelay(i);yes(delay>=1000&&delay<=60000);if(i>1)yes(delay>=MonoDngSpool1B.retryDelay(i-1));}
        scenario("bounded_exponential_retry");
        // 12MP actual writer: unchanged file bytes, high-precision samples, dimensions and metadata.
        try(Env e=new Env(base.resolve("real_dng"),null)) {
            MonoLinearPlane1A plane=MonoLinearPlane1A.create(4096,3072,90,new float[]{.65497077f,.7578125f,.042704627f},2.56,
                    (row,rgb)->{for(int x=0;x<4096;x++){rgb[3*x]=(short)((x*13+row*19)&65535);rgb[3*x+1]=(short)((x*17+row*7)&65535);rgb[3*x+2]=(short)((x*23+row*11)&65535);}return rgb.length;});
            MonoDngWriter1A.Metadata m=new MonoDngWriter1A.Metadata();m.make="Fixture";m.model="MultiDevice";m.iso=1783;m.exposureNs=25399495;
            byte[] thumb={50,50,50};Path reference=base.resolve("reference_12mp.dng");long size;
            try(OutputStream out=Files.newOutputStream(reference)){size=MonoDngWriter1A.write(out,plane,m,1,1,thumb);}
            Path target=e.out.resolve("actual_MONO_LINEAR1A.dng");
            e.spool.stage(target,"{}",26L<<20,o->MonoDngWriter1A.write(o,plane,m,1,1,thumb));e.spool.pump();
            equal(MonoDngSpool1B.hashFile(reference),MonoDngSpool1B.hashFile(target));yes(Files.size(target)==size);
            Files.copy(target,base.resolve("transport_12mp.dng"));scenario("12mp_DNG_transport_byte_identical_to_unchanged_writer");
        }
        System.out.println("MONOOUTPUT1B_SPOOL_PASS scenarios="+scenarios+" assertions="+assertions);
    }
}
