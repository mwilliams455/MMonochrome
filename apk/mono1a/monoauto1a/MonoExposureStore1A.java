package com.particlesdevs.photoncamera.m9.exposure;

import java.util.ArrayDeque;
import java.util.Iterator;

/** Controller-local state. No global camera settings, blocking waits, or image buffers. */
public final class MonoExposureStore1A {
    private long epoch=1;
    private String camera="";
    private MonoExposurePlan1A.Controls controls;
    private MonoExposurePlan1A latest;
    private final ArrayDeque<Draw> draws=new ArrayDeque<>();
    public synchronized void invalidate() { epoch++; latest=null; draws.clear(); }
    public synchronized long context(String camera, MonoExposurePlan1A.Controls controls) {
        if(!this.camera.equals(camera) || !controls.equals(this.controls)) {
            invalidate();this.camera=camera;this.controls=controls;
        }
        return epoch;
    }
    public synchronized boolean accepts(MonoExposurePlan1A p,long now) {
        return p!=null && p.validFor(camera,controls,epoch,now);
    }
    public synchronized boolean publish(MonoExposurePlan1A p,long now) {
        if(!accepts(p,now) || (latest!=null && p.createdNs<latest.createdNs)) return false;
        latest=p;return true;
    }
    public synchronized MonoExposurePlan1A latest(long now) { return accepts(latest,now)?latest:null; }
    public synchronized void drawn(MonoExposurePlan1A p,long now,long textureNs,float scale) {
        if(!accepts(p,now) || !Float.isFinite(scale) || scale<=0) return;
        draws.addLast(new Draw(p,now,textureNs,scale));
        while(draws.size()>48) draws.removeFirst();
    }
    public synchronized Selection select(long shutterNs) {
        for(Iterator<Draw> i=draws.descendingIterator();i.hasNext();) {
            Draw d=i.next();
            if(accepts(d.plan,shutterNs) && d.elapsedNs<=shutterNs && shutterNs-d.elapsedNs<=500000000L)
                return new Selection(d.plan,"recent_pre_shutter_GL_draw",d.elapsedNs,d.textureNs,d.scale);
        }
        MonoExposurePlan1A p=latest(shutterNs);
        return new Selection(p,p==null?"no_current_plan":"current_plan_no_recent_GL_acknowledgement",
                -1,-1,p==null?1.0f:MonoExposurePlan1A.boundedScale(p.previewScale()));
    }
    private static final class Draw {
        final MonoExposurePlan1A plan;final long elapsedNs,textureNs;final float scale;
        Draw(MonoExposurePlan1A p,long n,long t,float s){plan=p;elapsedNs=n;textureNs=t;scale=s;}
    }
    public static final class Selection {
        public final MonoExposurePlan1A plan; public final String reason;
        public final long drawElapsedNs,textureTimestampNs; public final float scale;
        public Selection(MonoExposurePlan1A p,String why,long n,long t,float s){plan=p;reason=why;drawElapsedNs=n;textureTimestampNs=t;scale=s;}
    }
    /** One atomic publication to the GL thread, never independent ISO/shutter fields. */
    public static final class Presentation {
        public final MonoExposurePlan1A plan;public final MonoExposureStore1A store;
        public Presentation(MonoExposurePlan1A p,MonoExposureStore1A s){plan=p;store=s;}
    }
}
