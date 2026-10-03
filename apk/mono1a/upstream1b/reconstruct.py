#!/usr/bin/env python3
from pathlib import Path
import hashlib, json, shutil, subprocess, sys

if len(sys.argv) != 4:
    raise SystemExit("usage: reconstruct.py <legacy-monochrom-root> <modern-photon-root> <m9-modern-root>")

here = Path(__file__).resolve().parent
legacy = Path(sys.argv[1]).resolve()
modern = Path(sys.argv[2]).resolve()
m9modern = Path(sys.argv[3]).resolve()

for p in (legacy, modern, m9modern):
    if not p.is_dir():
        raise SystemExit("missing source root: " + str(p))

expected = json.loads((here / "expected_hashes.json").read_text())
frozen = json.loads((here / "frozen_monochrome.json").read_text())
if expected.get("photonCommit") != "4ee108e169496f429c0afa0cc33e57bb6b2ec724":
    raise SystemExit("unexpected Photon pin")

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

# Apply only the reviewed modern-Photon integration delta.
parts = sorted(here.glob("modern-integration.patch.part*"))
if len(parts) != 4:
    raise SystemExit("expected 4 modern integration patch parts")
patch_text = "\n".join(p.read_text().rstrip("\n") for p in parts) + "\n"
subprocess.run(
    ["git", "-C", str(modern), "apply", "--whitespace=nowarn", "-"],
    input=patch_text.encode(),
    check=True,
)

# Copy the exact frozen Monochrom photographic/exposure/DNG seam from the
# validated MONOTAPMETER1B parent. These files stay Monochrom-specific.
for rel, digest in frozen.items():
    src = legacy / rel
    dst = modern / rel
    if not src.is_file():
        raise SystemExit("legacy Monochrom file missing: " + rel)
    if sha(src) != digest:
        raise SystemExit("legacy Monochrom hash mismatch: " + rel)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

# The modern Photon native build uses four pinned headers. Reuse the exact
# published M9 UPSTREAM2R reconstruction copies; hashes are checked below.
for rel in [
    "app/src/main/cpp/deps/archive.h",
    "app/src/main/cpp/deps/archive_entry.h",
    "app/src/main/cpp/deps/technicallyflac.h",
    "app/src/main/cpp/deps/tiny_dng_writer.h",
]:
    src = m9modern / rel
    dst = modern / rel
    if not src.is_file():
        raise SystemExit("M9 modern dependency header missing: " + rel)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

# M9PrimaryRenderQueue is frozen from the current Monochrom parent except for
# the four UPSTREAM1A diagnostic fields validated on the phone on 30 Sep 2026.
queue_rel = "app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9PrimaryRenderQueue.java"
queue_src = legacy / queue_rel
queue_dst = modern / queue_rel
q = queue_src.read_text()
old = '''                if (renderResult != null && renderResult.diagnostics != null) {
                    rendererDiagnosticsJson = renderResult.diagnostics.toString();
                }
'''
new = '''                if (renderResult != null && renderResult.diagnostics != null) {
                    renderResult.diagnostics.put("monoPhotonUpstream", "MONOUPSTREAM1A_RAW16");
                    renderResult.diagnostics.put("photonUpstreamCommit", "4ee108e169496f429c0afa0cc33e57bb6b2ec724");
                    renderResult.diagnostics.put("rawBufferPackedBits", ownedFrame.packedBits);
                    renderResult.diagnostics.put("rawBufferCapacityBytes", ownedFrame.buffer.capacity());
                    rendererDiagnosticsJson = renderResult.diagnostics.toString();
                }
'''
if q.count(old) != 1:
    raise SystemExit("modern queue diagnostic anchor mismatch")
q = q.replace(old, new, 1)
queue_dst.parent.mkdir(parents=True, exist_ok=True)
queue_dst.write_text(q)

# Restore the two original modern-merge regression tests.
for name, rel in [
    ("MonoUpstream1AZoomTest.java", "app/src/test/java/com/particlesdevs/photoncamera/capture/MonoUpstream1AZoomTest.java"),
    ("MonoUpstream1ARawPackingTest.java", "app/src/test/java/com/particlesdevs/photoncamera/processing/MonoUpstream1ARawPackingTest.java"),
]:
    src = here / name
    dst = modern / rel
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)

# Verify every file changed or supplied by the original September UPSTREAM1A
# reconstruction. Everything else remains pinned Photon 4ee108e.
bad = []
for rel, digest in expected["files"].items():
    p = modern / rel
    if not p.is_file():
        bad.append((rel, "missing", digest))
        continue
    actual = sha(p)
    if actual != digest:
        bad.append((rel, actual, digest))
if bad:
    for row in bad[:20]:
        print("MISMATCH", *row)
    raise SystemExit("UPSTREAM1A reconstruction mismatch count=" + str(len(bad)))

receipt = {
    "revision": "MONOUPSTREAM1B_MODERNUI_RESTORE",
    "photonCommit": expected["photonCommit"],
    "verifiedChangedFiles": len(expected["files"]),
    "frozenMonochromFiles": len(frozen),
    "modernPhotonUi": True,
    "photographicSeamChanged": False,
}
(modern / "MONOUPSTREAM1B_RECONSTRUCTION.json").write_text(json.dumps(receipt, indent=2) + "\n")
print(json.dumps(receipt, indent=2))
