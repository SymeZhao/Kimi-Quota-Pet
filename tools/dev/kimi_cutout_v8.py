# 抠图 v8：放宽冷色细线清除网 + 两轮"清除→重跑连通填充"
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
for i in range(2):
    opaque = ~bgm
    near_bg = dilate(bgm, 2)
    thin_cool = near_bg & (cool >= 5) & (sad >= 55)         # 贴近背景的冷色细线（月亮描边）
    # 只保留"细"的：两端都能在 2px 内摸到背景
    thin = thin_cool & dilate(bgm, 2)
    newcand = cand | thin
    bgm2 = grow(seed, newcand)
    print("第 %d 轮：清除冷色细线 %d px，背景 %.1f%% -> %.1f%%" % (i + 1, thin.sum(), bgm.mean() * 100, bgm2.mean() * 100))
    if bgm2.sum() == bgm.sum():
        break
    bgm = bgm2

opaque = ~bgm
remaining = opaque.copy()
comps = []
while remaining.any():
    idx = np.argwhere(remaining)[0]
    s = np.zeros_like(remaining); s[idx[0], idx[1]] = True
    c = grow(s, remaining); comps.append(c); remaining &= ~c
comps.sort(key=lambda c: -c.sum())
main = comps[0]
near3 = dilate(main, 3)
keep = main.copy(); kept = 0; dropped = []
for c in comps[1:]:
    if c.sum() >= 800 or (c & near3).any():
        keep |= c; kept += 1
    else:
        ys, xs = np.where(c); dropped.append((int(c.sum()), int(xs.min()), int(ys.min())))
print("连通域 %d；主域 %.1f%%；保留附加 %d；丢弃碎屑 %d %s" % (len(comps), main.mean() * 100, kept, len(dropped), dropped[:6]))

mf = np.asarray(Image.fromarray((keep * 255).astype(np.uint8), "L").resize((W, H), Image.LANCZOS)) > 128
af = np.asarray(full).astype(np.int16)
sad_full = np.abs(af - bg).sum(axis=2)
fringe = (mf & ~erode(mf, 3)) & (sad_full <= 140)
mf2 = mf & ~fringe
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


compose(checker(340), sq, 340).save(os.path.join(OUT, "v8_340_checker.png"))
compose((18, 22, 38), sq, 340, "v8 @340").save(os.path.join(OUT, "v8_340_dark.png"))
compose(checker(624), sq, 624).save(os.path.join(OUT, "v8_624_checker.png"))
compose((18, 22, 38), sq, 624, "v8 @624").save(os.path.join(OUT, "v8_624_dark.png"))
z = sq.crop((int(side * 0.10), int(side * 0.02), int(side * 0.95), int(side * 0.40)))
zb = Image.new("RGB", z.size, (18, 22, 38)); zb.paste(z, (0, 0), z)
zb.save(os.path.join(OUT, "v8_head_zoom.png"))

orig = full
cutc = cut
for name, box in {"left_mid": (0, 380, 300, 700), "moon_upper": (0, 0, 420, 420)}.items():
    o = orig.crop(box).resize(((box[2] - box[0]) * 2, (box[3] - box[1]) * 2), Image.LANCZOS)
    c = cutc.crop(box); cb = Image.new("RGB", c.size, (18, 22, 38)); cb.paste(c, (0, 0), c)
    cb = cb.resize(o.size, Image.LANCZOS)
    sheet = Image.new("RGB", (o.width * 2 + 12, o.height), (60, 60, 60))
    sheet.paste(o, (0, 0)); sheet.paste(cb, (o.width + 12, 0))
    sheet.save(os.path.join(OUT, "v8_zoom_%s.png" % name))
print("成品 -> kimi-pet.png / kimi-pet-cutout.png（含 v8 预览）")
