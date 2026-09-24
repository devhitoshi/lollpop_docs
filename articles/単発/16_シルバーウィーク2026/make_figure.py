#!/usr/bin/env python3
"""シルバーウィーク5本の披露曲を点の表にして PNG にする（note は表が使えないため）。

    bash resources/install_capture_font.sh   # リモート環境では毎回
    pip install playwright
    python3 articles/単発/16_シルバーウィーク2026/make_figure.py

events/data_event.csv から 9/19〜9/23 の公演を読み、fig_setlist.html を書いてから
img/01_setlist.png（1280幅・2倍）を撮る。描画フォントが Noto Sans JP でなければ中断する。
"""
from __future__ import annotations

import asyncio
import csv
import glob
import html
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CSV = ROOT / "events" / "data_event.csv"
HTML_OUT = HERE / "fig_setlist.html"
PNG_OUT = HERE / "img" / "01_setlist.png"

# 列見出し（日付・会場の短縮）。CSV の並びと同じ順にする
LABELS = {
    ("2026-09-19", "白金高輪SELENE b2"): ("9/19 土", "白金高輪"),
    ("2026-09-20", "池袋W:IKE329"): ("9/20 日", "池袋・単独"),
    ("2026-09-22", "青山RizM"): ("9/22 火祝", "青山"),
    ("2026-09-23", "大塚FUTURE"): ("9/23 水祝", "大塚"),
    ("2026-09-23", "SHIBUYA CYCLONE"): ("9/23 水祝", "渋谷"),
}
ORDER = list(LABELS)


def load():
    shows = {}
    for r in csv.DictReader(open(CSV, encoding="utf-8")):
        key = (r["date"], r["venue"])
        if key in LABELS:
            songs = []
            for item in r["setlist"].split(";"):
                item = item.strip()
                if item[:2].isdigit():
                    songs.append((int(item[:2]), item[3:].strip()))
            shows[key] = songs
    return [shows[k] for k in ORDER]


def build(shows) -> str:
    songs = {}  # 表示名 -> {列: 曲順}
    first = {}
    for ci, setlist in enumerate(shows):
        for no, raw in setlist:
            name = raw.replace("🆕", "").strip()
            songs.setdefault(name, {})[ci] = no
            first.setdefault(name, (ci, no))
    names = sorted(songs, key=lambda n: (-len(songs[n]), first[n]))
    total = sum(len(s) for s in shows)
    head = "".join(
        f'<th><span class="d">{html.escape(d)}</span><span class="v">{html.escape(v)}</span></th>'
        for d, v in (LABELS[k] for k in ORDER)
    )
    rows = []
    for n in names:
        cells = "".join(
            f'<td><span class="dot">{songs[n][ci]}</span></td>' if ci in songs[n] else '<td><span class="none"></span></td>'
            for ci in range(len(shows))
        )
        c = len(songs[n])
        new = '<span class="tag">NEW</span>' if n == "また会う日まで" else ""
        rows.append(
            f'<tr><th class="song">{html.escape(n)}{new}</th>{cells}'
            f'<td class="cnt"><span class="bar" style="width:{c * 22}px"></span><b>{c}</b></td></tr>'
        )
    return f"""<!doctype html><html lang="ja"><head><meta charset="utf-8">
<style>
:root {{ --primary:#d6006e; --ink:#1d1216; --body:#45383e; --muted:#71646b; --hairline:#f2e2ea;
  --blush:#fbe7f0; --canvas:#ffffff; }}
* {{ margin:0; padding:0; box-sizing:border-box; }}
body {{ background:var(--canvas); font-family:"Noto Sans JP",sans-serif; color:var(--body); }}
#fig {{ width:1280px; padding:56px 64px 44px; background:var(--canvas); }}
.eyebrow {{ color:var(--primary); font-weight:700; font-size:15px; letter-spacing:.08em; }}
h1 {{ color:var(--ink); font-size:34px; font-weight:700; letter-spacing:-.015em; margin:6px 0 8px; }}
.lead {{ font-size:16px; color:var(--muted); margin-bottom:28px; }}
table {{ border-collapse:collapse; width:100%; }}
thead th {{ padding:0 0 12px; font-weight:700; text-align:center; width:112px; }}
thead th.song {{ text-align:left; width:auto; }}
thead th.cnt {{ text-align:left; width:170px; color:var(--muted); font-size:13px; }}
.d {{ display:block; font-size:13px; color:var(--muted); font-weight:500; }}
.v {{ display:block; font-size:16px; color:var(--ink); }}
tbody tr {{ border-top:1px solid var(--hairline); }}
tbody tr:nth-child(odd) {{ background:#fff5f9; }}
tbody th.song {{ text-align:left; font-size:17px; font-weight:700; color:var(--ink); padding:9px 12px 9px 8px; white-space:nowrap; }}
td {{ text-align:center; padding:7px 0; }}
.dot {{ display:inline-flex; align-items:center; justify-content:center; width:30px; height:30px; border-radius:50%;
  background:var(--primary); color:#fff; font-size:14px; font-weight:700; }}
.none {{ display:inline-block; width:8px; height:8px; border-radius:50%; background:#dcc8d2; }}
td.cnt {{ text-align:left; padding-left:18px; white-space:nowrap; }}
.bar {{ display:inline-block; height:14px; background:#ee8abc; border-radius:0 4px 4px 0; vertical-align:middle; margin-right:10px; }}
td.cnt b {{ color:var(--ink); font-size:17px; vertical-align:middle; }}
.tag {{ display:inline-block; margin-left:10px; padding:1px 8px; font-size:12px; color:#fff; background:var(--ink); border-radius:4px; vertical-align:2px; }}
.foot {{ margin-top:22px; font-size:13px; color:var(--muted); line-height:1.7; }}
</style></head><body><div id="fig">
<div class="eyebrow">SILVER WEEK 2026</div>
<h1>シルバーウィーク5本で歌った曲</h1>
<p class="lead">ろりぽっぷ!!!!!!!　2026年9月19日〜23日の5公演・のべ{total}曲。丸の中の数字はその日の曲順。</p>
<table><thead><tr><th class="song"></th>{head}<th class="cnt">披露回数</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<p class="foot">9/21（月祝）の出演予定は台風の影響でイベント中止。9/20 の単独ライブは日向なのマネージャーの生誕編で、なのちゃんとのコラボ曲を含む。<br>
出典: 公式 X（@lollipop_1116）のセトリ投稿をまとめた events/data_event.csv。曲名はセトリ投稿の表記のまま。</p>
</div></body></html>"""


async def capture():
    from playwright.async_api import async_playwright

    exe = sorted(glob.glob("/opt/pw-browsers/chromium-*/chrome-linux/chrome"))
    async with async_playwright() as p:
        browser = await p.chromium.launch(executable_path=exe[-1] if exe else None, args=["--no-sandbox"])
        page = await browser.new_page(viewport={"width": 1280, "height": 800}, device_scale_factor=2)
        await page.goto(HTML_OUT.as_uri())
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
        print("描画フォント:", used)
        await page.locator("#fig").screenshot(path=str(PNG_OUT))
        await browser.close()


if __name__ == "__main__":
    HTML_OUT.write_text(build(load()), encoding="utf-8")
    PNG_OUT.parent.mkdir(exist_ok=True)
    asyncio.run(capture())
    print("書き出し:", PNG_OUT.relative_to(ROOT))
