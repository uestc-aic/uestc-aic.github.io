#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
AI 芯动力 · UESTC AIC 官网 —— 静态站点生成器
================================================

零依赖（仅 Python 标准库），把 content/*.json 与 assets/ 渲染成 dist/。

设计基线
--------
本文件的标记结构与类名**对齐仓库既有设计系统**（assets/css/style.css，
令牌 --paper/--white/--ink/--muted/--blue/--blue-dark/--blue-soft/--line），
不另立一套。新增页面只在其基础上扩展组件，保证跨页视觉一致。

三条纪律
--------
1. **内容与代码分离**：会变的东西都在 content/*.json，运维不碰 Python。
2. **生成物可丢弃**：docs/ 是产物（也是 GitHub Pages 的发布目录），随时可由本脚本重建。
3. **图标用 SVG sprite**：全站 `<symbol>` 定义一次，`<use>` 引用，不用 emoji。

用法
----
    python3 scripts/build.py            # 生成 dist/
    python3 scripts/build.py --clean    # 先清空 dist/ 再生成
    python3 scripts/build.py --check    # 只校验内容，不生成
"""

import json
import re
import sys
import shutil
import html as htmllib
from pathlib import Path
from datetime import datetime, timezone, timedelta

ROOT = Path(__file__).resolve().parent.parent
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
DIST = ROOT / "docs"   # 发布目录：GitHub Pages 支持从分支的 /docs 直接发布，无需工作流

CN_TZ = timezone(timedelta(hours=8))
NOW = datetime.now(CN_TZ)

CATEGORIES = {
    "salon":       {"label": "芯沙龙",   "en": "SALON"},
    "regular":     {"label": "常规活动", "en": "REGULAR"},
    "campus":      {"label": "学院资讯", "en": "CAMPUS"},
    "competition": {"label": "竞赛信息", "en": "COMPETITION"},
}

STATUS = {
    "tbd":      {"label": "待定",     "cls": "status-tbd"},
    "upcoming": {"label": "即将开始", "cls": "status-upcoming"},
    "ongoing":  {"label": "进行中",   "cls": "status-ongoing"},
    "past":     {"label": "已结束",   "cls": "status-past"},
}

RESOURCE_CATEGORIES = {
    "ai4eda":        {"label": "AI for EDA",   "en": "AI4EDA"},
    "ic-design":     {"label": "IC 设计",      "en": "IC DESIGN"},
    "eda-tool":      {"label": "EDA 工具",     "en": "EDA TOOLS"},
    "ai-agent":      {"label": "AI / Agent",   "en": "AI AGENT"},
    "course":        {"label": "课程教程",     "en": "COURSE"},
    "paper-list":    {"label": "论文清单",     "en": "PAPER LIST"},
    "dataset-model": {"label": "数据集/模型",  "en": "DATASET"},
    "workflow":      {"label": "工作流",       "en": "WORKFLOW"},
    "community":     {"label": "社区竞赛",     "en": "COMMUNITY"},
}


# ══════════════════════════════════════════════════════════════════
# 基础工具
# ══════════════════════════════════════════════════════════════════

def esc(value) -> str:
    """转义为安全的 HTML 文本。所有来自 JSON 的字符串都必须过这里。"""
    return htmllib.escape(str(value if value is not None else ""), quote=True)


def safe_url(value) -> str:
    """只放行 http(s) 链接，挡掉 javascript: 之类的注入。"""
    value = str(value or "").strip()
    return esc(value) if re.match(r"^https?://", value, re.I) else ""


def load(name, default=None):
    path = CONTENT / f"{name}.json"
    if not path.exists():
        warn(f"缺少内容文件 content/{name}.json，已按空处理")
        return default if default is not None else {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        die(f"content/{name}.json 不是合法 JSON：{exc}")


_WARNINGS = []


def warn(msg):
    _WARNINGS.append(msg)
    print(f"  [警告] {msg}")


def die(msg):
    print(f"  [错误] {msg}")
    sys.exit(1)


def rel(depth: int) -> str:
    """按页面目录深度生成资源前缀。depth=0 → ''，depth=1 → '../'。"""
    return "../" * depth


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


# ══════════════════════════════════════════════════════════════════
# 极简 Markdown 渲染（只支持本站实际用到的语法，行为可预期）
# ══════════════════════════════════════════════════════════════════

def md_inline(text: str) -> str:
    text = esc(text)
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", text)
    text = re.sub(r"`([^`]+?)`", r"<code>\1</code>", text)

    # 图片必须在链接之前处理，否则 ![alt](url) 会被链接规则吃成 !<a>
    def _img(m):
        url = safe_url(m.group(2))
        if not url:
            return m.group(1)
        alt = re.sub(r"<[^>]*>", "", m.group(1))
        return f'<img src="{url}" alt="{alt}" loading="lazy" decoding="async">'
    text = re.sub(r"!\[([^\]]*?)\]\((https?://[^\s)]+)\)", _img, text)

    def _link(m):
        url = safe_url(m.group(2))
        return (f'<a href="{url}" target="_blank" rel="noopener noreferrer">{m.group(1)}</a>'
                if url else m.group(1))
    return re.sub(r"\[([^\]]+?)\]\((https?://[^\s)]+)\)", _link, text)


def render_md(text: str) -> str:
    """Markdown → HTML。支持 h2/h3、段落、有序/无序列表、引用、表格、水平线、围栏代码块。"""
    if not text or not text.strip():
        return ""
    out, lines, i = [], text.replace("\r\n", "\n").split("\n"), 0
    while i < len(lines):
        raw = lines[i]
        s = raw.strip()

        if not s:
            i += 1
            continue

        # 围栏代码块
        if s.startswith("```"):
            lang = s[3:].strip()
            buf, i = [], i + 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            cls = f' class="lang-{esc(lang)}"' if lang else ""
            out.append(f"<pre><code{cls}>{esc(chr(10).join(buf))}</code></pre>")
            continue

        if re.fullmatch(r"-{3,}", s):
            out.append("<hr>")
            i += 1
            continue

        # 独占一行的图片 → <figure>（可带 *说明文字* 作为图注）
        img = re.fullmatch(r"!\[([^\]]*?)\]\((https?://[^\s)]+)\)", s)
        if img:
            url = safe_url(img.group(2))
            alt = img.group(1)
            caption = ""
            if i + 1 < len(lines) and lines[i + 1].strip().startswith("*") \
                    and lines[i + 1].strip().endswith("*") and not lines[i + 1].strip().startswith("**"):
                caption = lines[i + 1].strip().strip("*")
                i += 1
            if url:
                fig = (f'<figure class="photo"><img src="{url}" alt="{esc(alt)}" '
                       f'loading="lazy" decoding="async">')
                if caption:
                    fig += f"<figcaption>{esc(caption)}</figcaption>"
                out.append(fig + "</figure>")
            i += 1
            continue

        m = re.match(r"^(#{2,4})\s+(.*)$", s)
        if m:
            lvl = len(m.group(1))
            out.append(f'<h{lvl}>{md_inline(m.group(2))}</h{lvl}>')
            i += 1
            continue

        if s.startswith("|") and i + 1 < len(lines) and re.match(r"^\|[\s:|-]+\|$", lines[i + 1].strip()):
            header = [c.strip() for c in s.strip("|").split("|")]
            rows, i = [], i + 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            thead = "".join(f"<th>{md_inline(c)}</th>" for c in header)
            tbody = "".join("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>"
                            for r in rows)
            out.append('<div class="table-wrap"><table><thead><tr>'
                       f'{thead}</tr></thead><tbody>{tbody}</tbody></table></div>')
            continue

        if s.startswith(">"):
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.append(f'<blockquote>{" ".join(md_inline(b) for b in buf)}</blockquote>')
            continue

        if re.match(r"^\d+\.\s+", s):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append(md_inline(re.sub(r"^\d+\.\s+", "", lines[i].strip())))
                i += 1
            out.append("<ol>" + "".join(f"<li>{x}</li>" for x in items) + "</ol>")
            continue

        if re.match(r"^[-*+]\s+", s):
            items = []
            while i < len(lines) and re.match(r"^[-*+]\s+", lines[i].strip()):
                items.append(md_inline(re.sub(r"^[-*+]\s+", "", lines[i].strip())))
                i += 1
            out.append("<ul>" + "".join(f"<li>{x}</li>" for x in items) + "</ul>")
            continue

        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#{2,4}\s|[-*+]\s|\d+\.\s|>|\||```|-{3,}$)", lines[i].strip()
        ):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.append(f'<p>{" ".join(md_inline(b) for b in buf)}</p>')
    return "\n".join(out)


# ══════════════════════════════════════════════════════════════════
# 图标：SVG sprite（定义一次，全站 <use> 引用）
# 新增图标只在这里加一条 <symbol>，页面写 icon("名字") 即可。
# ══════════════════════════════════════════════════════════════════

SPRITE_SYMBOLS = {
    "arrow":    '<path d="M5 19 19 5M5 5h14v14"/>',
    "arrow-r":  '<path d="M4 12h15m-6-7 7 7-7 7"/>',
    "down":     '<path d="M12 4v16m-7-7 7 7 7-7"/>',
    "chip":     '<rect x="5" y="5" width="14" height="14" rx="2"/><rect x="9" y="9" width="6" height="6" rx="1"/>'
                '<path d="M9 2v3m6-3v3M9 19v3m6-3v3M2 9h3m-3 6h3m14-6h3m-3 6h3"/>',
    "clock":    '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
    "pin":      '<path d="M19 10c0 5-7 11-7 11S5 15 5 10a7 7 0 1 1 14 0Z"/><circle cx="12" cy="10" r="2.5"/>',
    "book":     '<path d="M12 5v15M3 4c3-1 6-1 9 1 3-2 6-2 9-1v15c-3-1-6-1-9 1-3-2-6-2-9-1Z"/>',
    "terminal": '<rect x="3" y="4" width="18" height="16" rx="2"/><path d="m7 9 3 3-3 3m6 0h4"/>',
    "globe":    '<circle cx="12" cy="12" r="9"/><ellipse cx="12" cy="12" rx="4" ry="9"/><path d="M3 12h18"/>',
    "agent":    '<path d="m12 2 2.5 6.5L21 11l-6.5 2.5L12 20l-2.5-6.5L3 11l6.5-2.5Z"/>'
                '<path d="m20 16 1 2 2 1-2 1-1 2-1-2-2-1 2-1Z"/>',
    "git":      '<circle cx="7" cy="5" r="2"/><circle cx="7" cy="19" r="2"/><circle cx="17" cy="5" r="2"/>'
                '<path d="M7 7v10m10-10v2a5 5 0 0 1-5 5H7"/>',
    "route":    '<rect x="2" y="3" width="6" height="6" rx="1"/><rect x="16" y="15" width="6" height="6" rx="1"/>'
                '<path d="M8 6h8a3 3 0 0 1 0 6H8a3 3 0 0 0 0 6h8"/>',
    "users":    '<circle cx="9" cy="8" r="3"/><path d="M3 21v-3a6 6 0 0 1 12 0v3m2-16a3 3 0 0 1 0 6m1 4a5 5 0 0 1 3 5"/>',
    "search":   '<circle cx="10.5" cy="10.5" r="6.5"/><path d="m16 16 5 5"/>',
    "github":   '<path d="M9 19c-4 1.5-4-2.5-6-3m12 5v-3.5c0-1 .1-1.4-.5-2 2.8-.3 4.5-1.4 4.5-4.8 0-1-.4-2-1-2.6.1-.3.5-1.3-.1-2.6 0 0-1-.3-3.3 1.2a11 11 0 0 0-5.8 0C6.5 5.2 5.5 5.5 5.5 5.5c-.6 1.3-.2 2.3-.1 2.6-.6.6-1 1.5-1 2.6 0 3.4 1.7 4.5 4.5 4.8-.5.5-.5 1.1-.5 2V21"/>',
    "share":    '<path d="M12 16V4M8 8l4-4 4 4"/><path d="M4 16v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2"/>',
    "layers":   '<path d="m12 3 9 5-9 5-9-5 9-5Z"/><path d="m3 13 9 5 9-5"/>',
    "flag":     '<path d="M5 21V4M5 4h11l-1.6 4L16 12H5"/>',
    "check":    '<path d="m5 13 4 4 10-11"/>',
    "close":    '<path d="M6 6l12 12M18 6 6 18"/>',
    "info":     '<circle cx="12" cy="12" r="9"/><path d="M12 11v5m0-8.5v.5"/>',
    "copy":     '<rect x="9" y="9" width="12" height="12" rx="2"/><path d="M5 15V5a2 2 0 0 1 2-2h8"/>',
    "file":     '<path d="M14 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V8Z"/><path d="M14 3v5h5"/>',
    "plug":     '<path d="M9 2v6M15 2v6M6 8h12v3a6 6 0 0 1-12 0Z"/><path d="M12 17v5"/>',
}


def sprite() -> str:
    body = "".join(f'<symbol id="icon-{k}" viewBox="0 0 24 24">{v}</symbol>'
                   for k, v in SPRITE_SYMBOLS.items())
    return f'<svg class="icon-definitions" xmlns="http://www.w3.org/2000/svg" aria-hidden="true"><defs>{body}</defs></svg>'


def icon(name: str, extra_class: str = "") -> str:
    """引用 sprite 里的图标。art 级图形不用这个，用内联 SVG。"""
    if name not in SPRITE_SYMBOLS:
        warn(f"图标 {name} 不存在于 sprite，已用 info 兜底")
        name = "info"
    cls = f"icon {extra_class}".strip()
    return f'<svg class="{cls}" aria-hidden="true"><use href="#icon-{name}"/></svg>'


# ══════════════════════════════════════════════════════════════════
# 页面骨架
# ══════════════════════════════════════════════════════════════════

BRAND_MARK = ('<span class="brand-mark">'
              '<svg class="icon" aria-hidden="true"><use href="#icon-chip"/></svg></span>')


def header(site: dict, depth: int, active: str) -> str:
    p = rel(depth)
    links = []
    for item in site.get("nav", []):
        label = item.get("label", "")
        href = item.get("href", "")
        if depth == 0 and href == "index.html":
            href = ""
        cls = ' class="current"' if label == active else ""
        links.append(f'<a href="{p}{esc(href)}"{cls}>{esc(label)}</a>')
    github = safe_url(site.get("github"))
    join = f"{p}join/index.html"
    return f"""<header class="header"><div class="container nav-wrap">
    <a class="brand" href="{p}index.html" aria-label="{esc(site.get("nameFull"))}首页">{BRAND_MARK}<span class="brand-name">{esc(site.get("name"))}<span>{esc(site.get("nameEn"))}</span></span></a>
    <nav class="nav" id="navigation" aria-label="主导航">{"".join(links)}</nav>
    <div class="nav-actions"><a class="github-link" href="{github}" target="_blank" rel="noopener noreferrer" aria-label="GitHub 社区，在新窗口打开">{icon("github")}</a><a class="button button-small" href="{join}">加入我们{icon("arrow")}</a><button class="menu-button" aria-label="打开导航" aria-expanded="false" aria-controls="navigation"><span></span><span></span></button></div>
  </div></header>"""


def footer(site: dict, depth: int) -> str:
    p = rel(depth)
    github = safe_url(site.get("github"))
    return f"""<footer class="footer"><div class="container footer-top">
    <a class="brand" href="{p}index.html">{BRAND_MARK}<span class="brand-name">{esc(site.get("name"))}<span>{esc(site.get("nameEn"))}</span></span></a>
    <p>{esc(site.get("footerNote"))}</p>
    <nav class="footer-links" aria-label="页脚导航">
      <a href="{p}events/index.html">活动</a>
      <a href="{p}resources/index.html">资源库</a>
      <a href="{p}partners/index.html">合作伙伴</a>
      <a href="{p}contribute/index.html">投稿</a>
      <a href="{p}docs/index.html">运维手册</a>
      <a href="{github}" target="_blank" rel="noopener noreferrer">GitHub{icon("arrow")}</a>
    </nav>
  </div><div class="container footer-bottom">
    <span>© {NOW.year} {esc(site.get("nameFull"))}．Built with curiosity.</span>
    <span>{esc(site.get("university"))} · {esc(site.get("college"))}</span>
    <span>内容更新于 {esc(site.get("updated", ""))}</span>
  </div></footer>"""


def page(site: dict, depth: int, active: str, title: str, description: str, body: str) -> str:
    p = rel(depth)
    full = f"{title} · {site.get('nameFull')}" if title else site.get("nameFull")
    desc = description or site.get("description", "")
    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="{esc(site.get("themeColor", "#f6f8fc"))}">
<meta name="description" content="{esc(desc)}">
<title>{esc(full)}</title>
<meta property="og:title" content="{esc(full)}">
<meta property="og:description" content="{esc(desc)}">
<meta property="og:type" content="website">
<link rel="icon" href="{p}assets/img/favicon.svg" type="image/svg+xml">
<link rel="preload" href="{p}assets/fonts/ma-shan-zheng-headings.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{p}assets/css/style.css?v=20261016-fonts">
<script src="{p}assets/js/app.js" defer></script>
</head>
<body>
{sprite()}
<a class="skip-link" href="#main">跳转到主要内容</a>
{header(site, depth, active)}
<main id="main">
{body}
</main>
{footer(site, depth)}
<div class="toast" id="toast" role="status" aria-live="polite"></div>
</body>
</html>"""


def page_hero(kicker: str, title: str, lead: str = "", aside: str = "", counts=None) -> str:
    """子页面统一页头：眉标 + 标题 + 导语 + 右侧统计。"""
    counts_html = ""
    if counts:
        items = "".join(f'<div class="hero-stat"><b>{esc(str(n))}</b><span>{esc(l)}</span></div>'
                        for n, l in counts)
        counts_html = f'<div class="page-hero-stats">{items}</div>'
    lead_html = f'<p class="hero-description">{lead}</p>' if lead else ""
    return f"""<section class="page-hero">
  <div class="litho-grid" aria-hidden="true"></div>
  <div class="container page-hero-inner">
    <div class="page-hero-copy"><p class="section-label">{esc(kicker)}</p><h1>{title}</h1>{lead_html}</div>
    {counts_html}{aside}
  </div>
</section>"""


def section_open(kicker: str, title: str, aside: str = "", sid: str = "", alt: bool = False) -> str:
    id_attr = f' id="{sid}"' if sid else ""
    cls = "section section-alt" if alt else "section"
    aside_html = f'<p class="section-aside">{aside}</p>' if aside else ""
    return f"""<section class="{cls}"{id_attr}>
  <div class="container">
    <div class="section-heading"><div><p class="section-label">{esc(kicker)}</p><h2>{title}</h2></div>{aside_html}</div>"""


def section_close() -> str:
    return "  </div>\n</section>"


def empty_state(title: str, desc: str, label: str = "", href: str = "", icon_name: str = "layers") -> str:
    action = (f'<a class="text-button" href="{esc(href)}">{esc(label)}{icon("arrow")}</a>'
              if label else "")
    return f"""<div class="empty-state" data-reveal>{icon(icon_name)}
  <h3>{esc(title)}</h3><p>{esc(desc)}</p>{action}</div>"""


def pending(value) -> str:
    if not value or str(value).strip() in ("", "待公布", "待定", "TBD", "tbd"):
        return '<span class="pending">待公布</span>'
    return esc(value)


# ══════════════════════════════════════════════════════════════════
# 数据装配
# ══════════════════════════════════════════════════════════════════

def load_collected() -> list:
    """读取 content/collected/*.json（采集器产出）。目录缺失视为没有数据。"""
    folder = CONTENT / "collected"
    if not folder.is_dir():
        return []
    items = []
    for path in sorted(folder.glob("*.json")):
        if path.name.startswith("_"):      # _state.json / _anomalies.json 不是内容
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            warn(f"collected/{path.name} 不是合法 JSON，已跳过")
            continue
        for it in (data.get("items") or []):
            it.setdefault("category", "campus")
            it.setdefault("status", "tbd")
            it.setdefault("source", {"name": data.get("source_name", data.get("source_id", "外部来源")),
                                     "url": it.get("url", "")})
            items.append(it)
    items.sort(key=lambda x: str(x.get("date") or ""), reverse=True)
    return items


def all_events(events: dict, collected: list) -> list:
    """人工维护的 events.json + 采集条目，按 URL / 标题去重合并。"""
    manual = events.get("items", [])
    urls = {e.get("url") for e in manual if e.get("url")}
    titles = {str(e.get("title", "")).strip() for e in manual}
    merged = list(manual)
    for it in collected:
        if it.get("url") in urls or str(it.get("title", "")).strip() in titles:
            continue
        # 标记来源，让卡片知道该链到详情页（人工条目）还是原文（采集条目）
        it["_from_collector"] = True
        merged.append(it)
    return merged


def filter_events(items: list, category: str) -> list:
    return [e for e in items if e.get("category") == category]


def read_page_md(name: str) -> str:
    """读 content/pages/<name>.md，也支持仓库内相对路径（如 ../manuals/运维手册.md）。"""
    if not name:
        return ""
    for candidate in (CONTENT / "pages" / name, ROOT / name):
        if candidate.exists():
            return candidate.read_text(encoding="utf-8")
    return ""


def resource_icon_name(r: dict) -> str:
    """按分类给资源选图标（sprite 名）。"""
    cat = r.get("category", "")
    return {
        "ai4eda": "chip", "ic-design": "chip", "eda-tool": "route",
        "ai-agent": "agent", "course": "book", "paper-list": "file",
        "dataset-model": "layers", "workflow": "git", "community": "users",
    }.get(cat, "globe")


# ══════════════════════════════════════════════════════════════════
# 芯片图形（内联 SVG：零图片请求、可换色、可动画、可无障碍标注）
# ══════════════════════════════════════════════════════════════════

CHIP_ART_FIGURE = """    <figure class="hero-art" aria-labelledby="chip-caption">
    <div class="art-top"><span><span class="blue-dot"></span>一块芯片，连接更多想法</span><span>AI × IC</span></div>
    <svg class="chip-art" viewBox="0 0 560 440" fill="none" role="img" aria-label="以同一中心对齐的 AI 与 IC 芯片电路示意图">
    <defs><pattern id="circuit-grid" width="24" height="24" patternUnits="userSpaceOnUse"><path d="M24 0H0v24" stroke="#dce6fa" stroke-width=".7"/></pattern></defs>
    <path fill="url(#circuit-grid)" d="M0 0h560v440H0z"/>
    <g stroke="#9cb2e8" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M208 125V84l-32-32H64m168 73V65L211 44h-73m118 81V20m24 105V60l32-32h66m-74 97V90l52-52h126m-154 87v-22l37-37h131m-123 59V107l48-48h78M185 153h-48L90 106H38m147 71H110l-28-28H20m165 52H36m149 24H68m117 24H99l-28 28H20m165-4h-56l-46 46H38m147-22h-25l-45 45H64M375 153h25l45-45h51m-121 69h56l46-46h45m-147 70h86l28-28h51m-165 52h117m-117 24h149m-149 24h75l28 28h62m-165-4h48l47 47h52M208 315v18l-48 48H64m168-66v22l-37 37H64m192-59v35l-52 52H38m242-87v65l-32 32h-66m122-97v105m24-105v60l21 21h73m-70-81v41l32 32h112"/></g>
    <g fill="#f5f8ff" stroke="#9cb2e8" stroke-width="1.5"><circle cx="64" cy="52" r="4"/><circle cx="138" cy="44" r="3"/><circle cx="378" cy="28" r="4"/><circle cx="482" cy="38" r="3"/><circle cx="38" cy="106" r="3"/><circle cx="36" cy="201" r="4"/><circle cx="68" cy="225" r="3"/><circle cx="492" cy="225" r="3"/><circle cx="524" cy="249" r="4"/><circle cx="496" cy="108" r="3"/><circle cx="522" cy="344" r="3"/><circle cx="64" cy="381" r="3"/><circle cx="182" cy="412" r="3"/><circle cx="422" cy="396" r="4"/><circle cx="496" cy="388" r="3"/></g>
    <g stroke="#294fd6" stroke-width="2"><path d="M256 125V20M185 201H36M375 249h149M304 315v105"/></g>
    <g class="chip-pins" stroke="#294fd6" stroke-width="7"><path d="M208 112v13m24-13v13m24-13v13m24-13v13m24-13v13m24-13v13m24-13v13M208 315v13m24-13v13m24-13v13m24-13v13m24-13v13m24-13v13m24-13v13M172 153h13m-13 24h13m-13 24h13m-13 24h13m-13 24h13m-13 24h13m-13 24h13M375 153h13m-13 24h13m-13 24h13m-13 24h13m-13 24h13m-13 24h13m-13 24h13"/></g>
    <rect class="chip-body" x="185" y="125" width="190" height="190" rx="12" fill="#294fd6"/>
    <rect x="198" y="138" width="164" height="164" rx="6" stroke="#819af2"/>
    <path d="M213 167v-14h14m106 0h14v14M213 273v14h14m106 0h14v-14" stroke="#b7c8ff" stroke-width="1.5"/>
    <text class="chip-type" x="280" y="217" fill="white" text-anchor="middle" font-size="40" font-family="Arial,sans-serif" font-weight="600">AI × IC</text>
    <path d="M238 238h84" stroke="#819af2"/>
    <text x="280" y="263" fill="#dce5ff" text-anchor="middle" font-size="13" font-family="Arial,sans-serif" letter-spacing="2">UESTC AIC</text>
    </svg>
    <figcaption id="chip-caption"><span>人工智能</span><span class="caption-line"></span><svg class="icon" aria-hidden="true"><use href="#icon-chip"/></svg><span class="caption-line"></span><span>集成电路</span></figcaption>
    </figure>"""

POSTER_CIRCUIT = """<svg viewBox="0 0 300 100" fill="none" aria-hidden="true">
  <path d="M0 62h46l16-16h44M106 46h38l14 14h42M200 60h44l16-16h40M0 30h30l18 18h40M88 48h26l18 18h44M176 66h30"
        stroke="currentColor" stroke-width="1.3"/>
  <circle cx="46" cy="62" r="3" fill="currentColor"/><circle cx="106" cy="46" r="3" fill="currentColor"/>
  <circle cx="200" cy="60" r="3" fill="currentColor"/><circle cx="48" cy="48" r="3" fill="currentColor"/>
  <rect x="128" y="30" width="40" height="40" rx="5" stroke="currentColor" stroke-width="1.4"/>
  <rect x="139" y="41" width="18" height="18" rx="2" fill="currentColor" opacity=".45"/>
</svg>"""


def workflow_visual() -> str:
    return (f'<div class="workflow-node">{icon("agent")}<span>AI 需求</span></div>'
            f'<div class="workflow-link"></div>'
            f'<div class="workflow-node node-highlight node-type"><span>IC</span></div>'
            f'<div class="workflow-link"></div>'
            f'<div class="workflow-node">{icon("chip")}<span>芯片实践</span></div>')


def die_map(seed: int = 3) -> str:
    cells = "".join('<span class="%s"></span>' % ("is-on" if ((i * 7 + seed) % 5) < 2 else "")
                    for i in range(48))
    return f'<div class="die-map" aria-hidden="true">{cells}</div>'


# ══════════════════════════════════════════════════════════════════
# 组件
# ══════════════════════════════════════════════════════════════════


def event_destination(ev: dict, depth: int):
    """返回 (href, is_external, label)。
    人工维护的条目有独立详情页；采集来的条目没有详情页，直接链到原文。
    """
    p = rel(depth)
    eid = ev.get("id")
    url = safe_url(ev.get("url"))
    if ev.get("_from_collector"):
        if url:
            return url, True, "查看原文"
        return f"{p}contribute/index.html", False, "提供线索"
    if eid:
        return f"{p}events/{esc(eid)}/index.html", False, "查看详情"
    if url:
        return url, True, "查看原文"
    return f"{p}events/index.html", False, "查看活动"


def event_title_html(ev: dict, depth: int) -> str:
    href, external, _ = event_destination(ev, depth)
    attrs = ' target="_blank" rel="noopener noreferrer"' if external else ""
    return f'<a href="{href}"{attrs}>{esc(ev.get("title"))}</a>'


def status_badge(ev: dict) -> str:
    st = STATUS.get(ev.get("status", "tbd"), STATUS["tbd"])
    return f'<span class="status {st["cls"]}"><i></i>{esc(st["label"])}</span>'


def category_label(ev: dict) -> str:
    return CATEGORIES.get(ev.get("category", ""), {"label": "活动"})["label"]


def event_card(ev: dict, depth: int, featured: bool = False) -> str:
    """活动列表卡片（活动日历 / 学院资讯 / 竞赛页共用）。"""
    p = rel(depth)
    detail, external, more_label = event_destination(ev, depth)
    more_attrs = ' target="_blank" rel="noopener noreferrer"' if external else ""
    src = ev.get("source") or {}
    meta = []
    if ev.get("dateText") or ev.get("date"):
        meta.append(f'<span>{icon("clock")}{esc(ev.get("dateText") or ev.get("date"))}</span>')
    if ev.get("location") and ev["location"] != "待公布":
        meta.append(f'<span>{icon("pin")}{esc(ev["location"])}</span>')
    source_html = ""
    if src.get("url"):
        source_html = (f'<a class="event-source" href="{safe_url(src["url"])}" target="_blank" '
                       f'rel="noopener noreferrer">{esc(src.get("name", "外部来源"))}{icon("arrow")}</a>')
    cls = "event-card event-card-featured" if featured else "event-card"
    title = event_title_html(ev, depth)
    return f"""<article class="{cls}" data-filter-item data-filter-cat="{esc(ev.get("category", ""))}" data-reveal>
    <div class="event-card-top"><span class="event-card-cat">{esc(category_label(ev))}</span>{status_badge(ev)}</div>
    <h3 class="event-card-title">{title}</h3>
    <p class="event-card-desc">{esc(ev.get("summary", ""))}</p>
    <div class="event-card-meta">{"".join(meta)}</div>
    {source_html}
    <a class="text-button event-card-more" href="{detail}"{more_attrs}>{esc(more_label)}{icon("arrow")}</a>
  </article>"""


def featured_event(ev: dict, depth: int) -> str:
    """首页大卡：海报式（复用既有 .featured-event / .event-poster 组件）。"""
    p = rel(depth)
    detail, external, _ = event_destination(ev, depth)
    more_attrs = ' target="_blank" rel="noopener noreferrer"' if external else ""
    meta = []
    if ev.get("dateText") or ev.get("date"):
        meta.append(f'<span>{icon("clock")}{esc(ev.get("dateText") or ev.get("date"))}</span>')
    if ev.get("location"):
        meta.append(f'<span>{icon("pin")}{esc(ev["location"])}</span>')
    meta.append(f'<span>{icon("users")}{esc(ev.get("organizer", "AI 芯动力（UESTC AIC）"))}</span>')
    vol = ev.get("vol") or "VOL. 01"
    return f"""<article class="featured-event" data-reveal>
      <div class="event-poster">
        <p class="poster-series">{esc(ev.get("titleEn") or "COMMUNITY SALON")} · {esc(vol)}</p>
        <p class="poster-title">{esc(ev.get("title"))}</p>
        <div class="poster-circuit">{POSTER_CIRCUIT}</div>
        <div class="poster-bottom"><span>{esc(ev.get("category") == "salon" and "从一个问题开始" or "活动")}</span><span>AI × IC</span></div>
      </div>
      <div class="event-copy">{status_badge(ev)}<h3>{esc(ev.get("title"))}</h3>
        <p>{esc(ev.get("summary", ""))}</p>
        <div class="event-meta">{"".join(meta)}</div>
        <a class="text-button" href="{detail}">查看活动详情{icon("arrow")}</a>
      </div>
    </article>"""


def next_event_card(ev: dict, depth: int) -> str:
    """首页「下一期」预告卡（复用既有 .next-event / .preview-topics）。"""
    p = rel(depth)
    detail, external, _ = event_destination(ev, depth)
    more_attrs = ' target="_blank" rel="noopener noreferrer"' if external else ""
    topics = "".join(f'<li><span>{i + 1:02d}</span>{esc(t)}</li>'
                     for i, t in enumerate((ev.get("topics") or [])[:4]))
    return f"""<article class="next-event" data-reveal>
      <p class="section-label">下一期 · 预告</p>
      <h3>{esc(ev.get("title"))}</h3>
      <ul class="preview-topics">{topics}</ul>
      <p class="next-note">{esc(ev.get("summary", ""))}</p>
      <a class="text-button" href="{detail}">看看候选主题{icon("arrow")}</a>
    </article>"""


def resource_row(r: dict) -> str:
    """资源库列表行（对齐既有 .resource-row 五列网格）。"""
    cat = RESOURCE_CATEGORIES.get(r.get("category", ""), {"label": "资源"})
    search = " ".join([str(r.get("title", "")), str(r.get("titleZh", "")),
                       str(r.get("description", "")), str(r.get("source", "")),
                       " ".join(r.get("tags") or [])]).lower()
    zh = f' <span class="resource-zh">{esc(r.get("titleZh"))}</span>' if r.get("titleZh") else ""
    stars = r.get("stars") or 0
    source = esc(r.get("source", ""))
    if stars:
        source += f' · ★{stars:,}'
    return f"""<a class="resource-row" href="{safe_url(r.get("url"))}" target="_blank" rel="noopener noreferrer"
   data-filter-item data-filter-cat="{esc(r.get("category", ""))}" data-search="{esc(search)}"
   aria-label="{esc(r.get("title"))}，在新窗口打开">
    <span class="resource-icon">{icon(resource_icon_name(r))}</span>
    <div><h3>{esc(r.get("title"))}{zh}</h3><p>{esc(r.get("description", ""))}</p></div>
    <span class="resource-category">{esc(cat["label"])}</span>
    <span class="resource-source">{source}</span>
    <span class="resource-out">{icon("arrow")}</span>
  </a>"""


def featured_resource(r: dict) -> str:
    """精选资源卡（对齐既有 .featured-resource 三列网格）。"""
    cat = RESOURCE_CATEGORIES.get(r.get("category", ""), {"label": "资源"})
    host = r.get("host") or re.sub(r"^https?://", "", str(r.get("url", ""))).split("/")[0]
    return f"""<a class="featured-resource resource-item" href="{safe_url(r.get("url"))}" target="_blank" rel="noopener noreferrer"
     data-filter-item data-filter-cat="{esc(r.get("category", ""))}"
     data-search="{esc((str(r.get("title", "")) + " " + str(r.get("description", ""))).lower())}"
     aria-label="{esc(r.get("title"))}，在新窗口打开">
    <span class="featured-icon">{icon(resource_icon_name(r))}</span>
    <div class="featured-details"><p class="featured-label">{esc(r.get("label") or cat["label"])}</p>
      <h3>{esc(r.get("title"))}</h3><p>{esc(r.get("description", ""))}</p>
      <span class="site-host">{esc(host)}</span></div>
    {icon("arrow")}
  </a>"""


def partner_card(pt: dict) -> str:
    name = pt.get("name", "")
    name_html = (f'<span class="partner-serif">{esc(name)}</span>'
                 if pt.get("type") in ("class", "studio") and len(name) <= 4 else esc(name))
    url = safe_url(pt.get("url"))
    link = (f'<a class="text-button" href="{url}" target="_blank" rel="noopener noreferrer">'
            f'官网{icon("arrow")}</a>') if url else ""
    relation = pt.get("relationship", "洽谈中")
    rel_cls = "is-done" if relation == "已合作" else "is-wip"
    tags = "".join(f'<span>{esc(t)}</span>' for t in (pt.get("tags") or []))
    return f"""<article class="partner-card" data-reveal>
    <div class="partner-card-top"><span class="partner-abbr">{esc(pt.get("abbr") or name)}</span>
      <span class="partner-rel {rel_cls}">{esc(relation)}</span></div>
    <h3>{name_html}</h3>
    <p class="partner-en">{esc(pt.get("nameEn") or pt.get("nameZh") or "")}</p>
    <p class="partner-intro">{esc(pt.get("intro", ""))}</p>
    <div class="partner-tags">{tags}</div>
    {link}
  </article>"""


def org_card(o: dict) -> str:
    """组织架构卡（对齐既有 .organization-grid article）。"""
    return f"""<article data-reveal>
    <span class="department-symbol">{icon("layers")}</span>
    <span class="department-size">{esc(o.get("size"))}</span>
    <h3>{esc(o.get("name"))}</h3><p>{esc(o.get("duty"))}</p></article>"""


def project_card(pr: dict, detail: bool = False) -> str:
    extra = ""
    if detail:
        extra = (f'<dl class="info-dl"><dt>探索方向</dt><dd>{esc(pr.get("direction"))}</dd>'
                 f'<dt>当前进度</dt><dd>{esc(pr.get("progress"))}</dd></dl>')
    tags = "".join(f'<span>{esc(t)}</span>' for t in (pr.get("tags") or []))
    return f"""<article class="project-card" data-reveal>
    <div class="project-visual">{workflow_visual()}</div>
    <div class="project-copy"><p class="project-meta"><span>{esc(pr.get("code"))}</span><span>{esc(pr.get("size"))}</span></p>
      <h3>{esc(pr.get("title"))}</h3><p>{esc(pr.get("intro"))}</p>{extra}
      <div class="project-tags">{tags}</div></div>
  </article>"""


def quick_links(site: dict) -> str:
    """首页 hero 下方三条快速入口（复用既有 .quick-links）。"""
    p = ""
    data = [
        ("agent", "发现芯沙龙", "活动日历 · 预告与回顾", f"{p}events/index.html"),
        ("book", "打开资源库", "AI × IC 工具与课程", f"{p}resources/index.html"),
        ("users", "认识合作伙伴", "学院 · 班级 · 工作室", f"{p}partners/index.html"),
    ]
    items = "".join(
        f'<a href="{href}">{icon(i)}<div><strong>{t}</strong><span>{d}</span></div>{icon("arrow", "quick-arrow")}</a>'
        for i, t, d, href in data)
    return f'<div class="quick-links container" data-reveal>{items}</div>'


def filter_buttons(cats_present: dict, all_label: str = "全部") -> str:
    """筛选按钮（对齐既有 .resource-filters / .resource-filter）。"""
    btns = [f'<button class="resource-filter active" type="button" data-filter-btn data-filter-key="all" aria-pressed="true">{esc(all_label)}<span class="filter-count" data-filter-count></span></button>']
    for key, meta in cats_present:
        btns.append(f'<button class="resource-filter" type="button" data-filter-btn data-filter-key="{key}" aria-pressed="false">{esc(meta)}<span class="filter-count" data-filter-count></span></button>')
    return '<div class="resource-filters" role="group" aria-label="分类筛选">' + "".join(btns) + "</div>"


# ══════════════════════════════════════════════════════════════════
# 首页
# ══════════════════════════════════════════════════════════════════

def build_home(site, events, partners, projects, org, resources, collected) -> str:
    items = all_events(events, collected)
    salons = filter_events(items, "salon")
    featured = next((e for e in salons if e.get("status") in ("upcoming", "ongoing")),
                    salons[0] if salons else None)
    next_salon = next((e for e in salons if e is not featured), None)
    latest = [e for e in items if e.get("category") in ("campus", "competition")][:5]
    res_items = resources.get("items", [])
    featured_res = [r for r in res_items if r.get("featured")][:2]
    top_res = sorted([r for r in res_items if not r.get("featured")],
                     key=lambda r: -(r.get("stars") or 0))[:6]

    hero = f"""<section class="hero container" id="home">
    <div class="hero-copy"><p class="hero-label"><span class="live-dot"></span>{esc(site.get("university"))} · AI for IC 社区</p>
      <h1>一起探索<br>AI × IC 的可能</h1>
      <p class="hero-description">让 AI 成为手中的工具，让想法走向真实的项目。<br class="desktop-break">从第一次使用 Agent，到一起探索集成电路。</p>
      <div class="hero-buttons"><a class="button" href="events/index.html">看看近期活动{icon("arrow")}</a><a class="text-button" href="resources/index.html">从学习资源开始{icon("down")}</a></div>
      <p class="hero-note">带上好奇心，和我们一起动手。</p></div>
{CHIP_ART_FIGURE}
  </section>
{quick_links(site)}"""

    events_block = section_open("近期活动", "见面，让想法发生。",
                                "芯沙龙 · 常规活动 · 学院资讯 · 竞赛信息 · 全部活动入口") + f"""
    <div class="events-grid">{featured_event(featured, 0) if featured else ''}{next_event_card(next_salon, 0) if next_salon else ''}</div>
    <p class="project-footnote">{icon("info")}<span>完整列表（含自动同步的学院资讯与竞赛信息）在 <a class="inline-link" href="events/index.html">活动日历</a>。</span></p>
""" + section_close()

    about_block = f"""<section class="about-section" id="about"><div class="container section">
    <div class="about-introduction">
      <div><p class="section-label">关于社团</p><h2>因好奇相聚，<br>在实践中连接。</h2></div>
      <div><p>{esc(site.get("nameFull"))} 是 {esc(site.get("college"))} 的 AI for IC 开放技术社区。
      我们从 AI 工具应用出发，探索人工智能与集成电路的交叉实践。</p>
      <p>三件事：让工具真正用起来、一起走进 IC 的世界、把经验留给下一个人。
      落点就是芯沙龙、项目组，以及这个持续更新的网站。</p>
      <a class="text-button" href="about/index.html">了解我们的组织{icon("arrow")}</a></div>
    </div>
    <div class="organization-heading"><h3>组织架构</h3><span>从内容、活动到知识沉淀</span></div>
    <div class="organization-grid">{"".join(org_card(o) for o in org.get("items", []))}</div>
    <p class="organization-note">{" · ".join(esc(n) for n in org.get("notes", []))}</p>
  </div></section>"""

    projects_block = f"""<section class="projects-section" id="projects"><div class="container section">
    <div class="section-heading"><div><p class="section-label">项目实践</p><h2>好想法，值得动手。</h2></div>
      <p class="section-aside">项目孵化方向 · 欢迎跨组参与</p></div>
    <div class="projects-grid">{"".join(project_card(pr) for pr in projects.get("items", []))}</div>
    <p class="project-footnote">{icon("info")}<span>{esc(projects.get("footnote", ""))}</span></p>
  </div></section>"""

    feat_html = "".join(featured_resource(r) for r in featured_res)
    feat_block = ""
    if feat_html:
        feat_block = (f'<h3 class="resource-subheading">社区精选 <span>同学自己整理的笔记与课程</span></h3>'
                      f'<div class="featured-resources">{feat_html}</div>')
    res_block = f"""<section class="section" id="resources"><div class="container">
    <div class="section-heading"><div><p class="section-label">学习资源</p><h2>少走弯路，一起进步。</h2></div>
      <a class="text-button" href="resources/index.html">全部 {len(res_items)} 份资源{icon("arrow")}</a></div>
    {feat_block}
    <div class="library-heading"><h3 class="resource-subheading">资源库 <span>按用途分类，全部实测可访问</span></h3></div>
    <div class="resource-list">{"".join(resource_row(r) for r in top_res)}</div>
    <div class="resource-bottom"><span>显示 {len(top_res)} / {len(res_items)} 份资源</span><span>提交于 content/resources.json</span></div>
  </div></section>"""

    campus_block = ""
    if latest:
        rows = "".join(
            f'<a class="news-row" href="{esc(e.get("url") or ("events/" + str(e.get("id")) + "/index.html"))}"'
            f'{" target=_blank rel=noopener noreferrer" if e.get("url") else ""}>'
            f'<span class="news-date">{esc(e.get("date_text") or e.get("date") or "")}</span>'
            f'<span class="news-title">{esc(e.get("title"))}</span>'
            f'<span class="news-cat">{esc(category_label(e))}</span></a>' for e in latest)
        campus_block = section_open("学院与竞赛", "来自学院的动态",
                                    "自动同步校级公开信息源，保留原文链接", "campus", alt=True) + \
            f'\n    <div class="news-list">{rows}</div>\n' + section_close()

    partner_block = f"""<section class="section"><div class="container"><div class="partners">
    <div><h3>连接更多同行者</h3><span>合作交流筹备中</span></div>
    <div class="partner-names">{"".join(f'<span>{esc(pt.get("short") or pt.get("abbr") or pt.get("name"))}</span>' for pt in partners.get("items", []))}</div>
    <a class="text-button" href="partners/index.html">合作详情{icon("arrow")}</a>
  </div></div></section>"""

    join_block = f"""<section class="join-section container"><div class="join-panel" data-reveal>
    <div><p class="section-label">加入我们</p><h2>下一个想法，<br>一起实现。</h2>
      <p>对 AI 或 IC 感兴趣，就从这里开始。项目组、活动筹备、内容策划都需要人。</p></div>
    <div class="join-action"><span>不需要任何前置经验</span>
      <a class="button" href="join/index.html">加入 AI 芯动力{icon("arrow")}</a></div>
  </div></section>"""

    body = "\n".join([hero, events_block, about_block, projects_block, res_block,
                      campus_block, partner_block, join_block])
    return page(site, 0, "首页", "", site.get("description", ""), body)


# ══════════════════════════════════════════════════════════════════
# 活动日历 + 活动详情 + 学院资讯 + 竞赛
# ══════════════════════════════════════════════════════════════════

def build_events_index(site, events, collected) -> str:
    items = all_events(events, collected)
    counts = {k: len(filter_events(items, k)) for k in CATEGORIES}
    cats = [(k, v["label"]) for k, v in CATEGORIES.items()]
    cards = "".join(event_card(e, 1, featured=(e.get("category") == "salon"
                                               and e.get("status") in ("upcoming", "ongoing")))
                    for e in items)
    if not cards:
        cards = ""
    empty = empty_state("该分类下暂时没有内容", "换一个分类看看，或向我们提供线索。",
                        "投稿一条线索", "../contribute/index.html", "search")
    body = page_hero("Club Activities", "活动日历",
                     "芯沙龙、常规活动、学院资讯与竞赛信息，都在这里。"
                     "学院资讯与竞赛由系统每天自动同步校级公开信息源，并保留原文链接。",
                     counts=[(len(items), "条目"), (counts.get("salon", 0), "芯沙龙"),
                             (counts.get("competition", 0), "竞赛")]) + f"""
<section class="section"><div class="container" data-filter-root>
    {filter_buttons(cats, "全部活动")}
    <div class="events-grid">{"".join([cards])}</div>
    {empty}
  </div></section>"""
    return page(site, 1, "活动", "活动日历",
                "AI 芯动力的芯沙龙、常规活动、学院资讯与竞赛信息。", body)


def build_event_detail(site, ev, depth: int = 2) -> str:
    p = rel(depth)
    cat = CATEGORIES.get(ev.get("category", ""), {"label": "活动", "en": "EVENT"})
    body_html = render_md(read_page_md(ev.get("body", "")))

    panels = []
    speakers = ev.get("speakers") or []
    if speakers:
        rows = "".join(
            f'<dt>{esc(sp.get("role", "嘉宾"))}</dt><dd>{esc(sp.get("name"))}'
            + (f' · {esc(sp.get("title"))}' if sp.get("title") else "")
            + (f' · {esc(sp.get("org"))}' if sp.get("org") else "") + "</dd>" for sp in speakers)
        panels.append(f'<div class="info-panel"><h3>嘉宾与主讲</h3><dl class="info-dl">{rows}</dl></div>')

    topics = ev.get("topics") or []
    if topics:
        li = "".join(f'<li><span>{i + 1:02d}</span>{esc(t)}</li>' for i, t in enumerate(topics))
        panels.append(f'<div class="info-panel"><h3>议题与关键词</h3><ul class="topic-list">{li}</ul></div>')

    links = "".join(
        f'<a class="button button-outline" href="{safe_url(l.get("url"))}" target="_blank" '
        f'rel="noopener noreferrer">{esc(l.get("label", "打开链接"))}{icon("arrow")}</a>'
        for l in (ev.get("links") or []) if safe_url(l.get("url")))

    register = safe_url(ev.get("registerUrl") or site.get("salonRegisterForm"))
    register_html = (f'<a class="button" href="{register}" target="_blank" rel="noopener noreferrer">'
                     f'报名参加{icon("arrow")}</a>') if register else \
                    f'<a class="button" href="{p}join/index.html">关注后续通知{icon("arrow")}</a>'

    photos = ev.get("photos") or []
    gallery = ""
    if photos:
        figs = []
        for ph in photos:
            img = f'{p}assets/img/{esc(str(ph.get("src", "")).lstrip("/"))}'
            alt = ph.get("alt") or ph.get("caption") or ""
            cap = ph.get("caption") or ""
            cap_html = f"<figcaption>{esc(cap)}</figcaption>" if cap else ""
            figs.append(f'<figure class="photo"><img src="{img}" alt="{esc(alt)}" '
                        f'loading="lazy" decoding="async">{cap_html}</figure>')
        credit = ev.get("photoCredit") or ""
        credit_html = f'<p class="photo-credit">{icon("info")}<span>{esc(credit)}</span></p>' if credit else ""
        gallery = ('<section class="photo-gallery-section"><h2>活动现场</h2>'
                   f'<div class="photo-gallery">{"".join(figs)}</div>{credit_html}</section>')

    src = ev.get("source") or {}
    if src.get("url"):
        source_html = (f'<p class="event-source-line">信息来源：<a href="{safe_url(src["url"])}" '
                       f'target="_blank" rel="noopener noreferrer">{esc(src.get("name", "外部来源"))}</a>'
                       f'（本站仅保留结构化字段与原文链接）</p>')
    elif ev.get("locked"):
        source_html = ('<p class="event-source-line">信息来源：人工录入'
                       '（该条目已锁定，自动采集不会覆盖）</p>')
    else:
        source_html = ""

    kicker = f'{cat["en"]} / {esc(ev.get("vol") or "EVENT")}'
    body = page_hero(kicker, esc(ev.get("title")), status_badge(ev),
                     counts=[(ev.get("vol") or cat["en"], cat["label"])]) + f"""
<section class="section"><div class="container"><div class="detail-layout">
    <div class="detail-main prose" data-reveal>
      {body_html or f'<p>{esc(ev.get("summary", ""))}</p>'}
      {"".join(panels)}{source_html}
    </div>
    <aside class="detail-side" data-reveal data-delay="1">
      <div class="info-panel"><p class="section-label">活动信息</p>
        <dl class="info-dl"><dt>时间</dt><dd>{pending(ev.get("dateText") or ev.get("date"))}</dd>
          <dt>地点</dt><dd>{pending(ev.get("location"))}</dd>
          <dt>主办</dt><dd>{esc(ev.get("organizer", "AI 芯动力（UESTC AIC）"))}</dd>
          <dt>分类</dt><dd>{esc(cat["label"])}</dd></dl>
        <div class="detail-actions">{register_html}{links}</div></div>
      <div class="callout">{icon("info")}<p><strong>内容会持续更新。</strong>时间、地点与嘉宾确认后同步到本页。</p></div>
      <a class="text-button detail-back" href="{p}events/index.html">返回活动日历{icon("arrow-r")}</a>
    </aside>
  </div>
  {gallery}
  </div></section>"""
    return page(site, depth, "活动", ev.get("title", "活动"), ev.get("summary", ""), body)


def build_list_page(site, depth, active, kicker, title, lead, items, category,
                    empty_title, empty_desc) -> str:
    rows = [e for e in items if e.get("category") == category]
    p = rel(depth)
    cards = "".join(event_card(e, depth) for e in rows) if rows else \
        empty_state(empty_title, empty_desc, "投稿一条线索", p + "contribute/index.html", "search")
    note = ('<div class="callout callout-warn">' + icon("info") +
            '<p><strong>关于本页内容：</strong>系统每天定时扫描校级公开信息源，条目均标注原文链接；'
            '学院内网通知（需登录或受访问控制）由社区成员投稿补充，投稿后由维护者录入并锁定。'
            f'发现信息有误请通过 <a class="inline-link" href="{p}contribute/index.html">投稿页</a> 告知。</p></div>')
    body = page_hero(kicker, title, lead, counts=[(len(rows), "条目")]) + f"""
<section class="section"><div class="container">
    {note}<div class="events-grid">{cards}</div>
  </div></section>"""
    return page(site, depth, active, title, lead, body)


# ══════════════════════════════════════════════════════════════════
# 资源库
# ══════════════════════════════════════════════════════════════════

def build_resources(site, resources) -> str:
    items = resources.get("items", [])
    featured = [r for r in items if r.get("featured")]
    library = [r for r in items if not r.get("featured")]
    counts = {}
    for r in library:
        counts[r.get("category", "other")] = counts.get(r.get("category", "other"), 0) + 1
    cats = [(k, v["label"]) for k, v in RESOURCE_CATEGORIES.items() if counts.get(k)]
    if counts.get("other"):
        cats.append(("other", "其他"))

    feat_block = ""
    if featured:
        feat_block = ('<h3 class="resource-subheading">社区精选 <span>同学自己整理的笔记、课程与站点</span></h3>'
                      f'<div class="featured-resources">{"".join(featured_resource(r) for r in featured)}</div>')

    empty = empty_state("资源库正在建设", "我们正在整理 AI × IC 方向的优质资料，欢迎你推荐。",
                        "推荐一份资料", "../contribute/index.html", "book")
    body = page_hero("The Shared Toolbox", "资源库",
                     "AI × IC 方向的工具、项目、课程与论文清单。每条都实测可访问，按用途分类。",
                     counts=[(len(items), "份资源"), (len(counts), "个分类")]) + f"""
<section class="section"><div class="container" data-filter-root data-resource-root>
    <div class="resource-toolbar">{filter_buttons(cats, "全部资源")}
      <label class="search-box">{icon("search")}<input type="search" id="resource-search" placeholder="搜索资源、工具、课程…" aria-label="搜索资源"></label>
    </div>
    {feat_block}
    <div class="library-heading"><h3 class="resource-subheading">资源库 <span>按用途分类</span></h3>
      <span data-resource-count role="status" aria-live="polite"></span></div>
    <div class="resource-list">{"".join(resource_row(r) for r in library)}</div>
    {empty}
    <div class="resource-bottom"><span>所有链接均实测可访问</span><span>提交于 content/resources.json（维护方式见运维手册）</span></div>
  </div></section>"""
    return page(site, 1, "资源库", "资源库",
                "AI × IC 方向精选工具、项目、课程与论文清单。", body)


# ══════════════════════════════════════════════════════════════════
# 合作伙伴
# ══════════════════════════════════════════════════════════════════

def build_partners(site, partners) -> str:
    items = partners.get("items", [])
    note = ('<div class="callout callout-warn">' + icon("info") +
            '<p><strong>合作状态说明：</strong>本页伙伴关系目前均为<strong>洽谈中</strong>，尚未正式对外公布。'
            '确认后请把 <code>content/partners.json</code> 中对应的 <code>relationship</code> '
            '改为「已合作」，并补充官方链接与 logo。</p></div>')
    body = page_hero("Partners", "合作伙伴",
                     "连接学院、荣誉班级与学生工作室，让 AI for IC 的实践有更多同路人。",
                     counts=[(len(items), "家伙伴")]) + f"""
<section class="section"><div class="container">
    {note}
    <div class="partners-grid">{"".join(partner_card(pt) for pt in items)}</div>
    <div class="callout" style="margin-top:30px">{icon("share")}
      <p>希望与 AI 芯动力合作？欢迎通过 <a class="inline-link" href="../join/index.html">加入我们</a> 页面与我们联络。</p></div>
  </div></section>"""
    return page(site, 1, "合作伙伴", "合作伙伴",
                "AI 芯动力的合作伙伴：ICSE、钧业班、立人班、芯言工作室、芯传工作室。", body)


# ══════════════════════════════════════════════════════════════════
# 关于 / 项目 / 加入 / 投稿 / 手册 / 404
# ══════════════════════════════════════════════════════════════════

def build_about(site, org, projects) -> str:
    body = page_hero("About Us", "关于 AI 芯动力",
                     f'{esc(site.get("nameFull"))} 是 {esc(site.get("college"))} 的 AI for IC 开放技术社区。') + f"""
<section class="section"><div class="container"><div class="about-split">
    <div class="prose" data-reveal>
      <h2>我们从哪里来</h2>
      <p>AI 芯动力（{esc(site.get("nameEn"))}）从一群对 AI 工具和集成电路同时好奇的同学开始。
      我们发现 AI Agent 已经能实实在在改变查资料、写代码、整理文档的方式，
      而集成电路恰好是最需要「把复杂工具用顺手」的领域之一。</p>
      <h2>我们做什么</h2>
      <p>三件事：<strong>让工具真正用起来</strong>、<strong>一起走进 IC 的世界</strong>、
      <strong>把经验留给下一个人</strong>。落点就是芯沙龙、项目组，以及这个持续更新的网站。</p>
      <h2>内容怎么维护</h2>
      <p>本站所有内容都存在仓库的 <code>content/</code> 目录里，用 JSON 组织；
      提交后由 GitHub Actions 自动构建并发布，无需手动上传网页。
      学院资讯与竞赛信息由采集脚本每天定时同步校级公开信息源，并保留原文链接。
      具体操作见 <a href="../docs/index.html">运维手册</a>。</p>
    </div>
    <aside class="about-side" data-reveal data-delay="1">
      <div class="info-panel"><p class="section-label">基本信息</p>
        <dl class="info-dl"><dt>学校</dt><dd>{esc(site.get("university"))}</dd>
          <dt>学院</dt><dd>{esc(site.get("college"))}</dd>
          <dt>方向</dt><dd>AI × IC（AI for IC）</dd>
          <dt>形式</dt><dd>芯沙龙 · 项目组 · 开放资源库</dd>
          <dt>GitHub</dt><dd><a class="inline-link" href="{safe_url(site.get("github"))}" target="_blank" rel="noopener noreferrer">uestc-aic</a></dd></dl></div>
      <div class="callout">{icon("file")}<p>站点源码、内容与运维手册全部开源，欢迎贡献。</p></div>
    </aside>
  </div></div></section>
""" + section_open("Organization", "组织架构", "从内容、活动到知识沉淀", "organization") + f"""
    <div class="organization-grid">{"".join(org_card(o) for o in org.get("items", []))}</div>
    <p class="organization-note">{" · ".join(esc(n) for n in org.get("notes", []))}</p>
""" + section_close() + f"""
<section class="join-section container"><div class="join-panel" data-reveal>
    <div><p class="section-label">加入我们</p><h2>找到你的位置。</h2>
      <p>不管你想做内容、办活动，还是只想安静地学点东西，这里都有位置。</p></div>
    <div class="join-action"><span>项目组允许非正式成员参加</span>
      <a class="button" href="../join/index.html">加入 AI 芯动力{icon("arrow")}</a></div>
  </div></section>"""
    return page(site, 1, "关于", "关于我们", site.get("description", ""), body)


def build_projects(site, projects) -> str:
    body = page_hero("Learn by Building", "项目实践", esc(projects.get("footnote", ""))) + f"""
<section class="section"><div class="container">
    <div class="projects-grid">{"".join(project_card(pr, detail=True) for pr in projects.get("items", []))}</div>
    <div class="callout" style="margin-top:30px">{icon("users")}
      <p>项目组开放给非正式成员，职能部门成员也可以跨组参与。想加入？请到
      <a class="inline-link" href="../join/index.html">加入我们</a> 页面查看联系方式。</p></div>
  </div></section>"""
    return page(site, 1, "关于", "项目实践", "AI 芯动力的项目孵化方向。", body)


def _channel(icon_name, title, body, value, hint) -> str:
    if value:
        inner = (f'<div class="copy-field"><code>{esc(value)}</code>'
                 f'<button type="button" data-copy="{esc(value)}" data-copy-message="已复制">{icon("copy")}<span>复制</span></button></div>')
    else:
        inner = f'<p class="pending-note">{esc(hint)}</p>'
    return f"""<div class="info-panel" data-reveal>
    <div class="channel-head">{icon(icon_name)}<h3>{esc(title)}</h3></div>
    <p>{esc(body)}</p>{inner}</div>"""


def build_join(site) -> str:
    channels = "".join([
        _channel("github", "GitHub 社区", "关注我们的仓库，站点源码与全部内容都在这里公开。",
                 site.get("github"), "待补：content/site.json 的 github 字段"),
        _channel("users", "QQ 交流群", "进群聊 AI、IC 与项目实践，活动通知也会在群里同步。",
                 site.get("qqGroup"), "待公布 —— 把群链接填入 content/site.json 的 qqGroup"),
        _channel("share", "招新 / 活动报名", "填写报名表加入我们，或报名参加芯沙龙。",
                 site.get("joinForm"), "待公布 —— 把报名表链接填入 content/site.json 的 joinForm"),
    ])
    body = page_hero("Join Us", "加入 AI 芯动力",
                     "对 AI 或 IC 感兴趣，就从这里开始。项目组、活动筹备、内容策划都需要人。") + f"""
<section class="section"><div class="container"><div class="channels">{channels}</div>
    <div class="callout" style="margin-top:26px">{icon("info")}
      <p><strong>还没有正式入口？</strong>先关注 GitHub 仓库，或到
      <a class="inline-link" href="../contribute/index.html">投稿页</a> 给我们留言，我们会联系你。</p></div>
  </div></section>"""
    return page(site, 1, "关于", "加入我们", "加入 AI 芯动力：招新、QQ 群与活动报名入口。", body)


def build_contribute(site) -> str:
    template = "资料标题：\n原始链接：\n内容简介：\n适合人群："
    form = safe_url(site.get("contributeForm"))
    form_html = (f'<a class="button" href="{form}" target="_blank" rel="noopener noreferrer">'
                 f'打开投稿表单{icon("arrow")}</a>') if form else \
                '<p class="pending-note">投稿表单待公布 —— 把链接填入 content/site.json 的 contributeForm。在此期间可通过 GitHub Issue 投稿。</p>'
    body = page_hero("Contribute", "投稿与协作",
                     "把有用的资料留在这里：AI 工具教程、IC 学习资料、活动和竞赛线索，都欢迎。") + f"""
<section class="section"><div class="container"><div class="about-split">
    <div class="prose" data-reveal>
      <h2>可以投稿什么</h2>
      <ul><li><strong>资源库条目</strong>：AI / Agent 工具、IC 学习资料、开源项目、课程与论文清单。</li>
        <li><strong>学院资讯</strong>：学院内部通知、讲座、开放日等（外网抓不到，只能靠投稿）。</li>
        <li><strong>竞赛线索</strong>：报名通知、时间节点、经验分享、组队需求。</li>
        <li><strong>活动记录</strong>：沙龙笔记、项目复盘、踩坑记录。</li></ul>
      <h2>投稿格式</h2>
      <p>按下面四行写就行，我们按这个结构录入 <code>content/</code>：</p>
      <div class="copy-field"><code>资料标题：\n原始链接：\n内容简介：\n适合人群：</code>
        <button type="button" data-copy="{esc(template)}" data-copy-message="投稿格式已复制">{icon("copy")}<span>复制格式</span></button></div>
      <h2>会怎么被使用</h2>
      <p>编辑审核后会进入 <a href="../resources/index.html">资源库</a> 或
      <a href="../events/index.html">活动日历</a>，并保留原始链接与来源标注。投稿不要求你是社区成员。</p>
    </div>
    <aside class="about-side" data-reveal data-delay="1">
      <div class="info-panel"><p class="section-label">投稿入口</p>
        <h3 style="margin-top:12px">提交一份资料</h3><div style="margin-top:16px">{form_html}</div></div>
      <div class="info-panel"><p class="section-label">维护者直接改文件</p>
        <h3 style="margin-top:12px">推荐给有仓库权限的成员</h3>
        <p>直接编辑 <code>content/</code> 下的 JSON 并提交，Actions 会自动重建站点。
        步骤见 <a class="inline-link" href="../docs/index.html">运维手册</a>。</p></div>
    </aside>
  </div></div></section>"""
    return page(site, 1, "关于", "投稿与协作", "向 AI 芯动力投稿资源、学院资讯与竞赛线索。", body)


def build_docs(site) -> str:
    manual = read_page_md("manuals/运维手册.md")
    if not manual:
        # 不要静默失败：路径写错时页面会显示占位，必须让构建者看见
        warn("读不到 manuals/运维手册.md，站内「运维手册」页会显示占位（检查文件是否被移动/改名）")
    body = page_hero("Operations", "运维手册",
                     "怎么更新网站内容、怎么管理采集源、出问题怎么修。") + f"""
<section class="section"><div class="container container-narrow">
    <div class="callout">{icon("file")}<p><strong>本页内容来自仓库 <code>manuals/运维手册.md</code>。</strong>
      改手册 = 改那个文件，提交后自动同步到这里。</p></div>
    <div class="prose manual">{render_md(manual) or '<p class="pending-note">手册尚未生成。</p>'}</div>
  </div></section>"""
    return page(site, 1, "运维手册", "运维手册", "AI 芯动力官网的运维与内容更新手册。", body)


def build_404(site) -> str:
    body = f"""<section class="section" style="padding-block:110px"><div class="container container-narrow" style="text-align:center">
    <p class="section-label">ERROR 404</p>
    <h1 class="notfound-title">走线断了</h1>
    <p class="notfound-lead">这个地址没有对应的走线。可能是链接过期，或者页面搬了家。</p>
    <div class="hero-buttons" style="justify-content:center;margin-top:26px">
      <a class="button" href="index.html">回到首页{icon("arrow")}</a>
      <a class="text-button" href="events/index.html">看看活动{icon("arrow")}</a></div>
  </div></section>"""
    return page(site, 0, "", "页面不存在", "页面不存在", body)


# ══════════════════════════════════════════════════════════════════
# 校验
# ══════════════════════════════════════════════════════════════════

def validate(site, events, partners, projects, org, resources, collected) -> list:
    """构建前体检。返回问题清单（不中断，一次列全让运维一次改完）。"""
    problems, seen = [], set()
    for ev in events.get("items", []):
        eid = ev.get("id")
        if not eid:
            problems.append(f"events.json：有条目缺少 id（标题：{ev.get('title')}）")
            continue
        if eid in seen:
            problems.append(f"events.json：id 重复 —— {eid}")
        seen.add(eid)
        if ev.get("category") not in CATEGORIES:
            problems.append(f"events.json：{eid} 的 category 非法（{ev.get('category')}），"
                            f"只能是 {'/'.join(CATEGORIES)}")
        if ev.get("status") and ev["status"] not in STATUS:
            problems.append(f"events.json：{eid} 的 status 非法（{ev['status']}），"
                            f"只能是 {'/'.join(STATUS)}")
        if ev.get("body") and not read_page_md(ev["body"]):
            problems.append(f"events.json：{eid} 指向的正文 content/pages/{ev['body']} 不存在")
        for l in (ev.get("links") or []):
            if l.get("url") and not safe_url(l["url"]):
                problems.append(f"events.json：{eid} 的链接不是 http(s) —— {l.get('url')}")

    for pt in partners.get("items", []):
        if not pt.get("id"):
            problems.append(f"partners.json：有条目缺少 id（{pt.get('name')}）")
        if pt.get("relationship") not in (None, "", "洽谈中", "筹建", "已合作"):
            problems.append(f"partners.json：{pt.get('id')} 的 relationship 取值异常"
                            f"（{pt.get('relationship')}），只能是 洽谈中/筹建/已合作")

    for r in resources.get("items", []):
        if not safe_url(r.get("url")):
            problems.append(f"resources.json：{r.get('title')} 的 url 非法或缺失")
        if r.get("category") not in RESOURCE_CATEGORIES:
            problems.append(f"resources.json：{r.get('title')} 的 category 未知（{r.get('category')}）")

    for key in ("name", "nameFull", "description"):
        if not site.get(key):
            problems.append(f"site.json：缺少必填字段 {key}")
    return problems


# ══════════════════════════════════════════════════════════════════
# 入口
# ══════════════════════════════════════════════════════════════════

def build() -> int:
    print("AI 芯动力 · 站点构建")
    print("=" * 54)
    site = load("site")
    events = load("events", {"items": []})
    partners = load("partners", {"items": []})
    projects = load("projects", {"items": []})
    org = load("organization", {"items": []})
    resources = load("resources", {"items": []})
    collected = load_collected()

    problems = validate(site, events, partners, projects, org, resources, collected)
    if problems:
        print(f"\n内容校验：发现 {len(problems)} 个问题")
        for pr in problems:
            print(f"  · {pr}")
        print()
    else:
        print("内容校验：通过")

    if "--check" in sys.argv:
        return 1 if problems else 0

    if "--clean" in sys.argv and DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True, exist_ok=True)
    written = []

    def emit(rel_path, content):
        write(DIST / rel_path, content)
        written.append(rel_path)

    emit("index.html", build_home(site, events, partners, projects, org, resources, collected))
    emit("events/index.html", build_events_index(site, events, collected))
    for ev in events.get("items", []):
        if ev.get("id"):
            emit(f"events/{ev['id']}/index.html", build_event_detail(site, ev, 2))

    all_items = all_events(events, collected)
    emit("college/index.html", build_list_page(
        site, 1, "学院资讯", "Campus", "学院资讯",
        "学院内部的通知、讲座与交流活动。外网抓不到的靠社区投稿补充。",
        all_items, "campus", "学院资讯正在整理中", "学院内部信息暂无自动来源，欢迎投稿补充。"))
    emit("competitions/index.html", build_list_page(
        site, 1, "竞赛", "Competitions", "竞赛信息",
        "自动同步校级竞赛通知，保留原文链接；也收社区成员分享的赛事线索。",
        all_items, "competition", "竞赛信息正在整理中", "采集源暂未取到新通知，欢迎提供竞赛线索。"))
    emit("resources/index.html", build_resources(site, resources))
    emit("partners/index.html", build_partners(site, partners))
    emit("about/index.html", build_about(site, org, projects))
    emit("projects/index.html", build_projects(site, projects))
    emit("join/index.html", build_join(site))
    emit("contribute/index.html", build_contribute(site))
    emit("docs/index.html", build_docs(site))
    emit("404.html", build_404(site))
    emit(".nojekyll", "")

    if ASSETS.exists():
        for src in ASSETS.rglob("*"):
            if src.is_file():
                dest = DIST / "assets" / src.relative_to(ASSETS)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dest)

    print(f"\n生成 {len(written)} 个页面：")
    for w in written:
        print(f"  · {w}")
    if _WARNINGS:
        print(f"\n构建告警 {len(_WARNINGS)} 条（见上）")
    print(f"\n输出目录：{DIST}")
    print("完成。")
    return 0


if __name__ == "__main__":
    sys.exit(build())
