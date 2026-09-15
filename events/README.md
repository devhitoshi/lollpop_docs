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

- 必須ヘッダ: `x-timetreea: web/2.1.0/ja` と `x-csrf-token`。**ヘッダ無しの素の curl では通らない**（`{"error":{"code":-401}}`）。
  csrf トークンとセッション cookie は公開カレンダーのページから取れるので、**curl だけで完結する**（2026-09-15 にクラウド環境で確認）:

  ```bash
  curl -s https://timetreeapp.com/public_calendars/lollipop_1116 -c /tmp/tt_cookies.txt -o /tmp/tt_page.html
  TOKEN=$(grep -o 'csrf-token" content="[^"]*' /tmp/tt_page.html | sed 's/.*content="//')
  FROM=$(python3 -c "import datetime as d;print(int(d.datetime(2026,9,1,tzinfo=d.timezone(d.timedelta(hours=9))).timestamp()*1000))")
  TO=$(python3 -c "import datetime as d;print(int(d.datetime(2027,6,30,tzinfo=d.timezone(d.timedelta(hours=9))).timestamp()*1000))")
  curl -s "https://timetreeapp.com/api/v2/public_calendars/lollipop_1116/public_events?from=$FROM&to=$TO&utc_offset=32400" \
    -H "x-timetreea: web/2.1.0/ja" -H "x-csrf-token: $TOKEN" \
    -H "Referer: https://timetreeapp.com/public_calendars/lollipop_1116" -b /tmp/tt_cookies.txt
  ```
- レスポンス: `public_events[]` に `title` / `start_at`(epoch ms) / `note` / `location_name`。会場は `location_name` がほぼ空で、実際は `note` の `📍` 行に入っている
- 5 ヶ月分（78 件）でもページングなしで 1 リクエストに収まった
- ライブ以外の予定（ネットサイン会、打ち上げ、遠征、チェキ会）も混ざる。セトリが取れなくて当然のものとして扱う
- **タイトルが「ライブ予定」だけで `note` が空の行がある**（会場も公演名も未発表の押さえ）。
  これも `data_event.csv` に `ライブ予定` / `（未発表）` で入れておき、次に確認したときに
  公演名・会場が出ていれば書き換える（オーナー方針・2026-09-15）

## 未開催の公演を先に入れるとき

告知の段階で行を足しておいてよい（`setlist` 列は空のまま）。会場は TimeTree の `note` の `📍` 行か、
公式 X の「［ろりぽっぷ!!!!!!!ライブ情報🍭］」投稿から取る。TimeTree に無い公演が公式 X だけで告知されることがある
（例: 2026-10-05 の `NEW ORDER #無銭NIGHT`）ので、**両方を突き合わせる**。
開催後に公式 X のセトリ投稿が出たら、同じ行の `setlist` を埋める（`check_event_consistency.py` の
`MISSING_EVENTS` が、セトリ投稿があるのに行が無い公演を教えてくれる）。

**終わった日付が「ライブ予定」のまま残っていたら、TimeTree の更新漏れとみなす。公式 X の投稿を正として
公演名・会場・セトリを埋める**（TimeTree は押さえの段階で入れたまま直されないことがある）。

## ライブ以外の露出は入れない

`data_event.csv` は「ろりぽっぷ!!!!!!! としてステージに立った公演」のデータ。
メンバー個人の MC・リポーター、ネットサイン会、チェキ会、メディア出演はここには入れない
（例: 2026-09-25 エンタパークフェス2026 のやぎくるみの公式 MC、9/27 の松川愛美の公式リポーター）。
TimeTree にはこれらも混ざっているので、取り込むときに落とす。

2026-08 までは TimeTree → Grok 抽出 → 突合の 3 段で集めていたが、X 収集を API に一本化した 2026-09-02 以降は上の実運用に切り替えた。
