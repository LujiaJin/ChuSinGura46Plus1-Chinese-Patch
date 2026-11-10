# -*- coding: utf-8 -*-
"""chara01-43.jpg rebuild v3 — cross-page background reconstruction.
Ground truth: panel bg (lattice band + fields + para) is pixel-identical across
all 43 pages (verified spread=0). JP text = dark glyphs + ~3px white stroke.
Strategy:
  1. build per-page dark mask (glyphs+badge+hair+item) over three bands
  2. global bg = per-pixel nanmedian over all pages' valid (non-dark) px
  3. stage-2 for low-donor pixels: phase-shifted lattice cloning (autocorr period)
  4. per target page: patch = its own dilated dark mask ∩ allowed region <- bg
     (portrait hair outside glyph boxes, badges, items preserved)
  5. draw CN name / fields / intro with stroke halo
"""
import sys, io, os, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont

PIPE = Path(os.path.dirname(os.path.abspath(__file__)))
OUT = PIPE / "zh_out"
sys.path.insert(0, str(PIPE))
import xp3lib

BGARCH = xp3lib.read_xp3("D:/Games/Chusingura46+1/GameInstalled/app/app/bgimage.xp3")
BRUSH = "C:/Windows/Fonts/STXINGKA.TTF"
HEI = r"C:\Windows\Fonts\msyhbd.ttc"
DATA = json.load(open(PIPE / "chara_work" / "chara_cn.json", encoding="utf-8"))
LEN_JP = {1:5,2:5,3:4,4:6,5:6,6:3,7:4,8:5,9:7,10:8,11:7,12:5,13:4,14:5,15:5,16:4,
          17:5,18:4,19:4,20:9,21:4,22:4,23:5,24:4,25:2,26:2,27:4,28:3,29:3,30:5,
          31:4,32:3,33:7,34:4,35:5,36:4,37:7,38:2,39:4,40:2,41:4,42:3,43:7}

def dilate(m, it):
    for _ in range(it):
        p = np.pad(m, 1)
        m = p[1:-1, 1:-1] | p[:-2, 1:-1] | p[2:, 1:-1] | p[1:-1, :-2] | p[1:-1, 2:]
    return m

# ---------------- load originals ----------------
ORIG = {}
for i in range(1, 44):
    ORIG[i] = np.array(Image.open(io.BytesIO(BGARCH[f"chara{i:02d}.jpg"])).convert("RGB"))

# bands: strip y40-160, fields y192-258, para y256-548 (x clipped per band)
BANDS = {"strip": (40, 160, 326, 716), "fields": (192, 258, 380, 716), "para": (256, 548, 384, 710)}

DARK = {}
for i in range(1, 44):
    im = ORIG[i].astype(int)
    dm = np.zeros(im.shape[:2], bool)
    lum = im.sum(axis=2) / 3
    pmed = np.median(lum[40:560, 326:716])
    m = lum < pmed - 26
    m = dilate(m, 4)          # cover white stroke + antialias fringe
    dm[40:560, 326:716] = m[40:560, 326:716]
    DARK[i] = dm

# ---------------- global bg reconstruction ----------------
def band_bg(band, min_donors=6):
    y0, y1, x0, x1 = BANDS[band]
    h, w = y1 - y0, x1 - x0
    stack = np.stack([ORIG[i][y0:y1, x0:x1] for i in range(1, 44)]).astype(np.float32)
    valid = np.stack([~DARK[i][y0:y1, x0:x1] for i in range(1, 44)])
    vals = np.where(valid[:, :, :, None], stack, np.nan)
    bg = np.nanmedian(vals, axis=0)
    cnt = (~np.isnan(vals[:, :, :, 0])).sum(axis=0)
    return bg, cnt, (y0, x0)

