---
name: music-analysis
description: 「ろりぽっぷ!!!!!!!」の楽曲がどんな曲かを調べる。audio/ に置いた音源を AI（Antigravity）に聴かせて、かわいい↔かっこいい・湧き↔エモいの位置と歌詞との離れ具合を出し、オーナーの確認を経て songs/analysis/ に保存する。尺・BPM・キーなどの数値も出す（BPM とキーは参考値）。曲調の分析、「どんな曲か」の説明、新曲を曲の位置の図に足したいとき、歌詞考察に曲調の観点を足したいときに使う。
---

# 曲調データの作成・管理

歌詞（`songs/lyrics/`）と対になる、音の側のデータを作る。
歌詞考察記事（`articles/歌詞考察/`）で曲調に触れるための材料になる。

**ゴールは「どんな曲かを説明できること」**（かわいいのか・かっこいいのか、湧き曲か・エモい曲か、歌詞と音が合っているか）。
BPM やキーの数値を確定させることではない（2026-10-01 にやってみて、数値は確定できず、印象の説明にも届かなかった）。

## 前提

- 音源が `audio/` にあること。入手方法は [`audio/README.md`](../../../audio/README.md) を参照。
  音源が無い場合は、ユーザーに購入をお願いする以外に進める道はない。**推測で書かない。**
- Antigravity の `agy` CLI が使えること（ユーザースキル `agy-ask` を先に読む。残量の確認は PowerShell から）。
  **Gemini は Antigravity（サブスク枠）経由でだけ使う。従量課金の Gemini API は使わない**（オーナー決定・2026-10-01）。
- 数値も出すなら librosa が要る。

  ```bash
  python3 -m pip install -r .claude/skills/music-analysis/scripts/requirements.txt
  ```

## 手順 A: 曲の印象（主）

Claude は音を聴けないので、Antigravity に聴かせる。**AI は 1 回だけだと外すので、2 回聴かせて、食い違った所だけオーナーに聞く。**

1. **1 曲ずつ聴かせる**（1 曲 1〜4 分。12 曲で 20 分ほどかかるので、Bash ツールからは裏で実行する）

   ```bash
   python3 .claude/skills/music-analysis/scripts/listen_agy.py --all
   ```

   曲名を伏せて渡し、歌詞の意味を採点に使わせない（歌詞との相性を別に比べるため）。済んだ曲は飛ばす。

2. **全曲を聴き比べさせる**（12 曲で 3 分ほど）

   ```bash
   python3 .claude/skills/music-analysis/scripts/rank_agy.py
   ```

   曲の位置は全曲の中での相対的なものなので、**新曲を足すときもこれは全曲で取り直す**。

3. **歌詞の側を採点する**

   `songs/lyrics/[曲名].md` を読み、同じ軸で `songs/analysis/character/lyrics_scores.json` に採点と根拠を書く
   （既存の曲の根拠の書き方に合わせる）。これは Claude が読んで付ける。

4. **一覧と図を作る**

   ```bash
   python3 .claude/skills/music-analysis/scripts/build_character.py
   ```

   `songs/analysis/song_character.md`・`song_character.csv` と、確認用の図 `work/charts/song_character.html` ができる。
   「オーナーの確認が要る曲」が表示されたら、次へ。

5. **食い違った曲をオーナーに聞く**

   2 回の採点が 1.5 以上離れた曲と、位置は近くても説明の中身（楽器・テンポ感）が食い違う曲は、
   `character/raw/` の 2 つの説明を並べて「どちらが近いか」を聞く。
   **1 曲につき、1 回目の説明と 2 回目の説明を 1 行ずつの表にする**（オーナーは「1 回目」「2 回目」「どちらも」と答えるだけでよい）。
   答えを `character/owner_check.json` に書き、4 をやり直す。

   ```json
   "主人公": {"trust": "rank", "confirmed": "ピアノとストリングスが主役、ゆったりめ", "rejected": "歪んだギターの高速ビート"}
   ```

   - `trust`: `solo`（1 曲ずつの回が近い）／`rank`（聴き比べの回が近い）／`both`
   - `confirmed`: 合っていた説明。記事に書いてよい言葉になる
   - `rejected`: 外した説明。同じ説明が再び出ても採用しない
   - `owner_comment`: オーナー自身の言葉
   - `override`: オーナーの言葉に合わせて位置を手で動かすとき（例: `{"cute_cool": 2.6}`）

6. **結果を伝える**

   図（`work/charts/song_character.html`）と、音と歌詞が離れている曲を伝える。
   記事に書いてよい範囲は [`songs/analysis/README.md`](../../../songs/analysis/README.md) が正。

