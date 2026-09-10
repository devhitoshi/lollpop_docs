# CLAUDE.md

このリポジトリで Claude Code が作業するときの前提とルール。セッションをまたいだ引き継ぎ用。
詳細は各ファイルを参照し、この文書は入口として短く保つ（進捗の詳細は各 README の「未解決」節に書き、ここには 3 行以内の要約とリンクだけ置く）。

## リポジトリの概要

アイドルグループ「ろりぽっぷ!!!!!!!」のファンドキュメント集。全体構成は [`README.md`](./README.md) を参照。
**ローカル（Windows）とクラウドの Claude Code を並行して使う。** 決定・手順・進捗はメモリではなくこのリポジトリに書く（メモリはクラウドと同期されない）。

## 作業の基本ルール

- **表記**: 曲名・イベント名は資料の表記をそのまま使う（「!」の数、「☆」「★」を正規化しない）。グループ名は「ろりぽっぷ!!!!!!!」（!が7個）。
- **文体と表現規約**: note 用記事は [`prompts/write/style_ai_poppar.md`](./prompts/write/style_ai_poppar.md)（AIぽっぱー）に従う。note は表組み不可・見出しは2階層まで。
  同ファイル末尾の「使わない言葉・使い方」（**「地下アイドル」と言わない／「レア曲」と書かない／メンバー写真を直貼りしない／おすすめ曲は通算と直近を併記**）は記事・動画・字幕・キャプション・ハッシュタグすべてに適用する。
- **メンバー情報**: 基本情報の正は [`members/members.md`](./members/members.md)。人物像は [`members/`](./members/) のデータに根拠がある範囲だけ書く。卒業メンバーの卒業後の活動・私生活には踏み込まない。運営の意図・体調・人間関係の推測は書かない。
- **定型作業**: 歌詞ドキュメント作成は `.claude/skills/lyrics-management`、セトリ集計・公演データの整合性チェック・セトリ白書の図表は `.claude/skills/setlist-analysis`、曲調解析は `.claude/skills/music-analysis`、公式・メンバーのX投稿取得は `.claude/skills/x-account-fetch`、周囲の反応（エゴサーチ）は `.claude/skills/x-egosearch`、週刊・月刊の下書きは `.claude/skills/weekly-monthly-draft`（**収集〜仕上げを一本で回すなら `.claude/skills/weekly-pipeline`**。前回実行の翌日から今日までを既定期間にするので、毎週同じ曜日でなくてよい）、メンバーの人物像の更新は `.claude/skills/member-profile-refresh` の手順に従う（**節の定義と禁止事項の正は [`members/README.md`](./members/README.md)。書く前に読む**）。コール表のSNS画像はスキルにしていないので、[`resources/call_sheet_requirements.md`](./resources/call_sheet_requirements.md) を読んでから作る。
- **調査・分析**: 戦略の定点観測（フォロワー数・UGC・公式の発信量）は `.claude/skills/strategy-metrics`、Web 調査（市場・競合・業界）は `.claude/skills/web-research`。出典と確認日を付け、評価語を書かない。調査メモは `strategy/research_YYYY-MM-DD_<題名>.md`。
- **記事の公開前レビュー**: note 記事を書き終えたら、PR を作る前に `.claude/skills/article-review`（機械チェック＋読み取り専用エージェント `article-review`）を通す。手戻りの多い「公演の抜け」「公演数の誤り」「表記ゆれ」「文体の崩れ」を資料と突き合わせて拾う。
- **公開済み note の更新**: `.claude/skills/article-refresh`（差分検知→改稿→レビュー→貼り替え手順書。公開 URL と最終同期日は `articles/公開一覧.md`）。
- **セッションの終わり**: `.claude/skills/session-handoff` の手順で、各シリーズ README の「未解決」と CLAUDE.md の進行中セクションを更新してからコミット・push する。
- **デザイン**: `resources/` のHTMLを触るときは [`design.md`](./design.md)（色・タイポ・バンド構成の正）に従う。実装は `resources/css/style.css`。単一ファイル完結のHTML（セトリ白書・成長戦略）には同じトークン値が転記されている。
- **手動修正中のファイル**: オーナーが「いま手で直している」と言ったファイル（例: `songs/call_list.md`）は、確定の連絡まで編集も依存もしない。着手前に `git status` で他セッションの未コミット変更を見る。

## 資源配置ルール（何をどこに置くか）

ディレクトリはドメイン別。**新しく作るものは以下の表に従って置く**（迷ったらこの表が正）。

