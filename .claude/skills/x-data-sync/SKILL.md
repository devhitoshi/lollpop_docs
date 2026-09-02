---
name: x-data-sync
description: X の取得データ（work/x_fetch/*.jsonl。公式・メンバーの投稿とエゴサーチの生データ）を、非公開リポジトリ lollpop_data に退避・復元する。リモートの Claude Code はコンテナが使い捨てで work/ が消えるため、セッションの始め（復元）と終わり（退避）に使う。「データが消えた」「前回の取得データを戻して」「退避して」「x_fetch が空」と言われたとき、x-account-fetch / x-egosearch を使う前に work/x_fetch が空のときに使う。
---

# X 取得データの退避と復元

## なぜ要るか

- 他人の投稿の原文は公開リポジトリ（lollpop_docs）に入れない。だから `work/x_fetch/` は `.gitignore` 対象
- リモートの Claude Code はセッションごとにコンテナが変わり、`.gitignore` 対象のファイルは消える
- 取得には API 費用（8月分で約 $0.5）と時間（20〜30分）がかかり、エゴサーチの判定はさらに手間がかかる

そこで、**生データは非公開リポジトリ `devhitoshi/lollpop_data` に項目を絞った圧縮版で置き、判定などの成果物は `data/x/`（lollpop_docs で追跡）に置く**。

| 何 | どこ | 追跡 |
| --- | --- | --- |
| 投稿の原文（全項目） | `work/x_fetch/*.jsonl` | しない（消えてよい） |
| 投稿の原文（必要項目・gzip） | `lollpop_data/x/*.jsonl.gz` | 非公開リポジトリ |
| 判定・件数・要約 | `data/x/` | lollpop_docs |

## 前提

- `lollpop_data` がリポジトリの隣（`../lollpop_data`）にあること。場所を変えるなら環境変数 `LOLLPOP_DATA_DIR`
- リモート環境では、セッションのリポジトリ範囲に `devhitoshi/lollpop_data` が無いと clone できない。
  `add_repo`（owner: devhitoshi, repo: lollpop_data, access: push）で取り込んでから `git clone` する。
  環境の設定でソースに lollpop_data を足しておくと、起動時 hook が自動で clone と復元を行う

## 手順

**セッションの始め（`work/x_fetch/` が空のとき）**

```bash
python3 .claude/skills/x-data-sync/scripts/sync_x_data.py status   # 両側にあるものを見る
python3 .claude/skills/x-data-sync/scripts/sync_x_data.py pull     # 無いものだけ復元
```

起動時 hook（`.claude/hooks/session_start.sh`）が `lollpop_data` を見つけたら同じことを自動で行う。
復元したデータは項目を絞った版（本文・日時・投稿者名・いいね等・メディアの有無）。既存のスクリプトはこれで動く。

**新しく取得・判定したあと（セッションの終わり）**

```bash
python3 .claude/skills/x-data-sync/scripts/sync_x_data.py push -m "8月分のエゴサーチと公式・メンバー投稿"
```

`work/x_fetch/*.jsonl` を圧縮版にして `lollpop_data/x/` へ書き、commit と push まで行う。
判定ファイル（`data/x/`）は lollpop_docs 側で普通に commit する。`session-handoff` の手順に含まれている。

## 注意

- 退避先は非公開でも、他人の投稿を GitHub に置くことに変わりはない。再配布・公開・学習利用はしない
- `lollpop_data` を公開に変えない。lollpop_docs の hook は `*.jsonl` のコミットを止めるが、lollpop_data 側には hook が無い
- 圧縮版には `author` の詳細（フォロワー数など）や画像 URL は入れていない。要るなら x-account-fetch で取り直す
