---
name: note-publish
description: note（https://note.com/1116_fan）への記事の投稿・下書き作成・公開済み記事の更新を、Claude in Chrome のブラウザ操作で行う手順書。原稿（articles/ の Markdown）を note に流し込む、X や note の URL を埋め込みカードにする、図版を入れる、見出し画像を設定する、公開済み記事の本文を差し替える、ときは必ずこのスキルに従う。「note に投稿して」「下書きを作って」「note に貼って」「公開済みの記事を更新して」「貼り替えて」と言われたときに使う。
---

# note への投稿（ブラウザ操作）

2026-09-29 に、シルバーウィーク2026・スターターパック3本・全楽曲解説・旧スターターパック・3曲のコール表を
この手順で投稿／更新した。**手探りで同じ失敗を繰り返さないため、note を触るときは毎回ここから始める。**
うまくいかなかったことと、その回避策も「つまずいたこと」に全部残してある。

- 原稿→HTML の変換: [`scripts/md2note.py`](scripts/md2note.py)
- 編集画面での操作: [`scripts/helpers.js`](scripts/helpers.js)（javascript_tool に中身を渡すと `window.__note` に関数が入る）
- 記事の書き方・公開前レビューは別: `article-review`（レビュー）、`article-refresh`（公開済み記事の改稿）
- X の URL だけをまとめてカードにしたいとき（オーナーが自分で貼った下書き）: [`articles/note_embed_x/`](../../../articles/note_embed_x/README.md) のブックマークレット

## 守ること

1. **「公開」「更新する」はオーナーの OK をもらってから押す。** 1本ごとに確認する。下書き保存までは確認なしでよい
2. 公開前に `article-review` の機械チェックを通す（ERROR 0）。数字の時点（◯月◯日時点）と編集メモの除去を確認する
3. 全記事共通の注意書き `> ※Xの投稿を中心にAIで分析して限界オタクの性格づけして本記事を書き上げてます。` が冒頭の引用枠に入っていること
4. タブは自分で新しく開く（`tabs_create_mcp`）。終わったら閉じる。**古いタブのまま保存しない**
   （オーナーが別のブラウザで同じ下書きを直していたら上書きしてしまう。心配なら新しいタブで開き直して中身を比べる）
5. 公開・更新したら `articles/公開一覧.md` に URL・公開日・最終同期日を記録し、PR にする

## 手順：新しい記事を下書きまで作る

### 1. 原稿を HTML にする

```bash
python .claude/skills/note-publish/scripts/md2note.py articles/…/原稿.md > "$TEMP/note_body.json"
# 標準エラーに件数が出る: card_urls（カードにする URL の数）、image_marks（画像の目印）、blockquotes
```

- 原稿に注意書きの `> ※…` が無い（例: `songs/楽曲一覧.md`）ときは、HTML の先頭に
  `<blockquote><p>※Xの投稿を中心に…</p></blockquote>` を足してから使う
- 同じシリーズの他の記事の URL（相互リンク）は、**下書きを作った時点で確定する**（下書きの key がそのまま公開 URL）。
  先に全記事の下書きを作り、あとから `linkListItem` やカード化で埋めればよい

### 2. 新しい下書きを開いてタイトルを入れる

1. `tabs_create_mcp` → `navigate` で `https://note.com/notes/new`（`editor.note.com/notes/<key>/edit/` に飛ぶ。この key が公開 URL になる）
2. 5秒待つ → javascript_tool で `helpers.js` の中身を実行 → `window.__note.setTitle('タイトル')`

### 3. 本文を流し込む

```js
await window.__note.pasteBody(HTML)   // HTML は md2note.py の html
await window.__note.fixQuote()        // 先頭の注意書きを引用枠に入れ直す
```

### 4. URL をカードにする

時間がかかるので、`.then` で結果を置いて待つ（await すると 45 秒でタイムアウトすることがある）。

```js
window.__note.last = null; window.__note.embedBatch(4).then(r => window.__note.last = r); 'started'
```

`computer` の `wait` を 10〜15 秒 → `JSON.stringify(window.__note.last)` を読む。`remaining` が 0 になるまで繰り返す。
1回に4本まで。カードにしない URL は `embedBatch(4, ['https://…'])` で飛ばす（下の「カードにならない URL」）。

### 5. 図版を入れる

```js
window.__note.makeFileInput()          // 自前のファイル欄を作る
```

`find` で「file input labeled 'claude image source'」を探し、その ref に `file_upload` で画像を渡してから:

```js
await window.__note.pasteImgAt('【画像②')   // 目印の段落が画像に置き換わる
```

画像ごとに `file_upload` → `pasteImgAt` をくり返す。最後に `document.getElementById('claude-img-src').remove()`。
`window.__note.images()` で「何番目の要素の直後が何か」を見て、位置が正しいか確かめる。

### 6. 見出し画像を入れる

1. `window.__note.hookFileDialog()`（ネイティブのファイル選択ダイアログを開かせない）
2. `find` で「画像を追加 button above the title」→ `scroll_to` → `left_click`
3. 出てきたメニューの「画像をアップロード」をクリック（スクショで位置を確かめる）
4. `find` で「file input」→ id が `note-editor-eyecatch-input` のものに `file_upload`
5. トリミング画面が出る → 画像全体が枠に収まっているのを確かめて「保存」をクリック

