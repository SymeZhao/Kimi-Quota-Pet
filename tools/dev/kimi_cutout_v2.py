# Kimi 桌宠立绘抠图 v2：模糊去噪 -> 洪泛 -> 膨胀回补 -> 羽化
# 目标：把月亮、脚下阴影、乐谱纸等"近白背景道具"一起清掉，同时不吃掉白裙/白发
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageFont

ART = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art"
OUT = os.path.join(ART, "preview")
SRC = os.path.join(ART, "kimi-full.jpg")


def cutout_v2(path, tol, blur=2.0, grow=3, tol2=26, feather=1.2, pad=10):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    ring = np.concatenate([a[0, :, :], a[-1, :, :], a[:, 0, :], a[:, -1, :]])
    bg = np.median(ring, axis=0)
    bgc = tuple(int(c) for c in bg)

    soft = im.filter(ImageFilter.GaussianBlur(blur))          # 消掉 JPEG 噪点墙
    work = ImageOps.expand(soft, border=pad, fill=bgc)
    ImageDraw.floodfill(work, (0, 0), (255, 0, 255), thresh=tol)
    w = np.asarray(work)
    bgmask = ((w[:, :, 0] > 250) & (w[:, :, 1] < 5) & (w[:, :, 2] > 250))[pad:-pad, pad:-pad]

    m = Image.fromarray((bgmask * 255).astype(np.uint8), "L")
    if grow > 0:
        m = m.filter(ImageFilter.MaxFilter(grow * 2 + 1))     # 膨胀，覆盖边界噪声带
    grown = np.asarray(m) > 128

    # 膨胀区域里，只有"确实接近底色"的像素才算背景（否则是角色的白边，要留住）
    dist = np.sqrt(((a - bg) ** 2).sum(axis=2))
    final_bg = grown & (dist < tol2)
    alpha = Image.fromarray(((~final_bg) * 255).astype(np.uint8), "L")
    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return out, final_bg


def checker(size, box=16):
    img = Image.new("RGB", (size, size), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, size, box):
        for x in range(0, size, box):
            if ((x // box) + (y // box)) % 2:
                d.rectangle([x, y, x + box - 1, y + box - 1], fill=(205, 205, 205))
    return img


def compose(bg, sprite, size, label=None):
    s = sprite.copy()
    s.thumbnail((size, size), Image.LANCZOS)
    canvas = bg.copy() if isinstance(bg, Image.Image) else Image.new("RGB", (size, size), bg)
    canvas.paste(s, ((size - s.width) // 2, size - s.height), s)
    if label:
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, 0, 150, 16], fill=(0, 0, 0))
        d.text((3, 3), label, fill=(255, 255, 255), font=ImageFont.load_default())
    return canvas


size = 560
variants = []
for tol in (25, 35, 45):
    img, bgmask = cutout_v2(SRC, tol)
    removed = bgmask.mean() * 100
    print("tol=%-3d : 判定为背景 %.1f%%" % (tol, removed))
    variants.append((tol, img))

row = Image.new("RGB", (size * len(variants), size), (18, 22, 38))
for i, (tol, img) in enumerate(variants):
    row.paste(compose((18, 22, 38), img, size, "v2 tol=%d" % tol), (i * size, 0))
row.save(os.path.join(OUT, "compare_v2.png"))

best_tol, best_img = variants[1]
compose(checker(340), best_img, 340).save(os.path.join(OUT, "v2_340_checker.png"))
compose((18, 22, 38), best_img, 340, "v2 340 dark").save(os.path.join(OUT, "v2_340_dark.png"))
best_img.save(os.path.join(OUT, "v2_full_rgba.png"))
print("best tol =", best_tol)
for f in ("compare_v2.png", "v2_340_checker.png", "v2_340_dark.png", "v2_full_rgba.png"):
    print("   %-24s %7.1f KB" % (f, os.path.getsize(os.path.join(OUT, f)) / 1024))
