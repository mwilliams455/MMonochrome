#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,re,sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
writer=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngWriter1A.java"
gradle=root/"app/build.gradle"
if not writer.exists(): raise SystemExit("MonoDngWriter1A missing")
s=writer.read_text()
before=s.encode()
# Emit a real runtime/file marker so the packaged APK and generated DNG can be
# distinguished from the earlier tag-placement bug.
marker='    public static final String METADATA_REVISION="MONOOUTPUT1D_BASELINE_RAWIFD";\n'
ctor='    private MonoDngWriter1A() {}\n'
if marker not in s:
    if s.count(ctor)!=1: raise SystemExit("writer constructor anchor mismatch")
    s=s.replace(ctor,ctor+marker,1)
# Also put the revision in Software metadata; this does not touch raw samples.
s=s.replace('main.u16(284,1);main.text(305,"MMonochrome MONODNG1A");',
            'main.u16(284,1);main.text(305,"MMonochrome MONODNG1D "+METADATA_REVISION);',1)
old='''        double compensation=Math.log(plane.sourceUnitsPerWhite)/Math.log(2);
        main.add(50730,SRATIONAL,1,rational(Math.round(compensation*1000000),1000000));
        main.add(50731,RATIONAL,1,rational(1,1));main.add(50732,RATIONAL,1,rational(1,1));
'''
new='''        double compensation=Math.log(plane.sourceUnitsPerWhite)/Math.log(2);
        // MONOOUTPUT1D_BASELINE_RAWIFD:
        // BaselineExposure describes development of the full-resolution raw image.
        // Keep the preview IFD free of this raw-development hint.
        main.add(50731,RATIONAL,1,rational(1,1));main.add(50732,RATIONAL,1,rational(1,1));
'''
if s.count(old)!=1:
    raise SystemExit("BaselineExposure preview-IFD anchor mismatch")
s=s.replace(old,new,1)
anchor='''        raw.u16(50713,1,1);raw.add(50714,RATIONAL,1,rational(0,1));raw.u32(50717,65535);
'''
replace='''        raw.u16(50713,1,1);raw.add(50714,RATIONAL,1,rational(0,1));raw.u32(50717,65535);
        raw.add(50730,SRATIONAL,1,rational(Math.round(compensation*1000000),1000000));
'''
if s.count(anchor)!=1:
    raise SystemExit("raw IFD anchor mismatch")
s=s.replace(anchor,replace,1)
writer.write_text(s)

g=gradle.read_text()
m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("versionName missing")
if "monooutput1d" not in m.group(1):
    g=g[:m.start(1)]+m.group(1)+"-monooutput1d"+g[m.end(1):]
    gradle.write_text(g)

# Narrow isolation: this overlay may modify only writer + version label.
proof={
  "revision":"MONOOUTPUT1D_BASELINE_RAWIFD",
  "writerBeforeSha256":hashlib.sha256(before).hexdigest(),
  "writerAfterSha256":hashlib.sha256(writer.read_bytes()).hexdigest(),
  "pixelDataChanged":False,
  "linearPlaneChanged":False,
  "jpegRendererChanged":False,
  "exposurePlanChanged":False,
  "previewShaderChanged":False,
  "dngStorageScaleChanged":False,
  "change":"move_DNG_BaselineExposure_50730_from_preview_IFD0_to_full_resolution_LinearRaw_SubIFD"
}
(root/"MONOOUTPUT1D_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
