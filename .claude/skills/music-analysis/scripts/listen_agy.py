#!/usr/bin/env python3
"""Antigravity（agy CLI）に音源を 1 曲ずつ聴かせて、曲の印象を採点させる。

曲名は伏せる（trackNN.mp3 にして渡す）。歌詞の意味は採点に使わせない。
結果は songs/analysis/character/raw/[曲名]__runN.json に置く。**オーナーが確認するまでは未確認の生データ。**

Gemini は Antigravity（サブスク枠）経由でだけ使う。従量課金の Gemini API は使わない。

    python3 .claude/skills/music-analysis/scripts/listen_agy.py --all
    python3 .claude/skills/music-analysis/scripts/listen_agy.py --run 2 主人公
"""

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parents[4]

AUDIO_DIR = project_root / "audio"
RAW_DIR = project_root / "songs" / "analysis" / "character" / "raw"
AUDIO_SUFFIXES = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".mp3", ".m4a", ".aac", ".alac", ".wma", ".opus"}

AXES = {
    "cute_cool": "-3 かわいい 〜 +3 かっこいい",
    "moriagaru_miseru": "-3 客席と一緒に盛り上がる 〜 +3 ステージを見せる・魅せる",
    "waki_emo": "-3 湧き（声を出して騒ぐ） 〜 +3 エモい（聴き入る・胸にくる）",
    "pop_unique": "-3 王道のポップ 〜 +3 変わっている・ひねりがある",
    "bright_dark": "-3 明るい 〜 +3 暗い",
    "energy": "-3 穏やか 〜 +3 激しい",
}

PROMPT = """ワークスペースにある {name} は日本のアイドルグループの楽曲です。曲名と歌詞は伏せています。
この音声ファイルを音として直接聴いて、どんな曲かを答えてください。

守ってほしいこと:
- **歌詞の意味を採点や説明に使わない。** 歌詞との相性は別に比べるので、音だけの印象が必要です（メロディ、和音の響き、音色、リズム、歌い方で判断する）。
- 正確な BPM、調の名前、コード名は書かない。聴いて判断できないことは unsure に書く。
- ファイルの作成・変更、パッケージのインストールはしない。

各軸は -3〜+3 の整数で採点します。0 はどちらとも言えない、です。
{axes}

timeline には、音が大きく変わる時点（静かになる、楽器が増える・減る、雰囲気や調子が変わる、テンポ感が変わる）を時刻つきで書いてください。
first_words には、曲の最初に歌われる言葉を聞き取れた範囲で書いてください（聞き取れなければ空文字）。"""

SCHEMA = {
    "type": "object",
    "properties": {
        "first_words": {"type": "string"},
        "summary": {"type": "string", "description": "どんな曲かを2〜3文で"},
        "genre": {"type": "array", "items": {"type": "string"}},
        "instruments": {"type": "array", "items": {"type": "string"}},
        "vocal": {"type": "string"},
        "tempo_feel": {"type": "string", "enum": ["遅い", "やや遅い", "中くらい", "やや速い", "速い"]},
        "axes": {
            "type": "object",
            "properties": {k: {"type": "integer"} for k in AXES},
            "required": list(AXES),
        },
        "axes_reason": {
            "type": "object",
            "properties": {k: {"type": "string"} for k in AXES},
            "required": list(AXES),
        },
        "timeline": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"at": {"type": "string"}, "what": {"type": "string"}},
                "required": ["at", "what"],
            },
        },
        "unsure": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["first_words", "summary", "genre", "instruments", "vocal", "tempo_feel", "axes", "axes_reason", "timeline", "unsure"],
}


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def audio_files():
    return sorted(p for p in AUDIO_DIR.glob("*") if p.suffix.lower() in AUDIO_SUFFIXES)


def refuse_api_key():
    """環境変数に API キーがあると、agy はサブスク枠ではなく従量課金に倒れる。"""
    if os.environ.get("GEMINI_API_KEY") or os.environ.get("ANTIGRAVITY_API_KEY"):
        fail("GEMINI_API_KEY / ANTIGRAVITY_API_KEY が設定されています。課金に倒れるので中止します。")


def to_blind_mp3(src, dst):
    """曲名が分からないよう、メタデータを落とした mp3 にする。"""
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(src), "-map_metadata", "-1", "-b:a", "128k", str(dst)],
        check=True,
    )


def ask_agy(workdir, prompt, schema, timeout="280s"):
    """agy に投げて (応答の JSON, agy の返り値全体, エラー文) を返す。応答の生テキストは返り値全体に残る。"""
    schema_file = Path(workdir) / "schema.json"
    schema_file.write_text(json.dumps(schema, ensure_ascii=False), encoding="utf-8")
    proc = subprocess.run(
        ["agy", "--output-format", "json", "--print-timeout", timeout, "--add-dir", str(workdir), "--json-schema", str(schema_file), "-p", prompt],
        capture_output=True,
        cwd=workdir,
    )
    out = proc.stdout.decode("utf-8", "replace").strip()
    if not out:
        return None, None, f"出力なし: {proc.stderr.decode('utf-8', 'replace')[:300]}"
    res = json.loads(out[out.index("{"):])
    if res.get("status") != "SUCCESS" or not res.get("response"):
        return None, res, f"status={res.get('status')}: {str(res)[:300]}"
    text = res["response"].strip()
    try:
        return json.loads(text[text.index("{"): text.rindex("}") + 1]), res, None
    except ValueError:
        return None, res, f"JSON でない応答: {text[:300]}"


def listen(path, index, run):
    with tempfile.TemporaryDirectory() as tmp:
        name = f"track{index:02d}.mp3"
        to_blind_mp3(path, Path(tmp) / name)
        prompt = PROMPT.format(name=name, axes="\n".join(f"- {k}: {v}" for k, v in AXES.items()))
        data, res, err = ask_agy(tmp, prompt, SCHEMA)
    if err:
        return None, err
    data["_meta"] = {"conversation_id": res.get("conversation_id"), "usage": res.get("usage"), "run": run}
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    (RAW_DIR / f"{path.stem}__run{run}.json").write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline=""
    )
    return data, None


def main():
    parser = argparse.ArgumentParser(description="Antigravity に 1 曲ずつ聴かせて印象を採点させる")
    parser.add_argument("songs", nargs="*", help="曲名（audio/ のファイル名から拡張子を除いたもの）")
    parser.add_argument("--all", action="store_true", help="audio/ 以下の音源をすべて聴かせる")
    parser.add_argument("--run", type=int, default=1, help="何回目の採点か（既定: 1）")
    args = parser.parse_args()

    refuse_api_key()
    files = audio_files()
    if not files:
        fail(f"{AUDIO_DIR} に音源がありません。")
    by_name = {p.stem: p for p in files}
    targets = list(by_name) if args.all else args.songs
    if not targets:
        parser.error("曲名を指定するか、--all を付けてください。")

    # 1 曲に 1〜4 分かかる。枠を一気に使わないよう並列にはしない。
    for song in targets:
        if song not in by_name:
            fail(f"audio/ に {song} がありません。")
        if (RAW_DIR / f"{song}__run{args.run}.json").exists():
            print(f"済み: {song}（run {args.run}）")
            continue
        data, err = listen(by_name[song], files.index(by_name[song]) + 1, args.run)
        if err:
            print(f"失敗: {song}: {err}")
            continue
        print(f"{song}  [{data['tempo_feel']}] {data['axes']}")
        print(f"  {data['summary']}")


if __name__ == "__main__":
    main()
