#!/usr/bin/env python3
"""fig_infographic.html を img/01_infographic.png（1080幅・2倍）に撮る。

    python articles/単発/19_2周年SPライブ/make_figure.py

数字や文言を変えるときは HTML を直してから撮り直す。描画フォントが Noto Sans JP でなければ中断する。
"""
from __future__ import annotations

import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
HTML = HERE / "fig_infographic.html"
PNG = HERE / "img" / "01_infographic.png"


async def main() -> None:
    PNG.parent.mkdir(exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch()
        page = await browser.new_page(viewport={"width": 1080, "height": 800}, device_scale_factor=2)
        await page.goto(HTML.as_uri(), wait_until="networkidle")
        await page.evaluate("document.fonts.ready")
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("DOM.enable")
        await cdp.send("CSS.enable")
        doc = await cdp.send("DOM.getDocument")
        node = await cdp.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": ".hero h1"})
        fonts = await cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})
        names = [f["familyName"] for f in fonts["fonts"]]
        if not any("Noto Sans JP" in n for n in names):
            raise SystemExit(f"描画フォントが Noto Sans JP ではない: {names}")
        await page.locator("#fig").screenshot(path=str(PNG))
        await browser.close()
    print(PNG)


asyncio.run(main())
