# 抠图 v4：自定义判据 + 连通填充（不再用 PIL 的 floodfill）
# 关键判据（PIL 的 tol 是"通道差之和"，这里统一用 SAD=sum|ΔRGB|）：
#   基础背景 : SAD <= 45                        （平坦背景 + JPEG 噪点）
#   冷调浅色 : SAD <= 125 且 (B-R) >= 12         （月亮及其辉光；她头发 SAD≈166，被排除）
#   底部道具 : y >= 0.88H 且 SAD <= 100          （脚下阴影 / 底部乐谱纸）
#   右下纸片 : x >= 0.72W 且 y >= 0.60H 且 SAD <= 100
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ART = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art"
OUT = os.path.join(ART, "preview")
SRC = os.path.join(ART, "kimi-full.jpg")
SCALE = 0.5


def dilate(m):
    o = m.copy()
    o[1:, :] |= m[:-1, :]
    o[:-1, :] |= m[1:, :]
    o[:, 1:] |= m[:, :-1]
    o[:, :-1] |= m[:, 1:]
    o[1:, 1:] |= m[:-1, :-1]
    o[:-1, :-1] |= m[1:, 1:]
    o[1:, :-1] |= m[:-1, 1:]
    o[:-1, 1:] |= m[1:, :-1]
    return o


def build_mask(small_rgb, base=45, cool_sad=125, cool_min=12, bottom_sad=100, paper_sad=100,
               paper_x=0.72, paper_y=0.60, bottom_y=0.88):
    a = np.asarray(small_rgb).astype(np.int16)
    H, W = a.shape[:2]
    ring = np.concatenate([a[0, :, :], a[-1, :, :], a[:, 0, :], a[:, -1, :]])
    bg = np.median(ring, axis=0)
    sad = np.abs(a - bg).sum(axis=2)
    cool = a[:, :, 2] - a[:, :, 0]
    yy, xx = np.mgrid[0:H, 0:W]

    cand = sad <= base
    cand |= (sad <= cool_sad) & (cool >= cool_min)                       # 月亮
    cand |= (yy >= bottom_y * H) & (sad <= bottom_sad)                   # 影子 / 底部纸
    cand |= (xx >= paper_x * W) & (yy >= paper_y * H) & (sad <= paper_sad)  # 右下纸片

    seed = np.zeros_like(cand)
    seed[0, :] = seed[-1, :] = seed[:, 0] = seed[:, -1] = True
    seed &= cand
    for _ in range(4000):
        new = dilate(seed) & cand
        if new.sum() == seed.sum():
            break
        seed = new
    return seed, cand, bg


full = Image.open(SRC).convert("RGB")
W, H = full.size
small = full.resize((int(W * SCALE), int(H * SCALE)), Image.LANCZOS)
bgmask_s, cand, bg = build_mask(small)
print("底色 =", bg.astype(int))
print("候选像素 %.1f%%，其中与边界连通 %.1f%%" % (cand.mean() * 100, bgmask_s.mean() * 100))

# 上采样掩膜 -> 全分辨率 alpha（再做一次膨胀补 JPEG 边界带 + 羽化）
m = Image.fromarray((bgmask_s * 255).astype(np.uint8), "L").resize((W, H), Image.LANCZOS)
m = m.point(lambda v: 255 if v > 128 else 0)
m = m.filter(ImageFilter.MaxFilter(9))          # 全分辨率下补 4px 边界带
m = m.filter(ImageFilter.GaussianBlur(1.6))
alpha = ImageOps.invert(m)
cut = full.convert("RGBA")
cut.putalpha(alpha)
cut.save(os.path.join(OUT, "v4_full_rgba.png"))


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


compose(checker(340), cut, 340).save(os.path.join(OUT, "v4_340_checker.png"))
compose((18, 22, 38), cut, 340, "v4 @340").save(os.path.join(OUT, "v4_340_dark.png"))
compose(checker(624), cut, 624).save(os.path.join(OUT, "v4_624_checker.png"))
# 诊断：原图上把"判定为背景"的区域涂黑，直观看剩下什么
diag = np.asarray(full).copy()
bgfull = np.asarray(ImageOps.invert(alpha)) > 128
diag[bgfull] = (diag[bgfull] * 0.25).astype(np.uint8)
Image.fromarray(diag).resize((480, 860), Image.LANCZOS).save(os.path.join(OUT, "v4_diag_masked.png"))

for f in sorted(os.listdir(OUT)):
    if f.startswith("v4_"):
        print("   %-26s %7.1f KB" % (f, os.path.getsize(os.path.join(OUT, f)) / 1024))
