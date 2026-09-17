#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv)!=2: raise SystemExit('usage: apply-deviceport2b-blackorigin.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve()
R=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java'
N=root/'app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9NativeColorCore.java'
C=root/'app/src/main/cpp/m9color_jni.cpp'
for p in (R,N,C):
    if not p.exists(): raise SystemExit('DEVICEPORT2B missing '+str(p))

def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f'DEVICEPORT2B {label}: anchor count={n}, expected 1')
    return s.replace(a,b,1)

r,n,c=R.read_text(),N.read_text(),C.read_text()
if 'MONO_DEVICEPORT2B_BLACK_ORIGIN' in r: raise SystemExit('DEVICEPORT2B already applied')

# The pinned M9 CFA portability patch carries an M9-only closure-sharp stage in its
# generic neutral-aware Bayer path. The successful Monochrom baseline has no such
# helpers and its neutral MHC path is intentionally unsharpened here; Leica Standard
# sharpness is applied later by the frozen Monochrom SHARPSTD1B stage. Strip only the
# foreign closure helper and collapse the generic Bayer neutral path back to the
# Monochrom RGGB semantics, generalized solely by Bayer phase/origin.
foreign_helper=r'''inline void m9SharpSourceLeicaGreen14BayerPhase(const jshort* raw,int w,int h,std::vector<uint16_t>& dst,
                                                int phaseX,int phaseY){
    const size_t n=static_cast<size_t>(w)*static_cast<size_t>(h); dst.resize(n);
    for(int y=0;y<h;++y)for(int x=0;x<w;++x){
        const size_t p=static_cast<size_t>(y)*static_cast<size_t>(w)+static_cast<size_t>(x);
        const bool ey=m9PhaseEvenY(y,phaseY), ex=m9PhaseEvenX(x,phaseX); int g;
        if(ey==ex){
            g=(static_cast<int>(m9SharpSourceRaw14At(raw,w,h,y-1,x))+static_cast<int>(m9SharpSourceRaw14At(raw,w,h,y+1,x))+static_cast<int>(m9SharpSourceRaw14At(raw,w,h,y,x-1))+static_cast<int>(m9SharpSourceRaw14At(raw,w,h,y,x+1)))/4;
        }else{
            g=(4*static_cast<int>(m9SharpSourceRaw14At(raw,w,h,y,x))+static_cast<int>(m9SharpSourceRaw14At(raw,w,h,y-1,x-1))+static_cast<int>(m9SharpSourceRaw14At(raw,w,h,y-1,x+1))+static_cast<int>(m9SharpSourceRaw14At(raw,w,h,y+1,x-1))+static_cast<int>(m9SharpSourceRaw14At(raw,w,h,y+1,x+1)))/8;
        }
        dst[p]=static_cast<uint16_t>(g<0?0:(g>16383?16383:g));
    }
}
'''
foreign_neutral=r'''    if(neutralAware){
        std::vector<uint16_t> greenPlane(static_cast<size_t>(pixels64));
        for(int worker=0;worker<workerCount;++worker){
            const int y0=(height*worker)/workerCount,y1=(height*(worker+1))/workerCount;
            threads.emplace_back([=,&greenPlane](){for(int y=y0;y<y1;++y)for(int x=0;x<width;++x){
                greenPlane[static_cast<size_t>(y)*static_cast<size_t>(width)+static_cast<size_t>(x)]=mhcNeutralGreenBayerPhase(raw,width,height,y,x,invR,invB,phaseX,phaseY);
            }});
        }
        for(auto& thread:threads)thread.join();
        std::vector<uint16_t> sharpSourceGreen14; m9SharpSourceLeicaGreen14BayerPhase(raw,width,height,sharpSourceGreen14,phaseX,phaseY);
        std::vector<uint16_t> closureSharp14; m9ClosureSharpIso160Standard(sharpSourceGreen14,closureSharp14,width,height);
        threads.clear();
        for(int worker=0;worker<workerCount;++worker){
            const int y0=(height*worker)/workerCount,y1=(height*(worker+1))/workerCount;
            threads.emplace_back([=,&greenPlane,&sharpSourceGreen14,&closureSharp14](){for(int y=y0;y<y1;++y)for(int x=0;x<width;++x){
                const size_t p=static_cast<size_t>(y)*static_cast<size_t>(width)+static_cast<size_t>(x); uint16_t* dst=out+p*3u; uint16_t base[3];
                mhcPixelNeutralRbCompleteBayerPhase(raw,width,height,y,x,greenPlane[p],base,nr,nb,invR,invB,phaseX,phaseY);
                if(x>=9&&x<width-9&&y>=9&&y<height-9){
                    const int sg=static_cast<int>(closureSharp14[p]),mg=static_cast<int>(m9ClosureQ14(base[1]));
                    const int dr=static_cast<int>(m9ClosureQ14(base[0]))-mg,db=static_cast<int>(m9ClosureQ14(base[2]))-mg;
                    dst[0]=m9ClosureQ16(m9ClosureClamp14(sg+dr));dst[1]=m9ClosureQ16(static_cast<uint16_t>(sg));dst[2]=m9ClosureQ16(m9ClosureClamp14(sg+db));
                }else{dst[0]=base[0];dst[1]=base[1];dst[2]=base[2];}
            }});
        }
        for(auto& thread:threads)thread.join();
    }else{'''
