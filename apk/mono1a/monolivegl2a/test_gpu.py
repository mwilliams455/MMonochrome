#!/usr/bin/env python3
"""Mesa GLES3 execution of packaged shader (external sampler changed to 2D test fixture only)."""
from pathlib import Path
import os,ctypes as C,sys,re,subprocess,tempfile,json
import numpy as np
os.environ.setdefault('EGL_PLATFORM','surfaceless');os.environ.setdefault('LIBGL_ALWAYS_SOFTWARE','1')
root=Path(sys.argv[1]);egl=C.CDLL('libEGL.so.1')
V=C.c_void_p;I=C.c_int;U=C.c_uint;F=C.c_float

def ef(name,ret,args):
 f=getattr(egl,name);f.restype=ret;f.argtypes=args;return f
getdisplay=ef('eglGetDisplay',V,[V]);init=ef('eglInitialize',U,[V,C.POINTER(I),C.POINTER(I)])
bindapi=ef('eglBindAPI',U,[U]);choose=ef('eglChooseConfig',U,[V,C.POINTER(I),C.POINTER(V),I,C.POINTER(I)])
create=ef('eglCreateContext',V,[V,V,V,C.POINTER(I)]);surface=ef('eglCreatePbufferSurface',V,[V,V,C.POINTER(I)])
make=ef('eglMakeCurrent',U,[V,V,V,V]);gp=ef('eglGetProcAddress',V,[C.c_char_p])
display=getdisplay(None);a=I();b=I();assert init(display,C.byref(a),C.byref(b));assert bindapi(0x30A0)
attrs=(I*15)(0x3033,1,0x3040,0x40,0x3024,8,0x3023,8,0x3022,8,0x3021,8,0x3038,0,0)
config=V();n=I();assert choose(display,attrs,C.byref(config),1,C.byref(n)) and n.value
ctx=create(display,config,None,(I*3)(0x3098,3,0x3038));assert ctx
surf=surface(display,config,(I*5)(0x3057,128,0x3056,64,0x3038));assert surf;assert make(display,surf,surf,ctx)
def gl(name,ret,args):
 address=gp(name.encode());assert address,name
 return C.CFUNCTYPE(ret,*args)(address)
gen=gl('glGenTextures',None,[I,C.POINTER(U)]);active=gl('glActiveTexture',None,[U]);texbind=gl('glBindTexture',None,[U,U]);
image=gl('glTexImage2D',None,[U,I,I,I,I,I,U,U,V]);param=gl('glTexParameteri',None,[U,U,I]);
shaderCreate=gl('glCreateShader',U,[U]);src=gl('glShaderSource',None,[U,I,C.POINTER(C.c_char_p),V]);compile_=gl('glCompileShader',None,[U]);
shaderiv=gl('glGetShaderiv',None,[U,U,C.POINTER(I)]);shaderlog=gl('glGetShaderInfoLog',None,[U,I,V,V]);
programCreate=gl('glCreateProgram',U,[]);attach=gl('glAttachShader',None,[U,U]);link=gl('glLinkProgram',None,[U]);
programiv=gl('glGetProgramiv',None,[U,U,C.POINTER(I)]);programlog=gl('glGetProgramInfoLog',None,[U,I,V,V]);
use=gl('glUseProgram',None,[U]);loc=gl('glGetUniformLocation',I,[U,C.c_char_p]);ui=gl('glUniform1i',None,[I,I]);uf=gl('glUniform1f',None,[I,F]);
umat=gl('glUniformMatrix3fv',None,[I,I,U,C.POINTER(F)]);uv=gl('glUniform3fv',None,[I,I,C.POINTER(F)]);u2=gl('glUniform2f',None,[I,F,F]);
viewport=gl('glViewport',None,[I,I,I,I]);draw=gl('glDrawArrays',None,[U,I,I]);read=gl('glReadPixels',None,[I,I,I,I,U,U,V]);
disable=gl('glDisable',None,[U]);err=gl('glGetError',U,[]);getstr=gl('glGetString',C.c_char_p,[U]);
disable(0x0BD0);disable(0x0BE2)
def shader(kind,text):
 s=shaderCreate(kind);c=C.c_char_p(text.encode());src(s,1,C.byref(c),None);compile_(s);ok=I();shaderiv(s,0x8B81,C.byref(ok))
 if not ok.value:
  log=C.create_string_buffer(16384);shaderlog(s,len(log),None,log);raise RuntimeError(log.value.decode())
 return s
