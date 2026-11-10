# -*- coding: utf-8 -*-
"""Extract translatable segments from douga*/omake/Y-032 using apply_tm2's exact
line patterns. Produces worklist.json: [{file, idx, kind, src}]"""
import sys, re, json
sys.path.insert(0, r"D:/Games/Chusingura46+1/Tools/pipeline")
import xp3lib

scen = xp3lib.read_xp3("D:/Games/Chusingura46+1/GameInstalled/app/app/scenario.xp3")
RUBY = re.compile(r"\[ruby[^\]]*\]")
FILES = ["douga.KS"] + [f"douga{i:02d}.KS" for i in range(1, 15)] + ["omake.KS", "Y-032.kS"]

worklist = []
for fn in FILES:
    if fn not in scen:
        print("missing", fn); continue
    raw = scen[fn]
    enc = "utf-16-le" if raw[:2] == b"\xff\xfe" else "cp932"
    txt = raw.decode(enc, errors="replace").lstrip("﻿")
    for idx, line in enumerate(txt.split("\r\n")):
        core = line.rstrip("\\").rstrip()
        m = re.match(r"^(\[[^\]]*\]?)「(.*)」(\[p\].*)$", core)
        if m and m.group(2):
            worklist.append({"file": fn, "idx": idx, "kind": "dlg", "src": RUBY.sub("", m.group(2))})
            continue
        if core.endswith("[p]") and not core.startswith(("[", "@", "*")):
            worklist.append({"file": fn, "idx": idx, "kind": "narr", "src": RUBY.sub("", core[:-3])})
            continue
        m = re.match(r"^(\*[^|]*\|)(.*)$", core)
        if m:
            worklist.append({"file": fn, "idx": idx, "kind": "label", "src": RUBY.sub("", m.group(2))})
            continue
        m = re.match(r"^(\[sonota name=\")([^\"]+)(\".*)$", core)
        if m:
            worklist.append({"file": fn, "idx": idx, "kind": "name", "src": RUBY.sub("", m.group(2))})
            continue

# dedupe src -> count
from collections import Counter
c = Counter(w["src"] for w in worklist)
uniq = sorted(c.keys(), key=len)
print("total segments:", len(worklist), "unique:", len(uniq))
json.dump(worklist, open("worklist.json", "w", encoding="utf-8"), ensure_ascii=False)
json.dump(uniq, open("worklist_uniq.json", "w", encoding="utf-8"), ensure_ascii=False)
# file stats
fc = Counter(w["file"] for w in worklist)
for f, n in fc.items():
    print(f, n)
