#!/usr/bin/env python3
"""分離したステムと歌詞の時刻合わせから、使い回せるデータ（anatomy.json と series/*.csv）を作る。

    .venv/Scripts/python extract.py シーソーゲーム

先に separate.py と align.py を済ませておく。出力先は songs/analysis/anatomy/<曲名>/。
歌詞の原文は入れない（行番号と文字位置で songs/lyrics/<曲名>.md を参照する）。
"""
from __future__ import annotations

import csv
import datetime
import json
import sys
from pathlib import Path

import librosa
import numpy as np
import soundfile as sf

from common import SR, STEMS, compact, data_dir, read_lyrics, stems_dir, work_dir


HOP = 441  # 1/100 秒
FRAME = 2048
CHROMA_HOP = 4096  # 約 0.093 秒（CQT は 2 の累乗の hop が要る）
GAP_MIN = 4.0  # 歌の無い区間がこれ以上続いたら、間奏として 1 区間にする
QUIET_DROP_DB = 12.0  # ドラムが普段よりこれだけ下がったら「静か」
QUIET_MIN = 2.0


def db(x: np.ndarray) -> np.ndarray:
    return 20 * np.log10(np.maximum(x, 1e-6))


def rms(y: np.ndarray) -> np.ndarray:
    return librosa.feature.rms(y=y, frame_length=FRAME, hop_length=HOP)[0]


def smooth(x: np.ndarray, seconds: float) -> np.ndarray:
    n = max(1, int(seconds * SR / HOP))
    return np.convolve(x, np.ones(n) / n, mode="same")


def runs(mask: np.ndarray, min_len: float) -> list[tuple[float, float]]:
    """True が続く区間を (開始秒, 終了秒) で返す。"""
    out, start = [], None
    for i, v in enumerate(np.append(mask, False)):
        if v and start is None:
            start = i
        elif not v and start is not None:
            a, b = start * HOP / SR, i * HOP / SR
            if b - a >= min_len:
                out.append((round(a, 2), round(b, 2)))
            start = None
    return out


def write_csv(path: Path, header: list[str], rows) -> None:
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(header)
        w.writerows(rows)


def lyric_lines(song: str, raw: dict) -> list[dict]:
    """時刻合わせの結果を、原文なしの行データにする。"""
    lines = read_lyrics(song)
    segs = raw["segments"]
    if len(segs) != len(lines):
        raise SystemExit(f"歌詞 {len(lines)} 行に対して区間が {len(segs)} 個。align.py の結果を確かめる")
    out = []
    for line, seg in zip(lines, segs):
        if compact(seg["text"]) != compact(line["text"]):
            raise SystemExit(f"行の対応がずれた: {line['text']} / {seg['text']}")
        chars, cursor = [], 0
        for w in seg["words"]:
            token = w["word"].strip()
            if not token:
                continue
            at = line["text"].find(token, cursor)
            if at < 0:
                continue
            cursor = at + len(token)
            chars.append({"c0": at, "c1": cursor, "start": round(w["start"], 3), "end": round(w["end"], 3), "p": round(w["probability"], 3)})
        out.append(
            {
                "section": line["section"],
                "line_no": line["line_no"],
                "head": line["text"][:6],
                "n_chars": len(line["text"]),
                "start": round(seg["start"], 3),
                "end": round(seg["end"], 3),
                "tokens": chars,
                # 1 回目の時刻合わせが外れ、秒の範囲を人が決めてやり直した行（align.py --lines --window）
                **({"realigned_window": seg["realigned_window"]} if "realigned_window" in seg else {}),
            }
        )
    return out


