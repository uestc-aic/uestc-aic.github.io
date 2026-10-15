'use strict';

/* ═══════════════════════════════════════════════════════════════
   AI 芯动力 · UESTC AIC —— 站点交互
   零依赖原生 JS。约束见 DESIGN.md §7：
   只动 opacity / transform，不动布局属性；尊重 prefers-reduced-motion。
   类名与既有设计系统一致（.nav.open / .toast.visible / .resource-filter.active）。
   ═══════════════════════════════════════════════════════════════ */

(function () {
  const prefersReduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  /* ── Toast ──────────────────────────────────────────────── */
  let toastTimer;
  function toast(message) {
    const el = document.getElementById('toast');
    if (!el) return;
    el.textContent = message;
    el.classList.add('visible');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => el.classList.remove('visible'), 3200);
  }

  /* ── sticky 导航滚动状态 ────────────────────────────────── */
  const header = document.querySelector('.header');
  if (header) {
    const onScroll = () => header.classList.toggle('scrolled', window.scrollY > 40);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
  }

  /* ── 移动端导航抽屉 ─────────────────────────────────────── */
  const menuButton = document.querySelector('.menu-button');
  const navigation = document.getElementById('navigation');
  if (menuButton && navigation) {
    const setOpen = (open) => {
      navigation.classList.toggle('open', open);
      menuButton.setAttribute('aria-expanded', String(open));
      menuButton.setAttribute('aria-label', open ? '关闭导航' : '打开导航');
    };
    menuButton.addEventListener('click', (e) => {
      e.stopPropagation();
      setOpen(!navigation.classList.contains('open'));
    });
    navigation.addEventListener('click', (e) => { if (e.target.closest('a')) setOpen(false); });
    document.addEventListener('keydown', (e) => { if (e.key === 'Escape') setOpen(false); });
    document.addEventListener('click', (e) => { if (!e.target.closest('.header')) setOpen(false); });
    window.matchMedia('(min-width: 851px)').addEventListener('change', (e) => { if (e.matches) setOpen(false); });
  }

  /* ── 入场 reveal ────────────────────────────────────────── */
  const revealTargets = document.querySelectorAll('[data-reveal]');
  if (prefersReduced || !('IntersectionObserver' in window)) {
    revealTargets.forEach((el) => el.classList.add('revealed'));
  } else {
    const io = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) { entry.target.classList.add('revealed'); io.unobserve(entry.target); }
      });
    }, { rootMargin: '0px 0px -12% 0px', threshold: 0.08 });
    revealTargets.forEach((el) => io.observe(el));
  }

  /* ═══════════════════════════════════════════════════════════
     通用筛选器
     容器 [data-filter-root] / 按钮 [data-filter-btn][data-filter-key]
     条目 [data-filter-item][data-filter-cat] / 空态 [data-filter-empty]
     计数 [data-filter-count]
     ═══════════════════════════════════════════════════════════ */
  const roots = Array.from(document.querySelectorAll('[data-filter-root]'));
  roots.forEach((root) => {
    const buttons = Array.from(root.querySelectorAll('[data-filter-btn]'));
    const items = Array.from(root.querySelectorAll('[data-filter-item]'));
    const emptyEl = root.querySelector('[data-filter-empty]');
    const countEl = root.querySelector('[data-resource-count]');
    const searchInput = root.querySelector('#resource-search');
    if (!buttons.length) return;

    const counts = { all: items.length };
    items.forEach((item) => {
      const cat = item.dataset.filterCat || '';
      counts[cat] = (counts[cat] || 0) + 1;
    });
    // 计数自动填，避免运维手写数字对不上
    buttons.forEach((btn) => {
      const slot = btn.querySelector('[data-filter-count]');
      if (!slot) return;
      const n = counts[btn.dataset.filterKey] ?? 0;
      slot.textContent = String(n);
      if (n === 0) btn.classList.add('is-empty');
    });

    let activeCat = 'all';
    function apply() {
      const q = (searchInput?.value || '').trim().toLowerCase();
      let visible = 0;
      items.forEach((item) => {
        const catOk = activeCat === 'all' || item.dataset.filterCat === activeCat;
        const textOk = !q || (item.dataset.search || '').includes(q);
        const show = catOk && textOk;
        item.hidden = !show;
        if (show) visible += 1;
      });
      buttons.forEach((btn) => btn.classList.toggle('active', btn.dataset.filterKey === activeCat));
      buttons.forEach((btn) => btn.setAttribute('aria-pressed', String(btn.dataset.filterKey === activeCat)));
      if (emptyEl) emptyEl.hidden = visible > 0;
      if (countEl) countEl.textContent = `显示 ${visible} / ${items.length} 份资源`;
      // 同步 URL，便于把筛选结果分享出去
      const url = new URL(window.location.href);
      if (activeCat === 'all') url.searchParams.delete('f');
      else url.searchParams.set('f', activeCat);
      history.replaceState(null, '', url);
    }

    buttons.forEach((btn) => btn.addEventListener('click', () => {
      activeCat = btn.dataset.filterKey;
      apply();
    }));
    if (searchInput) searchInput.addEventListener('input', apply);

    const initial = new URL(window.location.href).searchParams.get('f');
    if (initial && counts[initial] !== undefined) activeCat = initial;
    apply();
  });

  /* ── 复制按钮 ───────────────────────────────────────────── */
  document.addEventListener('click', async (e) => {
    const btn = e.target.closest('[data-copy]');
    if (!btn) return;
    const text = btn.dataset.copy;
    try {
      if (!navigator.clipboard?.writeText) throw new Error('clipboard unavailable');
      await navigator.clipboard.writeText(text);
      toast(btn.dataset.copyMessage || '已复制到剪贴板');
    } catch {
      const target = btn.parentElement?.querySelector('code') || btn;
      const range = document.createRange();
      range.selectNodeContents(target);
      const selection = window.getSelection();
      selection.removeAllRanges();
      selection.addRange(range);
      toast('已选中内容，请按 Ctrl+C 复制');
    }
  });
})();
