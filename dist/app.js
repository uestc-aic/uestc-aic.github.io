'use strict';

// 填入实际入口后，对应按钮会自动变为可访问链接。
const CONFIG = {
  github: 'https://github.com/uestc-aic',
  recruitmentForm: '',
  qqGroup: '',
  contributionForm: '',
  salonRegistration: '',
  salonTime: '期中后，具体时间待公布',
  salonLocation: '待公布'
};

const RESOURCES = [
  { icon: 'chip', title: 'FPGA 小课堂', description: 'FPGA 接口与电路学习笔记，适合在动手实践时查阅。', category: 'ic', label: 'FPGA 学习', source: 'Sintherain', host: 'sintherain.github.io', featured: true, url: 'https://sintherain.github.io/fpga-website/' },
  { icon: 'book', title: 'Corleone’s Blog', description: '模拟电路、数字设计、信号与系统等微电子学习笔记。', category: 'ic', label: '微电子笔记', source: 'Corleone', host: 'corele-one.github.io', featured: true, url: 'https://corele-one.github.io/Corleone-s-Blog/' },
  { icon: 'agent', title: 'AI Agents for Beginners', description: 'Microsoft 开源课程，从基础概念开始了解 AI Agent。', category: 'agent', label: 'AI / Agent', source: 'Microsoft', url: 'https://github.com/microsoft/ai-agents-for-beginners' },
  { icon: 'terminal', title: 'GitHub CLI 官方手册', description: '了解 gh 的常用操作，连接本地开发与 GitHub 协作。', category: 'development', label: '开发工具', source: 'GitHub Docs', url: 'https://cli.github.com/manual/' },
  { icon: 'globe', title: '用 GitHub Actions 部署静态网站', description: 'GitHub Pages 官方发布指南，适合个人网站与社团主页。', category: 'development', label: '开发工具', source: 'GitHub Docs', url: 'https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages' },
  { icon: 'git', title: 'GitHub 入门练习', description: '通过官方练习了解仓库、提交与协作流程。', category: 'development', label: '开发工具', source: 'GitHub', url: 'https://skills.github.com/' },
  { icon: 'chip', title: 'HDLBits · Verilog 在线练习', description: '从小电路开始练习 Verilog，熟悉数字逻辑描述。', category: 'ic', label: 'IC 入门', source: 'HDLBits', url: 'https://hdlbits.01xz.net/wiki/Main_Page' },
  { icon: 'route', title: 'OpenROAD 开源设计流程文档', description: '进一步探索数字芯片设计流程与开源 EDA 工具。', category: 'ic', label: 'IC 入门', source: 'OpenROAD', url: 'https://openroad.readthedocs.io/en/latest/' }
];

