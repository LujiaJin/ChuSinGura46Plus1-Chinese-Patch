# -*- coding: utf-8 -*-
"""Rebuild DANGER.PNG completely: pure white canvas + full Chinese redraw.
No erase pass at all — every JP pixel gone by construction. RGB output."""
import sys, io, os
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

PIPE = Path(os.path.dirname(os.path.abspath(__file__)))
OUT = PIPE / "zh_out"

W, H = 1280, 720
img = Image.new("RGB", (W, H), (255, 255, 255))
d = ImageDraw.Draw(img)

F_TITLE = r"C:\Windows\Fonts\msyhbd.ttc"   # bold
F_BODY = r"C:\Windows\Fonts\msyh.ttc"      # regular
F_EN = r"C:\Windows\Fonts\msyh.ttc"

RED = (217, 32, 24)
BLACK = (25, 25, 25)
GRAY = (150, 150, 150)

def center_text(cx, cy, text, font, fill):
    bb = d.textbbox((0, 0), text, font=font)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    d.text((cx - tw // 2 - bb[0], cy - th // 2 - bb[1]), text, font=font, fill=fill)

# title
center_text(640, 140, "【注意】", ImageFont.truetype(F_TITLE, 46), RED)

# body lines (keep the same CN wording the user already approved)
body = ImageFont.truetype(F_BODY, 27)
lines = [
    (215, "本软件含有成人内容。"),
    (262, "未满 18 周岁者不得购买、下载或游玩本作品。"),
    (330, "本作品中登场的角色、组织、事件均为虚构，"),
    (372, "与现实中的任何人物、团体、事件无关。"),
    (440, "禁止将本作品内容转载、上传至任何公开平台。"),
]
for y, t in lines:
    center_text(640, y, t, body, BLACK)

# footer
center_text(640, 655, "INRE  All Rights Reserved.", ImageFont.truetype(F_EN, 23), GRAY)

b = io.BytesIO()
img.save(b, format="PNG")
(OUT / "DANGER.PNG").write_bytes(b.getvalue())
img.resize((W * 2 // 2, H * 2 // 2)).save(PIPE / "danger_v2_preview.png")
print("saved DANGER.PNG (pure white + CN, RGB, no JP pixels possible)")
