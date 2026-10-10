# 生成 Kimi 桌宠素材：
#   1) sprite.png      = 抠好的立绘 + 程序化深色平板（文字由桌宠运行时画在上面）
#   2) panel_quad.txt  = 平板四角在源图里的像素坐标（要粘到 kimi_pet.ps1 的 qx/qy）
#   3) face.png        = 扣费/点击特写的圆角头像
#   4) pet.ico         = 托盘与快捷方式图标（多尺寸）
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ART = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art"
OUT = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet"
SRC = os.path.join(ART, "kimi-pet.png")          # 1720x1720 透明立绘
preview = os.path.join(ART, "preview")

sprite = Image.open(SRC).convert("RGBA")
W, H = sprite.size
print("立绘 %dx%d" % (W, H))

# 人物实际范围（alpha>8 的包围盒），用来把平板贴在合理位置
a = np.asarray(sprite)[:, :, 3]
ys, xs = np.where(a > 8)
bx0, bx1, by0, by1 = xs.min(), xs.max(), ys.min(), ys.max()
print("人物包围盒 x %d..%d  y %d..%d" % (bx0, bx1, by0, by1))

# 平板：贴在她身前偏右（腰/裙摆高度），大小约 440x210
PW, PH = 440, 210
PX = int(bx0 + (bx1 - bx0) * 0.60)
PY = int(by0 + (by1 - by0) * 0.63)

panel = Image.new("RGBA", (PW + 60, PH + 60), (0, 0, 0, 0))
d = ImageDraw.Draw(panel)
ox, oy = 30, 26                     # 给阴影留边
# 阴影
for i in range(14, 0, -2):
    alpha = int(10 + (14 - i) * 2.2)
    d.rounded_rectangle([ox - i * 0.6, oy + i * 0.7, ox + PW + i * 0.6, oy + PH + i * 0.7],
                        radius=30 + i, fill=(6, 8, 18, alpha))
# 屏幕底色（深蓝黑，参考她腰上 K 小屏的配色）
d.rounded_rectangle([ox, oy, ox + PW, oy + PH], radius=28, fill=(16, 21, 38, 248))
# 内层微渐变
grad = Image.new("RGBA", (PW, PH), (0, 0, 0, 0))
gd = ImageDraw.Draw(grad)
for y in range(PH):
    t = y / max(1, PH - 1)
    gd.line([(0, y), (PW, y)], fill=(int(22 + 10 * (1 - t)), int(28 + 12 * (1 - t)), int(52 + 18 * (1 - t)), 255))
grad = grad.filter(ImageFilter.GaussianBlur(0.4))
mask = Image.new("L", (PW, PH), 0)
ImageDraw.Draw(mask).rounded_rectangle([0, 0, PW - 1, PH - 1], radius=26, fill=255)
panel.paste(grad, (ox, oy), mask)
# 边框（冷银蓝）
d.rounded_rectangle([ox, oy, ox + PW, oy + PH], radius=28, outline=(150, 172, 226, 210), width=3)
d.rounded_rectangle([ox + 6, oy + 6, ox + PW - 6, oy + PH - 6], radius=22, outline=(90, 108, 158, 90), width=1)
# 左上角两个小装饰点
d.ellipse([ox + 18, oy + 16, ox + 28, oy + 26], fill=(226, 196, 120, 230))
d.ellipse([ox + 34, oy + 16, ox + 44, oy + 26], fill=(150, 172, 226, 200))
# 底部一条高光
d.line([(ox + 24, oy + PH - 14), (ox + PW - 24, oy + PH - 14)], fill=(120, 145, 205, 70), width=2)

sprite2 = sprite.copy()
sprite2.alpha_composite(panel, (PX - 30, PY - 26))
sprite2.save(os.path.join(OUT, "sprite.png"))

# 平板的文字区四角（不含阴影留边）—— 源图像素坐标，顺序 TL, TR, BR, BL
quad = [(PX, PY), (PX + PW, PY), (PX + PW, PY + PH), (PX, PY + PH)]
print("panel quad (TL,TR,BR,BL) =", quad)
with open(os.path.join(OUT, "panel_quad.txt"), "w", encoding="utf-8") as fh:
    fh.write("sprite=%dx%d panel=%dx%d\n" % (W, H, PW, PH))
    fh.write("qx = %s\n" % ", ".join(str(p[0]) for p in quad))
    fh.write("qy = %s\n" % ", ".join(str(p[1]) for p in quad))

# ---- 特写头像 ----
face = Image.open(os.path.join(ART, "kimi-face.jpg")).convert("RGB")
fw, fh = face.size
# 取脸部：中线偏上，方形裁切
side = int(min(fw, fh) * 0.62)
cx, cy = int(fw * 0.50), int(fh * 0.42)
box = (cx - side // 2, cy - side // 2, cx + side // 2, cy + side // 2)
box = (max(0, box[0]), max(0, box[1]), min(fw, box[2]), min(fh, box[3]))
face = face.crop(box).resize((512, 512), Image.LANCZOS).convert("RGBA")
fmask = Image.new("L", (512, 512), 0)
ImageDraw.Draw(fmask).rounded_rectangle([0, 0, 511, 511], radius=64, fill=255)
face.putalpha(fmask)
# 一圈冷色描边，贴在深色桌面上更有形
ring = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
ImageDraw.Draw(ring).rounded_rectangle([2, 2, 509, 509], radius=62, outline=(160, 182, 236, 235), width=6)
face.alpha_composite(ring)
face.save(os.path.join(OUT, "face.png"))

# ---- 图标 ----
icon = Image.open(os.path.join(ART, "kimi-icon.webp")).convert("RGBA")
side = min(icon.size)
icon = icon.crop(((icon.width - side) // 2, (icon.height - side) // 2,
                  (icon.width + side) // 2, (icon.height + side) // 2))
icon.save(os.path.join(OUT, "pet.ico"), sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
icon.resize((256, 256), Image.LANCZOS).save(os.path.join(OUT, "tray_icon_256.png"))


def checker(size, box=16):
    img = Image.new("RGB", (size, size), (255, 255, 255)); d = ImageDraw.Draw(img)
    for y in range(0, size, box):
        for x in range(0, size, box):
            if ((x // box) + (y // box)) % 2:
                d.rectangle([x, y, x + box - 1, y + box - 1], fill=(205, 205, 205))
    return img


for sz, name in ((340, "sprite_340_checker.png"), (624, "sprite_624_checker.png")):
    s = sprite2.copy(); s.thumbnail((sz, sz), Image.LANCZOS)
    ch = checker(sz)
    ch.paste(s, ((sz - s.width) // 2, sz - s.height), s)
    ch.save(os.path.join(preview, name))
fb = Image.new("RGB", (512, 512), (18, 22, 38)); fb.paste(face, (0, 0), face)
fb.save(os.path.join(preview, "face_preview.png"))
print("产出：sprite.png / panel_quad.txt / face.png / pet.ico / tray_icon_256.png")
