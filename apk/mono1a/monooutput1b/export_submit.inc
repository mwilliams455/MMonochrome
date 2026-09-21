    public static JSONObject submit(Pending pending,Path originalDng,CaptureResult result,String cameraId) {
        JSONObject reply=new JSONObject();
        if(pending==null){note(reply,"status","no_linear_plane_original_RAW_retained");return reply;}
        Path output=originalDng.resolveSibling(stem(originalDng)+"_MONO_LINEAR1A.dng");
        try {
            JSONObject immutable=new JSONObject(pending.diagnostic.toString());
            immutable.put("outputPath",output.toString()).put("originalDngPath",originalDng.toString());
            // Preserve the original DNG's image/EXIF description. Transport fields are sidecar-only.
            MonoDngWriter1A.Metadata m=metadata(originalDng,result,cameraId,immutable.toString());
            startRecovery();
            if(!READY.await(5,TimeUnit.SECONDS)||!startupError.isEmpty()||store==null)
                throw new java.io.IOException("private_export_store_not_ready:"+startupError);
            byte[] thumb=pending.thumbnail;int tw=pending.thumbWidth,th=pending.thumbHeight;
            if(thumb==null){thumb=new byte[]{0,0,0};tw=1;th=1;immutable.put("thumbnailStatus","unavailable_black_placeholder");}
            else immutable.put("thumbnailStatus","primary_JPEG_appearance_preview_only");
            final byte[] bytes=thumb;final int w=tw,h=th;
            long bound=Math.addExact(Math.multiplyExact((long)pending.plane.width*pending.plane.height,2L),2L<<20);
            java.util.Properties state=store.stage(output,immutable.toString(),bound,
                    out->MonoDngWriter1A.write(out,pending.plane,m,w,h,bytes));
            reply=statusJson1B(state);
        }catch(Exception e){
            if(e instanceof InterruptedException)Thread.currentThread().interrupt();
            note(reply,"revision",MonoDngSpool1B.REVISION);
            note(reply,"status","private_stage_failed_original_RAW_retained");note(reply,"error",e.toString());
            note(reply,"originalRawRetained",true);note(reply,"outputPath",output.toString());stage(output,reply);
            PhotonCamera.showToast("The photograph and original RAW are retained, but its monochrome DNG could not be staged. Check storage and diagnostics.");
        }
        return reply;
    }
    private static JSONObject statusJson1B(java.util.Properties status)throws Exception {
        JSONObject d=new JSONObject(status.getProperty("diagnosticJson","{}"));
        d.put("dataRevision",REVISION);
        for(String key:status.stringPropertyNames()) {
            if(key.equals("diagnosticJson"))continue;
            String value=status.getProperty(key);
            if(value.equals("true")||value.equals("false"))d.put(key,Boolean.parseBoolean(value));
            else if(key.endsWith("Ms")||key.endsWith("Bytes")||key.equals("attempts")||key.equals("statusSequence")||key.equals("reportedSequence")) {
                try{d.put(key,Double.parseDouble(value));}catch(NumberFormatException e){d.put(key,value);}
            } else d.put(key,value);
        }
        d.put("retryPolicy","durable_private_job_exponential_1_to_60_seconds_while_process_runs_resume_on_app_start");
        d.put("publicationProtocol","verified_private_payload_to_unique_public_temporary_then_rename_then_final_readback");
        d.put("fullResolutionMemoryQueue",false);
        return d;
    }
    private static boolean recordStatus1B(java.util.Properties state) {
        try {
            String path=state.getProperty("outputPath","");if(path.isEmpty())return false;
            JSONObject d=statusJson1B(state);Path output=java.nio.file.Paths.get(path);
            Path json=output.resolveSibling(stem(output)+"_EXPORT.json");
            return M9DiagnosticBurstSpool.stage(json,d.toString(2).getBytes(StandardCharsets.UTF_8),"monochrome_dng_export");
        }catch(Exception e){Log.e("MonoDng1B","durable status retained for replay",e);return false;}
    }
