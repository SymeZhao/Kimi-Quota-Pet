# Kimi 桌宠立绘体检 + 抠图可行性试验
# 用捆绑 Python（Pillow 12 / numpy 2）运行：
#   python kimi_art_check.py
import os, time
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageFont

ART = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art"
OUT = os.path.join(ART, "preview")
os.makedirs(OUT, exist_ok=True)

FILES = {
    "full": "kimi-full.jpg",
    "face": "kimi-face.jpg",
    "icon": "kimi-icon.webp",
}


def info(path):
    im = Image.open(path)
    im.load()
    print("-" * 68)
    print(os.path.basename(path))
    print("   格式/模式 : %s / %s -> %s" % (im.format, im.mode, im.size))
    print("   宽高比   : %.3f (1:%.2f)" % (im.size[0] / im.size[1], im.size[1] / im.size[0]))
    print("   有 alpha : %s" % ("是" if im.mode in ("RGBA", "LA") or "transparency" in im.info else "否"))
    rgb = im.convert("RGB")
    a = np.asarray(rgb).astype(np.int16)
    ring = np.concatenate([a[0, :, :], a[-1, :, :], a[:, 0, :], a[:, -1, :]])
    med = np.median(ring, axis=0)
    std = ring.std(axis=0)
    if im.mode == "RGBA":
        alpha = np.asarray(im.convert("RGBA"))[:, :, 3]
        print("   透明像素 : %.1f%%" % (100.0 * (alpha < 8).mean()))
    print("   边缘底色 : RGB(%d,%d,%d)  std=(%.1f,%.1f,%.1f)  <- 越均匀越好抠"
          % (med[0], med[1], med[2], std[0], std[1], std[2]))
    return im


def cutout(path, thresh, shrink=1, feather=1.1, pad=8):
    t0 = time.time()
    im = Image.open(path).convert("RGB")
    a = np.asarray(im).astype(np.int16)
    ring = np.concatenate([a[0, :, :], a[-1, :, :], a[:, 0, :], a[:, -1, :]])
    bg = tuple(int(c) for c in np.median(ring, axis=0))
    work = ImageOps.expand(im, border=pad, fill=bg)
    ImageDraw.floodfill(work, (0, 0), (255, 0, 255), thresh=thresh)
    w = np.asarray(work)
    magic = (w[:, :, 0] > 250) & (w[:, :, 1] < 5) & (w[:, :, 2] > 250)
    inside = ~magic
    inside = inside[pad:-pad, pad:-pad]
    alpha = Image.fromarray((inside * 255).astype(np.uint8), "L")
    if shrink > 0:
        alpha = alpha.filter(ImageFilter.MinFilter(shrink * 2 + 1))
    if feather > 0:
        alpha = alpha.filter(ImageFilter.GaussianBlur(feather))
    out = im.convert("RGBA")
    out.putalpha(alpha)
    dt = time.time() - t0
    arr = np.asarray(out)
    op = arr[:, :, 3] > 8
    ys, xs = np.where(op)
    bbox = (xs.min(), ys.min(), xs.max(), ys.max()) if len(xs) else (0, 0, 0, 0)
    print("   tol=%-3d shrink=%d : 去背 %.1f%%, 主体 bbox=%s, 用时 %.1fs"
          % (thresh, shrink, 100.0 * (1 - op.mean()), bbox, dt))
    return out, bbox


def checker(size, box=16):
    w, h = size
    img = Image.new("RGB", (w, h), (255, 255, 255))
    d = ImageDraw.Draw(img)
    for y in range(0, h, box):
        for x in range(0, w, box):
            if ((x // box) + (y // box)) % 2:
                d.rectangle([x, y, x + box - 1, y + box - 1], fill=(205, 205, 205))
    return img


def compose(bg, sprite, size, label=None):
    s = sprite.copy()
    s.thumbnail((size, size), Image.LANCZOS)
    if isinstance(bg, tuple):
        canvas = Image.new("RGB", (size, size), bg)
    else:
        canvas = bg.copy()
    canvas.paste(s, ((size - s.width) // 2, size - s.height), s)
    if label:
        d = ImageDraw.Draw(canvas)
        d.rectangle([0, 0, 116, 16], fill=(0, 0, 0))
        d.text((3, 3), label, fill=(255, 255, 255), font=ImageFont.load_default())
    return canvas


full = info(os.path.join(ART, FILES["full"]))
face = info(os.path.join(ART, FILES["face"]))
icon = info(os.path.join(ART, FILES["icon"]))

print("=" * 68)
print("抠图试验（边界洪泛填充 + 收缩 + 羽化）：")
best = None
variants = []
for tol in (18, 32, 50):
    img, bbox = cutout(os.path.join(ART, FILES["full"]), tol)
    variants.append((tol, img, bbox))
    op = np.asarray(img)[:, :, 3] > 8
    cov = op.mean()
    if best is None or abs(cov - 0.42) < abs(best[3] - 0.42):
        best = (tol, img, bbox, cov)

# 三档并排，深色底最容易看出白边残留
size = 560
row = Image.new("RGB", (size * len(variants), size), (18, 22, 38))
for i, (tol, img, bbox) in enumerate(variants):
    row.paste(compose((18, 22, 38), img, size, "tol=%d" % tol), (i * size, 0))
row.save(os.path.join(OUT, "compare_tolerance.png"))

# 最佳档：真实尺寸（340px）呈现，棋盘格看透明、深色看白边
tok, timg, tbox, tcov = best
checker_bg = checker((340, 340))
compose(checker_bg, timg, 340).save(os.path.join(OUT, "cutout_340_checker.png"))
compose((18, 22, 38), timg, 340, "340px dark").save(os.path.join(OUT, "cutout_340_dark.png"))
timg.save(os.path.join(OUT, "cutout_full_rgba.png"))
print("=" * 68)
print("最佳档 tol=%d（主体占比 %.1f%%）" % (tok, 100 * tcov))
print("产出：")
for f in sorted(os.listdir(OUT)):
    print("   %-28s %6.1f KB" % (f, os.path.getsize(os.path.join(OUT, f)) / 1024))

# 图 3 做托盘图标：圆角矩形遮罩
ic = icon.convert("RGBA")
side = min(ic.size)
ic = ic.crop(((ic.width - side) // 2, (ic.height - side) // 2,
              (ic.width + side) // 2, (ic.height + side) // 2)).resize((256, 256), Image.LANCZOS)
mask = Image.new("L", (256, 256), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, 255, 255], radius=56, fill=255)
ic.putalpha(mask)
ic.save(os.path.join(OUT, "tray_icon_256.png"))
print("   %-28s %6.1f KB" % ("tray_icon_256.png", os.path.getsize(os.path.join(OUT, "tray_icon_256.png")) / 1024))
