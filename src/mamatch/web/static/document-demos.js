// Export only rendered fictional text; no storage, provider calls or deal mutations.
(() => {
  const preview = document.getElementById('document-preview');
  if (!preview) return;
  const zh = document.documentElement.lang.startsWith('zh');
  document.getElementById('document-download').addEventListener('click', () => {
    const blob = new Blob([preview.innerText], {type: 'text/plain;charset=utf-8'});
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = zh ? '柳树项目－虚构演示文档.txt' : `project-willow-${location.pathname.split('/').pop()}-fictional-demo.txt`;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    document.getElementById('document-status').textContent = zh ? '演示文本已导出；未发送或签署。' : 'Demo text exported; nothing sent or signed.';
  });
  document.getElementById('document-print').addEventListener('click', () => window.print());
})();
