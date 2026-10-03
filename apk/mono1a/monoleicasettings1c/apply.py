#!/usr/bin/env python3
"""Apply LEICASHARPNESS1C to the real SOURCE1D primary and live preview."""
from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET

if len(sys.argv)!=2: raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
pref_xml=root/"app/src/main/res/xml/preferences.xml"
keys_xml=root/"app/src/main/res/values/preference_keys.xml"
arrays_xml=root/"app/src/main/res/values/arrays.xml"
strings_xml=root/"app/src/main/res/values/strings.xml"
pref_java=root/"app/src/main/java/com/particlesdevs/photoncamera/settings/PreferenceKeys.java"
R=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java"
N=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java"
C=root/"app/src/main/cpp/m9color_jni.cpp"
H=root/"app/src/main/cpp/mm_monochrom_sharpness5.inc"
A=root/"app/src/main/assets/mono/mono_sharpness5.bin"
J=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/MonoSharpness1C.java"
P=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoGpuPreview2A.java"
M=root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java"
S=root/"app/src/main/assets/shaders/preview/main_fs.glsl"
G=root/"app/build.gradle"
for p in [pref_xml,keys_xml,arrays_xml,strings_xml,pref_java,R,N,C,H,A,J,P,M,S,G]:
    if not p.is_file(): raise SystemExit("LEICASHARPNESS1C missing "+str(p))
for receipt in ["LEICACONTRAST1A_ISOLATION.json","LEICATONING1A_ISOLATION.json",
                "LEICATONING1A_FIX1_ISOLATION.json","LEICATONING1A_FIX2_SOURCE1D_ISOLATION.json"]:
    if not (root/receipt).is_file(): raise SystemExit("LEICASHARPNESS1C missing parent receipt "+receipt)

def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"LEICASHARPNESS1C {label} anchor count={n}")
    return s.replace(a,b,1)
def append_resource(path,fragment):
    s=path.read_text()
    if fragment.splitlines()[0] in s: raise SystemExit("resource already applied "+str(path))
    path.write_text(one(s,"</resources>",fragment+"\n</resources>",path.name))
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

# Freeze non-JPEG policy.
frozen=[
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngExport1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngWriter1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoLinearPlane1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/exposure/MonoPlacementAssist1D.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoTapMeter1A.java",
 root/"app/src/main/java/com/particlesdevs/photoncamera/processing/parameters/IsoExpoSelector.java",
]
before={str(p.relative_to(root)):sha(p) for p in frozen}

# Generated asset identity.
asset=A.read_bytes()
if len(asset)!=5*16*2050*2: raise SystemExit("sharpness asset byte count mismatch")
asset_sha=hashlib.sha256(asset).hexdigest()
jtxt=J.read_text()
m=re.search(r'ASSET_SHA256="([0-9a-f]{64})"',jtxt)
if not m or m.group(1)!=asset_sha: raise SystemExit("sharpness Java/asset SHA mismatch")
if 'SOURCE_BANK_SHA256="282a6e7eb0603203d5ddb36f32862e0340a9cc2d24c35b4c0af2b1bd79c06d10"' not in jtxt:
    raise SystemExit("sharpness canonical source bank identity missing")

# ----- modern Leica settings UI -----
append_resource(keys_xml,'    <string name="pref_mono_sharpness_key" translatable="false">pref_mono_sharpness_key</string>')
append_resource(strings_xml,'    <string name="mono_sharpness">Sharpness</string>\n    <string name="mono_sharpness_summary">Original M Monochrom firmware sharpness</string>')
append_resource(arrays_xml,'''    <string-array name="mono_sharpness_entries">
        <item>Off</item><item>Low</item><item>Standard</item><item>Medium high</item><item>High</item>
    </string-array>
    <string-array name="mono_sharpness_entryvalues">
        <item>0</item><item>1</item><item>2</item><item>3</item><item>4</item>
    </string-array>''')

ANDROID="http://schemas.android.com/apk/res/android"; APP="http://schemas.android.com/apk/res-auto"
ET.register_namespace("android",ANDROID);ET.register_namespace("app",APP);akey="{"+ANDROID+"}key"
tree=ET.parse(pref_xml);screen=tree.getroot()
cat=next((n for n in list(screen) if n.attrib.get(akey)=="@string/pref_category_monochrom_key"),None)
if cat is None: raise SystemExit("Leica M Monochrom category missing")
if any(n.attrib.get(akey)=="@string/pref_mono_sharpness_key" for n in list(cat)):
    raise SystemExit("Sharpness preference already present")
