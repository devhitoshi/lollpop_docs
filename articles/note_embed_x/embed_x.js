/* note の編集画面で、単独行の X 投稿 URL をまとめて埋め込みカードにする。
 * 仕組み: URL の段落を空にしてから、その空段落へ URL の paste イベントを送る
 * （note は「空の段落に URL を貼る」と埋め込みにする）。手で貼るのと同じ経路なので、
 * 出来上がるカードも手作業の埋め込みと同じ構造になる（2026-09-29 に 28 本で確認）。
 * 「出典」「編集メモ」の見出しより後ろは触らない（出典の URL はリンクのまま残す）。
 * ブックマークレット版は bookmarklet.txt（build_bookmarklet.py で生成）。
 */
(async () => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const ed = document.querySelector('.ProseMirror');
  const toast = msg => {
    let t = document.getElementById('embed-x-toast');
    if (!t) {
      t = document.createElement('div');
      t.id = 'embed-x-toast';
      t.style.cssText = 'position:fixed;right:16px;bottom:16px;z-index:99999;background:#222;color:#fff;padding:10px 14px;border-radius:8px;font:14px/1.5 sans-serif;max-width:360px;white-space:pre-wrap';
      document.body.appendChild(t);
    }
    t.textContent = msg;
  };
  if (!ed) { toast('note の記事編集画面で実行してください'); return; }
  const re = /^https?:\/\/(x|twitter)\.com\/[^\s\/]+\/status\/\d+\/?(\?\S*)?$/;
  const targets = () => {
    const out = [];
    for (const e of ed.children) {
      if (/^H[23]$/.test(e.tagName) && /出典|編集メモ/.test(e.innerText)) break;
      if (e.tagName === 'P' && re.test(e.innerText.trim())) out.push(e);
    }
    return out;
  };
  const total = targets().length;
  if (!total) { toast('変換する X の URL の行はありませんでした'); return; }
  let done = 0;
  const failed = [];
  for (let i = 0; i < total + 5; i++) {
    const p = targets()[0];
    if (!p) break;
    const url = p.innerText.trim();
    const key = url.match(/status\/(\d+)/)[1];
    const before = ed.querySelectorAll(':scope > figure[embedded-service]').length;
    ed.focus();
    const r = document.createRange();
    r.selectNodeContents(p);
    const s = getSelection();
    s.removeAllRanges();
    s.addRange(r);
    await sleep(300);
    document.execCommand('delete');
    await sleep(300);
    const dt = new DataTransfer();
    dt.setData('text/plain', url);
    ed.dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
    let ok = false;
    for (let k = 0; k < 20 && !ok; k++) {
      await sleep(500);
      ok = ed.querySelectorAll(':scope > figure[embedded-service]').length > before &&
        [...ed.querySelectorAll(':scope > figure[embedded-service]')].some(f => f.outerHTML.includes(key));
    }
    if (!ok) { failed.push(url); break; }
    done++;
    toast(`X の埋め込み: ${done} / ${total}`);
  }
  const msg = `X の埋め込み: ${done} / ${total} 本を変換しました` +
    (failed.length ? `\n止まった URL: ${failed.join(' ')}\n（その行を手で「＋→埋め込み」にしてから、もう一度実行してください）` : '\n最後に「下書き保存」を押してください');
  toast(msg);
  console.log('[embed-x]', msg);
})();
