"""週刊まとめの図版モックを PNG にする（使い捨て）。

    python work/weekly_card_mock/shoot.py

実際に描画されたフォントを CDP で確認する（resources/capture_call_sheet.py と同じ理由。
CSS の指定と実物は別で、Noto Sans JP が無いと別の日本語フォントの字形で撮れてしまう）。
"""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

HERE = Path(__file__).resolve().parent
PAGE = HERE / "mock.html"
CARDS = ["schedule-a", "schedule-b", "setlist-a", "setlist-b", "setlist-week-a", "setlist-week-b"]


async def main():
    async with async_playwright() as pw:
        browser = await pw.chromium.launch()
        page = await browser.new_page(viewport={"width": 1200, "height": 1400})
        await page.goto(PAGE.as_uri())
        await page.evaluate("document.fonts.ready")

        cdp = await page.context.new_cdp_session(page)
        await cdp.send("DOM.enable")
        await cdp.send("CSS.enable")
        doc = await cdp.send("DOM.getDocument")
        node = await cdp.send("DOM.querySelector", {"nodeId": doc["root"]["nodeId"], "selector": ".band .title"})
        fonts = await cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})
        names = [f["familyName"] for f in fonts.get("fonts", [])]
        print("描画に使われたフォント:", names)

        for cid in CARDS:
            el = page.locator("#" + cid)
            out = HERE / f"{cid}.png"
            await el.screenshot(path=str(out))
            box = await el.bounding_box()
            print(f"{cid}.png  {int(box['width'])}x{int(box['height'])}")
        await browser.close()


asyncio.run(main())
