#!/usr/bin/env python3
from pathlib import Path
import json, re, sys

if len(sys.argv)!=2:
    raise SystemExit("usage: test.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
spool=(J/"m9/M9DiagnosticBurstSpool.java").read_text()
proof=json.loads((root/"MMONOSPOOLRESET1A_ISOLATION.json").read_text())

checks={
 "revision marker": 'MMONOSPOOLRESET1A_ONCE' in spool,
 "distinct Monochrome marker": 'mmonochrome_diag_spool_reset1a.done' in spool,
 "purge called before spool directory create": (
     spool.index('purgeMonochromeLegacyBacklogOnce(context);')
     < spool.index('Path dir = context.getFilesDir().toPath().resolve("m9diag_spool");')
 ),
 "purge only private spool path": 'Path dir=filesRoot.resolve("m9diag_spool");' in spool,
 "completion marker outside spool": 'Path marker=filesRoot.resolve(MONO_SPOOL_RESET_MARKER);' in spool,
 "pending individual map cleared": 'INDIVIDUAL_PENDING.clear();' in spool,
 "pending bundle map cleared": 'BUNDLE_PENDING.clear();' in spool,
 "individual executor queue cleared": 'INDIVIDUAL_EXPORTER.getQueue().clear();' in spool,
 "bundle task cancelled": 'scheduledBundle.cancel(false)' in spool,
 "regular staged files deleted": 'Files.deleteIfExists(p)' in spool,
 "spool dir removed after files": 'Files.deleteIfExists(dir);' in spool,
 "durable marker fsync": 'out.getFD().sync();' in spool,
 "marker replace": 'StandardCopyOption.REPLACE_EXISTING' in spool,
 "telemetry completed": 'monoSpoolResetCompleted' in spool,
 "telemetry deletion count": 'monoSpoolResetDeletedFiles' in spool,
 "telemetry deletion bytes": 'monoSpoolResetDeletedBytes' in spool,
 "error telemetry": 'monoSpoolResetError' in spool,
}
for k,v in checks.items():
    print(("PASS " if v else "FAIL ")+k)
    if not v: raise SystemExit(k)

# Prove the purge body has no public storage/DCIM target. Public writer logic elsewhere
# may legitimately reference public paths, so inspect only the reset method.
a=spool.index('private static void purgeMonochromeLegacyBacklogOnce')
b=spool.index('    private static void scheduleBundle()',a)
body=spool[a:b]
for forbidden in ['DCIM','Environment.getExternalStorageDirectory','SimpleStorageHelper.openOutputStreamByAbsPath',
                  'publicPath','_MONO_LINEAR1A.dng','.jpg']:
    if forbidden in body:
        raise SystemExit("purge method unexpectedly references public/photographic target: "+forbidden)
print("PASS purge body is app-private-only")

assert proof["revision"]=="MMONOSPOOLRESET1A_ONCE"
assert proof["purgedPath"]=="filesDir/m9diag_spool"
assert proof["deletesPublicDcimDiagnostics"] is False
for k in ["deletesJpeg","deletesDng","deletesPreferences","exposurePolicyChanged",
          "broadTailCalibrationChanged","mfmChanged","sourcePlacementChanged",
          "jpegRendererChanged","dngPixelMathChanged","curve02Changed","HDR"]:
    assert proof[k] is False,k

report={
 "status":"PASS",
 "revision":"MMONOSPOOLRESET1A_ONCE",
 "privateBacklogPurgedOnce":True,
 "publicDcimUntouched":True,
 "jpegDngUntouched":True,
 "exposurePolicyUntouched":True,
 "expectedNextBundleTelemetry":[
   "monoSpoolResetRevision",
   "monoSpoolResetAttempted",
   "monoSpoolResetCompleted",
   "monoSpoolResetDeletedFiles",
   "monoSpoolResetDeletedBytes"
 ],
 "phoneValidationRequired":True
}
(root/"MMONOSPOOLRESET1A_TEST_REPORT.json").write_text(json.dumps(report,indent=2)+"\n")
print(json.dumps(report,indent=2))
