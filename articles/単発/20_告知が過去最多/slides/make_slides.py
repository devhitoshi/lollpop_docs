#!/usr/bin/env python3
"""slides.html の4枚を PNG（1920×1080）と PDF（4ページ）に書き出す。

    python articles/単発/20_告知が過去最多/slides/make_slides.py

数字や文言を変えるときは slides.html を直してから撮り直す（集計の正は claude-work/20261027_単独ライブ告知の比較更新/）。
描画フォントが Noto Sans JP（見出し・本文）と Mochiy Pop One（ワードマーク）でなければ中断する。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
HTML = HERE / "slides.html"
SLIDES = ["s1", "s2", "s3", "s4"]
# セレクタ → 描画されていなければならない書体
FONT_CHECKS = {
    "#s1 h1": "Noto Sans JP",
    "#s1 .sub": "Noto Sans JP",
    "#s1 .foot": "Noto Sans JP",
    "#s1 svg text": "Noto Sans JP",
    "#s1 .wordmark": "Mochiy Pop One",
}


async def check_fonts(page) -> None:
    cdp = await page.context.new_cdp_session(page)
    await cdp.send("DOM.enable")
    await cdp.send("CSS.enable")
    doc = await cdp.send("DOM.getDocument", {"depth": -1})
    for sel, want in FONT_CHECKS.items():
        node = await cdp.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": sel})
        fonts = await cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})
        names = [f["familyName"] for f in fonts["fonts"]]
        if not any(want in n for n in names):
            raise SystemExit(f"{sel} の描画フォントが {want} ではない: {names}")


async def main() -> None:
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1920, "height": 1080})
        await page.goto(HTML.as_uri(), wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        await check_fonts(page)
        for i, sid in enumerate(SLIDES, 1):
            out = HERE / f"slide_{i}.png"
            await page.locator(f"#{sid}").screenshot(path=str(out))
            print(out)
        await page.emulate_media(media="print")
        out = HERE / "slides.pdf"
        await page.pdf(path=str(out), width="1920px", height="1080px", print_background=True,
                       margin={"top": "0", "right": "0", "bottom": "0", "left": "0"})
        print(out)
        await browser.close()


asyncio.run(main())
