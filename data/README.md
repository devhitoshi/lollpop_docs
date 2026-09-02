# data/ — 機械が読み書きする成果物の置き場

`work/` と違い、**ここは追跡する**。他人の投稿の原文は置かない（それは `work/x_fetch/` と非公開の `lollpop_data` リポジトリ）。

| パス | 内容 | 作るもの |
| --- | --- | --- |
| `x/egosearch_decisions_<since>_<until>.txt` | エゴサーチ候補の判定（投稿ID と採用/除外）。生データを取り直しても再判定しなくて済む | `.claude/skills/x-egosearch` |
| `x/egosearch_<since>_<until>_reactions.md` | 判定済みの反応の要約（要旨・短い引用・URL）。記事と定点観測が読む | 同上（Claude が書く） |
| `x/egosearch_triage_<since>_<until>_summary.txt` | 採用・除外の件数、日別件数 | 同上（triage が書く） |

生データ（`work/x_fetch/*.jsonl`）の退避と復元は `.claude/skills/x-data-sync`。

## X データの流れ（収集 → 保管）

どのスキルが何をどこへ書くか。**生データ（他人の投稿の原文）と、自分の成果物（判定・要約）を分けて置く**のが原則。

```
 セッション開始
   └─ 起動時 hook（.claude/hooks/session_start.sh）
        └─ x-data-sync pull : lollpop_data/x/*.jsonl.gz → work/x_fetch/*.jsonl（復元）

 取得（費用がかかる。復元してから実行する）
   ├─ x-account-fetch  : 公式・メンバーの投稿      → work/x_fetch/<handle>.jsonl
   └─ x-egosearch      : 周囲の反応（エゴサーチ）  → work/x_fetch/egosearch_<期間>.jsonl

 判定（人＝Claude の仕事。ここがいちばん高くつくので必ず残す）
   └─ x-egosearch の triage → work/x_fetch/..._adopt.txt / _review.txt を読む
        ├─ 判定   → data/x/egosearch_decisions_<期間>.txt   （追跡・再判定を防ぐ）
        ├─ 集計   → data/x/egosearch_triage_<期間>_summary.txt（追跡）
        └─ 要約   → data/x/egosearch_<期間>_reactions.md      （追跡・記事と定点観測が読む）

 利用（同じデータを読む）
   ├─ weekly-monthly-draft   : 記事の素材（work/x_fetch/draft_material_*.md、コミットしない）
   ├─ strategy-metrics       : UGC 件数・公式の発信量 → strategy/metrics_<日付>.md
   ├─ member-profile-refresh : 投稿統計 → members/*.md の更新根拠
   ├─ setlist-analysis       : 公式のセトリ投稿と events/data_event.csv の突き合わせ
   └─ x-media-collect        : 縦型動画の素材（画像・動画）
        ├─ build_media_index → data/x/media_index_<期間>.csv（追跡。URL と寸法だけ）
        └─ fetch_media       → work/x_media/（許諾済みのみ。コミットしない）
             ├─ 許諾の判断は data/x/media_permissions.md の「OK」の行だけ
             └─ manifest.csv に出典が残る（クレジット表記に使う）

 セッション終了（session-handoff の手順）
   ├─ x-data-sync push : work/x_fetch/*.jsonl → lollpop_data/x/*.jsonl.gz（項目を絞って圧縮・commit・push）
   └─ data/x/ と記事・README を lollpop_docs にコミット
```

守る優先順位は **判定 > 生データ**。生データは取り直せる（8月分で約 $0.5・30分）が、
1,700件を読んで採用・除外を決める作業は繰り返したくない。判定ファイルがあれば triage が自動で再適用する。

置き場を間違えないための一言:

- `work/x_fetch/` … 他人の投稿の原文。追跡しない。消えてよい（退避先から戻る）
- `data/x/` … 自分が書いた判定・件数・要約。追跡する。**他人の投稿の原文は置かない**
- `lollpop_data`（非公開リポジトリ）… 生データの圧縮版。公開しない・再配布しない
- `work/x_media/` … 許諾済みで落とした画像・動画。追跡しない・退避もしない（索引から落とし直せる）

### 通し検証（2026-09-02）

`work/` を丸ごと消してから、起動時 hook → triage → 索引 → ダウンロードを順に流し、
**索引の md5 が消す前と一致**することを確認済み。判定（349件の採用）も `data/x/` の判定ファイルから復元できる。