sharp=ET.Element("ListPreference",{
    "{"+ANDROID+"}layout":"@layout/preference_with_margin",akey:"@string/pref_mono_sharpness_key",
    "{"+ANDROID+"}title":"@string/mono_sharpness","{"+ANDROID+"}summary":"@string/mono_sharpness_summary",
    "{"+ANDROID+"}icon":"@drawable/ic_gradient_black_24dp","{"+ANDROID+"}entries":"@array/mono_sharpness_entries",
    "{"+ANDROID+"}entryValues":"@array/mono_sharpness_entryvalues","{"+ANDROID+"}defaultValue":"2",
    "{"+APP+"}useSimpleSummaryProvider":"true"})
children=list(cat)
contrast_index=next((i for i,n in enumerate(children) if n.attrib.get(akey)=="@string/pref_mono_contrast_key"),None)
if contrast_index is None: raise SystemExit("Contrast preference missing")
cat.insert(contrast_index+1,sharp)
ET.indent(tree,space="    ");tree.write(pref_xml,encoding="utf-8",xml_declaration=True)

# PreferenceKeys: global across lenses, default Standard.
s=pref_java.read_text()
s=one(s,"        COMMON_KEYS.add(Key.KEY_MONO_CONTRAST.mValue);\n",
      "        COMMON_KEYS.add(Key.KEY_MONO_CONTRAST.mValue);\n        COMMON_KEYS.add(Key.KEY_MONO_SHARPNESS.mValue);\n","global sharp key")
s=one(s,"        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_CONTRAST, 2); // Leica Standard\n",
      "        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_CONTRAST, 2); // Leica Standard\n        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_SHARPNESS, 2); // Leica Standard\n","sharp default")
s=one(s,
"""    public static int getMonoContrastValue() {
        int value = preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_CONTRAST);
        return value < 0 ? 0 : (value > 4 ? 4 : value);
    }
""",
"""    public static int getMonoContrastValue() {
        int value = preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_CONTRAST);
        return value < 0 ? 0 : (value > 4 ? 4 : value);
    }

    /** Leica M Monochrom Sharpening enum: 0 Off, 1 Low, 2 Standard, 3 Medium high, 4 High. */
    public static int getMonoSharpnessValue() {
        int value=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL, Key.KEY_MONO_SHARPNESS);
        return value<0?0:(value>4?4:value);
    }
""","sharp getter")
s=one(s,"        KEY_MONO_CONTRAST(R.string.pref_mono_contrast_key),\n",
      "        KEY_MONO_CONTRAST(R.string.pref_mono_contrast_key),\n        KEY_MONO_SHARPNESS(R.string.pref_mono_sharpness_key),\n","sharp enum")
pref_java.write_text(s)

# ----- actual SOURCE1D primary JNI declaration -----
s=N.read_text()
s=one(s,
"""                                                                 float weightR, float weightG, float weightB,
                                                                 byte[] contrastCurve, int toningCr, int toningCb);
""",
"""                                                                 float weightR, float weightG, float weightB,
                                                                 int sharpSelector, int physicalCaptureIso, long[] sharpStats,
                                                                 byte[] contrastCurve, int toningCr, int toningCb);
""","SOURCE1D sharp declaration")
N.write_text(s)

# ----- SOURCE1D renderer: select physical ISO + Leica sharpness before Contrast/Toning -----
r=R.read_text()
anchor="""                final int source1dContrast1A = MonoContrastCurves1A.clamp(
                        com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoContrastValue());
"""
insert="""                final int source1dSharpSelector1C = MonoSharpness1C.clampSelector(
                        com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoSharpnessValue());
                Integer source1dSharpPhysicalIsoObj1C = nativeCaptureResult != null
                        ? nativeCaptureResult.get(CaptureResult.SENSOR_SENSITIVITY) : null;
                final int source1dSharpPhysicalIso1C = source1dSharpPhysicalIsoObj1C != null
                        && source1dSharpPhysicalIsoObj1C > 0 ? source1dSharpPhysicalIsoObj1C : 320;
                final long[] source1dSharpStats1C = new long[9];
                final int source1dContrast1A = MonoContrastCurves1A.clamp(
                        com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoContrastValue());
"""
r=one(r,anchor,insert,"SOURCE1D sharp selection")
r=one(r,
"""                        source1dWeightR, source1dWeightG, source1dWeightB,
                        source1dContrastCurve1A, source1dToningCr1A, source1dToningCb1A);
""",
"""                        source1dWeightR, source1dWeightG, source1dWeightB,
                        source1dSharpSelector1C, source1dSharpPhysicalIso1C, source1dSharpStats1C,
                        source1dContrastCurve1A, source1dToningCr1A, source1dToningCb1A);
""","SOURCE1D sharp args")

