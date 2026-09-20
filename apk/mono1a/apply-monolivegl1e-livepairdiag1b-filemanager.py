#!/usr/bin/env python3
from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: apply-monolivegl1e-livepairdiag1b-filemanager.py <PhotonCamera-root>")

root = Path(sys.argv[1]).resolve()
p = root / "app/src/main/java/com/particlesdevs/photoncamera/m9/preview/MonoLivePairDiagnostics1E.java"
if not p.exists():
    raise SystemExit("GL1E diagnostic class missing: " + str(p))
s = p.read_text()
if "MONOLIVEGL1E_LIVEPAIRDIAG1A" not in s:
    raise SystemExit("GL1E prerequisite missing")
if "MONOLIVEGL1E_LIVEPAIRDIAG1B_FILEMANAGER" in s:
    raise SystemExit("GL1E 1B already applied")

# Use the exact storage authority already used by the production Monochrom/M9
# sidecars instead of a raw Environment external-storage path.
anchor = 'import com.particlesdevs.photoncamera.app.PhotonCamera;\n'
if s.count(anchor) != 1:
    raise SystemExit("PhotonCamera import anchor mismatch")
s = s.replace(anchor, anchor + 'import com.particlesdevs.photoncamera.util.FileManager;\n', 1)

anchor = 'import java.nio.charset.StandardCharsets;\n'
if s.count(anchor) != 1:
    raise SystemExit("charset import anchor mismatch")
s = s.replace(anchor, anchor + 'import java.nio.file.Files;\nimport java.nio.file.Path;\nimport java.nio.file.Paths;\n', 1)

old = '''            File dir = new File(Environment.getExternalStorageDirectory(), "DCIM/Camera");
            if (!dir.exists() && !dir.mkdirs()) throw new IllegalStateException("cannot create " + dir);
            File out = new File(dir, "MONO_LIVEPAIR_" + pairId + "_" + sensorPart + ".json");
            byte[] bytes = root.toString(2).getBytes(StandardCharsets.UTF_8);
            try (FileOutputStream fos = new FileOutputStream(out)) {
                fos.write(bytes); fos.flush();
            }
            Log.d(TAG, BUILD + " wrote " + out.getAbsolutePath() + " bytes=" + bytes.length);
'''
new = '''            // MONOLIVEGL1E_LIVEPAIRDIAG1B_FILEMANAGER
            // Use Photon's proven DCIM/Camera authority, identical to existing
            // Monochrom/M9 JSON sidecars that already persist on current Android.
            Path out = Paths.get(
                    FileManager.sDCIM_CAMERA.getAbsolutePath(),
                    "MONO_LIVEPAIR_" + pairId + "_" + sensorPart + ".json");
            if (out.getParent() != null) Files.createDirectories(out.getParent());
            byte[] bytes = root.toString(2).getBytes(StandardCharsets.UTF_8);
            Files.write(out, bytes);
            Log.d(TAG, BUILD + " wrote " + out.toString() + " bytes=" + bytes.length);
'''
if s.count(old) != 1:
    raise SystemExit("GL1E raw external writer anchor mismatch")
s = s.replace(old, new, 1)
p.write_text(s)

print("MONOLIVEGL1E_LIVEPAIRDIAG1B_FILEMANAGER applied")
print(" - diagnostic JSON uses FileManager.sDCIM_CAMERA")
print(" - writer uses java.nio.file.Files.write like existing sidecars")
print(" - preview visual transform unchanged")
print(" - still renderer/capture exposure policy unchanged")
