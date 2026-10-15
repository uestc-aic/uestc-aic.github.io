# DESIGN.md · AI 芯动力 · UESTC AIC

> 一张硅片的克制与秩序：米白纸面之上，走线有去向，每个像素都知道自己为什么在那里。

---

## 1. Visual Theme & Atmosphere

**Style**: Silicon Editorial（硅基编辑风）—— 瑞士网格的冷静秩序 × 芯片版图的工程质感 × 校园刊物的纸面温度

**Keywords**: 走线 · 焊盘 · 光刻网格 · 米白纸面 · 深松绿 · 留白 · 单色强调 · 等宽标注

**Tone**: 克制、精确、可信、有工程味 —— NOT 赛博朋克 / 霓虹渐变 / 玻璃拟态堆叠 / AI 紫色光晕 / 3D 悬浮卡片 / 全息投影

**Feel**: 像翻开一份排版精良的芯片设计手册——纸是暖的，线条是冷的，每个标注都为了被读懂，而不是为了好看。

**Interaction Tier**: L2 流畅交互（入场 fade+rise、滚动 reveal、信号走线动画、导航状态切换、弹窗）
**Dependencies**: CSS only + 原生 JS（零构建、零 npm、零 CDN 框架）。字体走 Google Fonts，失败时回退系统中文字族。

### 与既有站的延续性（重要）

本规范**继承** `uestc-aic.github.io` v1 的视觉身份，不推翻：
- 主色 深松绿 `#203d32` / 纸面 `#fafbf6` / 黄绿 `#d6e6b7` 原样保留
- 字体对 `Space Grotesk`（拉丁展示）+ `DM Sans`（拉丁正文）保留
- 首页芯片 SVG 插画的语言（走线 + 焊盘 + die 标注）升级为全站图形系统

**新增**（本次「科技感 × 芯片特色」增补）：光刻网格底纹、晶圆 die-map 图形、信号脉冲动效、等宽技术标注体系、深色 Silicon 反色区段。

---

## 2. Color Palette & Roles

```css
:root {
  /* Backgrounds */
  --bg: #fafbf6;              /* 页面背景 · 暖米白（纸） */
  --surface: #ffffff;         /* 卡片/容器 */
  --surface-alt: #f0f2e9;     /* 交替 section · 浅苔绿灰 */
  --surface-sunken: #edf1e4;  /* 图形底 · 内嵌视窗 */
  --surface-hover: #e7eddb;   /* 悬停态表面 */

  /* Borders */
  --border: #dfe4d8;          /* 默认边框 · 1px 发丝线 */
  --border-strong: #c9d2bd;   /* 强调边框 */
  --border-hover: #a7b98a;    /* 悬停边框 */

  /* Text */
  --text: #203d32;            /* 主文字 · 深松绿（近黑） */
  --text-secondary: #788277;  /* 正文、描述 */
  --text-tertiary: #98a08a;   /* 标签、页脚、辅助信息 */

  /* Accent */
  --accent: #355c43;          /* 主强调 · 森林绿（CTA、链接、活跃态） */
  --accent-hover: #365c43;
  --accent-soft: #d6e6b7;     /* 黄绿高光 · 选中背景、脉冲点 */
  --accent-warm: #c1744d;     /* 单一暖强调 · 仅用于「正在发生/提醒」 */

  /* Silicon（深色反色区段专用） */
  --silicon-bg: #193b32;      /* 芯片深绿底 */
  --silicon-bg-deep: #122b25; /* 更深 · 页脚/深色区渐变端 */
  --silicon-ink: #edf2df;     /* 深色区主文字 */
  --silicon-muted: #b3c0a5;   /* 深色区次文字 */
  --silicon-line: #d3dfb5;    /* 深色区发丝线（用 40% 不透明度） */
  --silicon-lime: #c3d99d;    /* 深色区高光 */

  /* RGB variants for rgba() */
  --bg-rgb: 250, 251, 246;
  --text-rgb: 32, 61, 50;
  --accent-rgb: 53, 92, 67;
  --silicon-rgb: 25, 59, 50;

  /* Semantic */
  --success: #6b8c49;
  --warning: #c1744d;
  --error: #a8453a;
}
```