# Telemetry directly on selected SOURCE1D block.
r=one(r,
'                source1dXyzY.put("formula", "clamp(Yrow_sensorToXYZD50 dot sensorRGB,0,65535)>>>2_then_selected_M_Monochrom_contrast_curve_then_firmware_toning");\n',
'                source1dXyzY.put("formula", "clamp(Yrow_sensorToXYZD50 dot sensorRGB,0,65535)>>>2_then_firmware_sharpness_then_selected_M_Monochrom_contrast_curve_then_firmware_toning");\n'
'                source1dXyzY.put("sharpnessEnum", source1dSharpSelector1C);\n'
'                source1dXyzY.put("sharpnessLabel", MonoSharpness1C.LABELS[source1dSharpSelector1C]);\n'
'                source1dXyzY.put("sharpnessPhysicalIso", source1dSharpPhysicalIso1C);\n'
'                source1dXyzY.put("sharpnessIsoDomain", "physical_Camera2_SENSOR_SENSITIVITY");\n'
'                source1dXyzY.put("sharpnessBankSha256", MonoSharpness1C.SOURCE_BANK_SHA256);\n'
'                if (source1dSharpStats1C.length >= 9) {\n'
'                    source1dXyzY.put("sharpnessChangedPixels", source1dSharpStats1C[1]);\n'
'                    source1dXyzY.put("sharpnessSelectedIsoSlot", source1dSharpStats1C[3]);\n'
'                    source1dXyzY.put("sharpnessSelectedLeicaIso", source1dSharpStats1C[4]);\n'
'                    source1dXyzY.put("sharpnessModifierCode", source1dSharpStats1C[5]);\n'
'                    source1dXyzY.put("sharpnessEffectiveBorder", source1dSharpStats1C[6]);\n'
'                    source1dXyzY.put("sharpnessNativeNs", source1dSharpStats1C[8]);\n'
'                }\n',
"SOURCE1D sharp telemetry")
r=one(r,
'                d.put("source1dPolicy", "selected_portable_active_sensor_DNG_XYZ_Y_with_Leica_JPEG_contrast_and_toning_DNG_and_exposure_unchanged");\n',
'                d.put("source1dPolicy", "selected_portable_active_sensor_DNG_XYZ_Y_with_Leica_JPEG_sharpness_contrast_toning_DNG_and_exposure_unchanged");\n',
"SOURCE1D policy")
R.write_text(r)

# ----- C++ SOURCE1D: exact 14-bit sharpness before contrast/toning -----
c=C.read_text()
if '#include "mm_monochrom_sharpness5.inc"' in c: raise SystemExit("sharpness header already included")
# Include once immediately before the SOURCE1D JNI helper.
needle='extern "C" JNIEXPORT jboolean JNICALL\nJava_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1AWeightedDirectBitmap('
if needle not in c: raise SystemExit("SOURCE1D JNI anchor missing")
c=c.replace(needle,'#include "mm_monochrom_sharpness5.inc"\n\n'+needle,1)
name="Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1AWeightedDirectBitmap("
pos=c.index(name);start=c.rfind('extern "C" JNIEXPORT jboolean JNICALL',0,pos);brace=c.index('{',pos)
depth=0;end=None
for i in range(brace,len(c)):
    if c[i]=='{': depth+=1
    elif c[i]=='}':
        depth-=1
        if depth==0: end=i+1;break
if end is None: raise SystemExit("SOURCE1D JNI end missing")

