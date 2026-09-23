---
name: x-account-fetch
description: 「ろりぽっぷ!!!!!!!」の公式・メンバーアカウントのX投稿を、twitterapi.io 経由で期間指定・全件取得する。週刊/月刊まとめ記事の収集手順（prompts/collect/x_collect.md）の「1. 公式・メンバーの投稿を取得」に対応。原文をそのまま保存する。エゴサーチ（周囲の反応）はここでは扱わない。
---

# 公式・メンバーアカウントの投稿取得

`prompts/collect/x_collect.md` が抱えていた2つの仕事のうち、**判断が要らないほう**
（対象アカウントが確定していて、原文をそのまま保存すればよい方）をスクリプト化したもの。

- Grok経由の検索は1クエリ10件で頭打ちになり、期間内の投稿を取りこぼしていた
  （2026-09-01の検証で実測: 30日分のグループ名検索は400件超で、Grokの下限20件を大幅に上回った）
- **エゴサーチ（ファンの反応・文脈判断が要るもの）はこのスキルの対象外。**
  `.claude/skills/x-egosearch/`（全件取得→機械仕分け→Claude が判定）で行う

## 前提

- **`work/x_fetch/` に前回までの取得データが復元されていること。** リモートではコンテナが変わると消えるので、
  起動時 hook が `lollpop_data` から自動復元する。空なら `.claude/skills/x-data-sync` の `pull` を先に実行する
  （復元しないまま取得すると、同じ期間を二重に取って課金が無駄になる）
- `TWITTERAPI_IO_KEY` が環境変数または `.env`（リポジトリルート、`.gitignore` 済み）にあること
- twitterapi.io にアクセスできるネットワーク環境であること（信頼モードのClaude Codeリモート環境では
  403で到達できないことがある。フルアクセス環境では到達を確認済み）
- Python 3（標準ライブラリのみ、追加インストール不要）

## 手順

1. **期間を決める。** `until` は終了日の翌日を渡す（`x_collect.md` と同じ慣習。終了日を含めるため）

2. **取得する**

   ```bash
   python3 .claude/skills/x-account-fetch/scripts/fetch_accounts.py \
     --since 2026-08-XX --until 2026-08-YY \
     --max-tweets-per-account 100
   ```

   `--max-tweets-per-account` は **この実行で新しく取る件数** の上限で、既存 jsonl の累計件数とは関係しない。
   何件溜まっていても 100〜200 程度でよい（1週間分ならメンバー1人あたり 100 件前後）。

   `--accounts` を省略すると公式＋現メンバー5人が対象になる。元メンバー（卒業済み）を含めたい場合は
   `--accounts lollipop_1116:公式,mana_lpop:愛月まな,...,asaka_lpop:姫杏朝香` のように明示する
   （ハンドルは `prompts/collect/x_collect.md` の「収集対象アカウント」を参照）。

   実行前に推定コストと所要時間を表示し、確認を求める（`--yes` で省略可）。

3. **出力を確認する**

   `work/x_fetch/` に、アカウントごとの生JSON（`<handle>.jsonl`）と、
   `draft_member_posts.md`（日付順・原文そのままのドラフト）ができる。

4. **記事に使う場合**

   `draft_member_posts.md` は原文の全件列挙であり、記事の「メンバーの投稿」節そのものではない。
   `prompts/collect/x_collect.md` の記録ルール（特徴的な一文を選ぶ、要旨は1〜2文、原文の丸写しは避ける）
   に従って、人間かLLMがここから該当する投稿を選び、「ライブ・イベント」「新曲・初披露」
   「アナウンス・告知」「メンバーの投稿」の各節に振り分ける。

5. **退避する**（このセッションで取得したら必ず）

   ```bash
   python3 .claude/skills/x-data-sync/scripts/sync_x_data.py push -m "<期間と対象>"
   ```

   `work/x_fetch/*.jsonl` は追跡しないので、退避しないと次のセッションで消える。取得には費用と時間がかかるので、
   **セッションを終える前に必ず実行する**（`.claude/skills/session-handoff` の手順にも入っている）。

## 毎日の自動取得（ローカルの Windows のみ・2026-09-17〜）

`scripts/daily_fetch.py` を Windows のタスクスケジューラで毎朝 06:00 に回す（タスク名 `lollpop_daily_fetch`）。
Claude を起動しないので、Claude の利用枠は使わない。