## 手順 B: 数値（補助）

```bash
python3 .claude/skills/music-analysis/scripts/analyze_audio.py --all
python3 .claude/skills/music-analysis/scripts/analyze_audio.py audio/主人公.m4a --sections 12
```

尺・BPM・キー・区間ごとの音量が `songs/analysis/[曲名].md` と `song_features.csv` に出る。
曲全体の音量は音圧で張り付いて展開が見えない。**楽器ごとの出入りや、歌詞の行ごとの時刻を見たいときは `.claude/skills/song-anatomy`**（音源を 4 つに分けて追う。読み解き図もそちら）。
**BPM とキーは参考値で、記事には書かない。**尺と、区間の大まかな並びだけが当てになる。

## 入出力

| パス | 役割 |
| --- | --- |
| `audio/[曲名].m4a` など | 入力。購入した音源（リポジトリには入らない） |
| `songs/lyrics/[曲名].md` | 入力。歌詞の採点に読む |
| `songs/analysis/character/raw/` | 中間。AI の採点の生データ（未確認の説明を含む） |
| `songs/analysis/character/owner_check.json` | 入力。オーナーの確認の記録 |
| `songs/analysis/character/lyrics_scores.json` | 入力。歌詞の採点 |
| `songs/analysis/song_character.md`・`.csv` | 出力。曲の印象の一覧 |
| `work/charts/song_character.html` | 出力。確認用の図（リポジトリには入らない） |
| `songs/analysis/[曲名].md`・`song_features.csv` | 出力。数値（BPM とキーは参考値） |

## やってみて分かったこと（2026-10-01）

- **AI は聴けるが、1 回では信用できない。** 12 曲中 8 曲で 2 回の採点か説明が食い違い、オーナーに聞いた結果、
  1 回目が近かったのが 4 曲、2 回目が 2 曲、どちらとも言えないのが 2 曲だった。**片方の回だけを信じる運用はできない。**
  オーナー自身も、いったん答えたあとで 1 曲を訂正している（約束!!!!!!!）。図にして見せてから、もう一度聞くとよい。
- **食い違う所が、そのまま怪しい所の目印になる。** 「シーソーゲームはラウドロック」「未完成ヒロインはバラード」は 2 回目だけが言い、どちらも誤りだった。
- **AI は全曲を「速い」「疾走感」と評しがち。** メンバーが「チルい」と書いた曲もアップテンポと評した。テンポ感の言葉は鵜呑みにしない。
- **歌詞の聞き取りは当てにならない**（歌い出しの言葉を間違える曲がある）。聴けているかの確認には使えるが、内容には使わない。
- **軸は 2 本で足りる。** 候補 6 本を採点させたら、「盛り上がる↔魅せる」は「湧き↔エモい」と（相関 0.85）、
  「明るい↔暗い」は「かわいい↔かっこいい」と（0.90）ほぼ同じ並びになり、「穏やか↔激しい」は全曲が激しい側だった。
- **librosa の数値は印象の説明に届かない。** BPM は倍・半分のほか 4:3・3:2 にも振れる。音圧が高く、区間ごとの音量差も出ない。
- **費用**: 12 曲を 1 曲ずつ＋聴き比べで、Antigravity の週の枠の 1〜2% ほど。

## 注意

- **`character/raw/` の説明を、オーナーの確認なしに記事へ書かない。**
- **音源ファイルを絶対にコミットしない。** `.gitignore` で除外済みだが、`git add -f` などで無理に追加しないこと。
  Antigravity に渡すために作る mp3 は一時フォルダに置き、終わると消える。
- `agy` を呼ぶ前に、環境変数に `GEMINI_API_KEY` / `ANTIGRAVITY_API_KEY` が無いことをスクリプトが確かめる
  （あると従量課金に倒れる）。止まったら、外さずにオーナーへ報告する。
- `rank_agy.py` は応答をいったん `_ranking_response.json` に残してから解釈する。解釈で落ちても、聴かせ直さずにそこから直す
  （Antigravity 側の記録 `~/.gemini/antigravity-cli/brain/<ID>/.system_generated/logs/transcript_full.jsonl` にも残る）。
- Windows では `PYTHONUTF8=1` を付けて実行する（曲名の出力が化けるのを防ぐ）。
- スクリプトは自分でリポジトリルートに `chdir` せず、`__file__` からの相対でパスを解決する。
  スクリプトを移動した場合は冒頭の `project_root` の階層数を直すこと。