fn=r'''static int mmMonoSharpNearestIsoSlot1C(int captureIso) {
    if(captureIso<=MM_MONO_SHARP_ISOS[0]) return 0;
    if(captureIso>=MM_MONO_SHARP_ISOS[MM_MONO_SHARP_ISO_COUNT-1]) return MM_MONO_SHARP_ISO_COUNT-1;
    const double target=std::log2(static_cast<double>(captureIso));
    int best=0; double bestD=std::abs(target-std::log2(static_cast<double>(MM_MONO_SHARP_ISOS[0])));
    for(int i=1;i<MM_MONO_SHARP_ISO_COUNT;++i){
        const double d=std::abs(target-std::log2(static_cast<double>(MM_MONO_SHARP_ISOS[i])));
        if(d<bestD){bestD=d;best=i;}
    }
    return best;
}

extern "C" JNIEXPORT jboolean JNICALL
Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_renderMonochrome1AWeightedDirectBitmap(
        JNIEnv* env, jclass, jlong camAddress, jint pixelCount, jint width, jint sourceHeight,
        jobject bitmap, jint cameraRotation, jint workers, jint pedestal14,
        jfloat weightR, jfloat weightG, jfloat weightB,
        jint sharpSelector, jint physicalCaptureIso, jlongArray sharpStatsArray,
        jbyteArray contrastCurveArray, jint toningCr, jint toningCb) {
    const auto* cam=reinterpret_cast<const jshort*>(static_cast<uintptr_t>(camAddress));
    if(!cam||!bitmap||width<=0||sourceHeight<=0||pixelCount!=width*sourceHeight
            ||workers<=0||pedestal14<0||pedestal14>16383
            ||!std::isfinite(weightR)||!std::isfinite(weightG)||!std::isfinite(weightB)){
        throwIllegalArgument(env,"Invalid MONO1A SOURCE1D sharp arguments");return JNI_FALSE;
    }
    const auto started=std::chrono::steady_clock::now();
    std::array<uint8_t,2048> contrastCurve{};
    if(contrastCurveArray&&env->GetArrayLength(contrastCurveArray)==2048){
        std::array<jbyte,2048> bytes{};env->GetByteArrayRegion(contrastCurveArray,0,2048,bytes.data());
        if(env->ExceptionCheck())return JNI_FALSE;
        for(size_t i=0;i<contrastCurve.size();++i)contrastCurve[i]=static_cast<uint8_t>(bytes[i]);
    }else{
        for(size_t i=0;i<contrastCurve.size();++i)contrastCurve[i]=MM_MONO1A_CURVE02[i];
    }
    const int selector=std::max(0,std::min(4,static_cast<int>(sharpSelector)));
    const int isoInput=physicalCaptureIso>0?static_cast<int>(physicalCaptureIso):320;
    const int isoSlot=mmMonoSharpNearestIsoSlot1C(isoInput);
    const int modifierCode=MM_MONO_SHARP_CODES[selector][isoSlot];
    const int cr=std::max(0,std::min(255,static_cast<int>(toningCr)));
    const int cb=std::max(0,std::min(255,static_cast<int>(toningCb)));
    const int dCr=cr-128,dCb=cb-128;
    auto roundShift16=[](int x)->int{return x>=0?((x+32768)>>16):-(((-x)+32768)>>16);};
    auto clamp8=[](int x)->uint8_t{return static_cast<uint8_t>(x<0?0:(x>255?255:x));};

    int rotation=cameraRotation%360;if(rotation<0)rotation+=360;
    const uint32_t outW=static_cast<uint32_t>((rotation==90||rotation==270)?sourceHeight:width);
    const uint32_t outH=static_cast<uint32_t>((rotation==90||rotation==270)?width:sourceHeight);
    AndroidBitmapInfo info{};
    if(AndroidBitmap_getInfo(env,bitmap,&info)!=ANDROID_BITMAP_RESULT_SUCCESS
            ||info.format!=ANDROID_BITMAP_FORMAT_RGBA_8888||info.width!=outW||info.height!=outH
            ||info.stride<outW*4u)return JNI_FALSE;
    void* rawPixels=nullptr;
    if(AndroidBitmap_lockPixels(env,bitmap,&rawPixels)!=ANDROID_BITMAP_RESULT_SUCCESS||!rawPixels)return JNI_FALSE;
    const int64_t pixels64=static_cast<int64_t>(width)*static_cast<int64_t>(sourceHeight);
    std::vector<uint16_t> image(static_cast<size_t>(pixels64));
    const int wc=std::max(1,std::min(static_cast<int>(workers),static_cast<int>(sourceHeight)));
    std::vector<std::thread> threads;threads.reserve(static_cast<size_t>(wc));
    const double wr=weightR,wg=weightG,wb=weightB;
    for(int worker=0;worker<wc;++worker){
        const int y0=(sourceHeight*worker)/wc,y1=(sourceHeight*(worker+1))/wc;
        threads.emplace_back([&,y0,y1](){
            for(int y=y0;y<y1;++y){const size_t row=static_cast<size_t>(y)*static_cast<size_t>(width);
                for(int x=0;x<width;++x){const size_t p=row+static_cast<size_t>(x),ci=p*3u;
                    double source=wr*u16(cam[ci])+wg*u16(cam[ci+1])+wb*u16(cam[ci+2]);
                    source=std::max(0.0,std::min(65535.0,source));
                    const uint32_t source16=static_cast<uint32_t>(std::llround(source));
                    image[p]=static_cast<uint16_t>(std::min<uint32_t>(16383u,source16>>2));
                }}
        });
    }
    for(auto&t:threads)t.join();threads.clear();

    uint64_t changed=0;
    const int B=(selector>0&&modifierCode>0)?MM_MONO_SHARP_BORDER:0;
    if(B>0&&width-2*B>0&&sourceHeight-2*B>0){
        const int16_t* table=MM_MONO_SHARP_LUT[selector][isoSlot];
        const int clipMag=-static_cast<int>(table[0]);
        std::vector<uint16_t> scratch(static_cast<size_t>(pixels64));
        for(int y=B-1;y<=sourceHeight-B;++y){const size_t row=static_cast<size_t>(y)*static_cast<size_t>(width);
            for(int x=B;x<width-B;++x){const size_t p=row+static_cast<size_t>(x);
                scratch[p]=static_cast<uint16_t>((static_cast<uint32_t>(image[p-1])+2u*image[p]+image[p+1])>>2);
            }}
        for(int y=B;y<sourceHeight-B;++y){const size_t row=static_cast<size_t>(y)*static_cast<size_t>(width);
            for(int x=B;x<width-B;++x){const size_t p=row+static_cast<size_t>(x);
                const int blur=(static_cast<int>(scratch[p-width])+2*static_cast<int>(scratch[p])+static_cast<int>(scratch[p+width]))>>2;
                const int detail=static_cast<int>(image[p])-blur;int correction;
                if(detail<-1024)correction=-clipMag;
                else if(detail>1024)correction=clipMag;
                else correction=static_cast<int>(table[1024+detail]);
                int v=static_cast<int>(image[p])+correction;
                if(v<0)v=0;else if(v>16383)v=16383;
                if(v!=image[p])changed++;
                image[p]=static_cast<uint16_t>(v);
            }}
    }

    auto* dst=static_cast<uint8_t*>(rawPixels);
    uint64_t near=0;
    for(int y=0;y<sourceHeight;++y){const size_t row=static_cast<size_t>(y)*static_cast<size_t>(width);
        for(int x=0;x<width;++x){const size_t p=row+static_cast<size_t>(x);
            int32_t v=static_cast<int32_t>(image[p])-pedestal14;if(v<0)v=0;
            int32_t idx=v>>3;if(idx>2047)idx=2047;
            const uint8_t yy=contrastCurve[static_cast<size_t>(idx)];if(yy>=250)near++;
            const uint8_t outR=clamp8(static_cast<int>(yy)+roundShift16(91881*dCr));
            const uint8_t outG=clamp8(static_cast<int>(yy)-roundShift16(22554*dCb+46802*dCr));
            const uint8_t outB=clamp8(static_cast<int>(yy)+roundShift16(116130*dCb));
            int dx,dy;if(rotation==90){dx=sourceHeight-1-y;dy=x;}else if(rotation==180){dx=width-1-x;dy=sourceHeight-1-y;}
            else if(rotation==270){dx=y;dy=width-1-x;}else{dx=x;dy=y;}
            uint8_t* d=dst+static_cast<size_t>(dy)*static_cast<size_t>(info.stride)+static_cast<size_t>(dx)*4u;
            const jint argb=static_cast<jint>(0xff000000u|(uint32_t(outR)<<16)|(uint32_t(outG)<<8)|uint32_t(outB));
            storeArgbAsRgba8888(d,argb);
        }}
    const int unlock=AndroidBitmap_unlockPixels(env,bitmap);
    const auto ended=std::chrono::steady_clock::now();
    if(sharpStatsArray&&env->GetArrayLength(sharpStatsArray)>=9){
        const jlong ns=static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(ended-started).count());
        const jlong stats[9]={static_cast<jlong>(pixels64),static_cast<jlong>(changed),static_cast<jlong>(selector),
            static_cast<jlong>(isoSlot),static_cast<jlong>(MM_MONO_SHARP_ISOS[isoSlot]),static_cast<jlong>(modifierCode),
            static_cast<jlong>(B),static_cast<jlong>(isoInput),ns};
        env->SetLongArrayRegion(sharpStatsArray,0,9,stats);
    }
    return unlock==ANDROID_BITMAP_RESULT_SUCCESS&&!env->ExceptionCheck()?JNI_TRUE:JNI_FALSE;
}'''
c=c[:start]+fn+c[end:]
C.write_text(c)

