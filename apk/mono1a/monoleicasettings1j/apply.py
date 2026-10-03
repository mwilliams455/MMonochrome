#!/usr/bin/env python3
"""LEICADISPLAYAIDS1A: live monochrome histogram + Leica-style highlight clipping warning."""
from pathlib import Path
import hashlib,json,re,sys,xml.etree.ElementTree as ET

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
pref_xml=root/"app/src/main/res/xml/preferences.xml"
keys_xml=root/"app/src/main/res/values/preference_keys.xml"
arrays_xml=root/"app/src/main/res/values/arrays.xml"
strings_xml=root/"app/src/main/res/values/strings.xml"
pref_java=J/"settings/PreferenceKeys.java"
fragment=J/"ui/camera/CameraFragment.java"
hud=J/"ui/camera/views/viewfinder/ViewfinderHudView.java"
gradle=root/"app/build.gradle"

for p in [pref_xml,keys_xml,arrays_xml,strings_xml,pref_java,fragment,hud,gradle]:
    if not p.is_file(): raise SystemExit("LEICADISPLAYAIDS1A missing "+str(p))
for receipt in ["LEICATIMER1A_ISOLATION.json","LEICABRACKET1B_ADMISSIONFIX1_ISOLATION.json"]:
    if not (root/receipt).is_file(): raise SystemExit("LEICADISPLAYAIDS1A missing parent receipt "+receipt)

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,label):
    n=s.count(a)
    if n!=1: raise SystemExit(f"LEICADISPLAYAIDS1A {label} anchor count={n}")
    return s.replace(a,b,1)
def append_resource(path,fragment_text):
    s=path.read_text()
    first=fragment_text.splitlines()[0]
    if first in s: raise SystemExit("LEICADISPLAYAIDS1A resource already present "+str(path))
    path.write_text(one(s,"</resources>",fragment_text+"\n</resources>",path.name))

# Strict display-only isolation.
frozen=[
 J/"m9/render/M9R35Renderer.java",J/"m9/render/M9NativeColorCore.java",
 J/"m9/export/MonoDngWriter1A.java",J/"m9/export/MonoLinearPlane1A.java",
 J/"m9/export/MonoDngExport1A.java",J/"processing/parameters/IsoExpoSelector.java",
 J/"capture/CaptureController.java",J/"m9/exposure/MonoExposurePlan1A.java",
 J/"m9/preview/MonoGpuPreview2A.java",root/"app/src/main/cpp/m9color_jni.cpp",
 root/"app/src/main/assets/shaders/preview/main_fs.glsl",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}

# ----- Leica Monochrom settings ------------------------------------------------
append_resource(keys_xml,'''    <string name="pref_mono_histogram_key" translatable="false">pref_mono_histogram_key</string>
    <string name="pref_mono_highlight_clipping_key" translatable="false">pref_mono_highlight_clipping_key</string>''')
append_resource(strings_xml,'''    <string name="mono_histogram">Histogram</string>
    <string name="mono_histogram_summary">Live luminance histogram from the rendered Monochrom viewfinder</string>
    <string name="mono_highlight_clipping">Highlight Clipping</string>
    <string name="mono_highlight_clipping_summary">Flash red where rendered viewfinder luminance reaches the selected threshold</string>
    <string name="mono_display_off">Off</string>
    <string name="mono_display_on">On</string>''')
append_resource(arrays_xml,'''    <string-array name="mono_histogram_entries">
        <item>Off</item><item>On</item>
    </string-array>
    <string-array name="mono_histogram_values">
        <item>0</item><item>1</item>
    </string-array>
    <string-array name="mono_highlight_clipping_entries">
        <item>Off</item><item>100%</item><item>99%</item><item>98%</item>
        <item>97%</item><item>96%</item><item>95%</item>
    </string-array>
    <string-array name="mono_highlight_clipping_values">
        <item>0</item><item>100</item><item>99</item><item>98</item>
        <item>97</item><item>96</item><item>95</item>
    </string-array>''')

ANDROID="http://schemas.android.com/apk/res/android";APP="http://schemas.android.com/apk/res-auto"
ET.register_namespace("android",ANDROID);ET.register_namespace("app",APP)
akey="{"+ANDROID+"}key"
tree=ET.parse(pref_xml);screen=tree.getroot()
cat=next((n for n in list(screen) if n.attrib.get(akey)=="@string/pref_category_monochrom_key"),None)
if cat is None: raise SystemExit("LEICADISPLAYAIDS1A Monochrom category missing")
for key in ["@string/pref_mono_histogram_key","@string/pref_mono_highlight_clipping_key"]:
    if any(n.attrib.get(akey)==key for n in list(cat)): raise SystemExit("display pref already present "+key)
