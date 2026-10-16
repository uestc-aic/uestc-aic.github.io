#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
「AI 芯动力」（UESTC AIC）官网 —— 学院资讯 / 竞赛信息采集脚本
================================================================

纯 Python 标准库实现（urllib / re / json / hashlib / html / datetime / argparse /
time / os / sys / urllib.robotparser），**不依赖 requests、bs4、feedparser 等第三方库**。
设计参考 pyzw618/UESTC-Teamup 的 docs/MODULE_CRAWLER.md：

    robots 合规 → Fetcher → 编码解码 → Parser → 日期抽取
                                              ↓
                       Differ（hash 去重）→ Matcher → Guard（异常拦截）→ Publisher

用法：
    python3 scripts/collect.py --dry-run --verbose      # 只抓不写，打印条数
    python3 scripts/collect.py --source uestc-news      # 只跑某个源
    python3 scripts/collect.py                          # 跑全部启用源并写盘

输出：
    content/collected/<source-id>.json   每条源一个文件
    content/collected/_state.json        运行状态 / 健康度 / 连续 0 条天数
    content/collected/_anomalies.json    Guard 拦截记录 (append)

设计纪律（照抄 TeamUp 的教训）：
  ● 先有刹车，再踩油门：Guard 在任何写盘之前。
  ● 抽不出来（日期/条目）是最常见且正常的结果 —— 不写、不报错、更不能崩溃。
  ● locked:true 的人工修正永远不被覆盖，否则人工修正形同虚设。
  ● "连续 N 天抓到 0 条" 是最重要的告警：网站改版后爬虫不报错，数据悄悄烂掉。
"""

import argparse
import hashlib
import html as html_mod
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from datetime import date, datetime, timedelta

# ---------------------------------------------------------------------------
# 路径常量：脚本在 scripts/ 下，仓库根目录是它的上一级
# ---------------------------------------------------------------------------
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SOURCES_FILE = os.path.join(ROOT, "sources", "sources.json")
COLLECTED_DIR = os.path.join(ROOT, "content", "collected")
EVENTS_FILE = os.path.join(ROOT, "content", "events.json")
STATE_FILE = os.path.join(COLLECTED_DIR, "_state.json")
ANOMALY_FILE = os.path.join(COLLECTED_DIR, "_anomalies.json")

DEFAULT_UA = (
    "AIC-UESTC-Crawler/1.0 (+https://github.com/uestc-aic; AI-for-IC community news collector) "
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

# Guard 阈值：日期合理区间
YEAR_MIN = 2020
YEAR_MAX = 2035
JUMP_MAX_DAYS = 180  # 同一 id 的日期跳变上限
# 无年份日期的「回溯容忍窗口」：算出来的日期比今天早但不超过这个天数，就认为是今年
# （公告上的 "09-29" 是已发布的公告，不是明年的）；超过则判定为明年（"即日起至1月3日"）。
GRACE_DAYS = 90

# 逐源运行统计（最后打印汇总用）
STATS = {}


def log(msg, verbose_only=False, verbose=False):
    if verbose_only and not verbose:
        return
    print(msg, flush=True)


# ===========================================================================
# 一、Fetcher —— 只做网络 IO，不做解析
# ===========================================================================
def fetch(url, timeout=20, retries=2, ua=DEFAULT_UA, verbose=False):
    """取一个 URL 的原始字节。

    返回 (body: bytes|None, status: int|None, headers: dict)

    为什么返回 bytes 而不是 str：编码判断必须拿到原始字节，见 decode_html()。
    为什么 5xx/429 才重试：4xx 是「你不该来」，重试毫无意义还显得有攻击性。
    """
    last_err = None
    # HTTP 头按 latin-1 编码：UA 里混进任何中文都会让【每一个】请求直接抛
    # UnicodeEncodeError（'latin-1' codec can't encode ...），表现为"所有源全挂"。
    # 配置是人写的，这里兜一道，别让一个中文字符废掉整轮采集。
    ua = re.sub(r"[^\x20-\x7e]", "", ua or "") or DEFAULT_UA
    for attempt in range(retries + 1):
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": ua,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
                # 明确不压缩：省掉 gzip 解包逻辑，而且有的老站点 Content-Encoding 会骗人
                "Accept-Encoding": "identity",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read()
                status = getattr(resp, "status", resp.getcode())
                headers = {k: v for k, v in resp.headers.items()}
                return body, status, headers
        except urllib.error.HTTPError as exc:
            hdrs = {k: v for k, v in (exc.headers or {}).items()}
            if exc.code == 429 or exc.code >= 500:
                last_err = exc
                if attempt < retries:
                    time.sleep(2 * (attempt + 1))
                continue
            # 4xx（含 412 WAF 挑战页）不重试
            return None, exc.code, hdrs
        except Exception as exc:  # URLError / timeout / SSL / DNS
            last_err = exc
            if attempt < retries:
                time.sleep(2 * (attempt + 1))
    log("    ! 抓取失败 %s: %s" % (url, last_err), verbose_only=True, verbose=verbose)
    return None, None, {}


# ===========================================================================
# 二、编码处理 —— 国内高校站点「静默失效」的头号原因
# ===========================================================================
_CHARSET_IN_HEADER = re.compile(r"charset\s*=\s*['\"]?\s*([\w\-]+)", re.I)
# meta 只在前 2KB 里找：真正的 <meta charset> 一定在 head 里，2KB 足够；
# 但注意用 bytes 正则（rb''），不能先 decode 再找 —— 那正是我们要解决的问题。
_CHARSET_IN_META = re.compile(
    rb"""<meta[^>]*?charset\s*=\s*['"]?\s*([A-Za-z0-9_\-]+)""", re.I
)
# 别名归一：写了 gb2312 的站点，正文几乎必然是 gbk/gb18030 超集。
# 用 gb2312 严格解码会抛异常 -> errors='replace' 会得到一片 "�"，
# 日期正则全部匹配失败，而且【不报错】—— 这就是静默失效。所以必须映射成 gbk。
_CHARSET_ALIAS = {
    "gb2312": "gbk",
    "gb-2312": "gbk",
    "gb_2312": "gbk",
    "gbk2312": "gbk",
    "utf8": "utf-8",
    "utf-8;": "utf-8",
    "big5": "big5",
    "ansi": "utf-8",
    "iso-8859-1": "utf-8",  # 老服务器默认值，中文站实际多为 utf-8
}


