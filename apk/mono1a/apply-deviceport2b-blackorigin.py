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
print(' - origin0 normalization remains exact legacy JNI')
print(' - nonzero RAW origins select Camera2 2x2 black/hist planes in sensor coordinates')