# ----- preview source metadata: keep current physical ISO available -----
p=P.read_text()
p=one(p,
"    private static volatile Draw lastProbe;\n",
"    private static volatile Draw lastProbe;\n    private static volatile int latestPhysicalIso1C=320;\n"
"    private static volatile int selectedSharpSelector1C=2,selectedSharpIso1C=320,selectedSharpCode1C=8;\n",
"preview sharp state")
p=one(p,
"""            Frame f=new Frame(camera,physicalId,physical,request,context,
                    transportTs==null?-1:transportTs,sensorTs==null?-1:sensorTs,SystemClock.elapsedRealtimeNanos());
""",
"""            Integer physicalIso1C=physical==null?null:physical.get(CaptureResult.SENSOR_SENSITIVITY);
            if(physicalIso1C!=null&&physicalIso1C>0) latestPhysicalIso1C=physicalIso1C;
            Frame f=new Frame(camera,physicalId,physical,request,context,
                    transportTs==null?-1:transportTs,sensorTs==null?-1:sensorTs,SystemClock.elapsedRealtimeNanos());
""","preview physical ISO observe")
# Insert methods before snapshot.
p=one(p,
"    public static synchronized JSONObject snapshot(long shutterElapsedNs) {\n",
"""    public static int latestPhysicalIso1C(){return latestPhysicalIso1C;}
    public static void setLeicaSharpnessSelection1C(int selector,int iso,int code){
        selectedSharpSelector1C=MonoSharpness1C.clampSelector(selector);
        selectedSharpIso1C=iso;selectedSharpCode1C=code;
    }

    public static synchronized JSONObject snapshot(long shutterElapsedNs) {
""","preview sharp methods")
# Import class.
p=one(p,
"import com.particlesdevs.photoncamera.m9.render.M9R35Renderer;\n",
"import com.particlesdevs.photoncamera.m9.render.M9R35Renderer;\nimport com.particlesdevs.photoncamera.m9.render.MonoSharpness1C;\n",
"preview sharp import")
# Context JSON telemetry after existing toning telemetry.
marker='            o.put("leicaToningCr",selectedToningCr).put("leicaToningCb",selectedToningCb);\n'
if marker not in p: raise SystemExit("preview toning telemetry anchor missing")
p=p.replace(marker,marker+
'            o.put("leicaSharpnessEnum",selectedSharpSelector1C);\n'
'            o.put("leicaSharpnessLabel",MonoSharpness1C.LABELS[selectedSharpSelector1C]);\n'
'            o.put("leicaSharpnessPhysicalIso",selectedSharpIso1C);\n'
'            o.put("leicaSharpnessModifierCode",selectedSharpCode1C);\n',1)
P.write_text(p)