def lp(key,title,summary,entries,values,default):
    return ET.Element("ListPreference",{
        "{"+ANDROID+"}layout":"@layout/preference_with_margin",
        akey:key,"{"+ANDROID+"}title":title,"{"+ANDROID+"}summary":summary,
        "{"+ANDROID+"}icon":"@drawable/ic_exposure",
        "{"+ANDROID+"}entries":entries,"{"+ANDROID+"}entryValues":values,
        "{"+ANDROID+"}defaultValue":default,"{"+APP+"}useSimpleSummaryProvider":"true"})
children=list(cat)
anchor_idx=next((i for i,n in enumerate(children)
                 if n.attrib.get(akey)=="@string/pref_mono_bracket_step_key"),len(children)-1)
cat.insert(anchor_idx+1,lp("@string/pref_mono_histogram_key","@string/mono_histogram",
    "@string/mono_histogram_summary","@array/mono_histogram_entries","@array/mono_histogram_values","0"))
cat.insert(anchor_idx+2,lp("@string/pref_mono_highlight_clipping_key","@string/mono_highlight_clipping",
    "@string/mono_highlight_clipping_summary","@array/mono_highlight_clipping_entries",
    "@array/mono_highlight_clipping_values","0"))
ET.indent(tree,space="    ");tree.write(pref_xml,encoding="utf-8",xml_declaration=True)

# ----- preference plumbing ----------------------------------------------------
s=pref_java.read_text()
s=one(s,
"        COMMON_KEYS.add(Key.KEY_MONO_BRACKET_STEP.mValue);\n",
"        COMMON_KEYS.add(Key.KEY_MONO_BRACKET_STEP.mValue);\n"
"        COMMON_KEYS.add(Key.KEY_MONO_HISTOGRAM.mValue);\n"
"        COMMON_KEYS.add(Key.KEY_MONO_HIGHLIGHT_CLIPPING.mValue);\n",
"display aid global keys")
s=one(s,
"        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_BRACKET_STEP, 1); // half-stop units = 0.5 EV\n",
"        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_BRACKET_STEP, 1); // half-stop units = 0.5 EV\n"
"        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_HISTOGRAM, 0);\n"
"        settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_HIGHLIGHT_CLIPPING, 0);\n",
"display aid defaults")
getter_anchor='''    public static int getMonoBracketStepHalfStopsValue() {
        int step=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL,Key.KEY_MONO_BRACKET_STEP);
        step=Math.max(1,Math.min(4,step));
        if(getMonoBracketFramesValue()==7 && step>2) {
            step=2;
            preferenceKeys.settingsManager.set(SCOPE_GLOBAL,Key.KEY_MONO_BRACKET_STEP,step);
        }
        return step;
    }
'''
s=one(s,getter_anchor,getter_anchor+'''
    public static boolean isMonoHistogramEnabled() {
        return preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL,Key.KEY_MONO_HISTOGRAM)!=0;
    }
    /** 0=Off; otherwise one of 95..100 percent. */
    public static int getMonoHighlightClippingPercent() {
        int value=preferenceKeys.settingsManager.getInteger(SCOPE_GLOBAL,Key.KEY_MONO_HIGHLIGHT_CLIPPING);
        if(value==0)return 0;
        return Math.max(95,Math.min(100,value));
    }
''',"display aid getters")
s=one(s,
"        KEY_MONO_BRACKET_STEP(R.string.pref_mono_bracket_step_key),\n",
"        KEY_MONO_BRACKET_STEP(R.string.pref_mono_bracket_step_key),\n"
"        KEY_MONO_HISTOGRAM(R.string.pref_mono_histogram_key),\n"
"        KEY_MONO_HIGHLIGHT_CLIPPING(R.string.pref_mono_highlight_clipping_key),\n",
"display aid enum keys")
pref_java.write_text(s)