mono_neutral=r'''    if(neutralAware){
        // MONO_DEVICEPORT2B_MONOCHROM_CFA_NEUTRAL_PARITY:
        // generalize only Bayer phase/origin. Preserve the Monochrom RGGB neutral
        // MHC semantics exactly; do not import the M9 closure-sharp path.
        std::vector<uint16_t> greenPlane(static_cast<size_t>(pixels64));
        for(int worker=0;worker<workerCount;++worker){
            const int y0=(height*worker)/workerCount,y1=(height*(worker+1))/workerCount;
            threads.emplace_back([=,&greenPlane](){for(int y=y0;y<y1;++y)for(int x=0;x<width;++x){
                greenPlane[static_cast<size_t>(y)*static_cast<size_t>(width)+static_cast<size_t>(x)]=mhcNeutralGreenBayerPhase(raw,width,height,y,x,invR,invB,phaseX,phaseY);
            }});
        }
        for(auto& thread:threads)thread.join();
        threads.clear();
        for(int worker=0;worker<workerCount;++worker){
            const int y0=(height*worker)/workerCount,y1=(height*(worker+1))/workerCount;
            threads.emplace_back([=,&greenPlane](){for(int y=y0;y<y1;++y)for(int x=0;x<width;++x){
                const size_t p=static_cast<size_t>(y)*static_cast<size_t>(width)+static_cast<size_t>(x);
                uint16_t* dst=out+p*3u;
                mhcPixelNeutralRbCompleteBayerPhase(raw,width,height,y,x,greenPlane[p],dst,nr,nb,invR,invB,phaseX,phaseY);
            }});
        }
        for(auto& thread:threads)thread.join();
    }else{'''
c=one(c,foreign_helper,'','Monochrom removal of M9 closure helper')
c=one(c,foreign_neutral,mono_neutral,'Monochrom generic CFA neutral parity')

# Keep the frozen origin0 normalizer untouched. Add an origin-aware JNI sibling for
# cropped RAW buffers whose local (0,0) is not sensor-grid (0,0).
decl='''    static native long normalizeRawDirect(java.nio.ByteBuffer rawBuffer,\n                                          int pixelCount,\n                                          int width,\n                                          int height,\n                                          float[] black,\n                                          int whiteLevel,\n                                          int workers,\n                                          short[] norm16,\n                                          long[] rawCountsFlat,\n                                          long[] stats);\n'''
new_decl=decl+'''\n    /** DEVICEPORT2B: same normalization, but 2x2 black/histogram planes follow sensor origin. */\n    static native long normalizeRawDirectOriginAware(java.nio.ByteBuffer rawBuffer,\n                                                     int pixelCount, int width, int height,\n                                                     int originX, int originY,\n                                                     float[] black, int whiteLevel, int workers,\n                                                     short[] norm16, long[] rawCountsFlat, long[] stats);\n'''
n=one(n,decl,new_decl,'native declaration')