# ----- preview shader: exact integer Gaussian/detail/LUT at preview resolution before contrast -----
s=S.read_text()
s=one(s,
"uniform highp sampler2D uMonoCurve2A;\n",
"uniform highp sampler2D uMonoCurve2A;\nuniform highp isampler2D uMonoSharpLut1C;\n"
"uniform bool uMonoSharpReady1C;\nuniform int uMonoSharpSelector1C;\n",
"shader sharp uniforms")

start=s.find("float monochrome(vec3 oes) {")
end=s.find("void main() {",start)
if start<0 or end<0: raise SystemExit("shader monochrome block missing")
newblock=r'''float fallbackMono1C(vec3 oes) {
    return clamp(srgbCode(dot(srgbLinear(clamp(oes,0.0,1.0))*uMonoExposureScale1A,
            vec3(0.2126,0.7152,0.0722))),0.0,1.0);
}
int source14At1C(vec2 uv) {
    vec3 oes=texture(sTexture,uv).rgb;
    vec3 linearRgb=vec3(inverseChannel(oes.r,0),inverseChannel(oes.g,1),inverseChannel(oes.b,2));
    vec3 sensor=uMonoInputToSensor2A*linearRgb;
    vec3 cam16=floor(clamp(sensor*uMonoExposureScale1A,0.0,1.0)*65535.0+0.5);
    float source16=floor(clamp(dot(cam16,uMonoSourceY2A),0.0,65535.0)+0.5);
    return int(source16)>>2;
}
int sharpSource14At1C(vec2 uv) {
    int src=source14At1C(uv);
    if(!uMonoSharpReady1C || uMonoSharpSelector1C==0) return src;
    ivec2 p=ivec2(floor(uv*resolution));
    if(p.x<2||p.y<2||p.x>=int(resolution.x)-2||p.y>=int(resolution.y)-2) return src;
    vec2 dx=vec2(1.0/resolution.x,0.0),dy=vec2(0.0,1.0/resolution.y);
    int ht=(source14At1C(uv-dy-dx)+2*source14At1C(uv-dy)+source14At1C(uv-dy+dx))>>2;
    int hm=(source14At1C(uv-dx)+2*src+source14At1C(uv+dx))>>2;
    int hb=(source14At1C(uv+dy-dx)+2*source14At1C(uv+dy)+source14At1C(uv+dy+dx))>>2;
    int blur=(ht+2*hm+hb)>>2;
    int detail=src-blur;
    int clipMag=-texelFetch(uMonoSharpLut1C,ivec2(0,0),0).r;
    int correction=detail<-1024 ? -clipMag :
                   (detail>1024 ? clipMag : texelFetch(uMonoSharpLut1C,ivec2(1024+detail,0),0).r);
    return clamp(src+correction,0,16383);
}
float monochrome(vec2 uv) {
    vec3 oes=texture(sTexture,uv).rgb;
    if(!uMonoSourceReady2A) return fallbackMono1C(oes);
    int source14=sharpSource14At1C(uv);
    int index=clamp(source14,0,16383)>>3;
    return texelFetch(uMonoCurve2A,ivec2(index,0),0).r;
}
'''
s=s[:start]+newblock+s[end:]
s=one(s,"    float y=monochrome(oes.rgb);\n","    float y=monochrome(uv);\n","shader sharp call")
S.write_text(s)