# ----- Viewfinder overlay: monochrome histogram + red flashing clip mask -------
s=hud.read_text()
s=one(s,
"import android.graphics.Canvas;\n",
"import android.graphics.Canvas;\nimport android.graphics.Bitmap;\nimport android.graphics.RectF;\nimport android.os.SystemClock;\n",
"HUD display imports")
s=one(s,
'''    private final Paint histChannelPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Path histPath = new Path();
''',
'''    private final Paint histChannelPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint monoHistPaint = new Paint(Paint.ANTI_ALIAS_FLAG);
    private final Paint monoClipPaint = new Paint(Paint.FILTER_BITMAP_FLAG);
    private final Path histPath = new Path();
    private final Path monoHistPath = new Path();
''',"HUD mono paints")
s=one(s,
'''    private int mHudMode = 0; // 0 = Off, 1 = HUD, 2 = HUD + Histogram
''',
'''    private int mHudMode = 0; // 0 = Off, 1 = HUD, 2 = HUD + Histogram
    private static final String MONO_DISPLAY_REVISION="LEICADISPLAYAIDS1A";
    private boolean mMonoHistogramEnabled = false;
    private int mMonoHighlightPercent = 0;
    private final int[] mMonoHistData = new int[64];
    private int mMonoHistMaxY = 1;
    private Bitmap mMonoClipBitmap = null;
    private boolean mMonoHasClipping = false;
''',"HUD mono state")
s=one(s,
'''        histBorderPaint.setStrokeWidth(1.0f * mDensity);
    }
''',
'''        histBorderPaint.setStrokeWidth(1.0f * mDensity);
        monoHistPaint.setColor(Color.WHITE);
        monoHistPaint.setStyle(Paint.Style.FILL);
        monoClipPaint.setAlpha(190);
    }

    public void setMonoAssistMode(boolean histogramEnabled,int highlightPercent) {
        boolean changed=mMonoHistogramEnabled!=histogramEnabled || mMonoHighlightPercent!=highlightPercent;
        mMonoHistogramEnabled=histogramEnabled;
        mMonoHighlightPercent=highlightPercent<=0?0:Math.max(95,Math.min(100,highlightPercent));
        if(mMonoHighlightPercent==0)mMonoHasClipping=false;
        if(changed)invalidate();
    }

    /** Called on UI thread with a sampled rendered-viewfinder luminance result. */
    public void setMonoAssistData(int[] histogram,int histogramMax,int[] clipPixels,int clipW,int clipH,
                                  boolean hasClipping) {
        if(histogram!=null) {
            int n=Math.min(mMonoHistData.length,histogram.length);
            System.arraycopy(histogram,0,mMonoHistData,0,n);
            if(n<mMonoHistData.length)java.util.Arrays.fill(mMonoHistData,n,mMonoHistData.length,0);
            mMonoHistMaxY=Math.max(1,histogramMax);
        }
        if(clipPixels!=null&&clipW>0&&clipH>0) {
            if(mMonoClipBitmap==null||mMonoClipBitmap.getWidth()!=clipW||mMonoClipBitmap.getHeight()!=clipH) {
                if(mMonoClipBitmap!=null&&!mMonoClipBitmap.isRecycled())mMonoClipBitmap.recycle();
                mMonoClipBitmap=Bitmap.createBitmap(clipW,clipH,Bitmap.Config.ARGB_8888);
            }
            mMonoClipBitmap.setPixels(clipPixels,0,clipW,0,0,clipW,clipH);
        }
        mMonoHasClipping=hasClipping;
        invalidate();
    }

    public void clearHudOnly() {
        if (mRotationAnimator != null) mRotationAnimator.cancel();
        mExpoText=null;mIsoText=null;mFocalText=null;mFocusText=null;mWbText=null;
        mHistColorsMap=null;
        invalidate();
    }
''',"HUD mono API")
# setHudMode(0) must not erase independent Monochrom display aids.
s=one(s,
'''            if (mode == 0) {
                clear();
            } else {
''',
'''            if (mode == 0) {
                clearHudOnly();
            } else {
''',"HUD zero mode preserves mono aids")
# Full clear on camera lifecycle still clears all sampled aid data.
s=one(s,
'''        mHistColorsMap = null;
        invalidate();
''',
'''        mHistColorsMap = null;
        java.util.Arrays.fill(mMonoHistData,0);
        mMonoHistMaxY=1;
        mMonoHasClipping=false;
        if(mMonoClipBitmap!=null&&!mMonoClipBitmap.isRecycled())mMonoClipBitmap.eraseColor(Color.TRANSPARENT);
        invalidate();
''',"HUD full clear mono aids")
s=one(s,
'''        if (mHudMode == 1) {
            drawHUD(canvas);
        } else if (mHudMode == 2) {
            drawHUD(canvas);
            drawHistogram(canvas);
        }
''',
'''        if(mMonoHighlightPercent>0)drawMonoHighlightClipping(canvas);
        if (mHudMode == 1) {
            drawHUD(canvas);
        } else if (mHudMode == 2) {
            drawHUD(canvas);
            if(!mMonoHistogramEnabled)drawHistogram(canvas);
        }
        if(mMonoHistogramEnabled)drawMonoHistogram(canvas);
''',"HUD draw mono aids")
# Insert new drawing methods before onDetachedFromWindow.
detach='''    @Override
    protected void onDetachedFromWindow() {
'''
methods=r'''    private void drawMonoHighlightClipping(Canvas canvas) {
        if(!mMonoHasClipping||mMonoClipBitmap==null||mMonoClipBitmap.isRecycled())return;
        // First-generation M Monochrom review clipping flashes red. This is the
        // live-view adaptation: it overlays only the rendered viewfinder and is
        // never fed into capture/render/export.
        boolean visible=((SystemClock.uptimeMillis()/350L)&1L)==0L;
        if(visible) {
            RectF dst=new RectF(0f,0f,getWidth(),getHeight());
            canvas.drawBitmap(mMonoClipBitmap,null,dst,monoClipPaint);
        }
        postInvalidateDelayed(350L);
    }

    private void drawMonoHistogram(Canvas canvas) {
        float marginSide=14f*mDensity;
        float marginTop=12f*mDensity;
        float w=84f*mDensity;
        float h=40f*mDensity;
        boolean isLandscape=(mTargetOrientation==90||mTargetOrientation==270);
        float pivotX=canvas.getWidth()-marginSide-(isLandscape?(h/2f):(w/2f));
        float pivotY=marginTop+(isLandscape?(w/2f):(h/2f));
        float left=pivotX-w/2f, top=pivotY-h/2f, right=left+w, bottom=top+h;

        canvas.save();
        if(mAnimatedOrientation!=0f)canvas.rotate(mAnimatedOrientation,pivotX,pivotY);
        float bleedPad=2.5f*mDensity;
        canvas.drawRect(left-bleedPad,top-bleedPad,right+bleedPad,bottom+bleedPad,histBgPaint);
        canvas.drawRect(left,top,right,bottom,histBorderPaint);

        // The original DNG review histogram is divided into 11 sections. In
        // live view these are visual guides only; data comes from rendered
        // WYSIWYG luminance rather than raw DNG code values.
        for(int i=1;i<11;i++) {
            float x=left+w*(i/11f);
            canvas.drawLine(x,top,x,bottom,histBorderPaint);
        }

        monoHistPath.reset();
        monoHistPath.moveTo(left,bottom);
        float dx=w/(mMonoHistData.length-1f);
        for(int i=0;i<mMonoHistData.length;i++) {
            float v=Math.min(1f,mMonoHistData[i]/(float)Math.max(1,mMonoHistMaxY));
            monoHistPath.lineTo(left+i*dx,bottom-v*h);
        }
        monoHistPath.lineTo(right,bottom);
        monoHistPath.close();
        canvas.drawPath(monoHistPath,monoHistPaint);

        if(mMonoHighlightPercent>0) {
            int thresholdBin=Math.max(0,Math.min(63,
                    (int)Math.floor((mMonoHighlightPercent/100.0)*64.0)));
            float thresholdX=left+w*(thresholdBin/63f);
            Paint old=histBorderPaint;
            int oldColor=old.getColor();
            old.setColor(Color.RED);
            canvas.drawLine(thresholdX,top,thresholdX,bottom,old);
            old.setColor(oldColor);
        }
        canvas.restore();
    }

'''
s=one(s,detach,methods+detach,"HUD mono draw methods")
# Recycle the mask on detach.
s=one(s,
'''        if (mRotationAnimator != null) {
            mRotationAnimator.cancel();
        }
        super.onDetachedFromWindow();
''',
'''        if (mRotationAnimator != null) {
            mRotationAnimator.cancel();
        }
        if(mMonoClipBitmap!=null&&!mMonoClipBitmap.isRecycled()) {
            mMonoClipBitmap.recycle();
            mMonoClipBitmap=null;
        }
        super.onDetachedFromWindow();
''',"HUD mask lifecycle")
hud.write_text(s)

