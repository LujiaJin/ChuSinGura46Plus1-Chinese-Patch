# -*- coding: utf-8 -*-
"""moviemode_bt* video gallery buttons (3-state strips 214x144 per segment).
Adapted from fix_sm_bt.py: detect text band in bottom half, wipe per segment
with local flat color, redraw CN centered in sampled original text color."""
import sys, io, os
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PIPE = Path(os.path.dirname(os.path.abspath(__file__)))
OUT = PIPE / "zh_out"
sys.path.insert(0, str(PIPE))
import xp3lib

BG = xp3lib.read_xp3("D:/Games/Chusingura46+1/GameInstalled/app/app/bgimage.xp3")

SM = {
    "bt0": "开场动画 1", "bt1": "开场动画 2",
    "bt2": "百花魁篇 开场动画", "bt3": "仇华宿怨篇 开场动画",
    "bt0a": "假名手本篇 结尾动画", "bt1a": "安兵卫篇 结尾动画",
    "bt2a": "主税篇 结尾动画", "bt3a": "一学篇 结尾动画",
    "bt4a": "大结局动画",
}

def sample_text_color(arr):
    lum = arr.astype(int).sum(axis=2) / 3
    med = np.median(lum)
    m = np.abs(lum - med) > 60
    if m.sum() < 10:
        return (255, 255, 255)
    return tuple(int(v) for v in np.median(arr[m][:, :3].reshape(-1, 3), axis=0))

def rebuild(name, cn):
    img = Image.open(io.BytesIO(BG[name])).convert("RGBA")
    W, H = img.size
    sw = W // 3
    arr = np.array(img)
    lum = arr[:, :sw, :3].astype(int).sum(axis=2) / 3
    med_all = np.median(lum)
    rowdev = np.abs(lum - med_all).mean(axis=1)
    text_rows = np.nonzero(rowdev > 12)[0]
    text_rows = text_rows[text_rows > H // 2 - 12]
    if len(text_rows) == 0:
        print("no text", name); return
    ty0, ty1 = int(text_rows.min()), int(text_rows.max())
    coldev = np.abs(lum[ty0:ty1 + 1] - med_all).mean(axis=0)
    tcols = np.nonzero(coldev > 12)[0]
    tx0 = int(tcols.min()) if len(tcols) else 0
    tx1 = int(tcols.max()) if len(tcols) else sw
    col = sample_text_color(arr[ty0:ty1 + 1, tx0:tx1 + 1])

    for s in range(3):
        xs = s * sw
        reg = arr[ty0 - 3:ty1 + 4, xs:xs + sw]
        rl = reg[:, :, :3].astype(int).sum(axis=2) / 3
        rmed = np.median(rl)
        rm = np.abs(rl - rmed) > 40
        if rm.sum() > 0 and (~rm).sum() > 30:
            bgc = np.median(reg[:, :, :3][~rm].reshape(-1, 3), axis=0).astype(np.uint8)
        else:
            bgc = np.array([40, 40, 40], dtype=np.uint8)
        arr[ty0 - 2:ty1 + 3, xs + max(0, tx0 - 4):xs + min(sw, tx1 + 5), :3] = bgc
        arr[ty0 - 2:ty1 + 3, xs + max(0, tx0 - 4):xs + min(sw, tx1 + 5), 3] = 255

    base = Image.fromarray(arr)
    d = ImageDraw.Draw(base)
    f = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 16)
    bb = d.textbbox((0, 0), cn, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    if tw > sw - 10:
        f = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 13)
        bb = d.textbbox((0, 0), cn, font=f)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
    for s in range(3):
        px = s * sw + (sw - tw) // 2 - bb[0]
        py = (ty0 + ty1) // 2 - th // 2 - bb[1]
        d.text((px, py), cn, font=f, fill=col + (255,))
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    (OUT / name).write_bytes(buf.getvalue())
    print("done", name, "->", cn, f"band y{ty0}-{ty1} col{col}")

for stem, cn in SM.items():
    name = f"moviemode_{stem}.png"
    if name in BG:
        rebuild(name, cn)
    else:
        print("skip", name)
