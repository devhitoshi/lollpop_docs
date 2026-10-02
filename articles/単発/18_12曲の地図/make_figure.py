#!/usr/bin/env python3
"""12 曲の位置（かわいい↔かっこいい × 湧き↔エモい）を note 用の PNG にする。

    bash resources/install_capture_font.sh   # リモート環境では毎回
    pip install playwright
    python3 articles/単発/18_12曲の地図/make_figure.py

songs/analysis/song_character.csv を読み、fig_map.html・fig_gap.html を書いてから
img/01_map.png（12 曲の地図）と img/02_gap.png（音と歌詞のずれ）を撮る（1280幅・2倍）。
描画フォントが Noto Sans JP でなければ中断する。

曲の位置を直すときは、この図ではなく songs/analysis/character/ を直して
`.claude/skills/music-analysis/scripts/build_character.py` を先に実行する。
"""
from __future__ import annotations

import asyncio
import csv
import glob
import html
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CSV = ROOT / "songs" / "analysis" / "song_character.csv"

# 図の座標系（#fig の内側 1152px に合わせる）
W, H = 1152, 920
SPAN_X, SPAN_Y = 3.75, 3.5
# 上下の帯は軸と四隅の言葉の置き場。曲の点と曲名はここに入れない
BAND = 50

# 音と歌詞がこれ以上離れている曲を、ずれの図で目立たせる
GAP_LIMIT = 2.0

# 曲名の置き場所を手で決める曲。(点からの横ずれ, 縦ずれ, 揃え)。書いていない曲は自動で置く。
# 左下の 3 曲は点がほぼ重なり、自動では曲名どうしがぶつかる。位置が変わったらここを直す
LABEL_OVERRIDES: dict[str, tuple[float, float, str]] = {
    "メイク☆マイダンス": (40, 6, "start"),
    "ぽっぽ♪ポジティブ！！": (26, 46, "start"),
}


def px(v: float) -> float:
    return W * (v + SPAN_X) / (2 * SPAN_X)


def py(v: float) -> float:
    return BAND + (H - 2 * BAND) * (SPAN_Y - v) / (2 * SPAN_Y)


def load() -> list[dict]:
    songs = []
    for r in csv.DictReader(open(CSV, encoding="utf-8")):
        songs.append(
            {
                "song": r["song"],
                "sound": (float(r["sound_cute_cool"]), float(r["sound_waki_emo"])),
                "lyrics": (float(r["lyrics_cute_cool"]), float(r["lyrics_waki_emo"])),
                "distance": float(r["sound_lyrics_distance"]),
                "built_at": r["built_at"],
            }
        )
    return songs


def text_width(text: str, size: float) -> float:
    return sum(size * (0.36 if c in "! " else 0.58 if ord(c) < 128 else 1.02) for c in text)


def overlap(a, b) -> bool:
    return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]


def fixed_obstacles() -> list[tuple]:
    """軸の端の言葉と、軸の線。曲名をここに重ねない。"""
    mx, my = px(0), py(0)
    return [
        (0, my - 44, 190, my - 6), (W - 200, my - 44, W, my - 6),
        (mx - 3, 0, mx + 3, H), (0, my - 3, W, my + 3),
    ]


