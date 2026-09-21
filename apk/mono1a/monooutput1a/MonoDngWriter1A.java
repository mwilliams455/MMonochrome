package com.particlesdevs.photoncamera.m9.export;

import java.io.IOException;
import java.io.OutputStream;
import java.nio.ByteBuffer;
import java.nio.ByteOrder;
import java.nio.charset.StandardCharsets;
import java.util.Map;
import java.util.TreeMap;

/**
 * Minimal uncompressed 16-bit single-channel LinearRaw DNG writer.
 * This product includes DNG technology under license by Adobe.
 * No CFA tags, colour matrices, tone curve, sharpening, or pixel exposure offset.
 */
public final class MonoDngWriter1A {
    private MonoDngWriter1A() {}
    public static final class Metadata {
        public String make="Unknown",model="Unknown",cameraId="unknown",originalName="",
                dateTime="",subsecond="",description="Derived scene-linear monochrome; original RAW retained";
        public int iso;
        public long exposureNs;
        public double aperture,focalLength;
    }
    private static final int BYTE=1,ASCII=2,SHORT=3,LONG=4,RATIONAL=5,UNDEFINED=7,SRATIONAL=10;
    private static int align(int n){return Math.addExact(n,3)&~3;}
    private static ByteBuffer buffer(int n){return ByteBuffer.allocate(n).order(ByteOrder.LITTLE_ENDIAN);}
    private static byte[] shorts(int... values){ByteBuffer b=buffer(values.length*2);for(int v:values)b.putShort((short)v);return b.array();}
    private static byte[] longs(long... values){ByteBuffer b=buffer(values.length*4);for(long v:values){if(v<0||v>0xffffffffL)throw new IllegalArgumentException("TIFF_overflow");b.putInt((int)v);}return b.array();}
    private static byte[] rational(long a,long b){return buffer(8).putInt((int)a).putInt((int)b).array();}
    private static byte[] number(double d){if(!Double.isFinite(d)||d<0||d>100000)throw new IllegalArgumentException("rational");return rational(Math.round(d*10000),10000);}
    private static byte[] ascii(String s){if(s==null)s="";s=s.replace('\0',' ');if(s.length()>16000)throw new IllegalArgumentException("text_size");return (s+"\0").getBytes(StandardCharsets.US_ASCII);}
    private static final class Entry {
        final int type,count;byte[] data;
        Entry(int type,int count,byte[] data){this.type=type;this.count=count;this.data=data;}
    }
    private static final class Ifd {
        final TreeMap<Integer,Entry> tags=new TreeMap<>();
        int start,end;
        void add(int tag,int type,int count,byte[] data){if(tags.put(tag,new Entry(type,count,data))!=null)throw new IllegalArgumentException("duplicate_tag");}
        void u16(int tag,int... v){add(tag,SHORT,v.length,shorts(v));}
        void u32(int tag,long... v){add(tag,LONG,v.length,longs(v));}
        void text(int tag,String s){byte[] a=ascii(s);add(tag,ASCII,a.length,a);}
        int layout(int start){this.start=start;int end=start+2+tags.size()*12+4;for(Entry e:tags.values())if(e.data.length>4)end=align(end)+align(e.data.length);return this.end=align(end);}
        void replaceLongs(int tag,long... v){Entry e=tags.get(tag);byte[] b=longs(v);if(e.type!=LONG||b.length!=e.data.length)throw new IllegalStateException("layout_changed");e.data=b;}
        void write(ByteBuffer b){b.position(start);b.putShort((short)tags.size());int tail=start+2+tags.size()*12+4;
            for(Map.Entry<Integer,Entry> pair:tags.entrySet()){
                Entry e=pair.getValue();b.putShort((short)(int)pair.getKey()).putShort((short)e.type).putInt(e.count);
                if(e.data.length<=4){b.put(e.data);for(int j=e.data.length;j<4;j++)b.put((byte)0);}
                else {tail=align(tail);b.putInt(tail);int position=b.position();b.position(tail);b.put(e.data);b.position(position);tail+=align(e.data.length);}
            }b.putInt(0);
        }
    }
    public static long write(OutputStream output,MonoLinearPlane1A plane,Metadata m,
            int thumbWidth,int thumbHeight,byte[] thumbnailRgb) throws IOException {
        if(output==null||plane==null||m==null||thumbnailRgb==null||thumbWidth<1||thumbHeight<1||
                thumbWidth>512||thumbHeight>512||thumbnailRgb.length!=Math.multiplyExact(Math.multiplyExact(thumbWidth,thumbHeight),3))
            throw new IllegalArgumentException("DNG_contract");
        final int rows=64,stripCount=(plane.height+rows-1)/rows;
        Ifd main=new Ifd(),raw=new Ifd(),exif=new Ifd();
        main.u32(254,1);main.u32(256,thumbWidth);main.u32(257,thumbHeight);main.u16(258,8,8,8);
        main.u16(259,1);main.u16(262,2);main.text(270,m.description);main.text(271,m.make);main.text(272,m.model);
        main.u32(273,0);main.u16(274,1);main.u16(277,3);main.u32(278,thumbHeight);main.u32(279,thumbnailRgb.length);
        main.u16(284,1);main.text(305,"MMonochrome MONODNG1A");if(!m.dateTime.isEmpty())main.text(306,m.dateTime);
        main.u32(330,0);main.u32(34665,0);
        main.add(50706,BYTE,4,new byte[]{1,4,0,0});main.add(50707,BYTE,4,new byte[]{1,1,0,0});
        main.text(50708,"MMonochrome Linear1A / "+m.make+" "+m.model+" / camera "+m.cameraId);
        double compensation=Math.log(plane.sourceUnitsPerWhite)/Math.log(2);
        main.add(50730,SRATIONAL,1,rational(Math.round(compensation*1000000),1000000));
        main.add(50731,RATIONAL,1,rational(1,1));main.add(50732,RATIONAL,1,rational(1,1));
        main.add(50734,RATIONAL,1,rational(1,1));
        main.text(50827,m.originalName);
        // This preview is RGB sRGB (three identical channel values), already oriented upright.
        main.u32(50970,2);
        raw.u32(254,0);raw.u32(256,plane.width);raw.u32(257,plane.height);raw.u16(258,16);
        raw.u16(259,1);raw.u16(262,34892);raw.u32(273,new long[stripCount]);raw.u16(277,1);
        raw.u32(278,rows);raw.u32(279,new long[stripCount]);raw.u16(284,1);raw.u16(339,1);
        raw.u16(50713,1,1);raw.add(50714,RATIONAL,1,rational(0,1));raw.u32(50717,65535);
        raw.add(50718,RATIONAL,2,buffer(16).putInt(1).putInt(1).putInt(1).putInt(1).array());
        raw.u32(50719,0,0);raw.u32(50720,plane.width,plane.height);raw.u32(50829,0,0,plane.height,plane.width);
        exif.add(36864,UNDEFINED,4,new byte[]{'0','2','3','1'});
        if(!m.dateTime.isEmpty()){exif.text(36867,m.dateTime);exif.text(36868,m.dateTime);}
        if(!m.subsecond.isEmpty()){exif.text(37521,m.subsecond);exif.text(37522,m.subsecond);}
        if(m.iso>0){exif.u16(34855,Math.min(65535,m.iso));exif.u16(34864,3);exif.u32(34867,m.iso);}
        if(m.exposureNs>0){long a=m.exposureNs,b=1000000000,g=gcd(a,b);a/=g;b/=g;
            if(a>0xffffffffL){a=Math.round(m.exposureNs/1000.0);b=1000000;g=gcd(a,b);a/=g;b/=g;}
            if(a>0xffffffffL)throw new IllegalArgumentException("exposure_range");exif.add(33434,RATIONAL,1,rational(a,b));}
        if(m.aperture>0)exif.add(33437,RATIONAL,1,number(m.aperture));
        if(m.focalLength>0)exif.add(37386,RATIONAL,1,number(m.focalLength));
        exif.u16(40961,1);exif.u32(40962,plane.width);exif.u32(40963,plane.height);
        int rawStart=main.layout(8),exifStart=raw.layout(rawStart),thumbStart=exif.layout(exifStart);
        int pixelStart=align(Math.addExact(thumbStart,thumbnailRgb.length));
        long length=Math.addExact(pixelStart,Math.multiplyExact((long)plane.pixels.length,2));
        if(length>0xffffffffL)throw new IllegalArgumentException("classic_TIFF_size_limit");
        main.replaceLongs(273,thumbStart);main.replaceLongs(330,rawStart);main.replaceLongs(34665,exifStart);
        long[] offsets=new long[stripCount],counts=new long[stripCount];
        for(int i=0;i<stripCount;i++){offsets[i]=pixelStart+(long)i*rows*plane.width*2;counts[i]=(long)Math.min(rows,plane.height-i*rows)*plane.width*2;}
        raw.replaceLongs(273,offsets);raw.replaceLongs(279,counts);
        ByteBuffer header=buffer(thumbStart);header.put((byte)'I').put((byte)'I').putShort((short)42).putInt(8);
        main.write(header);raw.write(header);exif.write(header);
        output.write(header.array());output.write(thumbnailRgb);
        for(int i=thumbStart+thumbnailRgb.length;i<pixelStart;i++)output.write(0);
        byte[] bytes=new byte[65536];int at=0;
        for(short pixel:plane.pixels){bytes[at++]=(byte)pixel;bytes[at++]=(byte)(pixel>>>8);
            if(at==bytes.length){output.write(bytes);at=0;}}
        if(at>0)output.write(bytes,0,at);
        return length;
    }
    private static long gcd(long a,long b){while(b!=0){long t=a%b;a=b;b=t;}return a;}
}
