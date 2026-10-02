---
name: x-egosearch-review
description: 「ろりぽっぷ!!!!!!!」のエゴサーチ候補を、スワイプ（右＝ろりぽっぷ関連／左＝別物）で人が仕分けるためのアプリを作り、その判定を判定ファイルに書き戻す。triage_egosearch.py の「要判定」を捌く工程を引き受ける。「エゴサをレビューしたい」「要判定を捌きたい」「仕分けアプリを作って」「スマホで判定したい」「判定を取り込んで」「アプリの判定を反映して」と言われたときに使う。候補の収集と機械仕分けは x-egosearch の担当。
---

# エゴサーチのレビュー（スワイプ仕分け）

`.claude/skills/x-egosearch` が集めて機械仕分けしたあと、**人が読んで決める**ところだけを引き受ける。
Claude が全部読んで判定してもよいが、**オーナーが自分で決めたいとき**（少人数のファンの投稿を、
文脈を知っている人が見分けたいとき）はこちらのほうが速くて正確になる。

- 入力: `work/x_fetch/egosearch_triage_<since>_<until>_review.txt` と `_adopt.txt`（triage の出力）
- 出力: `data/x/egosearch_decisions_<since>_<until>.txt`（判定ファイル。追跡する）
- 判定の置き場: 公開した Artifact の db の `decisions/<since>_<until>`

## 前提

- `x-egosearch` の手順1〜3（収集 → triage）まで終わっていること。`_review.txt` が無ければ先に triage を回す
- アプリは Artifact として公開する。**`capabilities` に `db` を宣言する**（判定を溜めて読み戻すため）

## 手順

### 1. アプリを作る

```bash
python3 .claude/skills/x-egosearch-review/scripts/build_triage_app.py --since 2026-09-07 --until 2026-09-15
```

`work/x_fetch/triage_app_<since>_<until>.html` ができる（1枚もの・データ埋め込み済み）。
要判定と採用候補をタブで切り替えられ、関係者（`OWN_HANDLES`）の投稿は束から外れる。

### 2. 公開する

`Artifact` ツールで、その HTML をそのまま公開する。

- `capabilities`: `{"db": {}}`
- `favicon`: 🍭
- **2回目以降は、同じ期間のアプリなら `url` を渡して同じ artifact を更新する**（判定が db に残っているので、
  続きから捌ける）。期間が変わったら新しい artifact を作る

**この HTML は他人の投稿の原文を含む。** db を宣言した artifact は組織内限定・既定で非公開になるが、
**共有リンクを配らない**こと。`data/x/` に出るのは ID と判定だけで、原文は出ない。

### 3. 人が捌く

右スワイプ＝ろりぽっぷ関連（adopt）、左＝別物（reject）。キーボードは → ← 、戻すは Z。
判定は端末（localStorage）と db の両方に入るので、途中で閉じても続きから再開できる。

アカウント単位の**備考**を書ける（「ファンのアカウント」「共演者・関係者」「同名の別物」のチップあり）。
ここに書いた説明は判定ファイルのメモ欄に入り、`data/x/known_accounts.txt` に残って次回以降の手がかりになる。
捌き終わった後でも、完了画面のアカウント一覧から書ける。

### 4. 判定を取り込む

**どちらでもよい。**

- **貼ってもらう**: アプリの「判定をコピー」の中身が、そのまま判定ファイルの中身。
  `data/x/egosearch_decisions_<since>_<until>.txt` に書けば終わり
- **db から読む**: `ArtifactData` ツールで `action: "get"`、`collection: "decisions"`、
  `doc_id: "<since>_<until>"`、`out_dir: "work/x_fetch/db"` として保存し、

  ```bash
  python3 .claude/skills/x-egosearch-review/scripts/import_decisions.py \
    --since 2026-09-07 --until 2026-09-15 \
    --from-json work/x_fetch/db/decisions/2026-09-07_2026-09-15.json
  ```

  備考をメモ欄に入れた判定ファイルができる（`--keep-existing` で、手で書いた判定を残せる）

### 5. 反映して、次回の手がかりを更新する

```bash
python3 .claude/skills/x-egosearch/scripts/triage_egosearch.py --since <since> --until <until> \
  --decisions data/x/egosearch_decisions_<since>_<until>.txt
python3 .claude/skills/x-egosearch/scripts/build_known_accounts.py
```

採用リスト・反応上位・件数（`data/x/..._summary.txt`）が出て、常連アカウントの一覧が更新される。
**判定するたびに次の週が楽になる**のがこの工程の効きどころ（→ `x-egosearch/SKILL.md` の打率の話）。

## 注意

- **判定は人の仕事。**このスキルは読む順番と道具を用意するだけで、採用・除外の基準は
  `.claude/skills/x-egosearch/SKILL.md` の手順3にある（迷ったら除外）
- アプリの HTML も db の中身も**他人の投稿**。再配布・公開・学習利用はしない
- `work/x_fetch/` は追跡しない。アプリの HTML と db の保存先もここに置く
- 要判定が多すぎる（100件超）ときは、まずクエリを疑う。
  2026-09-15 に愛称クエリの部分一致で要判定の7割が埋まっていたことがある（`x-egosearch/SKILL.md`）
