"""Validated weekly analog briefings rendered with the existing site layout."""
import json
import re
from datetime import date
from urllib.parse import urlsplit

FIELDS = [('新内容','novelty'),('为什么值得读','whyItMatters'),('证据与结果','evidence'),('权衡与局限','limitations'),('动手验证','takeaway')]

def load_issues(content):
    issues=[]
    for path in sorted((content/'analog-briefings').glob('*.json'),reverse=True):
        if path.name=='index.json':continue
        item=json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(item,dict):raise ValueError(f'{path}: issue must be an object')
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}',str(item.get('date',''))):
            raise ValueError(f'{path}: invalid issue date')
        date.fromisoformat(item['date'])
        if path.stem!=item['date']:raise ValueError(f'{path}: date/filename mismatch')
        for key in ('title','overview'):
            if not isinstance(item.get(key),str) or not item[key].strip():raise ValueError(f'{path}: missing {key}')
        selections=item.get('selections')
        if not isinstance(selections,list) or len(selections)>4:raise ValueError(f'{path}: expected 0–4 selections')
        if any(not isinstance(s,dict) for s in selections):raise ValueError(f'{path}: selection must be an object')
        if selections and sum(s.get('bestRead') is True for s in selections)!=1:raise ValueError(f'{path}: expected one best read')
        for selection in selections:
            for key in ('title','publishedDate',*(key for _,key in FIELDS)):
                if not isinstance(selection.get(key),str) or not selection[key].strip():raise ValueError(f'{path}: missing {key}')
            if not isinstance(selection.get('url'),str):raise ValueError(f'{path}: missing source URL')
            url=urlsplit(selection['url'])
            if url.scheme!='https' or not url.hostname or url.username or url.password or any(c.isspace() or c in '<>"' for c in selection['url']):raise ValueError(f'{path}: source must use a valid HTTPS URL')
        issues.append(item)
    index_path=content/'analog-briefings'/'index.json'
    if issues or index_path.exists():
        index=json.loads(index_path.read_text(encoding='utf-8'))
        expected=[{'date':i['date'],'title':i['title'],'overview':i['overview'],'count':len(i['selections'])} for i in issues]
        if not isinstance(index,dict) or index.get('issues')!=expected:raise ValueError(f'{index_path}: index must match issue dates, titles, overviews and counts')
    return issues

def markdown(issue,include_header=True):
    lines=[f"## {issue['title']}｜{issue['date']}",'',issue['overview'],''] if include_header else []
    for n,s in enumerate(issue['selections'],1):
        lines.extend([f"### {n}. {'本期最佳阅读 · ' if s.get('bestRead') else ''}{s['title']}",'',f"发布 / 更新：{s['publishedDate']}",'',f"原始来源：[查看论文原文]({s['url']})",''])
        for label,key in FIELDS:lines.extend([f'**{label}：** {s[key]}',''])
    lines.extend(['资料由 AI 辅助整理，关键指标请结合原文核验；原文版权归原作者所有。',''])
    return '\n'.join(lines)

def pages(site,issues,b):
    cards=[]
    for issue in issues:
        d=issue['date']
        cards.append(f'<article class="event-card info-panel"><p class="section-label">{b.esc(d)} / {len(issue["selections"])} 篇精选</p><h2 class="event-card-title"><a href="{b.esc(d)}/index.html">{b.esc(issue["title"])}</a></h2><p class="event-card-desc">{b.esc(issue["overview"])}</p><a class="text-button" href="{b.esc(d)}/index.html">阅读全文{b.icon("arrow")}</a></article>')
        texts=markdown(issue)
        body=b.page_hero('Analog circuits / '+d,b.esc(issue['title']),b.esc(issue['overview']))
        body+=f'<section class="section"><div class="container container-narrow"><nav class="detail-actions" aria-label="周报阅读与下载"><a class="text-button" href="../index.html">返回周报归档</a><a class="text-button" href="../data/{d}.json" download>下载结构化数据</a><a class="text-button" href="../data/{d}.md" download>下载阅读笔记</a></nav><div class="prose">{b.render_md(markdown(issue,include_header=False))}</div></div></section>'
        yield f'briefings/{d}/index.html',b.page(site,2,'周报',issue['title']+'｜'+d,issue['overview'],body)
        yield f'briefings/data/{d}.json',json.dumps(issue,ensure_ascii=False,indent=2)+'\n'
        yield f'briefings/data/{d}.md',texts
    lead='每周精选少量论文与工程文章，关注运放、有源滤波、反馈稳定性与传感前端；注明证据、局限和动手验证步骤。'
    body=b.page_hero('Weekly / Analog circuits','模拟电路周报',lead)
    body+='<section class="section"><div class="container container-narrow">'+(''.join(cards) or '<p>周报正在整理中。</p>')+'</div></section>'
    yield 'briefings/index.html',b.page(site,1,'周报','模拟电路周报',lead,body)
