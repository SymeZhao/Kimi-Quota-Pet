# Kimi 桌宠 · 差分立绘生成提示词

给 GPT-image（或同类文生图）用的提示词包。目标：画出 **Kimi 拟人角色在 4 个场景下的差分立绘**，
画完能直接替换进桌宠，让桌宠有"换表情"的能力，并且把现在"人小、平板浮在裙子前"的怪异感一起修掉。

---

## 一、先明确要什么（对照原版大肥鱼桌宠）

原版桌宠的立绘体系（`DSH-Balance-Pet\`，可直接当格式参考）：

| 项目 | 原版做法 | 为什么这样做 |
| --- | --- | --- |
| 画布 | **1024×1024 正方形**，透明底 | 桌宠控件是正方形，按**高度**缩放；正方形才不会被留白缩成小人 |
| 构图 | **半身**（头顶到大腿/腰），人物撑满画面 | 在 340~624px 的小挂件上，脸和表情才看得清 |
| 平板 | 她**双手举在胸前**，一块**纯黑空白**圆角屏，屏幕朝观众、几乎正对镜头 | 余额数字是运行时画上去的，所以屏必须是空白且尽量水平 |
| 差分 | 4 张：`expression_11 / 22 / 12 / 21` | 躯干、双手、平板、头发、光效**像素级一致**，**只有脸不同** → 切换时不跳 |
| 表情 | 11 开心（默认）、22 扣费中（眯眼皱眉 + 汗滴）、12 傲娇（撇嘴斜眼）、21 冷脸（死鱼眼） | 一图一状态，一眼能读懂 |

我们要画的 Kimi 版就是这套格式，角色换成 Kimi（白发紫瞳、藏青×白女仆风、月亮/音符/K 元素）。

**当前问题**（这次一起修）：现在的图是 1:1.79 竖构图全身像，塞进正方形后人物只占约 55% 宽，
且平板是程序化画上去的、浮在她裙前，手里还拿着长笛——所以看起来怪。

---

## 二、要喂给模型的参考图

一次对话里把这些一起上传：

| 用途 | 文件 |
| --- | --- |
| 格式 & 姿态参考（**最重要**） | `Kimi-Quota-Pet\art\preview\dsh_sprite_set.png`（我给原版 5 张拼的对照图，一张顶五张） |
| 原版单张（可选，补充细节） | `DSH-Balance-Pet\sprites\expression_11.png`、`expression_22.png`、`expression_12.png`、`expression_21.png` |
| Kimi 角色参考 ①（全身/服装/配饰） | `Kimi-Quota-Pet\art\kimi-full.jpg` |
| Kimi 角色参考 ②（五官/脸型/瞳色） | `Kimi-Quota-Pet\art\kimi-face.jpg` |
| Kimi 角色参考 ③（配色/图标感） | `Kimi-Quota-Pet\art\kimi-icon.webp` |

给模型的说明就一句：**角色长相看 Kimi 那三张；画法、构图、姿态、平板样式照大肥鱼那几张来。**

---

## 三、硬规格（4 个面板必须完全一致，逐条别改）

```
CANVAS      square 1:1. Recommended 2048×2048 (or 1024×1024). Nothing may be cropped by the edge.
FRAMING     half-body: top of head to about mid-thigh/waist. Character fills ~92% of the canvas
            height and is horizontally centered. Same camera, same zoom in every panel.
POSE        identical in every panel: upper body facing the viewer at a slight 3/4 angle,
            BOTH hands holding one tablet in front of the chest, elbows relaxed.
TABLET      one plain, BLANK dark tablet (near-black #101526, thin lighter bezel, slightly
            rounded corners). Screen faces the viewer, tilted no more than 10° from upright.
            Occupies ~50% of the canvas width, fully inside the frame, NOT covered by hair,
            fingers or clothing. The screen is EMPTY: no text, no icons, no logo, no reflections.
BACKGROUND  fully transparent if your tool supports it. Otherwise pure flat #FFFFFF white,
            absolutely nothing else: no shadow under her, no floor, no glow, no moon, no music
            notes, no sheet music, no gradient, no vignette, no frame.