def build_sections(lines: list[dict], duration: float) -> list[dict]:
    """歌詞のブロックを区間にし、歌の無い長い隙間をイントロ・間奏・アウトロとして挟む。"""
    blocks = []
    for l in lines:
        if blocks and blocks[-1]["name"] == l["section"]:
            blocks[-1]["end"] = l["end"]
        else:
            blocks.append({"name": l["section"], "kind": "vocal", "start": l["start"], "end": l["end"]})
    if blocks[0]["name"] == "イントロ":
        # 歌から始まる曲。歌詞ファイルの「イントロ」を曲の頭まで伸ばし、同じ名前の区間を 2 つ作らない
        blocks[0]["start"] = 0.0
    out, cursor = [], 0.0
    for i, b in enumerate(blocks):
        if b["start"] - cursor >= GAP_MIN:
            out.append({"name": "イントロ" if i == 0 else "間奏", "kind": "instrumental", "start": round(cursor, 2), "end": b["start"]})
        else:
            b["start"] = cursor if i else b["start"]
        out.append(b)
        cursor = b["end"]
    if duration - cursor >= GAP_MIN:
        out.append({"name": "アウトロ", "kind": "instrumental", "start": cursor, "end": round(duration, 2)})
    else:
        out[-1]["end"] = round(duration, 2)
    if out[0]["start"] > 0 and out[0]["kind"] == "vocal":
        out.insert(0, {"name": "イントロ", "kind": "instrumental", "start": 0.0, "end": out[0]["start"]})
    for s in out:
        s["status"] = "machine"
    return out