def detect_charset(buf, content_type, declared="auto"):
    """优先级：配置显式声明 > HTTP header charset > <meta charset>(前2KB) > 默认 utf-8。"""
    if declared and declared.lower() not in ("auto", ""):
        return _CHARSET_ALIAS.get(declared.lower().strip(), declared.lower().strip())

    if content_type:
        m = _CHARSET_IN_HEADER.search(content_type)
        if m:
            cs = m.group(1).lower().strip()
            return _CHARSET_ALIAS.get(cs, cs)

    m = _CHARSET_IN_META.search(buf[:2048])
    if m:
        cs = m.group(1).decode("ascii", "replace").lower().strip()
        return _CHARSET_ALIAS.get(cs, cs)

    return "utf-8"


def decode_html(buf, content_type, declared="auto", verbose=False, tag=""):
    """按探测到的编码解码，失败的字符用 errors='replace' 兜住（绝不抛异常）。"""
    if buf is None:
        return "", "utf-8"
    cs = detect_charset(buf, content_type, declared)
    try:
        return buf.decode(cs, errors="replace"), cs
    except LookupError:
        # 服务器给了一个 Python 不认识的 charset 名字，退回 utf-8 而不是崩
        log("    ! 未知编码 %r，退回 utf-8 (%s)" % (cs, tag), verbose_only=True, verbose=verbose)
        return buf.decode("utf-8", errors="replace"), "utf-8"


# ===========================================================================
# 三、robots.txt —— 合规第一道门
# ===========================================================================
_ROBOTS_CACHE = {}


def load_robots(page_url, timeout, ua, verbose=False):
    """取并解析 robots.txt。返回 (RobotFileParser, crawl_delay|None)。

    自建 parser 而不用 rp.read()：read() 用 Python 默认 UA 去取，既不礼貌也不好排查。
    返回 404 / 空文件 / 取不到 —— 一律视为「无限制」（用 allow_all 显式表达）。
    """
    parts = urllib.parse.urlsplit(page_url)
    origin = "%s://%s" % (parts.scheme, parts.netloc)
    if origin in _ROBOTS_CACHE:
        return _ROBOTS_CACHE[origin]

    rp = urllib.robotparser.RobotFileParser()
    rp.set_url(origin + "/robots.txt")
    buf, status, headers = fetch(origin + "/robots.txt", timeout=timeout, retries=1, ua=ua)

    if status != 200 or not buf:
        # 404 / 空文件：没有规则 = 全部允许
        setattr(rp, "allow_all", True)
        log("    robots %s/robots.txt -> HTTP %s 无内容，视为允许" % (origin, status),
            verbose_only=True, verbose=verbose)
        _ROBOTS_CACHE[origin] = (rp, None)
        return rp, None

    text, _ = decode_html(buf, headers.get("Content-Type"), "auto")
    rp.parse(text.splitlines())
    # Crawl-delay 可能写在 "*" 段或我们的 UA 段里，都取
    delay = None
    try:
        delay = rp.crawl_delay(ua) or rp.crawl_delay("*")
    except Exception:
        delay = None
    log("    robots %s/robots.txt -> HTTP 200 (%d 字节, Crawl-delay=%s)"
        % (origin, len(buf), delay), verbose_only=True, verbose=verbose)
    _ROBOTS_CACHE[origin] = (rp, delay)
    return rp, delay


