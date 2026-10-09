"""song-anatomy のスクリプトが共有するパスと小道具。標準ライブラリだけで動く。"""
from __future__ import annotations

import hashlib
import re
import shutil
import subprocess
from pathlib import Path

# スクリプトは自分でリポジトリルートに chdir せず、__file__ からの相対でパスを決める。
# 置き場所を動かしたら、この階層数を直す（scripts → song-anatomy → skills → .claude → ルート）
ROOT = Path(__file__).resolve().parents[4]
AUDIO = ROOT / "audio"
LYRICS = ROOT / "songs" / "lyrics"
STEMS = ("vocals", "drums", "bass", "other")
SR = 44100


def source_path(song: str) -> Path:
    hits = [p for p in AUDIO.glob(f"{song}.*") if p.suffix.lower() in (".m4a", ".mp3", ".wav", ".flac")]
    if not hits:
        raise SystemExit(f"音源が無い: {AUDIO / song}.*")
    return hits[0]


def stems_dir(song: str) -> Path:
    return AUDIO / "stems" / song


def data_dir(song: str) -> Path:
    """曲ごとのデータと図の置き場。リポジトリに入る。"""
    return ROOT / "songs" / "analysis" / "anatomy" / song


def work_dir(song: str) -> Path:
    """途中の出力（時刻合わせの生データ、確認ページ、図の HTML）の置き場。リポジトリには入らない。"""
    d = ROOT / "work" / "anatomy" / song
    d.mkdir(parents=True, exist_ok=True)
    return d


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def to_wav(src: Path, dst: Path) -> None:
    """analyze_audio.py と同じく ffmpeg で wav にする。こちらは左右の広がりを見るのでステレオのまま。"""
    if shutil.which("ffmpeg") is None:
        raise SystemExit("ffmpeg が見つからない")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-ac", "2", "-ar", str(SR), str(dst)], check=True)


def read_lyrics(song: str) -> list[dict]:
    """歌詞ファイルを構成ごとの行に分ける。line_no はファイルの行番号（1 始まり）。"""
    path = LYRICS / f"{song}.md"
    lines, section, in_lyrics = [], None, False
    for no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if raw.startswith("## "):
            section, in_lyrics = raw[3:].strip(), False
            if section.startswith("作詞"):
                break
            continue
        if raw.startswith("### "):
            in_lyrics = raw[4:].strip() == "歌詞"
            continue
        if raw.startswith("<!--"):
            break
        text = raw.strip()
        if section and in_lyrics and text:
            lines.append({"section": section, "line_no": no, "text": text})
    return lines


def mmss(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def compact(text: str) -> str:
    return re.sub(r"\s+", "", text)


# 和音（chords.json）。図のスクリプトからも使うので、ここに置く（標準ライブラリだけ）
NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
ROMAN = ["Ⅰ", "♭Ⅱ", "Ⅱ", "♭Ⅲ", "Ⅲ", "Ⅳ", "♯Ⅳ", "Ⅴ", "♭Ⅵ", "Ⅵ", "♭Ⅶ", "Ⅶ"]
MINOR = ("m", "m7")
# 和音の役割。初心者向けの言い方と、図の凡例に出す一行説明
FUNCTIONS = {
    "home": ("家", "Ⅰ。落ち着く場所。ここに来ると終わった感じがする"),
    "float": ("浮く", "Ⅳ。家から少し離れて、ふわっと浮く"),
    "tension": ("張る", "Ⅴ。家に帰りたくなる、張りつめた和音"),
    "sad": ("切ない", "Ⅵm・Ⅲm・Ⅱm。暗く、切ない側の和音"),
    "other": ("そのほか", "上のどれでもない和音（借りてきた和音など）"),
}


def chord_function(interval: int, quality: str) -> str:
    """主音から数えた半音の数と和音の形から、役割（FUNCTIONS の鍵）を返す。"""
    if interval == 0 and quality not in MINOR:
        return "home"
    if interval == 5 and quality not in MINOR:
        return "float"
    if interval == 7 and quality not in MINOR:
        return "tension"
    if interval in (2, 4, 9) and quality in MINOR:
        return "sad"
    return "other"


def apply_keys(chords: dict, keys: dict[str, str]) -> None:
    """区間のキーを決め（keys で上書き。鍵は構成名、値は長調の主音）、半小節ごとの度数・役割とキーの動きを入れ直す。

    同じ名前の区間（「間奏」など）は、名前だけで書くと全部に効く。1 つだけ変えるときは「間奏#2」（2 回目の間奏）と書く。
    """
    seen: dict[str, int] = {}
    for s in chords["sections"]:
        seen[s["name"]] = seen.get(s["name"], 0) + 1
        nth = f'{s["name"]}#{seen[s["name"]]}'
        if nth in keys or s["name"] in keys:
            s["key_tonic"], s["key_source"] = keys.get(nth, keys.get(s["name"])), "story"
    for h in chords["halfbars"]:
        sec = next((s for s in chords["sections"] if s["start"] - 0.3 <= h["t0"] < s["end"] - 0.3), None)
        h["key_tonic"] = sec["key_tonic"] if sec else None
        if h["root"] is None or sec is None:
            h["degree"], h["function"] = None, ("none" if h["root"] is None else "other")
            continue
        tonic = NOTES.index(sec["key_tonic"])
        iv = (NOTES.index(h["root"]) - tonic) % 12
        h["degree"] = ROMAN[iv] + h["quality"] + (f"/{ROMAN[(NOTES.index(h['bass']) - tonic) % 12]}" if h["bass"] else "")
        h["function"] = chord_function(iv, h["quality"])
    changes = []
    for p, q in zip(chords["sections"], chords["sections"][1:]):
        d = (NOTES.index(q["key_tonic"]) - NOTES.index(p["key_tonic"])) % 12
        if d:
            changes.append({"from_section": p["name"], "to_section": q["name"], "at": q["start"], "semitones": d if d <= 6 else d - 12})
    chords["key_changes"] = changes
