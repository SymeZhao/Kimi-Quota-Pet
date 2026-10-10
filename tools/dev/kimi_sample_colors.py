# 采样真实像素，判断"哪些道具能用颜色区分、哪些不能"
import numpy as np
from PIL import Image, ImageDraw

SRC = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art\kimi-full.jpg"
OUT = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art\preview\sample_points.png"
im = Image.open(SRC).convert("RGB")
W, H = im.size
a = np.asarray(im).astype(np.int16)
print("size", im.size)

ring = np.concatenate([a[0, :, :], a[-1, :, :], a[:, 0, :], a[:, -1, :]])
bg = np.median(ring, axis=0)
print("bg =", bg)

# 目测点位（960x1720 原图坐标）
pts = [
    ("背景-左上", 20, 30), ("背景-右上", 940, 40), ("背景-中间左", 40, 900),
    ("月亮-左弧", 62, 300), ("月亮-左上弧", 180, 120), ("月亮-右上(头右侧)", 700, 200),
    ("纸-右下", 900, 1350), ("纸-左下", 120, 1000), ("纸-底部中间", 660, 1650),
    ("影子-脚下左", 420, 1640), ("影子-脚下右", 560, 1660),
    ("发-左侧", 250, 700), ("发-右大团", 800, 700), ("发-头顶", 470, 120),
    ("裙-白主体", 480, 1150), ("裙-白蕾丝边", 380, 1300), ("袜-白", 470, 1450),
    ("鞋-黑", 470, 1650), ("深蓝裙", 300, 1100), ("皮肤-脸", 470, 260),
]
print("\n%-22s %-10s %-8s %-8s %s" % ("点位", "RGB", "离底色", "B-R", "备注"))
rows = []
for name, x, y in pts:
    c = a[y, x]
    d = float(np.sqrt(((c - bg) ** 2).sum()))
    note = []
    if d < 12: note.append("几乎=底色")
    if abs(int(c[2]) - int(c[0])) >= 6: note.append("偏冷")
    if abs(int(c[0]) - int(c[2])) >= 6: note.append("偏暖")
    if c.max() > 235 and (c.max() - c.min()) < 18: note.append("浅灰白")
    print("%-22s %-10s %-8.1f %-8d %s" % (name, "(%d,%d,%d)" % tuple(c), d, int(c[2]) - int(c[0]), ",".join(note)))
    rows.append((name, x, y))

# 可视化：把点位画在原图上，方便核对
vis = im.copy()
d = ImageDraw.Draw(vis)
for name, x, y in rows:
    d.ellipse([x - 6, y - 6, x + 6, y + 6], outline=(255, 0, 255), width=3)
vis.thumbnail((640, 1147), Image.LANCZOS)
vis.save(OUT)
print("\n点位图 ->", OUT)
