# -*- coding: utf-8 -*-
"""In-place JP->CN swap v2 with INPAINT erase:
- precise text mask (dist>12 from local bg, dilated) -> cv2.inpaint
  (catches ALL anti-aliased remnants that row-clone missed)
- CN drawn at original anchors in sampled original colors
- banner: whole-strip wipe (non-white -> inpaint), CN plain text
"""
import sys, io, os
from pathlib import Path
import numpy as np
import cv2
from PIL import Image, ImageDraw, ImageFont

PIPE = Path(os.path.dirname(os.path.abspath(__file__)))
OUT = PIPE / "zh_out"
sys.path.insert(0, str(PIPE))
import xp3lib

BG = xp3lib.read_xp3("D:/Games/Chusingura46+1/GameInstalled/app/app/bgimage.xp3")
img = Image.open(io.BytesIO(BG["opt_base.png"])).convert("RGBA")
arr = np.array(img)

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

# sample BEFORE erase
RED = sample_color(arr, 90, 144, 133, 160, "red")
GREEN = sample_color(arr, 306, 216, 460, 232, "green")
LIGHT = sample_color(arr, 655, 432, 850, 446, "light")
BULLET = sample_color(arr, 286, 215, 302, 231, "red")
print("colors:", RED, GREEN, LIGHT, BULLET)

# ---------- erase with inpaint ----------
BANDS = [
    (84, 130, 262, 174), (84, 238, 262, 282), (83, 475, 262, 519),
    (283, 126, 566, 172), (283, 197, 566, 243), (283, 269, 566, 315),
    (283, 340, 566, 386), (283, 412, 566, 458), (283, 483, 566, 529),
    (650, 126, 900, 172), (650, 225, 900, 271), (650, 315, 900, 364),
    (650, 420, 900, 466), (650, 450, 900, 486), (650, 501, 800, 547),
    (948, 125, 1180, 169), (948, 195, 1180, 239), (948, 265, 1180, 309),
    (948, 333, 1180, 377), (948, 398, 1180, 444),
    (320, 46, 1130, 82),   # banner strip whole
]
rgb = arr[:, :, :3].copy()
mask = np.zeros(arr.shape[:2], np.uint8)
for x0, y0, x1, y1 in BANDS:
    reg = rgb[y0:y1, x0:x1]
    med = np.median(reg.reshape(-1, 3), axis=0)
    dist = np.abs(reg.astype(int) - med).sum(axis=2)
    m = (dist > 12).astype(np.uint8) * 255
    m = cv2.dilate(m, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5)), iterations=2)
    mask[y0:y1, x0:x1] = np.maximum(mask[y0:y1, x0:x1], m)
# protect: don't erase my future text zones entirely - inpaint will fill, we redraw anyway
inp = cv2.inpaint(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), mask, 6, cv2.INPAINT_TELEA)
rgb = cv2.cvtColor(inp, cv2.COLOR_BGR2RGB)
arr[:, :, :3] = rgb

base = Image.fromarray(arr)
d = ImageDraw.Draw(base)
F = ImageFont.truetype(r"C:\Windows\Fonts\msyhbd.ttc", 15)

def swap(x, y, text, color):
    d.text((x, y - 1), text, font=F, fill=color)

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
swap(659, 431, "窗口设置", LIGHT)
swap(659, 460, "窗口不透明度", RED)
swap(664, 521, "字体设置", RED)
swap(962, 143, "语音音量", RED)
swap(962, 213, "BGM音量", RED)
swap(962, 283, "音效音量", RED)
swap(962, 351, "系统音量", RED)
swap(962, 416, "延续语音播放", RED)
d.text((332, 55), "可在此处进行游戏的各种设置", font=F, fill=(72, 60, 92, 255))

b = io.BytesIO()
base.save(b, format="PNG")
(OUT / "opt_base.png").write_bytes(b.getvalue())
print("opt_base inpaint v2 saved")

# verification crops at 3x
prev = base.convert("RGB")
prev.crop((318, 46, 1130, 82)).resize((812 * 2, 36 * 4), Image.LANCZOS).save(PIPE / "v2_banner.png")
prev.crop((70, 125, 420, 180)).resize((350 * 2, 55 * 3), Image.LANCZOS).save(PIPE / "v2_colA1.png")
prev.crop((640, 495, 900, 550)).resize((260 * 2, 55 * 3), Image.LANCZOS).save(PIPE / "v2_colC5.png")
prev.crop((930, 395, 1200, 450)).resize((270 * 2, 55 * 3), Image.LANCZOS).save(PIPE / "v2_colD5.png")
prev.crop((260, 120, 600, 550)).resize((340 * 2, 430 * 1.5), Image.LANCZOS).save(PIPE / "v2_colB.png")
