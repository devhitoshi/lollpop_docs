/* note の編集画面（editor.note.com/notes/<key>/edit/）で使う操作の関数。
 * javascript_tool（action: javascript_exec）にこのファイルの中身をそのまま渡すと、
 * window.__note に関数が入る。タブを開き直したら（ページが変わったら）入れ直す。
 *
 * どれも 2026-09-29 に実際の編集画面で確かめた手順。理由は SKILL.md の「なぜこの手順か」。
 *
 * 時間のかかる処理（embedBatch・pasteImgAt）は await すると 45 秒で javascript_tool が
 * タイムアウトすることがある。長いものは .then で window.__note.last に結果を置き、
 * wait のあとに読みに行く（SKILL.md の手順どおり）。
 */
(() => {
  const sleep = ms => new Promise(r => setTimeout(r, ms));
  const ed = () => document.querySelector('.ProseMirror');
  const sel = () => getSelection();
  const caretAt = (node, offset = 0) => {
    ed().focus();
    const r = document.createRange(); r.setStart(node, offset); r.collapse(true);
    sel().removeAllRanges(); sel().addRange(r);
  };
  const selectContents = node => {
    ed().focus();
    const r = document.createRange(); r.selectNodeContents(node);
    sel().removeAllRanges(); sel().addRange(r);
  };
  const paste = (type, value) => {
    const dt = new DataTransfer();
    if (type === 'file') dt.items.add(value); else dt.setData(type, value);
    if (type === 'text/html') dt.setData('text/plain', 'x');
    ed().dispatchEvent(new ClipboardEvent('paste', { clipboardData: dt, bubbles: true, cancelable: true }));
  };
  const key = (k, code) => ed().dispatchEvent(new KeyboardEvent('keydown', { key: k, code: k, keyCode: code, bubbles: true, cancelable: true }));
  const isEmpty = e => !e.innerText.trim() && !e.querySelector('img,iframe') && !e.hasAttribute('embedded-service');
  const isImageFig = e => e.tagName === 'FIGURE' && e.querySelector('img') && !e.hasAttribute('embedded-service');

  const N = {
    last: null,

    /** タイトル欄に入れる。type で打つと「!」や数字が落ちることがあるので値を直接入れる */
    setTitle(title) {
      const t = document.querySelector('textarea');
      Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value').set.call(t, title);
      t.dispatchEvent(new Event('input', { bubbles: true }));
      t.dispatchEvent(new Event('change', { bubbles: true }));
      t.blur();
      return t.value;
    },

    /** 本文を全部消す。引用枠が1つ残ることがあるので、先頭が段落になるまで消す */
    async clearBody() {
      selectContents(ed()); await sleep(200); document.execCommand('delete'); await sleep(500);
      for (let n = 0; n < 3 && ed().children[0].tagName !== 'P'; n++) {
        const t = ed().children[0].querySelector('p') || ed().children[0];
        caretAt(t); await sleep(150); key('Backspace', 8); await sleep(300);
      }
      return [...ed().children].map(e => e.tagName);
    },

    /** 本文 HTML を流し込む（空の本文の先頭に貼る）。先頭の引用ブロックは fixQuote で直す */
    async pasteBody(html) {
      caretAt(ed().children[0]); await sleep(300);
      paste('text/html', html); await sleep(3000);
      const tags = {}; for (const e of ed().children) tags[e.tagName] = (tags[e.tagName] || 0) + 1;
      return { tags, links: ed().querySelectorAll('a').length, first: [...ed().children].slice(0, 2).map(e => e.tagName + ':' + e.innerText.slice(0, 12)) };
    },

    /** 貼ると先頭の引用が普通の段落になり、直後に空の引用枠ができる。文を引用枠へ移して段落を消す */
    async fixQuote() {
      const [p0, q] = ed().children;
      if (!(p0.tagName === 'P' && q && q.tagName === 'FIGURE' && !q.innerText.trim())) return 'skip（形が想定と違う）';
      const txt = p0.innerText.trim();
      caretAt(q.querySelector('p')); await sleep(200);
      document.execCommand('insertText', false, txt); await sleep(400);
      if (ed().children[1].innerText.trim() !== txt) return 'NG（引用枠に入らなかった）';
      selectContents(ed().children[0]); await sleep(150); document.execCommand('delete'); await sleep(300);
      const e0 = ed().children[0];
      if (!e0.innerText.trim()) { caretAt(e0); key('Delete', 46); await sleep(300); }
      return ed().children[0].tagName + ':' + ed().children[0].innerText.slice(0, 12);
    },

    /** 単独行の URL をカードにする。「出典」見出しより後ろは触らない。skip に入れた URL も触らない */
    async embedBatch(max = 4, skip = []) {
      const re = /^https?:\/\/\S+$/;
      const targets = () => {
        const out = [];
        for (const e of ed().children) {
          if (/^H[23]$/.test(e.tagName) && /出典|編集メモ/.test(e.innerText)) break;
          if (e.tagName === 'P' && re.test(e.innerText.trim()) && !skip.includes(e.innerText.trim())) out.push(e);
        }
        return out;
      };
      const log = [];
      for (let i = 0; i < max; i++) {
        const p = targets()[0]; if (!p) break;
        const url = p.innerText.trim();
        const before = ed().querySelectorAll(':scope > figure[embedded-service]').length;
        selectContents(p); await sleep(250); document.execCommand('delete'); await sleep(250);
        paste('text/plain', url);
        let ok = false;
        for (let k = 0; k < 16 && !ok; k++) { await sleep(500); ok = ed().querySelectorAll(':scope > figure[embedded-service]').length > before; }
        log.push((ok ? 'OK ' : 'NG ') + url);
        if (!ok) break;
      }
      return { log, remaining: targets().map(p => p.innerText.trim()) };
    },

    /** 画像を入れるための自前のファイル欄を作る。find で「claude image source」を探し、file_upload で渡す */
    makeFileInput() {
      let inp = document.getElementById('claude-img-src');
      if (!inp) {
        inp = document.createElement('input');
        inp.type = 'file'; inp.id = 'claude-img-src'; inp.accept = 'image/png,image/jpeg';
        inp.style.cssText = 'position:fixed;left:0;top:0;width:10px;height:10px;opacity:0.01;z-index:99999';
        inp.setAttribute('aria-label', 'claude image source');
        document.body.appendChild(inp);
      }
      return 'ready';
    },

    /** 【画像…】の段落を、自前のファイル欄に入っている画像に差し替える（画像ファイルの paste） */
    async pasteImgAt(label) {
      const f = document.getElementById('claude-img-src').files[0];
      if (!f) return 'ファイル欄が空（file_upload が先）';
      const p = [...ed().children].find(e => e.tagName === 'P' && e.innerText.trim().startsWith(label));
      if (!p) return 'notfound: ' + label;
      const before = ed().querySelectorAll(':scope > figure img').length;
      selectContents(p); await sleep(200); document.execCommand('delete'); await sleep(300);
      paste('file', f);
      for (let k = 0; k < 24; k++) { await sleep(500); if (ed().querySelectorAll(':scope > figure img').length > before) break; }
      return f.name + ' -> ' + N.images().join(' | ');
    },

    /** 本文の画像の位置（直後の段落の頭）を一覧する */
    images() {
      const kids = [...ed().children];
      return kids.filter(isImageFig).map(f => { const i = kids.indexOf(f); return i + ':' + (kids[i + 1]?.innerText || '').slice(0, 12); });
    },

    /**
     * 空の段落・空の引用枠を下から消す。
     * 画像のすぐ下の空段落で止める。画像の直後で Backspace を押すと、下の段落が画像のキャプションに吸い込まれるため
     */
    async cleanupEmpty() {
      const log = [];
      for (let n = 0; n < 15; n++) {
        const kids = [...ed().children];
        const idx = kids.map((e, i) => (isEmpty(e) ? i : -1)).filter(i => i >= 0).pop();
        if (idx === undefined) break;
        if (kids[idx - 1] && isImageFig(kids[idx - 1])) { log.push('skip（画像の直後） ' + idx); break; }
        const t = kids[idx].querySelector('p') || kids[idx];
        caretAt(t); await sleep(150); key('Backspace', 8); await sleep(250);
        log.push(idx + ':' + kids[idx].tagName);
      }
      return log;
    },

    /** 文中の段落の文字列を置き換える（一覧の1行を書き換えるときなど）。見つかった最初の1つだけ */
    async replaceText(oldText, newText) {
      const w = document.createTreeWalker(ed(), NodeFilter.SHOW_TEXT);
      let n;
      while ((n = w.nextNode())) {
        const i = n.textContent.indexOf(oldText);
        if (i >= 0) {
          ed().focus();
          const r = document.createRange(); r.setStart(n, i); r.setEnd(n, i + oldText.length);
          sel().removeAllRanges(); sel().addRange(r); await sleep(150);
          document.execCommand('insertText', false, newText); await sleep(250);
          return 'OK';
        }
      }
      return 'notfound';
    },

    /** 一覧の項目（文字列が完全一致する li）をリンクにする */
    async linkListItem(label, url) {
      const li = [...ed().querySelectorAll('li')].find(l => l.innerText.trim() === label);
      if (!li) return 'notfound: ' + label;
      selectContents(li.querySelector('p') || li); await sleep(200);
      paste('text/html', `<a href="${url}">${label}</a>`); await sleep(500);
      const li2 = [...ed().querySelectorAll('li')].find(l => l.innerText.trim() === label);
      return li2 && li2.querySelector('a') ? 'OK ' + li2.querySelector('a').href : 'NOLINK';
    },

    /** 状態の確認 */
    status() {
      const kids = [...ed().children];
      return {
        title: document.querySelector('textarea')?.value,
        blocks: kids.length,
        firstIsQuote: kids[0]?.tagName === 'FIGURE' && !!kids[0].querySelector('blockquote'),
        cards: ed().querySelectorAll(':scope > figure[embedded-service]').length,
        images: N.images(),
        marks: kids.filter(e => /^【画像|^https?:\/\/\S+$/.test(e.innerText.trim())).map(e => e.innerText.trim().slice(0, 40)),
        empties: kids.map((e, i) => (isEmpty(e) ? i : null)).filter(x => x !== null),
      };
    },

    /** 保存の完了表示を拾う（表示は数秒で消える） */
    savedToast() {
      return (document.body.innerText.match(/下書きを保存しました|保存に失敗[^\n]*/g) || ['(表示なし)']).join(',');
    },

    /** ネイティブのファイル選択ダイアログを開かせない（見出し画像の「画像をアップロード」用） */
    hookFileDialog() {
      if (window.__fileHook) return 'already';
      window.__fileHook = true;
      const orig = HTMLInputElement.prototype.click;
      HTMLInputElement.prototype.click = function () {
        if (this.type === 'file') { if (!this.isConnected) { this.style.display = 'none'; document.body.appendChild(this); } return; }
        return orig.apply(this, arguments);
      };
      HTMLInputElement.prototype.showPicker = function () {
        if (this.type === 'file' && !this.isConnected) { this.style.display = 'none'; document.body.appendChild(this); }
      };
      return 'hooked';
    },
  };
  window.__note = N;
  return Object.keys(N).filter(k => typeof N[k] === 'function');
})();