# ===========================================================================
# 四、Parser —— 正则抽取（含极简 CSS「容器是否存在」预检）
# ===========================================================================
def _selector_to_regex(sel):
    """把极简 CSS 选择器（tag / .class / #id 组合，空格或 > 分层）转成正则。

    只用来做「列表容器还在不在」的健康预检 —— 真抽取仍然靠 item_pattern 正则。
    没有引入 CSS 解析库的打算：纯标准库 + 正则足够发现"页面改版了"。
    """
    parts = [p for p in re.split(r"\s*>\s*|\s+", sel.strip()) if p]
    regexes = []
    for part in parts:
        tag_m = re.match(r"^[A-Za-z][\w\-]*", part)
        tag = tag_m.group(0) if tag_m else r"[a-zA-Z][\w\-]*"
        attrs = []
        for cls in re.findall(r"\.([\w\-]+)", part):
            attrs.append(r'class="[^"]*(?<![\w\-])' + re.escape(cls) + r'(?![\w\-])[^"]*"')
        for iid in re.findall(r"#([\w\-]+)", part):
            attrs.append(r'id="' + re.escape(iid) + r'"')
        if attrs:
            regexes.append(r"<" + tag + r"[^>]*" + r"[^>]*".join(attrs))
        else:
            regexes.append(r"<" + tag + r"[\s>]")
    return re.compile(r".*?".join(regexes), re.S | re.I)


def container_present(raw_html, selector):
    """列表容器选择器是否还在页面里。找不到 = 页面结构可能已改版（健康告警依据）。"""
    if not selector:
        return None  # 未配置，不判断
    try:
        return bool(_selector_to_regex(selector).search(raw_html))
    except Exception:
        return None


def _clean_text(s):
    """去标签残留 + HTML 实体反转义 + 空白归一。标题里常见 &nbsp; &#8217; 之类。"""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", " ", s)
    s = html_mod.unescape(s)
    s = s.replace("\u3000", " ").replace("\xa0", " ")
    return re.sub(r"\s+", " ", s).strip()


def compile_patterns(source):
    """预编译该源的 item / title / date 三个正则。"""
    comp = {}
    for key in ("item_pattern", "title_pattern", "date_pattern"):
        pat = source.get(key) or ""
        comp[key] = re.compile(pat, re.S) if pat else None
    return comp


def parse_items(raw_html, source, comp, page_url, verbose=False):
    """从 HTML 抽结构化条目。返回候选列表（未去重、未过 Guard）。

    抽取策略（按可靠性从高到低）：
      1) item_pattern 里直接带 (?P<title>) 和 (?P<date>)  —— 最稳
      2) item_pattern 只带 href，另配 title_pattern / date_pattern 对条目片段二次抽
      3) 都没有 —— 日期留空（抽不出来是正常结果，不报错）
    """
    if not comp["item_pattern"]:
        return []
    base = source.get("base_url") or page_url
    url_tpl = source.get("url_template") or ""
    out = []
    seen = set()

    for m in comp["item_pattern"].finditer(raw_html):
        gd = m.groupdict()
        href = (gd.get("href") or "").strip()
        if not href:
            continue
        title = _clean_text(gd.get("title") or "")
        date_text = _clean_text(gd.get("date") or "")
        block = m.group(0)

        # 2) 二次抽取
        if not title and comp["title_pattern"]:
            tm = comp["title_pattern"].search(block)
            if tm and tm.groupdict().get("title"):
                title = _clean_text(tm.group("title"))
        if not date_text and comp["date_pattern"]:
            dm = comp["date_pattern"].search(block)
            if dm:
                # 优先取最后一个捕获组：date_pattern 常带前缀（如 news-scroll-time">），
                # 取 group(0) 会把属性名一起塞进 date_text，虽然还能解析出日期但不干净。
                date_text = _clean_text(dm.group(dm.lastindex) if dm.lastindex else dm.group(0))

        if not title:
            # 没有标题的条目对站上没有意义（导航链接等），丢弃不算异常
            continue

        # 拼绝对 URL：优先 url_template（jwc 的 newsId 不是路径），否则 urljoin
        if url_tpl:
            url = url_tpl.replace("{href}", href)
        else:
            url = urllib.parse.urljoin(base + "/" if not base.endswith("/") else base, href)

        if url in seen:  # 同页重复渲染（置顶区 + 列表区）只留一条
            continue
        seen.add(url)

        out.append(
            {
                "title": title,
                "url": url,
                "date_text": date_text,
                "category": source.get("category", "campus"),
                "source_name": source.get("name", ""),
                "source_id": source.get("id", ""),
            }
        )
    return out