# ----- MainRenderer: load exact selected modified row and bind it to preview -----
m=M.read_text()
m=one(m,
"    private int monoProgram2A, monoInverseTex2A, monoCurveTex2A;\n",
"    private int monoProgram2A, monoInverseTex2A, monoCurveTex2A;\n"
"    private int monoSharpTex1C,monoSharpReadyUniform1C,monoSharpSelectorUniform1C;\n"
"    private byte[] monoSharpBank1C; private int monoSharpBoundSelector1C=-1,monoSharpBoundSlot1C=-1;\n",
"renderer sharp fields")
m=one(m,
'        monoProbeUniform2A=GLES20.glGetUniformLocation(program,"uMonoProbe2A");\n',
'        monoProbeUniform2A=GLES20.glGetUniformLocation(program,"uMonoProbe2A");\n'
'        monoSharpReadyUniform1C=GLES20.glGetUniformLocation(program,"uMonoSharpReady1C");\n'
'        monoSharpSelectorUniform1C=GLES20.glGetUniformLocation(program,"uMonoSharpSelector1C");\n'
'        GLES20.glUniform1i(GLES20.glGetUniformLocation(program,"uMonoSharpLut1C"),4);\n',
"renderer sharp uniforms")
# After base texture IDs, create sharp texture.
m=one(m,
"        monoInverseTex2A=ids[0]; monoCurveTex2A=ids[1];\n",
"        monoInverseTex2A=ids[0]; monoCurveTex2A=ids[1];\n"
"        int[] sharpId1C=new int[1]; GLES20.glGenTextures(1,sharpId1C,0); monoSharpTex1C=sharpId1C[0];\n",
"renderer sharp texture id")
# Insert asset load just before active texture0 restore.
asset_anchor="        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);\n    }\n"
asset_block="""        GLES20.glActiveTexture(GLES20.GL_TEXTURE4);
        texture2A(monoSharpTex1C,GLES20.GL_NEAREST);
        ByteBuffer sharpZero1C=ByteBuffer.allocateDirect(2).order(java.nio.ByteOrder.LITTLE_ENDIAN);
        sharpZero1C.putShort((short)0).position(0);
        GLES30.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES30.GL_R16I,1,1,0,GLES30.GL_RED_INTEGER,GLES20.GL_SHORT,sharpZero1C);
        try(java.io.InputStream in=mView.getContext().getAssets().open(com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.ASSET)) {
            int expected=com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.SELECTOR_COUNT
                    *com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.ISO_COUNT
                    *com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.LUT_COUNT*2;
            byte[] data=new byte[expected]; int offset=0,n;
            while(offset<data.length&&(n=in.read(data,offset,data.length-offset))>0)offset+=n;
            if(offset!=data.length||in.read()!=-1)throw new java.io.IOException("sharpness_bank_length");
            byte[] hash=java.security.MessageDigest.getInstance("SHA-256").digest(data);
            StringBuilder text=new StringBuilder();for(byte b:hash)text.append(String.format(java.util.Locale.ROOT,"%02x",b&255));
            if(!text.toString().equals(com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.ASSET_SHA256))
                throw new java.io.IOException("sharpness_bank_checksum");
            monoSharpBank1C=data;
        } catch(Exception e) { monoSharpBank1C=null; Log.e("MonoGL2A","sharpness bank unavailable: "+e); }
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
    }
"""
if m.count(asset_anchor)!=1: raise SystemExit("renderer sharp asset anchor count="+str(m.count(asset_anchor)))
m=m.replace(asset_anchor,asset_block,1)