def place_labels(songs: list[dict], size: float, obstacles: list[tuple], only=None) -> None:
    """曲名を点の周りの候補位置から、ほかの点・文字との重なりが最も少ない位置に置く。"""
    boxes = list(obstacles)
    targets = [s for s in songs if only is None or s["song"] in only]
    # 手で置く曲名を先に確定させて、自動で置く曲名がそれを避けるようにする
    for s in sorted(targets, key=lambda s: (s["song"] not in LABEL_OVERRIDES, -s["sound"][1], s["sound"][0])):
        x, y = px(s["sound"][0]), py(s["sound"][1])
        w, h = text_width(s["song"], size) + 8, size * 1.25
        if s["song"] in LABEL_OVERRIDES:
            dx, dy, anchor = LABEL_OVERRIDES[s["song"]]
            bx = x + dx - {"start": 0, "end": w, "middle": w / 2}[anchor]
            box = (bx, y + dy - h / 2, bx + w, y + dy + h / 2)
        else:
            g = 20
            candidates = [
                (x + g, y - h / 2, "start"), (x - g - w, y - h / 2, "end"),
                (x - w / 2, y - g - h, "middle"), (x - w / 2, y + g, "middle"),
                (x + g * 0.7, y - g * 0.7 - h, "start"), (x + g * 0.7, y + g * 0.7, "start"),
                (x - g * 0.7 - w, y - g * 0.7 - h, "end"), (x - g * 0.7 - w, y + g * 0.7, "end"),
                (x + g, y + g * 1.6, "start"), (x - w / 2, y + g * 2.6, "middle"), (x - w / 2, y - g * 2.6 - h, "middle"),
                (x + g * 2.2, y - h / 2, "start"),
            ]
            best = None
            for bx, by, anchor in candidates:
                bx = min(max(bx, 2), W - 2 - w)
                by = min(max(by, BAND), H - BAND - h)
                box = (bx, by, bx + w, by + h)
                clashes = sum(overlap(box, b) for b in boxes)
                if best is None or clashes < best[0]:
                    best = (clashes, box, anchor)
                if clashes == 0:
                    break
            _, box, anchor = best
        boxes.append(box)
        tx = {"start": box[0] + 4, "end": box[2] - 4, "middle": (box[0] + box[2]) / 2}[anchor]
        s["label"] = (tx, box[1] + size * 0.95, anchor)


def spread_lyrics(songs: list[dict]) -> None:
    """歌詞の位置は整数で重なるので、ほかの点と重なる所は少しずらして描く。"""
    used = [s["sound"] for s in songs]
    for s in songs:
        x, y = s["lyrics"]
        while any(abs(x - u[0]) < 0.22 and abs(y - u[1]) < 0.22 for u in used):
            x, y = x + 0.26, y - 0.14
        used.append((x, y))
        s["lyrics_draw"] = (x, y)


def frame() -> list[str]:
    mx, my = px(0), py(0)
    return [
        f'<line class="axis" x1="0" y1="{my:.1f}" x2="{W}" y2="{my:.1f}"/>',
        f'<line class="axis" x1="{mx:.1f}" y1="0" x2="{mx:.1f}" y2="{H}"/>',
        f'<text class="end" x="0" y="{my - 16:.1f}" text-anchor="start">← かわいい</text>',
        f'<text class="end" x="{W}" y="{my - 16:.1f}" text-anchor="end">かっこいい →</text>',
        f'<text class="end" x="{mx + 14:.1f}" y="28" text-anchor="start">↑ エモい</text>',
        f'<text class="end" x="{mx + 14:.1f}" y="{H - 8}" text-anchor="start">↓ 湧き</text>',
        '<text class="corner" x="0" y="24" text-anchor="start">かわいくてエモい</text>',
        f'<text class="corner" x="{W}" y="24" text-anchor="end">かっこよくてエモい</text>',
        f'<text class="corner" x="0" y="{H - 8}" text-anchor="start">かわいくて湧く</text>',
        f'<text class="corner" x="{W}" y="{H - 8}" text-anchor="end">かっこよくて湧く</text>',
    ]


