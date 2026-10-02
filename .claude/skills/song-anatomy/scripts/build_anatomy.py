#!/usr/bin/env python3
"""anatomy.json から解剖図（横長の帯）を作る。音源は読まない。

    python build_anatomy.py シーソーゲーム            # 図（anatomy.html と PNG）
    python build_anatomy.py シーソーゲーム --no-png   # HTML だけ

読むのは songs/analysis/anatomy/<曲名>/ の anatomy.json・series/stem_loudness.csv・owner_check.json だけ。
owner_check.json に書いた訂正は、機械の値に上書きして描く。
見た目と撮り方は articles/単発/18_12曲の地図/make_figure.py に合わせている。
"""
from __future__ import annotations

import argparse
import asyncio
import csv
import glob
import html
import json
import re
import shutil
from pathlib import Path

import common


W = 1152
LANE_H = 64
FLOOR_DB = -42.0  # これより小さい音は帯の底に張り付ける
STEMS = [("vocals", "ボーカル", "#d6006e"), ("drums", "ドラム", "#45383e"), ("bass", "ベース", "#2a6fd6"), ("other", "その他の楽器", "#1a9a8a")]


def load(song: str) -> dict:
    d = common.data_dir(song)
    a = json.loads((d / "anatomy.json").read_text(encoding="utf-8"))
    check = json.loads((d / "owner_check.json").read_text(encoding="utf-8")) if (d / "owner_check.json").exists() else {}
    for s in a["sections"]:
        fix = check.get("sections", {}).get(s["name"])
        if fix:
            s.update(fix, status="owner_confirmed")
    for l in a["lines"]:
        fix = check.get("lines", {}).get(str(l["line_no"]))
        if fix:
            l.update(fix, status="owner_confirmed")
    for m in a["modulation"]["items"]:
        fix = check.get("modulation", {}).get(m["section"])
        if fix:
            m.update(fix, status="owner_confirmed")
    if "items" in check.get("quiet", {}):
        a["quiet"]["items"] = [dict(q, status="owner_confirmed") for q in check["quiet"]["items"]]
    rows = list(csv.DictReader(open(d / a["series"]["stem_loudness"]["file"], encoding="utf-8")))
    a["_loudness"] = {k: [float(r[f"{k}_db"]) for r in rows] for k in ("mix", "vocals", "drums", "bass", "other")}
    a["_hop"] = a["series"]["stem_loudness"]["hop_sec"]
    return a


