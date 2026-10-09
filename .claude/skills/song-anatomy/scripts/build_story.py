#!/usr/bin/env python3
"""初心者向けの読み解き図（横長）を作る。文面は songs/analysis/anatomy/<曲名>/story.json、数値は同じ場所の anatomy.json から読む。

    python build_story.py シーソーゲーム            # 図（story.html と PNG）
    python build_story.py シーソーゲーム --check    # 文面の事実と歌詞の引用を、データと突き合わせるだけ

曲の地図を真ん中に置き、出来事ごとに地図から線を伸ばして、上下の解説につなぐ。
事実（音で起きていること）と読み（考察）を見た目で分ける。読みは断定しない文で story.json に書く。
"""
from __future__ import annotations

import argparse
import asyncio
import html
import json
import re
import shutil

import build_anatomy as fig
import common

W = 1808  # 図の内側の幅（#fig は 1920）
LEFT = 124  # 楽器の名前を書く左の余白
COL_GAP = 34
LINK = 52  # 地図と解説のあいだ。線が通る
ON_DB = -40.0  # 1 秒の平均がこれより大きければ「鳴っている」


def use_threshold(story: dict) -> None:
    """分離の残り音が大きい曲は、-40 dB だと全部「鳴っている」になる。story.json の on_db で曲ごとに変えられる。"""
    global ON_DB
    ON_DB = float(story.get("on_db", ON_DB))
THEME_MIX = 0.06  # 背景に混ぜる曲の色の割合
ROWS = [("vocals", "歌"), ("drums", "ドラム"), ("bass", "ベース"), ("other", "その他の楽器")]
COLORS = {k: c for k, _, c in fig.STEMS}
# 和音の段の色。役割ごと。楽器の色（ピンク・墨・青・緑）と取り違えない色にする
FUNC_COLORS = {"home": "#c48a00", "float": "#8db4e6", "tension": "#e36a2e", "sad": "#7a5cc4", "other": "#c9bfc4"}
LYRICS = common.LYRICS


def on_runs(values: list[float], hop: float, duration: float) -> list[tuple[int, int]]:
    """1 秒ごとに鳴っているかを見て、続いている区間を (開始秒, 終了秒) で返す。1 秒だけの点は捨てる。"""
    n = int(1 / hop)
    on = []
    for t in range(int(duration) + 1):
        chunk = values[t * n : (t + 1) * n]
        on.append(bool(chunk) and sum(chunk) / len(chunk) > ON_DB)
    runs, start = [], None
    for t, v in enumerate(on + [False]):
        if v and start is None:
            start = t
        elif not v and start is not None:
            if t - start >= 2:
                runs.append((start, t))
            start = None
    return runs


def load_chords(song: str, story: dict) -> dict | None:
    """chords.json があれば読み、story.json の keys（区間のキーの指定）を当てて、度数と役割を入れ直す。"""
    path = common.data_dir(song) / "chords.json"
    if not path.exists():
        return None
    ch = json.loads(path.read_text(encoding="utf-8"))
    common.apply_keys(ch, story.get("keys", {}))
    return ch


def split_points(points: list[dict]) -> tuple[list[dict], list[dict]]:
    """出来事を時間順に、上・下・上…と振り分ける。隣どうしの解説が同じ側で詰まらないようにするため。"""
    ordered = sorted(points, key=lambda p: p["span"][0])
    return ordered[0::2], ordered[1::2]


