# -*- coding: utf-8 -*-
"""Legend correction for voiceopt_base: the original has ONE legend line only
「上記以外のその他キャラ ◆◆◆」 (red text on white arrow tag, text x~120-297,
y~658-675). v2 wrongly drew two CN lines and damaged the turquoise deco band.
This fix: restore legend region from original, erase red JP text, draw CN."""
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

orig = Image.open(io.BytesIO(BG[SRC])).convert("RGB")
img = Image.open(OUT / SRC).convert("RGB")

# 1) restore legend region wholesale from original (paste, not numpy-copy!)
img.paste(orig.crop((90, 640, 700, 720)), (90, 640))
a = np.array(img)

# 2) find red JP text pixels in the tag row band
band = a[650:682, 105:420].astype(int)
R, G, B = band[:, :, 0], band[:, :, 1], band[:, :, 2]
red = (R > 130) & (R - G > 50) & (R - B > 50)
print("red px:", int(red.sum()))
if red.sum() > 15:
    ys, xs = np.nonzero(red)
    tx0, tx1 = 105 + xs.min(), 105 + xs.max()
    ty0, ty1 = 650 + ys.min(), 650 + ys.max()
    print("text bbox:", tx0, tx1, ty0, ty1)
    tc = tuple(int(v) for v in np.median(band[red].reshape(-1, 3), axis=0))
    # tag bg: non-red bright pixels in same rows
    nonred = ~red & (band.sum(axis=2) / 3 > 170)
    bgc = tuple(int(v) for v in np.median(band[nonred].reshape(-1, 3), axis=0))
    print("text color:", tc, "tag bg:", bgc)
    # 3) erase text only (stop before the ◆ diamonds: erase to tx1 which is last red px;
    #    diamonds are green per analysis, not red, so red-mask bbox is safe)
    d = ImageDraw.Draw(img)
    d.rectangle([tx0 - 1, ty0 - 3, tx1 + 3, ty1 + 3], fill=bgc)
    # 4) draw CN, left-aligned at same x, vertically centered
    cn = "上述以外的其他角色"
    f = bb = None
    for size in range(17, 11, -1):
        f = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", size)
        bb = d.textbbox((0, 0), cn, font=f)
        if bb[2] - bb[0] <= (tx1 - tx0) + 16:
            break
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    cy = (ty0 + ty1) // 2
    d.text((tx0 - bb[0], cy - th // 2 - bb[1]), cn, font=f, fill=tc)
    print("drew", cn, "size", size, "at x", tx0, "cy", cy)

img.save(OUT / SRC, format="PNG")
(OUT / "opt_voice_base.png").write_bytes((OUT / SRC).read_bytes())
print("saved both")