vertex='''#version 300 es
precision highp float;
out vec2 texCoord;
void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);texCoord=p;gl_Position=vec4(p*2.0-1.0,0,1);}
'''
base=(root/'app/src/main/assets/shaders/preview/main_fs.glsl').read_text()
base='#version 300 es\n'+base.replace('#extension GL_OES_EGL_image_external_essl3 : require','').replace('samplerExternalOES','sampler2D')
def program(text):
 p=programCreate();attach(p,shader(0x8B31,vertex));attach(p,shader(0x8B30,text));link(p);ok=I();programiv(p,0x8B82,C.byref(ok))
 if not ok.value:
  log=C.create_string_buffer(16384);programlog(p,len(log),None,log);raise RuntimeError(log.value.decode())
 return p

def texture(unit,array,internal,fmt,type_,filter_=0x2600):
 array=np.ascontiguousarray(array);height,width=array.shape[:2]
 t=U();gen(1,C.byref(t));active(0x84C0+unit);texbind(0x0DE1,t.value)
 for what,val in [(0x2801,filter_),(0x2800,filter_),(0x2802,0x812F),(0x2803,0x812F)]:param(0x0DE1,what,val)
 image(0x0DE1,0,internal,width,height,0,fmt,type_,array.ctypes.data);assert err()==0
 return t.value
lut=np.frombuffer((root/'app/src/main/assets/mono/mono_curve02_gl2a.bin').read_bytes(),dtype=np.uint8).copy()
texture(2,lut.reshape(1,2048),0x8229,0x1903,0x1401)
# Literal two-row inverse table transport from a 64-point controlled sRGB-like curve.
codes=np.linspace(0,1,64);linear=np.where(codes<=.04045,codes/12.92,((codes+.055)/1.055)**2.4)
curveX=linear.astype(np.float32);curveY=codes.astype(np.float32)
inverse=np.round(np.interp(np.arange(1024)/1023,curveY,curveX)*65535).astype(np.uint16)
packed=np.zeros((2,1024,4),dtype=np.uint8);packed[0,:,:3]=(inverse>>8)[:,None];packed[1,:,:3]=(inverse&255)[:,None]
texture(1,packed,0x8058,0x1908,0x1401,0x2601)

def run(p,oes,weights,scale=1.,ready=1,probe=0,undo=None):
 h,w=oes.shape[:2];texture(0,oes,0x8814 if oes.dtype==np.float32 else 0x8058,0x1908,0x1406 if oes.dtype==np.float32 else 0x1401)
 use(p)
 for name,val in [('sTexture',0),('uMonoInverse2A',1),('uMonoCurve2A',2),('uMonoSourceReady2A',ready),('uMonoProbe2A',probe),('enablePeak',0),('mirror',0)]:ui(loc(p,name.encode()),val)
 uf(loc(p,b'uMonoExposureScale1A'),scale);u2(loc(p,b'resolution'),w,h)
 mat=np.eye(3,dtype=np.float32) if undo is None else np.array(undo,dtype=np.float32)
 mat=np.ascontiguousarray(mat.T);umat(loc(p,b'uMonoInputToSensor2A'),1,0,mat.ctypes.data_as(C.POINTER(F)))
 y=np.array(weights,dtype=np.float32);uv(loc(p,b'uMonoSourceY2A'),1,y.ctypes.data_as(C.POINTER(F)))
 viewport(0,0,w,h);draw(4,0,3);output=np.zeros((h,w,4),np.uint8);read(0,0,w,h,0x1908,0x1401,output.ctypes.data)
 assert err()==0;return output
