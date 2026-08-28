# 収集の作業場所

`.agent/scripts/prepare_collect.py` が生成した、Grok に貼るためのプロンプトを置いています。
**生成物なので、いつでも作り直せます。**

```
work/collect/<期間>/<チャンク>/
├── x_collect.md      … Grok に貼る（生成物）
├── chunk.json        … 期間などのメタ情報（生成物）
├── response.md       … Grok の出力をここに保存する ←★
└── response.csv      … event_get.md の出力があればここに ←★
```

## 手順

1. `x_collect.md` の全文を Grok に貼る
   - **1チャンク＝1新規チャット**。前の指示を引きずらせない
   - モデルは**「エキスパート」**（「ファスト」では X 検索が浅い）
   - `style_ai_poppar.md` や `write_*.md` は渡さない
2. 返ってきた本文を、同じディレクトリに `response.md` として**出力形式の見出しごとそのまま**保存する
3. 結合する
   ```bash
   python3 .agent/scripts/merge_collect.py --period <期間>
   ```
   「出力が途中で切れている可能性」が出たチャンクは取り直す
4. 原本を積み上げる
   ```bash
   python3 .agent/scripts/archive_collect.py --period <期間> --ingest-only
   ```
   並行して別セッションを走らせているなら `--ingest-only` を必ず付ける。
   全期間が揃ってから、1つのブランチで `--rebuild` を1回。

詳しくは `skills/note_article/SKILL.md`。

## いま置いてある期間

| 期間 | チャンク | 用途 |
|---|---|---|
| `20260810-20260816` | 1 | 先々週（週刊） |
| `20260817-20260823` | 1 | 先週（週刊） |
| `20260701-20260731` | 2（前半・後半） | 2026年7月分（月刊） |

いずれも `--no-population` で生成しているので `event_get.md` はありません。
`data_event.csv` の収集は別セッションで進めているためです。
セトリCSVもここで取るなら、母集団を付けて作り直してください。

```bash
python3 .agent/scripts/prepare_collect.py --month 2026-07
```
