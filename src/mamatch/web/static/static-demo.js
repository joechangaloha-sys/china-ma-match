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
})();
