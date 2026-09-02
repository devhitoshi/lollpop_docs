---
name: article-review
description: note 記事（articles/ 配下）を公開・マージする前にレビューする。機械チェック（note の制約、曲名・グループ名の表記、メンバーの担当カラー、期間内の公演の抜け、文体ルール）と、読み取り専用エージェント article-review による読解レビューの2段構え。記事を書き終えたとき、「記事をチェックして」「レビューして」「公開前に見て」と言われたとき、記事系の PR を作る前に必ず使う。
---

# 記事レビュー

記事の手戻りで多いのは「公演の抜け」「公演数の誤り」「表記ゆれ」「文体の崩れ」。
どれも資料と突き合わせれば機械的に見つかるので、公開前に必ず通す。

## 手順

1. **機械チェック**（数秒。まずこれ）

   ```bash
   python3 .claude/skills/article-review/scripts/check_article.py articles/週刊まとめ/YYYY-MM-DD_YYYY-MM-DD.md
   ```

   種別（weekly / monthly / lyrics）はパスから判定する。違う場所にある記事は `--type monthly` のように指定する。
   ERROR は直す。WARN / INFO は次の読解レビューで判断する。

2. **読解レビュー**（エージェントに任せる）

   Agent ツールで `subagent_type: article-review` を起動し、記事のパスを渡す。
   エージェントは読み取り専用で、「必須修正」「推奨」「確認したが問題なし」「資料側の課題」に分けたレポートを返す。

3. **直す**

   必須修正を記事に反映する。「資料側の課題」（楽曲一覧に無い曲、CSV に無い公演など）は記事ではなく資料を直し、
   直したら機械チェックを再実行して ERROR が消えたことを確認する。

4. **編集メモに残す**

   判断に迷って残した WARN（例: イベント名の「!!」は表記ママ）は、記事末尾の編集メモに1行書いておく。次に読む人が同じ検討を繰り返さないため。

## 機械チェックが見るもの

| コード | 内容 | 根拠 |
| --- | --- | --- |
| NOTE_TABLE / NOTE_HEADING | 表組み、3階層以上の見出し | note の制約（週刊 README） |
| GROUP_NAME | 「ろりぽっぷ」の「!」が7個でない | CLAUDE.md 表記ルール |
| EXCLAMATION / KAOMOJI / OTAKU_WORDS | 「!」の連打、顔文字、オタク語彙の回数 | style_ai_poppar.md |
| MEMBER_EMOJI / NICKNAME_FIRST | 担当カラーの絵文字違い、月刊で愛称の初出に本名が無い | members.md / monthly.md |
| GRADUATED / SENSITIVE / SPECULATION | 卒業メンバー・数字・運営・体調・推測表現への言及（要判断） | style_ai_poppar.md / CLAUDE.md |
| SONG_NOTATION | 同じ曲の表記が記事内で揺れている、楽曲一覧との違い | songs/楽曲一覧.md |
| MISSING_EVENT / DATE_NOT_IN_CSV / EVENT_COUNT | CSV にある公演が記事に無い、記事の公演数が CSV と違う | events/data_event.csv |
| JARGON / PARAGRAPH / SOURCES / MEMO | 月刊の注釈、段落の長さ、出典節、編集メモ | monthly.md / style / articles README |

引用（「」『』）と URL の中は文体チェックの対象外にしている。メンバーの発言の引用に「？？？」があっても指摘しない。

## 注意

- 楽曲一覧と表記が違うだけなら誤りではない（記事は投稿の表記ママが原則）。同じ記事内で揺れている場合だけ直す
- スクリプトは記事を変更しない。エージェントも変更しない。直すのは呼び出し側
- 新曲を楽曲一覧に足すときは `songs/楽曲一覧.md` の箇条書き（`- **曲名**`）に追加すると、集計とチェックの両方に効く
