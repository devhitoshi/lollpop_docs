# 曲の解剖データと読み解き図

曲ごとに 1 フォルダ（`[曲名]/`）。音源を楽器ごとに分けて取り出したデータと、そこから作った図です。
**手書きではなく、スキル `song-anatomy` が作ります**（手順は [`.claude/skills/song-anatomy/SKILL.md`](../../../.claude/skills/song-anatomy/SKILL.md)）。
人が書くのは `story.json`（図の文面）と `owner_check.json`（オーナーの訂正）だけです。

図・記事・動画・MV のどれからでも読めるように、**時刻はすべて秒の小数**で持っています（動画では `秒 × fps` でフレームに直す）。

音そのもの（分離した wav）はここには無く、`audio/stems/[曲名]/` にあります（リポジトリには入らない場所）。
歌詞の原文も入れていません。`lines[].line_no` が `songs/lyrics/[曲名].md` の行番号、
`tokens[].c0`〜`c1` がその行の中の文字位置です。

記事で書いてよい範囲は [`../README.md`](../README.md) が正です。**オーナーが確認する前の図と文面は、記事・動画に使いません。**

## ファイル

| ファイル | 中身 |
| --- | --- |
| `anatomy.json` | 本体。下の表の項目が入る |
| `series/stem_loudness.csv` | 1/100 秒ごとの音量。列は `t, mix_db, vocals_db, drums_db, bass_db, other_db`（dBFS。0 が最大で、小さいほど静か） |
| `series/vocal_presence.csv` | 1/100 秒ごとの、ボーカルが鳴っているか（`vocal_on` 0/1）と左右の広がり（`width`。鳴っていない所は空） |
| `series/chroma_accompaniment.csv` | 約 0.093 秒ごとの、伴奏（ベース＋その他）の 12 音の強さ（0〜1）。転調の検出に使った元データ |
| `chords.json` | 和音（コード）の推定。2 拍ごとのコード名・度数・役割と、区間ごとのキーの提案（下の「chords.json の項目」） |
| `和音の読み.md` | 和音の考察。用語の説明 → この曲で起きていること → 耳で確かめてほしい所。**人が書く** |
| `owner_check.json` | **オーナーの訂正を書く場所。**解析をやり直しても消えない。図はここの値を優先する |
| `story.json` | 読み解き図の文面（6 つの場面、曲の色）。**人が書く** |
| `読み解き図.png` | 初心者向けの図（横長）。`story.json` から作る |
| `解剖図.png` | データをそのまま並べた図（楽器ごとの音量の波形） |
| `歌割り表.md` | 行ごとの時刻と、誰が歌っているかの空欄 |

## anatomy.json の項目

| 項目 | 中身 | 確かさ |
| --- | --- | --- |
| `duration_sec` | 尺 | 確か |
| `source` / `tools` | 元ファイルの SHA-256、使った道具とモデルの版 | — |
| `sections[]` | 構成の区間。`name`・`kind`（vocal / instrumental）・`start`・`end`・`mean_db`（その区間の楽器ごとの平均音量） | 境目は機械の時刻合わせ。**耳での確認が要る** |
| `lines[]` | 歌詞 1 行ごとの `start`・`end`、`tokens[]`（文字単位の時刻と確からしさ `p`）、`vocal_width`、`singer`（空欄） | 同上。`start_aligned` がある行は、機械が頭を直した行 |
| `quiet.items[]` | ドラムが抜ける区間 | わりと確か |
| `modulation.items[]` | 最初のサビと比べて何半音ずれているか（`semitones_up`）と、12 通りのずらし方それぞれの相関 | 機械。**耳での確認が要る** |
| `voices` | 声の左右の広がりを 2 つに分けた境目 | 実験。当てにしない |
| `beats` | 拍の時刻と、小節の頭の見当（`times[downbeat_phase::4]`） | **参考値。**BPM と同じく倍・半分の取り違えがありうる |
| `onsets` | 楽器ごとの音の立ち上がり（`drums` がドラムの打点） | わりと確か。細かい取りこぼしはある |

`status` は `machine`（機械のまま）か `owner_confirmed`（オーナーが確認・訂正した）。

## chords.json の項目

| 項目 | 中身 | 確かさ |
| --- | --- | --- |
| `halfbars[]` | 2 拍ごとの `t0`・`t1`、`chord`（例 `Em7`、`C/D` はベースが D）、`root`・`quality`・`bass`、当てはまりの点 `score`、`section` | 機械。**メジャーとマイナー、7th の有無を取り違えることがある** |
| `halfbars[].degree`・`function` | 区間のキーから数えた度数（`Ⅵm7` など）と役割（`home` 家／`float` 浮く／`tension` 張る／`sad` 切ない／`other`／`none` 和音なし） | キー次第。図は `story.json` の `keys` を当てて出し直す |
| `sections[]` | 区間ごとのキーの提案 `key_tonic`（長調の主音。短調の曲もその平行長調で数える）、`key_source`（`family`＝同じ種類の区間でまとめた／`own`＝その区間だけ別）、`key_candidates`（当てはまりが並んだ候補） | **提案。**5 度隣と区別がつきにくい |
| `key_changes[]` | 隣り合う区間でキーが変わる所 | 提案のキーから出したもの。**耳での確認まで書かない** |
| `consistency` | くり返す区間（A・B・サビ…）で、同じ根音が出た割合 | 確からしさの目安。0.6 を切る区間は材料にしない |

