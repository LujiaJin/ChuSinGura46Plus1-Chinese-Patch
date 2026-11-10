# -*- coding: utf-8 -*-
"""Build the complete Chinese patch.xp3 from zh_out + reused system files.
Output goes to the pipeline directory only (validated, flat names)."""
import sys, os
from pathlib import Path

PIPE = Path(__file__).resolve().parent
OUTDIR = PIPE / "zh_out"
sys.path.insert(0, str(PIPE))
import xp3lib

# whitelist: flat NAME.EXT, ASCII letters/digits/dash/underscore/dot only
import re
SAFE = re.compile(r"[A-Za-z0-9_\-]+\.(?:KS|ks|tjs|TJS|png|PNG)\Z", re.I)

def main():
    files = []
    for f in sorted(OUTDIR.iterdir()):
        if not SAFE.match(f.name):
            raise ValueError("unexpected file in zh_out: " + repr(f.name))
        name = f.name
        if name.upper().endswith(".KS") and not name.endswith(".ks"):
            name = name[:-2] + "KS"  # normalize case variants like Y-032.kS -> Y-032.KS
        files.append((name, f.read_bytes()))
    # guard against duplicates after normalization
    seen = {}
    for name, data in files:
        if name in seen:
            raise ValueError("duplicate entry after normalize: " + name)
        seen[name] = data
    # reuse translated system macro from previous full build
    prev = xp3lib.read_xp3(str(PIPE / "patch_v2_full.xp3"))
    if "SH_MACRO.KS" in prev and "SH_MACRO.KS" not in dict(files):
        files.append(("SH_MACRO.KS", prev["SH_MACRO.KS"]))
    print(len(files), "files")
    data = xp3lib.build_xp3(files)
    out = PIPE / "patch_cn_full.xp3"
    out.write_bytes(data)
    print("wrote", out.name, len(data), "bytes")
    # verify round-trip
    back = xp3lib.read_xp3(str(out))
    assert len(back) == len(files)
    for name, plain in files:
        assert back[name] == plain, name
    print("round-trip OK")

if __name__ == "__main__":
    main()
