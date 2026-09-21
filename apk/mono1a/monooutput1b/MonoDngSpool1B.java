package com.particlesdevs.photoncamera.m9.export;

import java.io.*;
import java.nio.channels.FileChannel;
import java.nio.channels.FileLock;
import java.nio.file.*;
import java.security.DigestOutputStream;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.LongSupplier;

/** Durable disk jobs. Only the staging caller owns pixels; the publisher owns paths, never pixels.
 * File-format/photographic code is intentionally outside this class. One instance per process/root.
 * Staging is synchronous private I/O with bounded backpressure, not a lossy memory executor.
 */
public final class MonoDngSpool1B implements AutoCloseable {
    public static final String REVISION="MONOOUTPUT1B_DURABLE_EXPORT";
    public interface Encoder { long write(OutputStream out) throws Exception; }
    public interface Publisher { void publish(Job job) throws Exception; }
    public interface Listener { boolean record(Properties status); }
    public static final class Conflict extends IOException { public Conflict(String s){super(s);} }
    public static final class Capacity extends IOException { public Capacity(String s){super(s);} }
    public static final class Policy {
        public final int softJobs,hardJobs,receipts;
        public final long softBytes,hardBytes,reserveBytes;
        public Policy(int s,int h,int r,long sb,long hb,long reserve) {
            if(s<1||h<s||r<0||sb<1||hb<sb||reserve<0)throw new IllegalArgumentException("policy");
            softJobs=s;hardJobs=h;receipts=r;softBytes=sb;hardBytes=hb;reserveBytes=reserve;
        }
        public static Policy normal(){return new Policy(20,24,64,512L<<20,1024L<<20,256L<<20);}
    }
    public static final class Admission {
        public final boolean allowed; public final String reason;
        public final int pendingJobs; public final long pendingBytes;
        Admission(boolean a,String r,int n,long b){allowed=a;reason=r;pendingJobs=n;pendingBytes=b;}
    }
    public final class Job {
        private final Path dir; private final Properties p;
        private Job(Path d,Properties v){dir=d;p=v;}
        public String get(String key){return p.getProperty(key,"");}
        public long number(String key,long fallback){try{return Long.parseLong(get(key));}catch(Exception e){return fallback;}}
        public Path payload(){return dir.resolve("payload.dng");}
        public Path output(){return Paths.get(get("outputPath"));}
        public Properties snapshot(){Properties v=new Properties();synchronized(p){v.putAll(p);}return v;}
        public void checkpoint(String... pairs) throws IOException {
            if((pairs.length&1)!=0)throw new IllegalArgumentException("pairs");
            synchronized(p){for(int i=0;i<pairs.length;i+=2)p.setProperty(pairs[i],pairs[i+1]);saveProperties(dir.resolve("job.properties"),p);}
        }
        public void metric(String key,long startNs) throws IOException {checkpoint(key,Double.toString((System.nanoTime()-startNs)/1e6));}
        private void state(String value) throws IOException {
            checkpoint("status",value,"statusSequence",Long.toString(number("statusSequence",0)+1),
                    "statusEpochMs",Long.toString(clock.getAsLong()));
        }
    }
    private final Path root; private final Policy policy; private final LongSupplier clock,freeBytes;
    private final Publisher publisher; private final Listener listener;
    private final Object stageLock=new Object(),pumpLock=new Object();
    private final ConcurrentHashMap<String,Job> jobs=new ConcurrentHashMap<>();
    private volatile Admission admission=new Admission(false,"initializing_private_export_store",0,0);
    private volatile boolean recovered,closed; private FileChannel lockChannel; private FileLock ownerLock;
    public MonoDngSpool1B(Path root,Policy policy,LongSupplier clock,LongSupplier freeBytes,
            Publisher publisher,Listener listener) {
        this.root=root;this.policy=policy;this.clock=clock;this.freeBytes=freeBytes;
        this.publisher=publisher;this.listener=listener;
    }
    public Admission admission(){return admission;}
    public synchronized void recover() throws IOException {
        if(recovered)return;if(closed)throw new IOException("store_closed");
        Files.createDirectories(root);
        lockChannel=FileChannel.open(root.resolve("owner.lock"),StandardOpenOption.CREATE,StandardOpenOption.WRITE);
        try {ownerLock=lockChannel.tryLock();}catch(RuntimeException e){lockChannel.close();throw new IOException("store_already_owned",e);}
        if(ownerLock==null){lockChannel.close();throw new IOException("store_already_owned");}
        try(DirectoryStream<Path> dirs=Files.newDirectoryStream(root,"job_*")) {
            for(Path dir:dirs) {
                if(!Files.isDirectory(dir))continue;
                Properties p;
                try {p=loadProperties(dir.resolve("job.properties"));}
                catch(Exception e){p=new Properties();p.setProperty("status","unreadable_private_manifest_retained");p.setProperty("error",e.toString());}
                Job j=new Job(dir,p);jobs.put(dir.getFileName().toString(),j);
                try {
                    if("stage_sealed".equals(j.get("status"))) {
                        Path file=Files.exists(j.payload())?j.payload():dir.resolve("payload.part");
                        requirePayload(j,file);
                        if(!file.equals(j.payload()))moveAtomic(file,j.payload());
                        j.checkpoint("privateStageComplete","true","stagedEpochMs",Long.toString(j.number("stagedEpochMs",clock.getAsLong())));
                        j.state("staged_publication_pending");
                    } else if("staging".equals(j.get("status"))) {
                        j.state("interrupted_private_stage_original_RAW_retained");
                    } else if("publishing".equals(j.get("status"))) {
                        j.state("publication_retry_pending");
                    }
                    if(publishable(j))j.checkpoint("nextAttemptEpochMs","0","recoveredAfterRestart","true");
                    if("exported".equals(j.get("status")))releasePayload(j);
                }catch(Exception e){j.checkpoint("error",e.toString());j.state("private_stage_corrupt_original_RAW_retained");}
            }
        }
        recovered=true;refreshAdmission();
        // Diagnostic replay only: no public image I/O while recovering the private store.
        for(Job j:ordered())emit(j,true);
        pruneReceipts();
    }
    public Properties stage(Path output,String diagnosticJson,long maximumBytes,Encoder encoder) throws Exception {
        long enter=System.nanoTime();
        synchronized(stageLock) {
            if(!recovered||closed)throw new IOException("private_store_not_ready");
            if(output==null||!output.isAbsolute()||!output.getFileName().toString().endsWith("_MONO_LINEAR1A.dng"))
                throw new IOException("invalid_derived_output_identity");
            if(maximumBytes<1||maximumBytes>policy.hardBytes)throw new Capacity("export_size_over_disk_budget");
            String id="job_"+hashBytes(output.normalize().toString().getBytes(java.nio.charset.StandardCharsets.UTF_8)).substring(0,32);
            Job previous=jobs.get(id);
            if(previous!=null) {
                if(!output.normalize().toString().equals(previous.get("outputPath")))throw new Conflict("private_job_identity_collision");
                return previous.snapshot(); // Idempotent duplicate submission, never encode a second image.
            }
            Admission a=admission;
            if(a.pendingJobs>=policy.hardJobs||a.pendingBytes>policy.hardBytes-maximumBytes)
                throw new Capacity("private_export_capacity_reached_original_RAW_retained");
            if(freeBytes.getAsLong()<maximumBytes+(16L<<20))throw new Capacity("insufficient_private_space_original_RAW_retained");
            Path dir=root.resolve(id);Files.createDirectory(dir);
            Properties p=new Properties();p.setProperty("revision",REVISION);p.setProperty("status","staging");
            p.setProperty("outputPath",output.normalize().toString());p.setProperty("diagnosticJson",diagnosticJson);
            p.setProperty("createdEpochMs",Long.toString(clock.getAsLong()));p.setProperty("statusSequence","1");
            p.setProperty("reservedBytes",Long.toString(maximumBytes));p.setProperty("attempts","0");
            p.setProperty("temporaryName",".mono1b_"+UUID.randomUUID()+".pending");
            p.setProperty("privateLaneWaitMs",Double.toString((System.nanoTime()-enter)/1e6));
            p.setProperty("originalRawRetained","true");p.setProperty("publicWriteCompleted","false");
            Job j=new Job(dir,p);jobs.put(id,j);refreshAdmission();long began=System.nanoTime();
            try {
                j.checkpoint();
                MessageDigest digest=MessageDigest.getInstance("SHA-256");long expected,actual;
                try(FileOutputStream raw=new FileOutputStream(dir.resolve("payload.part").toFile())) {
                    BoundedCount out=new BoundedCount(new DigestOutputStream(new BufferedOutputStream(raw,65536),digest),maximumBytes);
                    long writing=System.nanoTime();expected=encoder.write(out);out.flush();actual=out.count;
                    j.metric("privateWriteMs",writing);
                    if(actual!=expected)throw new IOException("private_encoder_length_mismatch");
                    long syncing=System.nanoTime();raw.getFD().sync();j.metric("privateSyncMs",syncing);
                }
                if(Files.size(dir.resolve("payload.part"))!=actual)throw new IOException("private_staged_length_mismatch");
                // Seal metadata before moving: restart can recover a complete .part or a moved payload.
                j.checkpoint("stagedBytes",Long.toString(actual),"payloadSha256",hex(digest.digest()));
                j.state("stage_sealed");moveAtomic(dir.resolve("payload.part"),j.payload());
                j.metric("privateStageElapsedMs",began);
                j.checkpoint("privateStageComplete","true","stagedEpochMs",Long.toString(clock.getAsLong()),
                        "nextAttemptEpochMs","0","stagingPolicy","synchronous_private_only_no_public_IO_no_full_frame_queue");
                j.state("staged_publication_pending");
            }catch(Exception e) {
                try{j.checkpoint("error",e.toString());j.state("private_stage_failed_original_RAW_retained");}catch(IOException ignored){}
                refreshAdmission();emit(j,false);throw e;
            }
            refreshAdmission();emit(j,false);return j.snapshot();
        }
    }
    /** Called by one scheduled publication worker; never invoked by capture/render/UI threads. */
    public void pump() {
        synchronized(pumpLock) {
            if(!recovered||closed)return;
            for(Job j:ordered()) {
                if(closed)return;
                if("exported".equals(j.get("status"))) {
                    try{releasePayload(j);}catch(IOException ignored){}emit(j,false);continue;
                }
                if(!publishable(j)||j.number("nextAttemptEpochMs",0)>clock.getAsLong())continue;
                long began=System.nanoTime();
                try {
                    j.checkpoint("attempts",Long.toString(j.number("attempts",0)+1),"error","","currentOperation","private_verify");
                    j.state("publishing");
                    try{requirePayload(j,j.payload());}
                    catch(IOException e){j.checkpoint("error",e.toString());j.state("private_stage_corrupt_original_RAW_retained");emit(j,false);continue;}
                    j.metric("privateVerifyMs",began);
                    publisher.publish(j);
                    j.metric("publicPublicationElapsedMs",began);
                    j.checkpoint("publicWriteCompleted","true","publicReadbackVerified","true",
                            "completedEpochMs",Long.toString(clock.getAsLong()),"currentOperation","complete");
                    j.state("exported"); // Durable receipt BEFORE removing private pixels.
                    releasePayload(j);
                }catch(Conflict e) {
                    try{j.checkpoint("error",e.toString());j.state("publication_conflict_private_retained");}catch(IOException ignored){}
                }catch(Exception e) {
                    try {
                        // A failure cleaning up an already verified export must not undo that receipt.
                        if(!"exported".equals(j.get("status"))) {
                            long delay=retryDelay(j.number("attempts",1));
                            j.checkpoint("error",e.toString(),"retryDelayMs",Long.toString(delay),
                                    "nextAttemptEpochMs",Long.toString(clock.getAsLong()+delay));
                            j.state("publication_retry_pending");
                        } else j.checkpoint("privateCleanupError",e.toString());
                    }catch(IOException ignored){}
                }
                refreshAdmission();emit(j,false);
            }
            refreshAdmission();pruneReceipts();
        }
    }
    public static long retryDelay(long attempts){return Math.min(60000L,1000L<<Math.min(6,Math.max(0,attempts-1)));}
    private boolean publishable(Job j){return "staged_publication_pending".equals(j.get("status"))||"publication_retry_pending".equals(j.get("status"));}
    private List<Job> ordered(){List<Job> v=new ArrayList<>(jobs.values());v.sort(Comparator.comparingLong(j->j.number("createdEpochMs",0)));return v;}
    private void emit(Job j,boolean force) {
        synchronized(j.p) {
            long seq=j.number("statusSequence",0);
            if(!force&&j.number("reportedSequence",-1)>=seq)return;
            try{if(listener.record(j.snapshot()))j.checkpoint("reportedSequence",Long.toString(seq));}catch(Exception ignored){}
        }
    }
    public void refreshAdmission() {
        int count=0;long bytes=0;
        for(Job j:jobs.values())if(!"exported".equals(j.get("status"))||!"true".equals(j.get("privatePayloadReleased"))) {
            count++;bytes+=j.number("stagedBytes",j.number("reservedBytes",0));
        }
        String reason=!recovered?"initializing_private_export_store":closed?"private_export_store_closed":
                count>=policy.softJobs||bytes>=policy.softBytes?"saving_monochrome_DNG_backlog":
                freeBytes.getAsLong()<policy.reserveBytes?"low_storage_for_monochrome_DNG":"ready";
        admission=new Admission("ready".equals(reason),reason,count,bytes);
    }
    private void releasePayload(Job j) throws IOException {
        if(!"exported".equals(j.get("status")))throw new IOException("cannot_release_unpublished_pixels");
        Files.deleteIfExists(j.payload());Files.deleteIfExists(j.dir.resolve("payload.part"));
        if(!"true".equals(j.get("privatePayloadReleased")))j.checkpoint("privatePayloadReleased","true");
    }
    private void pruneReceipts() {
        List<Job> done=new ArrayList<>();for(Job j:ordered())if("exported".equals(j.get("status"))&&
                "true".equals(j.get("privatePayloadReleased"))&&j.number("reportedSequence",-1)>=j.number("statusSequence",0))done.add(j);
        for(int i=0;i<done.size()-policy.receipts;i++) {
            Job j=done.get(i);
            try{Files.deleteIfExists(j.dir.resolve("job.properties.new"));Files.delete(j.dir.resolve("job.properties"));Files.delete(j.dir);
                jobs.remove(j.dir.getFileName().toString(),j);}catch(IOException ignored){}
        }
    }
    public List<Properties> snapshots(){List<Properties> out=new ArrayList<>();for(Job j:ordered())out.add(j.snapshot());return out;}
    private static void requirePayload(Job j,Path file) throws IOException {
        if(!Files.isRegularFile(file)||Files.size(file)!=j.number("stagedBytes",-1)||!hashFile(file).equals(j.get("payloadSha256")))
            throw new IOException("private_payload_integrity_mismatch");
    }
    static void saveProperties(Path file,Properties p) throws IOException {
        Path temp=file.resolveSibling(file.getFileName()+".new");
        try(FileOutputStream raw=new FileOutputStream(temp.toFile())){p.store(raw,"MONOOUTPUT1B durable job");raw.flush();raw.getFD().sync();}
        moveAtomic(temp,file);
    }
    static Properties loadProperties(Path file) throws IOException {
        Properties p=new Properties();try(InputStream in=Files.newInputStream(file)){p.load(in);}return p;
    }
    static void moveAtomic(Path from,Path to) throws IOException {
        // Same private filesystem. Never downgrade to copying a half-written manifest into place.
        Files.move(from,to,StandardCopyOption.ATOMIC_MOVE,StandardCopyOption.REPLACE_EXISTING);
    }
    public static String hashFile(Path file) throws IOException {try(InputStream in=Files.newInputStream(file)){return hashStream(in,-1);}}
    public static String hashStream(InputStream in,long expected) throws IOException {
        try {
            MessageDigest d=MessageDigest.getInstance("SHA-256");byte[] block=new byte[65536];long count=0;int n;
            while((n=in.read(block))!=-1){count+=n;if(expected>=0&&count>expected)throw new IOException("public_length_excess");d.update(block,0,n);}
            if(expected>=0&&count!=expected)throw new IOException("public_length_mismatch");return hex(d.digest());
        }catch(java.security.NoSuchAlgorithmException e){throw new IOException(e);}
    }
    private static String hashBytes(byte[] bytes) throws Exception{return hex(MessageDigest.getInstance("SHA-256").digest(bytes));}
    private static String hex(byte[] bytes){StringBuilder s=new StringBuilder();for(byte b:bytes)s.append(String.format(Locale.ROOT,"%02x",b&255));return s.toString();}
    private static final class BoundedCount extends OutputStream {
        private final OutputStream out;private final long max;long count;
        BoundedCount(OutputStream out,long max){this.out=out;this.max=max;}
        public void write(int b)throws IOException{if(count>=max)throw new IOException("encoder_exceeds_reserved_bytes");out.write(b);count++;}
        public void write(byte[] b,int o,int n)throws IOException{if(n<0||count>max-n)throw new IOException("encoder_exceeds_reserved_bytes");out.write(b,o,n);count+=n;}
        public void flush()throws IOException{out.flush();}
    }
    public synchronized void close() throws IOException {
        closed=true;refreshAdmission();if(ownerLock!=null&&ownerLock.isValid())ownerLock.release();if(lockChannel!=null)lockChannel.close();
    }
}