**Color Rules:**
- 所有颜色必须通过 CSS 变量引用，**组件内禁止硬编码 hex**（图形 SVG 允许直接用变量引用 `currentColor` / `var()`）
- 每个 section 内**只允许一个强调色**；`--accent-warm` 全站预算 ≤ 3 处，仅标注「进行中 / 临近截止」
- 深色 Silicon 区段全站**最多 2 处**（首页 join-panel + 页脚），避免视觉疲劳
- 饱和度纪律：**任何颜色的 S 值不超过 45%**（`#c1744d` 是唯一例外且为低饱和陶土橙）。禁止纯蓝 `#00f`、禁止紫粉渐变

---

## 3. Typography Rules

**Font Stack:**
```css
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

--sans:    'DM Sans', 'Microsoft YaHei', 'PingFang SC', 'Noto Sans SC', sans-serif;
--display: 'Space Grotesk', 'Microsoft YaHei', 'PingFang SC', sans-serif;
--mono:    'JetBrains Mono', 'SFMono-Regular', Consolas, monospace;
--serif:   'Songti SC', 'SimSun', serif;   /* 仅用于中文伙伴名 3 处 */
```

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|------|------|------|--------|-------------|----------------|
| Hero H1 (桌面) | display | clamp(44px, 6vw, 64px) | 600 | 1.20 | −0.045em |
| Hero H1 (移动) | display | clamp(34px, 10vw, 44px) | 600 | 1.30 | −0.03em |
| Hero 衬线强调 | display | 1.16em (相对 H1) | 500 | 1.10 | −0.06em |
| Page H2 | sans | 34px | 600 | 1.35 | −1.1px |
| Section H2 | sans | 28px | 600 | 1.40 | −0.8px |
| H3 | sans | 19px | 600 | 1.45 | −0.4px |
| Body | sans | 14px | 400 | 1.75 | 0.01em |
| Body (长文页) | sans | 15px | 400 | 1.85 | 0.02em |
| Label / 标签 | display | 11px | 500 | 1.4 | 0.08em |
| Kicker / 眉标 | display | 10px | 500 | 1.4 | 0.14em |
| Tech 标注 | mono | 9px | 400 | 1.6 | 0.10em |
| Card 描述 | sans | 12px | 400 | 1.85 | 0.01em |

**Typography Rules:**
- 中文内容行高**不得低于 1.7**；中文正文加 `letter-spacing: 0.02em`
- H1/H2/H3 一律**负字距**（大字号要紧）；>24px 标题 `letter-spacing` 必须为负
- 标题一律 **sentence case / 中文照写**，不人为大写
- 技术标注（`FIG. 001`、`VOL. 01`、`AI × IC`）统一走 `--mono` + 宽字距，**全站大写**
- **NEVER use**: Comic Sans、Papyrus、Arial Black、Impact、任何"科技感"特效字体（Orbitron/Rajdhani/Audiowide）；禁止用 `font-weight: 900`
- 同屏字体家族 ≤ 2（display + sans）；mono 仅出现于 ≤9px 标注位

**Text Decoration:**
- Hero H1：**无渐变、无描边、无投影**。"AI × IC" 用字号与颜色（`--accent`）拉开层次，不用渐变色
- 无 text-shadow（全站禁止）；链接下划线用 1px `--border-strong`，hover 转 `--accent`

---

## 4. Component Stylings

### Buttons
```css
.button {
  display: inline-flex; align-items: center; justify-content: center; gap: 30px;
  padding: 13px 23px; border: 1px solid var(--text); border-radius: 5px;
  background: var(--text); color: var(--bg);
  font: 500 13px/1 var(--sans); letter-spacing: 0.02em;
  transition: background 200ms ease, transform 200ms ease, border-color 200ms ease;
}
.button:hover  { background: var(--accent-hover); border-color: var(--accent-hover); transform: translateY(-2px); }
.button:active { transform: translateY(0); }
.button:focus-visible { outline: 2px solid var(--accent); outline-offset: 3px; }
.button[disabled], .button[aria-disabled="true"] { opacity: .45; cursor: not-allowed; transform: none; }
.button span { font-size: 19px; line-height: 1; }        /* ↗ 箭头 */

.button-outline { background: transparent; color: var(--text); border-color: var(--border-strong); }
.button-outline:hover { background: var(--surface-hover); border-color: var(--border-hover); color: var(--text); }

.button-light { background: var(--accent-soft); border-color: var(--accent-soft); color: var(--silicon-bg); }  /* 仅深色区 */
.button-light:hover { background: #e7efcf; border-color: #e7efcf; }

.text-button { display: inline-flex; align-items: center; gap: 22px; padding: 0;
  font: 500 13px/1 var(--sans); color: var(--text); }
.text-button span { font-size: 19px; transition: transform 200ms ease; }
.text-button:hover span { transform: translate(2px, -2px); }
.text-button:focus-visible { outline: 2px solid var(--accent); outline-offset: 4px; }
```

