# ろりぽっぷ!!!!!!! Docs
「ろりぽっぷ!!!!!!!」のプロジェクト・ドキュメントです。各ファイルへのリンクや使い方をまとめています。

## 概要
"\\楽しさ無限大//ポップなお祭りへようこそ!!!!!!! 見て、聞いて、騒いで、"みんなと最高に楽しいライブ"をコンセプトとする、日本の5人組女性アイドルグループ。活動拠点は東京で、株式会社FLAP entertainmentの所属です。
J-POPアイドルジャンルを中心に、ライブを通じて観客と一緒に楽しい空間を創出することを重視しており、TikTok等を通じたファンへの発信や、海外でのイベント出演も精力的に行っています。

## 略歴
- **2024年10月26日**: 公式X（旧Twitter）にて結成、メンバー、ロゴを公開。
- **2024年11月16日**: サウンドノート秋葉原にてデビューライブを開催し活動開始。
- **2025年3月30日**: 代官山UNITにて初のワンマンライブ「始まりの宴!!!!!!」を開催し、新メンバー（松川 愛美）の加入を発表。
- **2025年5月4日**: 赤羽ReNY alphaにて「7人体制お披露目LIVE」を開催。
- **2025年8月**: シンガポールの「AFA Creators Super Fest Singapore 2025」に出演。
- **2025年11月24日**: 1st Anniversary LIVE / 2nd ワンマンライブ 「ろりぽの挑戦!!!!!!!」を赤羽ReNY alphaにて開催
- **2025年11月25日**: 1st EP「始まりの宴!!!!!!!」を配信開始。
- **2026年3月25日**: 中野坂上SUB TOKYOでの「単独ライブVol.13」にて新曲「未完成ヒロイン」を初披露。
- **2026年4月22日**: 姫杏 朝香が卒業（6人体制へ）
- **2026年6月6日**: 新宿ReNYにて3rd ワンマンライブ「全力疾走」を開催。新曲「シーソーゲーム」「メイク☆マイダンス」を初披露。
- **2026年6月25日**: EP「全力疾走」を配信開始。
- **2026年8月15日**: 苺花 なつみが卒業（5人体制へ）
- **2026年8月26日**: 中野坂上SUB TOKYOでの「単独ライブ Vol.18 夏曲お披露目公演」にて新曲「夏色ラムネ」を初披露。


  
## 目次
- [はじめての方へ / スターターパック (guide/starter_pack.md)](./guide/starter_pack.md)
- [楽曲一覧 (songs/楽曲一覧.md)](./songs/楽曲一覧.md)
- [市場・競合分析と成長戦略 (strategy/growth_strategy.md)](./strategy/growth_strategy.md) ／ [解説HTML版 (resources/growth_strategy.html)](./resources/growth_strategy.html)
- [全曲コール表 (songs/call_list.md)](./songs/call_list.md)
- [公式ルール・現場のマナー (guide/rules.md)](./guide/rules.md)
- [メンバープロフィール (members/members.md)](./members/members.md)
- [リンク集 (guide/link.md)](./guide/link.md)
- [アー写履歴 (members/artist_photos.md)](./members/artist_photos.md)
- [note記事のホーム (articles/)](./articles/README.md)
- [セトリ白書 — セットリスト分析記事 (resources/setlist_analysis.html)](./resources/setlist_analysis.html)
- [デザインシステム定義 (design.md)](./design.md)
- [公開用メインページ (resources/index.html)](./resources/index.html)

## リポジトリ構成

**ドメイン（何についての資料か）でディレクトリを分けています。**
迷ったら「公演→`events/`、曲→`songs/`、人→`members/`、入口→`guide/`、戦略→`strategy/`、
記事→`articles/`、一時作業→`work/`、旧版→`archive/`」。

### ドメイン別ディレクトリ

| パス | 内容 |
| --- | --- |
| `guide/` | ファン向けの入口ドキュメント（スターターパック・ルール・リンク集） |
| `members/` | メンバードメイン。基本情報の正 `members.md`、アー写履歴、パーソナリティデータ（人物像・口調・SNS傾向） |
| `songs/` | 曲ドメイン。楽曲一覧・コール表・歌詞（`lyrics/`）・曲調データ（`analysis/`、全曲比較は `analysis/song_features.csv`＝未生成） |
| `events/` | 公演ドメイン。一次データ `data_event.csv`（日付・会場・セトリ）と集計 `monthly_setlist_ranking.csv` |
| `strategy/` | 運用戦略。`growth_strategy.md` と四半期の定点観測 `metrics_YYYY-MM-DD.md` |
| `articles/` | **note記事のホーム**（全シリーズ＋単発。索引と置き方は `articles/README.md`） |
| `audio/` | 曲調解析に使う音源の置き場（音源自体はリポジトリに入りません） |
| `work/` | 汎用の一時作業場。**中身は空が正常**（案内は `work/README.md`） |
| `archive/` | 役目を終えた旧版ドラフト |

### 公開面と標準文書

| パス | 内容 |
| --- | --- |
| `resources/` | GitHub Pages で公開しているサイト一式（ポータル・ビューア・セトリ白書・成長戦略ノート・CSS） |
| `design.md` | デザインシステム定義（色・タイポ・バンド構成の正。`resources/css/style.css` が実装） |
| `README.md` | この文書。リポジトリの地図 |
| `CLAUDE.md` | Claude Code 用の作業ルールと資源配置ルール |

### 道具

| パス | 内容 |
| --- | --- |
| `prompts/` | note 記事を作るためのLLM用プロンプト（`collect/` = Grok・Gemini、`write/` = Claude） |
| `.claude/skills/` | 繰り返す作業の手順書（歌詞ドキュメント作成、月次セトリ集計と整合性チェック、曲調解析、X投稿の取得、週刊・月刊の下書き、記事の公開前レビュー、セッション引き継ぎ） |
| `.claude/agents/` | Claude Code のサブエージェント。`article-review` は記事を直さず校閲レポートだけを返す読み取り専用の校閲係 |
| `.claude/hooks/` + `.claude/settings.json` | Claude Code の自動処理。起動時サマリ、秘密情報・取得データのコミット防止、公演CSV編集後の自動集計 |

## 公式サイト
https://flapinc.jp/lollipop/about

## 参照ページ
https://devhitoshi.github.io/lollpop_docs/resources/index.html
