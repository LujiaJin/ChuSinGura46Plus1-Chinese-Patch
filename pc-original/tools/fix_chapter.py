# -*- coding: utf-8 -*-
"""Chapter-select page localization v2.
Pages: k2(1 unlocked) y2(2) c2(3) e2(4) g2(4, no 5th strip) a2(5).
Template text masks from all-lit a2; per-slot strip detection:
- no strip (std<25, mean<60) -> skip
- lit (mean>120) -> CN black brush + white halo
- locked -> CN dim black, no halo
Erase: row-median fill of dilated template mask (numpy -> Image.fromarray!).
chapter_bar.png caption -> CN.
"""
import sys, io, os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PIPE = Path(os.path.dirname(os.path.abspath(__file__)))
OUT = PIPE / "zh_out"
sys.path.insert(0, str(PIPE))
import xp3lib

BG = xp3lib.read_xp3("D:/Games/Chusingura46+1/GameInstalled/app/app/bgimage.xp3")
PAGES = ["chapter_base_k2.jpg", "chapter_base_y2.jpg", "chapter_base_c2.jpg",
         "chapter_base_e2.jpg", "chapter_base_g2.jpg", "chapter_base_a2.jpg"]
SLOT_Y = [178, 263, 348, 433, 518]
CN = ["假名手本忠臣藏篇", "江户急进派篇", "百花魁篇", "仇华·宿怨篇", "刃·忠勇义烈篇"]
ZONE = (95, 485)
BRUSH = "C:/Windows/Fonts/STXINGKA.TTF"

def dilate(m, it=2):
    for _ in range(it):
        p = np.pad(m, 1)
        m = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m

# ---- template masks from a2 (all 5 lit) ----
a2 = np.array(Image.open(io.BytesIO(BG["chapter_base_a2.jpg"])).convert("RGB")).astype(int)
masks = []
for sy in SLOT_Y:
    y0, y1 = sy + 2, sy + 63
    z = a2[y0:y1, ZONE[0]:ZONE[1]]
    lum = z.sum(axis=2) / 3
    med = np.median(lum)
    m = lum < med - 60          # black text on silver
    if m.sum() < 200:
        m = lum < med - 40
    masks.append(dilate(m, 2))
    print(f"tpl y{sy}: med {med:.0f} mask {int(m.sum())}px")

report = []
for page in PAGES:
    src = np.array(Image.open(io.BytesIO(BG[page])).convert("RGB"))
    a = src.astype(int).copy()
    draw_ops = []               # (cn, lit, cx, cy)
    for i, sy in enumerate(SLOT_Y):
        y0, y1 = sy + 2, sy + 63
        x0, x1 = ZONE
        z = a[y0:y1, x0:x1]
        lum = z.sum(axis=2) / 3
        std = float(lum.std())
        mean = float(lum.mean())
        if std < 25 and mean < 60:
            report.append(f"{page} slot{i+1}: no strip (std {std:.0f} mean {mean:.0f}) skip")
            continue
        lit = mean > 120
        m = masks[i]
        # stronger fill mask: dilated text + antialias fringes (lum < med-25 inside zone)
        med_zone = np.median(lum)
        fringe = lum < med_zone - 25
        fill = m | (fringe & dilate(m, 6))
        for r in range(z.shape[0]):
            row = z[r]
            rm = fill[r]
            if rm.any():
                bgrow = row[~rm]
                med = np.median(bgrow, axis=0) if len(bgrow) > 5 else np.median(row, axis=0)
                row[rm] = med
        draw_ops.append((CN[i], lit, (x0 + x1) // 2, (y0 + y1) // 2 + 3))
    img = Image.fromarray(a.astype(np.uint8))
    d = ImageDraw.Draw(img)
    for cn, lit, cx, cy in draw_ops:
        maxw = ZONE[1] - ZONE[0] - 24
        f = bb = None
        for size in range(38, 24, -1):
            f = ImageFont.truetype(BRUSH, size)
            bb = d.textbbox((0, 0), cn, font=f)
            if bb[2] - bb[0] <= maxw and bb[3] - bb[1] <= 40:
                break
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        ox, oy = cx - tw // 2 - bb[0], cy - th // 2 - bb[1]
        if lit:
            for dx in (-1, 0, 1):
                for dy in (-1, 0, 1):
                    if dx or dy:
                        d.text((ox + dx, oy + dy), cn, font=f, fill=(250, 250, 250))
        d.text((ox, oy), cn, font=f, fill=(28, 24, 26))
        report.append(f"{page} '{cn}' lit={lit}")
    img.save(OUT / page, quality=92)

# ---- chapter_bar caption ----
bar = Image.open(io.BytesIO(BG["chapter_bar.png"])).convert("RGBA")
ba = np.array(bar).astype(int)
z = ba[28:58, 388:770]
lum = z.sum(axis=2) / 3
med = np.median(lum)
tm = lum < med - 40
ys, xs = np.nonzero(tm)
tx0, tx1 = 388 + xs.min(), 388 + xs.max()
ty0, ty1 = 28 + ys.min(), 28 + ys.max()
bd = ImageDraw.Draw(bar)
bd.rectangle([tx0 - 6, ty0 - 3, tx1 + 6, ty1 + 3], fill=(252, 252, 252, 255))
cn = "可选择开始游戏的章节"
f = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 17)
bb = bd.textbbox((0, 0), cn, font=f)
tw, th = bb[2] - bb[0], bb[3] - bb[1]
bd.text((tx0 - bb[0], (ty0 + ty1) // 2 - th // 2 - bb[1]), cn, font=f, fill=(60, 60, 60, 255))
bar.save(OUT / "chapter_bar.png", format="PNG")
report.append(f"caption bbox {tx0}-{tx1} {ty0}-{ty1} -> {cn}")

print("\n".join(report))
