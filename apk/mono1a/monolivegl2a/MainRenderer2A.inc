    // MONOLIVEGL2A_CONTROLLEDOES
    private int monoProgram2A, monoInverseTex2A, monoCurveTex2A;
    private int monoReady2A, monoUndo2A, monoY2A, monoProbeUniform2A;
    private boolean monoCurveLoaded2A, boundSourceReady2A;
    private com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.Context boundContext2A;
    private long nextProbeNs2A;
    private int probeFbo2A, probeTex2A, probeWidth2A, probeHeight2A;
    private ByteBuffer probeBuffer2A;
    private String probeError2A;
    private long probeCostNs2A;

    private void initMonoTextures2A(int program) {
        monoProgram2A=program;
        monoReady2A=GLES20.glGetUniformLocation(program,"uMonoSourceReady2A");
        monoUndo2A=GLES20.glGetUniformLocation(program,"uMonoInputToSensor2A");
        monoY2A=GLES20.glGetUniformLocation(program,"uMonoSourceY2A");
        monoProbeUniform2A=GLES20.glGetUniformLocation(program,"uMonoProbe2A");
        GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"sTexture"),0);
        GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"uMonoInverse2A"),1);
        GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"uMonoCurve2A"),2);
        boundContext2A=null; monoCurveLoaded2A=false; nextProbeNs2A=0;
        probeFbo2A=0; probeTex2A=0; probeBuffer2A=null; probeError2A=null;
        int[] ids=new int[2]; GLES20.glGenTextures(2,ids,0);
        monoInverseTex2A=ids[0]; monoCurveTex2A=ids[1];
        GLES20.glActiveTexture(GLES20.GL_TEXTURE1);
        texture2A(monoInverseTex2A,GLES20.GL_NEAREST);
        GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES20.GL_RGBA,1,1,0,GLES20.GL_RGBA,
                GLES20.GL_UNSIGNED_BYTE,ByteBuffer.allocateDirect(4));
        GLES20.glActiveTexture(GLES20.GL_TEXTURE2);
        texture2A(monoCurveTex2A,GLES20.GL_NEAREST);
        // Complete sampler even if the asset is unavailable: source-ready then remains false.
        GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES20.GL_RGBA,1,1,0,GLES20.GL_RGBA,
                GLES20.GL_UNSIGNED_BYTE,ByteBuffer.allocateDirect(4));
        try(java.io.InputStream in=mView.getContext().getAssets().open("mono/mono_curve02_gl2a.bin")) {
            byte[] data=new byte[2048]; int offset=0,n;
            while(offset<data.length && (n=in.read(data,offset,data.length-offset))>0) offset+=n;
            if(offset!=2048 || in.read()!=-1) throw new java.io.IOException("curve_length");
            byte[] hash=java.security.MessageDigest.getInstance("SHA-256").digest(data);
            StringBuilder text=new StringBuilder(); for(byte b:hash) text.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
            if(!text.toString().equals(com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.CURVE_SHA))
                throw new java.io.IOException("curve_checksum");
            ByteBuffer bytes=ByteBuffer.allocateDirect(2048); bytes.put(data).position(0);
            GLES30.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES30.GL_R8,2048,1,0,GLES30.GL_RED,
                    GLES20.GL_UNSIGNED_BYTE,bytes);
            int curveError=GLES20.glGetError();
            if(curveError!=GLES20.GL_NO_ERROR) throw new java.io.IOException("curve_GL_error_"+curveError);
            monoCurveLoaded2A=true;
        } catch(Exception e) { Log.e("MonoGL2A","curve unavailable: "+e); }
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
    }
    private static void texture2A(int id,int filter) {
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,id);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_WRAP_S,GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_WRAP_T,GLES20.GL_CLAMP_TO_EDGE);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_MIN_FILTER,filter);
        GLES20.glTexParameteri(GLES20.GL_TEXTURE_2D,GLES20.GL_TEXTURE_MAG_FILTER,filter);
    }
    private void bindMono2A(com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.Context c) {
        boundSourceReady2A=false;
        GLES20.glActiveTexture(GLES20.GL_TEXTURE1);
        GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,monoInverseTex2A);
        if(c.ready && c!=boundContext2A) {
            byte[] data=c.inverse(); ByteBuffer bytes=ByteBuffer.allocateDirect(data.length); bytes.put(data).position(0);
            GLES20.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES20.GL_RGBA,1024,2,0,GLES20.GL_RGBA,
                    GLES20.GL_UNSIGNED_BYTE,bytes);
            GLES20.glUniformMatrix3fv(monoUndo2A,1,false,c.undo(),0);
            GLES20.glUniform3fv(monoY2A,1,c.y(),0);
            int sourceError=GLES20.glGetError();
            if(sourceError==GLES20.GL_NO_ERROR) boundContext2A=c;
            else {boundContext2A=null;probeError2A="source_GL_error_"+sourceError;}
        }
        boundSourceReady2A=c.ready && monoCurveLoaded2A && boundContext2A==c;
        GLES20.glUniform1i(monoReady2A,boundSourceReady2A?1:0);
        GLES20.glActiveTexture(GLES20.GL_TEXTURE2); GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,monoCurveTex2A);
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0); GLES20.glBindTexture(GLES11Ext.GL_TEXTURE_EXTERNAL_OES,hTex[0]);
    }
    /** Once/second at most; still capture never waits for the GL thread or this readback. */
    private byte[] probeMono2A(long now) {
        if(now<nextProbeNs2A) return null;
        nextProbeNs2A=now+1000000000L;
        int[] viewport=new int[4], drawFbo=new int[1],readFbo=new int[1];
        GLES20.glGetIntegerv(GLES20.GL_VIEWPORT,viewport,0);
        GLES30.glGetIntegerv(GLES30.GL_DRAW_FRAMEBUFFER_BINDING,drawFbo,0);
        GLES30.glGetIntegerv(GLES30.GL_READ_FRAMEBUFFER_BINDING,readFbo,0);
        long begin=android.os.SystemClock.elapsedRealtimeNanos();
        try {
            int w=viewport[2]>viewport[3]?64:48, h=viewport[2]>viewport[3]?48:64;
            if(probeFbo2A==0) {int[] id=new int[1];GLES20.glGenFramebuffers(1,id,0);probeFbo2A=id[0];
                GLES20.glGenTextures(1,id,0);probeTex2A=id[0];}
            GLES20.glActiveTexture(GLES20.GL_TEXTURE3); texture2A(probeTex2A,GLES20.GL_NEAREST);
            GLES20.glBindFramebuffer(GLES20.GL_FRAMEBUFFER,probeFbo2A);
            if(probeBuffer2A==null || w!=probeWidth2A || h!=probeHeight2A) {
                GLES30.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES30.GL_RGBA8,w,h,0,GLES20.GL_RGBA,GLES20.GL_UNSIGNED_BYTE,null);
                GLES20.glFramebufferTexture2D(GLES20.GL_FRAMEBUFFER,GLES20.GL_COLOR_ATTACHMENT0,GLES20.GL_TEXTURE_2D,probeTex2A,0);
                probeBuffer2A=ByteBuffer.allocateDirect(w*h*4);probeWidth2A=w;probeHeight2A=h;
            }
            if(GLES20.glCheckFramebufferStatus(GLES20.GL_FRAMEBUFFER)!=GLES20.GL_FRAMEBUFFER_COMPLETE)
                throw new IllegalStateException("probe_framebuffer_incomplete");
            GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
            GLES20.glViewport(0,0,w,h); GLES20.glUniform1i(monoProbeUniform2A,1);
            GLES20.glDrawArrays(GLES20.GL_TRIANGLE_STRIP,0,4);
            probeBuffer2A.position(0);
            GLES20.glReadPixels(0,0,w,h,GLES20.GL_RGBA,GLES20.GL_UNSIGNED_BYTE,probeBuffer2A);
            int error=GLES20.glGetError(); if(error!=GLES20.GL_NO_ERROR) throw new IllegalStateException("gl_error_"+error);
            byte[] data=new byte[w*h*4];probeBuffer2A.position(0);probeBuffer2A.get(data);probeError2A=null;
            return data;
        } catch(Exception e) {probeError2A=e.toString(); return null;}
        finally {
            probeCostNs2A=android.os.SystemClock.elapsedRealtimeNanos()-begin;
            GLES20.glUniform1i(monoProbeUniform2A,0);
            GLES30.glBindFramebuffer(GLES30.GL_DRAW_FRAMEBUFFER,drawFbo[0]);
            GLES30.glBindFramebuffer(GLES30.GL_READ_FRAMEBUFFER,readFbo[0]);
            GLES20.glViewport(viewport[0],viewport[1],viewport[2],viewport[3]);
            GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
        }
    }
