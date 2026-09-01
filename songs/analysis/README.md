# 曲調データ

各曲の音の側のデータです。`songs/lyrics/` の歌詞と対になります。

`audio/` に置いた音源を
[`.claude/skills/music-analysis/scripts/analyze_audio.py`](../../.claude/skills/music-analysis/scripts/analyze_audio.py)
で解析した結果で、**手書きではなく自動生成**です。

## ファイル

| パス | 内容 |
| --- | --- |
| `[曲名].md` | 1曲分。BPM・キー・セクション構成・音量推移 |
| `../../work/song_features.csv` | 全曲比較用。BPM・キー・尺・ダイナミクスレンジ |

## 作り方

```bash
python3 .claude/skills/music-analysis/scripts/analyze_audio.py --all
```

詳しい手順は [`.claude/skills/music-analysis/SKILL.md`](../../.claude/skills/music-analysis/SKILL.md) にあります。

## 読むときの注意

- **BPM は倍・半分に振れることがある**（168 と 84 など）。
- **キーは平行調と入れ替わることがある**（A minor の曲が C major と出る）。
- **セクション境界は楽曲構成の正解ではない**。音色と和音の変化から機械的に割ったもので、
  Aメロ・サビといった名前は付いていない。`songs/lyrics/[曲名].md` の構成と
  時間順に突き合わせて読む。

考察記事で数値に触れるときは、断定を避けるか耳で確かめてから書いてください。