# lattice period via autocorrelation on clean top band y16-44
def lattice_period():
    full = ORIG[25][16:44, 430:700].astype(float).sum(axis=2) / 3
    best = (0, 0, -1)
    for dy in range(0, 26):
        for dx in range(6, 64):
            a = ORIG[25][16 + dy:44 - dy, 430 + dx:700 - 0].astype(float).sum(axis=2) / 3
            r = full[0:a.shape[0], 0:a.shape[1]]
            r = r - r.mean(); a = a - a.mean()
            c = float((r * a).mean())
            if c > best[2]:
                best = (dy, dx, c)
    return best[0], best[1]

PY_, PX_ = lattice_period()
print("lattice period dy,dx =", PY_, PX_)

BGMAP = {}
CNT = {}
OFF = {}
for band in BANDS:
    bg, cnt, off = band_bg(band)
    BGMAP[band], CNT[band], OFF[band] = bg, cnt, off

def stage2_fill(band, target_img_arr):
    """fill low-donor pixels of the GLOBAL bg via phase-shifted cloning (scalar loop)"""
    y0, x0 = OFF[band]
    bg = BGMAP[band]; cnt = CNT[band]
    low = np.argwhere(cnt < min(cnt.min() + 1, 6))
    fixed = 0
    for (yy, xx) in low:
        gx, gy = x0 + xx, y0 + yy
        vals = []
        for dy in (0, PY_, -PY_, 2 * PY_, -2 * PY_):
            for dx in (0, PX_, -PX_, 2 * PX_, -2 * PX_):
                if dy == 0 and dx == 0:
                    continue
                sy, sx = gy + dy, gx + dx
                if not (BANDS[band][0] <= sy < BANDS[band][1] and BANDS[band][2] <= sx < BANDS[band][3]):
                    continue
                ly, lx = sy - y0, sx - x0
                for P in range(1, 44):
                    if not DARK[P][sy, sx]:
                        vals.append(ORIG[P][sy, sx])
                if len(vals) >= 6:
                    break
            if len(vals) >= 6:
                break
        if vals:
            bg[yy, xx] = np.median(np.array(vals), axis=0)
            fixed += 1
    return fixed

for band in BANDS:
    f = stage2_fill(band, None)
    print(band, "stage2 fixed px:", f)

# ---------------- per-page text masks & patch ----------------
def stroke_text(d, xy, s, font, fill, halo=(252, 250, 244)):
    x, y = xy
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            if dx or dy:
                d.text((x + dx, y + dy), s, font=font, fill=halo)
    d.text((x, y), s, font=font, fill=fill)

def fit(d, s, fontpath, maxw, start, floor=12):
    for size in range(start, floor - 1, -1):
        f = ImageFont.truetype(fontpath, size)
        bb = d.textbbox((0, 0), s, font=f)
        if bb[2] - bb[0] <= maxw:
            return f, bb
    return f, bb

def wrap(d, text, font, maxw):
    lines, cur = [], ""
    for ch in text:
        t = cur + ch
        if d.textlength(t, font=font) > maxw and cur:
            lines.append(cur); cur = ch
        else:
            cur = t
    if cur: lines.append(cur)
    return lines

JP_LINES = {1:5,2:11,3:6,4:6,5:8,6:7,7:7,8:8,9:7,10:6,11:7,12:9,13:7,14:7,15:9,
            16:7,17:5,18:8,19:4,20:10,21:7,22:6,23:7,24:7,25:4,26:6,27:8,28:4,
            29:4,30:8,31:5,32:6,33:6,34:4,35:5,36:5,37:5,38:1,39:3,40:2,41:4,
            42:3,43:6}

