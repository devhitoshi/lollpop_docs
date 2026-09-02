---
name: x-egosearch
description: 「ろりぽっぷ!!!!!!!」への周囲の反応（エゴサーチ）を twitterapi.io で期間指定・全件集め、Claude がノイズを判定して「外部の反応」「現場の反応」の素材にする。prompts/collect/x_collect.md の「2. 周囲の反応を取得」を Grok の代わりに実行するもの。「エゴサして」「反応を集めて」「現場の反応」「外からの反応」「UGC を数えて」と言われたとき、週刊・月刊・定点観測で周囲の反応が要るときに使う。公式・メンバー本人の投稿は x-account-fetch の担当。
---

# エゴサーチ（周囲の反応）

Grok でやっていた `x_collect.md` の手順2を、API で「漏れなく集める」＋Claude が「読んで判定する」の二段に分けた。
検索エンジンは文脈を判断できないので、レンタルサーバー「ロリポップ!」やゲームの投稿が混ざる。**判定は必ず Claude が本文を読んで行う。**

## 前提

- `TWITTERAPI_IO_KEY`（環境変数または `.env`）と、twitterapi.io に到達できる環境（信頼モードのリモート環境では 403）
- 残高の確認: `curl -s -H "x-api-key: $TWITTERAPI_IO_KEY" https://api.twitterapi.io/oapi/my/info`。1,000ツイート＝15,000クレジット（$0.15）
- **クレジットの購入・自動チャージ登録は承認なしに行わない**（x-account-fetch と同じ）

## 手順

1. **集める**

   ```bash
   python3 .claude/skills/x-egosearch/scripts/fetch_egosearch.py \
     --since 2026-08-01 --until 2026-08-31 --max-tweets-per-query 1500 --yes
   ```

   - `--since/--until` はその日を含む（build_material.py と同じ。x-account-fetch だけが「翌日」指定）
   - `--dry-run` でクエリだけ確認できる。`--max-tweets-per-query` は必須（暴走防止）
   - 1クエリ1,500件の上限で全体 10分〜20分かかる（0.2 QPS）。**必ずバックグラウンドで動かし、ログを見る**:
     `nohup python3 ... > work/x_fetch/egosearch_run.log 2>&1 &`
   - 中断しても進捗（`*.progress.json`）とカーソルが残るので、同じコマンドで続きから再開できる
   - 出力: `work/x_fetch/egosearch_<since>_<until>.jsonl`（生データ）と `egosearch_candidates_<since>_<until>.md`（判定用の候補リスト）

2. **クエリの中身**（`x_collect.md` の 2-1〜2-4）

   | ラベル | 内容 | 備考 |
   | --- | --- | --- |
   | 2-1 基本形 | ろりぽっぷ／#ろりぽっぷ／ろりぽ／@lollipop_1116 | 一番多い。学校名・個人名のノイズあり |
   | 2-2 カタカナ・英字 | ロリポップ／ロリポ／lollipop ＋ アイドル文脈の語 | サーバー「ロリポップ!」が混ざる |
   | 2-3 メンバー名 | 本名・愛称・ハンドル | 「まう」は一般語なので入れていない |
   | 2-4 固有名詞 | 期間内の新曲（🆕）、メンバー名・生誕・単独・主催を含むイベント名 | `--terms` で追加。対バン・フェス名は `--all-event-terms` のときだけ |

   対バン・フェスの名前で検索すると出演者全員のファンの投稿が数百件当たる（TOKYO GIRLS GIRLS で500件超）。
   ろりぽっぷへの反応はほぼ 2-1/2-3 に含まれるので、既定では入れない。
   `-from:` 除外は API 側で信用できないため、公式・メンバー（卒業含む）の投稿は取得後にハンドルで除外している。

3. **判定する**（Claude の仕事）

   まず機械仕分けで読む量を減らす:

   ```bash
   python3 .claude/skills/x-egosearch/scripts/triage_egosearch.py --since <since> --until <until>
   ```

   `work/x_fetch/egosearch_triage_*_adopt.txt`（強い手がかりあり）と `_review.txt`（要判定）を読み、判定を
   `data/x/egosearch_decisions_<since>_<until>.txt` に「<id> adopt|reject メモ」で書く。要判定のうち書かなかったものは除外になる。
   もう一度 triage を実行すると判定が反映され、採用リスト・反応上位・件数（`data/x/..._summary.txt`）が出る。
   判定ファイルは追跡するので、生データを取り直しても再判定は要らない。

   採用・除外の基準:

   - 採用: アイドルグループ「ろりぽっぷ!!!!!!!」（メンバー・曲・ライブ・特典会）について書かれた、公式・メンバー以外の投稿
   - 除外: サーバー、ゲーム、菓子、同名の学校・店・個人、別の「ろりぽっぷ」（名古屋の同名アイドルなど）、出演者一覧を並べただけの主催告知（ろりぽっぷへの言及が名前だけのもの）
   - 迷ったら除外（`x_collect.md` の「判断がつかないものは採用しない」）
   - [ノイズ候補] の印はヒントに過ぎない。付いていても本文で判断する

4. **素材にまとめる**

   `data/x/egosearch_<since>_<until>_reactions.md`（追跡ディレクトリ）に、`x_collect.md` の「外部の反応」の形式で書く:
   `- [投稿者名]（@handle）／[YYYY-MM-DD]／[何に対して・どう反応したか（1〜2文の要旨）]／[いいね・表示]／出典: URL`

   - 他人の投稿は**要旨**にする。原文の長文転載はしない（記事でも同じ）
   - 伸びているもの、現場の声、共演者・主催の言及、初見の感想を優先し、10〜20件（週刊は3〜6件）
   - 件数の集計（採用数／除外数／期間）を先頭に書く。定点観測（strategy-metrics）の UGC 量にそのまま使う
   - 記事に使うときは `weekly-monthly-draft` の素材ファイルの「## 外部の反応」に貼る

5. **記事に反映したら**

   各シリーズ README の未解決から「エゴサーチ待ち」を消し（取り消し線＋日付）、記事の出典に URL を足す。

## データの保存先

- 生データ（`work/x_fetch/*.jsonl`）はコミットしない。セッションの終わりに `.claude/skills/x-data-sync` で非公開リポジトリへ退避する
- 判定・件数・要約（`data/x/`）は lollpop_docs にコミットする

## 規約・法務

サードパーティ経由の取得は X の規約との関係がグレー。個人の分析・記事執筆の範囲を前提とする。
取得した投稿は他人の著作物。`work/x_fetch/` は `.gitignore` 済みで、**コミットしない・再配布しない**。
記事には要旨と URL だけを載せる。
