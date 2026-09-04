#!/usr/bin/env python3
"""resources/call_sheet.html の色ちがいを、1色1枚の画像にする（SNS投稿用）。

    pip install playwright && playwright install chromium
    python3 resources/capture_call_sheet.py

出力は resources/img/call_sheet_<色>.png。幅1440・16:9（実寸 2880x1620）。
帯の中身は736pxなので、足りない分はその帯の地の色で上下に足して 16:9 ちょうどに
する。X のタイムラインで上下が切られないため。

必要なもの:
- Playwright の Chromium。リモート環境では `/opt/pw-browsers` のものを
  --chromium で指定する（pip版とビルド番号がずれるため）。
- **Noto Sans JP がシステムに入っていること**（`bash resources/install_capture_font.sh`）。
  入っていないと別の日本語フォント（中国語フォントなど）で描画され、漢字の字形が
  変わったまま画像になる。実際に描画に使われたフォントを CDP で確認し、
  Noto Sans JP でなければ中断する。CLAUDE.md「実行環境の注意」も参照。
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "resources" / "call_sheet.html"
OUT_DIR = ROOT / "resources" / "img"
WIDTH = 1440
RATIO = 9 / 16
SCALE = 2
FONT = "Noto Sans JP"

# フォントが無い環境で撮ろうとしたときに出す直し方
INSTALL = "  bash resources/install_capture_font.sh"


async def capture(chromium_path: str | None) -> list[Path]:
    from playwright.async_api import async_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    async with async_playwright() as playwright:
        launch = {"args": ["--no-sandbox"]}
        if chromium_path:
            launch["executable_path"] = chromium_path
        browser = await playwright.chromium.launch(**launch)
        page = await browser.new_page(
            viewport={"width": WIDTH, "height": round(WIDTH * RATIO)},
            device_scale_factor=SCALE,
        )
        await page.goto(PAGE.as_uri())
        await page.wait_for_timeout(1500)

        # 実際に描画に使われたフォントを確かめる（指定と実物は別物なので）
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("DOM.enable")
        await cdp.send("CSS.enable")
        document = await cdp.send("DOM.getDocument")
        node = await cdp.send(
            "DOM.querySelector",
            {"nodeId": document["root"]["nodeId"], "selector": ".call__line"},
        )
        used = [
            font["familyName"]
            for font in (await cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]}))["fonts"]
        ]
        if FONT not in used:
            await browser.close()
            sys.exit(
                f"描画に使われたフォントが {FONT} ではない（{'、'.join(used) or '取得できず'}）。\n"
                f"このまま撮ると字形の違う画像になるので中断した。{FONT} を入れてから撮り直す:\n"
                f"{INSTALL}\n"
                "詳しくは CLAUDE.md「実行環境の注意」。"
            )

        for key in await page.eval_on_selector_all(
            ".sheet-band", "els => els.map(el => el.id)"
        ):
            band = await page.query_selector(f"#{key}")
            # 帯そのものを16:9に伸ばす。地の色ごと伸びるので、余白は背景に溶ける
            await band.evaluate(
                """(el, height) => {
                    el.dataset.shot = '1';
                    el.style.minHeight = height + 'px';
                    el.style.display = 'flex';
                    el.style.flexDirection = 'column';
                    el.style.justifyContent = 'center';
                }""",
                round(WIDTH * RATIO),
            )
            path = OUT_DIR / f"call_sheet_{key}.png"
            await band.screenshot(path=path)
            await band.evaluate(
                "el => { el.style.minHeight = el.style.display = el.style.justifyContent = ''; }"
            )
            written.append(path)

        await browser.close()
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--chromium",
        default=None,
        help="Chromium の実行ファイル（Playwright の既定を使わないとき）",
    )
    args = parser.parse_args()

    if not PAGE.exists():
        sys.exit(f"{PAGE.relative_to(ROOT)} が無い。先に build_call_sheet.py を実行する")

    for path in asyncio.run(capture(args.chromium)):
        print(f"{path.relative_to(ROOT)} ({WIDTH * SCALE}x{round(WIDTH * RATIO) * SCALE})")


if __name__ == "__main__":
    main()