### Cards
```css
.card {
  border: 1px solid var(--border); border-radius: var(--radius, 12px);
  background: var(--surface); padding: 24px;
  transition: border-color 200ms ease, background 200ms ease;
}
.card:hover { border-color: var(--border-hover); }
.card:focus-within { border-color: var(--accent); }
```

### Navigation
```css
.header { position: sticky; top: 0; z-index: 20; height: 90px;
  background: rgb(var(--bg-rgb) / .92); border-bottom: 1px solid var(--border);
  backdrop-filter: blur(16px); }
.header.is-scrolled { height: 72px; box-shadow: 0 12px 40px rgb(var(--text-rgb) / .06); }
.nav a { position: relative; color: var(--text-secondary); font-size: 13px; transition: color 200ms ease; }
.nav a:hover, .nav a[aria-current="page"] { color: var(--text); }
.nav a[aria-current="page"]::after { content: ''; position: absolute; left: 0; right: 0; bottom: -8px;
  height: 2px; background: var(--accent); border-radius: 2px; }
```

### Links
```css
a { color: inherit; text-decoration: none; }
.prose a { color: var(--accent); border-bottom: 1px solid var(--border-strong); }
.prose a:hover { border-bottom-color: var(--accent); }
```

### Tags / Badges
```css
.tag { display: inline-flex; align-items: center; gap: 6px; padding: 4px 10px;
  border: 1px solid var(--border); border-radius: 4px;
  font: 400 10px/1.4 var(--sans); color: var(--text-secondary); }
.tag--active { background: var(--accent-soft); border-color: var(--accent-soft);
  color: var(--silicon-bg); font-weight: 500; }
.status-dot { width: 5px; height: 5px; border-radius: 50%; background: var(--success); }
.status-dot--soon { background: var(--accent-warm); }
```

### 芯片图形系统（本次新增 · 全站复用的 4 个 motif）
```css
/* (1) 光刻网格底纹 —— 用于页面顶部/深色区，永远 ≤12% 不透明度 */
.litho-grid { position: absolute; inset: 0; pointer-events: none;
  background-image:
    linear-gradient(rgb(var(--accent-rgb) / .06) 1px, transparent 1px),
    linear-gradient(90deg, rgb(var(--accent-rgb) / .06) 1px, transparent 1px);
  background-size: 72px 72px;
  mask-image: linear-gradient(to bottom, #000 0%, transparent 78%);
}

/* (2) 走线脉冲 —— 信号沿 die 走线流动 */
.trace-pulse { stroke-dasharray: 10 120; animation: trace 7s linear infinite; }
@keyframes trace { to { stroke-dashoffset: -260; } }

/* (3) 焊盘阵列 —— 触点矩阵，用于 section 分隔 */
.pad-row { display: flex; gap: 7px; }
.pad-row i { width: 5px; height: 5px; border-radius: 1px; background: var(--border-strong); }

/* (4) Die Map —— 晶圆分区图，用于活动/资源分类的视觉锚点 */
.die-map { display: grid; gap: 3px; }
.die-map span { aspect-ratio: 1; border: 1px solid var(--border); border-radius: 2px; }
.die-map span.is-on { background: var(--accent-soft); border-color: var(--accent-soft); }
```

### Empty State（本次新增 · 采集空态的统一表达）
```css
.empty-state { padding: 52px 32px; text-align: center;
  border: 1px dashed var(--border-strong); border-radius: 10px; background: var(--surface-alt); }
.empty-state .trace-figure { width: 96px; margin: 0 auto 14px; color: var(--border-strong); }
```

---

## 5. Layout Principles

**Container:**
- Max width: `1240px`（>1450px 视口）/ `1200px`（默认）
- Padding: `calc(100% - 112px)` 桌面 → `- 72px` (≤1100px) → `- 48px` (≤850px) → `- 40px` (≤620px)
- Narrow variant（长文正文页）: `760px`

**Spacing Scale:** `4 / 8 / 12 / 16 / 24 / 32 / 48 / 64 / 80`
- Section padding: `80px 0`（桌面）/ `60px`（≤850px）/ `47px`（≤620px）
- Component gap: `24px`
- Card internal padding: `24px`（紧凑卡 20px）

