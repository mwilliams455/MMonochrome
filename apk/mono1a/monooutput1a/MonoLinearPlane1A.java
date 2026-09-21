package com.particlesdevs.photoncamera.m9.export;

/** A derived scene-linear luminance plane, not Leica sensor data or a JPEG conversion. */
public final class MonoLinearPlane1A {
    public interface Rows { int read(int row, short[] rgb); }
    public final int width, height;
    public final short[] pixels;
    public final double sourceUnitsPerWhite, quantizationStep, representationScale;
    public final float[] weights;
    public final long negativeCount, aboveJpegWhiteCount, sensorChannelClipCount;
    public final double maxSource;
    private MonoLinearPlane1A(int w,int h,short[] p,double range,double scale,float[] weights,
            long negative,long above,long clipped,double max) {
        width=w;height=h;pixels=p;sourceUnitsPerWhite=range;representationScale=scale;
        quantizationStep=range/65535.0;this.weights=weights.clone();negativeCount=negative;
        aboveJpegWhiteCount=above;sensorChannelClipCount=clipped;maxSource=max;
    }
    public static MonoLinearPlane1A create(int width,int height,int rotation,float[] weights,
            double scale,Rows rows) {
        if(width<=0||height<=0||weights==null||weights.length!=3||rows==null||
                !Double.isFinite(scale)||scale<=0)throw new IllegalArgumentException("source_contract");
        int count=Math.multiplyExact(width,height);
        if(count>80000000)throw new IllegalArgumentException("export_memory_limit");
        int rot=((rotation%360)+360)%360;
        if(rot%90!=0)throw new IllegalArgumentException("rotation");
        double positive=0;
        for(float weight:weights){if(!Float.isFinite(weight))throw new IllegalArgumentException("weight");positive+=Math.max(0,weight);}
        if(!(positive>0))throw new IllegalArgumentException("nonpositive_luminance");
        // Conservative metadata-derived bound, not a scene-max exposure normalization.
        double divisor=Math.max(1,positive),range=scale*divisor;
        if(!Double.isFinite(range)||range>256)throw new IllegalArgumentException("headroom_range");
        int ow=(rot==90||rot==270)?height:width,oh=(rot==90||rot==270)?width:height;
        short[] output=new short[count],row=new short[Math.multiplyExact(width,3)];
        long neg=0,above=0,clipped=0;double max=0;
        for(int y=0;y<height;y++){
            if(rows.read(y,row)!=row.length)throw new IllegalArgumentException("incomplete_RGB_row");
            for(int x=0;x<width;x++){
                int i=3*x,r=row[i]&65535,g=row[i+1]&65535,b=row[i+2]&65535;
                if(r==65535||g==65535||b==65535)clipped++;
                double s=(double)weights[0]*r+(double)weights[1]*g+(double)weights[2]*b;
                if(s<0)neg++;
                double source=Math.max(0,s)*scale/65535.0;
                if(source>1)above++;max=Math.max(max,source);
                long q=Math.round(Math.max(0,s)/divisor);
                if(q>65535)throw new IllegalStateException("quantization_bound");
                int dx=x,dy=y;
                if(rot==90){dx=height-1-y;dy=x;}else if(rot==180){dx=width-1-x;dy=height-1-y;}
                else if(rot==270){dx=y;dy=width-1-x;}
                output[dy*ow+dx]=(short)q;
            }
        }
        return new MonoLinearPlane1A(ow,oh,output,range,scale,weights,neg,above,clipped,max);
    }
}
