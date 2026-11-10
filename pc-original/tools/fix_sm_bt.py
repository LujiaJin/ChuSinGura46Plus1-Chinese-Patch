# -*- coding: utf-8 -*-
"""Translate sm_bt_* scene-mode title buttons (3-state strips, text zone only).
These are the CG/scene gallery entry cards: thumbnail area (keep) + title text at bottom."""
import sys, io, os, re
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PIPE = Path(os.path.dirname(os.path.abspath(__file__)))
OUT = PIPE / "zh_out"
sys.path.insert(0, str(PIPE))
import xp3lib

BG = xp3lib.read_xp3("D:/Games/Chusingura46+1/GameInstalled/app/app/bgimage.xp3")
F = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 18)

# translation map for sm_bt stems
SM = {
    "kurah01": "大石内藏助 H场景 1", "kurah02": "大石内藏助 H场景 2",
    "yasuh01": "堀部安兵卫 H场景 1", "yasuh02": "堀部安兵卫 H场景 2",
    "chikah01": "大石主税 H场景 1", "chikah02": "大石主税 H场景 2",
    "emosh01": "矢头右卫门七 H场景 1", "emosh02": "矢头右卫门七 H场景 2",
    "gakuh01": "清水一学 H场景 1",
    "uchiirik": "假名手本忠臣藏篇 讨入", "uchiiriy": "假名手本忠臣藏篇 讨入",
    "uchiiric": "假名手本忠臣藏篇 讨入",
    "saisyu": "最终回",
}

def sample_text_color(arr):
    lum = arr.sum(axis=2) / 3
    med = np.median(lum)
    m = np.abs(lum - med) > 60
    if m.sum() < 10:
        return (255, 255, 255, 255)
    return tuple(int(v) for v in np.median(arr[m][:, :3], axis=0)) + (255,)

def rebuild(name, cn):
    img = Image.open(io.BytesIO(BG[name])).convert("RGBA")
    W, H = img.size
    sw = W // 3
    arr = np.array(img)
    # find text band: rows in bottom half with high deviation
    lum = arr[:, :sw, :3].astype(int).sum(axis=2) / 3
    med_all = np.median(lum)
    rowdev = np.abs(lum - med_all).mean(axis=1)
    text_rows = np.nonzero(rowdev > 15)[0]
    if len(text_rows) == 0:
        print("no text found", name)
        return
    ty0, ty1 = int(text_rows.min()), int(text_rows.max())
    # find text columns
    coldev = np.abs(lum[ty0:ty1 + 1] - med_all).mean(axis=0)
    tcols = np.nonzero(coldev > 15)[0]
    tx0 = int(tcols.min()) if len(tcols) else 0
    tx1 = int(tcols.max()) if len(tcols) else sw

    # sample colors from original seg1
    col = sample_text_color(arr[ty0:ty1 + 1, tx0:tx1 + 1])

    # wipe text zone per segment (keep alpha=0 outside text bbox ring)
    for s in range(3):
        xs = s * sw
        # fill text bbox with surrounding flat color (median of non-dev pixels near it)
        reg = arr[ty0 - 3:ty1 + 4, xs:xs + sw]
        rl = reg[:, :, :3].astype(int).sum(axis=2) / 3
        rmed = np.median(rl)
        rm = np.abs(rl - rmed) > 40
        if rm.sum() > 0 and (~rm).sum() > 30:
            bgc = np.median(reg[:, :, :3][~rm].reshape(-1, 3), axis=0).astype(np.uint8)
        else:
            bgc = np.array([40, 40, 40], dtype=np.uint8)
        arr[ty0 - 2:ty1 + 3, xs + max(0, tx0 - 4):xs + min(sw, tx1 + 5), :3] = bgc
        # clear alpha in text zone
        arr[ty0 - 2:ty1 + 3, xs + max(0, tx0 - 4):xs + min(sw, tx1 + 5), 3] = 0

    base = Image.fromarray(arr)
    d = ImageDraw.Draw(base)
    bb = d.textbbox((0, 0), cn, font=F)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    if tw > sw - 8:
        f2 = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 15)
        bb = d.textbbox((0, 0), cn, font=f2)
        tw, th = bb[2] - bb[0], bb[3] - bb[1]
    else:
        f2 = F
    for s in range(3):
        px = s * sw + (sw - tw) // 2 - bb[0]
        py = (ty0 + ty1) // 2 - th // 2 - bb[1]
        d.text((px, py), cn, font=f2, fill=col)
    buf = io.BytesIO()
    base.save(buf, format="PNG")
    (OUT / name).write_bytes(buf.getvalue())
    print("done", name, "->", cn)

for stem, cn in SM.items():
    name = f"sm_bt_{stem}.png"
    if name in BG:
        rebuild(name, cn)
    else:
        print("skip (not in bg):", name)