- **取るもの**: 公式＋現メンバー5人の投稿（`work/x_fetch/<handle>.jsonl` に追記）と、
  **ハッシュタグだけのエゴサ**（`work/x_fetch/hashtags_YYYY-MM.jsonl`。どのタグに当たったかは `_tags`）
  - タグは `#ろりぽっぷ` ＋ 各メンバーの X プロフィールに書かれたタグ。取得済み投稿の `author.profile_bio` から毎回拾うので、
    プロフィールが変わっても追従する（取れないときはスクリプト内の予備リスト。2026-09-09 時点で
    `#まなてぃータイム` `#くるみるく` `#くるみんとKP` `#餃子のおまゆ` `#まんてんあみてん` `#まうだよ`）
  - 週刊用のフル・エゴサ（メンバー名・カタカナ表記など）は回さない。それは `x-egosearch`／`weekly-pipeline` のとき
- **期間**: 前回取り終えた日の翌日〜昨日。今日は取らない（途中で取ると翌日に取り直して二重に課金されるため）。
  PC が止まっていた日は次の実行でまとめて取る。空きが 31 日を超えたら取らずに止まる（`--since` で手動実行）
- **状態とログ**: `work/x_fetch/.daily_state.json`（`covered_from`〜`last_until` が途切れずに取れている範囲）と
  `work/x_fetch/logs/daily_fetch.log`。起動時サマリに「毎日取得: 〜まで取得済み（成功/失敗）」が出る。
  失敗したら状態を進めないので、次の実行で同じ期間から取り直す
- **週刊との関係**: `run_weekly.py --stage collect` は、毎日取得が取り終えた日の公式・メンバー投稿を取り直さない（`--refresh` 時を除く）
- **費用の目安**: 公式・メンバーが月 600 件前後（約 $0.09）、タグが 1 日 10 件前後（月 約 $0.05）。
  初回（2026-09-17、9/8〜9/16 の 9 日分）は 26 コール・約 5,000 クレジット
- **登録・確認・解除**:

  ```powershell
  powershell -ExecutionPolicy Bypass -File .claude\skills\x-account-fetch\scripts\register_daily_task.ps1   # 登録（-At 07:30 で時刻変更）
  Start-ScheduledTask -TaskName lollpop_daily_fetch                                                        # 今すぐ動かす
  Get-ScheduledTaskInfo -TaskName lollpop_daily_fetch                                                      # LastTaskResult 0 が成功
  Unregister-ScheduledTask -TaskName lollpop_daily_fetch -Confirm:$false                                   # 解除
  python .claude/skills/x-account-fetch/scripts/daily_fetch.py --dry-run                                   # 期間・タグ・検索文だけ表示
  ```

- クラウドでは回さない（コンテナが使い捨てで、twitterapi.io に届かない環境もある）。退避は今まで通りセッションの終わりに `x-data-sync`

## 制約・注意点（禁止事項に対応）

- `--max-tweets-per-account` は必須（デフォルトなし）。省略するとエラーで止まる。
  数えるのは **今回の新規取得分**（2026-09-15 に修正）。それ以前は既存 jsonl の累計件数と比べていたので、
  **累計が上限を超えているアカウントは API を1回も叩かず「新規0件」で終わっていた**
  （上限200・既存815件のアカウントが素通りした）。古い挙動を思い出して上限を盛らなくてよい
- 未課金は 0.2 QPS。**逐次のみ・並列化しない**（アカウント間も5秒空ける）
- 429/5xx はジッタ付き指数バックオフでリトライ
- 取得済みJSONLからIDを復元し、再実行時は重複取得しない（中断・再開対応）
- APIキーはコードに書かない。環境変数か `.env` から読む
- **$99/月の自動チャージサブスクリプションに登録しない。クレジットの購入手順を承認なしに実行しない**
- 取得したツイートの生JSON（`work/x_fetch/*.jsonl`）は `.gitignore` 対象。**他人の投稿をコミットしない**。
  保存は非公開リポジトリ `lollpop_data` へ（`.claude/skills/x-data-sync`）

## 既知の癖（2026-09-01の検証で判明）

- **`-from:` 除外オペレーターは信用しない。** 除外指定してもそのアカウント自身の投稿が
  紛れ込むことが実測されている（OR句と併用した場合の挙動と見られる）。
  このスクリプトはアカウントごとに個別の `from:` 検索をかけるだけなので、そもそも除外に頼っていない
- 日付は `since:YYYY-MM-DD until:YYYY-MM-DD`（空白区切り・時刻なし）で動作する。
  ドキュメントが「非対応」と明記しているのはアンダースコア＋時刻つきの `since:..._UTC` 形式で、
  この書き方は対象外
- 単価は `$0.15/1,000ツイート`、`$1=100,000クレジット`、最低課金 `15クレジット/リクエスト`
- 検索エンドポイントは `GET /twitter/tweet/advanced_search`（`docs.twitterapi.io/llms.txt` で確認済み）

## 規約・法務

サードパーティ経由の取得はXの規約との関係がグレー。個人の分析・記事執筆の範囲を前提とする。
収集した投稿は他人の著作物。再配布・データセット公開・生成モデルの学習利用はしない。