STYLE       clean anime illustration, crisp line art, soft cel shading, 2-tone hair highlights,
            consistent line weight and lighting direction (soft key light from upper left).
FORBIDDEN   no text/watermark/signature anywhere, no background props, no motion lines,
            no speech bubbles, no extra characters, no colour cast on the background,
            no changes to the body/hands/tablet/hair between panels.
```

> 关于透明底：如果工具支持 `transparent background` 就直接要透明底；
> 不支持也没关系，**纯白背景反而更安全**——只要没有阴影和道具，我这边抠图一秒干净
> （上次那张图难抠，就是因为背景里有月亮、乐谱纸、脚下阴影和一堆音符）。

---

## 四、推荐做法 A：一张 2×2 四格图（姿态天然对齐）

**为什么推荐**：4 张分别生成，模型每次都会微调构图和比例，切表情时会"跳"；
一张图里画 4 格，姿态/比例/光照由同一次生成保证，我切片后再做微对齐就够了。

### 主提示词（直接整段粘贴，英文）

```
Character reference: the attached Kimi illustrations (silver-white long wavy hair, violet eyes,
navy-blue × white frilly maid-style dress with star/moon/music-note motifs, a "K" round emblem
on the chest bow with a small rainbow ribbon, silver crescent-moon + music-note hair ornament,
navy hair bow with a hanging "K" charm).
Format reference: the attached desktop-pet sprite sheet (half-body framing, both hands holding
a blank dark tablet in front of the chest).

TASK: draw a 2×2 grid of FOUR EXPRESSION PANELS of this same character — one character per cell,
four equal square cells, thin clean white gutters between them, nothing crossing the gutters.

ABSOLUTE CONSTRAINTS (identical in all four panels):
- same half-body framing (top of head to mid-thigh), same camera, same zoom, same 3/4 angle
- identical body, identical hands, identical hair, identical tablet in every panel
- both hands hold ONE plain BLANK dark tablet in front of the chest, screen facing the viewer,
  tilted at most 10°, tablet about half the cell width, fully inside the cell, screen empty
- soft key light from the upper left, same cel-shading, same line weight
- pure flat white #FFFFFF background in every cell, nothing else — no shadow, no floor, no glow,
  no moon, no music notes, no sheet music, no gradient, no frame, no text, no watermark
- absolutely nothing may be cropped by the cell edges

THE ONLY DIFFERENCES between the four panels are the FACES (and at most one tiny accent mark):
  top-left      calm confident smile, eyes open, relaxed brows            (idle / default)
  top-right     eyes squeezed shut, wincing, blushing, one small sweat    (being charged)
                drop near the temple, mouth a small frown
  bottom-left   worried: brows raised and tilted, eyes wide with a small  (quota running out)
                tear at the outer corner, mouth slightly trembling
  bottom-right  flat deadpan stare, half-lidded eyes, straight mouth,     (offline / no reading)
                no blush, no other marks
Body pose, hands, tablet, hair and lighting must be pixel-identical across the four panels.
```

### 切片后要做的（我来做）

1. 4 格切成 4 张 1024×1024
2. 抠掉白底（边界洪泛 + 只削浅色白边，保住发丝和蕾丝）
3. **对齐**：以平板外接矩形为锚点，把 4 张平移到同一位置（差分不能跳）
4. 平板取角 → 写进 `kimi_pet.ps1` 的 `qx/qy`；生成 `sprite.png` + `sprites/expression_*.png`
5. 桌宠开 4 表情模式：常态 / 扣费中 / 额度见底 / 离线

---

## 五、备选做法 B：4 张独立图

如果四格图里人物一致性总是崩，就分开画：**同一个提示词跑 4 次，只改最后那段表情描述**。

```
Character reference: the attached Kimi illustrations (silver-white long wavy hair, violet eyes,
navy-blue × white frilly maid-style dress with star/moon/music-note motifs, a "K" round emblem
on the chest bow with a small rainbow ribbon, silver crescent-moon + music-note hair ornament).
Format reference: the attached desktop-pet sprite sheet.

