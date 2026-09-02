---
name: setlist-analysis
description: 「ろりぽっぷ!!!!!!!」のセットリストを月ごとに集計し、楽曲別の披露回数ランキングを作る。events/data_event.csv から events/monthly_setlist_ranking.csv を更新する。セトリの集計、披露回数の確認、月次ランキングの更新を依頼されたときに使う。
---

# 月次セットリスト集計

`events/data_event.csv`（公演ごとのセトリ）を集計し、`events/monthly_setlist_ranking.csv`（年月×楽曲の披露回数）を更新する。

## 手順

1. **不足している月を確認する**

   ```bash
   python3 .claude/skills/setlist-analysis/scripts/check_missing_months.py
   ```

2. **出力に応じてユーザーに確認する**

   | 出力 | 確認すること |
   | --- | --- |
   | `MISSING_MONTHS: 2026-04` | 「不足している月（2026-04）が見つかりました。不足月のみ追加集計しますか？それとも全体を再集計しますか？」 |
   | `NO_MISSING_MONTHS` | 「不足している月はありません。全体を最新データで再集計しますか？」 |

3. **選ばれたモードで集計する**

   不足月のみ:

   ```bash
   python3 .claude/skills/setlist-analysis/scripts/analyze_monthly_setlist.py --months YYYY-MM,YYYY-MM
   ```

   全体を再集計:

   ```bash
   python3 .claude/skills/setlist-analysis/scripts/analyze_monthly_setlist.py --all
   ```

4. **整合性を点検する**

   ```bash
   python3 .claude/skills/setlist-analysis/scripts/check_event_consistency.py
   ```

   楽曲一覧に名寄せできない曲名（集計から黙って落ちているもの）、重複行、日付の書式・並びを列挙する。
   `work/x_fetch/lollipop_1116.jsonl`（x-account-fetch で取得した公式投稿）があれば、セトリらしき投稿があるのに
   CSV に無い日（取りこぼし）や、同日の投稿数より行数が少ない日（1部/2部の片方抜け）も出す。
   `--since/--until` で期間を絞れる。**自動では直さない**ので、候補を見てユーザーと判断する。
   カバー曲・ソロ曲が「名寄せできない」に出るのは正常。

5. **結果を伝える**
   `events/monthly_setlist_ranking.csv` が更新されたこと、整合性チェックで見つかった候補をユーザーに伝える。

6. **（白書を更新するときだけ）図表を再生成する**

   ```bash
   python3 .claude/skills/setlist-analysis/scripts/render_charts.py --out work/charts      # 確認用
   python3 .claude/skills/setlist-analysis/scripts/render_charts.py --out articles/セトリ白書/img --until YYYY-MM-DD
   ```

   `design.md` の色トークンで 01_ranking / 02_heatmap / 03_roots / 04_position / 05_shows を描く。
   matplotlib と日本語フォントが要る（`python3 -m pip install matplotlib`。フォントは `--font` で指定）。
   白書の本文にある数字（公演数・回数）は図と一緒に更新する。

## 入出力

| パス | 役割 |
| --- | --- |
| `events/data_event.csv` | 入力。公演ごとの日付・イベント名・会場・セトリ |
| `songs/楽曲一覧.md` | 入力。曲名の正表記（表記ゆれの名寄せに使う） |
| `events/monthly_setlist_ranking.csv` | 出力。年月ごとの披露回数ランキング |

## 注意

- スクリプトは自分でリポジトリルートに `chdir` するので、どこから実行してもよい。
  ただしスクリプトを移動した場合は、両ファイル冒頭の `project_root` の階層数を直すこと。
- セトリの表記ゆれは `scripts/song_names.py` の `normalize_song_name()` で吸収している（集計とチェックの共通モジュール）。
  新曲を追加したら、まず `songs/楽曲一覧.md` に正表記を追加し、必要なら名寄せルールを足す。
- `events/data_event.csv` を Claude Code で編集すると、hook（`.claude/hooks/after_event_csv.py`）が集計の再実行と
  `check_event_consistency.py --quiet` を自動で回し、結果を文脈に返す。手順1〜3を飛ばしてよいのはこの場合だけ。
- `events/data_event.csv` の `setlist` が空、または「セトリ投稿確認」を含む行は集計対象外。
