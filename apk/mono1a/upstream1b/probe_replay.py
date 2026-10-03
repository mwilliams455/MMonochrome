#!/usr/bin/env python3
from pathlib import Path
import os, subprocess, sys

if len(sys.argv) != 3:
    raise SystemExit("usage: probe_replay.py <MMonochrome-root> <PhotonCamera-root>")
repo=Path(sys.argv[1]).resolve()
photon=Path(sys.argv[2]).resolve()
if not photon.is_dir():
    raise SystemExit("modern Photon source missing: "+str(photon))

# Existing Monochrom workflows uniformly address this path. The caller prepares
# the modern M9/Photon source there before this script runs.
expected=repo/"m9base"/"PhotonCamera"
if photon != expected:
    raise SystemExit(f"expected Photon root {expected}, got {photon}")

wf=repo/".github/workflows/build-mono1a-monoauto1d1g.yml"
lines=wf.read_text().splitlines()
stop=lines.index("      - name: Set up Android SDK")
i=0
count=0
while i<stop:
    if lines[i].strip()!="run: |":
        i+=1
        continue
    i+=1
    block=[]
    while i<stop and not lines[i].startswith("      - name: "):
        line=lines[i]
        if line.startswith("          "):
            block.append(line[10:])
        elif not line.strip():
            block.append("")
        else:
            raise SystemExit("Unexpected parent boundary "+line)
        i+=1
    count+=1
    p=Path(f"/tmp/mono-modern-parent-{count}.sh")
    p.write_text("\n".join(block)+"\n")
    env=os.environ.copy()
    env["GITHUB_WORKSPACE"]=str(repo)
    subprocess.run(["bash",str(p)],cwd=repo,env=env,check=True)
print("MONO_MODERN_PARENT_RUN_BLOCKS",count)
