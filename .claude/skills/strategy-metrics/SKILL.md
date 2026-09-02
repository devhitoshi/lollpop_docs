---
name: strategy-metrics
description: 「ろりぽっぷ!!!!!!!」の成長戦略の定点観測（フォロワー数・競合比較・UGC量・公式の発信量・初見反応）を twitterapi.io で取得し、strategy/metrics_YYYY-MM-DD.md を前回比付きで作る。prompts/collect/strategy_metrics.md（Grok 用）の API 版。「定点観測」「KPI を更新」「フォロワー数を調べて」「競合と比べて」「四半期の計測」と言われたとき、growth_strategy.md の KPI 表を更新するときに使う。
---

# 戦略の定点観測（API 版）

`strategy/growth_strategy.md` の KPI 表を、同じ物差しで定期的に更新するための手順。
Grok 版（`prompts/collect/strategy_metrics.md`）は検索が1クエリ10件で頭打ちになり UGC が「下限値」にしかならなかった。
API 版はフォロワー数と公式の発信量を確定値で取り、UGC は x-egosearch の全件取得＋Claude の判定に置き換える。

## 前提

- `TWITTERAPI_IO_KEY` と twitterapi.io に到達できる環境（信頼モードのリモート環境では 403）
- 費用は小さい（プロフィール11件＋公式の直近30日≒100件で 2,000 クレジット程度）。UGC 側は x-egosearch の費用
- **クレジットの購入・自動チャージ登録は承認なしに行わない**

## 手順

1. **UGC を先に集めて判定する**（x-egosearch）

   ```bash
   python3 .claude/skills/x-egosearch/scripts/fetch_egosearch.py --since <30日前> --until <基準日> --max-tweets-per-query 1500 --yes
   ```

   候補を読んで判定し、`data/x/egosearch_<since>_<until>_reactions.md` を作る（x-egosearch の手順3〜4）。
   先頭に「採用 N 件／除外 M 件」の行を必ず書く（このスキルがそこを読む）。初見らしき投稿には要旨に「初見」の語を残す。
   時間が無ければこの手順を飛ばしてもよい。その場合 UGC は「未判定の上限値」として出る。

2. **計測して下書きを作る**

   ```bash
   python3 .claude/skills/strategy-metrics/scripts/collect_metrics.py --days 30
   ```

   `strategy/metrics_<基準日>.md` ができる。前回の `strategy/metrics_*.md`（最新）を読んでフォロワー数の前回比を付ける。
   競合のハンドルが変わって取得できなかった場合はメモ欄に「取得失敗」と出るので、グループ名で検索して `BENCHMARKS` を直す。

3. **確認して仕上げる**

   - 「確認できなかった項目」「判断に迷った点」を埋める（書くことが無ければ「なし」）
   - 数値には「いつ時点か」が付いていることを確認する（計測時刻は自動で入る）
   - 評価語（「伸びている」「好調」）は書かない。数字と出典だけ

4. **戦略文書に反映する**

   `strategy/growth_strategy.md` の KPI 表（2.2「外から見える数字」）と「最終更新」を更新し、`strategy/metrics_<基準日>.md` へのリンクを付ける。
   競合の数字を更新するときも、評価や優劣の表現は書かない（web-research と同じ規律）。

## 頻度

四半期に1回が既定（growth_strategy.md の方針）。月刊まとめを書くタイミングで月次に回してもよいが、その場合も戦略文書の更新は四半期ごとにまとめる。

## 出力の形式

Grok 版の出力形式（`prompts/collect/strategy_metrics.md` の「出力形式」）と同じ見出しに「前回比」列を足したもの。
既存の `strategy/metrics_2026-09-01.md`（第1回・Grok＋API 追記）と並べて読める。