# ===========================================================================
# 五、中文日期抽取 —— 最大难点，抽不出来是正常结果
# ===========================================================================
# 顺序即优先级，不要随手调整。
_DATE_RES = [
    # ① 带 4 位年：2026年10月15日 / 2026-10-15 / 2026/10/15 / 2026.10.15
    (re.compile(r"(?P<y>\d{4})\s*[年\-/.]\s*(?P<m>\d{1,2})\s*[月\-/.]\s*(?P<d>\d{1,2})\s*日?"), "full"),
    # ② 只有月日（缺年份）：即日起至10月15日 / 报名截止时间：10月15日17:00
    (re.compile(r"(?P<m>\d{1,2})\s*月\s*(?P<d>\d{1,2})\s*日?"), "noyear"),
    # ③ 两位年：数模网是 (26-09-15)
    (re.compile(r"(?<!\d)(?P<y>\d{2})-(?P<m>\d{2})-(?P<d>\d{2})(?!\d)"), "yy"),
    # ④ 点分无年：10.15
    (re.compile(r"(?<!\d)(?P<m>\d{1,2})\.(?P<d>\d{1,2})(?!\d)"), "noyear"),
    # ⑤ 纯 MM-DD（教务处首页公告是 09-29）。这条**必须整串匹配**才生效，
    #    否则会在任意文本里乱抓 "09-29" 这种片段，所以加了 ^...$。
    (re.compile(r"^(?P<m>\d{1,2})-(?P<d>\d{1,2})$"), "noyear"),
]
# 出现这些词说明这段日期是「报名截止/起止时间」，指向未来 → 缺年份时按 deadline 语义补年
_DEADLINE_HINT = re.compile(r"至|截止|报名|即日起|提交|前完成|—|～|~|到")


def _safe_date(y, m, d):
    try:
        return date(int(y), int(m), int(d))
    except ValueError:
        return None  # 13 月 / 32 日 这类脏数据，直接判无效


def extract_date(text, today=None, policy="published", verbose=False):
    """从一段文本里抽第一个可用的日期。

    返回 (date|None, 命中的原始文本|None, 全部命中列表)

    缺年份（如 "10月15日" / "09-29" / "10.15"）时怎么补年，是本模块最容易出错的地方，
    必须区分两种语义 —— 这是 TeamUp 文档没写透、但踩了就会把日期整年搞错的地方：

      ● published（列表页上的发布日期）：年份 = 今年；若补出来是**未来**，
        说明它其实是去年的（今天 10-15 看到一个 "12-31"，必然是去年 12-31）。
      ● deadline（通知里的"即日起至10月15日"这类截止时间）：年份 = 今年；
        若补出来比今天早**很久**（> GRACE_DAYS），说明是明年的（1月3日的截止
        在 10 月看就是明年）。

    语义由 policy 参数决定，且文本里出现「至/截止/报名/到」等词时自动按 deadline 处理。
    ● 模糊表达（"10月下旬"、"详见附件"）不猜：返回 None。抽不出来不写、不报错。
    """
    if not text:
        return None, None, []
    today = today or date.today()
    text = _clean_text(text)
    effective = "deadline" if _DEADLINE_HINT.search(text) else policy
    hits = []
    for regex, kind in _DATE_RES:
        for m in regex.finditer(text):
            gd = m.groupdict()
            if kind == "full":
                y, mo, dd = gd["y"], gd["m"], gd["d"]
            elif kind == "yy":
                y, mo, dd = 2000 + int(gd["y"]), gd["m"], gd["d"]
            else:  # noyear：先用今年
                y, mo, dd = today.year, gd["m"], gd["d"]
            got = _safe_date(y, mo, dd)
            if got is None:
                continue
            if kind == "noyear":
                if effective == "deadline":
                    if (today - got).days > GRACE_DAYS:
                        nxt = _safe_date(int(y) + 1, mo, dd)
                        if nxt is not None:
                            got = nxt
                else:  # published
                    if got > today:
                        prv = _safe_date(int(y) - 1, mo, dd)
                        if prv is not None:
                            got = prv
            hits.append((got, m.group(0)))
        if hits:
            break  # 高级别格式命中就不再退化匹配，避免把 "2026年" 拆成别的
    if not hits:
        return None, None, []
    hits.sort(key=lambda t: t[0])
    return hits[0][0], hits[0][1], hits


def make_item_id(title, url):
    """条目内容 SHA256 前 16 位作为 id：标题或链接任意变化都会得到新 id。

    去重靠它而不是靠标题模糊匹配 —— 采集端只要保证「不重复写」，够用且不会误合并。
    """
    raw = ("%s|%s" % (title, url)).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


# ===========================================================================
# 六、Guard（异常拦截器）—— 必须在写盘之前
# ===========================================================================
def _as_date(v):
    """把「可能是 date 也可能是 ISO 字符串」的历史值统一成 date。

    已落盘的条目里 date 是字符串，守卫要拿它做日期运算 —— 不统一就会
    在第二次运行时抛 TypeError（第一次跑不出来，第二次才炸，典型的隐蔽 bug）。
    """
    if isinstance(v, datetime):
        return v.date()
    if isinstance(v, date):
        return v
    if isinstance(v, str) and len(v) >= 10:
        try:
            return date.fromisoformat(v[:10])
        except ValueError:
            return None
    return None


