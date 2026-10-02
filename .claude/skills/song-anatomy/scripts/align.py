#!/usr/bin/env python3
"""分離したボーカルに歌詞を時刻合わせする（stable-ts の align）。

    .venv/Scripts/python align.py シーソーゲーム [--model medium]

結果は work/anatomy/<曲名>/alignment_raw.json（リポジトリには入らない）。
extract.py がこれを読み、原文を落として行番号と文字位置だけにしたものを anatomy.json に入れる。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

import stable_whisper

from common import read_lyrics, stems_dir, work_dir



def realign(args, lines: list[dict]) -> None:
    """時刻合わせが外れた行だけを、時間の範囲を決めてやり直す。

        align.py <曲名> --lines 35 40 --window 99 114.1

    --lines は歌詞ファイルの行番号（この範囲の行をやり直す）、--window はその行が入っているはずの秒の範囲。
    範囲は人が決める（ボーカルが鳴っている区間などから）。やり直した行には realigned_window を残す。
    """
    out = work_dir(args.song) / "alignment_raw.json"
    payload = json.loads(out.read_text(encoding="utf-8"))
    idx = [i for i, l in enumerate(lines) if args.lines[0] <= l["line_no"] <= args.lines[1]]
    t0, t1 = args.window
    with tempfile.TemporaryDirectory() as tmp:
        clip = Path(tmp) / "clip.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t0), "-to", str(t1), "-i", str(stems_dir(args.song) / "vocals.wav"), str(clip)], check=True)
        model = stable_whisper.load_model(args.model)
        result = model.align(str(clip), "\n".join(lines[i]["text"] for i in idx), language="ja", original_split=True)
    if len(result.segments) != len(idx):
        raise SystemExit(f"行 {len(idx)} に対して区間 {len(result.segments)}")
    for i, seg in zip(idx, result.segments):
        payload["segments"][i] = {
            "text": seg.text,
            "start": seg.start + t0,
            "end": seg.end + t0,
            "words": [{"word": w.word, "start": w.start + t0, "end": w.end + t0, "probability": w.probability} for w in seg.words],
            "realigned_window": [t0, t1],
        }
        print(f"{seg.start + t0:7.2f} {seg.end + t0:7.2f}  {seg.text}")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8", newline="")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("--model", default="medium")
    ap.add_argument("--lines", nargs=2, type=int)
    ap.add_argument("--window", nargs=2, type=float)
    args = ap.parse_args()

    lines = read_lyrics(args.song)
    if args.lines:
        return realign(args, lines)
    text = "\n".join(l["text"] for l in lines)
    model = stable_whisper.load_model(args.model)
    result = model.align(str(stems_dir(args.song) / "vocals.wav"), text, language="ja", original_split=True)

    out = work_dir(args.song)
    segments = [
        {
            "text": seg.text,
            "start": seg.start,
            "end": seg.end,
            "words": [{"word": w.word, "start": w.start, "end": w.end, "probability": w.probability} for w in seg.words],
        }
        for seg in result.segments
    ]
    payload = {"model": args.model, "stable_ts": stable_whisper.__version__, "n_lyric_lines": len(lines), "segments": segments}
    (out / "alignment_raw.json").write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8", newline="")
    print(f"歌詞 {len(lines)} 行 → 区間 {len(segments)} 個")
    for seg in segments:
        print(f"{seg['start']:7.2f} {seg['end']:7.2f}  {seg['text']}")


if __name__ == "__main__":
    main()
