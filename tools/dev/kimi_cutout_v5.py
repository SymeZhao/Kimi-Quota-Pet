# 抠图 v5：v4 判据 + 连通域清理（去掉悬浮碎屑）+ 彩虹保护
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ART = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art"
OUT = os.path.join(ART, "preview")
SRC = os.path.join(ART, "kimi-full.jpg")
SCALE = 0.5


def dilate(m, r=1):
    o = m.copy()
    for _ in range(r):
        p = o.copy()
        p[1:, :] |= o[:-1, :]; p[:-1, :] |= o[1:, :]
        p[:, 1:] |= o[:, :-1]; p[:, :-1] |= o[:, 1:]
        p[1:, 1:] |= o[:-1, :-1]; p[:-1, :-1] |= o[1:, 1:]
        p[1:, :-1] |= o[:-1, 1:]; p[:-1, 1:] |= o[1:, :-1]
        o = p
    return o


def grow(seed, allowed):
    cur = seed & allowed
    while True:
        nxt = dilate(cur) & allowed
        if nxt.sum() == cur.sum():
            return cur
        cur = nxt


def build_bg_mask(small_rgb):
    a = np.asarray(small_rgb).astype(np.int16)
    H, W = a.shape[:2]
    ring = np.concatenate([a[0, :, :], a[-1, :, :], a[:, 0, :], a[:, -1, :]])
    bg = np.median(ring, axis=0)
    sad = np.abs(a - bg).sum(axis=2)
    cool = a[:, :, 2] - a[:, :, 0]
    sat = a.max(axis=2) - a.min(axis=2)
    yy, xx = np.mgrid[0:H, 0:W]

    cand = sad <= 45
    cand |= (sad <= 125) & (cool >= 12)
    cand |= (yy >= 0.88 * H) & (sad <= 100)
    cand |= (xx >= 0.72 * W) & (yy >= 0.60 * H) & (sad <= 100)

    seed = np.zeros_like(cand)
    seed[0, :] = seed[-1, :] = seed[:, 0] = seed[:, -1] = True
    bgmask = grow(seed, cand)

    # 彩虹保护：她眼睛射出的彩虹带在 (0.44~1.0)W x (0.05~0.15)H 内，饱和度高
    rect = (xx >= 0.44 * W) & (xx <= 1.0 * W) & (yy >= 0.04 * H) & (yy <= 0.16 * H)
    protect = rect & (sat >= 16)
    bgmask &= ~protect
    return bgmask, bg, protect.sum()


full = Image.open(SRC).convert("RGB")
W, H = full.size
small = full.resize((int(W * SCALE), int(H * SCALE)), Image.LANCZOS)
bgmask, bg, prot = build_bg_mask(small)
print("底色 =", bg.astype(int), " 彩虹保护像素 =", prot)
opaque = ~bgmask

# ---- 连通域清理：只保留主连通域，以及贴近主域的碎片（垂挂的 K 挂饰）----
remaining = opaque.copy()
comps = []
while remaining.any():
    idx = np.argwhere(remaining)[0]
    seed = np.zeros_like(remaining)
    seed[idx[0], idx[1]] = True
    comp = grow(seed, remaining)
    comps.append(comp)
    remaining &= ~comp
comps.sort(key=lambda c: -c.sum())
main = comps[0]
near = dilate(main, 6)
keep = main.copy()
dropped = []
for c in comps[1:]:
    area = int(c.sum())
    if area >= 300 or (c & near).any():
        keep |= c
    else:
        ys, xs = np.where(c)
        dropped.append((area, int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())))
print("连通域 %d 个；主域 %.1f%%；保留 %d 个；丢弃 %d 个碎屑"
      % (len(comps), main.mean() * 100, len([c for c in comps[1:] if (c.sum() >= 300 or (c & near).any())]), len(dropped)))
for area, x0, y0, x1, y1 in dropped[:12]:
    print("   丢弃 area=%d  bbox=(%d,%d)-(%d,%d)" % (area, x0, y0, x1, y1))

alpha_s = Image.fromarray((keep * 255).astype(np.uint8), "L")
m = alpha_s.resize((W, H), Image.LANCZOS).point(lambda v: 255 if v > 128 else 0)
m = m.filter(ImageFilter.MinFilter(9))       # 收缩 4px：去掉和白底混出来的白边
m = m.filter(ImageFilter.GaussianBlur(1.5))
cut = full.convert("RGBA")
cut.putalpha(m)
cut.save(os.path.join(ART, "kimi-pet-cutout.png"))


def checker(size, box=16):
    img = Image.new("RGB", (size, size), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, size, box):
        for x in range(0, size, box):
            if ((x // box) + (y // box)) % 2:
                d.rectangle([x, y, x + box - 1, y + box - 1], fill=(205, 205, 205))
    return img


def compose(bgv, sprite, size, label=None):
    s = sprite.copy()
    s.thumbnail((size, size), Image.LANCZOS)
    canvas = bgv.copy() if isinstance(bgv, Image.Image) else Image.new("RGB", (size, size), bgv)
    canvas.paste(s, ((size - s.width) // 2, size - s.height), s)
    if label:
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, 0, 150, 16], fill=(0, 0, 0))
        d.text((3, 3), label, fill=(255, 255, 255), font=ImageFont.load_default())
    return canvas


compose((18, 22, 38), cut, 340, "v5 @340").save(os.path.join(OUT, "v5_340_dark.png"))
compose(checker(340), cut, 340).save(os.path.join(OUT, "v5_340_checker.png"))
compose((18, 22, 38), cut, 624, "v5 @624").save(os.path.join(OUT, "v5_624_dark.png"))
compose(checker(624), cut, 624).save(os.path.join(OUT, "v5_624_checker.png"))
head = cut.crop((150, 60, 810, 500))
hb = Image.new("RGB", head.size, (18, 22, 38))
hb.paste(head, (0, 0), head)
hb.save(os.path.join(OUT, "v5_head_zoom.png"))
print("立绘成品 -> %s" % os.path.join(ART, "kimi-pet-cutout.png"))
