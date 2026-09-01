#!/usr/bin/env python3
"""音源を解析して songs/analysis/[曲名].md と songs/analysis/song_features.csv を作る。

購入した音源ファイルを audio/ に置いて実行する。音源そのものはリポジトリに入れない
（.gitignore で除外済み）。出力されるのは数値だけ。

    python3 .claude/skills/music-analysis/scripts/analyze_audio.py --all
    python3 .claude/skills/music-analysis/scripts/analyze_audio.py audio/主人公.flac
"""

import argparse
import csv
import datetime
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

project_root = Path(__file__).resolve().parents[4]

AUDIO_DIR = project_root / "audio"
ANALYSIS_DIR = project_root / "songs" / "analysis"
FEATURES_CSV = project_root / "songs" / "analysis" / "song_features.csv"

# librosa が soundfile 経由で直接読める拡張子。それ以外は ffmpeg で wav に変換する。
NATIVE_SUFFIXES = {".wav", ".flac", ".ogg", ".aiff", ".aif", ".mp3"}
AUDIO_SUFFIXES = NATIVE_SUFFIXES | {".m4a", ".aac", ".alac", ".wma", ".opus"}

# Krumhansl-Schmuckler のキープロファイル。12音のクロマ分布と相関を取ってキーを推定する。
MAJOR_PROFILE = [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88]
MINOR_PROFILE = [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17]
PITCH_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

SPARK_CHARS = "▁▂▃▄▅▆▇█"

# これより短い区間はセクションとして扱わず、手前のセクションに含める。
MIN_SECTION_SEC = 8.0


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def load_audio(path):
    """音源を読み込んで (波形, サンプリングレート) を返す。必要なら ffmpeg で変換する。"""
    import librosa

    if path.suffix.lower() in NATIVE_SUFFIXES:
        return librosa.load(str(path), sr=None, mono=True)

    if shutil.which("ffmpeg") is None:
        fail(
            f"{path.name} は直接読めない形式です。ffmpeg を入れるか、先に変換してください:\n"
            f"    ffmpeg -i '{path}' -ac 1 -ar 44100 '{path.with_suffix('.wav')}'"
        )

    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "converted.wav"
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-i", str(path), "-ac", "1", "-ar", "44100", str(wav)],
            check=True,
        )
        return librosa.load(str(wav), sr=None, mono=True)


def estimate_key(chroma):
    """クロマ分布から (キー名, 長調/短調) を推定する。"""
    import numpy as np

    profile = chroma.mean(axis=1)
    if profile.sum() <= 0:
        return "判定不能"

    best_score, best_name = -2.0, "判定不能"
    for tonic in range(12):
        rotated = np.roll(profile, -tonic)
        for quality, reference in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
            score = np.corrcoef(rotated, reference)[0, 1]
            if score > best_score:
                best_score, best_name = score, f"{PITCH_NAMES[tonic]} {quality}"
    return best_name


def sparkline(values):
    """数値列を ▁▂▃▄▅▆▇█ の文字列にする。"""
    low, high = min(values), max(values)
    if high - low < 1e-9:
        return SPARK_CHARS[0] * len(values)
    span = high - low
    return "".join(
        SPARK_CHARS[min(int((v - low) / span * len(SPARK_CHARS)), len(SPARK_CHARS) - 1)]
        for v in values
    )


def mmss(seconds):
    return f"{int(seconds) // 60}:{int(seconds) % 60:02d}"


def section_bounds(y, sr, beats, n_sections):
    """ビート単位の音色・和音の変化から、セクションの境界（秒）を求める。"""
    import librosa
    import numpy as np

    mfcc = librosa.feature.mfcc(y=y, sr=sr, n_mfcc=13)
    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    features = np.vstack([librosa.util.normalize(mfcc, axis=1), chroma])

    if len(beats) < n_sections + 1:
        # ビートが取れなかった曲は等分割にフォールバックする。
        total = librosa.get_duration(y=y, sr=sr)
        return [total * i / n_sections for i in range(n_sections + 1)]

    synced = librosa.util.sync(features, beats, aggregate=np.median)
    bound_frames = librosa.segment.agglomerative(synced, n_sections)
    times = list(librosa.frames_to_time(beats[bound_frames], sr=sr))

    # 数秒しかない断片が混ざると構成として読めないので、近すぎる境界は手前に吸収する。
    duration = librosa.get_duration(y=y, sr=sr)
    bounds = [0.0]
    for t in times:
        if t - bounds[-1] >= MIN_SECTION_SEC:
            bounds.append(t)
    if duration - bounds[-1] < MIN_SECTION_SEC and len(bounds) > 1:
        bounds.pop()
    bounds.append(duration)
    return bounds