# ----- CameraFragment sampling ------------------------------------------------
s=fragment.read_text()
s=one(s,
"import java.util.concurrent.Future;\n",
"import java.util.concurrent.Future;\nimport java.util.concurrent.atomic.AtomicBoolean;\n",
"fragment AtomicBoolean import")
# New sample buffers next to existing histogram buffers.
s=one(s,
'''    private final int[] mHistPixels = new int[128 * 96];
    private final int[][] mHistData = new int[3][64];
''',
'''    private final int[] mHistPixels = new int[128 * 96];
    private final int[][] mHistData = new int[3][64];
    private final int[] mMonoHistData1J = new int[64];
    private final int[] mMonoClipPixels1J = new int[128 * 96];
    private final AtomicBoolean mDisplayAidSampleBusy1J = new AtomicBoolean(false);
''',"fragment mono aid buffers")
# updateScreenLog: publish independent mode and sample even when debug HUD is off.
old='''            int afDataMode = PreferenceKeys.getAfDataValue();
            if (mViewfinderHudView != null) {
                mViewfinderHudView.setHudMode(afDataMode);
            }
'''
new='''            int afDataMode = PreferenceKeys.getAfDataValue();
            boolean monoHistogram1J=PreferenceKeys.isMonoHistogramEnabled();
            int monoClipPercent1J=PreferenceKeys.getMonoHighlightClippingPercent();
            if (mViewfinderHudView != null) {
                mViewfinderHudView.setHudMode(afDataMode);
                mViewfinderHudView.setMonoAssistMode(monoHistogram1J,monoClipPercent1J);
            }
'''
s=one(s,old,new,"fragment display mode selection")
# Do not full-clear Monochrom aids just because generic debug HUD is disabled.
s=one(s,
'''                if (mViewfinderHudView != null) {
                    mViewfinderHudView.clear();
                }
            }
        });
''',
'''                if (mViewfinderHudView != null) {
                    if(monoHistogram1J||monoClipPercent1J>0)mViewfinderHudView.clearHudOnly();
                    else mViewfinderHudView.clear();
                }
            }
            if(monoHistogram1J||monoClipPercent1J>0)requestLiveHistogram();
        });
''',"fragment mono aid sample trigger")
# Existing generic histogram trigger stays, but requestLiveHistogram itself becomes overlap-safe.
s=one(s,
'''        if (mHistBitmap == null) {
            mHistBitmap = Bitmap.createBitmap(128, 96, Bitmap.Config.ARGB_8888);
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
''',
'''        if(!mDisplayAidSampleBusy1J.compareAndSet(false,true))return;
        if (mHistBitmap == null) {
            mHistBitmap = Bitmap.createBitmap(128, 96, Bitmap.Config.ARGB_8888);
        }

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
''',"histogram overlap guard")
s=one(s,
'''                    if (copyResult == android.view.PixelCopy.SUCCESS) {
                        processExecutorService.execute(this::processHistogramData);
                    }
''',
'''                    if (copyResult == android.view.PixelCopy.SUCCESS) {
                        processExecutorService.execute(this::processHistogramData);
                    } else {
                        mDisplayAidSampleBusy1J.set(false);
                    }
''',"PixelCopy failure unlock")
s=one(s,
'''            } catch (Exception ignored) {
            }
        }
    }
''',
'''            } catch (Exception ignored) {
                mDisplayAidSampleBusy1J.set(false);
            }
        } else {
            mDisplayAidSampleBusy1J.set(false);
        }
    }
''',"PixelCopy exception unlock")
# Replace processHistogramData method by brace parsing in Python.
start=s.index("    private void processHistogramData() {")
brace=s.index("{",start);depth=0;end=None
for i in range(brace,len(s)):
    if s[i]=="{":depth+=1
    elif s[i]=="}":
        depth-=1
        if depth==0:
            end=i+1;break
