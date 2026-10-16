#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
站点构建产物自检
================

只做静态检查、不联网，用来在推送前抓出「断链 / 结构错 / 重复 id / 外链没标 noopener」
这类只在浏览器里才暴露的问题。

用法：
    python3 scripts/build.py && python3 scripts/verify.py

退出码：0 = 全部通过；1 = 有问题（CI 里可以直接当门禁）
"""

import re
import sys
from pathlib import Path
from html.parser import HTMLParser

ROOT = Path(__file__).resolve().parent.parent
DIST = ROOT / "docs"

VOID_TAGS = {"area", "base", "br", "col", "embed", "hr", "img", "input",
             "link", "meta", "param", "source", "track", "wbr"}

# 这些页面路径深度与目录深度不一致，是已知的例外
DEPTH_EXCEPTIONS = {"404.html": 0}


class PageCheck(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.stack = []
        self.errors = []
        self.ids = []
        self.links = []
        self.srcs = []
        self.external_noopener = []

    def handle_starttag(self, tag, attrs):
        d = dict(attrs)
        if d.get("id"):
            self.ids.append(d["id"])
        for k, v in attrs:
            if not v:
                continue
            if k == "href":
                self.links.append(v)
            elif k == "src":
                self.srcs.append(v)
        # 新窗口打开的外部链接必须带 rel=noopener（避免 window.opener 被利用）
        if tag == "a" and d.get("target") == "_blank":
            href = d.get("href") or ""
            if href.startswith("http"):
                rel = d.get("rel") or ""
                if "noopener" not in rel:
                    self.external_noopener.append(href)
        if tag not in VOID_TAGS:
            self.stack.append(tag)

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        if not self.stack:
            self.errors.append(f"多余的闭合标签 </{tag}>")
            return
        if self.stack[-1] == tag:
            self.stack.pop()
            return
        if tag in self.stack:
            while self.stack and self.stack[-1] != tag:
                self.errors.append(f"<{self.stack[-1]}> 未闭合（遇到 </{tag}>）")
                self.stack.pop()
            if self.stack:
                self.stack.pop()
        else:
            self.errors.append(f"多余的闭合标签 </{tag}>")


def main() -> int:
    if not DIST.is_dir():
        print("docs/ 不存在，请先运行 python3 scripts/build.py")
        return 1

    pages = sorted(DIST.rglob("*.html"))
    if not pages:
        print("dist/ 下没有 HTML，构建可能失败了")
        return 1

    problems = []
    checked_links = 0

    for pg in pages:
        rel = pg.relative_to(DIST)
        txt = pg.read_text(encoding="utf-8")
        chk = PageCheck()
        chk.feed(txt)

        for e in chk.errors:
            problems.append(f"{rel}: {e}")
        if chk.stack:
            problems.append(f"{rel}: 未闭合标签 {chk.stack}")
        for url in chk.external_noopener:
            problems.append(f"{rel}: 外部链接缺少 rel=noopener —— {url}")

        seen = set()
        for i in chk.ids:
            if i in seen:
                problems.append(f"{rel}: id 重复 —— #{i}")
            seen.add(i)

        base = pg.parent
        for href in chk.links:
            if href.startswith(("http://", "https://", "mailto:", "tel:", "data:", "#")):
                continue
            path = href.split("#")[0].split("?")[0]
            if not path:
                continue
            checked_links += 1
            if path.startswith("/"):
                target = (DIST / path.lstrip("/")).resolve()
            else:
                target = (base / path).resolve()
            if not target.exists():
                problems.append(f"{rel}: 断链 -> {href}")

        for src in chk.srcs:
            if src.startswith(("http", "data:")):
                continue
            checked_links += 1
            target = (base / src.split("#")[0].split("?")[0]).resolve()
            if not target.exists():
                problems.append(f"{rel}: 资源缺失 -> {src}")

        # 页面必须引到样式和脚本
        if "assets/css/style.css" not in txt:
            problems.append(f"{rel}: 没有引用 style.css")
        if "assets/js/app.js" not in txt:
            problems.append(f"{rel}: 没有引用 app.js")

        # 提示：占位符不该漏到线上
        for m in re.finditer(r"(TODO|FIXME|Lorem ipsum|这里是描述)", txt):
            problems.append(f"{rel}: 发现未清理的占位文本 —— {m.group(1)}")

    print(f"检查 {len(pages)} 个页面，{checked_links} 条内部引用")
    if problems:
        print(f"\n发现 {len(problems)} 个问题：")
        for p in problems:
            print(f"  ✗ {p}")
        return 1
    print("全部通过：无断链、无结构错误、无重复 id。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
