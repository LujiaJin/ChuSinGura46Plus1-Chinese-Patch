# -*- coding: utf-8 -*-
"""Fix sonota speaker names in the already-output douga/omake/Y-032 files."""
import re, os
from pathlib import Path

OUT = Path(r"D:/Games/Chusingura46+1/Tools/pipeline/zh_out")
import json
gloss = json.load(open(r"D:/Games/Chusingura46+1/Tools/pipeline/name_glossary.json", encoding="utf-8"))

NAMES = {
    "アナウンサー": "播音员", "マナリン": "真奈玲", "一同": "众人", "全員": "全员",
    "刺客Ａ": "刺客A", "刺客Ｂ": "刺客B", "夕霧": "夕雾", "浪士一同": "浪士一同",
    "浮橋": "浮桥", "謎の女の子": "神秘女孩", "？？": "？？", "菜夏": "菜夏",
    "絹": "绢", "袴田": "袴田", "三村": "三村",
}

def sub(m):
    n = m.group(2)
    zh = NAMES.get(n) or gloss.get(n)
    return m.group(1) + (zh if zh else n) + m.group(3)

FILES = ["douga.KS"] + [f"douga{i:02d}.KS" for i in range(1, 15)] + ["omake.KS", "Y-032.kS"]
for fn in FILES:
    p = OUT / fn
    if not p.exists():
        continue
    raw = p.read_bytes()
    txt = raw[2:].decode("utf-16-le")
    txt2 = re.sub(r'(sonota name=")([^"]+)(")', sub, txt)
    if txt2 != txt:
        p.write_bytes(b"\xff\xfe" + txt2.encode("utf-16-le"))
        print("fixed", fn)
    else:
        print("no change", fn)
