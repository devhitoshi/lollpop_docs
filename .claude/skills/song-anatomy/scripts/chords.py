#!/usr/bin/env python3
"""分離した音からコード（和音）を推定する。専用環境（.venv）で動かす。

    $VPY chords.py シーソーゲーム     # → songs/analysis/anatomy/<曲名>/chords.json

ベース（bass.wav）で根音、その他の楽器（other.wav）で和音の形を見る。歌を抜いた音なので、元の音源より当たりやすい。
時刻の土台は anatomy.json の拍（beats）と構成（sections）。2 拍（半小節）ごとに 1 つ判定し、ぶれを Viterbi でならす。
キーは区間ごとに、出てきた和音がいちばん素直に収まる長調を選ぶ。同じ種類の区間（サビどうし等）は 1 つにまとめ、
その区間だけ明らかに別のキーに収まるときだけ、区間のキーとして残す（転調の候補）。
正解データが無いので、くり返す区間（1 サビと 2 サビ等）で同じ並びが出たかの一致率を、確からしさの目安として出す。
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date

import librosa
import numpy as np

import build_anatomy as fig
import common

SR = 22050
HOP = 512
NOTES = common.NOTES
QUALITIES = {"": [0, 4, 7], "m": [0, 3, 7], "7": [0, 4, 7, 10], "M7": [0, 4, 7, 11], "m7": [0, 3, 7, 10], "sus4": [0, 5, 7]}
MINOR = common.MINOR
# 長調の中で素直に出てくる和音（度数 → 合う形）
DIATONIC = {0: ("", "M7", "sus4"), 2: MINOR, 4: MINOR, 5: ("", "M7"), 7: ("", "7", "sus4"), 9: MINOR}
BASS_ON_DB = -45.0  # ベースがこれより小さいと、根音の手がかりに使わない
NONE_DB = -50.0  # 伴奏もベースもこれより小さいと「和音なし」
STAY = 0.12  # 同じ和音に留まる方を少し好む（ぶれを抑える）
OWN_KEY_MARGIN = 0.2  # 区間だけのキーが、まとめたキーよりこれだけ収まりがよければ、区間のキーとして残す
OWN_KEY_MIN = 8  # 区間のキーを残すのは、半小節がこれ以上ある区間だけ（短い区間は数個の和音で振れる）
NEAR = 0.08  # 収まりの差がこれ以内のキーは「同じくらい」とみなし、曲の中で多く使われるキーを選ぶ


def templates() -> tuple[list[tuple[int, str]], np.ndarray]:
    names, mats = [], []
    for r in range(12):
        for q, iv in QUALITIES.items():
            t = np.zeros(12)
            for i in iv:
                t[(r + i) % 12] = 1.0
            t[r] += 0.5  # 根音を少し重く
            names.append((r, q))
            mats.append(t / np.linalg.norm(t))
    return names, np.array(mats)


def key_fit(chords: list[tuple[int, str]], tonic: int) -> float:
    """その長調に、和音がどれだけ素直に収まるか（0〜1）。根音が音階の上にあれば半分、形も合えば満点。"""
    if not chords:
        return 0.0
    s = 0.0
    for r, q in chords:
        iv = (r - tonic) % 12
        if iv in DIATONIC:
            s += 0.5 + (0.5 if q in DIATONIC[iv] else 0.0)
    return s / len(chords)


def best_key(chords: list[tuple[int, str]]) -> tuple[int, float]:
    fits = [(key_fit(chords, k), k) for k in range(12)]
    f, k = max(fits)
    return k, f


def near_keys(chords: list[tuple[int, str]]) -> list[int]:
    """いちばん収まりがよいキーと、差が NEAR 以内のキー。"""
    fits = [key_fit(chords, k) for k in range(12)]
    top = max(fits)
    return [k for k in range(12) if fits[k] >= top - NEAR]


MAJOR_PROFILE = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def profile_fit(chroma: np.ndarray, tonic: int) -> float:
    """12 音の分布が、その長調（または平行短調）の型にどれだけ似ているか。"""
    if not chroma.any():
        return 0.0
    major = np.corrcoef(np.roll(MAJOR_PROFILE, tonic), chroma)[0, 1]
    minor = np.corrcoef(np.roll(MINOR_PROFILE, (tonic + 9) % 12), chroma)[0, 1]
    return float(max(major, minor))


def family(name: str) -> str:
    """同じ種類の区間をまとめる名前。サビ・ラスサビ・頭サビは「サビ」、落ちサビは別。"""
    core = fig.section_core(name).strip()
    return "サビ" if core in ("サビ", "ラスサビ", "頭サビ") else core


def estimate(song: str) -> dict:
    a = fig.load(song)
    stems = common.stems_dir(song)
    other, _ = librosa.load(stems / "other.wav", sr=SR, mono=True)
    bass, _ = librosa.load(stems / "bass.wav", sr=SR, mono=True)
    beats = np.array(a["beats"]["times"])
    phase = a["beats"]["downbeat_phase"]
    dur = a["duration_sec"]
    grid = np.concatenate([[0.0], beats[phase % 2 :: 2], [dur]])
    grid = grid[np.concatenate([[True], np.diff(grid) > 0.2])]

    ch_o = librosa.feature.chroma_cqt(y=librosa.effects.harmonic(other), sr=SR, hop_length=HOP)
    ch_b = librosa.feature.chroma_cqt(y=bass, sr=SR, hop_length=HOP, fmin=librosa.note_to_hz("C1"), n_octaves=4)
    rms_o = librosa.feature.rms(y=other, hop_length=HOP)[0]
    rms_b = librosa.feature.rms(y=bass, hop_length=HOP)[0]
    fr = np.clip(librosa.time_to_frames(grid, sr=SR, hop_length=HOP), 0, ch_o.shape[1])

    names, T = templates()
    segs = []
    for a0, a1, t0, t1 in zip(fr[:-1], fr[1:], grid[:-1], grid[1:]):
        if a1 <= a0:
            continue
        segs.append(dict(
            t0=float(t0), t1=float(t1),
            co=np.median(ch_o[:, a0:a1], axis=1), cb=np.median(ch_b[:, a0:a1], axis=1),
            lo=float(20 * np.log10(np.mean(rms_o[a0:a1]) + 1e-9)), lb=float(20 * np.log10(np.mean(rms_b[a0:a1]) + 1e-9)),
        ))

    # 当てはまり（和音の形＋ベースの根音）。最後の列は「和音なし」
    n, K = len(segs), len(names) + 1
    S = np.zeros((n, K))
    penalty = np.array([0.03 if q not in ("", "m") else 0.0 for _, q in names])  # 7th などは、はっきりしているときだけ
    for i, s in enumerate(segs):
        co = s["co"] / (np.linalg.norm(s["co"]) + 1e-9)
        cb = s["cb"] / (s["cb"].max() + 1e-9)
        sc = T @ co - penalty
        if s["lb"] > BASS_ON_DB:
            sc = sc + 0.35 * np.array([cb[r] for r, _ in names])
        S[i, :-1] = sc
        S[i, -1] = 0.55 if (s["lo"] < NONE_DB and s["lb"] < BASS_ON_DB) else -1.0
    dp, bp = S[0].copy(), np.zeros((n, K), dtype=int)
    for i in range(1, n):
        j = int(dp.argmax())
        stay = dp + STAY
        bp[i] = np.where(stay >= dp[j], np.arange(K), j)
        dp = np.maximum(stay, dp[j]) + S[i]
    path = [int(dp.argmax())]
    for i in range(n - 1, 0, -1):
        path.append(int(bp[i, path[-1]]))
    path.reverse()

    def section_at(t: float) -> str | None:
        for x in a["sections"]:
            if x["start"] - 0.3 <= t < x["end"] - 0.3:
                return x["name"]
        return None

    halfbars = []
    for i, (s, k) in enumerate(zip(segs, path)):
        hb = dict(t0=round(s["t0"], 2), t1=round(s["t1"], 2), section=section_at(s["t0"]))
        if k == len(names):
            hb.update(chord="N", root=None, quality=None, bass=None, score=0.0)
        else:
            r, q = names[k]
            bn = int(np.argmax(s["cb"]))
            slash = NOTES[bn] if (s["lb"] > BASS_ON_DB and bn != r) else None
            hb.update(chord=NOTES[r] + q + (f"/{slash}" if slash else ""), root=NOTES[r], quality=q, bass=slash, score=round(float(S[i, k]), 3))
        halfbars.append(hb)

    # キー：種類ごとにまとめて決め、区間だけ明らかに違うものは区間のキーとして残す
    # 同じ名前の区間（「間奏」など）が複数あるので、区間は出てくる順の番号で持つ
    sec_list = a["sections"]
    per_sec = []
    for idx, x in enumerate(sec_list):
        cs = [(NOTES.index(h["root"]), h["quality"]) for h in halfbars if h["root"] is not None and x["start"] - 0.3 <= h["t0"] < x["end"] - 0.3]
        per_sec.append(cs)
    fam_chords = defaultdict(list)
    for x, cs in zip(sec_list, per_sec):
        fam_chords[family(x["name"])].extend(cs)
    # 候補が並ぶとき（5 度隣のキーは共通の和音が多い）は、伴奏の 12 音の分布（Krumhansl の長調・短調の型）で決める
    def chroma_of(t0: float, t1: float) -> np.ndarray:
        idx = [i for i, h in enumerate(halfbars) if t0 - 0.3 <= h["t0"] < t1 - 0.3 and h["root"] is not None]
        return sum((segs[i]["co"] for i in idx), np.zeros(12))

    def pick(ks: list[int], chroma: np.ndarray) -> int:
        return max(ks, key=lambda k: profile_fit(chroma, k))

    fam_chroma = defaultdict(lambda: np.zeros(12))
    for x in sec_list:
        fam_chroma[family(x["name"])] += chroma_of(x["start"], x["end"])
    fam_key = {f: pick(near_keys(cs), fam_chroma[f]) for f, cs in fam_chords.items() if cs}
    whole_key, whole_fit = best_key([c for cs in per_sec for c in cs])

    sections = []
    for x, cs in zip(sec_list, per_sec):
        f = family(x["name"])
        fk = fam_key.get(f, whole_key)
        tonic, source = fk, "family"
        if len(cs) >= OWN_KEY_MIN:
            own = near_keys(cs)
            if fk not in own and max(key_fit(cs, k) for k in own) - key_fit(cs, fk) >= OWN_KEY_MARGIN:
                tonic, source = pick(own, chroma_of(x["start"], x["end"])), "own"
        sections.append(dict(
            name=x["name"], start=x["start"], end=x["end"], family=f,
            key_tonic=NOTES[tonic], key_source=source, key_candidates=[NOTES[k] for k in near_keys(cs)] if cs else [],
            key_fit=round(key_fit(cs, tonic), 3), halfbar_count=len(cs),
        ))

    # くり返す区間で、同じ根音の並びが出たか。頭が半小節ずれることがあるので ±1 ずらして良い方を取る。
    # 転調したくり返し（ラスサビが半音上など）も同じ並びとして数えられるよう、全体を何半音ずらすと揃うかも探す。
    # 揃ったずらし幅（transposed）は、転調の手がかりとして残す（耳での確認までは書かない）
    by_fam = defaultdict(list)
    for x in sections:
        by_fam[x["family"]].append((x["name"], [h["root"] for h in halfbars if x["start"] - 0.3 <= h["t0"] < x["end"] - 0.3]))
    consistency, transposed = {}, []
    for f, items in by_fam.items():
        if len(items) < 2 or f in ("間奏", "イントロ", "アウトロ"):
            continue
        agree = total = 0
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                (ni, si), (nj, sj) = items[i], items[j]
                best = (-1.0, 0, 0, 0)  # 割合, 一致数, 比べた数, ずらし幅
                for shift in (-1, 0, 1):
                    u, v = (si[shift:], sj) if shift >= 0 else (si, sj[-shift:])
                    pairs = [(NOTES.index(p), NOTES.index(q)) for p, q in zip(u, v) if p and q]
                    if not pairs:
                        continue
                    for tr in range(12):
                        hit = sum((p + tr) % 12 == q for p, q in pairs)
                        # 同じ割合ならずらさない方（tr=0）を選ぶ
                        if hit / len(pairs) > best[0] + 1e-9:
                            best = (hit / len(pairs), hit, len(pairs), tr)
                if best[2]:
                    agree, total = agree + best[1], total + best[2]
                    if best[3] and best[0] >= 0.6:
                        transposed.append({"from": ni, "to": nj, "semitones": best[3] if best[3] <= 6 else best[3] - 12, "agreement": round(best[0], 3)})
        if total:
            consistency[f] = round(agree / total, 3)

    res = dict(
        schema_version=1, song=song, status="machine", analyzed_at=date.today().isoformat(),
        note="機械の推定。メジャーとマイナー、7th の有無は取り違えることがある。キーは提案で、story.json の keys で上書きする。オーナーの耳での確認まで記事・動画に使わない",
        method=dict(grid="2 拍ごと（anatomy.json の beats）", root="bass.wav", shape="other.wav（harmonic 成分）", smoothing=f"Viterbi stay={STAY}",
                    librosa=librosa.__version__, key="区間の和音が素直に収まる長調。並んだら伴奏の 12 音の分布で決める。度数はその長調の主音から数える"),
        whole_key=dict(tonic=NOTES[whole_key], fit=round(whole_fit, 3)),
        sections=sections, consistency=consistency, transposed_repeats=transposed, halfbars=halfbars,
    )
    common.apply_keys(res, {})
    return res


def summary(res: dict) -> str:
    out = [f"# {res['song']}  曲全体の収まりがよい長調: {res['whole_key']['tonic']}（{res['whole_key']['fit']}）",
           f"くり返し区間の一致率（移調も許す）: {res['consistency']}", f"ずらすと揃ったくり返し: {[(t['from'], t['to'], t['semitones'], t['agreement']) for t in res['transposed_repeats']]}", f"キーの動き: {[(k['from_section'], k['to_section'], k['semitones']) for k in res['key_changes']]}", ""]
    for s in res["sections"]:
        seq = [h for h in res["halfbars"] if s["start"] - 0.3 <= h["t0"] < s["end"] - 0.3]
        out.append(f"## {s['name']} ({common.mmss(s['start'])}〜) キー {s['key_tonic']}（{s['key_source']}, 収まり {s['key_fit']}, 候補 {s['key_candidates']}）")
        out.append("  " + " | ".join(h["chord"] for h in seq))
        out.append("  " + " | ".join(h["degree"] or "N" for h in seq))
    return "\n".join(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    args = ap.parse_args()
    res = estimate(args.song)
    (common.data_dir(args.song) / "chords.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    text = summary(res)
    (common.work_dir(args.song) / "chords_summary.md").write_text(text, encoding="utf-8")
    print(text)