def main(song: str) -> None:
    sdir, out = stems_dir(song), data_dir(song)
    (out / "series").mkdir(parents=True, exist_ok=True)
    meta = json.loads((sdir / "stems_meta.json").read_text(encoding="utf-8"))
    raw = json.loads((work_dir(song) / "alignment_raw.json").read_text(encoding="utf-8"))

    stereo = {}
    for name in STEMS:
        y, sr = sf.read(str(sdir / f"{name}.wav"), dtype="float32", always_2d=True)
        assert sr == SR
        stereo[name] = y.T
    mono = {k: v.mean(0) for k, v in stereo.items()}
    mix = sum(mono.values())
    duration = len(mix) / SR

    # 1. ステムごとの音量（1/100 秒）
    level = {k: db(rms(v)) for k, v in {"mix": mix, **mono}.items()}
    n = len(level["mix"])
    t = np.arange(n) * HOP / SR
    write_csv(
        out / "series" / "stem_loudness.csv",
        ["t", "mix_db", *[f"{s}_db" for s in STEMS]],
        ([f"{t[i]:.2f}", *[f"{level[k][i]:.1f}" for k in ("mix", *STEMS)]] for i in range(n)),
    )

    # 2. ボーカルの有無と左右の広がり（side / mid。0 なら真ん中 1 本、大きいほど左右に広がる）
    v = stereo["vocals"]
    mid, side = rms((v[0] + v[1]) / 2), rms((v[0] - v[1]) / 2)
    width = side / np.maximum(mid, 1e-6)
    vocal_on = smooth(level["vocals"], 0.3) > level["vocals"].max() - 30
    write_csv(
        out / "series" / "vocal_presence.csv",
        ["t", "vocal_on", "width"],
        ([f"{t[i]:.2f}", int(vocal_on[i]), f"{width[i]:.3f}" if vocal_on[i] else ""] for i in range(n)),
    )

    # 3. 音の立ち上がり（ステムごと）
    onsets = {}
    for name in STEMS:
        times = librosa.onset.onset_detect(y=mono[name], sr=SR, hop_length=512, backtrack=True, units="time")
        onsets[name] = [round(float(x), 3) for x in times]

    # 4. 拍と小節の頭（参考値。4 拍子と仮定し、ドラムとベースの低音がいちばん強い拍を小節の頭にする）
    tempo, beats = librosa.beat.beat_track(y=mono["drums"], sr=SR, hop_length=512, units="time")
    low = librosa.onset.onset_strength(y=mono["drums"] + mono["bass"], sr=SR, hop_length=512, fmax=150)
    low_at = low[np.minimum(librosa.time_to_frames(beats, sr=SR, hop_length=512), len(low) - 1)]
    phase = int(np.argmax([low_at[p::4].mean() for p in range(4)]))

    # 5. 伴奏（ベース＋その他）の 12 音の分布
    chroma = librosa.feature.chroma_cqt(y=mono["bass"] + mono["other"], sr=SR, hop_length=CHROMA_HOP)
    ct = np.arange(chroma.shape[1]) * CHROMA_HOP / SR
    write_csv(
        out / "series" / "chroma_accompaniment.csv",
        ["t", *"C C# D D# E F F# G G# A A# B".split()],
        ([f"{ct[i]:.3f}", *[f"{x:.3f}" for x in chroma[:, i]]] for i in range(chroma.shape[1])),
    )

    # 6. 歌詞の時刻と構成
    lines = lyric_lines(song, raw)
    # 時刻合わせは、歌の無い所まで行の頭を引き伸ばすことがある（間奏明けの行など）。
    # 行の頭でボーカルが鳴っていなければ、その行の中で最初に鳴り始める所まで頭を進める。元の値も残す
    for l in lines:
        i0, i1 = int(l["start"] * SR / HOP), int(l["end"] * SR / HOP)
        on = np.flatnonzero(vocal_on[i0:i1])
        if len(on) and on[0] * HOP / SR > 0.3:
            l["start_aligned"] = l["start"]
            l["start"] = round((i0 + on[0]) * HOP / SR, 3)
        # 行の終わりも同じ。間奏の前の行は、歌が終わったあとまで伸びることがある
        # 行の中に 2 秒以上の無音があれば、そこで行を切る（次の歌い出しまで引き伸ばされた行）
        if len(on):
            i_start = int(l["start"] * SR / HOP) - i0
            voiced = on[on >= i_start]
            breaks = np.flatnonzero(np.diff(voiced) * HOP / SR > 2.0)
            last = voiced[breaks[0]] if len(breaks) else voiced[-1]
            if (i1 - i0 - 1 - last) * HOP / SR > 1.0:
                l["end_aligned"] = l["end"]
                l["end"] = round((i0 + last + 1) * HOP / SR, 3)
    sections = build_sections(lines, duration)

    def span(arr: np.ndarray, a: float, b: float, hop: int) -> np.ndarray:
        return arr[..., int(a * SR / hop) : max(int(b * SR / hop), int(a * SR / hop) + 1)]

    for s in sections:
        s["start"], s["end"] = round(s["start"], 2), round(s["end"], 2)
        s["mean_db"] = {k: round(float(span(level[k], s["start"], s["end"], HOP).mean()), 1) for k in ("mix", *STEMS)}

    # 7. 静かになる所（ドラムが普段より大きく下がる区間）
    drums = smooth(level["drums"], 1.0)
    usual = float(np.median(drums[drums > drums.max() - 20]))
    quiet = [{"start": a, "end": b, "status": "machine"} for a, b in runs(drums < usual - QUIET_DROP_DB, QUIET_MIN)]

    # 8. 転調の見当。最初のサビと比べて、伴奏の音の分布が何半音ずれるといちばん重なるか
    chorus = [s for s in sections if "サビ" in s["name"]]
    modulation = []
    if len(chorus) >= 2:
        base = span(chroma, chorus[0]["start"], chorus[0]["end"], CHROMA_HOP).mean(1)
        for s in chorus[1:]:
            cur = span(chroma, s["start"], s["end"], CHROMA_HOP).mean(1)
            corr = [float(np.corrcoef(np.roll(base, k), cur)[0, 1]) for k in range(12)]
            best = int(np.argmax(corr))
            modulation.append(
                {
                    "section": s["name"],
                    "start": s["start"],
                    "compared_to": chorus[0]["name"],
                    "semitones_up": best,
                    "correlation_by_shift": [round(c, 3) for c in corr],
                    "status": "machine",
                }
            )

    # 9. ソロ／全員の見当。行ごとに、歌っている間の左右の広がりの中央値を出して 2 つに分ける
    for l in lines:
        w = span(width, l["start"], l["end"], HOP)
        on = span(vocal_on, l["start"], l["end"], HOP)
        l["vocal_width"] = round(float(np.median(w[on])), 3) if on.any() else None
    widths = sorted(l["vocal_width"] for l in lines if l["vocal_width"] is not None)
    # いちばん大きく値が飛ぶ所を境目にする
    gaps = np.diff(widths)
    cut = (widths[int(np.argmax(gaps))] + widths[int(np.argmax(gaps)) + 1]) / 2 if len(widths) > 1 else 0.0
    for l in lines:
        l["voices_guess"] = None if l["vocal_width"] is None else ("wide" if l["vocal_width"] > cut else "narrow")
        l["singer"] = None
        l["status"] = "machine"

    anatomy = {
        "schema_version": 1,
        "song": song,
        "duration_sec": round(duration, 2),
        "analyzed_at": datetime.date.today().isoformat(),
        "source": {"file": meta["source_file"], "sha256": meta["source_sha256"], "lyrics": f"songs/lyrics/{song}.md"},
        "tools": {
            "separation": {"name": "demucs", "version": meta["demucs"], "model": meta["model"], "device": meta["device"]},
            "alignment": {"name": "stable-ts", "version": raw["stable_ts"], "model": raw["model"], "input": "vocals stem"},
            "features": {"name": "librosa", "version": librosa.__version__},
        },
        "series": {
            "stem_loudness": {"file": "series/stem_loudness.csv", "hop_sec": HOP / SR, "unit": "dBFS (RMS)"},
            "vocal_presence": {"file": "series/vocal_presence.csv", "hop_sec": HOP / SR, "unit": "vocal_on は 0/1、width は side/mid の比"},
            "chroma_accompaniment": {"file": "series/chroma_accompaniment.csv", "hop_sec": CHROMA_HOP / SR, "unit": "0〜1（bass+other）"},
        },
        "sections": sections,
        "lines": lines,
        "quiet": {"method": f"ドラムの音量（1 秒平均）が普段より {QUIET_DROP_DB:.0f} dB 以上下がり {QUIET_MIN:.0f} 秒以上続く区間", "usual_drums_db": round(usual, 1), "items": quiet},
        "modulation": {"method": "最初のサビと比べ、伴奏の 12 音の分布を何半音ずらすと相関が最大になるか", "items": modulation},
        "voices": {"method": "行ごとのボーカルの左右の広がり（side/mid）の中央値。値がいちばん飛ぶ所で 2 つに分けた", "threshold": round(float(cut), 3), "status": "experimental"},
        "beats": {
            "status": "reference",
            "note": "参考値。倍・半分に取り違えることがある。小節の頭は 4 拍子と仮定した推定",
            "tempo_bpm": round(float(np.atleast_1d(tempo)[0]), 1),
            "times": [round(float(b), 3) for b in beats],
            "downbeat_phase": phase,
        },
        "onsets": onsets,
    }
    (out / "anatomy.json").write_text(json.dumps(anatomy, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="")
    check = out / "owner_check.json"
    if not check.exists():
        check.write_text('{\n  "sections": {},\n  "lines": {},\n  "modulation": {},\n  "quiet": {}\n}\n', encoding="utf-8", newline="")

    print(f"尺 {duration:.1f} 秒 ／ 区間 {len(sections)} ／ 行 {len(lines)} ／ 拍 {len(beats)}")
    for s in sections:
        d = s["mean_db"]
        print(f"{s['start']:7.2f}–{s['end']:7.2f} {s['name']:<6} mix {d['mix']:6.1f} vo {d['vocals']:6.1f} dr {d['drums']:6.1f} ba {d['bass']:6.1f} ot {d['other']:6.1f}")
    print("静か:", quiet)
    print("転調:", [(m["section"], m["semitones_up"], max(m["correlation_by_shift"]), m["correlation_by_shift"][0]) for m in modulation])
    print("広がりの境目:", round(float(cut), 3), [(l["head"], l["vocal_width"]) for l in lines])


if __name__ == "__main__":
    main(sys.argv[1])
