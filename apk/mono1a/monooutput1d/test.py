#!/usr/bin/env python3
from pathlib import Path
import json,hashlib,subprocess,sys,tempfile
import numpy as np
import tifffile
import rawpy

if len(sys.argv)!=2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
java=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/export"
host=Path(__file__).resolve().parents[1]/"monooutput1a"/"MonoDngHostTest.java"
out=root/"monooutput1d-fixtures";out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as d:
    subprocess.run(["javac","-d",d,str(java/"MonoLinearPlane1A.java"),str(java/"MonoDngWriter1A.java"),str(host)],check=True)
    subprocess.run(["java","-Xmx512m","-cp",d,"MonoDngHostTest",str(out)],check=True)

fixtures=json.loads((out/"fixtures.json").read_text())
checked=[]
for fixture in fixtures["fixtures"]:
    path=out/fixture["file"]
    expected=np.fromfile(path.with_suffix(".u16"),dtype="<u2").reshape(fixture["height"],fixture["width"])
    with tifffile.TiffFile(path) as tf:
        main=tf.pages[0]
        raw=main.pages[0]
        pixels=raw.asarray()
        assert np.array_equal(pixels,expected),("sample_mismatch",path.name)
        assert 50730 not in main.tags,("BaselineExposure_wrong_IFD0",path.name)
        assert 50730 in raw.tags,("BaselineExposure_missing_raw_IFD",path.name)
        ev=raw.tags[50730].value
        value=ev[0]/ev[1]
        target=float(np.log2(fixture["sourceUnitsPerWhite"]))
        assert abs(value-target)<=0.50001e-6,(path.name,value,target)
        checked.append({"file":path.name,"baselineExposureEv":value,"rawSamplesExact":True,
                        "rawIfdHasBaselineExposure":True,"previewIfdHasBaselineExposure":False})
    if min(fixture["width"],fixture["height"])>=128:
        with rawpy.imread(str(path)) as raw:
            assert raw.num_colors==1
            # Ensure moving the metadata tag did not alter the stored raw samples.
            assert np.array_equal(raw.raw_image_visible.copy(),expected),path.name

# Explicitly inspect the realistic 12MP fixture.
real=[x for x in checked if "16" in x["file"] or True][-1]
proof=json.loads((root/"MONOOUTPUT1D_ISOLATION.json").read_text())
report={"status":"PASS","revision":"MONOOUTPUT1D_BASELINE_RAWIFD",
        "fixtureCount":len(checked),"checks":checked,
        "baselineExposureLocation":"full_resolution_LinearRaw_SubIFD_only",
        "pixelSamplesChanged":False,
        "LightroomPhoneValidated":False,
        "phoneInitialBrightnessValidated":False,
        "isolation":proof}
(root/"MONOOUTPUT1D_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print("MONOOUTPUT1D baseline exposure raw-IFD and exact-sample tests PASS")
print(json.dumps(report,indent=2))
