# events/ — 公演データ

- `data_event.csv` … 公演ごとの一次データ（日付・会場・イベント名・セトリ）。**1 公演 1 行**（同日 2 部制は別行）。表記は投稿ママ（`!` の数、`☆`/`★` を揃えない）
- `monthly_setlist_ranking.csv` … 年月 × 楽曲の披露回数。`.claude/skills/setlist-analysis` が生成する（手で直さない）

## 新しい公演の入れ方（2026-09 時点の実運用）

セトリは **公式 X（@lollipop_1116）のライブ後投稿**から取る。`.claude/skills/x-account-fetch` で取得した投稿を、
`.claude/skills/weekly-monthly-draft` の素材化が「CSV に無い公演の疑い」として警告するので、その投稿を読んで行を足す。
`data_event.csv` を編集すると hook（`after_event_csv.py`）が集計と整合性チェックを自動で回す。

## 母集団の確認に使える参照情報: TimeTree 公開カレンダー

出演予定の一覧は TimeTree の公開カレンダー（`lollipop_1116`）から一括で取れる。**取りこぼしの検出（CSV に無い公演を探す）** に使う。
2026-08-28 に確認した内部 API:

```
GET https://timetreeapp.com/api/v2/public_calendars/lollipop_1116/public_events
    ?from=<epoch_ms>&to=<epoch_ms>&utc_offset=32400
```

- 必須ヘッダ: `x-timetreea: web/2.1.0/ja` と `x-csrf-token`。**素の curl では通らない**（`{"error":{"code":-401}}`）。
  公開カレンダーのページを開いた状態でブラウザから `fetch` するのが確実。csrf トークンはページの通信を 1 回覗けば取れる
- レスポンス: `public_events[]` に `title` / `start_at`(epoch ms) / `note` / `location_name`。会場は `location_name` がほぼ空で、実際は `note` の `📍` 行に入っている
- 5 ヶ月分（78 件）でもページングなしで 1 リクエストに収まった
- ライブ以外の予定（ネットサイン会、打ち上げ、遠征、チェキ会）も混ざる。セトリが取れなくて当然のものとして扱う

2026-08 までは TimeTree → Grok 抽出 → 突合の 3 段で集めていたが、X 収集を API に一本化した 2026-09-02 以降は上の実運用に切り替えた。
