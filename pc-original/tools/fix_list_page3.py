# -*- coding: utf-8 -*-
"""List page v3 — remove all visible text boxes:
1. cl_bt_*: chip area -> fully transparent; name = black brush text + soft white halo
2. cl_bt_return: transparent + black 返回
3. list_base: white banner strip REMOVED (glass rows y+30 cloned in, stripe phase exact),
   CN subtitle drawn as plain dark text on the glass.
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
F_BRUSH = r"C:\Windows\Fonts\STXINGKA.TTF"
F_UI = r"C:\Windows\Fonts\msyhbd.ttc"

saved = 0
def save(img, name):
    global saved
    b = io.BytesIO()
    img.save(b, format="PNG")
    (OUT / name).write_bytes(b.getvalue())
    saved += 1

CL_NAMES = {
    "taku": "浅野内匠头", "agu": "浅野阿久里", "iso": "矶贝十郎左卫门",
    "kura": "大石内藏助", "chi": "大石松之丞（主税）", "mago": "奥田孙太夫",
    "oku": "奥野将监", "gen": "片冈源五右卫门", "kaya": "萱野三平",
    "gunb": "高田郡兵卫", "tada": "武林唯七", "shin": "间新六",
    "haya": "早水藤左卫门", "fuwa": "不破数卫门", "yasu": "堀部安兵卫",
    "kohe": "毛利小平太", "mimu": "三村次郎左卫门", "emos": "矢头右卫门七",
    "cho": "矢头长助", "iro": "色部安长", "oume": "阿梅",
    "oka": "多门传八郎", "sorai": "荻生徂徕", "kaki": "垣见五郎兵卫",
    "kira": "吉良上野介", "kozi": "深海铛", "saru": "猿桥",
    "gaku": "清水一学", "tsuchi": "土屋主税", "tsuna": "德川纲吉",
    "okin": "阿琴", "nana": "菜夏", "oha": "桥本阿初",
    "hei": "桥本平左卫门", "toki": "毛利时房", "kinu": "矢头绢",
    "sayo": "矢头小夜", "muku": "矢头无垢", "rui": "矢头琉依",
    "yazi": "屋治助", "yana": "柳泽吉保", "asa": "山田浅右卫门",
    "yama": "山吉新八郎",
}

def find_avatar_edge(seg1_arr, sw):
    lum = seg1_arr[:, :, :3].astype(int).sum(axis=2) / 3   # RGB only — alpha would inflate ink pixels
    cnt = (lum > 60).sum(axis=0)
    edge = 0
    for x in range(min(80, sw)):
        if cnt[x] > 10:
            edge = x
    return edge + 1

INK = (32, 28, 34, 255)          # near-black ink
HALO = (255, 255, 255, 185)      # soft white halo (not a box)

def rebuild_cl_bt(tag, cn):
    name = f"cl_bt_{tag}.png"
    img = Image.open(io.BytesIO(BG[name])).convert("RGBA")
    W, H = img.size
    sw = W // 3
    arr = np.array(img)
    seg1 = arr[:, :sw]
    av_edge = find_avatar_edge(seg1, sw)

    # wipe chip area to fully transparent (all rows, all segments); from av_edge —
    # the original ink text starts at av_edge, +2 offset left 1-2px slivers
    for s in range(3):
        arr[:, s * sw + av_edge:(s + 1) * sw, 3] = 0

    # fit font
    avail = sw - av_edge - 12
    d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    fs = 27
    while fs > 10:
        f = ImageFont.truetype(F_BRUSH, fs)
        bb = d0.textbbox((0, 0), cn, font=f, stroke_width=2)
        if bb[2] - bb[0] <= avail:
            break
        fs -= 1
    f = ImageFont.truetype(F_BRUSH, fs)
    bb = d0.textbbox((0, 0), cn, font=f, stroke_width=2)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    tx = av_edge + 6 + (avail - tw) // 2 - bb[0]
    ty = (H - th) // 2 - bb[1]

    base = Image.fromarray(arr)
    d = ImageDraw.Draw(base)
    for s in range(3):
        d.text((s * sw + tx, ty), cn, font=f, fill=INK,
               stroke_width=2, stroke_fill=HALO)
    save(base, name)

print("=== cl_bt names (boxless) ===")
for tag, cn in CL_NAMES.items():
    rebuild_cl_bt(tag, cn)
print("  43 done")

# --- cl_bt_return: transparent + black 返回 ---
img = Image.open(io.BytesIO(BG["cl_bt_return.png"])).convert("RGBA")
W, H = img.size
sw = W // 3
arr = np.array(img)
for s in range(3):
    arr[:, s * sw:(s + 1) * sw, 3] = 0
base = Image.fromarray(arr)
d = ImageDraw.Draw(base)
d0 = ImageDraw.Draw(Image.new("RGB", (8, 8)))
f = ImageFont.truetype(F_UI, 20)
cn = "返回"
bb = d0.textbbox((0, 0), cn, font=f, stroke_width=1)
tw, th = bb[2] - bb[0], bb[3] - bb[1]
for s in range(3):
    px = s * sw + (sw - tw) // 2 - bb[0]
    py = (H - th) // 2 - bb[1]
    d.text((px, py), cn, font=f, fill=INK, stroke_width=1, stroke_fill=HALO)
save(base, "cl_bt_return.png")
print("  cl_bt_return done")

# ============================================================
# list_base: remove white banner + boxless subtitle
# ============================================================
print("=== list_base ===")
img = Image.open(io.BytesIO(BG["list_base.png"])).convert("RGBA")
arr = np.array(img)
H, W = arr.shape[:2]

# detect banner horizontal extent (rows 52..58 & 70..75 near-white opaque)
def is_white_col(x):
    for y in list(range(52, 59)) + list(range(70, 76)):
        px = arr[y, x]
        if not ((px[0] > 238 and px[1] > 238 and px[2] > 240) and px[3] > 225):
            return False
    return True

left = None
for x in range(280, 380):
    if is_white_col(x):
        left = x
        break
right = None
for x in range(1279, 1100, -1):
    if is_white_col(x):
        right = x
        break
print(f"  banner x: {left}..{right}")

if left and right:
    # fill from x=315 (right of CHARA LIST's final T at 290-310) down to row 96 —
    # covers the banner strip (left edge ~322) incl. its rounded cap
    x0 = 315
    x1 = min(W - 1, right + 5)
    for y in range(48, 97):
        arr[y, x0:x1 + 1] = arr[y + 30, x0:x1 + 1]
    # feather the paste seams vertically (2px)
    for y in [48, 49, 95, 96]:
        a = arr[y, x0:x1 + 1, 3].astype(int)
        ab = arr[y - 1 if y == 48 else y + 1, x0:x1 + 1, 3].astype(int)
        arr[y, x0:x1 + 1, 3] = ((a + ab) // 2).astype(np.uint8)

base = Image.fromarray(arr)
d = ImageDraw.Draw(base)
cn = "可浏览游戏中登场角色的信息"
f = ImageFont.truetype(F_UI, 16)
d.text((330, 54), cn, font=f, fill=(48, 40, 66, 255),
       stroke_width=1, stroke_fill=(255, 255, 255, 150))
save(base, "list_base.png")
print("  done")

print(f"\nTOTAL: {saved} files")