# Extract the exact weighted scalar C++ body from the frozen JNI, not a second handwritten implementation.
cpp=(root/'app/src/main/cpp/m9color_jni.cpp').read_text()
func=cpp[cpp.index('Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1AWeightedDirectBitmap('):]
a=func.index('double source=wr*u16(cam[ci])');z=func.index('argb[p]=',a)
scalar=func[a:z]
lutBody=re.search(r'MM_MONO1A_CURVE02\s*\[\s*2048\s*\]\s*=\s*\{(.*?)\}',cpp,re.S)[1]
wrapped='#include <cmath>\n#include <cstdint>\n#include <algorithm>\nstatic uint8_t MM_MONO1A_CURVE02[2048]={'+lutBody+'};\n'
wrapped+='static uint16_t u16(uint16_t x){return x;}\nextern "C" void oracle(const uint16_t* in,int n,const float* y,uint8_t* out){'
wrapped+='const double wr=y[0],wg=y[1],wb=y[2];const int pedestal14=0;for(int i=0;i<n;i++){const uint16_t* cam=in+3*i;const int ci=0;'+scalar+'out[i]=yy;}}'
with tempfile.TemporaryDirectory() as d:
 p=Path(d);(p/'oracle.cpp').write_text(wrapped);subprocess.run(['g++','-std=c++17','-O2','-shared','-fPIC',str(p/'oracle.cpp'),'-o',str(p/'oracle.so')],check=True)
 native=C.CDLL(str(p/'oracle.so')).oracle;native.argtypes=[V,I,V,V]
 def expect(cam,weights):
  c=np.ascontiguousarray(cam,dtype=np.uint16);y=np.array(weights,np.float32);o=np.zeros(c.shape[:-1],np.uint8);native(c.ctypes.data,c.size//3,y.ctypes.data,o.ctypes.data);return o
 direct=program(base.replace('vec3 sensor=uMonoInputToSensor2A*linearRgb;','vec3 sensor=oes;'))
 full=program(base)
 rng=np.random.default_rng(2209);cam=rng.integers(0,65536,size=(64,128,3),dtype=np.uint16)
 oes=np.ones((64,128,4),np.float32);oes[:,:,:3]=cam.astype(np.float32)/65535
 rows=[[.627451,.7578125,.042553194],[.59733325,.7578125,.04339964],[1,0,0],[.2,.7,.1]]
 findings=[]
 for w in rows:
  output=run(direct,oes,w)[:,:,0];expected=expect(cam,w);delta=np.abs(output.astype(int)-expected.astype(int))
  assert delta.max()<=1,delta.max()
  findings.append({'weights':w,'pixels':int(delta.size),'differentPixels':int((delta>0).sum()),'maximumCodeError':int(delta.max())})
 # Exercise the FULL shader, controlled inverse, post-WB/boost inverse matrix and exposure bracket.
 oes8=rng.integers(0,256,size=(64,128,4),dtype=np.uint8);oes8[:,:,3]=255
 undo=np.array([[.5,.02,0],[-.01,1.0,0],[0,.02,.8]],np.float32);w=rows[0]
 # High-precision shader interpolation reconstructs this quantized inverse function.
 before=np.interp(oes8[:,:,:3]/255,np.arange(1024)/1023,inverse/65535)
 sensor=before@undo.astype(float).T
 bracket=[]
 for scale in [.5,1,2]:
  quant=np.floor(np.clip(sensor*scale,0,1)*65535+.5).astype(np.uint16)
  expected=expect(quant,w);output=run(full,oes8,w,scale=scale,undo=undo)[:,:,0]
  delta=np.abs(output.astype(int)-expected.astype(int));assert delta.max()<=1,int(delta.max())
  bracket.append(output)
  findings.append({'fullShaderScale':scale,'pixels':int(delta.size),'differentPixels':int((delta>0).sum()),'maximumCodeError':int(delta.max())})
 assert np.all(bracket[0]<=bracket[1]) and np.all(bracket[1]<=bracket[2])
 packedResult=run(full,oes8,w,probe=1,undo=undo)
 assert np.array_equal(packedResult[:,:,:3],oes8[:,:,:3]),'paired input RGB changed'
 assert np.array_equal(packedResult[:,:,3],bracket[1]),'paired output differs from normal shader'
 fallback=[]
 for scale in [.5,1,2]:fallback.append(run(full,oes8,w,scale=scale,ready=0)[:,:,0])
 assert np.all(fallback[0]<=fallback[1]) and np.all(fallback[1]<=fallback[2])
print(json.dumps({'status':'PASS','renderer':getstr(0x1F01).decode(),'scalarOracle':'exact_body_extracted_from_frozen_SOURCE1D_JNI',
 'comparisons':findings,'pairedProbeRgbAndOutputExact':True,'exposureBracketMonotonic':True,'fallbackBracketMonotonic':True,
 'devicePixelParityProven':False},indent=2))