def build_map(a: dict, story: dict, ch: dict | None = None) -> str:
    e = html.escape
    dur = a["duration_sec"]
    x = lambda t: LEFT + (W - LEFT) * t / dur
    parts: list[str] = []
    band: list[str] = []  # 構成の帯。線より手前に描くので、最後に足す
    y = LINK

    # 構成
    band_top = y
    for s in a["sections"]:
        x0, x1 = x(s["start"]), x(s["end"])
        cls = fig.section_class(s)
        band.append(f'<rect class="sec {cls}" x="{x0 + 1:.1f}" y="{y}" width="{max(x1 - x0 - 2, 1):.1f}" height="54"/>')
        name = fig.display_name(s["name"])
        size = 19 if x1 - x0 > len(name) * 19 else 14
        if x1 - x0 > len(name) * 13:
            band.append(f'<text class="secname {cls}" x="{(x0 + x1) / 2:.1f}" y="{y + 34}" text-anchor="middle" font-size="{size}">{e(name)}</text>')
    row_box = {"band": (y, y + 54)}
    y += 54
    for t in range(0, int(dur) + 1, 30):
        band.append(f'<text class="tick" x="{x(t):.1f}" y="{y + 18}" text-anchor="{"start" if t == 0 else "middle"}">{fig.mmss(t)}</text>')
    y += 36

    # 楽器が鳴っている所
    for key, label in ROWS:
        parts.append(f'<rect class="track" x="{LEFT}" y="{y + 7}" width="{W - LEFT}" height="12" rx="6"/>')
        for t0, t1 in on_runs(a["_loudness"][key], a["_hop"], dur):
            parts.append(f'<rect x="{x(t0):.1f}" y="{y}" width="{x(min(t1, dur)) - x(t0):.1f}" height="26" rx="5" fill="{COLORS[key]}"/>')
        parts.append(f'<text class="rowname" x="{LEFT - 14}" y="{y + 19}" text-anchor="end" fill="{COLORS[key]}">{label}</text>')
        row_box[key] = (y, y + 26)
        y += 36
    if ch:
        # 和音の段。2 拍ごとの役割を色で塗る。家（Ⅰ）に着く所が濃い金色で見える
        parts.append(f'<rect class="track" x="{LEFT}" y="{y + 7}" width="{W - LEFT}" height="12" rx="6"/>')
        runs: list[list] = []  # 同じ役割が続く所は 1 本にまとめる（2 拍ごとに切ると縞になって読めない）
        for h in ch["halfbars"]:
            if runs and runs[-1][2] == h["function"] and abs(runs[-1][1] - h["t0"]) < 0.05:
                runs[-1][1] = h["t1"]
            else:
                runs.append([h["t0"], h["t1"], h["function"]])
        for t0, t1, f in runs:
            if f == "none":
                continue
            parts.append(f'<rect x="{x(t0) + 1:.1f}" y="{y}" width="{max(x(t1) - x(t0) - 2, 1):.1f}" height="26" rx="3" fill="{FUNC_COLORS[f]}"/>')
        parts.append(f'<text class="rowname" x="{LEFT - 14}" y="{y + 19}" text-anchor="end" fill="var(--ink)">和音</text>')
        row_box["chords"] = (y, y + 26)
        y += 36
    rows_bottom = y - 10
    height = rows_bottom + LINK

    # 出来事ごとに、地図の上の場所から解説へ線を伸ばす
    top, bottom = split_points(story["points"])
    for side, points in (("top", top), ("bottom", bottom)):
        col_w = (W - COL_GAP * (len(points) - 1)) / len(points)
        for i, p in enumerate(points):
            t0, t1 = p["span"]
            cx = x((t0 + t1) / 2)
            # 囲むのは出来事が起きている段だけ。線は、その囲みの解説側の辺から出す
            boxes = [row_box[k] for k in p.get("rows", [p["target"]])]
            y0, y1 = min(b[0] for b in boxes) - 5, max(b[1] for b in boxes) + 5
            cy = y0 if side == "top" else y1
            col0 = i * (col_w + COL_GAP)
            # 線の行き先は解説の幅の中。真上・真下に解説が無いときは、地図と解説のあいだで横に折る
            tx = min(max(cx, col0 + 16), col0 + col_w - 16)
            (band if p["target"] == "band" else parts).append(f'<rect class="span" x="{x(t0) - 3:.1f}" y="{y0}" width="{max(x(t1) - x(t0), 6) + 6:.1f}" height="{y1 - y0}" rx="6"/>')
            y_end = 0 if side == "top" else height
            # 折る高さを出来事ごとにずらして、横線どうしが重ならないようにする
            y_turn = (14 + 10 * i) if side == "top" else height - (14 + 10 * i)
            route = f"M{cx:.1f},{cy} L{cx:.1f},{y_turn} L{tx:.1f},{y_turn} L{tx:.1f},{y_end}"
            for cls in ("halo", "link"):
                parts.append(f'<path class="{cls}" d="{route}"/>')
            # 帯そのものを囲む出来事の枠と点は、帯より手前に出す
            (band if p["target"] == "band" else parts).append(f'<circle class="dot" cx="{cx:.1f}" cy="{cy}" r="7"/>')
    return f'<svg viewBox="0 0 {W} {height}" width="{W}" height="{height}">' + "\n".join(parts + band) + "</svg>"


def chord_legend(ch: dict | None) -> str:
    if not ch:
        return ""
    e = html.escape
    items = "".join(f'<span><i class="sw" style="background:{FUNC_COLORS[k]}"></i><b>{e(name)}</b>{e(desc)}</span>' for k, (name, desc) in common.FUNCTIONS.items())
    return f'<div class="legend chords"><span><b>和音の段</b>2 拍ごとの和音を、役割で色分け（機械の推定）</span><span class="sep"></span>{items}</div>'


