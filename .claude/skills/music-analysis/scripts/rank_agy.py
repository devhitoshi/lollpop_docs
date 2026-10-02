#!/usr/bin/env python3
"""Antigravity（agy CLI）に全曲をまとめて聴き比べさせ、軸ごとの相対的な位置を小数で返させる。

1 曲ずつの採点（listen_agy.py）は 7 段階で点が重なり、しかも 1 回だけでは外すことがある。
聴き比べの採点を 2 回目として取り、食い違った曲をオーナーに確認してもらう。
結果は songs/analysis/character/raw/_ranking.json。**オーナーが確認するまでは未確認の生データ。**

    python3 .claude/skills/music-analysis/scripts/rank_agy.py
"""

import json
import re
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from listen_agy import RAW_DIR, ask_agy, audio_files, fail, refuse_api_key, to_blind_mp3  # noqa: E402

PROMPT = """ワークスペースに track01.mp3 〜 track{n:02d}.mp3 があります。同じ日本のアイドルグループの楽曲 {n} 曲で、曲名と歌詞は伏せています。
全曲を音として直接聴き、**曲どうしを聴き比べて**、次の軸の上に並べてください。

守ってほしいこと:
- 歌詞の意味を判断に使わない（メロディ、和音の響き、音色、リズム、歌い方で判断する）。
- 同じグループの中での相対的な位置を知りたいので、{n} 曲が軸の上で広がるように付ける。本当に区別がつかない場合を除き、同じ値を付けない。
- ファイルの作成・変更、パッケージのインストールはしない。全曲を聴けなかった場合は、聴けなかった曲を unheard に挙げ、その曲には値を付けない。

軸（-3.0〜+3.0、小数 1 桁）:
- cute_cool: -3 かわいい 〜 +3 かっこいい
- waki_emo: -3 湧き（客席が声を出して騒ぐ） 〜 +3 エモい（聴き入る・胸にくる）
- bright_dark: -3 明るい 〜 +3 暗い

tempo_rank は、体感の速さの順位です（1 がいちばんゆったり、{n} がいちばん速い）。
note には、その曲を他の曲と区別する音の特徴を 1 文で書いてください。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "tracks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file": {"type": "string"},
                    "cute_cool": {"type": "number"},
                    "waki_emo": {"type": "number"},
                    "bright_dark": {"type": "number"},
                    "tempo_rank": {"type": "integer"},
                    "note": {"type": "string"},
                },
                "required": ["file", "cute_cool", "waki_emo", "bright_dark", "tempo_rank", "note"],
            },
        },
        "unheard": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["tracks", "unheard"],
}


def main():
    refuse_api_key()
    files = audio_files()
    if not files:
        fail("audio/ に音源がありません。")

    with tempfile.TemporaryDirectory() as tmp:
        for i, path in enumerate(files, start=1):
            to_blind_mp3(path, Path(tmp) / f"track{i:02d}.mp3")
        # 12 曲で 3 分ほどかかった。Bash ツールから呼ぶときは裏で実行する。
        data, res, err = ask_agy(tmp, PROMPT.format(n=len(files)), SCHEMA, timeout="1500s")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    if res:
        # 採点に枠を使っているので、解釈に失敗しても応答そのものは必ず残す。
        (RAW_DIR / "_ranking_response.json").write_text(
            json.dumps(res, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline=""
        )
    if err:
        fail(err)

    for track in data["tracks"]:
        # "track01.mp3" から番号を取る。数字を全部拾うと「mp3」の 3 まで入る。
        track["song"] = files[int(re.search(r"track(\d+)", track["file"]).group(1)) - 1].stem
    data["_meta"] = {"conversation_id": res.get("conversation_id"), "usage": res.get("usage")}
    (RAW_DIR / "_ranking.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
    (RAW_DIR / "_ranking_response.json").unlink()

    print("聴けなかった曲:", data["unheard"] or "なし")
    for track in sorted(data["tracks"], key=lambda t: t["cute_cool"]):
        print(f"{track['song']}\t{track['cute_cool']:+.1f}\t{track['waki_emo']:+.1f}\t速さ{track['tempo_rank']}\t{track['note']}")


if __name__ == "__main__":
    main()
