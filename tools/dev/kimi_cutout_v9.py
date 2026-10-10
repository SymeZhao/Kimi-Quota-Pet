# 抠图 v9（成品）
#   A. 第一轮连通填充（同 v7）
#   B. 组件级细线过滤：非主连通域里"细长/碎小"的直接丢（=月亮描边、悬浮音符），
#      绝不对主轮廓逐像素下刀 -> 头发/发饰边缘不会被啃
#   C. 口袋回填：被描边围住、且离外部背景很近的小块候选背景 -> 判为背景
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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


def components(mask):
    rem = mask.copy(); out = []
    while rem.any():
        idx = np.argwhere(rem)[0]
        s = np.zeros_like(rem); s[idx[0], idx[1]] = True
        c = grow(s, rem); out.append(c); rem &= ~c
    return out


full = Image.open(SRC).convert("RGB")
W, H = full.size
small = full.resize((int(W * SCALE), int(H * SCALE)), Image.LANCZOS)
a = np.asarray(small).astype(np.int16)
Hs, Ws = a.shape[:2]
ring = np.concatenate([a[0, :, :], a[-1, :, :], a[:, 0, :], a[:, -1, :]])
bg = np.median(ring, axis=0)
sad = np.abs(a - bg).sum(axis=2)
cool = a[:, :, 2] - a[:, :, 0]
sat = a.max(axis=2) - a.min(axis=2)
yy, xx = np.mgrid[0:Hs, 0:Ws]

cand = sad <= 45
cand |= (sad <= 125) & (cool >= 12)
cand |= (yy >= 0.88 * Hs) & (sad <= 100)
cand |= (xx >= 0.72 * Ws) & (yy >= 0.60 * Hs) & (sad <= 100)
cand &= ~(((xx >= 0.42 * Ws) & (yy >= 0.03 * Hs) & (yy <= 0.17 * Hs)) & (sat >= 14))   # 彩虹保护

seed = np.zeros_like(cand)
seed[0, :] = seed[-1, :] = seed[:, 0] = seed[:, -1] = True
bgm = grow(seed, cand)
print("A 第一轮填充：背景 %.1f%%" % (bgm.mean() * 100))

# ---- B. 组件级细线过滤 ----
op = ~bgm
comps = components(op)
comps.sort(key=lambda c: -c.sum())
main = comps[0]
near_main = dilate(main, 4)
keep = main.copy()
dropped_thin = dropped_small = kept_extra = 0
for c in comps[1:]:
    ys, xs = np.where(c)
    area = int(c.sum())
    bw, bh = int(xs.max() - xs.min()) + 1, int(ys.max() - ys.min()) + 1
    mean_w = area / max(bw, bh)
    if (c & near_main).any() and mean_w >= 6:
        keep |= c; kept_extra += 1                 # 贴着主体的紧凑碎块：垂挂的 K 挂饰等
    elif mean_w < 6:
        dropped_thin += 1                          # 细长 = 月亮描边 / 游离音符
    else:
        dropped_small += 1
print("B 主域 %.1f%%；保留贴合碎块 %d；丢弃细长 %d、零散 %d（共 %d 个连通域）"
      % (main.mean() * 100, kept_extra, dropped_thin, dropped_small, len(comps)))

# ---- C. 口袋回填 ----
enc = cand & ~keep
enc_comps = components(enc)
filled = 0
near_out = dilate(bgm, 8)
for c in enc_comps:
    area = int(c.sum())
    if area < 60000 and (c & near_out).any() and area > 40:
        keep &= ~c                                  # 判为背景 -> 从主体里去掉
        filled += 1
print("C 口袋回填：%d 块" % filled)

# ---- 去白边（只削轮廓内侧 3px 内的浅色像素）----
mf = np.asarray(Image.fromarray((keep * 255).astype(np.uint8), "L").resize((W, H), Image.LANCZOS)) > 128
af = np.asarray(full).astype(np.int16)
sad_full = np.abs(af - bg).sum(axis=2)
fringe = (mf & ~erode(mf, 3)) & (sad_full <= 140)
mf2 = mf & ~fringe
print("去白边：%d px（占不透明 %.2f%%）" % (fringe.sum(), 100.0 * fringe.sum() / max(1, mf.sum())))

alpha = Image.fromarray((mf2 * 255).astype(np.uint8), "L").filter(ImageFilter.GaussianBlur(1.4))
cut = full.convert("RGBA"); cut.putalpha(alpha)
side = max(W, H)
sq = Image.new("RGBA", (side, side), (0, 0, 0, 0))
sq.paste(cut, ((side - W) // 2, (side - H) // 2), cut)
sq.save(os.path.join(ART, "kimi-pet.png"))
cut.save(os.path.join(ART, "kimi-pet-cutout.png"))


def compose(bgv, sprite, size, label=None):
    s = sprite.copy(); s.thumbnail((size, size), Image.LANCZOS)
    canvas = bgv.copy() if isinstance(bgv, Image.Image) else Image.new("RGB", (size, size), bgv)
    canvas.paste(s, ((size - s.width) // 2, size - s.height), s)
    if label:
        d = ImageDraw.Draw(canvas); d.rectangle([0, 0, 150, 16], fill=(0, 0, 0))
        d.text((3, 3), label, fill=(255, 255, 255), font=ImageFont.load_default())
    return canvas


def checker(size, box=16):
    img = Image.new("RGB", (size, size), (255, 255, 255)); d = ImageDraw.Draw(img)
    for y in range(0, size, box):
        for x in range(0, size, box):
            if ((x // box) + (y // box)) % 2:
                d.rectangle([x, y, x + box - 1, y + box - 1], fill=(205, 205, 205))
    return img


compose(checker(340), sq, 340).save(os.path.join(OUT, "v9_340_checker.png"))
compose((18, 22, 38), sq, 340, "v9 @340").save(os.path.join(OUT, "v9_340_dark.png"))
compose(checker(624), sq, 624).save(os.path.join(OUT, "v9_624_checker.png"))
compose((18, 22, 38), sq, 624, "v9 @624").save(os.path.join(OUT, "v9_624_dark.png"))
z = sq.crop((int(side * 0.10), int(side * 0.02), int(side * 0.95), int(side * 0.40)))
zb = Image.new("RGB", z.size, (18, 22, 38)); zb.paste(z, (0, 0), z)
zb.save(os.path.join(OUT, "v9_head_zoom.png"))
for name, box in {"left_mid": (0, 380, 300, 700), "moon_upper": (0, 0, 420, 420)}.items():
    o = full.crop(box).resize(((box[2] - box[0]) * 2, (box[3] - box[1]) * 2), Image.LANCZOS)
    c = cut.crop(box); cb = Image.new("RGB", c.size, (18, 22, 38)); cb.paste(c, (0, 0), c)
    cb = cb.resize(o.size, Image.LANCZOS)
    sheet = Image.new("RGB", (o.width * 2 + 12, o.height), (60, 60, 60))
    sheet.paste(o, (0, 0)); sheet.paste(cb, (o.width + 12, 0))
    sheet.save(os.path.join(OUT, "v9_zoom_%s.png" % name))
print("成品 -> kimi-pet.png (%dx%d) / kimi-pet-cutout.png" % (side, side))
