package com.particlesdevs.photoncamera.m9.exposure;

import android.hardware.camera2.CameraCharacteristics;
import android.util.Range;

/** First-generation Leica M Monochrom automatic-bracketing math. */
public final class MonoBracket1H {
    public static final String REVISION="LEICABRACKET1A";
    public static final int SEQUENCE_ZERO_PLUS_MINUS=0;
    public static final int SEQUENCE_MINUS_ZERO_PLUS=1;
    private MonoBracket1H(){}

    public static int clampFrames(int frames){
        return frames==5?5:(frames==7?7:3);
    }
    /** Step is encoded in half-stops: 1=.5EV, 2=1EV, 3=1.5EV, 4=2EV. */
    public static int clampHalfStops(int frames,int halfStops){
        int v=Math.max(1,Math.min(4,halfStops));
        return clampFrames(frames)==7?Math.min(2,v):v;
    }
    public static int clampSequence(int sequence){
        return sequence==SEQUENCE_MINUS_ZERO_PLUS?SEQUENCE_MINUS_ZERO_PLUS:SEQUENCE_ZERO_PLUS_MINUS;
    }
    public static double stepEv(int frames,int halfStops){
        return 0.5*clampHalfStops(frames,halfStops);
    }
    public static double[] offsets(int frames,int sequence,int halfStops){
        frames=clampFrames(frames);
        sequence=clampSequence(sequence);
        final double step=stepEv(frames,halfStops);
        final int side=(frames-1)/2;
        double[] out=new double[frames];
        if(sequence==SEQUENCE_MINUS_ZERO_PLUS){
            int k=0;
            for(int n=-side;n<=side;n++)out[k++]=n*step;
        }else{
            out[0]=0.0;
            int k=1;
            for(int n=1;n<=side;n++){
                out[k++]=n*step;
                out[k++]=-n*step;
            }
        }
        return out;
    }
    public static long bracketExposureNs(long baseExposureNs,double offsetEv,
            CameraCharacteristics chars){
        if(baseExposureNs<=0||!Double.isFinite(offsetEv))
            throw new IllegalArgumentException("invalid_bracket_input");
        Range<Long> range=chars==null?null:chars.get(CameraCharacteristics.SENSOR_INFO_EXPOSURE_TIME_RANGE);
        long lo=range==null?1L:Math.max(1L,range.getLower());
        long hi=range==null?Long.MAX_VALUE:Math.max(lo,range.getUpper());
        double raw=baseExposureNs*Math.pow(2.0,offsetEv);
        long value;
        if(!Double.isFinite(raw)||raw>=Long.MAX_VALUE)value=hi;
        else value=Math.round(raw);
        return Math.max(lo,Math.min(hi,value));
    }
}
