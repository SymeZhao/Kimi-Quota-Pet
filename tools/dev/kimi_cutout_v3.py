# 抠图 v3：只用"模糊 + 洪泛 + 膨胀 + 羽化"，不做事后阈值还原（v2 的 tol2 就是罪魁）
# 目的：验证更高容差能否一并吃掉月亮/影子/乐谱纸，同时不动白裙白发
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageFont

ART = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art"
OUT = os.path.join(ART, "preview")
SRC = os.path.join(ART, "kimi-full.jpg")


def cutout(path, tol, blur=2.0, grow=3, feather=1.2, pad=12):
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    ring = np.concatenate([a[0, :, :], a[-1, :, :], a[:, 0, :], a[:, -1, :]])
    bgc = tuple(int(c) for c in np.median(ring, axis=0))
    soft = im.filter(ImageFilter.GaussianBlur(blur))
    work = ImageOps.expand(soft, border=pad, fill=bgc)
    ImageDraw.floodfill(work, (0, 0), (255, 0, 255), thresh=tol)
    w = np.asarray(work)
    bgmask = ((w[:, :, 0] > 250) & (w[:, :, 1] < 5) & (w[:, :, 2] > 250))[pad:-pad, pad:-pad]
    m = Image.fromarray((bgmask * 255).astype(np.uint8), "L")
    if grow > 0:
        m = m.filter(ImageFilter.MaxFilter(grow * 2 + 1))
    if feather > 0:
        m = m.filter(ImageFilter.GaussianBlur(feather))
    alpha = ImageOps.invert(m)
    out = im.convert("RGBA")
    out.putalpha(alpha)
    return out, bgmask


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
res = []
for tol in (35, 50, 65, 85):
    img, bgmask = cutout(SRC, tol)
    res.append((tol, img))
    print("tol=%-3d 背景占比 %.1f%%" % (tol, bgmask.mean() * 100))

row = Image.new("RGB", (size * len(res), size), (18, 22, 38))
for i, (tol, img) in enumerate(res):
    row.paste(compose((18, 22, 38), img, size, "v3 tol=%d" % tol), (i * size, 0))
row.save(os.path.join(OUT, "compare_v3.png"))

# 实际显示尺寸检查（340px）+ 头部 2 倍放大（看白发有没有被咬出洞）
for tol, img in res[1:3]:
    compose(checker(340), img, 340).save(os.path.join(OUT, "v3_%d_340_checker.png" % tol))
    compose((18, 22, 38), img, 340, "v3 %d @340" % tol).save(os.path.join(OUT, "v3_%d_340_dark.png" % tol))
    head = img.crop((0, 0, 960, 620)).resize((720, 465), Image.LANCZOS)
    bg = Image.new("RGB", head.size, (18, 22, 38))
    bg.paste(head, (0, 0), head)
    bg.save(os.path.join(OUT, "v3_%d_head_zoom.png" % tol))

for f in sorted(os.listdir(OUT)):
    if f.startswith("v3_"):
        print("   %-26s %7.1f KB" % (f, os.path.getsize(os.path.join(OUT, f)) / 1024))