def analyze(path, n_sections=0):
    import librosa
    import numpy as np

    y, sr = load_audio(path)
    if y.size == 0:
        fail(f"{path.name} は空のファイルです。")

    duration = librosa.get_duration(y=y, sr=sr)
    if n_sections <= 0:
        # 1セクション20秒前後を目安に、尺から分割数を決める。
        n_sections = max(4, min(14, round(duration / 20)))
    tempo, beats = librosa.beat.beat_track(y=y, sr=sr)
    bpm = float(np.atleast_1d(tempo)[0])

    chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
    key = estimate_key(chroma)

    # 音量は 0.1 秒刻みの RMS。dBFS に直して平均とレンジを出す。
    hop = max(int(sr * 0.1), 1)
    rms = librosa.feature.rms(y=y, frame_length=hop * 2, hop_length=hop)[0]
    rms_db = librosa.amplitude_to_db(rms, ref=1.0)
    audible = rms_db[rms_db > rms_db.max() - 60]
    mean_db = float(audible.mean()) if audible.size else float(rms_db.mean())
    dynamic_range = float(np.percentile(audible, 95) - np.percentile(audible, 5)) if audible.size else 0.0

    centroid = librosa.feature.spectral_centroid(y=y, sr=sr)[0]
    onsets = librosa.onset.onset_detect(y=y, sr=sr, units="time")

    bounds = section_bounds(y, sr, beats, n_sections)
    sections = []
    for start, end in zip(bounds[:-1], bounds[1:]):
        s_frame, e_frame = int(start / 0.1), int(end / 0.1)
        seg_db = rms_db[s_frame:e_frame]
        c_start = librosa.time_to_frames(start, sr=sr)
        c_end = librosa.time_to_frames(end, sr=sr)
        seg_centroid = centroid[c_start:c_end]
        seg_chroma = chroma[:, c_start:c_end]
        sections.append(
            {
                "start": start,
                "length": end - start,
                "db": float(seg_db.mean()) if seg_db.size else mean_db,
                "centroid": float(seg_centroid.mean()) if seg_centroid.size else 0.0,
                "density": float(((onsets >= start) & (onsets < end)).sum() / (end - start)),
                "key": estimate_key(seg_chroma) if seg_chroma.size else "判定不能",
            }
        )

    # 音量は絶対値よりも「曲の中でどこが大きいか」が読みたいので、最大セクションを 0 dB に揃える。
    loudest = max((s["db"] for s in sections), default=0.0)
    for s in sections:
        s["relative_db"] = s["db"] - loudest

    # 推移のスパークラインは 1 秒ごとに間引く。
    per_second = [float(rms_db[i : i + 10].mean()) for i in range(0, len(rms_db), 10) if rms_db[i : i + 10].size]

    return {
        "song": path.stem,
        "source": path.name,
        "duration": duration,
        "bpm": bpm,
        "key": key,
        "mean_db": mean_db,
        "dynamic_range": dynamic_range,
        "sections": sections,
        "per_second": per_second,
    }


