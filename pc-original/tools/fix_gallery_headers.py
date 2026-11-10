# -*- coding: utf-8 -*-
"""Gallery page headers: wipe banner text, draw CN title + subtitle."""
import sys, io
sys.path.insert(0, r"D:/Games/Chusingura46+1/Tools/pipeline")
import xp3lib
from PIL import Image, ImageDraw, ImageFont
import numpy as np

bg = xp3lib.read_xp3("D:/Games/Chusingura46+1/GameInstalled/app/app/bgimage.xp3")
F_BIG = ImageFont.truetype(r"C:\Windows\Fonts\STKAITI.TTF", 24)
F_SUB = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 15)

jobs = [("bgm_base.png", "音乐", "欣赏游戏中的全部背景音乐与歌曲"),
        ("moviemode_base.png", "影像", "观看已解锁的动画影片"),
        ("al_base.png", "CG", "浏览已解锁的事件CG画廊"),
        ("al_base2.png", "CG", "浏览已解锁的事件CG画廊")]

for n, big, sub in jobs:
    img = Image.open(io.BytesIO(bg[n])).convert("RGBA")
    arr = np.array(img)
    arr[52:77, 64:1116, :3] = (250, 249, 252)
    for yb in (52, 76):
        arr[yb, 64:1116] = ((arr[yb - 1, 64:1116].astype(int)
                             + 2 * arr[yb, 64:1116].astype(int)
                             + arr[yb + 1, 64:1116].astype(int)) // 4).astype(np.uint8)
    base = Image.fromarray(arr)
    d = ImageDraw.Draw(base)
    d.text((110, 54), big, font=F_BIG, fill=(60, 48, 90, 255))
    d.text((190, 58), sub, font=F_SUB, fill=(110, 92, 150, 255))
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    open(rf"D:/Games/Chusingura46+1/Tools/pipeline/zh_out/{n}", "wb").write(buf.getvalue())
    print("done", n)