# Insert selected row upload immediately before toning selection (which is already per draw).
toning_anchor="        int toningHue1A=com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoToningHueValue();\n"
sharp_bind="""        int sharpSelector1C=com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.clampSelector(
                com.particlesdevs.photoncamera.settings.PreferenceKeys.getMonoSharpnessValue());
        int sharpPhysicalIso1C=com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.latestPhysicalIso1C();
        int sharpIsoSlot1C=com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.nearestIsoSlot(sharpPhysicalIso1C);
        int sharpCode1C=com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.CODES[sharpSelector1C][sharpIsoSlot1C];
        boolean sharpReady1C=sharpSelector1C==0;
        if(sharpSelector1C>0 && monoSharpBank1C!=null) {
            if(sharpSelector1C!=monoSharpBoundSelector1C || sharpIsoSlot1C!=monoSharpBoundSlot1C) {
                int rowBytes1C=com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.LUT_COUNT*2;
                int rowIndex1C=sharpSelector1C*com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.ISO_COUNT+sharpIsoSlot1C;
                int off1C=rowIndex1C*rowBytes1C;
                ByteBuffer bytes1C=ByteBuffer.allocateDirect(rowBytes1C).order(java.nio.ByteOrder.LITTLE_ENDIAN);
                bytes1C.put(monoSharpBank1C,off1C,rowBytes1C).position(0);
                GLES20.glActiveTexture(GLES20.GL_TEXTURE4); GLES20.glBindTexture(GLES20.GL_TEXTURE_2D,monoSharpTex1C);
                GLES30.glTexImage2D(GLES20.GL_TEXTURE_2D,0,GLES30.GL_R16I,
                        com.particlesdevs.photoncamera.m9.render.MonoSharpness1C.LUT_COUNT,1,0,
                        GLES30.GL_RED_INTEGER,GLES20.GL_SHORT,bytes1C);
                int sharpError1C=GLES20.glGetError();
                if(sharpError1C==GLES20.GL_NO_ERROR) {
                    monoSharpBoundSelector1C=sharpSelector1C; monoSharpBoundSlot1C=sharpIsoSlot1C;
                } else {
                    monoSharpBoundSelector1C=-1; monoSharpBoundSlot1C=-1;
                    probeError2A="sharpness_GL_error_"+sharpError1C;
                }
            }
            sharpReady1C=monoSharpBoundSelector1C==sharpSelector1C && monoSharpBoundSlot1C==sharpIsoSlot1C;
        }
        GLES20.glUniform1i(monoSharpReadyUniform1C,sharpReady1C?1:0);
        GLES20.glUniform1i(monoSharpSelectorUniform1C,sharpSelector1C);
        com.particlesdevs.photoncamera.m9.preview.MonoGpuPreview2A.setLeicaSharpnessSelection1C(
                sharpSelector1C,sharpPhysicalIso1C,sharpCode1C);
        GLES20.glActiveTexture(GLES20.GL_TEXTURE0);
"""
if m.count(toning_anchor)!=1: raise SystemExit("renderer toning anchor count="+str(m.count(toning_anchor)))
m=m.replace(toning_anchor,sharp_bind+toning_anchor,1)
M.write_text(m)

# Identity.
g=G.read_text();mm=re.search(r"versionName\s+'([^']+)'",g)
if not mm: raise SystemExit("versionName missing")
if "leicasharpness1c" not in mm.group(1):
    g=g[:mm.start(1)]+mm.group(1)+"-leicasharpness1c"+g[mm.end(1):]
G.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICASHARPNESS1C modified frozen DNG/exposure/tap files "+repr(changed))
proof={
 "revision":"LEICASHARPNESS1C",
 "firmware":"Leica M Monochrom 1.022",
 "menu":["Off","Low","Standard","Medium high","High"],
 "menuEnum":[0,1,2,3,4],
 "default":2,
 "sourceBankSha256":"282a6e7eb0603203d5ddb36f32862e0340a9cc2d24c35b4c0af2b1bd79c06d10",
 "generatedAssetSha256":asset_sha,
 "isoDomain":"physical_Camera2_SENSOR_SENSITIVITY",
 "selectorIsoCodes":[
  [0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0],
  [4,4,4,4,2,2,2,2,2,2,2,2,2,2,1,1],
  [8,8,8,8,4,4,4,4,4,4,4,4,3,3,2,2],
  [11,11,11,11,8,8,8,8,8,8,8,7,6,5,4,3],
  [12,12,12,12,11,11,11,11,11,11,11,10,9,8,7,6]
 ],
 "kernel":"14bit_scalar_two_stage_integer_gaussian_detail_LUT",
 "borderAddedPerSide":2,
 "source1dPrimaryUsesSharpness":True,
 "sharpnessBeforeContrast":True,
 "sharpnessBeforeToning":True,
 "previewUsesSameSelectorIsoCodeAndModifiedLut":True,
 "previewPixelParityClaim":False,
 "linearDngSharpnessChanged":False,
 "exposureChanged":False,
 "tapMeterChanged":False,
 "contrastPreserved":True,
 "toningPreserved":True,
 "frozenPolicyHashes":after
}
(root/"LEICASHARPNESS1C_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
