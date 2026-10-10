# 验收第 2 版：行/列投影定位平板 + PCA 求倾角与四角；然后抠图、对齐、桌宠实渲
import os, math, shutil
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ART = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art"
SRC = os.path.join(ART, "kimi-grid.webp")
OUT = os.path.join(ART, "preview")
names = ["11 常态", "22 右上", "12 左下", "21 冷脸"]

img = Image.open(SRC).convert("RGB")
W, H = img.size
cw, ch = W // 2, H // 2
print("源图 %dx%d，单格 %dx%d\n" % (W, H, cw, ch))


def find_tablet(a):
    """平板 = 一块大的近黑矩形：行列投影找大致范围，再用 PCA 求倾角与真实四角"""
    dark = a.max(axis=2) < 70
    rows = dark.sum(axis=1) / float(cw)
    cols = dark.sum(axis=0) / float(ch)
    def longest_run(profile, thr):
        best = (0, -1, -1); cur = -1
        for i, v in enumerate(profile):
            if v > thr:
                if cur < 0: cur = i
                if i - cur > best[0]: best = (i - cur, cur, i)
            else:
                cur = -1
        return best[1], best[2]
    y0, y1 = longest_run(rows, 0.22)
    x0, x1 = longest_run(cols, 0.20)
    if y0 < 0 or x0 < 0: return None
    sub = dark[y0:y1 + 1, x0:x1 + 1]
    yy, xx = np.where(sub)
    if len(xx) < 2000: return None
    pts = np.stack([xx.astype(float), yy.astype(float)])
    c = pts.mean(axis=1)
    cov = np.cov(pts)
    ev, evec = np.linalg.eigh(cov)
    u = evec[:, -1]; v = evec[:, 0]
    if u[0] < 0: u = -u
    if v[1] < 0: v = -v
    pu = (pts - c.reshape(2, 1)).T @ u
    pv = (pts - c.reshape(2, 1)).T @ v
    hu = (np.percentile(pu, 99.0) - np.percentile(pu, 1.0)) / 2
    hv = (np.percentile(pv, 99.0) - np.percentile(pv, 1.0)) / 2
    ang = math.degrees(math.atan2(u[1], u[0]))
    cen = np.array([c[0] + x0, c[1] + y0])
    corners = []
    for su, sv in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        p = cen + u * hu * su + v * hv * sv
        corners.append((float(p[0]), float(p[1])))
    return dict(cx=cen[0], cy=cen[1], w=2 * hu, h=2 * hv, ang=ang, corners=corners,
                rect=float(len(xx)) / float((2 * hu + 1) * (2 * hv + 1)))


cells = []
print("%-10s %-30s %-22s %s" % ("面板", "平板（中心/尺寸/倾角/矩形度）", "人物外接框(sad>60)", "离边缘"))
for i, nm in enumerate(names):
    x0, y0 = (i % 2) * cw, (i // 2) * ch
    cell = img.crop((x0, y0, x0 + cw, y0 + ch))
    a = np.asarray(cell).astype(np.int16)
    ring = np.concatenate([a[:4, :, :].reshape(-1, 3), a[-4:, :, :].reshape(-1, 3),
                           a[:, :4, :].reshape(-1, 3), a[:, -4:, :].reshape(-1, 3)])
    bg = np.median(ring, axis=0)
    sad = np.abs(a - bg).sum(axis=2)
    sil = sad > 60
    ys, xs = np.where(sil)
    bbox = (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max()))
    margin = min(bbox[0], bbox[1], cw - 1 - bbox[2], ch - 1 - bbox[3])
    t = find_tablet(a)
    if t:
        print("%-10s 中心(%4.0f,%4.0f) %4.0fx%-4.0f 倾角%5.1f° 矩形度%.2f   %-22s %dpx" %
              (nm, t["cx"], t["cy"], t["w"], t["h"], t["ang"], t["rect"], str(bbox), margin))
    else:
        print("%-10s 未检出                                        %-22s %dpx" % (nm, str(bbox), margin))
    cells.append(dict(name=nm, cell=cell, bg=bg, sil=sil, bbox=bbox, tab=t))

