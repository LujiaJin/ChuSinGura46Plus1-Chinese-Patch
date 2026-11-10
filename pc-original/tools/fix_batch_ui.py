# -*- coding: utf-8 -*-
"""Batch UI localization for remaining high-frequency items:
1. message-window quick buttons opt_bt_x1-4(+a): 跳过/自动/存档/读档
2. opt_bt_close -> 关闭, opt_bt_info -> 许可信息, his_bt_speaker -> 名字
3. save_base/load_base page titles: セーブ->存档 / ロード->读档
4. save_support/load_support askYesNo -> CN (add to patch)
Method: per-segment flat-fill (median of segment bg after excluding text-colored
pixels) + CN text in sampled original text color; three-state strips preserved.
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
F = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 15)

def seg_bg_and_textcolor(seg):
    """segment: HxWx3 array. bg = median of non-text px; text = median of deviant px."""
    lum = seg.astype(int).sum(axis=2) / 3
    med = np.median(lum)
    m_text = np.abs(lum - med) > 45
    if m_text.sum() < 10:
        return None, None
    bg = np.median(seg[~m_text].reshape(-1, 3), axis=0) if (~m_text).sum() > 30 else None
    tc = np.median(seg[m_text].reshape(-1, 3), axis=0)
    return bg, tc

def redo_button(name, cn):
    img = Image.open(io.BytesIO(BG[name])).convert("RGB")
    W, H = img.size
    sw = W // 3
    arr = np.array(img)
    d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    fs = H - 10
    f = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", max(11, fs))
    bb = d0.textbbox((0, 0), cn, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    for s in range(3):
        seg = arr[:, s * sw:(s + 1) * sw]
        bg, tc = seg_bg_and_textcolor(seg)
        if bg is None:
            bg = np.median(seg.reshape(-1, 3), axis=0)
        if tc is None:
            tc = np.array([255, 255, 255])
        # flat fill preserving 2px border (button edge bevel)
        fill = np.zeros_like(seg)
        for yy in range(seg.shape[0]):
            for xx in range(0, seg.shape[1], 1):
                pass
        # faster: fill interior rows only
        seg[2:H - 2, 2:sw - 2] = bg.astype(np.uint8)
        seg[:, :2] = seg[:, :2]
        arr[:, s * sw:(s + 1) * sw] = seg
    base = Image.fromarray(arr)
    d = ImageDraw.Draw(base)
    for s in range(3):
        bg2, tc2 = seg_bg_and_textcolor(np.array(base)[:, s * sw:(s + 1) * sw])
        col = tuple(int(v) for v in (tc2 if tc2 is not None else [255, 255, 255]))
        px = s * sw + (sw - tw) // 2 - bb[0]
        py = (H - th) // 2 - bb[1]
        d.text((px, py), cn, font=f, fill=col)
    b = io.BytesIO()
    base.save(b, format="PNG")
    (OUT / name).write_bytes(b.getvalue())
    print("done", name, "->", cn)

# 1. quick buttons (x1-4 + a variants share translations)
XMAP = {"opt_bt_x1.png": "跳过", "opt_bt_x1a.png": "跳过",
        "opt_bt_x2.png": "自动", "opt_bt_x2a.png": "自动",
        "opt_bt_x3.png": "存档", "opt_bt_x3a.png": "存档",
        "opt_bt_x4.png": "读档", "opt_bt_x4a.png": "读档",
        "opt_bt_close.png": "关闭", "opt_bt_info.png": "许可信息",
        "his_bt_speaker.png": "名字"}
for n, cn in XMAP.items():
    if n in BG:
        redo_button(n, cn)

# 2. save_base / load_base page titles — locate big title glyphs first
def title_zone(name):
    img = Image.open(io.BytesIO(BG[name])).convert("RGBA")
    arr = np.array(img)
    lum = arr[:, :, :3].astype(int).sum(axis=2) / 3
    # title = big bright glyphs in top band y<120; find columns
    band = lum[:120]
    med = np.median(band)
    dev = np.abs(band - med) > 60
    cols = dev.sum(axis=0)
    nz = np.nonzero(cols > 3)[0]
    rows = dev.sum(axis=1)
    nzr = np.nonzero(rows > 3)[0]
    if not len(nz) or not len(nzr):
        return None
    return int(nz.min()), int(nzr.min()), int(nz.max()), int(nzr.max()), arr

for name, cn in [("save_base.png", "存档"), ("load_base.png", "读档")]:
    z = title_zone(name)
    if not z:
        print(name, "no title found"); continue
    x0, y0, x1, y1, arr = z
    # sample title text color
    reg = arr[y0:y1 + 1, x0:x1 + 1]
    lum = reg[:, :, :3].astype(int).sum(axis=2) / 3
    med = np.median(lum)
    m = np.abs(lum - med) > 60
    tc = np.median(reg[:, :, :3][m], axis=0) if m.sum() > 20 else np.array([255, 255, 255])
    bgc = np.median(reg[:, :, :3][~m], axis=0) if (~m).sum() > 20 else np.array([40, 30, 60])
    # erase: fill title bbox with bg color (bg is the header band color, flat)
    pad = 6
    arr[max(0, y0 - pad):y1 + pad, max(0, x0 - pad):x1 + pad, :3] = bgc.astype(np.uint8)
    base = Image.fromarray(arr)
    d = ImageDraw.Draw(base)
    f = ImageFont.truetype(r"C:\Windows\Fonts\STKAITI.TTF", min(54, (y1 - y0) + 14))
    bb = d.textbbox((0, 0), cn, font=f)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text((x0 - bb[0], y0 - bb[1]), cn, font=f, fill=tuple(int(v) for v in tc))
    b = io.BytesIO()
    base.save(b, format="PNG")
    (OUT / name).write_bytes(b.getvalue())
    print(f"done {name} title x{x0}-{x1} y{y0}-{y1} -> {cn}")

# 3. save/load_support askYesNo
scen = xp3lib.read_xp3("D:/Games/Chusingura46+1/GameInstalled/app/app/scenario.xp3")
for fn in ["save_support.ks", "load_support.ks"]:
    raw = scen[fn]
    enc = "utf-16" if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else "cp932"
    txt = raw.decode(enc)
    txt = txt.replace("推奨設定に戻しますか？", "要恢复推荐设置吗？")
    (OUT / fn).write_bytes(b"\xff\xfe" + txt.encode("utf-16-le"))
    print("done", fn)
print("ALL DONE")
