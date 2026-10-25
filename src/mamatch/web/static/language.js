/* Remember an explicit language switch. The choice stays in this
   browser (localStorage) and in a first-party cookie so the server can open the same edition
   from the neutral homepage. Ordinary links into the other edition are not remembered. */
(() => {
  const key = 'mm-language';
  document.addEventListener('click', event => {
    const link = event.target.closest('a');
    if (!link || !link.closest('[aria-label="Language"], [data-language-switch]')) return;
    const target = new URL(link.href, location.href);
    if (target.origin !== location.origin) return;
    const lang = target.pathname.split('/')[1];
    if (lang !== 'zh' && lang !== 'en') return;
    try { localStorage.setItem(key, lang); } catch {}
    document.cookie = `mm_lang=${lang}; path=/; max-age=31536000; samesite=lax`;
  });
})();
