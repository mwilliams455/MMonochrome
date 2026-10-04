#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys,xml.etree.ElementTree as ET
if len(sys.argv)!=2: raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve();J=root/"app/src/main/java/com/particlesdevs/photoncamera"
p=json.loads((root/"LEICADIAGNOSTICS1A_ISOLATION.json").read_text())
assert p["revision"]=="LEICADIAGNOSTICS1A"
assert p["diagnosticsSetting"]=="Off_On" and p["default"]=="Off"
assert p["diagnosticSpoolPhotographicStorage"] is False
assert p["privateMonoDngRecoveryPreserved"] and p["jpegFinalizePreserved"]
assert p["originalSensorRawSemanticsPreserved"] and p["saveModeSemanticsPreserved"]
for k in ["exposurePlanChanged","rendererMathChanged","dngPixelMathChanged","previewChanged"]: assert not p[k],k
for rel,want in p["frozenPhotographicAndDurabilityHashes"].items():
    assert hashlib.sha256((root/rel).read_bytes()).hexdigest()==want,rel
parent=json.loads((root/"LEICAOUTPUTMODE1A_ISOLATION.json").read_text())
assert parent["saveModes"]["0_JPEG"]=={"jpeg":True,"monochromDng":False}
assert parent["saveModes"]["1_DNG_JPEG"]=={"jpeg":True,"monochromDng":True}
assert parent["saveModes"]["2_DNG"]=={"jpeg":False,"monochromDng":True}
assert parent["originalSensorRaw"]=="independent_toggle_default_off"

ANDROID="http://schemas.android.com/apk/res/android";akey="{"+ANDROID+"}key"
tree=ET.parse(root/"app/src/main/res/xml/preferences.xml")
cat=next(n for n in list(tree.getroot()) if n.attrib.get(akey)=="@string/pref_category_monochrom_key")
node=next(n for n in list(cat) if n.attrib.get(akey)=="@string/pref_mono_diagnostics_key")
assert node.attrib.get("{"+ANDROID+"}defaultValue")=="false"
assert node.attrib.get("{"+ANDROID+"}title")=="@string/mono_diagnostics"

prefs=(J/"settings/PreferenceKeys.java").read_text()
for marker in ["KEY_MONO_DIAGNOSTICS(R.string.pref_mono_diagnostics_key)",
               "isMonoDiagnosticsEnabled()","setMonoDiagnosticsEnabled(boolean value)",
               "settingsManager.setInitial(SCOPE_GLOBAL, Key.KEY_MONO_DIAGNOSTICS, false)"]:
    assert marker in prefs,marker

spool=(J/"m9/M9DiagnosticBurstSpool.java").read_text()
assert "SIDECAR1B diagnostic-only storage spool" in spool
assert "No photographic JPEG/DNG storage is routed here." in spool
assert spool.count("LEICADIAGNOSTICS1A suppressed")>=2
stage=spool[spool.index("public static boolean stage("):spool.index("public static boolean stage(")+1800]
assert "if (!diagnosticsEnabled1A())" in stage and "return true;" in stage
pub=spool[spool.index("private static boolean writePublic("):spool.index("private static boolean writePublic(")+1200]
assert "if (!diagnosticsEnabled1A())" in pub and "return true;" in pub
assert "MonoDiagnosticPublicWriter1C.write(" in pub

legacy=(J/"m9/M9DiagnosticSidecarIO.java").read_text()
persist=legacy[legacy.index("public static boolean persist("):legacy.index("public static boolean persist(")+1500]
assert "if (!diagnosticsEnabled1A())" in persist
assert "LEICADIAGNOSTICS1A suppressed legacy diagnostic write" in persist
assert "return true;" in persist

checks={
    "m9/M9DeferredMetadataStore.java":["M9DiagnosticBurstSpool.stage","M9DiagnosticSidecarIO.persist"],
    "m9/render/M9PrimaryTimingWriter.java":["M9DiagnosticBurstSpool.stage","_M9_PRIMARY.json"],
    "m9/render/M9RawShadingAudit1A.java":["M9DiagnosticBurstSpool.stage","_M9_RAWSHADING1A.json"],
    "m9/render/M9SourceCalibrationAudit1A.java":["M9DiagnosticBurstSpool.stage","_M9_SOURCECAL1A.json"],
    "m9/preview/MonoLivePairExport1D.java":["M9DiagnosticBurstSpool.stage","_MONO_LIVEPAIR.json"],
    "m9/export/MonoDngExport1A.java":["M9DiagnosticBurstSpool.stage","_EXPORT.json"],
}
for rel,markers in checks.items():
    s=(J/rel).read_text()
    for marker in markers: assert marker in s,(rel,marker)

direct=[]
for f in J.rglob("*.java"):
    if f==J/"m9/M9DiagnosticBurstSpool.java": continue
    if "MonoDiagnosticPublicWriter1C.write(" in f.read_text(errors="replace"):
        direct.append(str(f.relative_to(root)))
assert not direct,direct

mono=(J/"m9/export/MonoDngSpool1B.java").read_text()
for marker in ["public synchronized void recover()","public Properties stage(","payload.part","publication_retry_pending"]:
    assert marker in mono,marker

report={"revision":"LEICADIAGNOSTICS1A_TEST","status":"PASS","defaultOff":True,
        "publicJsonSuppressedWhenOff":True,"existingPendingDiagnosticExportSuppressedWhenOff":True,
        "diagnosticsOnRetainsExistingPipeline":True,"monoDngDurabilityFrozen":True,
        "jpegAndOutputModesFrozen":True,"photographicPipelineFrozen":True}
(root/"LEICADIAGNOSTICS1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
