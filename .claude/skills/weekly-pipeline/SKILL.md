---
name: weekly-pipeline
description: 週刊まとめ記事の「収集→素材化→仕上げ」を一本で連結する。x-account-fetch・x-egosearch・weekly-monthly-draft・setlist-analysis・article-review・x-data-sync の実行順・引数・鮮度確認・件数表示をまとめて引き受け、既存6スキルの責務は変えない。「週刊を最初から最後まで」「先週分を取り直して」「週刊の続きから」「データを最新化して」「いいね数を最新にして」と言われたとき、または実行頻度が不定で前回からの空き期間が分からないときに使う。
---

# 週刊パイプライン（収集〜仕上げの連結）

`.claude/skills/weekly-pipeline/scripts/run_weekly.py` が本体。3段階（`--stage collect/material/finish`）に分けて、
各段階の中で本物のスクリプトを決まった順に呼ぶ。スクリプトのdescriptionや引数はここでは変えない。
文体・構成の正は `prompts/write/`、素材の作り方の正は各スキルの SKILL.md（`.claude/skills/x-account-fetch/`
`.claude/skills/x-egosearch/` `.claude/skills/weekly-monthly-draft/`）にある。**このスキルは読む順番と手順、
特に「鮮度の確認」「いいね数を最新化するための再取得」「3段階の件数表示」だけを引き受ける。**

## 前提

- 期間は毎週決まった曜日に回せるとは限らない（実行頻度が不定）。**既定の期間は「前回実行の翌日〜今日」**。
  2週間空いても1回で追いつく。記事の期間（週刊なら7日）は `--stage material` の素材化のときに別途切る
- 状態は `work/x_fetch/.pipeline_state.json`（`last_until` / `last_run_at` / `stage`）に持つ。
  無ければ `work/x_fetch/*.jsonl` の最新投稿日から since を逆算し、表示して確認を求める（`--yes` で省略可）
- `TWITTERAPI_IO_KEY` と twitterapi.io への到達性は `.claude/skills/x-account-fetch` と同じ前提

## 手順

1. **collect（収集）**

   ```bash
   python .claude/skills/weekly-pipeline/scripts/run_weekly.py --stage collect
   ```

   - 既存 `work/x_fetch/*.jsonl` の鮮度（アカウントごとの最終日・件数）を表示する
   - `--refresh` を付けると、期間内の既存行を削除してから取得し直す（いいね数などを最新化したいとき）。
     削除前に `work/x_fetch_bak_<今日の日付>/` へバックアップする（2026-09-07 に手作業で行ったのと同じ運用）。
     **本番キャッシュを消す操作なので、実行前にバックアップ先を確認する**
   - `fetch_accounts.py` → `fetch_egosearch.py` → `triage_egosearch.py`（初回・`--decisions` 無し）の順に呼ぶ。
     `--max` は両方の上限引数（`--max-tweets-per-account` / `--max-tweets-per-query`）に渡る（既定 200）
   - 最後に3段階の件数（生データ→候補→機械仕分け内訳）を表示する
   - **人がやる判断**: `work/x_fetch/egosearch_triage_<since>_<until>_review.txt` を読み、
     `data/x/egosearch_decisions_<since>_<until>.txt` に `<id> adopt|reject [メモ]` で判定を書く
     （書式・判断基準は `.claude/skills/x-egosearch/SKILL.md` の手順3）
   - **次に進む条件**: 判定ファイルを書き終えたら `--stage material`

2. **material（素材化）**

   ```bash
   python .claude/skills/weekly-pipeline/scripts/run_weekly.py --stage material
   ```

   - `triage_egosearch.py --decisions data/x/egosearch_decisions_<since>_<until>.txt`（最終）を実行し、
     3段階の件数（生データ→候補→**採用**・最終）を表示する
   - `build_material.py` で素材ファイル（`work/x_fetch/draft_material_<since>_<until>.md`）を組み立てる。
     **「CSV に無い公演の疑い」が出たら exit 2 で止まる。** 表示された該当行を見て `events/data_event.csv` を直し、
     `--stage material` をやり直す
   - `check_event_consistency.py` を実行する（QA用。ここでは常に exit 0 なので、出力の
     `MISSING_EVENTS` / `UNSOURCED_ROWS` は目視で確認する）
   - **人がやる判断**: 素材ファイルと `events/data_event.csv` を読み、`data/x/egosearch_<since>_<until>_reactions.md`
     を手書きしてから、`prompts/write/` の文体・構成で `articles/週刊まとめ/<since>_<until>.md` を書く
     （手順は `.claude/skills/weekly-monthly-draft/SKILL.md` の3〜4）
   - **次に進む条件**: 記事の本文を書き終えたら `--stage finish`

3. **finish（仕上げ）**

   ```bash
   python .claude/skills/weekly-pipeline/scripts/run_weekly.py --stage finish
   ```

   - `check_article.py` を記事に対して実行し、`RESULT: ERROR` が1件以上あれば exit 1 で止まる。直して再実行する
   - `analyze_monthly_setlist.py --months <対象月>`（期間が月をまたぐ場合は両方）でセトリ集計を更新する
   - `sync_x_data.py push` で `work/x_fetch/` を非公開リポジトリへ退避する
   - `.claude/skills/article-refresh/scripts/check_stale.py` が**存在すれば**実行する（無ければスキップ。別作業で作る予定）
   - 最後に「README とコミットは手作業」と表示する。`articles/週刊まとめ/README.md` の更新は
     `.claude/skills/session-handoff` の書き方に従う

## 件数の読み方（3段階）

2026-09-01 に「え、5件しか見つけられなかったの？」という誤解が起きた。**候補と採用は別の数字**なので、
`collect` と `material` はどちらも次の3段階を必ず表示する。

1. **生データ**: `fetch_egosearch.py` が取得した全件（`work/x_fetch/egosearch_<since>_<until>.jsonl` の行数）
2. **候補**: 公式・メンバー本人の投稿を除外した後の件数（`egosearch_candidates_*.md` の「合計」）
3. **採用**: `collect` の時点ではまだ機械仕分けの内訳（採用候補・要判定・除外候補）で、要判定は
   Claude が判定を書くまで未確定。`material` を通した後は `triage_egosearch.py --decisions` が出す最終の採用数

## 注意

- API 呼び出し（`fetch_accounts.py` / `fetch_egosearch.py`）には費用がかかる。`--dry-run` でコマンド列だけ
  確認してから実行する。クレジットの購入・自動チャージ登録は承認なしに行わない（既存スキルと同じ）
- `--refresh` は本番の `work/x_fetch/*.jsonl` を書き換える。実行前に表示される鮮度と、
  削除後にできる `work/x_fetch_bak_<日付>/` を確認する。誤って消したら同じ日付のバックアップから戻す
- リモート環境（信頼モード）では twitterapi.io に 403 で到達できないことがある
  （`.claude/skills/x-account-fetch/SKILL.md` と同じ制約）。フルアクセス環境で実行する
- 各段階は他スキルのスクリプトをそのまま `subprocess` で呼ぶだけで、判断（判定ファイルを書く・記事を書く・
  資料を直す）は代行しない。表示された「次にやること」を人（またはClaude）が行ってから次の `--stage` に進む