def mmss(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def section_core(name: str) -> str:
    """歌詞ファイルの構成名の揺れ（1A・Aメロ・2Bメロ・2番 Aメロ・Cメロ）を、A・B・C… にそろえる。"""
    return re.sub(r"^\d+(番\s*)?|メロ$", "", name)


def section_class(s: dict) -> str:
    if s["kind"] == "instrumental":
        return "inst"
    core = section_core(s["name"])
    return "chorus" if "サビ" in core else "b" if core == "B" else "c" if core in ("C", "D") else "a"


def display_name(name: str) -> str:
    """図に出す呼び名。番号を外し、サビはどれも「サビ」にする（落ちサビは残す）。"""
    core = section_core(name)
    if core in ("A", "B", "C", "D"):
        return f"{core} メロ"
    return "サビ" if core in ("サビ", "ラスサビ") else core


def area(values: list[float], hop: float, x, y0: float, peak: float) -> str:
    """0.5 秒ごとの平均にならして、帯の中の面グラフにする。"""
    step = max(1, int(0.5 / hop))
    pts = []
    for i in range(0, len(values), step):
        chunk = values[i : i + step]
        v = sum(chunk) / len(chunk) - peak
        h = max(0.0, min(1.0, (v - FLOOR_DB) / -FLOOR_DB)) * (LANE_H - 8)
        pts.append((x(i * hop + 0.25), y0 + LANE_H - h))
    path = f"M{pts[0][0]:.1f},{y0 + LANE_H:.1f} " + " ".join(f"L{px:.1f},{py:.1f}" for px, py in pts)
    return path + f" L{pts[-1][0]:.1f},{y0 + LANE_H:.1f} Z"


def build_svg(a: dict) -> tuple[str, int]:
    e = html.escape
    dur = a["duration_sec"]
    x = lambda t: W * t / dur
    parts: list[str] = []
    y = 0

    # 時刻の目盛り
    for t in range(0, int(dur) + 1, 30):
        parts.append(f'<text class="tick" x="{x(t):.1f}" y="{y + 14}" text-anchor="{"start" if t == 0 else "middle"}">{mmss(t)}</text>')
    y += 24

    # 構成
    sec_y = y
    for s in a["sections"]:
        x0, x1 = x(s["start"]), x(s["end"])
        cls = section_class(s)
        parts.append(f'<rect class="sec {cls}" x="{x0 + 1:.1f}" y="{y}" width="{max(x1 - x0 - 2, 1):.1f}" height="44"/>')
        size = 17 if x1 - x0 > len(s["name"]) * 18 else 12
        if x1 - x0 > len(s["name"]) * 11:
            parts.append(f'<text class="secname {cls}" x="{(x0 + x1) / 2:.1f}" y="{y + 28}" text-anchor="middle" font-size="{size}">{e(s["name"])}</text>')
    y += 44
    # 区間の頭の時刻
    for s in a["sections"]:
        if s["kind"] == "vocal":
            parts.append(f'<text class="sectime" x="{x(s["start"]) + 2:.1f}" y="{y + 16}">{mmss(s["start"])}</text>')
    y += 26

    # 歌詞の行（頭の位置に印）
    for l in a["lines"]:
        parts.append(f'<rect class="line" x="{x(l["start"]):.1f}" y="{y}" width="{max(x(l["end"]) - x(l["start"]) - 1, 1.5):.1f}" height="10"/>')
    lines_y = y
    y += 26

    # ステムごとの音量
    lanes_top = y
    peak = max(a["_loudness"]["mix"])
    for key, label, color in STEMS:
        parts.append(f'<rect class="lane" x="0" y="{y}" width="{W}" height="{LANE_H}"/>')
        parts.append(f'<path d="{area(a["_loudness"][key], a["_hop"], x, y, peak)}" fill="{color}"/>')
        parts.append(f'<text class="lanename" x="8" y="{y + 18}" fill="{color}">{label}</text>')
        y += LANE_H + 8
    lanes_bottom = y - 8

    # 静かになる所
    for q in a["quiet"]["items"]:
        if q["start"] < 1 or q["end"] > dur - 1:
            continue  # 曲の頭と終わりは、静かで当たり前なので印を付けない
        parts.append(f'<rect class="quiet" x="{x(q["start"]):.1f}" y="{lanes_top}" width="{x(q["end"]) - x(q["start"]):.1f}" height="{lanes_bottom - lanes_top}"/>')
        parts.append(f'<text class="note" x="{(x(q["start"]) + x(q["end"])) / 2:.1f}" y="{lanes_bottom + 20}" text-anchor="middle">ドラムが抜ける {mmss(q["start"])}〜{mmss(q["end"])}</text>')

    # 構成の境目を下まで通す
    for s in a["sections"][1:]:
        parts.append(f'<line class="cut" x1="{x(s["start"]):.1f}" y1="{sec_y}" x2="{x(s["start"]):.1f}" y2="{lanes_bottom}"/>')

    # 転調
    for m in a["modulation"]["items"]:
        if m["semitones_up"] == 0:
            continue
        up = m["semitones_up"] if m["semitones_up"] <= 6 else m["semitones_up"] - 12
        mark = "" if m["status"] == "owner_confirmed" else "（未確認）"
        word = f"半音 {abs(up)} つ{'上がる' if up > 0 else '下がる'}"
        parts.append(f'<line class="mod" x1="{x(m["start"]):.1f}" y1="{sec_y - 4}" x2="{x(m["start"]):.1f}" y2="{lanes_bottom}"/>')
        parts.append(f'<text class="note mod" x="{x(m["start"]) - 6:.1f}" y="{lanes_bottom + 20}" text-anchor="end">{e(m["section"])}で{word}{mark}</text>')
    y += 34

    # ソロ／全員の見当
    # 2 つに割り切れるほど値が分かれないので、行ごとの値をそのまま棒の高さにする
    parts.append(f'<text class="lanename plain" x="0" y="{y + 12}" fill="#71646b">声の左右の広がり（実験。高いほど広い）</text>')
    y += 22
    top = max(l["vocal_width"] or 0 for l in a["lines"])
    parts.append(f'<line class="base" x1="0" y1="{y + 40}" x2="{W}" y2="{y + 40}"/>')
    for l in a["lines"]:
        if l.get("vocal_width") is not None:
            h = 4 + 36 * l["vocal_width"] / top
            parts.append(f'<rect class="voice {l["voices_guess"]}" x="{x(l["start"]):.1f}" y="{y + 40 - h:.1f}" width="{max(x(l["end"]) - x(l["start"]) - 1, 1.5):.1f}" height="{h:.1f}"/>')
    y += 48
    return f'<svg viewBox="0 0 {W} {y}" width="{W}" height="{y}">' + "\n".join(parts) + "</svg>", lines_y


PAGE = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<style>
:root { --primary:#d6006e; --blue:#2a6fd6; --ink:#1d1216; --body:#45383e; --muted:#71646b; --muted-soft:#998a92;
  --axis:#dcc8d2; --canvas:#ffffff; --soft:#f7f1f4; }
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--canvas); font-family:"Noto Sans JP",sans-serif; color:var(--body); }
#fig { width:1280px; padding:56px 64px 44px; background:var(--canvas); }
.eyebrow { color:var(--primary); font-weight:700; font-size:15px; letter-spacing:.08em; }
h1 { color:var(--ink); font-size:34px; font-weight:700; letter-spacing:-.015em; margin:6px 0 8px; }
.lead { font-size:16px; color:var(--muted); margin-bottom:22px; }
.legend { display:flex; flex-wrap:wrap; gap:8px 24px; font-size:14px; color:var(--body); margin-top:14px; }
.legend span { display:inline-flex; align-items:center; gap:8px; }
.key { display:inline-block; width:22px; height:12px; }
svg { display:block; }
.tick { font-size:13px; fill:var(--muted-soft); }
.sec.a { fill:#eadfe5; } .sec.b { fill:#cfdff7; } .sec.c { fill:#d3ece8; } .sec.chorus { fill:var(--primary); } .sec.inst { fill:var(--soft); }
.secname { font-weight:700; fill:var(--ink); } .secname.chorus { fill:#fff; } .secname.inst { fill:var(--muted-soft); font-weight:500; }
.sectime { font-size:12px; fill:var(--muted); }
.line { fill:var(--muted-soft); }
.lane { fill:var(--soft); }
.lanename { font-size:14px; font-weight:700; paint-order:stroke; stroke:var(--soft); stroke-width:4px; }
.cut { stroke:var(--canvas); stroke-width:2; opacity:.9; }
.quiet { fill:var(--ink); opacity:.08; }
.mod { stroke:var(--ink); stroke-width:2; stroke-dasharray:5 4; }
.note { font-size:14px; font-weight:700; fill:var(--ink); } .note.mod { stroke:none; }
.lanename.plain { stroke:none; font-weight:500; }
.base { stroke:var(--axis); stroke-width:1; }
.voice.wide { fill:var(--muted-soft); } .voice.narrow { fill:var(--ink); }
.foot { margin-top:18px; font-size:13px; color:var(--muted); line-height:1.7; }
</style></head><body><div id="fig">
<div class="eyebrow">SONG ANATOMY ／ 試作</div>
<h1>__TITLE__</h1>
<p class="lead">__LEAD__</p>
__SVG__
<div class="legend">__LEGEND__</div>
<p class="foot">__FOOT__</p>
</div></body></html>"""


def build(song: str) -> str:
    a = load(song)
    svg, _ = build_svg(a)
    confirmed = all(s["status"] == "owner_confirmed" for s in a["sections"] if s["kind"] == "vocal")
    legend = (
        '<span><i class="key" style="background:#d6006e"></i>サビ</span>'
        '<span><i class="key" style="background:#cfdff7"></i>B メロ</span>'
        '<span><i class="key" style="background:#eadfe5"></i>A メロ</span>'
        '<span><i class="key" style="background:#d3ece8"></i>C メロ</span>'
        '<span><i class="key" style="background:#f7f1f4;outline:1px solid #dcc8d2"></i>歌の無い所</span>'
        '<span><i class="key" style="background:#998a92;height:6px"></i>歌詞の 1 行</span>'
        '<span><i class="key" style="background:#1d1216"></i>声が真ん中に集まる行</span>'
    )
    foot = (
        "音源を機械でボーカル・ドラム・ベース・その他に分け、それぞれの音量を 0.5 秒ごとに描いたもの。"
        f"構成の境目は、歌詞を歌声に機械で時刻合わせした結果{'（管理人が耳で確認済み）' if confirmed else 'で、耳での確認はまだです'}。"
        "「声の広がり」は、ソロと全員の切り替わりの見当を付けるための実験で、誰が歌っているかは分かりません。"
        f"ファンによる非公式の図です。解析日: {a['analyzed_at']}。作図: AIぽっぱー"
    )
    out = PAGE
    for key, value in (
        ("TITLE", f"「{html.escape(song)}」の解剖図"),
        ("LEAD", f"横は時間（0:00〜{mmss(a['duration_sec'])}）。上から、曲の構成、歌詞の行、楽器ごとの音量。"),
        ("SVG", svg),
        ("LEGEND", legend),
        ("FOOT", foot),
    ):
        out = out.replace(f"__{key}__", value)
    return out


async def capture(src: Path, dst: Path) -> None:
    from playwright.async_api import async_playwright

    exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    async with async_playwright() as p:
        if exe:
            browser = await p.chromium.launch(executable_path=exe[-1], args=["--no-sandbox"])
        else:
            try:
                browser = await p.chromium.launch()
            except Exception:
                browser = await p.chromium.launch(channel="chrome")
        page = await browser.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        await page.goto(src.as_uri())
        await page.evaluate("document.fonts.ready")
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("DOM.enable")
        await cdp.send("CSS.enable")
        doc = await cdp.send("DOM.getDocument")
        node = await cdp.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": "h1"})
        fonts = await cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})
        used = [f["familyName"] for f in fonts["fonts"]]
        if not any("Noto Sans JP" in f or "Noto Sans CJK JP" in f for f in used):
            raise SystemExit(f"描画フォントが Noto Sans JP ではない: {used}")
        await page.locator("#fig").screenshot(path=str(dst))
        print("書き出し:", dst, "／描画フォント:", used)
        await browser.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("song")
    ap.add_argument("--no-png", action="store_true")
    args = ap.parse_args()
    out = common.work_dir(args.song)
    (out / "anatomy.html").write_text(build(args.song), encoding="utf-8", newline="")
    if not args.no_png:
        asyncio.run(capture(out / "anatomy.html", out / "anatomy.png"))
        shutil.copyfile(out / "anatomy.png", common.data_dir(args.song) / "解剖図.png")
