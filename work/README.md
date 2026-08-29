# work/ — 作業用ドラフト置き場

このディレクトリは、note記事などの**下書き・作業ファイル**を置く場所です。
正式版のドキュメントはリポジトリのルート（`starter_pack.md`、`rules.md`、`link.md` など）にあり、
内容が食い違う場合は**ルート側が最新**です。

## ファイル一覧

| ファイル | 内容 | 対応する正式版 |
|---|---|---|
| `note_starter_pack.md` | note公開用スターターパック記事のドラフト | [starter_pack.md](../starter_pack.md) |
| `ろりぽっぷスターターパック.md` | スターターパックの旧ドラフト | [starter_pack.md](../starter_pack.md) |
| `ろりぽっぷリンク集.md` | リンク集の旧ドラフト | [link.md](../link.md) |
| `ろりぽっぷルール.md` | ルールまとめの旧ドラフト | [rules.md](../rules.md) |
| `monthly_setlist_ranking.csv` | 月間セトリランキング（集計スクリプトの出力先） | [monthly_setlist_ranking.csv](../monthly_setlist_ranking.csv) |

## monthly_setlist_ranking.csv について

`.agent/scripts/analyze_monthly_setlist.py` は `data_event.csv` を集計し、
`work/monthly_setlist_ranking.csv` と ルートの `monthly_setlist_ranking.csv` の**両方に同じ内容を出力**します。
手動でどちらか一方だけを編集しないでください（再集計で上書きされます）。
