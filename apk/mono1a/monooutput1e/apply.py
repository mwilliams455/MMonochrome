#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
writer = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/export/MonoDngWriter1A.java"
gradle = root / "app/build.gradle"
if not writer.exists():
    raise SystemExit("MonoDngWriter1A missing")

s = writer.read_text()
before = s.encode()

# MONOOUTPUT1E: Adobe DNG BaselineExposure is an IFD0 development hint.
# The MONOOUTPUT1C writer already emits it on main/IFD0; preserve that location
# and only add an unmistakable file/runtime revision marker.
main_tag = 'main.add(50730,SRATIONAL,1,rational(Math.round(compensation*1000000),1000000));'
raw_tag = 'raw.add(50730,SRATIONAL,1,rational(Math.round(compensation*1000000),1000000));'
if s.count(main_tag) != 1:
    raise SystemExit("expected exactly one BaselineExposure tag on IFD0")
if raw_tag in s:
    raise SystemExit("unexpected BaselineExposure tag on raw SubIFD")

marker = '    public static final String METADATA_REVISION="MONOOUTPUT1E_BASELINE_IFD0";\n'
ctor = '    private MonoDngWriter1A() {}\n'
if marker not in s:
    if s.count(ctor) != 1:
        raise SystemExit("writer constructor anchor mismatch")
    s = s.replace(ctor, ctor + marker, 1)

old_software = 'main.u16(284,1);main.text(305,"MMonochrome MONODNG1A");'
new_software = 'main.u16(284,1);main.text(305,"MMonochrome MONODNG1E "+METADATA_REVISION);'
if old_software in s:
    s = s.replace(old_software, new_software, 1)
elif new_software not in s:
    raise SystemExit("Software tag anchor mismatch")

# Add a source comment beside the retained IFD0 BaselineExposure, without
# touching the arithmetic or raw samples.
needle = '''        double compensation=Math.log(plane.sourceUnitsPerWhite)/Math.log(2);
        main.add(50730,SRATIONAL,1,rational(Math.round(compensation*1000000),1000000));
'''
replacement = '''        double compensation=Math.log(plane.sourceUnitsPerWhite)/Math.log(2);
        // MONOOUTPUT1E_BASELINE_IFD0: DNG BaselineExposure remains on IFD0.
        main.add(50730,SRATIONAL,1,rational(Math.round(compensation*1000000),1000000));
'''
if needle in s:
    s = s.replace(needle, replacement, 1)
elif "MONOOUTPUT1E_BASELINE_IFD0: DNG BaselineExposure remains on IFD0." not in s:
    raise SystemExit("BaselineExposure block anchor mismatch")

writer.write_text(s)

g = gradle.read_text()
m = re.search(r"versionName\s+'([^']+)'", g)
if not m:
    raise SystemExit("versionName missing")
if "monooutput1e" not in m.group(1):
    g = g[:m.start(1)] + m.group(1) + "-monooutput1e" + g[m.end(1):]
    gradle.write_text(g)

proof = {
    "revision": "MONOOUTPUT1E_BASELINE_IFD0",
    "writerBeforeSha256": hashlib.sha256(before).hexdigest(),
    "writerAfterSha256": hashlib.sha256(writer.read_bytes()).hexdigest(),
    "baselineExposureLocation": "IFD0_only",
    "pixelDataChanged": False,
    "linearPlaneChanged": False,
    "jpegRendererChanged": False,
    "exposurePlanChanged": False,
    "previewShaderChanged": False,
    "dngStorageScaleChanged": False,
    "change": "retain_DNG_BaselineExposure_50730_on_IFD0_remove_none_from_raw_SubIFD_add_revision_marker"
}
(root / "MONOOUTPUT1E_ISOLATION.json").write_text(json.dumps(proof, indent=2) + "\n")
print(json.dumps(proof, indent=2))