def guard_check(item, prev_item, today, verbose=False):
    """命中任一规则 → 不发布、保留原值、记 anomaly。

    注意：这是最后一道防线，不是第一道。它拦不住「格式对了但抽错字段」，
    那种只能靠人工锁定 + 事后纠错。
    """
    problems = []
    d = item.get("date")
    old = _as_date((prev_item or {}).get("date"))

    # 1) 日期超出合理区间
    if d and (d.year < YEAR_MIN or d.year > YEAR_MAX):
        problems.append(("date-out-of-range", "日期 %s 超出 %d-%d" % (d, YEAR_MIN, YEAR_MAX)))
    # 2) 1970 纪元日期（默认值/解析失败的经典症状）
    if d and d.year == 1970:
        problems.append(("epoch-date", "抽到 1970-01-01，典型的解析失败默认值"))
    # 3) 区间倒挂（"至/到/-"说明是区间，两个日期必须递增）
    ds, de = item.get("date_start"), item.get("date_end")
    if ds and de and de < ds:
        problems.append(("end-before-start", "结束 %s 早于开始 %s" % (de, ds)))
    # 4) 同一 id 的日期跳变过大
    if d and old and abs((d - old).days) > JUMP_MAX_DAYS:
        problems.append(
            ("jump-too-large", "旧值 %s → 新值 %s（%d 天）" % (old, d, abs((d - old).days)))
        )
    # 5) 非空被空覆盖
    if old and not d:
        problems.append(("null-overwrite", "旧值 %s 非空，本次解析为空，保留旧值" % old))
    if (prev_item or {}).get("title") and not item.get("title"):
        problems.append(("null-overwrite", "标题旧值非空，本次为空"))
    return problems


# ===========================================================================
# 七、Publisher —— 写盘（含人工锁定保护）
# ===========================================================================
def load_json(path, default):
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return default


def save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    os.replace(tmp, path)  # 原子替换：跑一半被打断也不会留下半个 JSON


def build_locked_index():
    """收集所有 locked:true 的记录（content/events.json + content/collected/*.json）。

    返回 (locked_ids, locked_urls)。这两类 id 空间不同（events 用 slug，采集用 hash），
    所以两个都收。**没有这个机制，人工修正形同虚设** —— 下一次采集会把它改回去，
    而且看起来像"数据自己变回去了"。
    """
    ids, urls = set(), set()

    def _absorb(obj):
        for it in (obj.get("items") or []):
            if not isinstance(it, dict) or not it.get("locked"):
                continue
            if it.get("id"):
                ids.add(str(it["id"]))
            if it.get("url"):
                urls.add(str(it["url"]))
            src = it.get("source")
            if isinstance(src, dict) and src.get("url"):
                urls.add(str(src["url"]))

    _absorb(load_json(EVENTS_FILE, {}))
    if os.path.isdir(COLLECTED_DIR):
        for fn in sorted(os.listdir(COLLECTED_DIR)):
            if fn.endswith(".json") and not fn.startswith("_"):
                _absorb(load_json(os.path.join(COLLECTED_DIR, fn), {}))
    return ids, urls


def append_anomalies(records):
    if not records:
        return
    data = load_json(ANOMALY_FILE, {"updated": "", "items": []})
    if not isinstance(data, dict):
        data = {"updated": "", "items": []}
    data.setdefault("items", [])
    data["items"].extend(records)
    data["items"] = data["items"][-500:]  # 只留最近 500 条，别把仓库撑爆
    data["updated"] = datetime.now().astimezone().date().isoformat()
    save_json(ANOMALY_FILE, data)