const TOPICS = ['Agent 打破信息差', '用 Agent 搭建自己的个人网站', 'Git、Agent 与提问的智慧：软技能培训', 'IC 各方向科普'];
const escapeHTML = value => String(value).replace(/[&<>"']/g, character => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[character]));
const icon = name => `<svg class="icon" aria-hidden="true"><use href="#icon-${escapeHTML(name)}"/></svg>`;
const safeURL = value => { try { const url = new URL(value); return ['https:', 'http:'].includes(url.protocol) ? url.href : ''; } catch { return ''; } };
const link = (url, label, extraClass = '') => `<a class="button ${extraClass}" href="${escapeHTML(safeURL(url))}" target="_blank" rel="noopener noreferrer">${escapeHTML(label)} <svg class="icon" aria-hidden="true"><use href="#icon-arrow"/></svg></a>`;
const topicList = () => `<ol class="topic-list">${TOPICS.map((title, index) => `<li><span>0${index + 1}</span>${escapeHTML(title)}</li>`).join('')}</ol>`;
const dialog = document.getElementById('detail-dialog');
const dialogContent = document.getElementById('dialog-content');

const DIALOGS = {
  join: () => ({ eyebrow: '加入 AI 芯动力', title: '带着好奇心，加入我们。', content: `<p>欢迎对 AI 工具或集成电路感兴趣的同学。你可以参与芯沙龙、加入项目组，也可以从内容策划、活动运营或资料整理开始。</p><div class="contact-status"><svg class="icon" aria-hidden="true"><use href="#icon-arrow"/></svg><div><strong>招新报名</strong><p>${CONFIG.recruitmentForm ? '报名入口已开放，点击下方按钮填写。' : '报名表正在准备中，正式入口将在这里公布。'}</p></div></div><div class="contact-status"><svg class="icon" aria-hidden="true"><use href="#icon-users"/></svg><div><strong>QQ 交流社群</strong><p>${CONFIG.qqGroup ? '欢迎进群讨论 AI、IC 与项目实践。' : 'QQ群入口待公布，欢迎先关注 GitHub。'}</p></div></div><div class="dialog-actions">${CONFIG.recruitmentForm ? link(CONFIG.recruitmentForm, '填写报名表') : ''}${CONFIG.qqGroup ? link(CONFIG.qqGroup, '加入 QQ 群') : ''}${link(CONFIG.github, '关注 GitHub', 'button-outline')}</div><p class="dialog-callout">项目组允许非正式成员参加，职能部门成员也可以跨组参与。</p>` }),
  salon: () => ({ eyebrow: '第一期芯沙龙', title: '第一期芯沙龙', content: `<p>第一期活动计划在期中后举行。目前正在讨论以下主题，最终主题与嘉宾安排将在确认后公布。</p><dl class="dialog-info"><dt>活动时间</dt><dd>${escapeHTML(CONFIG.salonTime)}</dd><dt>活动地点</dt><dd>${escapeHTML(CONFIG.salonLocation)}</dd><dt>当前进度</dt><dd>选题与活动筹备中</dd></dl>${topicList()}<div class="dialog-actions">${CONFIG.salonRegistration ? link(CONFIG.salonRegistration, '报名参加') : '<button class="button" data-dialog="join">关注后续通知 <svg class="icon" aria-hidden="true"><use href="#icon-arrow"/></svg></button>'}</div>` }),
  topics: () => ({ eyebrow: '芯沙龙候选主题', title: '从哪个话题开始？', content: `<p>这些是首期芯沙龙正在讨论的主题，也会作为后续活动的选题参考。</p>${topicList()}<p>最终主题、时间和参与方式将在活动区更新。</p><div class="dialog-actions"><button class="button" data-dialog="salon">查看首期预告 <svg class="icon" aria-hidden="true"><use href="#icon-arrow"/></svg></button></div>` }),
  'project-a': () => ({ eyebrow: '项目方向 · AI 工具与应用', title: 'AI 工具与应用', content: '<p>从一个具体需求开始，和同伴一起把 AI 工具用到日常学习与开发中。</p><dl class="dialog-info"><dt>探索方向</dt><dd>Agent 工作流、个人网站、AI 辅助学习</dd><dt>计划规模</dt><dd>4–6 名参与者</dd><dt>参与方式</dt><dd>可跨部门、跨项目参与，欢迎非正式成员</dd><dt>当前进度</dt><dd>项目组筹备中，具体选题待确定</dd></dl><div class="dialog-actions"><button class="button" data-dialog="join">了解如何加入 <svg class="icon" aria-hidden="true"><use href="#icon-arrow"/></svg></button></div>' }),
  'project-b': () => ({ eyebrow: '项目方向 · AI × IC', title: 'AI × IC 技术实践', content: '<p>围绕人工智能与集成电路的交叉方向，共同梳理问题、确定选题，再通过实际项目验证想法。</p><dl class="dialog-info"><dt>探索方向</dt><dd>AI for IC 技术学习与项目实践</dd><dt>计划规模</dt><dd>4–6 名参与者</dd><dt>参与方式</dt><dd>可跨部门、跨项目参与，欢迎非正式成员</dd><dt>当前进度</dt><dd>项目组筹备中，具体选题待确定</dd></dl><div class="dialog-actions"><button class="button" data-dialog="join">了解如何加入 <svg class="icon" aria-hidden="true"><use href="#icon-arrow"/></svg></button></div>' }),
  contribute: () => ({ eyebrow: '资源共建', title: '把有用的资料，留在这里。', content: `<p>欢迎分享 AI 工具教程、IC 学习资料、活动信息和竞赛线索。请附上原始链接、简短介绍，以及适合的学习阶段。</p><p class="dialog-callout">投稿建议格式：<br><strong>资料标题：</strong><br><strong>原始链接：</strong><br><strong>内容简介：</strong><br><strong>适合人群：</strong></p><p style="margin-top:16px">${CONFIG.contributionForm ? '通过投稿入口提交资料，整理后将在资源库更新。' : '投稿表单正在准备中。也可以先到社团 GitHub 查看后续开放的投稿方式。'}</p><div class="dialog-actions">${CONFIG.contributionForm ? link(CONFIG.contributionForm, '提交资料') : link(CONFIG.github, '前往社团 GitHub')}<button class="button button-outline" id="copy-template">复制投稿格式</button></div>` })
};

function openDialog(key) {
  if (!DIALOGS[key]) return;
  const details = DIALOGS[key]();
  document.getElementById('dialog-eyebrow').textContent = details.eyebrow;
  document.getElementById('dialog-title').textContent = details.title;
  dialogContent.innerHTML = details.content;
  if (!dialog.open) { dialog.showModal(); document.body.classList.add('dialog-open'); }
}

document.addEventListener('click', event => {
  const trigger = event.target.closest('[data-dialog]');
  if (trigger) openDialog(trigger.dataset.dialog);
});
document.querySelector('.dialog-close').addEventListener('click', () => dialog.close());
dialog.addEventListener('close', () => document.body.classList.remove('dialog-open'));
dialog.addEventListener('click', event => {
  if (event.target !== dialog) return;
  const box = dialog.getBoundingClientRect();
  if (event.clientX < box.left || event.clientX > box.right || event.clientY < box.top || event.clientY > box.bottom) dialog.close();
});

const menuButton = document.querySelector('.menu-button');
const navigation = document.getElementById('navigation');
function closeMenu() { navigation.classList.remove('open'); menuButton.setAttribute('aria-expanded', 'false'); menuButton.setAttribute('aria-label', '打开导航'); }
menuButton.addEventListener('click', () => {
  const open = navigation.classList.toggle('open');
  menuButton.setAttribute('aria-expanded', String(open));
  menuButton.setAttribute('aria-label', open ? '关闭导航' : '打开导航');
});
navigation.querySelectorAll('a').forEach(anchor => anchor.addEventListener('click', closeMenu));
document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
document.addEventListener('click', event => { if (!event.target.closest('.header')) closeMenu(); });
window.matchMedia('(min-width: 621px)').addEventListener('change', event => { if (event.matches) closeMenu(); });

document.querySelectorAll('[data-event-filter]').forEach(button => button.addEventListener('click', () => {
  const filter = button.dataset.eventFilter;
  document.querySelectorAll('[data-event-filter]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
  let visible = 0;
  document.querySelectorAll('[data-event-category]').forEach(item => { item.hidden = filter !== 'all' && item.dataset.eventCategory !== filter; if (!item.hidden) visible++; });
  document.getElementById('event-list').hidden = !visible;
  document.getElementById('event-empty').hidden = !!visible;
  document.getElementById('event-empty-title').textContent = filter === 'competition' ? '竞赛信息正在整理中' : '学院资讯正在整理中';
  document.getElementById('event-empty-description').textContent = filter === 'competition' ? '后续将在这里更新赛事通知与参与方式，欢迎提供竞赛线索。' : '后续将在这里更新学院内活动与交流信息，欢迎提供线索。';
}));

let resourceFilter = 'all';
const resourceSearch = document.getElementById('resource-search');
function renderResources() {
  const query = resourceSearch.value.trim().toLocaleLowerCase();
  const matched = RESOURCES.filter(resource => (resourceFilter === 'all' || resource.category === resourceFilter) && `${resource.title} ${resource.description} ${resource.source} ${resource.label}`.toLocaleLowerCase().includes(query));
  const featured = matched.filter(resource => resource.featured);
  const library = matched.filter(resource => !resource.featured);
  document.getElementById('featured-resources').innerHTML = featured.map(resource => `<a class="featured-resource resource-item" href="${escapeHTML(resource.url)}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHTML(resource.title)}，在新窗口打开"><span class="featured-icon">${icon(resource.icon)}</span><div class="featured-details"><div class="featured-label">${escapeHTML(resource.label)}</div><h3>${escapeHTML(resource.title)}</h3><p>${escapeHTML(resource.description)}</p><span class="site-host">${escapeHTML(resource.host)}</span></div>${icon('arrow')}</a>`).join('');
  document.getElementById('featured-resource-section').hidden = !featured.length;
  document.getElementById('library-heading').hidden = !library.length;
  document.getElementById('resource-list').hidden = !library.length;
  document.getElementById('resource-list').innerHTML = library.map(resource => `<a class="resource-row resource-item" href="${escapeHTML(resource.url)}" target="_blank" rel="noopener noreferrer" aria-label="${escapeHTML(resource.title)}，在新窗口打开"><span class="resource-icon">${icon(resource.icon)}</span><div><h3>${escapeHTML(resource.title)}</h3><p>${escapeHTML(resource.description)}</p></div><span class="resource-category">${escapeHTML(resource.label)}</span><span class="resource-source">${escapeHTML(resource.source)}</span><span class="resource-out">${icon('arrow')}</span></a>`).join('');
  document.getElementById('resource-empty').hidden = matched.length > 0;
  document.getElementById('resource-count').textContent = `显示 ${matched.length} / ${RESOURCES.length} 份资源`;
}
document.querySelectorAll('[data-resource-filter]').forEach(button => button.addEventListener('click', () => {
  resourceFilter = button.dataset.resourceFilter;
  document.querySelectorAll('[data-resource-filter]').forEach(item => { const active = item === button; item.classList.toggle('active', active); item.setAttribute('aria-pressed', String(active)); });
  renderResources();
}));
resourceSearch.addEventListener('input', renderResources);
renderResources();

let toastTimeout;
function showToast(message) {
  const toast = document.getElementById('toast'); toast.textContent = message; toast.classList.add('visible');
  clearTimeout(toastTimeout); toastTimeout = setTimeout(() => toast.classList.remove('visible'), 3200);
}
dialogContent.addEventListener('click', async event => {
  if (!event.target.closest('#copy-template')) return;
  const template = '资料标题：\n原始链接：\n内容简介：\n适合人群：';
  try {
    if (!navigator.clipboard?.writeText) throw new Error('Clipboard unavailable');
    await navigator.clipboard.writeText(template);
    showToast('投稿格式已复制');
  } catch {
    const range = document.createRange(); range.selectNodeContents(dialogContent.querySelector('.dialog-callout'));
    const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);
    showToast('请复制已选中的投稿格式');
  }
});

if ('IntersectionObserver' in window) {
  const navObserver = new IntersectionObserver(entries => {
    entries.forEach(entry => { if (entry.isIntersecting) navigation.querySelectorAll('a').forEach(anchor => anchor.classList.toggle('current', anchor.getAttribute('href') === `#${entry.target.id}`)); });
  }, { rootMargin: '-15% 0px -55% 0px' });
  ['about', 'events', 'projects', 'resources'].forEach(id => navObserver.observe(document.getElementById(id)));
}
