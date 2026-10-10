# 定位残留：把原图和抠图结果的同一区域并排放大
import os
from PIL import Image, ImageDraw, ImageFont

ART = r"C:\Users\Administrator\Documents\Kimi-Quota-Pet\art"
OUT = os.path.join(ART, "preview")
orig = Image.open(os.path.join(ART, "kimi-full.jpg")).convert("RGB")
cut = Image.open(os.path.join(ART, "kimi-pet-cutout.png")).convert("RGBA")

BOXES = {
    "left_mid": (0, 380, 300, 700),
    "moon_upper": (0, 0, 420, 420),
    "right_arc": (600, 300, 960, 700),
}
scale = 2
for name, box in BOXES.items():
    o = orig.crop(box).resize(((box[2] - box[0]) * scale, (box[3] - box[1]) * scale), Image.LANCZOS)
    c = cut.crop(box)
    cb = Image.new("RGB", c.size, (18, 22, 38))
    cb.paste(c, (0, 0), c)
    cb = cb.resize(o.size, Image.LANCZOS)
    sheet = Image.new("RGB", (o.width * 2 + 12, o.height), (60, 60, 60))
    sheet.paste(o, (0, 0))
    sheet.paste(cb, (o.width + 12, 0))
    d = ImageDraw.Draw(sheet)
    d.text((4, 4), "ORIGINAL  %s" % str(box), fill=(255, 255, 0), font=ImageFont.load_default())
    d.text((o.width + 16, 4), "CUTOUT on dark", fill=(0, 255, 255), font=ImageFont.load_default())
    sheet.save(os.path.join(OUT, "v7_leftover_%s.png" % name))
    print("v7_leftover_%s.png  %dx%d" % (name, sheet.width, sheet.height))
