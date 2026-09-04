# CLAUDE.md

このリポジトリで Claude Code が作業するときの前提とルール。セッションをまたいだ引き継ぎ用。
詳細は各ファイルを参照し、この文書は入口として短く保つ。

## リポジトリの概要

アイドルグループ「ろりぽっぷ!!!!!!!」のファンドキュメント集。全体構成は [`README.md`](./README.md) を参照。

## 作業の基本ルール

- **表記**: 曲名・イベント名は資料の表記をそのまま使う（「!」の数、「☆」「★」を正規化しない）。グループ名は「ろりぽっぷ!!!!!!!」（!が7個）。
- **文体**: note 用記事は [`prompts/write/style_ai_poppar.md`](./prompts/write/style_ai_poppar.md)（AIぽっぱー）に従う。note は表組み不可・見出しは2階層まで。
- **メンバー情報**: 基本情報の正は [`members/members.md`](./members/members.md)。人物像は [`members/`](./members/) のデータに根拠がある範囲だけ書く。卒業メンバーの卒業後の活動・私生活には踏み込まない。運営の意図・体調・人間関係の推測は書かない。
- **定型作業**: 歌詞ドキュメント作成は `.claude/skills/lyrics-management`、セトリ集計・公演データの整合性チェック・セトリ白書の図表は `.claude/skills/setlist-analysis`、曲調解析は `.claude/skills/music-analysis`、公式・メンバーのX投稿取得は `.claude/skills/x-account-fetch`、周囲の反応（エゴサーチ）は `.claude/skills/x-egosearch`、週刊・月刊の下書きは `.claude/skills/weekly-monthly-draft`、メンバーの人物像の更新は `.claude/skills/member-profile-refresh` の手順に従う。
- **調査・分析**: 戦略の定点観測（フォロワー数・UGC・公式の発信量）は `.claude/skills/strategy-metrics`、Web 調査（市場・競合・業界）は `.claude/skills/web-research`。出典と確認日を付け、評価語を書かない。
- **記事の公開前レビュー**: note 記事を書き終えたら、PR を作る前に `.claude/skills/article-review`（機械チェック＋読み取り専用エージェント `article-review`）を通す。手戻りの多い「公演の抜け」「公演数の誤り」「表記ゆれ」「文体の崩れ」を資料と突き合わせて拾う。
- **セッションの終わり**: `.claude/skills/session-handoff` の手順で、各シリーズ README の「未解決」と CLAUDE.md の進行中セクションを更新してからコミット・push する。
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
| 機械が作る成果物（エゴサの判定・件数・要約） | `data/x/`（追跡する。他人の投稿の原文は置かない）。**収集→保管の流れは [`data/README.md`](./data/README.md)** |
| X の取得データ（他人の投稿の原文） | `work/x_fetch/`（追跡しない）。セッションの終わりに `.claude/skills/x-data-sync` で非公開リポジトリ `lollpop_data` へ退避し、始めに復元する |
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
- **X収集は API に一本化した（2026-09-02〜）。** 公式・メンバーの投稿は `.claude/skills/x-account-fetch`、周囲の反応（エゴサーチ）は `.claude/skills/x-egosearch`（全件取得→機械仕分け→Claude が判定）。Grok 版の `prompts/collect/x_collect.md` は API が使えない環境の予備。8月分は両方とも完了し、週刊8/25-8/31号と月刊8月号に反映済み。取得データは `work/x_fetch/`（コミットしない）にあり、コンテナが変わると消える。**消える前に `.claude/skills/x-data-sync` で非公開リポジトリ `lollpop_data` へ退避し、次のセッションの始めに復元する**（起動時 hook が自動で試みる。リモート環境ではセッションの範囲に lollpop_data が要る）。判定ファイルは `data/x/` にコミット済みなので、再取得しても再判定は要らない。
- **執筆の入口は `.claude/skills/weekly-monthly-draft`**（2026-09-02〜）。取得済み投稿と `events/data_event.csv` から素材ファイル（`work/x_fetch/draft_material_*.md`、コミットしない）を組み立て、`prompts/write/` の文体・構成で書き、`article-review` でレビューしてから README を更新する。

## 縦型動画の素材（進行中・2026-09-02〜）

- 目的: 告知・周知を縦型動画（TikTok・Reels・Shorts）ベースにする。そのための素材集め。
- 手順は `.claude/skills/x-media-collect`、データの流れは [`data/README.md`](./data/README.md)。
- 済: 8月分の索引（`data/x/media_index_2026-08-01_2026-08-31.csv`・882件）。許諾の記録（`data/x/media_permissions.md`）。
  許諾済みは公式・メンバー5人・ファン5アカウントで **456件がダウンロード可能**。