if end is None:raise SystemExit("processHistogramData end missing")
replacement=r'''    private void processHistogramData() {
        try {
            if (mHistBitmap == null || mHistBitmap.isRecycled()) return;
            int w=mHistBitmap.getWidth(),h=mHistBitmap.getHeight(),size=64;
            mHistBitmap.getPixels(mHistPixels,0,w,0,0,w,h);
            for(int i=0;i<3;i++)Arrays.fill(mHistData[i],0);
            Arrays.fill(mMonoHistData1J,0);
            Arrays.fill(mMonoClipPixels1J,Color.TRANSPARENT);

            boolean monoHistogram=PreferenceKeys.isMonoHistogramEnabled();
            int clipPercent=PreferenceKeys.getMonoHighlightClippingPercent();
            int clipCode=clipPercent<=0?256:(clipPercent>=100?255:
                    Math.round(255f*(clipPercent/100f)));
            int clipped=0,total=w*h;
            for(int i=0;i<total;i+=2) {
                int c=mHistPixels[i];
                int r=(c>>16)&0xFF,g=(c>>8)&0xFF,b=c&0xFF;
                // Remove Photon's magenta focus-peaking delta before display-aid measurement.
                int delta=Math.max(0,Math.min(r-g,b-g));
                int cleanR=Math.max(0,r-delta),cleanB=Math.max(0,b-delta);
                mHistData[0][cleanR*size/256]++;
                mHistData[1][g*size/256]++;
                mHistData[2][cleanB*size/256]++;

                int y=(77*cleanR+150*g+29*cleanB+128)>>8;
                mMonoHistData1J[y*size/256]++;
                if(clipPercent>0&&y>=clipCode) {
                    // Fill both pixels represented by 2x subsampling so the mask does
                    // not become a checkerboard when scaled to the viewfinder.
                    mMonoClipPixels1J[i]=0xD0FF0000;
                    if(i+1<total)mMonoClipPixels1J[i+1]=0xD0FF0000;
                    clipped++;
                }
            }

            int maxY=1,monoMax=1;
            for(int ch=0;ch<3;ch++)for(int j=0;j<size;j++) {
                mHistData[ch][j]=(int)Math.sqrt(mHistData[ch][j]);
                maxY=Math.max(maxY,mHistData[ch][j]);
            }
            for(int j=0;j<size;j++) {
                mMonoHistData1J[j]=(int)Math.sqrt(mMonoHistData1J[j]);
                monoMax=Math.max(monoMax,mMonoHistData1J[j]);
            }

            final int genericMax=maxY,finalMonoMax=monoMax;
            final boolean hasClipping=clipped>0;
            if(mViewfinderHudView!=null) {
                mViewfinderHudView.post(() -> {
                    if(PreferenceKeys.getAfDataValue()==2)
                        mViewfinderHudView.setHistogramData(mHistData,genericMax,size);
                    if(PreferenceKeys.isMonoHistogramEnabled()
                            ||PreferenceKeys.getMonoHighlightClippingPercent()>0) {
                        mViewfinderHudView.setMonoAssistData(mMonoHistData1J,finalMonoMax,
                                mMonoClipPixels1J,w,h,hasClipping);
                    }
                });
            }
        } finally {
            mDisplayAidSampleBusy1J.set(false);
        }
    }'''