**Grid:**
```css
.grid-2 { display: grid; grid-template-columns: repeat(2, 1fr); gap: 24px; }
.grid-3 { display: grid; grid-template-columns: repeat(3, 1fr); gap: 22px; }
.grid-4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 20px; }
@media (max-width: 850px) { .grid-2, .grid-3, .grid-4 { grid-template-columns: 1fr; } }
```

**页面骨架统一**（每个子页面必须遵守，保证跨页一致）：
```
header (sticky, 90px)
  └ page-hero：kicker(眉标) + h1 + 一句导语 + 可选筛选/统计条
  └ [正文区 section × N]
footer (深色 Silicon 或浅色，全站唯一)
```

---

## 6. Depth & Elevation

| Level | Treatment | Use |
|-------|-----------|-----|
| Flat | 无阴影 | 所有 section、卡片默认态、表格 |
| Hairline | `1px solid var(--border)` | 卡片、分隔、输入框 |
| Subtle | `0 12px 40px rgb(var(--text-rgb) / .06)` | sticky 导航（滚动后） |
| Overlay | `0 30px 100px rgb(18 45 48 / .17)` | 弹窗 dialog 唯一使用者 |

**Elevation Rules:**
- **卡片禁止阴影**，只用 1px 发丝线 + hover 变色（本设计身份的核心纪律）
- 除 dialog 外**全站不出现第二处投影**
- 深色 Silicon 区段不用投影，用 1px `--silicon-line` 40% 描边区分

---

## 7. Animation & Interaction

**Motion Philosophy**: 像示波器上的信号——只在有信息变化时出现，干脆、短促、不弹跳（**禁止回弹缓动**）。
**Tier**: L2

### Dependencies
无。纯 CSS + 原生 JS（`IntersectionObserver`）。**不引入 GSAP / Framer Motion / 任何动画库。**

### Base Setup
```js
// 统一的入场 reveal：只做 opacity + translateY(12px)，不改布局属性
const prefersReduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const io = new IntersectionObserver((entries) => {
  entries.forEach(e => { if (e.isIntersecting) { e.target.classList.add('is-in'); io.unobserve(e.target); } });
}, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });
if (!prefersReduced) document.querySelectorAll('[data-reveal]').forEach(el => io.observe(el));
else document.querySelectorAll('[data-reveal]').forEach(el => el.classList.add('is-in'));
```

### Entrance Animation
```css
[data-reveal] { opacity: 0; transform: translateY(12px);
  transition: opacity 480ms cubic-bezier(.22,.61,.36,1), transform 480ms cubic-bezier(.22,.61,.36,1); }
[data-reveal].is-in { opacity: 1; transform: none; }
[data-reveal][data-delay="1"] { transition-delay: 60ms; }
[data-reveal][data-delay="2"] { transition-delay: 120ms; }
[data-reveal][data-delay="3"] { transition-delay: 180ms; }
```

### Scroll Behavior
- Sticky 导航：滚动 > 40px 加 `.is-scrolled`（高度 90→72px + subtle 阴影）
- 章节眉标滚动进入时数字递进（纯 CSS `is-in` 触发，不做数字滚动动画）
- 长文页右侧自动生成目录（`<details>`，移动端折叠）

### Hover & Focus States
- 所有可交互元素**必须有 hover + focus-visible**（focus 用 `outline: 2px solid var(--accent); outline-offset: 3px`），禁止 `outline: none`
- 卡片 hover：边框转 `--border-hover`，**不移动、不放大**
- 链接 hover：下划线颜色转 `--accent`
- 走线脉冲：仅首页 hero 与 section 分隔处，7s 线性无限循环

### Special Effects
- **信号走线脉冲**：仅 hero SVG 与 3 条 hero 走线（`.trace-pulse`），尊重 `prefers-reduced-motion`
- 无光标跟随、无视差滚动、无页面转场、无粒子背景（明确排除，避免廉价科技感）
- 深色区入口：`--silicon-bg` 区段入场仅 fade，不做遮罩位移

### Reduced Motion
```css
@media (prefers-reduced-motion: reduce) {
  html { scroll-behavior: auto; }
  *, *::before, *::after { animation-duration: .001ms !important; animation-iteration-count: 1 !important; transition-duration: .001ms !important; }
  [data-reveal] { opacity: 1 !important; transform: none !important; }
}
```

---

## 8. Do's and Don'ts