def card(p: dict, side: str) -> str:
    e = html.escape
    quotes = "".join(f"<span>「{e(q['text'])}」</span>" for q in p["quotes"])
    section = p.get("where") or fig.display_name(p["section"])
    return f"""<section class="card {side}">
  <header><span class="when">{fig.mmss(p["time"])}</span><span class="where">{e(section)}</span><h2>{e(p["title"])}</h2></header>
  <div class="fact"><i>音</i><p>{e(p["fact"])}</p></div>
  <div class="quote">{quotes}</div>
  <div class="reading"><i>読み</i><p>{e(p["reading"])}</p></div>
</section>"""


CSS = """
:root { --primary:#d6006e; --blue:#2a6fd6; --ink:#1d1216; --body:#45383e; --muted:#71646b; --muted-soft:#998a92;
  --axis:#dcc8d2; --canvas:#ffffff; --soft:#f7f1f4; --tint:#fdeaf3;
  /* 歌の無い所・楽器の段の下地。曲の色の背景の上でも沈まないよう、白ではなく墨を薄く重ねる */
  --quiet:rgba(29,18,22,.07); }
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--canvas); font-family:"Noto Sans JP",sans-serif; color:var(--body); }
#fig { width:1920px; padding:48px 56px 36px; background:var(--canvas); }
.head { display:grid; grid-template-columns:auto 1fr; column-gap:64px; align-items:end; margin-bottom:34px; }
.eyebrow { color:var(--muted); font-weight:700; font-size:15px; letter-spacing:.08em; }
/* 曲名を大きく。下線が曲の色 */
h1 { display:inline-block; color:var(--ink); font-size:64px; font-weight:700; letter-spacing:-.01em; margin-top:2px; line-height:1.25;
  white-space:nowrap; padding-bottom:6px; border-bottom:8px solid var(--theme); }
.sub { font-size:26px; font-weight:700; color:var(--ink); margin-top:14px; white-space:nowrap; }
.lead { font-size:17px; line-height:1.8; color:var(--body); text-wrap:pretty; padding-bottom:2px; }
svg { display:block; }
.sec.a { fill:#eadfe5; } .sec.b { fill:#cfdff7; } .sec.c { fill:#d3ece8; } .sec.chorus { fill:var(--primary); } .sec.inst { fill:var(--quiet); }
.secname { font-weight:700; fill:var(--ink); } .secname.chorus { fill:#fff; } .secname.inst { fill:var(--muted-soft); font-weight:500; }
.tick { font-size:13px; fill:var(--muted-soft); }
.track { fill:var(--quiet); }
.rowname { font-size:15px; font-weight:700; }
.span { fill:none; stroke:var(--ink); stroke-width:3; }
.halo { stroke:var(--canvas); stroke-width:7; fill:none; } .link { stroke:var(--ink); stroke-width:2.5; fill:none; }
.dot { fill:var(--ink); }
.cards { display:grid; grid-auto-flow:column; grid-auto-columns:1fr; column-gap:34px; }
.cards.upper { align-items:end; }
.card { padding:0 0 18px; }
.card.top { border-bottom:3px solid var(--ink); }
.card.bottom { border-top:3px solid var(--ink); padding:18px 0 0; }
.card header { display:flex; flex-wrap:wrap; align-items:baseline; gap:4px 10px; margin-bottom:10px; }
.card .when { font-size:15px; font-weight:700; color:#fff; background:var(--ink); padding:1px 10px; }
.card .where { font-size:14px; color:var(--muted); font-weight:500; }
.card h2 { flex-basis:100%; font-size:24px; color:var(--ink); font-weight:700; line-height:1.4; }
.fact, .reading { display:grid; grid-template-columns:50px 1fr; column-gap:12px; font-size:16px; line-height:1.75; }
.fact i, .reading i { font-style:normal; font-size:13px; font-weight:700; height:26px; margin-top:1px; display:flex; align-items:center; justify-content:center; }
.fact i { border:1.5px solid var(--ink); color:var(--ink); }
.fact p { color:var(--ink); } .card p { text-wrap:pretty; }
.quote { margin:10px 0 10px 62px; padding-left:12px; border-left:3px solid var(--axis); font-size:17px; font-weight:700; color:var(--ink); line-height:1.7; }
.quote span { display:inline-block; margin-right:4px; }
.reading { background:var(--tint); padding:10px 14px 10px 0; }
.reading i { background:var(--primary); color:#fff; }
.reading p { color:var(--body); }
.legend { display:flex; flex-wrap:wrap; gap:8px 26px; font-size:14px; color:var(--muted); margin-top:30px; align-items:center; }
.legend span { display:inline-flex; align-items:center; gap:8px; }
.legend i { font-style:normal; font-size:13px; font-weight:700; padding:1px 10px; }
.legend .f { border:1.5px solid var(--ink); color:var(--ink); } .legend .r { background:var(--primary); color:#fff; }
.legend b { color:var(--ink); }
.legend.chords { margin-top:10px; } .legend .sw { width:22px; height:14px; padding:0; border-radius:2px; } .legend .sep { width:1px; height:18px; background:var(--axis); }
.foot { margin-top:14px; padding-top:14px; border-top:1px solid var(--axis); font-size:13px; color:var(--muted); line-height:1.8; }
"""


