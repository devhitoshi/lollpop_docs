---
description: 週刊/月刊 note 記事を作る。期間を半月刻みに分割してGrokで収集し、チャンクを結合してから執筆する
---

詳細な作法は `skills/note_article/SKILL.md` を参照してください。

1. 対象期間をユーザーに確認します（週刊なら対象週、月刊なら対象月）。
   母集団は `data_timetree.csv` に入っているので、TimeTree を毎回見に行く必要はありません。
   対象期間に新しい公演が増えているなら、先に TimeTree のエクスポートを取り込みます。
```bash
python3 .agent/scripts/update_timetree.py [エクスポート] --apply
```

2. 収集プロンプトを半月刻みで生成します。母集団は既定で `data_timetree.csv` を読みます。
```bash
python3 .agent/scripts/prepare_collect.py --month [YYYY-MM]
```
   週刊の場合は `--week [YYYY-MM-DD]`（7日間なので1チャンクのままになります）。
   記事だけ書いてセトリCSVは取らない場合は `--no-population` を付けます。

3. 生成された各チャンクを Grok に投げてもらいます。**ここは代行しません。**
   - 1チャンク＝1新規チャット。モデルは「エキスパート」
   - `x_collect.md` の出力 → 同じディレクトリに `response.md` として保存
   - `event_get.md` の出力（CSV） → 同じディレクトリに `response.csv` として保存
   - `style_ai_poppar.md` や `write_*.md` は Grok に渡さない
   保存が終わったと言われるまで待ちます。

4. チャンクを結合します。
```bash
python3 .agent/scripts/merge_collect.py --period [YYYYMMDD-YYYYMMDD]
```
   警告を必ず読みます。「出力が途中で切れている可能性」が出たチャンクは、
   欠けたまま先に進まず、そのチャンクだけ取り直してもらいます。

5. セトリCSVがあれば `data_event.csv` に取り込みます。まず差分を確認します。
```bash
python3 .agent/scripts/merge_setlist.py --period [YYYYMMDD-YYYYMMDD]
```
   衝突が出た場合はどちらが正しいかユーザーに確認してから適用します。
```bash
python3 .agent/scripts/merge_setlist.py --period [YYYYMMDD-YYYYMMDD] --apply
```

6. 取り込んだ場合はセトリ集計も更新します。
// turbo
```bash
python3 .agent/scripts/check_missing_months.py
```

7. `work/collect/[期間]/merged.md` と、`prompts/style_ai_poppar.md`、
   `prompts/write_weekly.md`（または `write_monthly.md`）を読んで記事を書きます。
   収集データに無いことは書かず、曲名・イベント名は収集データの表記のまま使います。
   `work/note_weekly_[開始日]-[終了日].md` または `work/note_monthly_[YYYY-MM].md` に保存します。

8. ユーザーにレビューを依頼します。記事末尾の編集メモ（確認できなかった項目／判断に迷った点）は
   note には載せないものだと伝えます。
