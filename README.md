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
- [はじめての方へ / スターターパック (starter_pack.md)](./starter_pack.md)
- [楽曲一覧 (songs/楽曲一覧.md)](./songs/楽曲一覧.md)
- [全曲コール表 (songs/call_list.md)](./songs/call_list.md)
- [公式ルール・現場のマナー (rules.md)](./rules.md)
- [メンバープロフィール (members.md)](./members.md)
- [リンク集 (link.md)](./link.md)
- [アー写履歴 (artist_photos.md)](./artist_photos.md)
- [記事一覧 (articles/)](./articles/README.md)
- [セトリ白書 — セットリスト分析記事 (resources/setlist_analysis.html)](./resources/setlist_analysis.html)
- [公開用メインページ (resources/index.html)](./resources/index.html)

## リポジトリ構成

読み物と、それを作るための道具を分けています。

### 読み物（公開する資料）

| パス | 内容 |
| --- | --- |
| `starter_pack.md` | はじめての方へ |
| `members.md` | メンバープロフィール（基本情報の正） |
| `rules.md` / `link.md` / `artist_photos.md` | ルール・リンク集・アー写履歴 |
| `songs/` | 楽曲一覧、コール表、歌詞（`songs/lyrics/`）、曲調データ（`songs/analysis/`） |
| `articles/` | AIぽっぱー文体の note 用記事ドラフト（索引は `articles/README.md`） |
| `resources/` | GitHub Pages で公開しているポータル |
| `resources/setlist_analysis.html` | セトリ白書（セットリスト分析記事。`data_event.csv` から集計したグラフ付き） |

### データ

| パス | 内容 |
| --- | --- |
| `members/` | メンバーのパーソナリティデータ（人物像・口調・SNS発信の傾向） |
| `data_event.csv` | 公演ごとの日付・会場・セトリ |
| `audio/` | 曲調解析に使う音源の置き場（音源自体はリポジトリに入りません） |
| `work/` | 生成物・作業中のファイル（月次セトリ集計、全曲の曲調比較表など。案内は `work/README.md`） |

### 道具

| パス | 内容 |
| --- | --- |
| `prompts/` | note 記事を作るためのLLM用プロンプト（`collect/` = Grok・Gemini、`write/` = Claude） |
| `.claude/skills/` | 繰り返す作業の手順書（歌詞ドキュメント作成、月次セトリ集計、曲調解析） |

## 公式サイト
https://flapinc.jp/lollipop/about

## 参照ページ
https://devhitoshi.github.io/lollpop_docs/resources/index.html