for i in range(1, 44):
    fn = f"chara{i:02d}.jpg"
    if fn not in DATA:
        continue
    rec = DATA[fn]
    img = ORIG[i].copy()
    imf = im.astype(int) if False else None
    lum = img.astype(int).sum(axis=2) / 3
    pmed = np.median(lum[40:560, 326:716])
    dark = lum < pmed - 26

    # crest pages: hardcoded from visual contact sheet (crest art at x358-408)
    CREST = {1,2,3,4,5,6,7,8,9,10,11,12,21,22,23,24,30,33,34}
    if i in CREST:
        patch_x0 = 414
    else:
        # first glyph-like dark column band (skip colorful items e.g. chara32 pencil)
        strip_dark = dark[44:160, 326:716]
        strip_chroma = (img[44:160, 326:716].max(axis=2).astype(int)
                        - img[44:160, 326:716].min(axis=2).astype(int))
        colcnt = strip_dark.sum(axis=0)
        colchroma = np.zeros(390)
        for c in range(390):
            m_ = strip_dark[:, c]
            if m_.any():
                colchroma[c] = strip_chroma[:, c][m_].mean()
        bands = []
        inb = False
        for c in range(390):
            if colcnt[c] > 3 and not inb:
                s = c; inb = True
            elif colcnt[c] <= 3 and inb:
                if c - s > 3:
                    bands.append((326 + s, 326 + c - 1, colchroma[s:c].mean()))
                inb = False
        if inb:
            bands.append((326 + s, 715, colchroma[s:].mean()))
        glyph_bands = [b for b in bands if b[2] < 45]
        patch_x0 = (glyph_bands[0][0] - 6) if glyph_bands else 328
        patch_x0 = max(328, patch_x0)

    # build patch mask
    patch = np.zeros(img.shape[:2], bool)
    d3 = dilate(dark, 3)
    patch[44:160, :] = d3[44:160, :]          # furigana + name strip
    patch[192:258, 384:716] = d3[192:258, 384:716]   # data fields (was missing!)
    patch[:, :patch_x0] = False
    patch[:44, :] = False; patch[160:192, :] = False

    # para band: up to max(jpb, cnb)
    fi0 = ImageFont.truetype(HEI, 15)
    tmp = ImageDraw.Draw(Image.new("RGB", (8, 8)))
    cn_lines = wrap(tmp, rec["intro"], fi0, 306)
    jpb = 263 + 20 * (JP_LINES[i] - 1) + 18
    cnb = 268 + len(cn_lines) * 21 + 6
    py1 = min(548, max(jpb, cnb))
    patch[256:py1, 386:708] = d3[256:py1, 386:708]

    # apply global bg into patch (per-band)
    for band in BANDS:
        y0, y1, x0, x1 = BANDS[band]
        sel = patch[y0:y1, x0:x1]
        bgv = BGMAP[band][sel]
        ok = ~np.isnan(bgv[:, 0])
        sel_idx = np.nonzero(sel)
        ys2, xs2 = sel_idx[0][ok], sel_idx[1][ok]
        img[y0 + ys2, x0 + xs2] = bgv[ok].astype(np.uint8)

    img = img.astype(np.uint8)
    im = Image.fromarray(img)
    d = ImageDraw.Draw(im)

    # CN name
    name = rec["name"]
    maxw = 698 - patch_x0 if patch_x0 > 340 else 362
    f, bb = fit(d, name, BRUSH, 698 - max(414, patch_x0) if patch_x0 <= 414 else 698 - patch_x0, 56, 24)
    tw, th = bb[2] - bb[0], bb[3] - bb[1]
    stroke_text(d, (698 - tw - bb[0], 108 - th // 2 - bb[1]), name, f, (24, 20, 22))
    # CN fields
    for k, fl in enumerate(rec["fields"][:3]):
        f2, bb2 = fit(d, fl, BRUSH, 315, 18, 12)
        stroke_text(d, (390 - bb2[0], 217 + k * 21 - (bb2[3] - bb2[1]) // 2 - bb2[1]), fl, f2, (105, 100, 95))
    # CN intro
    fi = ImageFont.truetype(HEI, 15)
    for k, ln in enumerate(cn_lines):
        stroke_text(d, (391, 268 + k * 21), ln, fi, (72, 68, 66))

    im.save(OUT / fn, quality=92)
    print(fn, "crest" if i in CREST else "-----", f"patch_x0={patch_x0}", name, f"({len(cn_lines)} lines)")
print("done")
