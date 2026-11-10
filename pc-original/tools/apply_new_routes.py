# -*- coding: utf-8 -*-
"""Apply trans_full.json to douga*/omake/Y-032 using apply_tm2's exact patterns.
Outputs UTF-16LE+BOM files into zh_out/."""
import sys, json, re, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import xp3lib

PIPE = Path(os.path.dirname(os.path.abspath(__file__)))
OUTDIR = PIPE / "zh_out"
GAME = "D:/Games/Chusingura46+1/GameInstalled/app/app"

tr = json.load((PIPE / "trans_full.json").open(encoding="utf-8"))
gloss = json.load((PIPE / "name_glossary.json").open(encoding="utf-8"))

NAME_OK = re.compile(r"(?:douga\d*|omake|Y-032)\.k[sS]\Z", re.I)
RUBY = re.compile(r"\[ruby[^\]]*\]")

def out_path_for(name):
    # normalize Y-032.kS -> Y-032.KS style (match scenario entry exactness)
    if not NAME_OK.match(name):
        raise ValueError("unsafe entry: " + repr(name))
    if ".." in name or "/" in name or "\\" in name:
        raise ValueError("sep in name")
    p = OUTDIR / name
    if p.parent != OUTDIR:
        raise ValueError("escape")
    return p

def main():
    scen = xp3lib.read_xp3(GAME + "/scenario.xp3")
    names = sorted(n for n in scen if NAME_OK.match(n))
    print(len(names), "files")
    stats = {}
    for n in names:
        raw = scen[n]
        enc = "utf-16-le" if raw[:2] == b"\xff\xfe" else "cp932"
        txt = raw.decode(enc, errors="replace").lstrip("﻿")
        out_lines = []
        st = {"hit": 0, "miss": 0}
        for line in txt.split("\r\n"):
            core = line.rstrip("\\").rstrip()
            m = re.match(r"^(\[[^\]]*\]?)「(.*)」(\[p\].*)$", core)
            if m and m.group(2):
                key = RUBY.sub("", m.group(2))
                zh = tr.get(key)
                if zh is not None:
                    out_lines.append(m.group(1) + "「" + zh + "」" + m.group(3))
                    st["hit"] += 1
                else:
                    st["miss"] += 1
                    out_lines.append(line)
                continue
            if core.endswith("[p]") and not core.startswith(("[", "@", "*")):
                key = RUBY.sub("", core[:-3])
                zh = tr.get(key)
                if zh is not None:
                    suffix = "\\" if line.rstrip().endswith("\\") else ""
                    out_lines.append(zh + "[p]" + suffix)
                    st["hit"] += 1
                else:
                    st["miss"] += 1
                    out_lines.append(line)
                continue
            m = re.match(r"^(\*[^|]*\|)(.*)$", core)
            if m:
                key = RUBY.sub("", m.group(2))
                zh = tr.get(key)
                if zh is not None:
                    out_lines.append(m.group(1) + zh)
                    st["hit"] += 1
                else:
                    st["miss"] += 1
                    out_lines.append(line)
                continue
            def sub_name(mo):
                inner = RUBY.sub("", mo.group(2))
                zh = tr.get(inner) or gloss.get(inner)
                return mo.group(1) + (zh if zh else mo.group(2)) + mo.group(3)
            line2 = re.sub(r'(\[sonota name=")([^"]+)(".*\))', sub_name, line)
            if line2 != line:
                st["hit"] += 1
            out_lines.append(line2)
        p = out_path_for(n)
        p.write_bytes(b"\xff\xfe" + "\r\n".join(out_lines).encode("utf-16-le"))
        stats[n] = st
        print(n, st)
    tot_hit = sum(s['hit'] for s in stats.values())
    tot_miss = sum(s['miss'] for s in stats.values())
    print(f"TOTAL hit={tot_hit} miss={tot_miss}")

main()
