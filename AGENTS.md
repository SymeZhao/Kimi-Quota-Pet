# 项目维护约定

本仓库是 **Kimi 额度桌宠**（Windows 单平台）。界面外壳移植自 [VKmich16/VK-1](https://github.com/VKmich16/VK-1) 的
Windows 版 v3（MIT），数据层与显示口径为本仓库自行实现。改动前请先读本文件。

## 通用

- **不要提交个人数据**：`kimi_pet.log`、`kimi_quota.log`、`state.ini`、`kimi_quota_sample.json`、
  `_shot*.png`、`art/generated/**` 都已在 `.gitignore` 里。提交前跑一次 `git status --porcelain` 确认为空。
- 代码里**不得出现任何令牌内容**：日志、错误信息、`Console.WriteLine` 一律不许带 `access_token` / `refresh_token`。
- 立绘是本项目自备素材，**不适用代码的 MIT 许可**；`LICENSE` 末尾的「素材说明」要保持同步。

## 代码约定

- `kimi_pet.ps1`、`kimi_quota.ps1`、`.vbs`、`.cmd` **必须保持纯 ASCII**：
  Windows PowerShell 5.1 读取无 BOM 的脚本时按 ANSI 解码，脚本里直接写中文会乱码甚至解析失败。
  界面中文一律用 C# 的 `\uXXXX` 转义（例如 `"\u5269\u4F59\u989D\u5EA6"`）。
- `.md` 用 UTF-8（给记事本看的可带 BOM）；`.py`、`.json` 用 UTF-8。
- 改完 `kimi_pet.ps1` 至少做两步验证：
  1. PowerShell 语法：`[System.Management.Automation.Language.Parser]::ParseFile(...)`
  2. 真机编译 + 出图：`powershell -NoProfile -ExecutionPolicy Bypass -File kimi_pet.ps1 --shot`
     （内嵌 C# 是运行时编译的，语法没错不代表能编译；`--shot` 会打印 `shot ok` 并写出截图）

## 素材与坐标

- 四张表情必须**同姿态、像素级对齐**（跨图误差 ≤ 2px），否则切换时人物会跳。
  素材流程：`tools/kimi_grid_check2.py`（切图 + 抠图 + 按平板对齐）→ `tools/kimi_make_sprites.py`（缩放并写出 sprite）。
- 平板四角写在 `kimi_pet.ps1` 的 `Relayout()` 里（`qx` / `qy`，顺序 TL, TR, BR, BL，单位是**源图像素**）。
  换素材后必须重算并更新，否则额度数字会落在她手外面。
- 面板位置/大小只改 `tools/kimi_make_assets.py` 顶部的 `PX/PY/PW/PH`，重跑后把 `panel_quad.txt` 里的新值抄进代码。

## 已知坑（都踩过，别再踩）

| 坑 | 说明 |
| --- | --- |
| leveldb 只取第一条记录 | 本地存储的 `.log` 是**追加写**的，同一文件里躺着多枚历史 token。必须扫全部文件、全部记录，取未过期里 `exp` 最大的那枚；只取第一条会让桌宠报"读不到 token" |
| 换表情走 `Relayout()` | 会重算缩放图、红色受击层、命中图并重新分配整屏画布（这台桌面约 100ms 级），扣费动画因此发闷。现用**表情缓存**（`EnsureMoodCache`）+ `_moodChanged` 标记修复，改渲染时别把这条路径弄丢 |
| 把窗口缩成挂件大小 | 试过：能省掉每帧 20MB 推送，但 `飘字带 / 擦除掩码 / 命中图` 全是屏幕坐标系写的，会抛"参数无效"。要做必须先审计所有相关矩形 |
| 写死的停靠角 | `SyncWindowModeInternal()` 里曾把停靠位置写死成左下，`corner=right` 时一换表情就被拽回左边。任何重排路径都要走同一套停靠计算 |
| 轮询与扣费节奏 | 轮询 10s（`DSHPET_POLL_MS`），扣费 cue 间隔 0.2s（`CueGapSec`）。两者别混为一谈 |
| **自检用例依赖真实时钟** | `--topup` 的「animation tail」按**像素**比对基准图，而基准图是在表情被 tick 更新前抓的：夜间换脸一开，最终帧的退避脸变成"担忧"，整个立绘都算成"残留"（23:00 后必 FAIL，2026-10-11 踩到）。离线诊断必须钉死退避脸：`_nightOn = false; SetExpression(EXPR_HAPPY);` |

## 文档同步

功能、行为或口径有任何变化，同步更新：

- `README.md` 的「特性」「展示口径」「常见问题」「版本历史」
- `安装说明.md` 对应小节（接口字段表、日志对照表、排错）
- 涉及素材生成方式时，更新 `art/Kimi差分立绘-生成提示词.md`

## 提交

- 小步提交，中文提交信息，直接提 `main`
- 只改必要文件；`tools/dev/` 是历史记录，**不要**继续往里加新脚本
