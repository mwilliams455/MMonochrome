#!/usr/bin/env python3
from pathlib import Path
import hashlib, sys

if len(sys.argv)!=2:
    raise SystemExit("usage: patch_queue_marker.py <PhotonCamera-root>")
root=Path(sys.argv[1]).resolve()
p=root/"app/src/main/java/com/particlesdevs/photoncamera/m9/render/M9PrimaryRenderQueue.java"
s=p.read_text()
needle="                    rendererDiagnosticsJson = renderResult.diagnostics.toString();"
if "monoPhotonUpstream" not in s:
    insert=(
        '                    renderResult.diagnostics.put("monoPhotonUpstream", "MONOUPSTREAM1A_RAW16");\n'
        '                    renderResult.diagnostics.put("photonUpstreamCommit", "4ee108e169496f429c0afa0cc33e57bb6b2ec724");\n'
        '                    renderResult.diagnostics.put("rawBufferPackedBits", ownedFrame.packedBits);\n'
        '                    renderResult.diagnostics.put("rawBufferCapacityBytes", ownedFrame.buffer.capacity());\n'
    )
    if s.count(needle)!=1:
        raise SystemExit("queue marker anchor mismatch")
    p.write_text(s.replace(needle,insert+needle,1))
digest=hashlib.sha256(p.read_bytes()).hexdigest()
expected="697a6113f2a929a09ee3796c0d64d26e10d53a270c510939ab67fbb81ff9bb2d"
if digest!=expected:
    raise SystemExit("queue target SHA mismatch "+digest)
print("queue marker restored",digest)
