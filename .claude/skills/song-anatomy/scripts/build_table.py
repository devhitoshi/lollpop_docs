#!/usr/bin/env python3
"""歌割り表（行ごとの時刻と、誰が歌っているかの空欄）を作る。

    python build_table.py シーソーゲーム

歌詞の原文は載せず、行の頭の数文字と歌詞ファイルの行番号で示す。
"""
import sys
import build_anatomy as fig
import common

song = sys.argv[1]
a = fig.load(song)
out = [
    f"# {song} 歌割り表（試作）",
    "",
    "機械が出した行ごとの時刻です。**「誰が歌っているか」はオーナーが埋める欄**で、機械は当てていません。",
    f"行番号は `songs/lyrics/{song}.md` の行番号。歌詞は頭の 6 文字だけ載せています。",
    "「声の広がり」は左右にどれだけ広がって聞こえるかの値（実験）。小さい行はソロ、大きい行は全員の可能性がありますが、未確認です。",
    "",
    "| 構成 | 始まり | 終わり | 行番号 | 歌詞の頭 | 声の広がり | 誰が歌っているか |",
    "| --- | --- | --- | --- | --- | --- | --- |",
]
t = lambda s: f"{int(s // 60)}:{s % 60:04.1f}"
for l in a["lines"]:
    w = "—" if l["vocal_width"] is None else f"{l['vocal_width']:.2f}"
    out.append(f"| {l['section']} | {t(l['start'])} | {t(l['end'])} | {l['line_no']} | {l['head']}… | {w} | {l.get('singer') or ''} |")
(common.data_dir(song) / "歌割り表.md").write_text("\n".join(out) + "\n", encoding="utf-8", newline="")
print("書き出し:", common.data_dir(song) / "歌割り表.md", len(a["lines"]), "行")