def write_markdown(result):
    today = datetime.date.today().isoformat()
    lines = [
        f"# {result['song']} — 曲調データ",
        "",
        "> `.claude/skills/music-analysis/scripts/analyze_audio.py` による自動解析の結果です。",
        f"> 解析日: {today} ／ 元ファイル: `{result['source']}`",
        "",
        "## 概要",
        "",
        "| 項目 | 値 |",
        "| --- | --- |",
        f"| 尺 | {mmss(result['duration'])} |",
        f"| BPM | {result['bpm']:.1f} |",
        f"| キー | {result['key']} |",
        f"| 平均音量 | {result['mean_db']:.1f} dBFS |",
        f"| ダイナミクスレンジ | {result['dynamic_range']:.1f} dB |",
        "",
        "## セクション",
        "",
        "境界は音色と和音の変化から機械的に割ったもので、Aメロ・サビといった名前は付いていません。",
        f"`songs/lyrics/{result['song']}.md` の構成と突き合わせて読んでください。",
        "",
        "| # | 開始 | 長さ | 相対音量 | 明るさ | 密度 | キー |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for i, s in enumerate(result["sections"], start=1):
        lines.append(
            f"| {i} | {mmss(s['start'])} | {s['length']:.0f}秒 | {s['relative_db']:+.1f} dB "
            f"| {s['centroid']:.0f} Hz | {s['density']:.1f} 音/秒 | {s['key']} |"
        )

    lines += [
        "",
        "- **相対音量**: 曲中でいちばん大きいセクションを 0 dB とした相対値。サビの持ち上がり方が見える。",
        "- **明るさ**: スペクトル重心。高いほど高音成分が多く、抜けの良い音になる。",
        "- **密度**: 1秒あたりの音の立ち上がり数。高いほど手数が多く、忙しい。",
        "",
        "## 音量の推移（1秒ごと）",
        "",
        "```",
        sparkline(result["per_second"]),
        "```",
        "",
        "## 注意",
        "",
        "- BPM は倍・半分に振れることがある（168 と 84 など）。歌ってみて合わない場合は倍率を疑う。",
        "- キーは12音の分布からの推定で、転調のある曲や借用和音の多い曲では平行調と入れ替わることがある。",
        "- セクション数は既定で尺から自動決定している。合わないときは `--sections N` で指定し直す。",
        "",
    ]
    out = ANALYSIS_DIR / f"{result['song']}.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def update_features_csv(results):
    """全曲比較用の CSV を更新する。同じ曲名の行は新しい結果で置き換える。"""
    header = ["song", "duration_sec", "bpm", "key", "mean_dbfs", "dynamic_range_db", "sections", "analyzed_at"]
    rows = {}
    if FEATURES_CSV.exists():
        with FEATURES_CSV.open(encoding="utf-8") as f:
            for row in csv.DictReader(f):
                rows[row["song"]] = row

    today = datetime.date.today().isoformat()
    for r in results:
        rows[r["song"]] = {
            "song": r["song"],
            "duration_sec": f"{r['duration']:.1f}",
            "bpm": f"{r['bpm']:.1f}",
            "key": r["key"],
            "mean_dbfs": f"{r['mean_db']:.1f}",
            "dynamic_range_db": f"{r['dynamic_range']:.1f}",
            "sections": str(len(r["sections"])),
            "analyzed_at": today,
        }

    FEATURES_CSV.parent.mkdir(parents=True, exist_ok=True)
    with FEATURES_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=header)
        writer.writeheader()
        for song in sorted(rows):
            writer.writerow(rows[song])


def main():
    parser = argparse.ArgumentParser(description="音源から BPM・キー・構成・音量推移を出す")
    parser.add_argument("files", nargs="*", type=Path, help="解析する音源ファイル")
    parser.add_argument("--all", action="store_true", help="audio/ 以下の音源をすべて解析する")
    parser.add_argument("--sections", type=int, default=0, help="セクション分割数（既定: 尺から自動）")
    args = parser.parse_args()

    try:
        import librosa  # noqa: F401
    except ImportError:
        fail(
            "librosa が入っていません。次のコマンドで入れてください:\n"
            "    python3 -m pip install -r .claude/skills/music-analysis/scripts/requirements.txt"
        )

    if args.all:
        targets = sorted(p for p in AUDIO_DIR.glob("*") if p.suffix.lower() in AUDIO_SUFFIXES)
        if not targets:
            fail(f"{AUDIO_DIR} に音源がありません。購入したファイルを置いてから実行してください。")
    elif args.files:
        targets = args.files
    else:
        parser.error("解析するファイルを指定するか、--all を付けてください。")

    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    results = []
    for path in targets:
        if not path.exists():
            fail(f"{path} が見つかりません。")
        print(f"解析中: {path.name}")
        result = analyze(path, args.sections)
        out = write_markdown(result)
        results.append(result)
        print(f"  BPM {result['bpm']:.1f} / {result['key']} / {mmss(result['duration'])} -> {out.relative_to(project_root)}")

    update_features_csv(results)
    print(f"\n{len(results)} 曲を解析しました。比較表: {FEATURES_CSV.relative_to(project_root)}")


if __name__ == "__main__":
    main()