| 作るもの | 置き場 |
| --- | --- |
| 新しい歌詞 | `songs/lyrics/[曲名].md`（公式表記のまま） |
| 曲調データ | `songs/analysis/[曲名].md`＋全曲比較 `songs/analysis/song_features.csv`（スキルが自動生成） |
| note記事（シリーズ・単発とも） | `articles/`（シリーズは専用ディレクトリ、単発は `articles/単発/`。詳細は `articles/README.md`） |
| 公演・セトリのデータ | `events/data_event.csv`（一次データ）。集計は `events/monthly_setlist_ranking.csv`。入れ方と TimeTree の使い方は [`events/README.md`](./events/README.md) |
| 戦略・定点観測 | `strategy/`（観測結果は `strategy/metrics_YYYY-MM-DD.md`、調査メモは `strategy/research_*.md`） |
| 縦動画の運用設計・型定義・量産フロー | `strategy/short_video_playbook.md`（運用の正）と [`strategy/video/`](./strategy/video/)（型定義 A〜G、量産フロー、台本の部品、流行調査）。制作ツールは別リポジトリ `lollpop_video`（F・G）とこのリポジトリの `x-media-collect/scripts/make_vertical.py`（A〜E） |
| ファン向け入口文書 | `guide/`。メンバー情報は `members/` |
| デザイン定義の変更 | `design.md` を先に直し、`resources/css/style.css` に反映 |
| 公開HTML | `resources/`（design.md のバンド原則に従う） |
| 機械が作る成果物（エゴサの判定・件数・要約） | `data/x/`（追跡する。他人の投稿の原文は置かない）。**収集→保管の流れは [`data/README.md`](./data/README.md)** |
| X の取得データ（他人の投稿の原文） | `work/x_fetch/`（追跡しない）。セッションの終わりに `.claude/skills/x-data-sync` で非公開リポジトリ `lollpop_data` へ退避し、始めに復元する |
| 一時的な作業ファイル | `work/`（恒久化が決まったらドメインへ運び出す。**基本は空**） |
| 旧版・役目を終えたもの | `archive/` |

命名規則（既存の混在は歴史として維持し、**改名はしない**。新規分のみ適用）:
- 機械が読み書きするもの（`events/` のCSV、スクリプト、スキル）: 英小文字スネークケース
- 人が読む日本語ドキュメント（歌詞・note原稿・記事シリーズのディレクトリ）: 公式表記の日本語名
- 日付は `YYYY-MM-DD`（週刊は `YYYY-MM-DD_YYYY-MM-DD`、月刊は `YYYY-MM`）
- リポジトリ名 `lollpop` の綴りは意図的（README「リポジトリ名の綴りについて」）。直さない

## 進行中（要約のみ。詳細は各 README）

- **歌詞考察**: 正は [`articles/歌詞考察/README.md`](./articles/歌詞考察/README.md)。1曲1記事＋横断考察。オリジナル9曲・ルーツ曲1・横断01 まで済。待ち: 「未完成ヒロイン」「夏色ラムネ」の歌詞資料。
  **曲調に触れてよいのは `songs/analysis/[曲名].md` がある曲だけ**（BPM・キーは推定値。断定しない）。
- **週刊・月刊まとめ**: 正は [`articles/週刊まとめ/README.md`](./articles/週刊まとめ/README.md)・[`articles/月刊まとめ/README.md`](./articles/月刊まとめ/README.md)。8月分まで公開済み。**週刊 9/1〜9/7 号は 2026-09-07 作成・未コミット（オーナー確認待ち）**。
  X 収集は API 一本化済み（2026-09-02〜。Grok 版 `prompts/collect/x_collect.md` は予備）。取得データは `work/x_fetch/`、退避は `x-data-sync`。
- **スターターパック・全楽曲解説（公開済み note の保守）**: 正は [`articles/スターターパック/README.md`](./articles/スターターパック/README.md)（公開 URL の表あり）。2026-09-02〜04 に 3 本立て化と全楽曲解説の最新化を実施。
  `guide/starter_pack.md` より `articles/スターターパック/` が正（2026-09-03 に反転）。次に陳腐化したら「差分検知→改稿→article-review→貼り替え手順書」の型で更新する（スキル `article-refresh` を作る予定）。
- **メンバーのパーソナリティ**: 正は [`members/README.md`](./members/README.md)。2026-09-09〜10 に、なりきりプロンプト由来の記述から
  **人格心理学の3層（傾向／動機・価値観／自己物語）＋アイドル固有の2層（特典会用の話題の在庫／舞台での見え方）の6節構成**へ全面改稿。
  現メンバー5人は完了（デビュー 2024-11-16 以降・約11,900件が根拠。手順は `.claude/skills/member-profile-refresh`）。
  **元メンバー2人は旧構成のまま凍結する**（オーナー判断・2026-09-10。取得もしない）。
  「やぎくるみ＝リーダー」表記は削除済み（ストクレ時代の経験。現グループに役職は無い。claude-work #17）。