s=s[:start]+replacement+s[end:]
fragment.write_text(s)

g=gradle.read_text();m=re.search(r"versionName\s+'([^']+)'",g)
if not m:raise SystemExit("LEICADISPLAYAIDS1A versionName missing")
if "leicadisplayaids1a" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-leicadisplayaids1a"+g[m.end(1):]
gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.is_file()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("LEICADISPLAYAIDS1A changed frozen photographic files "+repr(changed))

proof={
 "revision":"LEICADISPLAYAIDS1A",
 "cameraModel":"first_generation_Leica_M_Monochrom",
 "histogram":"live_rendered_luminance_64_bins_with_11_visual_sections",
 "histogramDefault":"Off",
 "highlightClippingChoicesPercent":[0,100,99,98,97,96,95],
 "highlightDefault":"Off",
 "highlightColor":"red",
 "highlightBehavior":"flashing_live_viewfinder_overlay",
 "sampleSource":"rendered_TextureView_via_PixelCopy_128x96",
 "focusPeakingNeutralizedBeforeMeasurement":True,
 "displayOnly":True,
 "captureExposureChanged":False,
 "rendererChanged":False,
 "dngChanged":False,
 "previewShaderChanged":False,
 "jpegChanged":False,
 "genericDebugHudStillAvailable":True,
 "frozenPhotographicHashes":after,
}
(root/"LEICADISPLAYAIDS1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
