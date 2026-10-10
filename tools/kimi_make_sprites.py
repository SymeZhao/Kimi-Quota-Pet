# 从生成的四格图做出桌宠用的 sprite 素材
#
#   python tools/kimi_grid_check2.py   # ① 量平板四角 + 切图 + 抠图 + 对齐（输出 art/kimi-pet-new.png 等）
#   python tools/kimi_make_sprites.py  # ② 本脚本：缩放成 1024² 并写 sprite.png / sprites/expression_*.png
#
# 需要 Pillow（numpy 不必须）。运行目录无所谓，路径都是绝对/相对本文件推算的。
import os
import sys
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "art")
SPRITES = os.path.join(ROOT, "sprites")
SIDE = 1024                      # 桌宠最大档 624px，1024 有 1.6 倍余量

# 四张对齐后的 1720² 母图（由 kimi_grid_check2.py 产出）
SRC = {"11": "newart_11.png", "22": "newart_22.png", "12": "newart_12.png", "21": "newart_21.png"}
# 母图上的平板四角（TL, TR, BR, BL），换成你自己的图时用 kimi_grid_check2.py 打印的新值
QUAD_1720 = {"qx": (641, 1187, 1208, 661), "qy": (1113, 1080, 1412, 1445)}


def main():
    os.makedirs(SPRITES, exist_ok=True)
    for key, name in SRC.items():
        src = os.path.join(ART, name)
        if not os.path.exists(src):
            sys.exit("缺少母图 %s —— 请先运行 tools/kimi_grid_check2.py" % src)
        im = Image.open(src).convert("RGBA").resize((SIDE, SIDE), Image.LANCZOS)
        dst = os.path.join(SPRITES, "expression_%s.png" % key)
        im.save(dst)
        print("写出 %-34s %d KB" % (os.path.relpath(dst, ROOT), os.path.getsize(dst) // 1024))
    # 基准 sprite 用常态那张（程序启动时先加载它，随后被表情图替换）
    base = Image.open(os.path.join(SPRITES, "expression_11.png"))
    base.save(os.path.join(ROOT, "sprite.png"))
    print("写出 sprite.png（= expression_11）")

    sc = SIDE / 1720.0
    qx = [round(v * sc) for v in QUAD_1720["qx"]]
    qy = [round(v * sc) for v in QUAD_1720["qy"]]
    print("\n把下面两行抄进 kimi_pet.ps1 的 Relayout()（平板四角，顺序 TL, TR, BR, BL）：")
    print("        double[] qx = new double[] { %d, %d, %d, %d };" % tuple(qx))
    print("        double[] qy = new double[] { %d, %d, %d, %d };" % tuple(qy))


if __name__ == "__main__":
    main()