# ===========================================================================
# 八、单源流水线
# ===========================================================================
def process_source(source, cfg, args, today, locked_ids, locked_urls):
    sid = source["id"]
    name = source.get("name", sid)
    verbose = args.verbose
    stat = {
        "id": sid, "name": name, "fetched": 0, "new": 0, "skipped": 0,
        "updated": 0, "anomalies": 0, "blocked": 0, "locked_skipped": 0, "health": "ok",
        "note": "", "http": None, "seen_ids": [],
    }
    STATS[sid] = stat

    log("\n[%s] %s" % (sid, name), verbose=verbose)
    log("  URL: %s" % source.get("url"), verbose=verbose)

    if not source.get("enabled"):
        stat["health"] = "disabled"
        log("  已停用（enabled:false），跳过", verbose=verbose)
        return

    timeout = int(cfg.get("timeout", 20))
    retries = int(cfg.get("retries", 2))
    # 同样去掉非 ASCII：这个值既要给 Request 头，也要给 robots 的 can_fetch
    ua = re.sub(r"[^\x20-\x7e]", "", cfg.get("user_agent") or "") or DEFAULT_UA
    max_items = int(cfg.get("max_items_per_source", 30))

    # --- 合规：robots.txt 先行 -------------------------------------------
    rp, crawl_delay = load_robots(source["url"], timeout, ua, verbose=verbose)
    if rp is not None and not rp.can_fetch(ua, source["url"]):
        stat["health"] = "blocked"
        stat["note"] = "robots.txt Disallow，遵守并放弃"
        log("  ✗ robots.txt 不允许抓取，已放弃（合规红线）")
        return

    # --- 抓取 + 编码 ------------------------------------------------------
    buf, status, headers = fetch(source["url"], timeout=timeout, retries=retries, ua=ua, verbose=verbose)
    stat["http"] = status
    if buf is None or status != 200:
        stat["health"] = "failing"
        stat["note"] = "HTTP %s" % status
        log("  ✗ 抓取失败：HTTP %s" % status, verbose=verbose)
        return

    raw, charset = decode_html(buf, headers.get("Content-Type"), source.get("encoding", "auto"),
                              verbose=verbose, tag=sid)
    log("  编码: %s（%d 字节）" % (charset, len(buf)), verbose=verbose)

    # --- 容器预检（页面改版探针）----------------------------------------
    present = container_present(raw, source.get("list_selector"))
    if present is False:
        log("  ! 列表容器选择器未命中：%s（页面可能已改版）" % source.get("list_selector"),
            verbose=verbose)

    # --- 解析 ------------------------------------------------------------
    comp = compile_patterns(source)
    raw_items = parse_items(raw, source, comp, source["url"], verbose=verbose)
    stat["fetched"] = len(raw_items)
    log("  解析到候选条目: %d" % len(raw_items), verbose=verbose)

    # --- 日期抽取 --------------------------------------------------------
    year_policy = source.get("date_year_policy") or cfg.get("date_year_policy") or "published"
    for it in raw_items:
        d, hit, hits = extract_date(it.get("date_text"), today=today,
                                    policy=year_policy, verbose=verbose)
        it["date"] = d
        it["date_hit"] = hit
        if len(hits) >= 2:
            # 区间：首末两个（hits 已排序），供 end-before-start 规则使用
            it["date_start"], it["date_end"] = hits[0][0], hits[-1][0]
        it["id"] = make_item_id(it["title"], it["url"])

    n_date = sum(1 for it in raw_items if it.get("date"))
    log("  其中解析出日期: %d（抽不出来是正常结果，不报错）" % n_date, verbose=verbose)

    # --- 去重 / 入库（dry-run 就此打住）----------------------------------
    out_path = os.path.join(COLLECTED_DIR, sid + ".json")
    existing_doc = load_json(out_path, {})
    existing = {}
    for it in (existing_doc.get("items") or []):
        if isinstance(it, dict) and it.get("id"):
            existing[str(it["id"])] = it
    locked_in_file = {str(i) for i, v in existing.items() if v.get("locked")}

    # 曾经见过的 id 全集（不随 max_items_per_source 裁剪而丢失）。
    # 为什么要它：发布的 JSON 只留最近 N 条，被裁掉的旧条目如果只靠 JSON 比对，
    # 下一轮会被判成"新条目"重新写回来 —— 于是列表在 N 条和 N+k 条之间反复横跳，
    # 而且永远满足不了"第二次新增为 0"。去重必须对着"见过的全集"做。
    state_all = load_json(STATE_FILE, {})
    seen_ids = set()
    try:
        seen_ids = set((state_all.get("sources") or {}).get(sid, {}).get("seen_ids") or [])
    except Exception:
        seen_ids = set()
    seen_ids |= set(existing.keys())

    now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
    anomalies = []
    kept = list(existing.values())  # 先保留原有条目（含人工锁定），最后整体重写
    by_id = {str(it["id"]): it for it in kept if it.get("id")}

    for it in raw_items:
        iid = it["id"]

        # (a) 人工锁定：永不覆盖，连字段都不碰
        if iid in locked_ids or iid in locked_in_file or it["url"] in locked_urls:
            stat["locked_skipped"] += 1
            seen_ids.add(iid)
            continue

        prev = by_id.get(iid)

        # (a2) 见过但已被裁剪掉 → 仍是重复，别加回来（防止 30 条 / 49 条来回跳）
        if prev is None and iid in seen_ids:
            stat["skipped"] += 1
            continue

        # (b) Guard 拦截（写盘前）
        problems = guard_check(it, prev, today, verbose=verbose)
        if problems:
            old_d = _as_date((prev or {}).get("date"))
            for rule, detail in problems:
                stat["anomalies"] += 1
                anomalies.append({
                    "ts": now_iso, "source_id": sid, "rule": rule, "path": out_path,
                    "id": iid, "title": it.get("title", ""),
                    "old": old_d.isoformat() if old_d else None,
                    "new": it["date"].isoformat() if it.get("date") else None,
                    "detail": detail,
                    "_note": "命中 Guard 规则：不发布、保留原值",
                })
                log("    ⚠ Guard[%s] %s" % (rule, detail), verbose_only=True, verbose=verbose)

        # (b2) 新条目命中 Guard → 不发布。"保留原值"对还不存在的记录 = 干脆别写进去。
        #      （若这里是已存在的条目，则落到 (c) 走"保留旧值"分支）
        if problems and prev is None:
            stat["blocked"] += 1
            # 记入 seen：否则每一轮都会为同一条 2010 年的老公告重复报警，
            # 把 _anomalies.json 淹掉，真正的异常反而看不见。
            # （要重新评估它：删掉 _state.json 里该源的 seen_ids 再跑。）
            seen_ids.add(iid)
            continue

        # (c) 已存在 → 只允许「日期从空到有」或「小幅修正」，其余原样保留
        if prev is not None:
            if it.get("date") and not _as_date(prev.get("date")) and not problems:
                prev["date"] = it["date"].isoformat()
                prev["date_text"] = it.get("date_text") or prev.get("date_text", "")
                prev["collected_at"] = now_iso
                stat["updated"] += 1
                log("    ↻ 补全日期 %s %s" % (iid, it["title"][:30]), verbose_only=True, verbose=verbose)
            else:
                stat["skipped"] += 1
            continue

        # (d) 新条目 → 发布
        stat["new"] += 1
        by_id[iid] = {
            "id": iid,
            "title": it["title"],
            "url": it["url"],
            "date": it["date"].isoformat() if it.get("date") else None,
            "date_text": it.get("date_text", ""),
            "category": it.get("category", "campus"),
            "source": {"name": it.get("source_name", name), "url": it["url"], "source_id": sid},
            "collected_at": now_iso,
            "locked": False,
        }

    # 本轮见到的全部 id 都记进 seen（含被 Guard 拦截与被裁剪的），下次不再当新条目
    seen_ids |= {it["id"] for it in raw_items}
    stat["seen_ids"] = sorted(seen_ids)

    items = sorted(
        by_id.values(),
        key=lambda x: (x.get("date") or "0000-00-00", x.get("collected_at") or ""),
        reverse=True,
    )[:max_items]  # 只留最近 N 条，只存结构化字段 + 原文链接，不转载全文

    # --- 健康度 ----------------------------------------------------------
    if not raw_items:
        stat["health"] = "degraded"
        stat["note"] = "抓到 0 条：选择器很可能已失效" + ("" if present else "（容器也未命中）")
    elif present is False:
        stat["health"] = "degraded"
        stat["note"] = "有条目但容器选择器未命中，注意改版"
    else:
        stat["health"] = "ok"

    if args.dry_run:
        log("  [dry-run] 不写盘：抓取 %d / 将新增 %d / 将跳过 %d / 待更新 %d / Guard拦截 %d / 人工锁定 %d"
            % (stat["fetched"], stat["new"], stat["skipped"], stat["updated"],
               stat["blocked"], stat["locked_skipped"]),
            verbose=verbose)
        if verbose:
            for it in raw_items[:5]:
                log("    · %s | %s | %s"
                    % (it["date"] or "（无日期）", it["title"][:38], it["url"][:70]), verbose=verbose)
        return

    payload = {
        "source_id": sid,
        "source_name": name,
        "source_url": source["url"],
        "fetched_at": now_iso,
        "items": items,
    }
    # 抓取时间保存在本地状态中；内容未变时保留原文件，避免每天产生空更新。
    previous_content = {k: v for k, v in existing_doc.items() if k != "fetched_at"}
    next_content = {k: v for k, v in payload.items() if k != "fetched_at"}
    if previous_content != next_content:
        save_json(out_path, payload)
    append_anomalies(anomalies)
    log("  → 已写入 %s（%d 条）" % (os.path.relpath(out_path, ROOT), len(items)), verbose=verbose)


