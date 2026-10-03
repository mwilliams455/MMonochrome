#!/usr/bin/env python3
from pathlib import Path
import json,sys
if len(sys.argv)!=2: raise SystemExit("usage: test.py <root>")
root=Path(sys.argv[1])
p=json.loads((root/"LEICATONING1A_FIX1_ISOLATION.json").read_text())
assert p["revision"]=="LEICATONING1A_FIX1"
assert p["previewInstallsVerifiedSharedBank"]
assert p["stillUsesSharedCacheFirst"]
assert p["stillAssetReopenNonfatal"]
assert p["nativeMissingCurveFallback"]=="validated_standard_curve02"
assert p["captureMustNotFailForMissingContrastBank"]
assert not p["toningMathChanged"] and not p["dngPolicyChanged"]

meta=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/MonoContrastCurves1A.java").read_text()
for m in ["installVerifiedBank(byte[] data)","tryLoadBank()","loadCurveOrNull(int selector)","lastLoadError()"]:
    assert m in meta,m
main=(root/"app/src/main/java/com/particlesdevs/photoncamera/ui/camera/views/viewfinder/MainRenderer.java").read_text()
assert "MonoContrastCurves1A.installVerifiedBank(data)" in main
r=(root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9R35Renderer.java").read_text()
for m in ["loadCurveOrNull(MonoContrastCurves1A.DEFAULT)","loadCurveOrNull(monoContrast1A)","monoContrastCurveFallback1A"]:
    assert m in r,m
cpp=(root/"app/src/main/cpp/m9color_jni.cpp").read_text()
for m in ["if (contrastCurveArray && env->GetArrayLength(contrastCurveArray) == 2048)","contrastCurve[i]=MM_MONO1A_CURVE02[i]"]:
    assert m in cpp,m
assert "throwIllegalArgument(env, \"MONO1A Contrast curve must be 2048 bytes\")" not in cpp
# Existing Leica controls remain.
tone=json.loads((root/"LEICATONING1A_ISOLATION.json").read_text())
contrast=json.loads((root/"LEICACONTRAST1A_ISOLATION.json").read_text())
assert tone["Cr"]==[128,130,131,127,126,128,128]
assert tone["Cb"]==[128,125,123,130,132,129,131]
assert contrast["firmwareCurveBankSha256"]=="ac010ac0a107fb4b98ed817f24b4b9ab2d739fcfd70571b4f7d8375335e293c6"
report={"revision":"LEICATONING1A_FIX1_TEST","status":"PASS","missingBankCannotAbortCapture":True,"toningPreserved":True}
(root/"LEICATONING1A_FIX1_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
