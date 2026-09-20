#!/usr/bin/env python3
from pathlib import Path
import subprocess,sys,tempfile,json,hashlib
root=Path(sys.argv[1]); here=Path(__file__).parent
java=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoPreviewMath2A.java'
source=r'''
import com.particlesdevs.photoncamera.m9.preview.MonoPreviewMath2A;
public class MathTest {
 static int count=0;
 static void yes(boolean v){count++;if(!v)throw new AssertionError("assertion "+count);}
 static void near(double a,double b,double t){yes(Math.abs(a-b)<=t);}
 public static void main(String[] args) {
  for(int points:new int[]{16,32,64,128}) {
   float[] c=MonoPreviewMath2A.srgbCurve(points);yes(MonoPreviewMath2A.validCurve(c));
   yes(c.length==2*Math.min(points,64));
   double last=-1;
   for(int i=0;i<=1023;i++){double y=i/1023.0,x=MonoPreviewMath2A.invert(c,y);yes(x>=last);last=x;}
   byte[] b=MonoPreviewMath2A.inverseTexture(new float[][]{c,c,c});yes(b.length==8192);
   for(int i=0;i<1024;i++){
    int q=((b[4*i]&255)<<8)|(b[4096+4*i]&255);
    near(q/65535.0,MonoPreviewMath2A.invert(c,i/1023.0),0.5/65535.0+1e-9);
   }
  }
  for(float[] c:new float[][]{null,new float[]{0,0},new float[]{0,0,1,Float.NaN},
    new float[]{0,0,1,.9f},new float[]{0,0,.5f,.5f,1,.5f},new float[]{0,0,.5f,.9f,.4f,1},
    new float[]{0,0,.5f,-.2f,1,1}})yes(!MonoPreviewMath2A.validCurve(c));
  java.util.Random rng=new java.util.Random(125);
  for(int k=0;k<150;k++) {
   double[] a={1.4,-.3,-.1,-.2,1.3,-.1,.02,-.5,1.48};
   double[] inv=MonoPreviewMath2A.inverse3(a);
   for(int r=0;r<3;r++)for(int c=0;c<3;c++) {
    double s=0;for(int z=0;z<3;z++)s+=a[r*3+z]*inv[z*3+c];near(s,r==c?1:0,1e-10);
   }
   double[] wb={2+rng.nextDouble(),1,1.4+rng.nextDouble()};int boost=100+rng.nextInt(400);
   float[] undo=MonoPreviewMath2A.undoColor(a,wb,boost);
   double[] sensor={rng.nextDouble()*.2,rng.nextDouble()*.2,rng.nextDouble()*.2};
   double[] linear=new double[3];
   for(int r=0;r<3;r++)for(int c=0;c<3;c++)linear[r]+=a[r*3+c]*wb[c]*sensor[c]*(boost/100.0);
   for(int r=0;r<3;r++){double x=0;for(int c=0;c<3;c++)x+=undo[c*3+r]*linear[c];near(x,sensor[r],1e-6);}
  }
  boolean rejected=false;try {MonoPreviewMath2A.inverse3(new double[9]);}catch(IllegalArgumentException e){rejected=true;}yes(rejected);
  float[] y={.627451f,.7578125f,.042553194f};
  near(y[0]*.3486328125+y[1]+y[2]*.55078125,1,1e-6);
  int last=-1;for(int i=0;i<=65535;i++){int idx=MonoPreviewMath2A.source1dIndex(i,i,i,new float[]{1,0,0});yes(idx==(i>>>5));yes(idx>=last);last=idx;}
  System.out.println("MONOLIVEGL2A MATH PASS assertions="+count);
 }
}
'''
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'MathTest.java').write_text(source)
 subprocess.run(['javac','-d',d,str(java),str(p/'MathTest.java')],check=True)
 subprocess.run(['java','-cp',d,'MathTest'],check=True)
isolation=json.loads((root/'MONOLIVEGL2A_ISOLATION.json').read_text())
for rel,expected in isolation['frozen'].items():assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==expected,rel
shader=(root/'app/src/main/assets/shaders/preview/main_fs.glsl').read_text()
assert 'monoResidualTone1B' not in shader and 'TRIPAIR' not in shader
assert 'texelFetch(uMonoCurve2A' in shader and 'uMonoProbe2A' in shader
print('MONOLIVEGL2A ISOLATION and shader active-path contract PASS')