### 7. 片付けて保存する

```js
await window.__note.cleanupEmpty()     // 空の段落・空の引用枠を消す
window.__note.status()                 // 注意書き・カード数・画像・残った目印を一覧
```

`find` で「下書き保存 button」→ クリック → `window.__note.savedToast()`。表示は数秒で消えるので、
拾えなかったら**新しいタブで `…/edit/` を開き直して `status()` を見る**（これが確実）。

### 8. 公開

オーナーにプレビューを見てもらい、OK をもらったら「公開に進む」→ 公開設定（ハッシュタグ・無料/有料）→「公開」。
公開後は `articles/公開一覧.md` と各シリーズの README に記録する。

## 手順：公開済みの記事を更新する

- **一部だけ直す**: `replaceText(旧, 新)` や `linkListItem` で書き換え、「公開に進む」→「更新する」
- **冒頭に追記する**（例: 旧スターターパックへの誘導文）: 先頭の段落の頭にカーソルを置いて `text/html` を paste する。
  末尾に `<hr>` を付けると、元の本文の1段落目と混ざらない（区切り線になる）
- **全文を差し替える**（例: 全楽曲解説）: `clearBody()` → `pasteBody(HTML)` → `fixQuote()` → カード化 → 画像。
  末尾の「メタデータ／検索用タグ」の行など、元の公開版にだけある行は先に控えておき、HTML に残す
- 更新の公開設定では、ハッシュタグ等は前回のまま引き継がれている（変えない）

## つまずいたこと（回避策つき）

| 起きたこと | 回避策 |
| --- | --- |
| Markdown をそのまま note に貼ると、URL がリンクのままでカードにならない | 空の段落に URL を paste するとカードになる → `embedBatch` |
| タイトル欄をクリックして `type` すると本文側に入る／「!」や数字が落ちる | `setTitle`（値を直接入れる） |
| HTML を貼ると先頭の引用が普通の段落になり、空の引用枠が別にできる | `fixQuote` |
| 引用枠の中に HTML を貼ると書式が全部落ちてテキストだけになる | 引用枠の外（普通の段落）に貼る |
| 本文中の「＋」→「画像」メニューで入れると、「＋」の位置が古いまま画面外に残り押せない | 画像ファイルを paste する（`makeFileInput` → `file_upload` → `pasteImgAt`） |
| **入れた画像を消せない**（クリックで選択できない。範囲選択して delete も効かない） | 画像を差し替えるときは本文を作り直す（`clearBody` から）か、オーナーに手で消してもらう |
| **画像の直後の段落の頭で Backspace を押すと、その段落が画像のキャプション欄に吸い込まれる** | 押してしまったら `ctrl+z`。`cleanupEmpty` は画像の直後で止まるようにしてある |
| 改行キー（Return）が効くタブと効かないタブがある | 段落を足すなら HTML の paste で入れる |
| 裏のタブでは処理が進まない（タイマーが間引かれる） | そのタブで `computer` の `screenshot` を撮ると前面になる |
| 長い処理を await すると 45 秒で javascript_tool がタイムアウトし、固まったように見える | `.then` で結果を置いて待つ。タイムアウトしても処理は進んでいることが多いので、`status()` で確かめてから再実行する |
| 旧スターターパック（n3d4fe835603f）の公開設定画面が、開くたびに固まった | 編集内容は下書きとして保存されているので、オーナーに「公開に進む」→「更新する」を押してもらう |
| 保存したつもりでも確証がない（完了表示がすぐ消える） | 新しいタブで開き直して `status()` |
| 画面座標が合わない | `javascript_tool` の座標（CSS px）× `1568 / window.innerWidth` がスクショの座標。`find` + `scroll_to` の方が確実 |

### カードにならない URL

| URL | 起きたこと | 扱い |
| --- | --- | --- |
| Apple Music の旧名義アーティスト（`music.apple.com/jp/artist/1798031127`） | paste するとページが固まる | `embedBatch` の skip に入れ、リンクのまま残す |
| BASE のショップ（`lollipopshop.base.ec`） | カードにならず段落ごと消える | skip に入れる。消えたら `linkListItem` 相当で文中リンクとして入れ直す |

カードになったもの: X の投稿・プロフィール、note 記事、Spotify（アーティスト）、Apple Music（現名義）、TikTok（アカウント）、TimeTree 公開カレンダー。

## 下書き・公開の記録（参考）

| 記事 | key | 方法 |
| --- | --- | --- |
| シルバーウィーク2026 | n223c076d9706 | オーナーが貼る → X の URL をカード化 |
| スターターパック（1）（2）（3） | nd98992b3a1b8 / nf09312b594be / nb81f2d33aacb | この手順で新規作成 |
| 全楽曲解説 | n849cd83c1bb4 | 全文差し替え |
| 旧スターターパック | n3d4fe835603f | 冒頭に誘導文＋カード（公開はオーナーが手動） |
| 【コール表】まずはこの3曲 | nd2cb50c690f2 | この手順で新規作成 |