- 制約: **他人の素材は `data/x/media_permissions.md` に「OK」がある分だけ。** 記録に無いものは落とせない作りにしてある。
  @Bf1pR（しゃけさん）は都度依頼。ファン素材は上位10人で58%・上位20人で73%なので、増やすならそこから。
- 容量: 許諾済み456件を全部落とすと約12.5GB（動画12.2GB・写真175MB。4Kが31本）。`--dry-run` で概算を見てから落とす。
- 素材の偏り: 縦型の動画は6件しかない。**横動画は上下にテロップを入れて 9:16 に載せる**方針。
  自分で縦持ちで撮るのがいちばん強く、主催・単独は動画全編可・掲載可（`guide/rules.md`）。
- 組み立ても同じスキル（`scripts/make_vertical.py`）。構成を JSON で渡すと 1080x1920 の mp4 を書き出す。
  横の映像は切り取らず中央に置き、背景は同じ映像のぼかし、上下に半透明の帯とテロップ。
  試作1本（8/26単独＋8/30カモガワ＋8/31の縦写真、24秒）を作って構成は確認済み。**書き出しは `work/` に置きコミットしない。**
- **クレジットは必ず入れる**（オーナー方針・2026-09-02）。`make_vertical.py` が `manifest.csv` の出典から
  文面を作って全区間に焼き込む。外す引数は無く、出典が引けない素材は spec に `"credit"` を書かないと止まる。
- 待ち: 楽曲は TikTok のライブラリにあると確認済み。**書き出しは無音にして、アプリ内で公式音源を選ぶ。**
  運営・メンバーの許諾の範囲（改変・クレジット・期限）は未確認。次に作るなら 9/20 単独ライブ Vol.19 の告知。
- 未解決: クレジットの文面は本来「許諾の属性」。いまは `media_permissions.md` が可否（OK／都度）しか持たず、
  文面を `make_vertical.py` 側で決め打ちしている。運営・メンバーに改変とクレジットの条件を確認したら、
  その回答を permissions.md の列にして、動画側は読むだけにする（個別条件を記憶でなく記録で扱うため）。

## 実行環境の注意（Claude Code リモート環境）

- **twitterapi.io は環境によって到達可否が変わる。** 信頼モードでは403、フルアクセス環境では到達可能（2026-09-01確認）。APIキーは環境変数 `TWITTERAPI_IO_KEY` かルートの `.env`（`.gitignore` 済み）から読む。**キーをチャットに貼らせない。** 取得した投稿データ（`work/x_fetch/`）は他人の著作物なのでコミットしない（`.gitignore` 済み）。
- **linkco.re（TuneCore配信ページ）はネットワークポリシーで到達不可。** 歌詞はユーザーにスクリーンショットかテキストで貼ってもらい、転記する。原文の表記揺れは正規化せず、歌詞ファイル末尾のHTMLコメント（転記メモ）に記録して、ユーザーにレビューを依頼する。
- **公開用の画像を撮る前に、必ず `bash resources/install_capture_font.sh` を実行する。入れずに撮ると漢字が中国語フォントの字形になる**（2026-09-04に実際にやらかした）。コンテナのヘッドレスChromiumは `fonts.googleapis.com` に到達できず（curl は proxy 経由で通るのにブラウザは `ERR_CONNECTION_RESET`）、コンテナの日本語フォントは IPAGothic と WenQuanYi しか無い。そのまま撮ると **WenQuanYi Zen Hei（中国語フォント）で漢字が描画される**。コンテナは使い捨てなので、セッションが変わるたびに入れ直す。
  **CSSの指定と実際に描画されたフォントは別物。** 画像にする前に CDP の `CSS.getPlatformFontsForNode` で実物を確認する（`resources/capture_call_sheet.py` は Noto Sans JP でなければ中断する。他のページを撮るときも同じ確認を入れる）。ページ側のフォント指定は design.md が正で、この件で変えない。
- **Playwright はコンテナに未インストール。`pip install playwright` で入れる。** ブラウザは `/opt/pw-browsers` にあり、`playwright install` は不要（禁止）。pip版とバンドル版でビルド番号がずれて起動に失敗するので、`executable_path="/opt/pw-browsers/chromium-1194/chrome-linux/chrome"`（実際のディレクトリ名を確認する）と `args=["--no-sandbox"]` を渡す。
- **記事系のPRは、作成後そのままマージしてよい**（オーナー方針・2026年9月確認）。マージ後は作業ブランチを origin/main に揃え直す。
- **hooks（`.claude/settings.json`、2026-09-02〜）が3つ動く。** 起動時に現状サマリ（ブランチ・不足月・APIキーの有無・取得済み投稿）を出す `session_start.sh`、`git add -f` と `.env`／`work/x_fetch/`／音源を含むコミットを止める `guard_git.py`、`events/data_event.csv` を編集したら集計と整合性チェックを自動で回す `after_event_csv.py`。止められたときは理由が表示されるので、無理に回避せずユーザーに確認する。
