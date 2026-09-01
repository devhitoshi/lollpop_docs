# プロンプト管理

アイドルグループ「ろりぽっぷ!!!!!!!」の **note 記事を作るためのLLM用プロンプト**を置いています。

**収集と執筆を分離**しています。Grok は X 検索と画像OCRという代替不能な能力にだけ使い、
文章の質は Claude 側で握ります。こうしておくと、**文体を直すたびに Grok で取り直す必要がなくなります**。

```
[Grok]   collect/x_collect.md   ──→  構造化された事実データ
                                       │
                                       ├─→ [Claude] write/style_ai_poppar.md + write/weekly.md  ──→ 週刊note
                                       └─→ [Claude] write/style_ai_poppar.md + write/monthly.md ──→ 月刊note

[Gemini] collect/music_listen.md ──→  曲調の聴取メモ  ──→ [Claude] 歌詞考察記事の曲調パート
```

## ディレクトリ構成

| パス | 実行するLLM | 中身 |
| --- | --- | --- |
| [`collect/`](./collect/) | Grok / Gemini | 素材（X の事実データ、音源の聴取メモ）を集めるプロンプト |
| [`write/`](./write/) | Claude | 集めたデータを記事にするプロンプト |

**`write/` のファイルを Grok に渡さないでください。** 収集プロンプトに文体指示が混ざると、
記事の体裁で出力されてしまい、事実の抜けが見えなくなります。ディレクトリを分けているのはこのためです。

## collect/ — 収集用LLMに投げるもの

| ファイル | 用途 |
| --- | --- |
| [`collect/x_collect.md`](./collect/x_collect.md) | 指定期間のXの動きを**事実データとして**収集する（週刊・月刊で共通） |
| [`collect/event_get.md`](./collect/event_get.md) | 公式Xのライブ後投稿からセトリを抽出し、`events/data_event.csv` に追記する |
| [`collect/music_listen.md`](./collect/music_listen.md) | 音源を聴いて曲調を言語化する（**Gemini など音声入力に対応したLLM**に、音源を添付して投げる） |
| [`collect/strategy_metrics.md`](./collect/strategy_metrics.md) | フォロワー数・UGC量・競合比較の**定点観測**（四半期ごと）。`growth_strategy.md` のKPI更新用 |

**使い方**

1. プロンプト内の `[開始日]` `[終了日]`（`event_get.md` は `[ここにJSONを貼る]`）を実際の値に置換する
2. Grok で**新規チャット**を開き、モデルを**「エキスパート」**にする
   （「ファスト」では X 検索が浅く、精度が落ちます）
3. プロンプト全文を貼り付けて送信する（長文なのでクリップボード経由が確実）
4. 1回＝1チャットにする。前の指示を引きずらせないため

## write/ — Claude に渡すもの

| ファイル | 用途 |
| --- | --- |
| [`write/style_ai_poppar.md`](./write/style_ai_poppar.md) | 書き手「AIぽっぱー」の文体定義（週刊・月刊で共通） |
| [`write/weekly.md`](./write/weekly.md) | 週刊記事の構成（**既にグループを知っている人**向け） |
| [`write/monthly.md`](./write/monthly.md) | 月刊記事の構成（**グループを知らない人**向け。オタク度を一段下げる） |

`style_ai_poppar.md` と、記事の種類に応じた構成ファイルの**2つを合わせて**渡します。

## 共通の方針

- **確認できなかったことは書かない。** 推測で埋めさせない
- **曲名・イベント名は投稿どおりの表記を保つ**（`!` の数、`☆`/`★`、`〜`/`～` を正規化しない）
- 他人のポストは長文引用せず、要旨＋リンクにする
- 卒業したメンバーの卒業後の活動・私生活には踏み込まない
- 出典リスト・予定表・編集メモは**素の口調**で書く（感情を混ぜない）

## 関連

- メンバーの人物像・口調・SNS発信の傾向は [`../members/`](../members/) にデータとしてまとめています。
  月刊記事のメンバー紹介などで参照してください（プロンプトではなく資料です）。
- リポジトリ全体の作業手順（歌詞ドキュメント作成、セトリ集計、曲調解析）は [`../.claude/skills/`](../.claude/skills/) にあります。
- 曲調の**数値**（BPM・キー・音量推移）は `music_listen.md` ではなく
  [`../.claude/skills/music-analysis/`](../.claude/skills/music-analysis/) のスクリプトで取ります。
  聴取メモは数値にならない「音の表情」を担当します。
