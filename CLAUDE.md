# CLAUDE.md

このリポジトリで Claude Code が作業するときの前提とルール。セッションをまたいだ引き継ぎ用。
詳細は各ファイルを参照し、この文書は入口として短く保つ。

## リポジトリの概要

アイドルグループ「ろりぽっぷ!!!!!!!」のファンドキュメント集。全体構成は [`README.md`](./README.md) を参照。

## 作業の基本ルール

- **表記**: 曲名・イベント名は資料の表記をそのまま使う（「!」の数、「☆」「★」を正規化しない）。グループ名は「ろりぽっぷ!!!!!!!」（!が7個）。
- **文体**: note 用記事は [`prompts/write/style_ai_poppar.md`](./prompts/write/style_ai_poppar.md)（AIぽっぱー）に従う。note は表組み不可・見出しは2階層まで。
- **メンバー情報**: 基本情報の正は [`members/members.md`](./members/members.md)。人物像は [`members/`](./members/) のデータに根拠がある範囲だけ書く。卒業メンバーの卒業後の活動・私生活には踏み込まない。運営の意図・体調・人間関係の推測は書かない。
- **定型作業**: 歌詞ドキュメント作成は `.claude/skills/lyrics-management`、セトリ集計は `.claude/skills/setlist-analysis`、曲調解析は `.claude/skills/music-analysis`、公式・メンバーのX投稿取得は `.claude/skills/x-account-fetch` の手順に従う。
- **デザイン**: `resources/` のHTMLを触るときは [`design.md`](./design.md)（色・タイポ・バンド構成の正）に従う。実装は `resources/css/style.css`。単一ファイル完結のHTML（セトリ白書・成長戦略）には同じトークン値が転記されている。

## 資源配置ルール（何をどこに置くか）

ディレクトリはドメイン別。**新しく作るものは以下の表に従って置く**（迷ったらこの表が正）。

| 作るもの | 置き場 |
| --- | --- |
| 新しい歌詞 | `songs/lyrics/[曲名].md`（公式表記のまま） |
| 曲調データ | `songs/analysis/[曲名].md`＋全曲比較 `songs/analysis/song_features.csv`（スキルが自動生成） |
| note記事（シリーズ・単発とも） | `articles/`（シリーズは専用ディレクトリ、単発は `articles/単発/`。詳細は `articles/README.md`） |
| 公演・セトリのデータ | `events/data_event.csv`（一次データ）。集計は `events/monthly_setlist_ranking.csv` |
| 戦略・定点観測 | `strategy/`（観測結果は `strategy/metrics_YYYY-MM-DD.md`） |
| ファン向け入口文書 | `guide/`。メンバー情報は `members/` |
| デザイン定義の変更 | `design.md` を先に直し、`resources/css/style.css` に反映 |
| 公開HTML | `resources/`（design.md のバンド原則に従う） |
| 一時的な作業ファイル | `work/`（恒久化が決まったらドメインへ運び出す。**基本は空**） |
| 旧版・役目を終えたもの | `archive/` |

命名規則（既存の混在は歴史として維持し、**改名はしない**。新規分のみ適用）:
- 機械が読み書きするもの（`events/` のCSV、スクリプト、スキル）: 英小文字スネークケース
- 人が読む日本語ドキュメント（歌詞・note原稿・記事シリーズのディレクトリ）: 公式表記の日本語名
- 日付は `YYYY-MM-DD`（週刊は `YYYY-MM-DD_YYYY-MM-DD`、月刊は `YYYY-MM`）

## 歌詞考察シリーズ（進行中）

- 置き場と現状の正: [`articles/歌詞考察/README.md`](./articles/歌詞考察/README.md)。
- 方針: **1曲1記事**（ルーツ曲も歌詞資料が揃ったものから対象）＋数曲ごとに**横断考察記事**。
- 済（2026年9月時点）: オリジナル曲9曲の単独記事、ルーツ曲編第1回「♀︎正解の方程式♂︎」、「横断考察01_主人公の系譜」。
- 待ち: 「未完成ヒロイン」「夏色ラムネ」の歌詞資料。揃ったら単独記事を追加し、横断考察02（候補はシリーズREADME参照）を検討する。
- 制約: **曲調に触れてよいのは `songs/analysis/[曲名].md` がある曲だけ。** 無い曲は音源を聴いていないので、歌詞・構成・コール表・披露記録から読めることだけを書く。
- 曲調データの作り方は `.claude/skills/music-analysis`。購入した音源を `audio/` に置いて解析する。**音源ファイルはリポジトリに入れない**（`.gitignore` で除外済み）。BPM・キーは推定値なので記事では断定しない（キーは平行調と入れ替わることがある）。

## 週刊・月刊まとめ記事（進行中）

- 置き場と現状の正: [`articles/週刊まとめ/README.md`](./articles/週刊まとめ/README.md)、[`articles/月刊まとめ/README.md`](./articles/月刊まとめ/README.md)。
- 2026年8月分まで作成済み。8月の全17公演は `events/data_event.csv` 追記済み・集計反映済み。
- **X収集は2ルートに分かれた（2026-09-01〜）。** 公式・メンバーの投稿は `.claude/skills/x-account-fetch`（twitterapi.io・全件取得）、エゴサーチ（周囲の反応）は従来どおり `prompts/collect/x_collect.md` の手順2をGrokで実行する。前者は完了済み、**後者が未実施**（詳細は各READMEの「未解決」参照）。

## 実行環境の注意（Claude Code リモート環境）

- **twitterapi.io は環境によって到達可否が変わる。** 信頼モードでは403、フルアクセス環境では到達可能（2026-09-01確認）。APIキーは環境変数 `TWITTERAPI_IO_KEY` かルートの `.env`（`.gitignore` 済み）から読む。**キーをチャットに貼らせない。** 取得した投稿データ（`work/x_fetch/`）は他人の著作物なのでコミットしない（`.gitignore` 済み）。
- **linkco.re（TuneCore配信ページ）はネットワークポリシーで到達不可。** 歌詞はユーザーにスクリーンショットかテキストで貼ってもらい、転記する。原文の表記揺れは正規化せず、歌詞ファイル末尾のHTMLコメント（転記メモ）に記録して、ユーザーにレビューを依頼する。
- **記事系のPRは、作成後そのままマージしてよい**（オーナー方針・2026年9月確認）。マージ後は作業ブランチを origin/main に揃え直す。
