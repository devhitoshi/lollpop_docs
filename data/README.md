# data/ — 機械が読み書きする成果物の置き場

`work/` と違い、**ここは追跡する**。他人の投稿の原文は置かない（それは `work/x_fetch/` と非公開の `lollpop_data` リポジトリ）。

| パス | 内容 | 作るもの |
| --- | --- | --- |
| `x/egosearch_decisions_<since>_<until>.txt` | エゴサーチ候補の判定（投稿ID と採用/除外）。生データを取り直しても再判定しなくて済む | `.claude/skills/x-egosearch` |
| `x/egosearch_<since>_<until>_reactions.md` | 判定済みの反応の要約（要旨・短い引用・URL）。記事と定点観測が読む | 同上（Claude が書く） |
| `x/egosearch_triage_<since>_<until>_summary.txt` | 採用・除外の件数、日別件数 | 同上（triage が書く） |

生データ（`work/x_fetch/*.jsonl`）の退避と復元は `.claude/skills/x-data-sync`。
