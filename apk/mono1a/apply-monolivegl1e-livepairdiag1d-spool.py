#!/usr/bin/env python3
"""Apply only diagnostic transport/association changes on the assembled GL1E1C baseline."""
from pathlib import Path
import hashlib
import re
import sys

if len(sys.argv) != 2:
    raise SystemExit('usage: apply-monolivegl1e-livepairdiag1d-spool.py <PhotonCamera-root>')
root = Path(sys.argv[1]).resolve()
java = root / 'app/src/main/java/com/particlesdevs/photoncamera'
diag = java / 'm9/preview/MonoLivePairDiagnostics1E.java'
controller = java / 'capture/CaptureController.java'
store = java / 'm9/M9DeferredMetadataStore.java'
helper = java / 'm9/preview/MonoLivePairExport1D.java'
source = Path(__file__).with_name('MonoLivePairExport1D.java')
if helper.exists():
    raise SystemExit('GL1E1D already applied')
for p in [diag, controller, store, source]:
    if not p.is_file():
        raise SystemExit('missing prerequisite: ' + str(p))
frozen = [java/'m9/render/M9R35Renderer.java', root/'app/src/main/cpp/m9color_jni.cpp',
          java/'processing/parameters/IsoExpoSelector.java', java/'processing/SaverImplementation.java',
          java/'ui/camera/CameraFragment.java', java/'ui/camera/views/viewfinder/MainRenderer.java',
          java/'ui/camera/views/viewfinder/GLPreview.java', root/'app/src/main/assets/shaders/preview/main_fs.glsl']
before = {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in frozen}
d = diag.read_text(); c = controller.read_text(); m = store.read_text()
if 'MONOLIVEGL1E_LIVEPAIRDIAG1C_ZSL' not in c:
    raise SystemExit('GL1E1C controller required')
start = d.index('            String pairId = root.optString("pairId", "unknown");')
end = d.index('        } catch (Throwable t) {', start)
d = d[:start] + '''            // MONOLIVEGL1E_LIVEPAIRDIAG1D_SPOOL: memory only at callback.
            MonoLivePairExport1D.remember(root);
''' + d[end:]
old = '            Log.e(TAG, BUILD + " write failed: " + t);'
assert d.count(old) == 1
d = d.replace(old, '            MonoLivePairExport1D.noteFailure(t);\n' + old, 1)
d = d.replace('public static final String BUILD = "MONOLIVEGL1E_LIVEPAIRDIAG1A";',
              'public static final String BUILD = "MONOLIVEGL1E_LIVEPAIRDIAG1D_SPOOL";')
# Remove imports for the retired direct public-file writer.
for imp in ['import android.os.Environment;', 'import java.io.File;',
            'import java.io.FileOutputStream;', 'import java.nio.charset.StandardCharsets;',
            'import java.nio.file.Files;', 'import java.nio.file.Path;', 'import java.nio.file.Paths;',
            'import com.particlesdevs.photoncamera.util.FileManager;']:
    d = d.replace(imp+'\n', '')
# No process-executor race: writeCompleted now caches small immutable JSON only.
pat = re.compile(r'processExecutor\.execute\(\(\) -> MonoLivePairDiagnostics1E\.writeCompleted\((.*?)\)\);', re.S)
c, count = pat.subn(r'MonoLivePairDiagnostics1E.writeCompleted(\1);', c)
c = c.replace('one asynchronous sidecar per shutter.', 'one bounded in-memory pair per shutter; export is deferred.')
c = c.replace('// exact preview request/result that supplied the buffered RAW frames.',
              '// latest preview request/result; exact RAW timestamp matching is checked at export.')
if count != 2:
    raise SystemExit('expected Photo+ZSL diagnostic callbacks, found ' + str(count))
# Export at the universal capture metadata boundary. No image/RAW ownership changes.
old = '        if (M9DiagnosticBurstSpool.stage(jsonPath, bytes, "capture_metadata")) {'
new = '''        // MONOLIVEGL1E_LIVEPAIRDIAG1D_SPOOL: exact RAW identity, inline fallback.
        final byte[] monoCaptureBytes1D =
                com.particlesdevs.photoncamera.m9.preview.MonoLivePairExport1D.attachAndStage(jsonPath, bytes);
        if (M9DiagnosticBurstSpool.stage(jsonPath, monoCaptureBytes1D, "capture_metadata")) {'''
if m.count(old) != 1:
    raise SystemExit('capture-metadata spool boundary not unique')
m = m.replace(old, new, 1)
# Keep the enriched bytes if the existing private-spool fallback is needed.
fallback = 'M9DiagnosticSidecarIO.persist(jsonPath, bytes,'
if m.count(fallback) != 1:
    raise SystemExit('capture-metadata fallback boundary not unique')
m = m.replace(fallback, 'M9DiagnosticSidecarIO.persist(jsonPath, monoCaptureBytes1D,', 1)
retry = '            STAGED.put(key, bytes);'
if m.count(retry) != 1:
    raise SystemExit('capture-metadata retry boundary not unique')
m = m.replace(retry, '            STAGED.put(key, monoCaptureBytes1D);', 1)
assert 'Files.write(out, bytes)' not in d
assert 'MonoLivePairExport1D.remember(root)' in d
assert 'validExposurePair' in source.read_text()
# All prerequisites checked before modifying the assembled tree.
diag.write_text(d); controller.write_text(c); store.write_text(m)
helper.write_text(source.read_text())
for rel, digest in before.items():
    if hashlib.sha256((root/rel).read_bytes()).hexdigest() != digest:
        raise SystemExit('photographic contract changed: '+rel)
# Persistent proof, not a string-valued pseudo-assertion.
(root/'MONOLIVEGL1E1D_ISOLATION.json').write_text(__import__('json').dumps(before, indent=2)+'\n')
print('MONOLIVEGL1E_LIVEPAIRDIAG1D_SPOOL PASS')
print('Photo+ZSL callback memory cache; common capture JSON export; exact timestamp or unavailable')
print('Dedicated _MONO_LIVEPAIR.json + complete monoLivePair in existing _M9.json/burst')
print('Eight photographic/preview/allocator files unchanged by SHA256')
