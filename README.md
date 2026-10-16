# AI 芯动力 · UESTC AIC

电子科技大学集成电路科学与工程学院 **AI for IC** 社区官网。
原生 HTML / CSS / JavaScript，**零构建依赖**（只用 Python 3 标准库生成静态页）。

线上地址：<https://uestc-aic.github.io/>

## 字体与阅读体验

字母与数字使用本地托管的 Space Grotesk 可变字体；中文主标题使用马善政毛笔楷体（Ma Shan Zheng），中文正文和功能栏目使用系统黑体。书法字体的 Unicode 范围仅覆盖中文及相关标点，避免英文字母误用毛笔字形。正文与描述为 16–18px，长文桌面 18px、手机 17px；日期、来源等辅助文字通常不低于 14px。

字体文件、OFL 开源许可证与下载来源位于 `assets/fonts/`。页面提前加载约 99KB 的中文标题子集和约 22KB 的拉丁字体，访客无需连接外部字体服务。中文子集覆盖当前站点的标题；新增标题后，请同步补充字体字符，或允许新字符回退到系统楷体。没有活动照片时，首页会回退到芯片示意图。

---

## 它长什么样

- **首页**：沙龙现场照片、活动回顾与预告、项目方向、资源库精选、组织架构、合作伙伴、加入入口
- **活动日历** `/events/`：按「芯沙龙 / 常规活动 / 学院资讯 / 竞赛信息」分类筛选
- **活动详情** `/events/<id>/`：每场活动独立页面，支持长文、议题、嘉宾、报名
- **学院资讯** `/college/`：自动同步校级公开信息源 + 社区投稿
- **竞赛信息** `/competitions/`：同上，重点覆盖校内选拔赛通知
- **资源库** `/resources/`：AI × IC 方向的工具、项目、课程、论文清单，分类 + 搜索
- **合作伙伴** `/partners/`：ICSE、钧业班、立人班、芯言工作室、芯传工作室
- **关于 / 项目 / 加入 / 投稿** `/about/` `/projects/` `/join/` `/contribute/`
- **运维手册** `/docs/`：站内可直接查的操作手册

## 架构

```
content/*.json        ← 唯一内容源（运维只改这里）
content/pages/*.md    ← 长文（活动详情、手册）
content/collected/    ← 采集脚本自动写入
content/inbox/        ← 人工投稿暂存
assets/               ← CSS / JS / 图片
sources/sources.json  ← 采集源配置
scripts/build.py      ← 静态生成器（零依赖）
scripts/collect.py    ← 采集器（零依赖）
manuals/              ← 运维手册、采集系统说明（手写文档）
docs/                 ← 构建产物 = GitHub Pages 发布目录
```

统一自动流程：`.github/workflows/pages.yml`（Actions 中显示为 **Update and deploy website**）。

| 触发方式 | 是否采集 | 后续操作 |
|---|---|---|
| 推送到 main | 否 | 运行回归检查 → 生成 `docs/` → 检查全部页面 → 发布 |
| 每天北京时间 03:10 | 是 | 采集 → 生成与检查网页 → 有内容变动才提交 → 在同一次运行中发布 |
| 手动运行 | 可选 | 可选择来源；勾选试运行时不提交、不发布 |

Pages 的 Source 使用 **GitHub Actions**。机器人提交后，在同一次运行中继续发布，不依赖它触发另一条工作流。采集全部失败或网页检查失败时停止，保留已上线版本；部分来源失败会在运行摘要中列出。定时任务可能受 GitHub 排队影响。

`docs/` 继续作为可重建的网页快照保留；自动采集有变动时会一起更新它。直接编辑内容后，线上页面由自动构建产生。

## 本地预览

```bash
python3 scripts/build.py --clean
python3 -m http.server 8000 --directory docs
# 打开 http://localhost:8000
```

不需要 Node、不需要 npm、不需要任何第三方 Python 包。

## 发布保护与交付

日常使用完整克隆的仓库，先同步远端，再编辑并正常提交。普通 Git 推送不可用时，才使用 `scripts/push_via_api.py`；它仅提交 `git add` 后的暂存区内容，默认不删除远端文件。本地版本落后、仓库不完整、关键文件缺失或文件清单读取失败时会停止。具体步骤见 [交付说明](manuals/交付说明.md)。

生成交付包（自动构建、自检并附文件大小及 SHA-256 清单）：

```bash
python3 scripts/package_release.py --output ../uestc-aic-website-delivery.zip
python3 scripts/package_release.py --verify ../uestc-aic-website-delivery.zip
```

ZIP 用于归档与阅读，不包含 Git 历史。不要从解压副本执行推送。新增文件应先加入 Git，再生成交付包。

只校验内容不生成：

```bash
python3 scripts/build.py --check
```

## 我要改内容，从哪开始

看 [`manuals/运维手册.md`](manuals/运维手册.md)。速查：

| 想做的事 | 改哪 |
|---|---|
| 发布/更新活动 | `content/events.json` |
| 加资源 | `content/resources.json` |
| 改伙伴状态 | `content/partners.json` |
| 改 QQ 群 / 报名表 / 投稿表链接 | `content/site.json` |
| 写活动长文 | `content/pages/<id>.md` |
| 换配色 | `assets/css/style.css` 的 `:root` |

**设计规范**全文见 [`DESIGN.md`](DESIGN.md)（配色、字体、组件、动效、
Do's & Don'ts、响应式断点），改样式前请先读它。

## 采集系统的边界（重要）

- 能自动抓：`news.uestc.edu.cn`、`gr.uestc.edu.cn`（含竞赛实践栏目）、
  `jwc.uestc.edu.cn`、`uestc.edu.cn`、电赛培训网、数模竞赛网等**校级公开、服务端渲染**的源。
- **抓不到**：`icse.uestc.edu.cn`（集成电路科学与工程学院官网）全站启用了
  JS 挑战型 WAF，程序直连一律返回 `HTTP 412`。**学院内部信息走人工投稿**，
  在 `content/events.json` 里以 `locked: true` 录入，采集永不覆盖。
- 合规：串行抓取、间隔 ≥3 秒、遵守 `robots.txt`、只存结构化字段 + 原文链接不转载全文。

细节见 [`manuals/采集系统说明.md`](manuals/采集系统说明.md)。

## 环境要求

- 本地与 CI：Python 3.12；生成、采集、测试及打包只用标准库
- 日常维护与生成交付包需要 Git；API 推送备用工具另需已登录的 GitHub CLI

## 参考

- <https://uestc-ia.github.io/> —— 社团站点结构与开源社区入口的组织方式
- <https://github.com/pyzw618/UESTC-Teamup> —— 竞赛信息采集的思路与流水线设计
  （Fetcher → 编码处理 → Differ → Parser → Matcher → Guard → Publisher）

## 许可

站点内容版权归 AI 芯动力（UESTC AIC）所有。