def build(song: str) -> str:
    e = html.escape
    a = fig.load(song)
    story = json.loads((common.data_dir(song) / "story.json").read_text(encoding="utf-8"))
    use_threshold(story)
    ch = load_chords(song, story)
    top, bottom = split_points(story["points"])
    glossary = "".join(f"<span><b>{e(g['term'])}</b>{e(g['meaning'])}</span>" for g in story["glossary"])
    foot = " ".join(story["notes"]) + f" 歌詞の引用は説明に必要な範囲の部分引用です。ファンによる非公式の図です。解析日: {a['analyzed_at']}。作図: AIぽっぱー"
    theme = story.get("theme_color", "")
    if not re.fullmatch(r"#[0-9a-fA-F]{6}", theme):
        raise SystemExit("story.json に theme_color（例: #4b3a8f）が無い。曲の色は、図を作る前にオーナーに聞いて決める（SKILL.md 手順 B）")
    # 背景は曲の色をごく薄く混ぜた色。図の中の配色を変えずに済む濃さにとどめる
    canvas = "#" + "".join(f"{round(255 + (int(theme[i : i + 2], 16) - 255) * THEME_MIX):02x}" for i in (1, 3, 5))
    css = CSS.replace("--canvas:#ffffff;", f"--canvas:{canvas}; --theme:{theme};")
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8"><style>{css}</style></head><body><div id="fig">
<div class="head">
  <div><div class="eyebrow">SONG ANATOMY</div><h1>{e(song)}</h1><div class="sub">{e(story["headline"])}</div></div>
  <p class="lead">{e(story["lead"])}</p>
