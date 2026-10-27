#!/usr/bin/env python3
"""fig_infographic.html の節ごとに img/ へ PNG（1080幅・2倍）を撮る。

    python articles/単発/20_告知が過去最多/make_figure.py

数字や文言を変えるときは HTML を直してから撮り直す（集計は claude-work/20261027_単独ライブ告知の比較更新/analyze.py）。
描画フォントが Noto Sans JP でなければ中断する。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
HTML = HERE / "fig_infographic.html"
# 節の id → 画像ファイル名（00 は見出し画像用、01〜05 は本文の【画像①】〜【画像⑤】）
SECTIONS = {
    "top": "00_top.png",
    "count": "01_count.png",
    "timing": "02_timing.png",
    "members": "03_members.png",
    "variety": "04_themes.png",
    "video": "05_video.png",
}


async def main() -> None:
    (HERE / "img").mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 800}, device_scale_factor=2)
        await page.goto(HTML.as_uri(), wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("DOM.enable")
        await cdp.send("CSS.enable")
        doc = await cdp.send("DOM.getDocument")
        for sel in ["h1", ".row .name", ".lead"]:
            node = await cdp.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": sel})
            fonts = await cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})
            names = [f["familyName"] for f in fonts["fonts"]]
            if not any("Noto Sans JP" in n for n in names):
                raise SystemExit(f"{sel} の描画フォントが Noto Sans JP ではない: {names}")
        for sec, name in SECTIONS.items():
            await page.locator(f"#{sec}").screenshot(path=str(HERE / "img" / name))
            print(HERE / "img" / name)
        await browser.close()


asyncio.run(main())