def svg_map(songs: list[dict]) -> str:
    e = html.escape
    obstacles = fixed_obstacles()
    for s in songs:
        x, y = px(s["sound"][0]), py(s["sound"][1])
        obstacles.append((x - 15, y - 15, x + 15, y + 15))
    place_labels(songs, 25, obstacles)
    parts = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}">'] + frame()
    for s in songs:
        if s["song"] in LABEL_OVERRIDES:
            # 手で置いた曲名は点から離れるので、どの点の名前かを細い線でつなぐ
            lx, ly, _ = s["label"]
            parts.append(f'<line class="leader" x1="{px(s["sound"][0]):.1f}" y1="{py(s["sound"][1]):.1f}" x2="{lx + 6:.1f}" y2="{ly - 9:.1f}"/>')
    for s in songs:
        parts.append(f'<circle class="dot sound" cx="{px(s["sound"][0]):.1f}" cy="{py(s["sound"][1]):.1f}" r="12"/>')
    for s in songs:
        lx, ly, anchor = s["label"]
        parts.append(f'<text class="name" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{e(s["song"])}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


def svg_gap(songs: list[dict]) -> str:
    e = html.escape
    spread_lyrics(songs)
    far = {s["song"] for s in songs if s["distance"] >= GAP_LIMIT}
    obstacles = fixed_obstacles()
    for s in songs:
        (x1, y1), (x2, y2) = (px(s["sound"][0]), py(s["sound"][1])), (px(s["lyrics_draw"][0]), py(s["lyrics_draw"][1]))
        obstacles.append((x1 - 15, y1 - 15, x1 + 15, y1 + 15))
        obstacles.append((x2 - 12, y2 - 12, x2 + 12, y2 + 12))
        # 線の上にも曲名を置かない
        steps = max(2, int(((x2 - x1) ** 2 + (y2 - y1) ** 2) ** 0.5 // 14))
        for i in range(1, steps):
            cx, cy = x1 + (x2 - x1) * i / steps, y1 + (y2 - y1) * i / steps
            obstacles.append((cx - 7, cy - 7, cx + 7, cy + 7))
    # 曲名を出すのは離れている曲だけ。近い曲は薄い点のままにして、名前は地図の図で見てもらう
    place_labels(songs, 25, obstacles, only=far)

    parts = [f'<svg viewBox="0 0 {W} {H}" width="{W}" height="{H}">'] + frame()
    for group in (False, True):
        for s in songs:
            if (s["song"] in far) != group:
                continue
            cls = "far" if group else "near"
            x1, y1, x2, y2 = px(s["sound"][0]), py(s["sound"][1]), px(s["lyrics_draw"][0]), py(s["lyrics_draw"][1])
            parts.append(f'<line class="link {cls}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
            parts.append(f'<circle class="dot lyrics {cls}" cx="{x2:.1f}" cy="{y2:.1f}" r="{10 if group else 7}"/>')
            parts.append(f'<circle class="dot sound {cls}" cx="{x1:.1f}" cy="{y1:.1f}" r="{12 if group else 8}"/>')
    for s in songs:
        if s["song"] in far:
            lx, ly, anchor = s["label"]
            parts.append(f'<text class="name" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{e(s["song"])}</text>')
    parts.append("</svg>")
    return "\n".join(parts)


PAGE = """<!doctype html><html lang="ja"><head><meta charset="utf-8">
<style>
:root { --primary:#d6006e; --blue:#2a6fd6; --ink:#1d1216; --body:#45383e; --muted:#71646b; --muted-soft:#998a92;
  --axis:#dcc8d2; --canvas:#ffffff; }
* { margin:0; padding:0; box-sizing:border-box; }
body { background:var(--canvas); font-family:"Noto Sans JP",sans-serif; color:var(--body); }
#fig { width:1280px; padding:56px 64px 44px; background:var(--canvas); }
.eyebrow { color:var(--primary); font-weight:700; font-size:15px; letter-spacing:.08em; }
h1 { color:var(--ink); font-size:34px; font-weight:700; letter-spacing:-.015em; margin:6px 0 8px; }
.lead { font-size:16px; color:var(--muted); margin-bottom:18px; }
.legend { display:flex; gap:28px; font-size:16px; color:var(--body); margin-bottom:18px; }
.legend span { display:inline-flex; align-items:center; gap:8px; }
.key { display:inline-block; width:16px; height:16px; border-radius:50%; }
.key.sound { background:var(--primary); } .key.lyrics { background:var(--blue); width:13px; height:13px; }
svg { display:block; }
.axis { stroke:var(--axis); stroke-width:2; }
.end { font-size:22px; font-weight:700; fill:var(--body); }
.corner { font-size:16px; font-weight:500; fill:var(--muted-soft); letter-spacing:.04em; }
.dot { stroke:var(--canvas); stroke-width:3; }
.dot.sound { fill:var(--primary); } .dot.lyrics { fill:var(--blue); }
.dot.near { opacity:.38; }
.leader { stroke:var(--muted-soft); stroke-width:2; }
.link { stroke-linecap:round; }
.link.near { stroke:var(--axis); stroke-width:2; }
.link.far { stroke:var(--ink); stroke-width:3; }
.name { font-size:25px; font-weight:700; fill:var(--ink); paint-order:stroke; stroke:var(--canvas); stroke-width:7px; stroke-linejoin:round; }
.foot { margin-top:22px; font-size:13px; color:var(--muted); line-height:1.7; }
</style></head><body><div id="fig">
<div class="eyebrow">__EYEBROW__</div>
<h1>__TITLE__</h1>
<p class="lead">__LEAD__</p>
__LEGEND__
__SVG__
<p class="foot">__FOOT__</p>
</div></body></html>"""

FOOT = (
    "音の位置は、音声を聴ける AI に曲名を伏せて 2 回聴かせ、食い違った所を人が耳で確かめたもの。測定値ではなく印象です。"
    "ファンによる非公式の見立てで、公式の分類ではありません。対象は配信されているオリジナル曲 {n} 曲（{date}時点）。{extra}作図: AIぽっぱー"
)


def page(eyebrow: str, title: str, lead: str, legend: str, svg: str, foot: str) -> str:
    out = PAGE
    for key, value in (("EYEBROW", eyebrow), ("TITLE", title), ("LEAD", lead), ("LEGEND", legend), ("SVG", svg), ("FOOT", foot)):
        out = out.replace(f"__{key}__", value)
    return out


def build() -> dict[str, str]:
    songs = load()
    y, m, d = songs[0]["built_at"].split("-")
    date = f"{y}年{int(m)}月{int(d)}日"
    n_far = sum(s["distance"] >= GAP_LIMIT for s in songs)
    return {
        "fig_map.html": page(
            "SONG MAP",
            f"ろりぽっぷ!!!!!!! {len(songs)}曲の地図",
            "横は「かわいい ↔ かっこいい」、縦は「湧き ↔ エモい」。音を聴いた印象で並べました。",
            "",
            svg_map(songs),
            FOOT.format(n=len(songs), date=date, extra=""),
        ),
        "fig_gap.html": page(
            "SOUND × LYRICS",
            "音と歌詞は、同じ場所にいるか",
            f"ピンクが音、青が歌詞。線が長いほど、音の印象と歌詞の内容が離れています。濃いのは離れている {n_far} 曲、薄いのは近い {len(songs) - n_far} 曲。",
            '<div class="legend"><span><i class="key sound"></i>音（聴いた印象）</span><span><i class="key lyrics"></i>歌詞（読んだ印象）</span></div>',
            svg_gap(songs),
            FOOT.format(n=len(songs), date=date, extra="歌詞の位置は歌詞だけを読んで付けたもの。点が重なる所は少しずらして描いています。"),
        ),
    }


async def capture(names: dict[str, str]) -> None:
    from playwright.async_api import async_playwright

    exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    async with async_playwright() as p:
        if exe:
            browser = await p.chromium.launch(executable_path=exe[-1], args=["--no-sandbox"])
        else:
            try:
                browser = await p.chromium.launch()
            except Exception:
                # Playwright 用の Chromium が無い PC では、入っている Chrome を使う
                browser = await p.chromium.launch(channel="chrome")
        page = await browser.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        for src, dst in names.items():
            await page.goto((HERE / src).as_uri())
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
            await page.locator("#fig").screenshot(path=str(HERE / "img" / dst))
            print("書き出し:", (HERE / "img" / dst).relative_to(ROOT), "／描画フォント:", used)
        await browser.close()


if __name__ == "__main__":
    for name, text in build().items():
        (HERE / name).write_text(text, encoding="utf-8", newline="")
    (HERE / "img").mkdir(exist_ok=True)
    asyncio.run(capture({"fig_map.html": "01_map.png", "fig_gap.html": "02_gap.png"}))