Draw ONE half-body portrait of this character: top of head to mid-thigh, centered, filling ~92%
of the height of a square 1:1 canvas, upper body facing the viewer at a slight 3/4 angle, both
hands holding one plain BLANK dark tablet (near-black, thin lighter bezel, rounded corners) in
front of the chest, screen facing the viewer, tilted at most 10°, screen completely empty.

Expression: <在这里粘下面任意一条>

Background: pure flat #FFFFFF white, nothing else — no shadow, no floor, no glow, no moon,
no music notes, no gradient, no frame, no text, no watermark. Nothing cropped by the edges.
Style: clean anime illustration, crisp line art, soft cel shading, soft key light from upper left.
```

四条表情行（替换 `<...>`）：

| 用途 | 英文 |
| --- | --- |
| 常态 | `calm confident smile, eyes open, relaxed brows, slight blush` |
| 扣费中 | `eyes squeezed shut, wincing, blushing hard, one small sweat drop near the temple, small frown` |
| 额度见底 | `worried, brows raised and tilted inward, eyes wide with a small tear at the outer corner, mouth slightly trembling` |
| 离线 | `flat deadpan stare, half-lidded eyes, straight mouth, no blush, no marks` |
| （备用）回升/充值 | `delighted, eyes closed in a happy arc, wide smile, a few tiny sparkles around the head only` |

---

## 六、想保持角色一致，再补这几条

同一角色多次生成容易"长歪"，可以追加：

```
Keep the character design EXACTLY as in the reference: the same face shape and eye shape,
the same violet iris colour, the same silver-white hair with the same parting and the same
crescent-moon + music-note hair ornament on her left side, the same "K" chest emblem with the
rainbow ribbon, the same navy × white outfit with star/moon/music-note embroidery.
Do not restyle, do not change her age, do not add or remove accessories.
```

---

## 七、生成得不对时，这样追加指令

| 症状 | 追加一句 |
| --- | --- |
| 4 格姿态/大小不一致 | `All four panels must share the exact same body, pose and scale — treat the body as one drawing that is copied four times, and change ONLY the facial features.` |
| 平板上有字/图案 | `The tablet screen must be completely empty dark glass — no text, no letters, no "K", no icons, no reflections.` |
| 背景又跑出月亮/音符/影子 | `Remove every background element. The background must be pure flat white, with no shadow under the character and no decorative props of any kind.` |
| 人物被裁掉 | `Zoom out slightly so the whole head, both hands and the entire tablet are inside the frame with a small margin.` |
| 平板歪太多 | `Hold the tablet almost straight: no more than 10 degrees of tilt, screen squarely facing the viewer.` |
| 画成全身 | `Crop to a half-body portrait: from the top of her head to about her waist. Do not show legs or feet.` |
| 只有一张里有彩虹光束 | `No rainbow beam or any other effect in any panel.` |

---

## 八、拿到图我会做什么（你不用管，列出来是让你知道要什么格式）

1. 切片 + 抠图（纯白底最好抠；透明底直接用）
2. 以平板为锚点做四张对齐，检查差分跳不跳
3. 输出 `sprite.png`（1720² 方形）+ `sprites/expression_11/12/21/22.png`
4. 平板矩形取角 → 抄进 `kimi_pet.ps1` 的 `qx/qy`（额度数字正好落在她举的屏上）
5. 把两个新状态接进去：**额度见底**（额外额度低于阈值时）、**离线**（读不到令牌时）
6. 跑一遍 `--shot` 出图给你看，不满意就调（平板位置/大小只是一行常量）

---

## 九、验收清单（我拿到图会逐条查）

- [ ] 四格是 1:1 正方形、等分、四张的**躯干/手/平板/头发**能对齐到 1~2px 内
- [ ] 平板是空白深色屏、朝向观众、倾角 ≤10°、四边都在画面内、没被头发或手指遮住
- [ ] 背景是纯白或透明，**没有**阴影/月亮/音符/乐谱/渐变/边框
- [ ] 没有文字、水印、签名、彩虹光束、多余角色
- [ ] 头到腰的半身构图，人物占满高度，脸够大（缩小到 340px 后表情仍可辨认）
- [ ] 白发/白裙边缘干净（没有和背景糊在一起），缩到 340px 后没有白边
- [ ] 四张的脸型、瞳色、发饰、"K" 胸针完全一致
