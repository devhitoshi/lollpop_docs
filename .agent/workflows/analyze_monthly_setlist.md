---
description: 月ごとのセットリストを解析し、楽曲ごとの披露回数をランキング形式で集計する
---

1. まず、既存の集計結果と生データを比較し、不足している月がないか確認します。
// turbo
```bash
python3 .agent/scripts/check_missing_months.py
```

2. スクリプトの出力結果を確認します。
   - `MISSING_MONTHS: 2026-04` のように出力された場合、ユーザーに「以下の不足している月が見つかりました（2026-04）。不足月のみを追加集計しますか？それとも全体を最初からやり直しますか？」と尋ねます。
   - `NO_MISSING_MONTHS` のように出力された場合、ユーザーに「現在不足している月はありません。全体を最新データで再集計しますか？」と尋ねます。

3. ユーザーの回答に応じて、それぞれのモードで集計処理を実行します。
   - 「不足月のみ」の場合：
```bash
python3 .agent/scripts/analyze_monthly_setlist.py --months [YYYY-MM,YYYY-MM]
```
   - 「全体」の場合：
// turbo
```bash
python3 .agent/scripts/analyze_monthly_setlist.py --all
```

4. 処理完了後、`work/monthly_setlist_ranking.csv` が更新されたことをユーザーに伝えます。
