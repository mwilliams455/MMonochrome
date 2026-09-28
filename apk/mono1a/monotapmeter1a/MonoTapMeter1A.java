package com.particlesdevs.photoncamera.m9.preview;

import java.util.Arrays;
import org.json.JSONArray;
import org.json.JSONException;
import org.json.JSONObject;

/**
 * MONOTAPMETER1A: one explicit, screen-fixed Monochrom exposure subject.
 *
 * The selection supplies photographic intent only.  It never edits pixels,
 * never creates a local exposure, and never owns the capture independently of
 * the shared Monochrom exposure plan.
 */
public final class MonoTapMeter1A {
    public static final String REVISION="MONOTAPMETER1A";
    public static final long LIFETIME_NS=15_000_000_000L;
    private static final long GEOMETRY_MAX_AGE_NS=750_000_000L;
    private static long serial;
    private static Geometry geometry;
    private static long geometryTimeNs;
    private static Selection selected;
    private static volatile String status="AUTO";

    private MonoTapMeter1A() {}

    public static final class Geometry {
        public final String camera,mode;
        public final int width,height,x,y,w,h,probeWidth,probeHeight,transform;
        public final boolean mirror;
        Geometry(String camera,String mode,int width,int height,int x,int y,int w,int h,
                int probeWidth,int probeHeight,int transform,boolean mirror) {
            this.camera=camera;this.mode=mode;this.width=width;this.height=height;
            this.x=x;this.y=y;this.w=w;this.h=h;this.probeWidth=probeWidth;
            this.probeHeight=probeHeight;this.transform=transform;this.mirror=mirror;
        }
        boolean same(Geometry b) {
            return b!=null && camera.equals(b.camera) && mode.equals(b.mode)
                    && width==b.width && height==b.height && x==b.x && y==b.y
                    && w==b.w && h==b.h && probeWidth==b.probeWidth
                    && probeHeight==b.probeHeight && transform==b.transform
                    && mirror==b.mirror;
        }
    }

    public static final class Selection {
        public final long id,createdNs,expiryNs;
        public final Geometry geometry;
        public final double viewX,viewY;
        public final int x0,y0,x1,y1;
        Selection(long id,long now,Geometry geometry,double viewX,double viewY,int[] r) {
            this.id=id;this.createdNs=now;this.expiryNs=now+LIFETIME_NS;
            this.geometry=geometry;this.viewX=viewX;this.viewY=viewY;
            x0=r[0];y0=r[1];x1=r[2];y1=r[3];
        }
        public double[] viewRect() {
            Geometry g=geometry;
            return new double[]{
                    g.x+x0*g.w/(double)g.probeWidth,
                    g.height-g.y-y1*g.h/(double)g.probeHeight,
                    g.x+x1*g.w/(double)g.probeWidth,
                    g.height-g.y-y0*g.h/(double)g.probeHeight};
        }
        public JSONObject json(long now) throws JSONException {
            return new JSONObject()
                    .put("active",true).put("generation",id)
                    .put("ageMs",(now-createdNs)/1e6)
                    .put("expiresInMs",Math.max(0L,expiryNs-now)/1e6)
                    .put("cameraKey",geometry.camera).put("mode",geometry.mode)
                    .put("screenPoint",array(viewX,viewY))
                    .put("viewSize",array(geometry.width,geometry.height))
                    .put("viewport",array(geometry.x,geometry.y,geometry.w,geometry.h))
                    .put("probeSize",array(geometry.probeWidth,geometry.probeHeight))
                    .put("sampledPatch",array(x0,y0,x1,y1))
                    .put("sampleCount",(x1-x0)*(y1-y0))
                    .put("mapping","display_GL_viewport_UI_top_to_probe_GL_bottom_once")
                    .put("tracking","fixed_screen_patch_not_object_tracking")
                    .put("lifetimeMs",LIFETIME_NS/1_000_000L);
        }
    }

    public static synchronized void configure(String camera,String mode,long now,
            int width,int height,int[] viewport,float[] transform,boolean mirror,
            int probeWidth,int probeHeight) {
        if(camera==null||mode==null||width<=0||height<=0||viewport==null||viewport.length!=4
                ||viewport[2]<=0||viewport[3]<=0||probeWidth<=0||probeHeight<=0) {
            clear("geometry_unavailable");geometry=null;return;
        }
        Geometry next=new Geometry(camera,mode,width,height,viewport[0],viewport[1],
                viewport[2],viewport[3],probeWidth,probeHeight,Arrays.hashCode(transform),mirror);
        if(!next.same(geometry)) { clear("camera_mode_or_geometry_change");geometry=next; }
        geometryTimeNs=now;
    }

    public static synchronized Geometry currentGeometry(long now) {
        return geometry!=null && now>=geometryTimeNs && now-geometryTimeNs<=GEOMETRY_MAX_AGE_NS
                ?geometry:null;
    }

    public static synchronized Selection selection(long now) {
        if(selected!=null && now<selected.createdNs)return null;
        if(selected!=null && now>=selected.expiryNs)clear("expired");
        return selected;
    }

    public static synchronized long epoch() { return serial; }

    public static synchronized void clear(String reason) {
        if(selected!=null){selected=null;serial++;}
        status="AUTO";
    }

    public static synchronized boolean choose(double x,double y,long now) {
        Geometry g=currentGeometry(now);if(g==null)return false;
        int[] r=map(x,y,g);
        if(r==null)return false;
        selected=new Selection(++serial,now,g,x,y,r);
        status="TAP …";
        return true;
    }

    public static synchronized boolean insideSelection(double x,double y,long now) {
        Selection s=selection(now);if(s==null)return false;
        double[] r=s.viewRect();return x>=r[0]&&x<r[2]&&y>=r[1]&&y<r[3];
    }

    public static synchronized void status(long generation,String next) {
        if(selected!=null && selected.id==generation && next!=null)status=next;
    }

    public static String status() { return status; }

    /**
     * Display and probe use the same shader rotation/mirror/crop.  Do not invert
     * sensor rotation again.  Only the UI-top -> GL-bottom convention is changed.
     */
    static int[] map(double x,double y,Geometry g) {
        if(!Double.isFinite(x)||!Double.isFinite(y)||x<0||x>=g.width||y<0||y>=g.height)
            return null;
        double gx=x-g.x,gy=g.height-y-g.y;
        if(gx<0||gx>=g.w||gy<0||gy>g.h)return null;
        double half=.10*Math.min(Math.min(g.width,g.height),Math.min(g.w,g.h));
        double left=Math.max(0,Math.max(g.x,x-half));
        double right=Math.min(g.width,Math.min(g.x+g.w,x+half));
        double top=Math.max(0,Math.max(g.height-g.y-g.h,y-half));
        double bottom=Math.min(g.height,Math.min(g.height-g.y,y+half));
        int x0=Math.max(0,(int)Math.floor((left-g.x)*g.probeWidth/g.w));
        int x1=Math.min(g.probeWidth,(int)Math.ceil((right-g.x)*g.probeWidth/g.w));
        int y0=Math.max(0,(int)Math.floor((g.height-bottom-g.y)*g.probeHeight/g.h));
        int y1=Math.min(g.probeHeight,(int)Math.ceil((g.height-top-g.y)*g.probeHeight/g.h));
        if(x1<=x0||y1<=y0||(x1-x0)*(y1-y0)<4)return null;
        return new int[]{x0,y0,x1,y1};
    }

    private static JSONArray array(double... values) {
        JSONArray out=new JSONArray();for(double v:values)out.put(v);return out;
    }
}
