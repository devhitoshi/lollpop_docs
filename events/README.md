# events/ — 公演データ

- `data_event.csv` … 公演ごとの一次データ（日付・会場・イベント名・セトリ）。**1 公演 1 行**（同日 2 部制は別行）。表記は投稿ママ（`!` の数、`☆`/`★` を揃えない）
- `monthly_setlist_ranking.csv` … 年月 × 楽曲の披露回数。`.claude/skills/setlist-analysis` が生成する（手で直さない）
- `data_appearance.csv` … **ライブ以外の露出**（メディア出演・MC・チェキ会など）。下の「ライブ以外の露出」節を参照

## 新しい公演の入れ方（2026-09 時点の実運用）

セトリは **公式 X（@lollipop_1116）のライブ後投稿**から取る。`.claude/skills/x-account-fetch` で取得した投稿を、
`.claude/skills/weekly-monthly-draft` の素材化が「CSV に無い公演の疑い」として警告するので、その投稿を読んで行を足す。
`data_event.csv` を編集すると hook（`after_event_csv.py`）が集計と整合性チェックを自動で回す。

## 公式の過去投稿はデビュー日からそろっている

2026-09-15 に `@lollipop_1116` の 2024-11-16〜2026-08-01 を取得した（`work/x_fetch/lollipop_1116.jsonl`、約1,480件）。
おかげで `check_event_consistency.py` の `MISSING_EVENTS` / `MORE_POSTS_THAN_ROWS` が**全期間を見られる**。
このとき見つかった抜け7本を補っている。残る警告は誤検知（前日の公演の投稿、セトリが複数投稿に分かれたワンマン、
公式の二重投稿、「ライブ情報」の告知をセトリ投稿と誤認したもの）なので、鵜呑みにせず投稿を開いて確かめる。

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

## ライブ以外の露出は `data_appearance.csv` へ

`data_event.csv` は「ろりぽっぷ!!!!!!! としてステージに立った公演」のデータ。
メンバー個人の MC・リポーター、ネットサイン会、チェキ会、メディア出演はここには入れない。
TimeTree にはこれらも混ざっているので、取り込むときに `data_event.csv` と `data_appearance.csv` に振り分ける。

`data_appearance.csv` の列:

| 列 | 中身 |
| --- | --- |
| `date` | `YYYY-MM-DD`。日が特定できないときだけ `YYYY-MM` を許す（放送月しか分からないメディア出演など） |
| `member` | 誰の露出か。**空ならグループ全体**。複数人なら `・` で区切る。表記は `members/members.md` に合わせる |
| `category` | 下の語彙から1つ |
| `title` | 番組名・企画名・イベント名。表記は発表ママ |
| `outlet` | 放送局・媒体・会場・プラットフォーム |
| `url` | 出典（公式 X の告知投稿など）。無ければ空にして `note` に出典を書く |
| `note` | 補足（役名、欠席、料金、`members/` のどこから取ったか など） |

`category` の語彙（増やすときはこの表も直す）:

- `メディア` … TV・ラジオ・雑誌・Web 記事・ドラマ・映画
- `配信` … YouTube・ツイキャス・SHOWROOM・X スペース・企画動画
- `MC・司会` … イベントの MC、リポーター、司会
- `イベント` … ネットサイン会、チェキ会、撮影会、オフ会（ライブを伴わないもの）
- `客演` … 他グループへのサポート出演、ソロでの対バン出演（ろりぽっぷ!!!!!!! としての出演ではないもの）
- `その他` … 上に当てはまらないもの

セトリの集計（`setlist-analysis`）はこのファイルを見ない。公演数を数える処理も `data_event.csv` だけを見るので、
ここに何を足しても記事の公演数はずれない。

**使いどころ**: 月刊まとめの「ライブ以外の動き」、`strategy/` の定点観測（公演数とは別軸の露出量）、
`members/` の「グループ外の仕事」の根拠。

**未整備**: 2026-07 より前の露出はまだ拾えていない（`members/*.md` に書いてある分だけ入れた）。
過去分は `work/x_fetch/` に投稿が揃っている期間から順に足していく。

2026-08 までは TimeTree → Grok 抽出 → 突合の 3 段で集めていたが、X 収集を API に一本化した 2026-09-02 以降は上の実運用に切り替えた。
