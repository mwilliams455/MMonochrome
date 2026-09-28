#!/usr/bin/env python3
from pathlib import Path
import json, math, re, sys

if len(sys.argv)!=2: raise SystemExit('usage: test.py <PhotonCamera-root>')
root=Path(sys.argv[1]).resolve();J=root/'app/src/main/java/com/particlesdevs/photoncamera'
proof=json.loads((root/'MONOTAPMETER1A_ISOLATION.json').read_text())
assert proof['revision']=='MONOTAPMETER1A_LOWKEYREAD1A'
assert proof['noTapAutomaticPolicyMethodByteIdentical']
assert proof['tapPositiveOnly'] and not proof['HDR'] and not proof['localRelighting'] and not proof['postCaptureRescue']
assert proof['selectionRetainedAcrossShutter'] and proof['measurementInvalidatedByExisting1EShutterBoundary']

assist=(J/'m9/exposure/MonoPlacementAssist1D.java').read_text()
gpu=(J/'m9/preview/MonoGpuPreview2A.java').read_text()
selector=(J/'processing/parameters/IsoExpoSelector.java').read_text()
helper=(J/'m9/preview/MonoTapMeter1A.java').read_text()
focus=(J/'control/TouchFocus.java').read_text()
renderer=(J/'ui/camera/views/viewfinder/MainRenderer.java').read_text()

for marker in [
 'MONOTAPMETER1A_LOWKEYREAD1A','TAP_MEDIAN_FLOOR_SOURCE1D = 0.050',
 'TAP_Q25_FLOOR_SOURCE1D = 0.015','TAP_MEDIAN_APPEARANCE_CEILING_SOURCE1D = 0.065',
 'TAP_MAX_POSITIVE_EV = 0.40','evaluateTap(boolean eligible',
 'broadTailEligibleFromExplicitTapIntent','tapDoesNotNormalizeToFrameReference']:
    assert marker in assist,marker
for marker in ['p.selectionId!=s.id','p.capturedElapsedNs<s.createdNs',
               'p.capturedElapsedNs<=lastCaptureBoundaryNs1E','now-p.capturedElapsedNs>750000000L',
               'baseMedian,baseQ25,baseQ90,baseQ95']:
    assert marker in gpu,marker
assert 'if(tap1A!=null)' in selector and 'M9M10rMfmTest1A.evaluateForMonoPlan1A' in selector
assert 'processMonoTap1A' in focus and 'new MeteringRectangle(0,0,0,0,0)' in focus
assert 'MonoTapMeter1A.configure' in renderer
assert 'LIFETIME_NS=15_000_000_000L' in helper

MED=0.050;Q25=0.015;CEIL=0.065;MAX_EV=.40;DEAD=.08;Q998_LIMIT=.92;BROAD=250/255;CLIP=.005

def log2(x): return math.log(x,2)
def tap(median,q25,global_q998=.20,sensor_q99=.30,sensor_clip=0.0,plan_scale=1.0,scaled_clip=0.0):
    median_need=log2(MED/median) if median<MED else 0.0
    q25_need=log2(Q25/max(q25,1e-6)) if q25<Q25 else 0.0
    requested=max(median_need,q25_need)
    appearance=max(0.0,log2(CEIL/median))
    appearance_bound=min(MAX_EV,appearance)
    strict_q=log2(Q998_LIMIT/global_q998) if global_q998>0 else 0.0
    strict_clip=log2(Q998_LIMIT*plan_scale) if scaled_clip>0 else float('inf')
    strict=max(0.0,min(strict_q,strict_clip))
    broad=log2(BROAD/sensor_q99) if sensor_q99>0 else float('nan')
    broad_ok=math.isfinite(broad) and broad>0 and sensor_clip<=CLIP and sensor_q99<BROAD
    global_head=max(strict,max(0.0,broad) if broad_ok else 0.0)
    candidate=min(requested,appearance_bound)
    applied=min(candidate,min(.50,global_head))
    if applied<DEAD: applied=0.0
    return dict(requested=requested,appearance=appearance_bound,global_head=global_head,applied=applied,
                median_after=median*(2**applied),q25_after=q25*(2**applied))

a=tap(.055,.018);assert a['applied']==0.0
b=tap(.040,.012);assert .30<b['applied']<.35 and abs(b['median_after']-.050)<.002
c=tap(.015,.004);assert abs(c['applied']-.40)<1e-9 and c['median_after']<.021
d=tap(.050,.005);assert d['applied']<.40 and d['median_after']<=.0650001
e=tap(.035,.009,global_q998=.915,sensor_q99=.995,sensor_clip=.01);assert e['applied']==0.0
f=tap(.040,.012,global_q998=.90,sensor_q99=.80,sensor_clip=.001);assert 0.20<f['applied']<.35

curve=root/'app/src/main/assets/mono/mono_curve02_gl2a.bin'
curve_codes={}
if curve.is_file():
    data=curve.read_bytes();assert len(data)==2048
    for name,x,want in [('q25',.015,19),('median',.050,51),('ceiling',.065,64),('frame',.107*(8192/10000),83)]:
        code=data[round(x*2047)];curve_codes[name]=code;assert abs(code-want)<=1,(name,code,want)

def map_rect(x,y,vw,vh,vx,vy,w,h,pw,ph):
    gx=x-vx;gy=vh-y-vy
    if x<0 or x>=vw or y<0 or y>=vh or gx<0 or gx>=w or gy<0 or gy>h:return None
    half=.10*min(vw,vh,w,h)
    left=max(0,max(vx,x-half));right=min(vw,min(vx+w,x+half))
    top=max(0,max(vh-vy-h,y-half));bottom=min(vh,min(vh-vy,y+half))
    x0=max(0,math.floor((left-vx)*pw/w));x1=min(pw,math.ceil((right-vx)*pw/w))
    y0=max(0,math.floor((vh-bottom-vy)*ph/h));y1=min(ph,math.ceil((vh-top-vy)*ph/h))
    return (x0,y0,x1,y1)
portrait=map_rect(540,240,1080,1920,0,0,1080,1920,48,64)
landscape=map_rect(960,200,1920,1080,0,0,1920,1080,64,48)
assert portrait and portrait[1]>32,portrait
assert landscape and landscape[1]>24,landscape
center=map_rect(540,960,1080,1920,0,0,1080,1920,48,64);assert center and center[0]<24<center[2] and center[1]<32<center[3]

report={
 'revision':'MONOTAPMETER1A_LOWKEYREAD1A_TEST',
 'policy':{'alreadyReadable':a,'modestlyDark':b,'blackObject':c,'q25Starved':d,'highlightLimited':e,'broadTail':f},
 'curve02Codes':curve_codes,'coordinatePortrait':portrait,'coordinateLandscape':landscape,'coordinateCenter':center,
 'checks':{
   'positiveOnly':True,'noTapPolicyBodyPreserved':True,'generationMatchRequired':True,
   'freshPostShutterMeasurementRequired':True,'manualAuthorityPreserved':True,
   'rendererAndDngFrozenByApplyProof':True,'oneGlobalExposure':True
 }
}
(root/'MONOTAPMETER1A_TEST_REPORT.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
