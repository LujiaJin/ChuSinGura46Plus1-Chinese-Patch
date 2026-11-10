# -*- coding: utf-8 -*-
"""Fix dialog yes/no buttons: TVP2 ButtonLayer multi-state sprite strip.

ButtonLayer.loadImages divides image width by 3 (showFocusImage=false):
  seg1 (x 0-93)   = normal state
  seg2 (x 93-186) = pushed state
  seg3 (x 186-279)= disabled state
Each segment needs its own centered text. Start from original (keeps pink
bg + border), erase original YES/NO per segment, draw CN text per segment.
Output: RGB PNG (color_type=2) matching original format.
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
F_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

N_SEG = 3
FILL = (255, 255, 255)          # white text
STROKE = (170, 60, 109)         # dark pink outline (matches original pushed state)
FONT_SIZE = 30                  # ~30px char fits 93px segment

for name, cn in [("dialog_btyes.png", "是"), ("dialog_btno.png", "否")]:
    img = Image.open(io.BytesIO(BG[name])).convert("RGB")
    W, H = img.size
    sw = W // N_SEG
    arr = np.array(img)

    # --- erase original text in each segment ---
    clean = img
    for i in range(N_SEG):
        seg = np.array(clean.crop((i * sw, 0, (i + 1) * sw, H)))
        lum = seg.sum(axis=2) / 3
        bgmed = np.median(lum)
        mask = (np.abs(lum - bgmed) > 22).astype(np.uint8) * 255
        mask = cv2.dilate(mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
                          iterations=2)
        inp = cv2.inpaint(cv2.cvtColor(seg, cv2.COLOR_RGB2BGR), mask, 5, cv2.INPAINT_TELEA)
        clean = Image.fromarray(cv2.cvtColor(inp, cv2.COLOR_BGR2RGB)) if isinstance(clean, Image.Image) else clean
        # paste back (inpaint returns ndarray per segment)
        clean_img = Image.new("RGB", (W, H))
    # simpler: erase whole-strip at once
    arr = np.array(img)
    lum = arr.sum(axis=2) / 3
    # per-segment background level
    full_mask = np.zeros((H, W), np.uint8)
    for i in range(N_SEG):
        seg_lum = lum[:, i * sw:(i + 1) * sw]
        bgmed = np.median(seg_lum)
        m = np.abs(seg_lum - bgmed) > 22
        full_mask[:, i * sw:(i + 1) * sw] = m.astype(np.uint8) * 255
    full_mask = cv2.dilate(full_mask, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)),
                           iterations=2)
    inp = cv2.inpaint(cv2.cvtColor(arr, cv2.COLOR_RGB2BGR), full_mask, 5, cv2.INPAINT_TELEA)
    base = Image.fromarray(cv2.cvtColor(inp, cv2.COLOR_BGR2RGB)).convert("RGBA")

    # --- draw CN text centered in each segment ---
    font = ImageFont.truetype(F_BOLD, FONT_SIZE)
    d0 = ImageDraw.Draw(Image.new("RGBA", (8, 8)))
    bb = d0.textbbox((0, 0), cn, font=font, stroke_width=2)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    for i in range(N_SEG):
        cx = i * sw + sw // 2
        cy = H // 2
        if i == 1:
            cy += 1  # pushed state: shift down 1px for press feel
        px, py = cx - tw // 2 - bb[0], cy - th // 2 - bb[1]
        ImageDraw.Draw(base).text((px, py), cn, font=font,
                                  fill=FILL + (255,), stroke_width=2,
                                  stroke_fill=STROKE + (255,))

    # save as RGB (color_type=2) to match original format
    out_img = base.convert("RGB")
    b = io.BytesIO()
    out_img.save(b, format="PNG")
    (OUT / name).write_bytes(b.getvalue())

    # verify: each segment now has visible dark-stroke pixels
    varr = np.array(out_img)
    for i in range(N_SEG):
        seg = varr[:, i * sw:(i + 1) * sw]
        slum = seg.sum(axis=2) / 3
        n_dark = int((slum < 120).sum())
        n_white = int((slum > 230).sum())
        print(f"{name} seg{i+1}: dark={n_dark} white={n_white}")

    # preview strip
    out_img.resize((W * 2, H * 2), Image.NEAREST).save(f"preview3_{name[:-4]}.png")

print("Done — 3-state sprite strips with per-segment CN text")
