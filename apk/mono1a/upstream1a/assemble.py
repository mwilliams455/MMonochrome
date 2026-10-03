#!/usr/bin/env python3
from pathlib import Path
import gzip,hashlib,subprocess,sys
PIN="4ee108e169496f429c0afa0cc33e57bb6b2ec724"
SHA="3ff77b1dab533cf53f4bafc17967238b94c6dfa4bf1d5d87a04e7c088722ea09"
here=Path(__file__).resolve().parent
root=Path(sys.argv[1]).resolve()
blob=(here/"monochrome-overlay.patch.gz").read_bytes()
assert hashlib.sha256(blob).hexdigest()==SHA
assert not root.exists()
subprocess.run(["git","clone","--no-checkout","--depth","1","--branch","dev","https://github.com/eszdman/PhotonCamera.git",str(root)],check=True)
subprocess.run(["git","-C",str(root),"fetch","--depth","1","origin",PIN],check=True)
subprocess.run(["git","-C",str(root),"checkout","--detach",PIN],check=True)
subprocess.run(["git","-C",str(root),"apply","--binary","--whitespace=nowarn","-"],input=gzip.decompress(blob),check=True)
print("MONOUPSTREAM1A restored on Photon",PIN)