# Only production prospective source normalization changes. The dormant historical
# renderCore normalizeRawDirect call remains exactly unchanged as a parity reference.
call='''        long clipped = M9NativeColorCore.normalizeRawDirect(dup, pixels, width, height,\n                black, wl, normalizeWorkers, norm16, rawCountsFlat, normalizeStats);\n'''
if r.count(call)!=2:
    raise SystemExit(f'DEVICEPORT2B expected two normalizeRawDirect calls, found {r.count(call)}')
first=r.find(call); second=r.find(call, first+len(call))
replacement='''        final boolean blackPlaneOrigin0 = sourceRawOriginX == 0 && sourceRawOriginY == 0;\n        long clipped = blackPlaneOrigin0\n                ? M9NativeColorCore.normalizeRawDirect(dup, pixels, width, height,\n                        black, wl, normalizeWorkers, norm16, rawCountsFlat, normalizeStats)\n                : M9NativeColorCore.normalizeRawDirectOriginAware(dup, pixels, width, height,\n                        sourceRawOriginX, sourceRawOriginY, black, wl, normalizeWorkers,\n                        norm16, rawCountsFlat, normalizeStats);\n'''
r=r[:second]+r[second:].replace(call,replacement,1)

# Telemetry next to the source-origin diagnostics.
anchor='''            d.put("sourceRawOriginDerivedFromPhysicalGeometry", true);\n'''
add='''            d.put("sourceBlackLevelPlaneOriginAware", true);\n            d.put("sourceBlackLevelLegacyOrigin0Path", sourceRawOriginX == 0 && sourceRawOriginY == 0);\n            d.put("sourceBlackLevelPlaneRule", "sensor_grid_2x2_row_major_with_RAW_origin_parity");\n            d.put("monoDevicePortBlackRevision", "MONO_DEVICEPORT2B_BLACK_ORIGIN");\n'''
r=one(r,anchor,anchor+add,'origin telemetry')

