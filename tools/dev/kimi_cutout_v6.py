# 抠图 v6（成品版）
#   1) 判据同 v5；彩虹保护加强
#   2) 碎屑清理：只保留主连通域 + 3px 内相邻 + 面积够大的
#   3) 去白边：只削"边界带上且接近底色"的浅色像素（保住长笛/链条这类细深色细节）
#   4) 输出方形画布成品 kimi-pet.png（v3 桌宠的控件是正方形，居中放最稳）
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


def erode(m, r=1):
    return ~dilate(~m, r)


def grow(seed, allowed):
    cur = seed & allowed
    while True:
        nxt = dilate(cur) & allowed
        if nxt.sum() == cur.sum():
            return cur
        cur = nxt


def build(small):
    a = np.asarray(small).astype(np.int16)
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
    rect = (xx >= 0.42 * W) & (yy >= 0.03 * H) & (yy <= 0.17 * H) & (xx <= 1.0 * W)
    bgmask &= ~(rect & (sat >= 14))
    return bgmask, bg


full = Image.open(SRC).convert("RGB")
W, H = full.size
small = full.resize((int(W * SCALE), int(H * SCALE)), Image.LANCZOS)
bgmask, bg = build(small)
opaque = ~bgmask

remaining = opaque.copy()
comps = []
while remaining.any():
    idx = np.argwhere(remaining)[0]
    seed = np.zeros_like(remaining); seed[idx[0], idx[1]] = True
    c = grow(seed, remaining)
    comps.append(c); remaining &= ~c
comps.sort(key=lambda c: -c.sum())
main = comps[0]
near3 = dilate(main, 3)
keep = main.copy()
kept_extra = dropped = 0
drop_list = []
for c in comps[1:]:
    area = int(c.sum())
    if area >= 800 or (c & near3).any():
        keep |= c; kept_extra += 1
    else:
        dropped += 1
        ys, xs = np.where(c)
        drop_list.append((area, int(xs.min()), int(ys.min())))
print("连通域 %d；主域占比 %.1f%%；保留附加 %d；丢弃碎屑 %d" % (len(comps), main.mean() * 100, kept_extra, dropped))
print("典型丢弃碎片（半分辨率坐标）:", drop_list[:10])

mask = Image.fromarray((keep * 255).astype(np.uint8), "L").resize((W, H), Image.LANCZOS) \
            .point(lambda v: 255 if v > 128 else 0)
mf = np.asarray(mask) > 128
# 只削浅色白边：边界带 3px 内、且颜色接近底色的像素
a = np.asarray(full).astype(np.int16)
sad_full = np.abs(a - bg).sum(axis=2)
band = mf & ~erode(mf, 3)
fringe = band & (sad_full <= 140)
mf2 = mf & ~fringe
print("白边像素削减 %d（占比 %.2f%%）" % (fringe.sum(), 100.0 * fringe.sum() / mf.sum()))
alpha = Image.fromarray((mf2 * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.4))
cut = full.convert("RGBA")
cut.putalpha(alpha)

# 方形画布（控件是正方形；图片按高度缩放，居中放最稳）
side = max(W, H)
square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
square.paste(cut, ((side - W) // 2, (side - H) // 2), cut)
square.save(os.path.join(ART, "kimi-pet.png"))
cut.save(os.path.join(ART, "kimi-pet-cutout.png"))
print("成品 -> kimi-pet.png (%dx%d) / kimi-pet-cutout.png (%dx%d)" % (side, side, W, H))


def checker(size, box=16):
    img = Image.new("RGB", (size, size), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, size, box):
        for x in range(0, size, box):
            if ((x // box) + (y // box)) % 2:
                d.rectangle([x, y, x + box - 1, y + box - 1], fill=(205, 205, 205))
    return img


def compose(bgv, sprite, size, label=None):
    s = sprite.copy(); s.thumbnail((size, size), Image.LANCZOS)
    canvas = bgv.copy() if isinstance(bgv, Image.Image) else Image.new("RGB", (size, size), bgv)
    canvas.paste(s, ((size - s.width) // 2, size - s.height), s)
    if label:
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, 0, 150, 16], fill=(0, 0, 0))
        d.text((3, 3), label, fill=(255, 255, 255), font=ImageFont.load_default())
    return canvas


compose(checker(340), square, 340).save(os.path.join(OUT, "v6_340_checker.png"))
compose((18, 22, 38), square, 340, "v6 @340").save(os.path.join(OUT, "v6_340_dark.png"))
compose(checker(624), square, 624).save(os.path.join(OUT, "v6_624_checker.png"))
compose((18, 22, 38), square, 624, "v6 @624").save(os.path.join(OUT, "v6_624_dark.png"))
z = square.crop((int(side * 0.10), int(side * 0.02), int(side * 0.95), int(side * 0.40)))
zb = Image.new("RGB", z.size, (18, 22, 38)); zb.paste(z, (0, 0), z)
zb.save(os.path.join(OUT, "v6_head_zoom.png"))
print("预览 -> v6_340_checker / v6_340_dark / v6_624_dark / v6_head_zoom")