- **縦動画**: 運用の正は [`strategy/short_video_playbook.md`](./strategy/short_video_playbook.md)、型定義と量産フローは [`strategy/video/`](./strategy/video/README.md)。
  2026-09-07 に型体系を A〜E＋F・G に一本化（主力は A 反応集と F/G メンバーエピソードの両輪、月 10〜12 本。ファン投稿の引用は 7.3 の作法で可。コール講座は不採用→入門コンテンツをバックログ）。
  素材の索引・許諾・組み立ては `.claude/skills/x-media-collect` と [`data/README.md`](./data/README.md)。**他人の素材は `data/x/media_permissions.md` に「OK」がある分だけ。クレジットは必ず入れる。**
  未解決: 運営・メンバーの許諾条件（改変・クレジット・期限。playbook 11章）が未確認で、クレジット文面を `make_vertical.py` が決め打ちしている。F 用の VOICEVOX 話者 1 名が未決定。

## 実行環境の注意

- **ローカル（Windows）**: このリポジトリで起動する（`work/` から起動すると hooks・スキル・専用メモリが効かない。PowerShell の `cl` で起動できる）。`python3` はシムで `python` 3.10 に解決する（2026-09-07〜）。
- **クラウド（リモート環境）**:
  - **twitterapi.io は環境によって到達可否が変わる。** 信頼モードでは403、フルアクセス環境では到達可能（2026-09-01確認）。APIキーは環境変数 `TWITTERAPI_IO_KEY` かルートの `.env`（`.gitignore` 済み）から読む。**キーをチャットに貼らせない。** 取得した投稿データ（`work/x_fetch/`）は他人の著作物なのでコミットしない（`.gitignore` 済み）。
  - **linkco.re（TuneCore配信ページ）はネットワークポリシーで到達不可。** 歌詞はユーザーにスクリーンショットかテキストで貼ってもらい、転記する。原文の表記揺れは正規化せず、歌詞ファイル末尾のHTMLコメント（転記メモ）に記録して、ユーザーにレビューを依頼する。
  - **公開用の画像を撮る前に、必ず `bash resources/install_capture_font.sh` を実行する。入れずに撮ると漢字が中国語フォントの字形になる**（2026-09-04に実際にやらかした）。コンテナのヘッドレスChromiumは `fonts.googleapis.com` に到達できず、日本語フォントは IPAGothic と WenQuanYi しか無い。**CSSの指定と実際に描画されたフォントは別物。** 画像にする前に CDP の `CSS.getPlatformFontsForNode` で実物を確認する（`resources/capture_call_sheet.py` は Noto Sans JP でなければ中断する）。コンテナは使い捨てなので、セッションが変わるたびに入れ直す。
  - **Playwright はコンテナに未インストール。`pip install playwright` で入れる。** ブラウザは `/opt/pw-browsers` にあり、`playwright install` は不要（禁止）。`executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"`（実際のディレクトリ名を確認する）と `args=["--no-sandbox"]` を渡す。
  - `lollpop_video` は GitHub に無い（ローカルのみ）。動画のレンダリングや Remotion の実装はクラウドに投げても進まない。
- **共通**:
  - **記事系のPRは、作成後そのままマージしてよい**（オーナー方針・2026年9月確認）。それ以外の PR は本文を提示して承認を得る。マージ後は作業ブランチを origin/main に揃え直す。
  - **PR 本文の末尾に `## 判断待ち` 節を必ず書く。**オーナーが決めないと進まないことを箇条書きにする。**無ければ「なし」と明記する**（書き忘れと区別するため）。
    残タスクは `devhitoshi/claude-work`（private）の Issues に集約していて、**この節が唯一の回収口**。クラウドセッションは会話ログが残らず、PR 本文とコミットだけが引き継ぎ面になる。
    過去に #18（許諾の範囲）・#20（未push コミットの扱い）・#21（コール表未整備・`x_cache/`）が PR 本文に書かれたまま誰にも拾われず、いまも未対応で残っている。
    `claude-work` に直接書き込める環境なら `gh issue create -R devhitoshi/claude-work` でもよい（権限が無ければ PR 本文だけでよい。ローカルの週次走査が拾う）。
  - **hooks（`.claude/settings.json`、2026-09-02〜）が3つ動く。** 起動時に現状サマリを出す `session_start.sh`、`git add -f` と `.env`／`work/x_fetch/`／音源を含むコミットを止める `guard_git.py`、`events/data_event.csv` を編集したら集計と整合性チェックを自動で回す `after_event_csv.py`。止められたときは理由が表示されるので、無理に回避せずユーザーに確認する。
