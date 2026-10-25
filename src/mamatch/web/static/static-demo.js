/* Static demo only (added by `mamatch export-static`). Runs the opportunities search in the browser
   using the band edges on each card, and stops every other form from submitting. */
(() => {
  const num = v => (v === '' || v == null ? null : Number(v));
  const form = document.getElementById('search');
  const results = [...document.querySelectorAll('.result')];
  const count = document.getElementById('result-count');

  function matches(el, f) {
    const d = el.dataset;
    if (f.sector && d.sector !== f.sector) return false;
    if (f.macro && d.macro !== f.macro) return false;
    if (f.q) {
      const words = f.q.toLowerCase().replace(/[，,]/g, ' ').split(/\s+/).filter(Boolean);
      if (!words.every(w => d.words.includes(w))) return false;
    }
    // Each filter value is a band edge, so comparing band edges equals comparing the hidden figures.
    const lo = (key, min) => min == null || (num(d[key]) != null && num(d[key]) >= min);
    const hi = (key, max) => max == null || (num(d[key]) != null && num(d[key]) <= max);
    if (!lo('revLo', num(f.revenue_min)) || !hi('revHi', num(f.revenue_max))) return false;
    if (num(f.revenue_max) != null && d.revHi === '') return false;
    if (!lo('empLo', num(f.employees_min)) || !hi('empHi', num(f.employees_max))) return false;
    if (num(f.employees_max) != null && d.empHi === '') return false;
    if (!lo('yrsLo', num(f.years_min))) return false;
    if (num(f.price_max) != null && (d.priceHi === '' || num(d.priceHi) > num(f.price_max))) return false;
    if (f.profitable === 'yes' && d.profitable !== 'yes') return false;
    if (num(f.margin_min) != null && !lo('marginLo', num(f.margin_min))) return false;
    if (f.reasons.length && !f.reasons.includes(d.reason)) return false;
    if (f.deal_types.length && !f.deal_types.includes(d.deal)) return false;
    return true;
  }

  function run() {
    const fd = new FormData(form);
    const f = Object.fromEntries([...fd.entries()].filter(([k]) => !['reasons', 'deal_types'].includes(k)));
    f.reasons = fd.getAll('reasons');
    f.deal_types = fd.getAll('deal_types');
    let shown = 0;
    results.forEach(el => { const ok = matches(el, f); el.hidden = !ok; shown += ok; });
    if (count) count.textContent = count.dataset.tpl.replace('%d', shown).replace('%d', count.dataset.total);
  }

  if (form) {
    form.addEventListener('submit', e => { e.preventDefault(); run(); });
    const clear = form.querySelector('a[href$="opportunities"], a[href$="opportunities/"], a[href$="index.html"]');
    if (clear) clear.addEventListener('click', e => { e.preventDefault(); form.reset(); run(); });
  }

  document.querySelectorAll('form').forEach(f => {
    if (f === form) return;
    f.addEventListener('submit', e => {
      e.preventDefault();
      alert(document.documentElement.lang.startsWith('zh')
        ? '这是静态演示：表单和按钮不会提交。'
        : 'This is a static demo: forms and buttons do not submit.');
    });
  });

  // ---------------------------------------------------------------- guided tour
  const steps = window.MM_TOUR || [];
  const me = document.querySelector('script[src$="static-demo.js"]');
  if (!steps.length || !me) return;
  const root = new URL('../', me.src);  // static/ sits at the site root
  const lang = document.documentElement.lang.startsWith('zh') ? 'zh' : 'en';
  const key = 'mm-tour-step';
  const go = i => {
    try { sessionStorage.setItem(key, String(i)); } catch {}
    location.href = new URL(lang + '/' + steps[i].path, root).href;
  };
  document.querySelectorAll('[data-start-tour]').forEach(b => {
    b.hidden = false;
    b.addEventListener('click', e => { e.preventDefault(); go(0); });
  });
  let i = null;
  try { i = sessionStorage.getItem(key); } catch {}
  if (i === null) return;
  i = Number(i);
  if (!(i >= 0 && i < steps.length)) return;
  const zh = lang === 'zh';
  const bar = document.createElement('div');
  bar.className = 'tour-bar';
  bar.setAttribute('role', 'region');
  bar.setAttribute('aria-label', zh ? '导览' : 'Guided tour');
  const text = document.createElement('p');
  text.textContent = (zh ? `导览 ${i + 1}/${steps.length}：` : `Tour ${i + 1} of ${steps.length}: `) + steps[i][lang];
  const nav = document.createElement('div');
  const button = (label, fn) => { const b = document.createElement('button'); b.type = 'button'; b.textContent = label; b.addEventListener('click', fn); nav.append(b); return b; };
  if (i > 0) button(zh ? '上一步' : 'Back', () => go(i - 1)).className = 'ghost';
  if (i < steps.length - 1) button(zh ? '下一步' : 'Next', () => go(i + 1));
  button(zh ? '结束导览' : 'End tour', () => { try { sessionStorage.removeItem(key); } catch {} bar.remove(); }).className = 'ghost';
  bar.append(text, nav);
  document.body.prepend(bar);
})();