ok = [c for c in cells if c["tab"]]
if len(ok) == 4:
    print("\n跨面板一致性：")
    print("  平板中心偏差  Δx=%.0fpx  Δy=%.0fpx" % (max(c["tab"]["cx"] for c in ok) - min(c["tab"]["cx"] for c in ok),
                                                  max(c["tab"]["cy"] for c in ok) - min(c["tab"]["cy"] for c in ok)))
    print("  平板尺寸偏差  宽=%.0fpx  高=%.0fpx" % (max(c["tab"]["w"] for c in ok) - min(c["tab"]["w"] for c in ok),
                                                  max(c["tab"]["h"] for c in ok) - min(c["tab"]["h"] for c in ok)))
    print("  人物外接框    x %d~%d，y %d~%d" % (min(c["bbox"][0] for c in cells), max(c["bbox"][0] for c in cells),
                                               min(c["bbox"][1] for c in cells), max(c["bbox"][1] for c in cells)))

    # ---- 抠图（白底洪泛 + 只削浅色白边）----
    def cut(cell, bg):
        im = cell.convert("RGB")
        soft = im.filter(ImageFilter.GaussianBlur(1.6))
        work = ImageOps = None
        from PIL import ImageOps as _IO
        pad = 10
        work = _IO.expand(soft, border=pad, fill=tuple(int(v) for v in bg))
        ImageDraw.floodfill(work, (0, 0), (255, 0, 255), thresh=42)
        w = np.asarray(work)
        bgm = ((w[:, :, 0] > 250) & (w[:, :, 1] < 5) & (w[:, :, 2] > 250))[pad:-pad, pad:-pad]
        m = Image.fromarray((bgm * 255).astype(np.uint8), "L").filter(ImageFilter.MaxFilter(5))
        band = np.asarray(m) > 128
        a2 = np.asarray(im).astype(np.int16)
        sad2 = np.abs(a2 - bg).sum(axis=2)
        kill = band & (sad2 < 120)          # 只削"接近底色"的浅色白边，保住发丝与蕾丝
        alpha = Image.fromarray(((~bgm) & (~kill) if False else (~(bgm | kill)) * 255).astype(np.uint8), "L")
        alpha = alpha.filter(ImageFilter.GaussianBlur(1.0))
        out = im.convert("RGBA"); out.putalpha(alpha)
        return out

    cut_cells = [cut(c["cell"], c["bg"]) for c in cells]
    # 以平板中心为锚点平移对齐
    base = ok[0]["tab"]
    aligned = []
    for c, im in zip(cells, cut_cells):
        dx = int(round(c["tab"]["cx"] - base["cx"])); dy = int(round(c["tab"]["cy"] - base["cy"]))
        canv = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        canv.paste(im, (-dx, -dy), im)
        aligned.append(canv)

    SIDE = 1720
    def to_square(im, side=SIDE):
        arr = np.asarray(im)[:, :, 3] > 8
        ys, xs = np.where(arr)
        bx0, by0, bx1, by1 = xs.min(), ys.min(), xs.max() + 1, ys.max() + 1
        crop = im.crop((bx0, by0, bx1, by1))
        sc = side / float(crop.height)
        crop = crop.resize((max(1, int(crop.width * sc)), side), Image.LANCZOS)
        canv = Image.new("RGBA", (side, side), (0, 0, 0, 0))
        canv.paste(crop, ((side - crop.width) // 2, 0), crop)
        return canv, (bx0, by0, sc, (side - crop.width) // 2)

    sq0, (bx0, by0, sc, offx) = to_square(aligned[0])
    def mapq(pt):
        return (int((pt[0] - bx0) * sc) + offx, int((pt[1] - by0) * sc))
    quad = [mapq(p) for p in base["corners"]]
    print("\n缩放系数 %.3f（%d → %d）；平板四角映射到 %d² 画布：" % (sc, ch, SIDE, SIDE))
    for lbl, p in zip(("TL", "TR", "BR", "BL"), quad):
        print("   %s (%d, %d)" % (lbl, p[0], p[1]))
    print("        double[] qx = new double[] { %d, %d, %d, %d };" % (quad[0][0], quad[1][0], quad[2][0], quad[3][0]))
    print("        double[] qy = new double[] { %d, %d, %d, %d };" % (quad[0][1], quad[1][1], quad[2][1], quad[3][1]))

    sq0.save(os.path.join(ART, "kimi-pet-new.png"))
    for i, im in enumerate(aligned):
        to_square(im)[0].save(os.path.join(ART, "newart_%s.png" % ["11", "22", "12", "21"][i]))

    # ---- 桌宠实渲（把额度文字画在她的平板上）----
    def render(sprite, size, label, value, out_name):
        s = sprite.copy(); s.thumbnail((size, size), Image.LANCZOS)
        canvas = Image.new("RGB", (size, size), (18, 22, 38))
        canvas.paste(s, ((size - s.width) // 2, size - s.height), s)
        xs = [q[0] * s.width / SIDE for q in quad]; ys = [q[1] * s.height / SIDE for q in quad]
        x0, x1 = int(min(xs)), int(max(xs)); y0, y1 = int(min(ys)), int(max(ys))
        pw, ph = x1 - x0, y1 - y0
        d = ImageDraw.Draw(canvas)
        try:
            f1 = ImageFont.truetype("msyhbd.ttc", max(8, int(ph * 0.19)))
            f2 = ImageFont.truetype("arialbd.ttf", max(11, int(ph * 0.40)))
        except Exception:
            f1 = f2 = ImageFont.load_default()
        d.text((x0 + pw / 2, y0 + ph * 0.24), label, font=f1, fill=(150, 176, 222), anchor="mm")
        d.text((x0 + pw / 2, y0 + ph * 0.64), value, font=f2, fill=(240, 246, 255), anchor="mm")
        canvas.save(os.path.join(OUT, out_name))

    render(sq0, 454, "额外额度", "¥17.99", "newart_454.png")
    render(sq0, 340, "额外额度", "¥17.99", "newart_340.png")
    render(sq0, 624, "剩余额度", "100%", "newart_624.png")

    sheet = Image.new("RGB", (300 * 4, 300), (18, 22, 38))
    for i, im in enumerate(aligned):
        sqi = to_square(im)[0]; sqi.thumbnail((292, 292), Image.LANCZOS)
        sheet.paste(sqi, (i * 300 + 4, 4), sqi)
    sheet.save(os.path.join(OUT, "newart_four.png"))
    print("\n产出：art\\kimi-pet-new.png / art\\newart_11..21.png / preview\\newart_454|340|624.png / newart_four.png")
