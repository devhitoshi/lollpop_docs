---
name: posfie-summary
description: 「ろりぽっぷ!!!!!!!」の1週間分の X 投稿を posfie（Xポストまとめサービス）のまとめにする。取得済みの投稿データから貼るポストを選び、タイトル・見出し・各ポストへのコメントを素材 md にまとめ、Playwright で posfie の編集画面に投入するところまで。「posfie にまとめて」「ポストをまとめて」「1週間分の投稿をまとめたい」「生誕祭のまとめを作って」と言われたときに使う。note 用の記事は weekly-monthly-draft の担当。
---

# posfie まとめの作成

note の週刊まとめが「読ませる記事」なのに対して、posfie は**ポストを時系列に並べて、その日の空気を見せる**もの。
生誕祭やワンマンのように投稿が1日に集中する回と相性がいい。

## posfie 側の制約（先に知っておく）

- **ログインは X の OAuth。** X の自動ログインはしない（自動化検知・2FA があり、規約上も避ける）。
  人が1回通してセッションを保存し、以降はそれを使い回す
- **ポストの追加は「URL を貼り付けて取得 → 左カラムから中央カラムへドラッグ&ドロップ」。**
  DnD は DOM 構造に依存するので壊れやすい。**壊れても素材 md があれば手で貼って完成できる**、という前提で組む
- 見出しやテキストは「デコレーション」で差し込める。表組みは無い

## 手順

### 1. データを揃える

`work/x_fetch/` に対象期間の投稿があること。無ければ取得する。

```bash
# 公式・メンバー（--max-tweets-per-account は「期間内の件数」ではなく jsonl の総件数の上限。
# 既存件数より大きい値を渡さないと1件も取りに行かない。kurumi_lpop は既に4000件ある）
python3 .claude/skills/x-account-fetch/scripts/fetch_accounts.py \
  --since 2026-09-01 --until 2026-09-08 --max-tweets-per-account 4200 --yes
```

現場の反応は `x-egosearch` の判定済みデータ（`data/x/egosearch_adopted_*.txt` と
`work/x_fetch/egosearch_triage_*_final.jsonl`）を使う。無ければ `x-egosearch` を先に回す。

### 2. 候補を切り出す

```bash
python3 .claude/skills/posfie-summary/scripts/build_material.py \
  --since 2026-09-01 --until 2026-09-07
```

`work/posfie/<since>_<until>_素材データ.md` に候補が出る。スクリプトが自動で外すもの:

- RT（本人の言葉ではない）、メンバーのリプライ（文脈が切れて読めない）
- `@mo_8_c`（オーナー本人。外部の反応として扱わない）
- **同じ文面が複数アカウントに現れる投稿**（「文章ガチャ」のような生成文。個々のファンの言葉として引用できない）

### 3. 選ぶ・書く

`articles/posfie/<since>_<until>.md` に素材 md を作る。既存の
[`articles/posfie/2026-09-01_2026-09-07.md`](../../../articles/posfie/2026-09-01_2026-09-07.md) が雛形。

- **40〜60 件**が読み通せる分量。日ごとに章を切り、章の頭に見出しとリード2〜3文
- コメントは要所だけ。全部に付けると読み手の目が滑る
- 文体は [`prompts/write/style_ai_poppar.md`](../../../prompts/write/style_ai_poppar.md)。
  **「地下アイドル」「レア曲」を使わない、`!` は1文に1個、事実に感情を混ぜない、
  メンバーの写真は貼らない（X の埋め込みのみ）**
- **外した投稿は理由とセットで素材 md の末尾に記録する。**同じ判断を毎回やり直さないため
- 手作業でやりがちな取りこぼし: 同一アカウントの連投（1〜2件に絞る）、
  役職の誤記（現グループに「リーダー」は無い）、メンバーの本名に触れた投稿

### 4. 検証

```bash
python3 - <<'PY'
import re
src = open("work/posfie/2026-09-01_2026-09-07_素材データ.md", encoding="utf-8").read()
mat = open("articles/posfie/2026-09-01_2026-09-07.md", encoding="utf-8").read()
known = set(re.findall(r"https://x\.com/\w+/status/\d+", src))
used  = re.findall(r"https://x\.com/\w+/status/\d+", mat)
print(len(used), "件／重複", len(used)-len(set(used)), "／データに無いURL", [u for u in used if u not in known])
PY
```

**URL を推測で組み立てない。**取得データに無い URL が混ざっていないことをここで確かめる。

### 5. posfie に入れる

```bash
# 初回・セッション切れのとき。ブラウザが開くので人が X 認証を通す（完了は自動検知）
python .claude/skills/posfie-summary/scripts/posfie_post.py --login

# URL の投入。タイトル・説明も入る。公開ボタンは押さない
python .claude/skills/posfie-summary/scripts/posfie_post.py --build articles/posfie/2026-09-01_2026-09-07.md
```

並べ替え・見出しの差し込み・公開は人がやる。**セレクタが合わなくなったら `--inspect` で
編集画面の要素を一覧にして、`posfie_post.py` の候補セレクタを直す。**
直すより手で貼ったほうが早いなら、深追いしない（posfie 側の DOM が変わるたび壊れるものを保守しない）。

### 6. 記録

公開したら URL と公開日を [`articles/posfie/README.md`](../../../articles/posfie/README.md) の表に足す。