</div>
<div class="cards upper">{"".join(card(p, "top") for p in top)}</div>
{build_map(a, story, ch)}
<div class="cards">{"".join(card(p, "bottom") for p in bottom)}</div>
<div class="legend"><span><i class="f">音</i>データで確かめた、音で起きていること</span><span><i class="r">読み</i>そこから考えたこと（解釈）</span><span class="sep"></span>
<span>真ん中の帯は曲の流れ（横が時間、0:00〜{fig.mmss(a["duration_sec"])}）。色の帯は、その楽器が鳴っている所</span><span class="sep"></span>{glossary}</div>
{chord_legend(ch)}
<p class="foot">{e(foot)}</p>
</div></body></html>"""


def degree_core(h: dict) -> str:
    """度数を、根音＋（短調の和音なら m）だけにそろえる。7th・sus4・分数（/ベース）は見ない。"""
    roman = h["degree"].split("/")[0]
    base = next(r for r in sorted(common.ROMAN, key=len, reverse=True) if roman.startswith(r))
    return base + ("m" if h["quality"] in common.MINOR else "")


def section_halfbars(ch: dict, name: str) -> list[dict]:
    secs = [s for s in ch["sections"] if s["name"] == name]
    if not secs:
        raise SystemExit(f"chords.json に区間が無い: {name}")
    return [h for s in secs for h in ch["halfbars"] if s["start"] - 0.3 <= h["t0"] < s["end"] - 0.3]


def run_check(c: dict, a: dict, ch: dict | None = None) -> bool:
    """story.json の checks の 1 項目を、データから確かめる。書き方は data/README の「checks」。"""
    L, hop = a["_loudness"], a["_hop"]
    sec = lambda k, t: sum(L[k][int(t / hop) : int((t + 1) / hop)]) * hop
    lines = {l["line_no"]: l for l in a["lines"]}
    if "stem" in c:
        # その楽器が from 秒〜to 秒のあいだ、ずっと鳴っている（on）／鳴っていない（off）
        if "quieter_than" in c:
            # 止まってはいないが小さくなる所。1 秒ごとの平均がすべて、この dB より小さい
            return all(sec(c["stem"], t) < c["quieter_than"] for t in range(c["from"], c["to"]))
        on = [sec(c["stem"], t) > ON_DB for t in range(c["from"], c["to"])]
        return all(on) if c["state"] == "on" else not any(on)
    if "width_lines" in c:
        w = [lines[n]["vocal_width"] for n in c["width_lines"]]
        rest = [l["vocal_width"] for n, l in lines.items() if n not in c["width_lines"] and l["vocal_width"] is not None]
        ok = True
        if "below" in c:
            ok &= max(w) < c["below"]
        if "above" in c:
            ok &= min(w) > c["above"]
        if c.get("widest"):
            ok &= min(w) > max(rest)
        if c.get("narrowest"):
            ok &= max(w) < min(rest)
        return ok
    if "section_seconds" in c:
        dur = {x["name"]: x["end"] - x["start"] for x in a["sections"]}
        return all(abs(dur[n] - c["about"]) < c["tol"] for n in c["section_seconds"])
    if "sections_in_order" in c:
        names = [x["name"] for x in a["sections"]]
        want = c["sections_in_order"]
        return any(names[i : i + len(want)] == want for i in range(len(names)))
    if "section_count" in c:
        return sum(fig.section_core(x["name"]) == c["section_count"] for x in a["sections"] if x["kind"] == "vocal") == c["equals"]
    if "line_contains" in c:
        return lines[c["line_contains"]]["start"] < c["t"] < lines[c["line_contains"]]["end"]
    if "line_starts_within" in c:
        return 0 <= lines[c["line_starts_within"]]["start"] - c["after"] < c["sec"]
    if any(k in c for k in ("chord_seq", "home_in", "key_shift", "function_at")) and ch is None:
        raise SystemExit("和音の check があるのに chords.json が無い。先に chords.py を回す")
    if "chord_seq" in c:
        # 区間の中に、度数の並びがそのまま（同じ和音の続きは 1 つにまとめて）出てくる
        seq = [degree_core(h) for h in section_halfbars(ch, c["chord_seq"]) if h["degree"]]
        seq = [d for i, d in enumerate(seq) if i == 0 or d != seq[i - 1]]
        want = c["degrees"]
        return any(seq[i : i + len(want)] == want for i in range(len(seq)))
    if "home_in" in c:
        # 区間で家（Ⅰ）に着くか。none＝一度も着かない、some＝着く
        n = sum(h["function"] == "home" for h in section_halfbars(ch, c["home_in"]))
        return n == 0 if c["state"] == "none" else n > 0
    if "function_at" in c:
        # その秒の和音の役割
        h = next(h for h in ch["halfbars"] if h["t0"] <= c["function_at"] < h["t1"])
        return h["function"] == c["is"]
    if "key_shift" in c:
        # 2 つの区間のキーの差（半音の数。上がるが正）
        k = {s["name"]: s["key_tonic"] for s in ch["sections"]}
        d = (common.NOTES.index(k[c["key_shift"][1]]) - common.NOTES.index(k[c["key_shift"][0]])) % 12
        return (d if d <= 6 else d - 12) == c["semitones"]
    raise SystemExit(f"知らない種類の check: {c}")


def check(song: str) -> bool:
    """文面に書いた時刻・数値と歌詞の引用を、データと歌詞ファイルから出し直して突き合わせる。"""
    a = fig.load(song)
    story = json.loads((common.data_dir(song) / "story.json").read_text(encoding="utf-8"))
    use_threshold(story)
    ch = load_chords(song, story)
    raw = (LYRICS / f"{song}.md").read_text(encoding="utf-8").splitlines()
    tests = {}
    for p in story["points"]:
        tag = fig.mmss(p["time"])
        if not p.get("checks"):
            tests[f"{tag}: 事実を確かめる checks が書いてある"] = False
        for c in p.get("checks", []):
            tests[f"{tag}: {c['say']}"] = run_check(c, a, ch)
        for q in p["quotes"]:
            tests[f"{tag}: 引用「{q['text']}」が歌詞 {q['line_no']} 行目のとおり"] = raw[q["line_no"] - 1].strip() == q["text"]
        tests[f"{tag}: 場面の時刻が {p['section']} の中"] = any(x["name"] == p["section"] and x["start"] - 0.01 <= p["time"] < x["end"] for x in a["sections"])
    for name, ok in tests.items():
        print("OK " if ok else "NG ", name)
    return all(tests.values())


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if not check(args.song):
        raise SystemExit("文面とデータが合わない所がある。story.json を直す")
    if not args.check:
        out = common.work_dir(args.song)
        (out / "story.html").write_text(build(args.song), encoding="utf-8", newline="")
        asyncio.run(fig.capture(out / "story.html", out / "story.png"))
        shutil.copyfile(out / "story.png", common.data_dir(args.song) / "読み解き図.png")
