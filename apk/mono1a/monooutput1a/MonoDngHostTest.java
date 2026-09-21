import com.particlesdevs.photoncamera.m9.export.*;
import java.nio.*;
import java.nio.file.*;
import java.io.*;
import java.util.*;
public class MonoDngHostTest {
    static long count=0;
    static void yes(boolean value){count++;if(!value)throw new AssertionError("test "+count);}
    static void near(double a,double b,double e){yes(Math.abs(a-b)<=e);}
    static void rejected(Runnable action){try{action.run();throw new AssertionError("not rejected");}catch(IllegalArgumentException|ArithmeticException expected){count++;}}
    public static void main(String[] args)throws Exception {
        Path out=Paths.get(args[0]);Files.createDirectories(out);
        List<String> reports=new ArrayList<>();
        int[][] dims={{1,1},{13,9},{131,71},{256,192},{4096,3072}};
        float[][] weights={{.35387048f,.7578125f,.06666667f},{.627451f,.7578125f,.042553194f},{1,0,0},{.2f,.7f,.1f}};
        int fixture=0;
        for(int[] dim:dims)for(int rot:new int[]{0,90,180,270}){
            final int w=dim[0],h=dim[1];if(w==4096&&rot!=90)continue;
            final float[] y=weights[fixture%weights.length];
            double scale=fixture%3==0?1:3.5;
            final short[] source=new short[w*h*3];Random rng=new Random(100+fixture);
            for(int i=0;i<source.length;i++)source[i]=(short)rng.nextInt(65536);
            if(w*h>=3){source[0]=0;source[1]=0;source[2]=0;source[3]=(short)65535;source[4]=(short)65535;source[5]=(short)65535;}
            int sourceHash=Arrays.hashCode(source);long start=System.nanoTime();
            MonoLinearPlane1A p=MonoLinearPlane1A.create(w,h,rot,y,scale,(row,dst)->{System.arraycopy(source,row*w*3,dst,0,w*3);return dst.length;});
            yes(Arrays.hashCode(source)==sourceHash);yes(p.pixels.length==w*h);
            double divisor=Math.max(1,(double)y[0]+y[1]+y[2]);
            near(p.sourceUnitsPerWhite,divisor*scale,1e-12);
            for(int row=0;row<h;row++)for(int x=0;x<w;x++){
                int i=(row*w+x)*3;double scalar=(double)y[0]*(source[i]&65535)+(double)y[1]*(source[i+1]&65535)+(double)y[2]*(source[i+2]&65535);
                int dx=x,dy=row;
                if(rot==90){dx=h-1-row;dy=x;}else if(rot==180){dx=w-1-x;dy=h-1-row;}else if(rot==270){dx=row;dy=w-1-x;}
                int q=p.pixels[dy*p.width+dx]&65535;
                yes(q==Math.round(Math.max(0,scalar)/divisor));
                near(q/65535.0*p.sourceUnitsPerWhite,scalar/65535.0*scale,p.quantizationStep*.50001);
            }
            if(w*h>=3&&scale>1)yes(p.aboveJpegWhiteCount>0);
            MonoDngWriter1A.Metadata m=new MonoDngWriter1A.Metadata();m.make="Synthetic";m.model="NonDevice validation";m.cameraId="test-"+fixture;
            m.dateTime="2026:09:21 06:00:00";m.subsecond="123";m.originalName="synthetic-original.dng";
            m.iso=fixture==0?70000:345;m.exposureNs=fixture%2==0?33430445787L:66608695L;m.aperture=1.63;m.focalLength=8.72;
            int tw=16,th=12;byte[] thumbnail=new byte[tw*th*3];for(int i=0;i<tw*th;i++)Arrays.fill(thumbnail,i*3,i*3+3,(byte)(i%256));
            Path dng=out.resolve(String.format("SYNTHETIC_%02d.dng",fixture));
            long size;try(OutputStream stream=Files.newOutputStream(dng)){size=MonoDngWriter1A.write(stream,p,m,tw,th,thumbnail);}
            yes(Files.size(dng)==size);
            // Separate raw reference permits an independent TIFF/LibRaw sample comparison.
            try(OutputStream f=Files.newOutputStream(out.resolve(String.format("SYNTHETIC_%02d.u16",fixture)))){
                byte[] block=new byte[65536];int n=0;for(short q:p.pixels){block[n++]=(byte)q;block[n++]=(byte)(q>>>8);if(n==block.length){f.write(block);n=0;}}
                f.write(block,0,n);
            }
            reports.add(String.format(java.util.Locale.ROOT,"{\"file\":\"%s\",\"width\":%d,\"height\":%d,\"rotationApplied\":%d,\"sourceUnitsPerWhite\":%.12f,\"aboveWhite\":%d,\"bytes\":%d,\"elapsedMs\":%.3f}",dng.getFileName(),p.width,p.height,rot,p.sourceUnitsPerWhite,p.aboveJpegWhiteCount,size,(System.nanoTime()-start)/1e6));fixture++;
        }
        rejected(()->MonoLinearPlane1A.create(1,1,45,new float[]{1,0,0},1,(r,d)->d.length));
        rejected(()->MonoLinearPlane1A.create(1,1,0,new float[]{Float.NaN,0,0},1,(r,d)->d.length));
        rejected(()->MonoLinearPlane1A.create(1,1,0,new float[]{-1,0,0},1,(r,d)->d.length));
        rejected(()->MonoLinearPlane1A.create(1,1,0,new float[]{1,0,0},Double.POSITIVE_INFINITY,(r,d)->d.length));
        rejected(()->MonoLinearPlane1A.create(1,1,0,new float[]{1,0,0},1,(r,d)->0));
        MonoLinearPlane1A neg=MonoLinearPlane1A.create(1,1,0,new float[]{1,-1,0},1,(r,d)->{d[1]=(short)65535;return 3;});yes(neg.negativeCount==1&&neg.pixels[0]==0);
        Files.writeString(out.resolve("fixtures.json"),"{\"hostAssertions\":"+count+",\"fixtures\":["+String.join(",",reports)+"]}");
        System.out.println("MONODNG1A Java checks PASS: "+count+"; fixture files="+fixture);
    }
}
