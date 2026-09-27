#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, re, sys

if len(sys.argv)!=2:
    raise SystemExit("usage: apply.py <PhotonCamera-root>")

root=Path(sys.argv[1]).resolve()
J=root/"app/src/main/java/com/particlesdevs/photoncamera"
spool=J/"m9/M9DiagnosticBurstSpool.java"
gradle=root/"app/build.gradle"
if not spool.exists() or not gradle.exists():
    raise SystemExit("MMONOSPOOLRESET1A missing assembled parent files")

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def one(s,a,b,name):
    if s.count(a)!=1:
        raise SystemExit(f"{name} anchor mismatch count={s.count(a)}")
    return s.replace(a,b,1)

src=spool.read_text()
for marker in [
    'public final class M9DiagnosticBurstSpool',
    'm9cam.sidecarspool.v1.privatebundle1b',
    'INDIVIDUAL_PENDING',
    'BUNDLE_PENDING',
    'public static boolean stage(',
    'public static JSONObject snapshotJson()'
]:
    if marker not in src:
        raise SystemExit("MMONOSPOOLRESET1A parent marker missing: "+marker)
if "MMONOSPOOLRESET1A_ONCE" in src:
    raise SystemExit("MMONOSPOOLRESET1A already applied")

# This is storage/backlog hygiene only. Freeze every photographic/exposure component.
frozen=[
    J/"m9/render/M9R35Renderer.java",
    J/"m9/export/MonoDngExport1A.java",
    J/"m9/export/MonoDngWriter1A.java",
    J/"m9/export/MonoLinearPlane1A.java",
    J/"m9/export/MonoPlacementProbe1A.java",
    J/"m9/exposure/MonoPlacementAssist1D.java",
    J/"m9/exposure/MonoExposureStore1A.java",
    J/"m9/exposure/MonoExposurePlan1A.java",
    J/"m9/M9M10rMfmTest1A.java",
    J/"processing/parameters/IsoExpoSelector.java",
    root/"app/src/main/cpp/m9color_jni.cpp",
    root/"app/src/main/assets/mono/mono_curve02_gl2a.bin",
    root/"app/src/main/assets/shaders/preview/main_fs.glsl",
]
before={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}

# Add Monochrome-specific one-time reset state. App package/filesDir is already
# separate from the M9 app, but use a distinct marker for unambiguous telemetry.
src=one(src,
'''    private static final String TAG = "M9DiagSpool";
''',
'''    private static final String TAG = "M9DiagSpool";
    private static final String MONO_SPOOL_RESET_REVISION = "MMONOSPOOLRESET1A_ONCE";
    private static final String MONO_SPOOL_RESET_MARKER = "mmonochrome_diag_spool_reset1a.done";
    private static final Object MONO_SPOOL_RESET_LOCK = new Object();
    private static final java.util.concurrent.atomic.AtomicBoolean MONO_SPOOL_RESET_ATTEMPTED =
            new java.util.concurrent.atomic.AtomicBoolean();
    private static final java.util.concurrent.atomic.AtomicBoolean MONO_SPOOL_RESET_COMPLETED =
            new java.util.concurrent.atomic.AtomicBoolean();
    private static final java.util.concurrent.atomic.AtomicLong MONO_SPOOL_RESET_DELETED_FILES =
            new java.util.concurrent.atomic.AtomicLong();
    private static final java.util.concurrent.atomic.AtomicLong MONO_SPOOL_RESET_DELETED_BYTES =
            new java.util.concurrent.atomic.AtomicLong();
    private static volatile String monoSpoolResetError = null;
''',"reset fields")

# Run before creating/staging the first new diagnostic file. The synchronized helper
# prevents concurrent renderer/audit stage calls from racing the first purge.
src=one(src,
'''            Context context = PhotonCamera.getAppContext();
            if (context == null) throw new IllegalStateException("PhotonCamera app context unavailable");
            Path dir = context.getFilesDir().toPath().resolve("m9diag_spool");
''',
'''            Context context = PhotonCamera.getAppContext();
            if (context == null) throw new IllegalStateException("PhotonCamera app context unavailable");
            purgeMonochromeLegacyBacklogOnce(context);
            Path dir = context.getFilesDir().toPath().resolve("m9diag_spool");
''',"stage purge boundary")

