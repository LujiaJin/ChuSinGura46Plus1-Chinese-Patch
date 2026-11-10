# -*- coding: utf-8 -*-
"""voiceopt_base / opt_voice_base (identical) localization, v2 with hard geometry.
Ground truth (analyze of col1 row1): slider col x_s=112+c*241, slider row y_s=158+68r.
Nameplate: x_s+1..x_s+140, y_s-45..y_s-18. Leading icon x_s+6..x_s+16,
trailing icons x_s+114..x_s+131. JP text zone ~x_s+28..x_s+112, y_s-39..y_s-24.
Header banner subtitle: ボイスの設定を変更します (green text on white, ~x255-460, y52-75).
Legend bottom-left 2 lines: 上記の女性キャラ / 上記以外のその他キャラ.
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
SRC = "voiceopt_base.png"

COLS = [
    ["大石内藏助", "矶贝十郎左卫门", "奥田孙太夫", "高田郡兵卫", "矢头无垢", "毛利时房", "深海铛"],
    ["堀部安兵卫", "片冈源五右卫门", "清水一学", "萱野三平", "矢头绢", "阿梅", "其他男性角色"],
    ["大石主税", "早水藤左卫门", "矢头小夜", "毛利小平太", "矢头琉依", "阿琴", "其他女性角色"],
    ["矢头右卫门七", "间新六", "浅野内匠头", "桥本阿初", "浅野阿久里", "德川纲吉"],
    ["不破数卫门", "武林唯七", "奥野将监", "山田浅右卫门", "多门传八郎", "山吉新八郎"],
]
X0, DX, Y0, DY = 112, 241, 158, 68

img = Image.open(io.BytesIO(BG[SRC])).convert("RGB")
arr = np.array(img)
d = ImageDraw.Draw(img)
report = []

def fit_font(cn, maxw, maxh, start=14, floor=10):
    f = bb = None
    for size in range(start, floor - 1, -1):
        f = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", size)
        bb = d.textbbox((0, 0), cn, font=f)
        if bb[2] - bb[0] <= maxw and bb[3] - bb[1] <= maxh:
            return f, bb
    return f, bb

def darkest_quartile(pixels):
    """pixels Nx3 int: text color = mean of darkest 25% by luminance."""
    if len(pixels) < 4:
        return (0, 100, 60)
    l = pixels.sum(axis=1)
    idx = np.argsort(l)[: max(4, len(pixels) // 4)]
    return tuple(int(v) for v in np.mean(pixels[idx], axis=0))

# ---- 1. header banner subtitle ----
band = arr[54:74, 250:700].astype(int)
blum = band.sum(axis=2) / 3
bmed = np.median(blum)
tmask = np.abs(blum - bmed) > 40
if tmask.sum() > 20:
    ys, xs = np.nonzero(tmask)
    tx0, tx1 = 250 + xs.min(), 250 + xs.max()
    ty0, ty1 = 54 + ys.min(), 54 + ys.max()
    tc = darkest_quartile(band[tmask])
    bgw = tuple(int(v) for v in np.median(band[~tmask].reshape(-1, 3), axis=0))
    d.rectangle([tx0 - 4, ty0 - 3, tx1 + 5, ty1 + 3], fill=bgw)
    f, bb = fit_font("修改语音设置", 230, 22, 17)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text((tx0 - bb[0], (ty0 + ty1) // 2 - th // 2 - bb[1]), "修改语音设置", font=f, fill=tc)
    report.append(f"banner: x{tx0}-{tx1} y{ty0}-{ty1} tc={tc} bg={bgw}")
else:
    report.append("banner: NOT FOUND")

# ---- 2. 33 nameplates (fixed geometry) ----
for c, names in enumerate(COLS):
    xs = X0 + c * DX
    for r, cn in enumerate(names):
        ys = Y0 + r * DY
        # text search zone (between icons)
        zx0, zx1, zy0, zy1 = xs + 28, xs + 112, ys - 40, ys - 23
        zone = arr[zy0:zy1, zx0:zx1].astype(int)
        zlum = zone.sum(axis=2) / 3
        zmed = np.median(zlum)
        tmask = zlum < zmed - 50  # dark text on light plate
        # plate bg: brightest half of zone
        bmask = zlum > zmed
        if bmask.sum() > 30:
            bgc = tuple(int(v) for v in np.median(zone[bmask].reshape(-1, 3), axis=0))
        else:
            bgc = (250, 250, 250)
        if tmask.sum() >= 6:
            tc = darkest_quartile(zone[tmask])
            ys_, xs_ = np.nonzero(tmask)
            ex0, ex1 = zx0 + xs_.min(), zx0 + xs_.max()
            ey0, ey1 = zy0 + ys_.min(), zy0 + ys_.max()
        else:
            tc = (0, 105, 55)
            ex0, ex1, ey0, ey1 = zx0, zx1 - 1, ys - 39, ys - 25
            report.append(f"cell c{c}r{r}: fallback zone")
        # erase full between-icon span (safe: icons outside x_s+16..x_s+114)
        d.rectangle([xs + 18, ey0 - 3, xs + 112, ey1 + 3], fill=bgc)
        f, bb = fit_font(cn, 90, 17, 14)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
        cx = xs + 65  # center between icons
        cy = (ey0 + ey1) // 2
        d.text((cx - tw // 2 - bb[0], cy - th // 2 - bb[1]), cn, font=f, fill=tc)
        report.append(f"c{c}r{r} '{cn}': erase y{ey0}-{ey1} tc={tc} bg={bgc}")

# ---- 3. legend 2 lines ----
LEGEND = [("上述女性角色", 655, 678), ("上述以外的其他角色", 687, 708)]
for cn, ry0, ry1 in LEGEND:
    zone = arr[ry0:ry1, 134:520].astype(int)
    zlum = zone.sum(axis=2) / 3
    zmed = np.median(zlum)
    tmask = np.abs(zlum - zmed) > 45
    if tmask.sum() >= 10:
        ys_, xs_ = np.nonzero(tmask)
        lx0, lx1 = 134 + xs_.min(), 134 + xs_.max()
        ly0, ly1 = ry0 + ys_.min(), ry0 + ys_.max()
        tc = darkest_quartile(zone[tmask])
        bgc = tuple(int(v) for v in np.median(zone[~tmask].reshape(-1, 3), axis=0))
    else:
        lx0, lx1, ly0, ly1, tc, bgc = 134, 330, ry0 + 2, ry1 - 2, (0, 90, 60), (20, 70, 50)
        report.append(f"legend '{cn}': fallback")
    d.rectangle([lx0 - 3, ly0 - 3, lx1 + 3, ly1 + 3], fill=bgc)
    f, bb = fit_font(cn, lx1 - lx0 + 60, ly1 - ly0 + 6, 15)
    ox, oy = lx0 - bb[0], (ly0 + ly1) // 2 - (bb[3] - bb[1]) // 2 - bb[1]
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                d.text((ox + dx, oy + dy), cn, font=f, fill=(240, 240, 240))
    d.text((ox, oy), cn, font=f, fill=tc)
    report.append(f"legend '{cn}': x{lx0}-{lx1} y{ly0}-{ly1} tc={tc}")

img.save(OUT / SRC, format="PNG")
(OUT / "opt_voice_base.png").write_bytes((OUT / SRC).read_bytes())
print("\n".join(report))
print("saved:", SRC, "+ opt_voice_base.png")
