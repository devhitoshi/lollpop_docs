---
name: note_article
description: ろりぽっぷ!!!!!!! の週刊/月刊 note 記事を作る。TimeTree の出演予定を母集団に、Grok で X の動きを半月刻みで収集し、複数チャンクを結合してから Claude で執筆する
---

# 週刊・月刊 note 記事の制作

## 全体の流れ

**収集と執筆を分離**している（`prompts/README.md`）。Grok は X 検索と画像OCRという代替不能な部分にだけ使い、
文章の質は Claude 側で握る。こうしておくと、文体を直すたびに Grok で取り直す必要がない。

```
TimeTree（出演予定 ＝ 母集団）
  │
  ├─→ [Grok] event_get.md   ──→ セトリCSV        ──→ data_event.csv
  │
  └─→ [Grok] x_collect.md   ──→ 収集データ(Markdown)
                                    │（半月チャンクを結合）
                                    └─→ [Claude] style_ai_poppar.md
                                                 + write_weekly.md / write_monthly.md
                                                    ──→ note 記事
```

## Claude がやる範囲・やらない範囲

| | 担当 |
|---|---|
| 期間を半月刻みに分割し、チャンクごとの収集プロンプトを生成 | Claude（スクリプト） |
| Grok に投げて出力を得る | **ユーザー**（ブラウザ操作が必要） |
| 複数チャンクの結合・重複除去・打ち切り検出 | Claude（スクリプト） |
| data_event.csv へのマージ | Claude（スクリプト） |
| 記事の執筆 | Claude |

**Grok の操作は代行しない。** プロンプトを用意したら手を止め、ユーザーが出力を保存するのを待つ。

---

## 手順

### 1. 期間を決める

- 週刊 … 対象週（月曜起点の7日間）
- 月刊 … 対象月

### 2. 母集団を用意する（セトリCSVを更新するときだけ）

記事だけを書くなら省略してよい。`event_get.md` は出演イベントのJSONを必要とするので、そのときだけ要る。

公開カレンダー: https://timetreeapp.com/public_calendars/lollipop_1116

ユーザーに `.ics` / `.json` / `.csv` のいずれかで用意してもらう。JSON なら次の形。

```json
[{ "title": "単独ライブ（2部 Vol.18 夏曲お披露目公演）",
   "start_at": "2026-08-26",
   "venue": "中野坂上SUB TOKYO" }]
```

過去分のセトリを埋め直すだけなら `--population data_event.csv` を渡してもよい。

### 3. 収集プロンプトを生成する（半月刻み）

```bash
# 月刊（自動で前半・後半の2チャンクになる）
python3 .agent/scripts/prepare_collect.py --month 2026-08 --population <母集団ファイル>

# 週刊（7日間なので1チャンクのまま。半月境界を跨いでも分割しない）
python3 .agent/scripts/prepare_collect.py --week 2026-08-24

# 任意期間
python3 .agent/scripts/prepare_collect.py --from 2026-07-20 --to 2026-09-10
```

分割規則は「期間が16日以内なら割らない。超えたら半月境界（1〜15日 / 16日〜月末）で割る」。

`work/collect/<期間>/<チャンク>/` に次が生成される。

| ファイル | 中身 |
|---|---|
| `x_collect.md` | `[開始日]` `[終了日]` `[終了日+1日]` を実際の日付に置換済み |
| `event_get.md` | 母集団JSONを差し込み済み（`--population` を渡したときのみ） |
| `population.json` | そのチャンクの期間に入る出演イベント |
| `chunk.json` | チャンク番号・期間（結合時に使う） |

### 4. ユーザーに Grok へ投げてもらう

伝えること。

- **1チャンク＝1新規チャット。** 前の指示を引きずらせない
- モデルは**「エキスパート」**（「ファスト」では X 検索が浅い）
- 記事用: `x_collect.md` を貼る → 返ってきた本文を同じディレクトリに **`response.md`** として保存
- セトリ用: `event_get.md` を貼る → 返ってきた CSV を **`response.csv`** として保存
- **`style_ai_poppar.md` / `write_weekly.md` / `write_monthly.md` は Grok に渡さない。**
  収集プロンプトに文体指示が混ざると記事の体裁で出力され、事実の抜けが見えなくなる

`response.md` は**出力形式の見出し（`## ライブ・イベント` など）を保ったまま**保存してもらう。
結合スクリプトはこの見出しを見て節を対応づける。

### 5. チャンクを結合する

```bash
python3 .agent/scripts/merge_collect.py --period 20260801-20260831
```

節ごとにマージし、`work/collect/<期間>/merged.md` を作る。

- ライブ・イベントは日付昇順に並べ直す
- メンバーの投稿はメンバー単位でまとめ、各メンバーの中を日付順にする
- アナウンス・外部の反応は重複を除いて日付順にする
- `## 今後の予定` の表は行を統合して日付順にする
- 編集メモ（確認できなかった項目 / 判断に迷った点）はチャンク別に残す（どこで取りこぼしたか追えなくなるため）