# ===========================================================================
# 九、状态与健康度落盘
# ===========================================================================
def update_state(today, dry_run=False):
    if dry_run:
        return
    state = load_json(STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}
    srcs = state.get("sources") or {}
    now_iso = datetime.now().astimezone().isoformat(timespec="seconds")
    for sid, st in STATS.items():
        old = srcs.get(sid) or {}
        if st["health"] == "disabled":
            srcs[sid] = dict(old, enabled=False, last_health="disabled", last_run=now_iso)
            continue
        zero_streak = old.get("zero_streak_days", 0)
        if st["health"] == "ok":
            zero_streak = 0
        elif st["health"] in ("degraded", "blocked"):
            zero_streak = zero_streak + 1
        fail_streak = 0 if st["health"] not in ("failing", "blocked") else old.get("fail_streak", 0) + 1
        srcs[sid] = {
            "enabled": True,
            "last_run": now_iso,
            "last_health": st["health"],
            "last_http": st["http"],
            "last_fetched": st["fetched"],
            "last_new": st["new"],
            "zero_streak_days": zero_streak,
            "fail_streak": fail_streak,
            "note": st["note"],
            # 见过的 id 全集：去重与"连续 N 天 0 条"之外的第三道护栏。
            # 只留最近 2000 条，避免状态文件无限膨胀（远超 max_items_per_source 即可）。
            "seen_ids": sorted(set((st.get("seen_ids") or []) +
                                   (old.get("seen_ids") or [])))[-2000:],
        }
    state["updated"] = today.isoformat()
    state["sources"] = srcs
    save_json(STATE_FILE, state)


