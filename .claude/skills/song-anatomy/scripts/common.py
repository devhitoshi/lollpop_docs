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
