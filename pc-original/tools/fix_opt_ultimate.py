# -*- coding: utf-8 -*-
"""ULTIMATE config page = proven components combined:
- label bands: v3 compact BANDS + clone_above (verified clean in v3)
- banner: solid white strip interior (verified in rebuild)
- panel titles: white band repaint + CN (verified in rebuild)
- colC mid header handled in-band
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
img = Image.open(io.BytesIO(BG["opt_base.png"])).convert("RGBA")
arr = np.array(img)
H, W = arr.shape[:2]

def sample_color(a, x0, y0, x1, y1, kind):
    reg = a[y0:y1 + 1, x0:x1 + 1].astype(int)
    r, g, b = reg[:, :, 0], reg[:, :, 1], reg[:, :, 2]
    if kind == "red":
        m = (r > 120) & (g < 115) & (r - g > 40)
    elif kind == "green":
        m = (g > r + 15) & (g > 60)
    else:
        m = (r + g + b) / 3 > 200
    if m.sum() < 8:
        return (120, 120, 120, 255)
    return tuple(int(v) for v in np.median(reg[m][:, :3], axis=0)) + (255,)

RED = sample_color(arr, 90, 144, 133, 160, "red")
GREEN = sample_color(arr, 306, 216, 460, 232, "green")
LIGHT = sample_color(arr, 655, 432, 850, 446, "light")
BULLET = sample_color(arr, 286, 215, 302, 231, "red")
TITLE_G = sample_color(arr, 82, 100, 248, 138, "green")

def clone_fill_rows(a, x0, y0, x1, y1):
    sy = max(0, y0 - 8)
    src = a[sy:sy + 4, x0:x1 + 1].mean(axis=0)
    for i in range(y1 - y0 + 1):
        a[y0 + i, x0:x1 + 1] = src.astype(np.uint8)
    for yb in (y0, y0 + 1, y1, y1 - 1):
        if 0 < yb < H - 1:
            a[yb, x0:x1 + 1] = ((a[yb - 1, x0:x1 + 1].astype(int)
                                 + 2 * a[yb, x0:x1 + 1].astype(int)
                                 + a[yb + 1, x0:x1 + 1].astype(int)) // 4).astype(np.uint8)

# v3 compact bands (proven)
BANDS = [
    (84, 136, 262, 170), (84, 244, 262, 278), (83, 481, 262, 515),
    (283, 132, 566, 168), (283, 203, 566, 239), (283, 275, 566, 311),
    (283, 346, 566, 382), (283, 418, 566, 454), (283, 489, 566, 525),
    (650, 132, 900, 168), (650, 231, 900, 267), (650, 321, 900, 360),
    (650, 426, 900, 462), (650, 450, 900, 482), (650, 507, 800, 543),
    (948, 131, 1180, 165), (948, 201, 1180, 235), (948, 271, 1180, 305),
    (948, 339, 1180, 373), (948, 404, 1180, 440),
]
for x0, y0, x1, y1 in BANDS:
    clone_fill_rows(arr, x0, y0, x1, y1)

# banner solid white
arr[52:77, 326:1116] = (250, 249, 252, 255)
for yb in (52, 76):
    arr[yb, 326:1116] = ((arr[yb - 1, 326:1116].astype(int)
                          + 2 * arr[yb, 326:1116].astype(int)
                          + arr[yb + 1, 326:1116].astype(int)) // 4).astype(np.uint8)

# title boxes white band
for x0, x1 in [(66, 262), (270, 566), (630, 902), (926, 1186)]:
    arr[104:127, x0 + 12:x1 - 48] = (252, 251, 252, 255)
    for yb in (104, 126):
        arr[yb, x0 + 12:x1 - 48] = ((arr[yb - 1, x0 + 12:x1 - 48].astype(int)
                                      + 2 * arr[yb, x0 + 12:x1 - 48].astype(int)
                                      + arr[yb + 1, x0 + 12:x1 - 48].astype(int)) // 4).astype(np.uint8)

base = Image.fromarray(arr)
d = ImageDraw.Draw(base)
F = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 15)
FT = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 16)

def swap(x, y, text, color, f=F):
    d.text((x, y - 1), text, font=f, fill=color)

def bullet(x, y):
    d.polygon([(x + 5, y), (x + 10, y + 5), (x + 5, y + 10), (x, y + 5)], fill=BULLET)

swap(90, 145, "画面模式", RED)
swap(90, 253, "画面大小", RED)
swap(89, 490, "始终置顶", RED)
for y, cn in [(145, "系统按钮显示"), (216, "画面特效"), (288, "对话框鼠标显示"),
              (359, "非激活时动作"), (431, "自动隐藏指针"), (502, "跳过未读")]:
    bullet(289, y + 1)
    swap(306, y, cn, GREEN)
swap(663, 144, "消息速度", RED)
swap(664, 243, "自动消息速度", RED)
swap(659, 343, "已读文字变色", RED)
swap(663, 431, "窗口设置", LIGHT)
swap(659, 460, "窗口不透明度", RED)
swap(664, 521, "字体设置", RED)
swap(962, 143, "语音音量", RED)
swap(962, 213, "BGM音量", RED)
swap(962, 283, "音效音量", RED)
swap(962, 351, "系统音量", RED)
swap(962, 416, "延续语音播放", RED)
for x0, x1, cn in [(66, 262, "画面设置"), (270, 566, "详细设置"),
                    (630, 902, "消息设置"), (926, 1186, "声音设置")]:
    d.text((x0 + 18, 106), cn, font=FT, fill=TITLE_G)
d.text((332, 55), "可在此处进行游戏的各种设置", font=F, fill=(72, 60, 92, 255))

b = io.BytesIO()
base.save(b, format="PNG")
(OUT / "opt_base.png").write_bytes(b.getvalue())
print("ULTIMATE opt_base saved")

prev = base.convert("RGB")
prev.crop((260, 120, 600, 550)).resize((680, 860), Image.LANCZOS).save(PIPE / "ult_left.png")
prev.crop((620, 120, 1240, 550)).resize((1240, 860), Image.LANCZOS).save(PIPE / "ult_right.png")
prev.crop((60, 90, 1200, 150)).resize((2280, 120), Image.LANCZOS).save(PIPE / "ult_titles.png")
prev.crop((316, 44, 1132, 84)).resize((1632, 80), Image.LANCZOS).save(PIPE / "ult_banner.png")
print("previews ok")