def print_summary(dry_run=False):
    head = "%-24s %6s %6s %6s %6s %6s %6s %6s  %-9s %s" % (
        "源 ID", "抓取", "新增", "跳过", "更新", "拦截", "锁定", "异常", "健康", "备注")
    print("\n" + "=" * 118)
    print("采集汇总" + ("（dry-run，未写盘）" if dry_run else ""))
    print("=" * 118)
    print(head)
    print("-" * 118)
    tot = {"fetched": 0, "new": 0, "skipped": 0, "updated": 0, "blocked": 0,
           "locked_skipped": 0, "anomalies": 0}
    for sid in sorted(STATS):
        st = STATS[sid]
        for k in tot:
            tot[k] += st.get(k, 0)
        print("%-24s %6d %6d %6d %6d %6d %6d %6d  %-9s %s" % (
            st["id"][:24], st["fetched"], st["new"], st["skipped"],
            st["updated"], st["blocked"], st["locked_skipped"], st["anomalies"],
            st["health"], st["note"]))
    print("-" * 118)
    print("%-24s %6d %6d %6d %6d %6d %6d %6d" % (
        "合计", tot["fetched"], tot["new"], tot["skipped"], tot["updated"],
        tot["blocked"], tot["locked_skipped"], tot["anomalies"]))
    print("=" * 118)
    if not dry_run and os.path.exists(STATE_FILE):
        print("状态: %s" % os.path.relpath(STATE_FILE, ROOT))
    bad = [s for s in STATS.values() if s["health"] in ("degraded", "failing")]
    if bad:
        print("\n⚠ 需要人工查看的源：")
        for s in bad:
            print("   - %s [%s] %s" % (s["id"], s["health"], s["note"]))


# ===========================================================================
# 十、入口
# ===========================================================================
def main(argv=None):
    ap = argparse.ArgumentParser(
        description="AI 芯动力 —— 学院资讯 / 竞赛信息采集（纯标准库）")
    ap.add_argument("--dry-run", action="store_true", help="只抓取解析，不写任何文件")
    ap.add_argument("--source", action="append", default=None,
                    help="只跑指定源 id（可重复；默认跑全部 enabled 源）")
    ap.add_argument("--verbose", "-v", action="store_true", help="打印每一步细节")
    ap.add_argument("--interval", type=float, default=None,
                    help="覆盖源之间的抓取间隔秒数（默认取配置，且不小于 robots Crawl-delay）")
    args = ap.parse_args(argv)

    conf = load_json(SOURCES_FILE, None)
    if not conf:
        print("✗ 读不到源配置：%s" % SOURCES_FILE, file=sys.stderr)
        return 2
    cfg = conf.get("defaults") or {}
    all_sources = conf.get("sources") or []

    if args.source:
        want = set(args.source)
        picked = [s for s in all_sources if s["id"] in want]
        missing = want - {s["id"] for s in picked}
        if missing:
            print("✗ 未知源 id: %s" % ", ".join(sorted(missing)), file=sys.stderr)
            return 2
    else:
        picked = [s for s in all_sources if s.get("enabled")]

    if not picked:
        print("没有可跑的源（检查 enabled / --source）", file=sys.stderr)
        return 1

    today = date.today()
    locked_ids, locked_urls = build_locked_index()
    interval = float(cfg.get("interval_seconds", 3))
    if args.interval is not None:
        interval = args.interval

    print("AI 芯动力 · 采集开始  %s  （%d 个源，dry-run=%s）"
          % (datetime.now().astimezone().isoformat(timespec="seconds"), len(picked), args.dry_run))

    for idx, source in enumerate(picked):
        if idx > 0:
            # 串行 + 间隔：2C2G 机器上并发只会让内存尖峰叠加，采集根本不需要快
            time.sleep(interval)
        try:
            process_source(source, cfg, args, today, locked_ids, locked_urls)
        except Exception as exc:  # 单源崩了不能拖垮整轮
            STATS[source["id"]] = STATS.get(source["id"]) or {
                "id": source["id"], "name": source.get("name", ""), "fetched": 0, "new": 0,
                "skipped": 0, "updated": 0, "anomalies": 0, "blocked": 0, "locked_skipped": 0,
                "health": "failing", "note": "内部异常: %s" % exc, "http": None,
            }
            print("  ✗ %s 运行异常：%s" % (source["id"], exc))

    print_summary(dry_run=args.dry_run)
    update_state(today, dry_run=args.dry_run)
    if not any(st.get("health") == "ok" for st in STATS.values()):
        print("本轮没有成功的采集来源；停止自动发布，保留线上版本。", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