**出力の警告を必ず読む。**

- `出力が途中で切れている可能性` … そのチャンクだけ Grok で取り直してもらう。
  **欠けたまま記事を書かない。** 「外部の反応」以降が丸ごと落ちるのが典型
- `「今後の予定」に結合後の期間内の行があります` … 前半チャンク時点では予定だったもの。
  すでに実施済みなら、記事では「今後の予定」ではなくライブの節で扱う

### 6. セトリCSVを取り込む（`response.csv` があるとき）

```bash
python3 .agent/scripts/merge_setlist.py --period 20260801-20260831           # dry-run
python3 .agent/scripts/merge_setlist.py --period 20260801-20260831 --apply
```

- 既定は dry-run。差分を読んでから `--apply`
- 既存行と中身が食い違ったら **既存を残して衝突として報告**する。どちらが正しいかユーザーに確認してから
  `--prefer new` を付ける。勝手に上書きしない
- 既存のセトリが「セトリ投稿確認できず」などの未確定値だった場合は、自動で新しい値に置き換える
- 触らない行は元の行をそのまま残すので、無関係な差分は出ない

取り込んだらセトリ集計も更新する。

```bash
python3 .agent/scripts/check_missing_months.py
python3 .agent/scripts/analyze_monthly_setlist.py --months 2026-08
```

### 7. 記事を書く

読み込むもの。

1. `work/collect/<期間>/merged.md` … 事実データ。**ここに無いことは書かない**
2. `prompts/style_ai_poppar.md` … 書き手「AIぽっぱー」の文体
3. `prompts/write_weekly.md` または `prompts/write_monthly.md` … 構成

週刊と月刊は読者が違う。

- **週刊** … すでにグループを知っている人向け。用語の注釈は不要
- **月刊** … ほとんど知らない人向け。限界オタク度を一段下げ、専門用語に短い注釈を付け、愛称は初出で本名を添える

書くときに落としやすい点（詳細は元ファイルを読むこと）。

- 事実（日時・会場・料金・チケット・セトリ）は**箇条書きや表のまま淡々と**。ここに感情を混ぜない
- テンションは地の文にだけ載せる。`!` は1文に1個まで（グループ名の `ろりぽっぷ!!!!!!!` は別）
- **曲名・イベント名は収集データの表記のまま。** `!` の数、`☆`/`★`、`〜`/`～` を正規化しない
- 「今後の予定」「出典」「編集メモ」は**素の口調**で書く
- 記事の後ろに `---` で区切って編集メモ（確認できなかった項目 / 判断に迷った点）。note には載せない
- 動員数・売上・他グループとの比較・運営やメンバーの内情の推測には感情を乗せない。煽らない
- 卒業したメンバーは在籍時の事実のみ。卒業後の活動やプライベートには踏み込まない

保存先。

- 週刊 … `work/note_weekly_<開始日>-<終了日>.md`
- 月刊 … `work/note_monthly_<YYYY-MM>.md`

---

## 置き場所

```
work/collect/20260801-20260831/
├── 20260801-20260815/
│   ├── x_collect.md      … Grok に貼る（生成物）
│   ├── event_get.md      … Grok に貼る（生成物・母集団あり時）
│   ├── population.json   … 母集団（生成物）
│   ├── chunk.json        … メタ情報（生成物）
│   ├── response.md       … Grok の出力（ユーザーが保存）
│   └── response.csv      … Grok の出力（ユーザーが保存）
├── 20260816-20260831/
│   └── （同上）
└── merged.md             … 結合結果。執筆はこれを読む
```

## つまずきやすいところ

- **月を一度に投げると切れる。** 2026年8月（ライブ13本）を1回で投げたところ「メンバーの投稿」の途中で
  打ち切られ、それ以降が丸ごと欠落した。1回の出力はおおむね1万3千字が上限。半月刻みは省略しない
- **「ロリポップ」はレンタルサーバーの投稿が大量に混ざる。** 除外条件は `x_collect.md` に書いてある
- **「まう」は一般語**なので単体で検索しない
- メンバー構成が変わったら `prompts/x_collect.md` の収集対象アカウントと
  `prompts/README.md` の記述を直す

## 関連ファイル

- `prompts/README.md` … 収集と執筆を分けている理由、Grok の使い方
- `prompts/x_collect.md` / `prompts/event_get.md` … Grok に投げる（収集）
- `prompts/style_ai_poppar.md` / `prompts/write_weekly.md` / `prompts/write_monthly.md` … Claude が使う（執筆）
- `.agent/scripts/prepare_collect.py` / `merge_collect.py` / `merge_setlist.py`
- `data_event.csv` … セトリの蓄積先