`status` は `machine`。オーナーが確かめた点は `和音の読み.md` に書く。

## owner_check.json の書き方

```json
{
  "sections": {"3B": {"start": 174.3}},
  "lines": {"68": {"start": 174.3, "singer": "全員"}},
  "modulation": {"ラスサビ": {"semitones_up": 0}},
  "quiet": {"items": [{"start": 195.6, "end": 202.6}]}
}
```

`sections` は構成名、`lines` は歌詞ファイルの行番号が鍵。書いた項目だけが上書きされ、`status` が `owner_confirmed` になります。

## story.json（読み解き図の文面）の書き方

読み解き図の 1 場面が `points` の 1 項目。図の文を直すときも、別の曲を足すときも、ここを書く。

| 項目 | 中身 |
| --- | --- |
| `theme_color` | 曲の色（`#rrggbb`）。背景と曲名の下線に使う。**オーナーに聞いて決める。無いと図を作らない** |
| `on_db` | 省いてよい。「鳴っている」とみなす境目（既定 −40 dB）。分離した音の残りが大きく、歌の無い所まで歌の段が塗られる曲だけ書く（乙女ロックは −33）。図の帯と `checks` の `on`／`off` の両方に効く |
| `headline`・`lead` | 曲名の下の一言と、導入文。根拠は `headline_basis` に書く |
| `time`・`section`・`where` | 場面の時刻（秒）と、それが入っている構成名。`where` は図に出す場所の言い方（省くと構成名） |
| `title`・`fact`・`reading` | 見出し、音で起きていること（事実）、そこからの読み（考察。断定しない文で書く） |
| `evidence` | 事実の根拠を人が読める形で |
| `checks` | 事実を機械で確かめる条件。**1 つも無い場面があると図を作らない** |
| `quotes` | 引用する歌詞。`line_no` は歌詞ファイルの行番号で、表記が一字でも違うと止まる |
| `span`・`target`・`rows` | 地図の上で囲む時間の範囲と段（`band`＝構成の帯／`vocals`／`drums`／`bass`／`other`／`chords`＝和音の段） |
| `keys`・`keys_note` | 省いてよい。区間のキーの指定（`{"1B": "F#"}`。長調の主音。同じ名前の区間の 1 つだけなら `"間奏#2"`）と、そう決めた理由。和音の段の色と和音の `checks` に効く |
| `replaced` | 和音の場面などと入れ替えた、元の場面の記録 |

`checks` に書ける条件（どれも `say` に日本語の説明を付ける）:

```json
{"say": "…", "stem": "bass", "state": "off", "from": 22, "to": 31}
{"say": "…", "stem": "drums", "quieter_than": -33, "from": 154, "to": 164}
{"say": "…", "width_lines": [5, 6], "below": 0.09}
{"say": "…", "width_lines": [13, 16], "widest": true}
{"say": "…", "section_seconds": ["1サビ", "2サビ"], "about": 22.3, "tol": 0.5}
{"say": "…", "sections_in_order": ["2サビ", "Cメロ", "間奏", "3B"]}
{"say": "…", "section_count": "B", "equals": 3}
{"say": "…", "line_contains": 83, "t": 203}
{"say": "…", "line_starts_within": 8, "after": 31, "sec": 2}
{"say": "…", "chord_seq": "1サビ", "degrees": ["Ⅱm", "Ⅲm", "Ⅳ"]}
{"say": "…", "home_in": "1サビ", "state": "none"}
{"say": "…", "function_at": 202.6, "is": "home"}
{"say": "…", "key_shift": ["1B", "1サビ"], "semitones": 1}
```

- `stem` の `on`／`off` は、from 秒から to 秒の手前まで、1 秒ごとの平均が −40 dB より大きい／小さいこと
- 和音の 4 つ（2026-10-09〜）は `chords.json` に `keys` を当てた結果で確かめる。`chord_seq` の度数は根音＋短調なら `m` だけ（7th・sus4・分数は見ない）で、同じ和音の続きは 1 つにまとめて比べる。`key_shift` は上がるが正
- `width_lines` は歌詞の行番号。`above`／`below` は声の広がりの値、`widest`／`narrowest` は曲中のほかの全行との比較

## 作り直し方

コマンドは [`SKILL.md`](../../../.claude/skills/song-anatomy/SKILL.md) の手順 A〜D。
図だけなら音源も専用環境も要りません（`build_story.py [曲名]`。このフォルダのデータだけを読む）。
