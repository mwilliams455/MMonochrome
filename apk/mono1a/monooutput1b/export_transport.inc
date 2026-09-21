    // MONOOUTPUT1B: no executor contains Pending/plane/Bitmap objects. Only durable paths are published.
    private static final Object START_LOCK=new Object();
    private static final java.util.concurrent.CountDownLatch READY=new java.util.concurrent.CountDownLatch(1);
    private static final java.util.concurrent.ScheduledThreadPoolExecutor PUBLISHER=
            new java.util.concurrent.ScheduledThreadPoolExecutor(1,r->{
                Thread t=new Thread(r,"MonoDngPublish1B");t.setDaemon(true);return t;
            });
    private static volatile MonoDngSpool1B store;
    private static volatile String startupError="";
    public static void startRecovery() {
        synchronized(START_LOCK) {
            if(store!=null)return;
            android.content.Context context=PhotonCamera.getAppContext();if(context==null)return;
            Path root=context.getFilesDir().toPath().resolve("mono_dng_jobs1b");
            store=new MonoDngSpool1B(root,MonoDngSpool1B.Policy.normal(),System::currentTimeMillis,
                    ()->context.getFilesDir().getUsableSpace(),new MonoDngPublicWriter1B(context),MonoDngExport1A::recordStatus1B);
            PUBLISHER.setRemoveOnCancelPolicy(true);
            PUBLISHER.execute(()->{
                android.os.Process.setThreadPriority(android.os.Process.THREAD_PRIORITY_BACKGROUND);
                try{store.recover();}catch(Exception e){startupError=e.toString();Log.e("MonoDng1B","private recovery failed",e);}
                finally{READY.countDown();}
            });
            // Fixed-size scheduler: no runnable per shot, no queued full-resolution image ownership.
            PUBLISHER.scheduleWithFixedDelay(()->{
                try{store.pump();}catch(Exception e){Log.e("MonoDng1B","publication pump retained its durable jobs",e);}
            },1,2,TimeUnit.SECONDS);
        }
    }
    public static boolean admitCapture1B() {
        startRecovery();MonoDngSpool1B s=store;
        if(s!=null&&startupError.isEmpty()&&s.admission().allowed)return true;
        String reason=s==null?"initializing_private_export_store":s.admission().reason;
        String text=!startupError.isEmpty()?"Monochrome DNG storage could not open. Restart the camera; existing files are retained.":
                reason.equals("low_storage_for_monochrome_DNG")?"Storage is nearly full. Free space before taking another photograph.":
                reason.equals("initializing_private_export_store")?"Preparing monochrome DNG storage. Please try the shutter again.":
                "Saving monochrome DNGs. Please wait before taking another photograph; pending files are retained.";
        PhotonCamera.showToast(text);return false;
    }
