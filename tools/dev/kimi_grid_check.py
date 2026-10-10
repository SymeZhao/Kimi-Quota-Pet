# 验收 GPT 生成的 2×2 差分图：测量 + 抠图 + 对齐 + 桌宠实渲预览
import os, math, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps

ART = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art"
SRC_ATT = r"C:\Users\Administrator\.dsh\attachments\v1\objects\63\63cf722593ac8b03127fab80e245bf7809552edf40955ce82656409f741ca9f1"
SRC = os.path.join(ART, "kimi-grid.webp")
OUT = os.path.join(ART, "preview")
os.makedirs(OUT, exist_ok=True)
if os.path.exists(SRC_ATT):
    shutil.copy2(SRC_ATT, SRC)

img = Image.open(SRC).convert("RGB")
W, H = img.size
print("源图 %dx%d" % (W, H))
cw, ch = W // 2, H // 2
names = ["11 常态(左上)", "22 惊喜(右上)", "12 担心(左下)", "21 冷脸(右下)"]


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


cells = []
print("\n%-14s %-22s %-26s %s" % ("面板", "人物外接框", "离画布边缘", "平板"))
for i, name in enumerate(names):
    x0, y0 = (i % 2) * cw, (i // 2) * ch
    cell = img.crop((x0, y0, x0 + cw, y0 + ch))
    a = np.asarray(cell).astype(np.int16)
    # 背景色取四角中位数
    corners = np.stack([a[0, 0], a[0, -1], a[-1, 0], a[-1, -1]]).astype(np.int16)
    bg = np.median(corners, axis=0)
    sad = np.abs(a - bg).sum(axis=2)
    sil = sad > 24
    sil = grow(np.zeros_like(sil) | (sil & np.pad(np.ones((ch - 2, cw - 2), bool), 1) & False) | sil, sil) if False else sil
    ys, xs = np.where(sil)
    bbox = (xs.min(), ys.min(), xs.max(), ys.max())
    margin = min(bbox[0], bbox[1], cw - 1 - bbox[2], ch - 1 - bbox[3])
    # 平板：最暗的一坨矩形
    dark = (a.max(axis=2) < 90)
    best = None
    rem = dark.copy()
    for _ in range(12):
        if not rem.any(): break
        idx = np.argwhere(rem)[0]
        s = np.zeros_like(rem); s[idx[0], idx[1]] = True
        c = grow(s, rem); rem &= ~c
        area = int(c.sum())
        if area < 0.02 * cw * ch: continue
        yy, xx = np.where(c)
        bw, bh = xx.max() - xx.min() + 1, yy.max() - yy.min() + 1
        rect = area / float(bw * bh)
        if rect > 0.55 and area < 0.45 * cw * ch:
            if best is None or area > best[0]:
                best = (area, xx, yy, bw, bh, rect)
    tab = "-"
    if best:
        area, xx, yy, bw, bh, rect = best
        # PCA 求倾角
        pts = np.stack([xx - xx.mean(), yy - yy.mean()])
        cov = np.cov(pts)
        ev, evec = np.linalg.eigh(cov)
        v = evec[:, -1]
        ang = math.degrees(math.atan2(v[1], v[0]))
        if ang > 90: ang -= 180
        if ang < -90: ang += 180
        tab = "bbox=%dx%d 矩形度=%.2f 倾角=%.1f° 占画面=%.0f%%" % (bw, bh, rect, ang, 100.0 * area / (cw * ch))
        cells.append(dict(name=name, cell=cell, bg=bg, sil=sil, bbox=bbox,
                          tab=(xx.min(), yy.min(), xx.max(), yy.max()), ang=ang))
    print("%-14s %-22s %-26s %s" % (name, str(bbox), "最小边距 %dpx" % margin, tab))

# 对齐检查：以平板中心为锚点
if len(cells) == 4:
    cx = [ (c["tab"][0] + c["tab"][2]) / 2 for c in cells]
    cy = [ (c["tab"][1] + c["tab"][3]) / 2 for c in cells]
    print("\n平板中心跨面板偏差: Δx=%.0fpx  Δy=%.0fpx（面板尺寸 %d）" % (max(cx) - min(cx), max(cy) - min(cy), cw))
    bh = [ (c["tab"][3] - c["tab"][1] + 1) for c in cells]
    bw = [ (c["tab"][2] - c["tab"][0] + 1) for c in cells]
    print("平板尺寸跨面板偏差: 宽 %.0fpx 高 %.0fpx" % (max(bw) - min(bw), max(bh) - min(bh)))
    sb = [c["bbox"] for c in cells]
    print("人物外接框跨面板偏差: x %d~%d, y %d~%d" %
          (min(b[0] for b in sb), max(b[0] for b in sb),
           min(b[1] for b in sb), max(b[1] for b in sb)))

# 对齐 + 抠图 + 桌宠实渲
SIDE = 1720
aligned = []
for c in cells:
    a = np.asarray(c["cell"]).astype(np.int16)
    sad = np.abs(a - c["bg"]).sum(axis=2)
    m = (sad > 24).astype(np.uint8) * 255
    mask = Image.fromarray(m, "L").filter(ImageFilter.MinFilter(6)).filter(ImageFilter.GaussianBlur(1.2))
    # 平移对齐：把平板中心挪到统一位置
    dx = int(round((c["tab"][0] + c["tab"][2]) / 2 - (cells[0]["tab"][0] + cells[0]["tab"][2]) / 2))
    dy = int(round((c["tab"][1] + c["tab"][3]) / 2 - (cells[0]["tab"][1] + cells[0]["tab"][3]) / 2))
    rgba = c["cell"].convert("RGBA"); rgba.putalpha(mask)
    canv = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
    canv.paste(rgba, (-dx, -dy), rgba)
    aligned.append(canv)

# 统一缩放到 1720² 方形画布（人物撑满高度）
def to_square(im, side=SIDE):
    arr = np.asarray(im)[:, :, 3] > 8
    ys, xs = np.where(arr)
    box = (xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)
    crop = im.crop(box)
    sc = side / float(crop.height)
    crop = crop.resize((max(1, int(crop.width * sc)), side), Image.LANCZOS)
    canv = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canv.paste(crop, ((side - crop.width) // 2, 0), crop)
    return canv, sc

sq, sc = to_square(aligned[0])
print("\n缩放系数 %.3f（源 %d → %d）" % (sc, aligned[0].height, SIDE))
# 平板四角映射到方形画布
t = cells[0]["tab"]
mx0 = (t[0] + (SIDE - int(aligned[0].width * sc)) / 2 if False else 0)
# 用和 to_square 相同的映射：先裁 bbox，再缩放，再居中
arr0 = np.asarray(aligned[0])[:, :, 3] > 8
ys, xs = np.where(arr0)
bx0, by0 = xs.min(), ys.min()
sq_w = int((xs.max() + 1 - bx0) * sc)
off_x = (SIDE - sq_w) // 2
quad = [(int((t[0] - bx0) * sc) + off_x, int((t[1] - by0) * sc)),
        (int((t[2] - bx0) * sc) + off_x, int((t[1] - by0) * sc)),
        (int((t[2] - bx0) * sc) + off_x, int((t[3] - by0) * sc)),
        (int((t[0] - bx0) * sc) + off_x, int((t[3] - by0) * sc))]
print("平板四角（源图坐标）: %s" % (t,))
print("映射到 %d² 画布: TL%s TR%s BR%s BL%s" % (SIDE, quad[0], quad[1], quad[2], quad[3]))
for n, q in zip(("qx", "qy"), zip(*quad)):
    print("        double[] %s = new double[] { %d, %d, %d, %d };" % (n, q[0], q[1], q[2], q[3]))

# 桌宠实渲：平板里写上真实额度文字
def render(sprite, size, label, value, out_name):
    s = sprite.copy(); s.thumbnail((size, size), Image.LANCZOS)
    canvas = Image.new("RGB", (size, size), (18, 22, 38))
    canvas.paste(s, ((size - s.width) // 2, size - s.height), s)
    # 面板 = 平板矩形的 88%
    p = quad
    x0 = int(min(q[0] for q in p) * s.width / SIDE); x1 = int(max(q[0] for q in p) * s.width / SIDE)
    y0 = int(min(q[1] for q in p) * s.height / SIDE); y1 = int(max(q[1] for q in p) * s.height / SIDE)
    pw, ph = x1 - x0, y1 - y0
    pad = int(pw * 0.06)
    d = ImageDraw.Draw(canvas)
    try:
        f1 = ImageFont.truetype("msyhbd.ttc", max(9, int(ph * 0.20)))
        f2 = ImageFont.truetype("arialbd.ttf", max(12, int(ph * 0.42)))
    except Exception:
        f1 = f2 = ImageFont.load_default()
    d.text((x0 + pw / 2, y0 + ph * 0.22), label, font=f1, fill=(158, 182, 224), anchor="mm")
    d.text((x0 + pw / 2, y0 + ph * 0.62), value, font=f2, fill=(240, 246, 255), anchor="mm")
    canvas.save(os.path.join(OUT, out_name))
    return canvas


render(sq, 454, "额外额度", "¥17.99", "newart_454.png")
render(sq, 340, "额外额度", "¥17.99", "newart_340.png")
render(sq, 624, "剩余额度", "100%", "newart_624_plan.png")

# 四张对齐后的差分，并排看跳不跳
sheet = Image.new("RGB", (300 * 4, 300), (18, 22, 38))
for i, im in enumerate(aligned):
    s = to_square(im)[0]; s.thumbnail((292, 292), Image.LANCZOS)
    sheet.paste(s, (i * 300 + 4, 4), s)
sheet.save(os.path.join(OUT, "newart_four.png"))
print("\n产出: newart_454.png / newart_340.png / newart_624_plan.png / newart_four.png")