purge=r'''
    /**
     * MMONOSPOOLRESET1A.
     *
     * One-time purge of only the app-private diagnostic staging backlog inherited
     * from older Monochrome builds. It intentionally does NOT touch DCIM, JPEG,
     * DNG, public JSON sidecars, preferences, exposure state or photographic data.
     *
     * The completion marker is outside m9diag_spool so the purge is not repeated
     * after it succeeds. A failed purge leaves no marker and can retry next process.
     */
    private static void purgeMonochromeLegacyBacklogOnce(Context context) {
        synchronized (MONO_SPOOL_RESET_LOCK) {
            if (context == null) return;
            Path filesRoot=context.getFilesDir().toPath();
            Path marker=filesRoot.resolve(MONO_SPOOL_RESET_MARKER);
            if (Files.isRegularFile(marker)) {
                MONO_SPOOL_RESET_ATTEMPTED.set(true);
                MONO_SPOOL_RESET_COMPLETED.set(true);
                return;
            }
            if (MONO_SPOOL_RESET_ATTEMPTED.get()) return;
            MONO_SPOOL_RESET_ATTEMPTED.set(true);

            long deletedFiles=0L,deletedBytes=0L;
            try {
                synchronized (BUNDLE_LOCK) {
                    if (scheduledBundle != null) {
                        scheduledBundle.cancel(false);
                        scheduledBundle=null;
                    }
                }
                BUNDLE_EXECUTOR.getQueue().clear();
                INDIVIDUAL_EXPORTER.getQueue().clear();
                INDIVIDUAL_PENDING.clear();
                BUNDLE_PENDING.clear();

                Path dir=filesRoot.resolve("m9diag_spool");
                if (Files.isDirectory(dir)) {
                    try (java.nio.file.DirectoryStream<Path> entries=Files.newDirectoryStream(dir)) {
                        for (Path p:entries) {
                            if (!Files.isRegularFile(p)) continue;
                            try { deletedBytes+=Files.size(p); } catch (Throwable ignored) {}
                            if (Files.deleteIfExists(p)) deletedFiles++;
                        }
                    }
                    Files.deleteIfExists(dir);
                }

                MONO_SPOOL_RESET_DELETED_FILES.set(deletedFiles);
                MONO_SPOOL_RESET_DELETED_BYTES.set(deletedBytes);

                java.util.Properties receipt=new java.util.Properties();
                receipt.setProperty("revision",MONO_SPOOL_RESET_REVISION);
                receipt.setProperty("deletedFiles",Long.toString(deletedFiles));
                receipt.setProperty("deletedBytes",Long.toString(deletedBytes));
                receipt.setProperty("completedEpochMs",Long.toString(System.currentTimeMillis()));
                Path tmp=marker.resolveSibling(marker.getFileName()+".tmp");
                try (java.io.FileOutputStream out=new java.io.FileOutputStream(tmp.toFile())) {
                    receipt.store(out,MONO_SPOOL_RESET_REVISION);
                    out.getFD().sync();
                }
                Files.move(tmp,marker,java.nio.file.StandardCopyOption.REPLACE_EXISTING);
                MONO_SPOOL_RESET_COMPLETED.set(true);
                Log.d(TAG,MONO_SPOOL_RESET_REVISION+" cleared private backlog files="
                        +deletedFiles+"; bytes="+deletedBytes);
            } catch (Throwable error) {
                monoSpoolResetError=error.toString();
                MONO_SPOOL_RESET_COMPLETED.set(false);
                Log.e(TAG,MONO_SPOOL_RESET_REVISION+" private backlog purge failed",error);
            }
        }
    }

'''
src=one(src,
'''    private static void scheduleBundle() {
''',
purge+'''    private static void scheduleBundle() {
''',"purge method")

# Expose proof in the very next burst telemetry.
src=one(src,
'''            o.put("schema", SCHEMA);
''',
'''            o.put("schema", SCHEMA);
            o.put("monoSpoolResetRevision", MONO_SPOOL_RESET_REVISION);
            o.put("monoSpoolResetAttempted", MONO_SPOOL_RESET_ATTEMPTED.get());
            o.put("monoSpoolResetCompleted", MONO_SPOOL_RESET_COMPLETED.get());
            o.put("monoSpoolResetDeletedFiles", MONO_SPOOL_RESET_DELETED_FILES.get());
            o.put("monoSpoolResetDeletedBytes", MONO_SPOOL_RESET_DELETED_BYTES.get());
            o.put("monoSpoolResetMarker", MONO_SPOOL_RESET_MARKER);
            if (monoSpoolResetError != null) o.put("monoSpoolResetError", monoSpoolResetError);
''',"reset telemetry")

spool.write_text(src)

g=gradle.read_text()
m=re.search(r"versionName\s+'([^']+)'",g)
if not m: raise SystemExit("versionName missing")
v=m.group(1)
if "mmonospoolreset1a" not in v:
    g=g[:m.start(1)]+v+"-mmonospoolreset1a"+g[m.end(1):]
    gradle.write_text(g)

after={str(p.relative_to(root)):sha(p) for p in frozen if p.exists()}
if before!=after:
    changed=[k for k in before if before[k]!=after.get(k)]
    raise SystemExit("MMONOSPOOLRESET1A changed frozen photographic/exposure files: "+repr(changed))

proof={
 "revision":"MMONOSPOOLRESET1A_ONCE",
 "parent":"MONOAUTO1D_PLACEMENTASSIST1E_BUFFERHYGIENE1A",
 "purpose":"one_time_private_diagnostic_backlog_purge",
 "purgedPath":"filesDir/m9diag_spool",
 "marker":"filesDir/mmonochrome_diag_spool_reset1a.done",
 "runs":"first_diagnostic_stage_after_install_if_marker_absent",
 "deletesPublicDcimDiagnostics":False,
 "deletesJpeg":False,
 "deletesDng":False,
 "deletesPreferences":False,
 "exposurePolicyChanged":False,
 "broadTailCalibrationChanged":False,
 "mfmChanged":False,
 "sourcePlacementChanged":False,
 "jpegRendererChanged":False,
 "dngPixelMathChanged":False,
 "curve02Changed":False,
 "HDR":False,
 "frozen":after
}
(root/"MMONOSPOOLRESET1A_ISOLATION.json").write_text(json.dumps(proof,indent=2)+"\n")
print(json.dumps(proof,indent=2))