# Native origin-aware normalization. Camera2 BlackLevelPattern is a sensor-grid 2x2
# pattern, so local pixels must select the plane after adding the RAW buffer origin.
marker='''extern "C" JNIEXPORT jlong JNICALL\nJava_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_normalizeRawDirect(\n'''
if c.count(marker)!=1: raise SystemExit('DEVICEPORT2B normalize JNI anchor missing/ambiguous')
fn=r'''extern "C" JNIEXPORT jlong JNICALL
Java_com_particlesdevs_photoncamera_m9_render_M9NativeColorCore_normalizeRawDirectOriginAware(
        JNIEnv* env, jclass, jobject rawBuffer, jint pixelCount, jint width, jint height,
        jint originX, jint originY, jfloatArray blackArray, jint whiteLevel, jint workers,
        jshortArray normArray, jlongArray histogramArray, jlongArray statsArray) {
    if (!rawBuffer || !normArray || !histogramArray || !statsArray
            || pixelCount <= 0 || width <= 0 || height <= 0
            || pixelCount != width * height || whiteLevel < 2 || workers <= 0) {
        throwIllegalArgument(env, "Invalid MONO DEVICEPORT2B origin-aware normalization arguments");
        return 0;
    }
    auto* rawBytes = static_cast<uint8_t*>(env->GetDirectBufferAddress(rawBuffer));
    const jlong rawCapacity = env->GetDirectBufferCapacity(rawBuffer);
    const jlong expectedBytes = static_cast<jlong>(pixelCount) * 2LL;
    if (!rawBytes || rawCapacity < expectedBytes) {
        throwIllegalArgument(env, "MONO DEVICEPORT2B requires packed direct RAW16 buffer");
        return 0;
    }
    if (env->GetArrayLength(normArray) < pixelCount
            || env->GetArrayLength(histogramArray) < 4 * whiteLevel
            || env->GetArrayLength(statsArray) < 3) {
        throwIllegalArgument(env, "MONO DEVICEPORT2B output buffers too small");
        return 0;
    }
    std::array<float,4> black={64.0f,64.0f,64.0f,64.0f};
    if (blackArray && env->GetArrayLength(blackArray)>=4) {
        env->GetFloatArrayRegion(blackArray,0,4,black.data());
        if (env->ExceptionCheck()) return 0;
    }
    const int workerCount=std::max(1,std::min(static_cast<int>(workers),static_cast<int>(height)));
    const size_t histogramBins=static_cast<size_t>(4)*static_cast<size_t>(whiteLevel);
    thread_local std::vector<jshort> normalizedScratch;
    thread_local std::vector<uint64_t> workerHistograms;
    thread_local std::vector<uint64_t> workerClipped;
    normalizedScratch.resize(static_cast<size_t>(pixelCount));
    workerHistograms.assign(histogramBins*static_cast<size_t>(workerCount),0u);
    workerClipped.assign(static_cast<size_t>(workerCount),0u);
    auto* normalizedOut=normalizedScratch.data();
    auto* histogramBase=workerHistograms.data();
    auto* clippedBase=workerClipped.data();
    const auto computeStart=std::chrono::steady_clock::now();
    std::vector<std::thread> threads; threads.reserve(static_cast<size_t>(workerCount));
    for(int worker=0;worker<workerCount;++worker){
        const int y0=(height*worker)/workerCount, y1=(height*(worker+1))/workerCount;
        threads.emplace_back([=,&black](){
            uint64_t clipped=0;
            for(int y=y0;y<y1;++y){
                const int row=y*width;
                const int sensorPy=(y+originY)&1;
                for(int x=0;x<width;++x){
                    const int i=row+x;
                    const int plane=sensorPy*2+((x+originX)&1);
                    const size_t byteIndex=static_cast<size_t>(i)*2u;
                    const uint16_t rv=static_cast<uint16_t>(rawBytes[byteIndex])
                        | static_cast<uint16_t>(static_cast<uint16_t>(rawBytes[byteIndex+1])<<8u);
                    if(rv>=static_cast<uint16_t>(whiteLevel)) ++clipped;
                    else ++histogramBase[static_cast<size_t>(worker)*histogramBins
                            + static_cast<size_t>(plane)*static_cast<size_t>(whiteLevel)+rv];
                    const float bl=black[static_cast<size_t>(plane)];
                    const float denom=std::max(1.0f,static_cast<float>(whiteLevel)-bl);
                    float v=(static_cast<float>(rv)-bl)/denom;
                    v=std::max(0.0f,std::min(1.0f,v));
                    const int nv=static_cast<int>(std::floor(static_cast<double>(v*65535.0f+0.5f)));
                    normalizedOut[i]=static_cast<jshort>(static_cast<uint16_t>(nv));
                }
            }
            clippedBase[static_cast<size_t>(worker)]=clipped;
        });
    }
    for(auto& t:threads)t.join();
    std::vector<jlong> flatHistogram(histogramBins,0); uint64_t clipped=0;
    for(int worker=0;worker<workerCount;++worker){
        clipped+=workerClipped[static_cast<size_t>(worker)];
        const uint64_t* local=workerHistograms.data()+static_cast<size_t>(worker)*histogramBins;
        for(size_t bin=0;bin<histogramBins;++bin) flatHistogram[bin]+=static_cast<jlong>(local[bin]);
    }
    const auto computeEnd=std::chrono::steady_clock::now();
    const auto outputStart=std::chrono::steady_clock::now();
    env->SetShortArrayRegion(normArray,0,pixelCount,normalizedScratch.data());
    if(env->ExceptionCheck())return 0;
    const auto outputEnd=std::chrono::steady_clock::now();
    env->SetLongArrayRegion(histogramArray,0,static_cast<jsize>(histogramBins),flatHistogram.data());
    if(env->ExceptionCheck())return 0;
    const jlong stats[3]={
        static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(computeEnd-computeStart).count()),
        static_cast<jlong>(std::chrono::duration_cast<std::chrono::nanoseconds>(outputEnd-outputStart).count()),
        static_cast<jlong>(workerCount)};
    env->SetLongArrayRegion(statsArray,0,3,stats);
    return static_cast<jlong>(clipped);
}

'''
c=c.replace(marker,fn+marker,1)

R.write_text(r);N.write_text(n);C.write_text(c)
print('MONO_DEVICEPORT2B_BLACK_ORIGIN applied')
print(' - Monochrom neutral MHC parity retained; M9 closure-sharp dependency removed')
print(' - origin0 normalization remains exact legacy JNI')
print(' - nonzero RAW origins select Camera2 2x2 black/hist planes in sensor coordinates')