### Do
1. **发丝线优先于阴影** —— 结构靠 1px `--border` 表达，层次靠留白和 `--surface-alt` 色块，不靠投影
2. **等宽标注讲工程感** —— `FIG. 002`、`VOL. 01`、`AIC / SALON` 这类 mono 小标注是全站"芯片味"的主要来源，用宽字距（0.10em+）+ 全大写
3. **数字与索引显式可见** —— 章节用 `01 / 02 / 03` 编号（mono），让页面像手册而不是宣传页
4. **中文优先排版** —— 行高 ≥1.7、字距 0.02em，标题负字距；先保证中文好看再加拉丁效果
5. **图形用内联 SVG** —— 所有芯片/走线/晶圆图形写成内联 SVG，零图片请求、可换色、可动画、可无障碍标注（`role="img"` + `aria-label`）
6. **深色区段克制** —— Silicon 深绿区全站 ≤2 处，且必须承载真实内容（报名 CTA、页脚），不做纯装饰深色块
7. **每个页面都有可操作出口** —— 每页至少 1 个通往「活动 / 资源 / 投稿 / 加入」的 CTA
8. **响应式先想手机** —— 内容全部单列可读，表格横向可滚，导航折叠为汉堡

### Don't
- ❌ **禁止霓虹/赛博朋克**：不出现 `#0ff`、`#f0f`、发光文字 `text-shadow`、扫描线、CRT 噪点
- ❌ **禁止紫色 AI 渐变**：不出现 `linear-gradient(135deg, #667eea, #764ba2)` 这类"AI 味"渐变
- ❌ **禁止玻璃拟态堆叠**：全站 `backdrop-filter` 只允许出现在 sticky 导航（1 处），卡片禁玻璃
- ❌ **禁止卡片投影**：除 dialog 外任何元素不得有 `box-shadow` 带位移阴影
- ❌ **禁止 emoji 当图标**：不用 🚀✨💡🔥 做图标或装饰；图形一律内联 SVG
- ❌ **禁止弹跳/回弹缓动**：不用 `cubic-bezier(.68,-.55,.27,1.55)` 等 overshoot 曲线
- ❌ **禁止三字体混用**：同屏字体家族 ≤2（display + sans）
- ❌ **禁止渐变色文字**：`background-clip: text` 全站禁用
- ❌ **禁止「AI 生成感」占位**：不写 Lorem ipsum，不写"这里是描述文字"；内容未定时用明确占位（`待公布`）并高亮可填写位
- ❌ **禁止动画驱动布局**：不动 `width/height/top/left`，只动 `opacity` / `transform`
- ❌ **禁止超长单行文本**：正文容器 >760px 必须收窄或分栏
- ❌ **禁止把数据写死在 HTML**：所有活动/资源/伙伴/项目数据来自 `content/*.json`，由 `scripts/build.py` 注入
- ❌ **禁止 Google Fonts 阻塞渲染**：字体失败必须能回退到系统中文族并保持可用（`font-display: swap`）

---

## 9. Responsive Behavior

**Breakpoints:**
| Name | Width | Key Changes |
|------|-------|-------------|
| Wide | > 1450px | container 1240px；hero 字号 64px；图形区 max 550px |
| Desktop | 1100–1450px | container 1200px；hero 两栏；网格 3–4 列 |
| Tablet | 850–1100px | hero 字号 45px；网格 2–3 列；导航间距收紧 |
| Mobile-L | 620–850px | 网格全单列；导航折叠为汉堡 + 抽屉；hero 字号 36–44px |
| Mobile-S | < 620px | container 减 40px；hero 单栏；表格转卡片；`resource-row` 隐藏 source 列 |
| Tiny | < 360px | 字号再降一档；隐藏次级信息（统计条、页脚中间列） |

**Touch Targets:** minimum **44×44px**（导航项、筛选按钮、卡片箭头、弹窗关闭按钮）
**Collapsing Strategy:**
- 导航 → 汉堡按钮（`aria-expanded` 驱动，`Escape` 关闭，外层点击关闭，≥621px 自动复位）
- 筛选条 → `flex: 1` 等分横向排列，允许横向滚动
- 表格（资源库/竞赛） → 移动端转卡片，丢弃低优先级列（来源、分类）
- 事件时间线 → 竖轴上单列，日期在标题上方

```css
/* 内容长度纪律 */
.prose { max-width: 760px; }
.page-hero { padding-top: 64px; padding-bottom: 48px; }
@media (max-width: 850px) { .page-hero { padding-top: 44px; padding-bottom: 34px; } }
```

---

*DESIGN.md v1.0 · 2026-10-15 · 由 Hermes 依据 `web-design` skill 两阶段流程产出，Phase C 代码生成须严格遵循本规范并对照 `references/quality-checklist.md` 自审。*
