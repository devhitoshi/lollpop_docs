---
name: setlist-analysis
description: 「ろりぽっぷ!!!!!!!」のセットリストを月ごとに集計し、楽曲別の披露回数ランキングを作る。data_event.csv から work/monthly_setlist_ranking.csv を更新する。セトリの集計、披露回数の確認、月次ランキングの更新を依頼されたときに使う。
---

# 月次セットリスト集計

`data_event.csv`（公演ごとのセトリ）を集計し、`work/monthly_setlist_ranking.csv`（年月×楽曲の披露回数）を更新する。

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

4. **結果を伝える**
   `work/monthly_setlist_ranking.csv` が更新されたことをユーザーに伝える。

## 入出力

| パス | 役割 |
| --- | --- |
| `data_event.csv` | 入力。公演ごとの日付・イベント名・会場・セトリ |
| `songs/楽曲一覧.md` | 入力。曲名の正表記（表記ゆれの名寄せに使う） |
| `work/monthly_setlist_ranking.csv` | 出力。年月ごとの披露回数ランキング |

## 注意

- スクリプトは自分でリポジトリルートに `chdir` するので、どこから実行してもよい。
  ただしスクリプトを移動した場合は、両ファイル冒頭の `project_root` の階層数を直すこと。
- セトリの表記ゆれは `analyze_monthly_setlist.py` の `normalize_song_name()` で吸収している。
  新曲を追加したら、まず `songs/楽曲一覧.md` に正表記を追加し、必要なら名寄せルールを足す。
- `data_event.csv` の `setlist` が空、または「セトリ投稿確認」を含む行は集計対象外。
