# work/ — 生成物・作業中ファイルの置き場

このディレクトリは、note記事などの**下書き・生成物・作業ファイル**を置く場所です。
正式版のドキュメントはリポジトリのルート（`starter_pack.md`、`rules.md`、`link.md` など）や `articles/` にあり、
内容が食い違う場合は**ルート側・各シリーズREADME側が最新**です。

## ディレクトリ

| パス | 内容 |
|---|---|
| `note_週刊まとめ/` | 週刊まとめ記事シリーズ（現状の正は同ディレクトリのREADME） |
| `note_月刊まとめ/` | 月刊まとめ記事シリーズ（同上） |
| `note_歌詞考察/` | 歌詞考察記事シリーズ（同上） |
| `setlist_hakusho/` | セトリ白書のnote・X入稿セット（グラフ画像付き） |
| `setlist_hakusho_zenryoku/` | セトリ白書 全力疾走編の入稿セット |

## 単発ファイル

| ファイル | 内容 | 対応する正式版 |
|---|---|---|
| `note_starter_pack.md` | note公開用スターターパック記事のドラフト | [starter_pack.md](../starter_pack.md) |
| `ろりぽっぷスターターパック.md` | スターターパックの旧ドラフト | [starter_pack.md](../starter_pack.md) |
| `ろりぽっぷリンク集.md` | リンク集の旧ドラフト | [link.md](../link.md) |
| `ろりぽっぷルール.md` | ルールまとめの旧ドラフト | [rules.md](../rules.md) |
| `monthly_setlist_ranking.csv` | 月間セトリランキング（集計スクリプトの出力先） | [monthly_setlist_ranking.csv](../monthly_setlist_ranking.csv) |

## monthly_setlist_ranking.csv について

`.claude/skills/setlist-analysis` の集計スクリプトは `data_event.csv` を集計し、
`work/monthly_setlist_ranking.csv` と ルートの `monthly_setlist_ranking.csv` の**両方に同じ内容を出力**します。
手動でどちらか一方だけを編集しないでください（再集計で上書きされます）。
