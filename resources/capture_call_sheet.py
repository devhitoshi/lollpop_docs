#!/usr/bin/env python3
"""コール表を SNS 投稿用の画像にする。

    pip install playwright
    python3 resources/capture_call_sheet.py                 # 縦型カード（既定）
    python3 resources/capture_call_sheet.py --format both   # 横長も一緒に

**縦型（既定・SNSに載せるのはこっち）**
  resources/call_sheet_cards.html のカードを撮る。**1曲 = 1枚**。
  1パートを3段（曲の構成 → やること → メンバーパート）で積む。
  出力は resources/img/call_sheet_<色>.png（2700x6126 / 実寸1.5倍）。
  1曲を3枚に割ると、SNSで1曲のコール表が散らばって追えない。横長1枚に
  詰め込むと本文が4px相当まで縮んで拡大しないと読めない。どちらも試して
  却下し、縦1枚に落ち着いた（2026-09-04）。

**横長（--format landscape / both）**
  resources/call_sheet.html の帯を撮る。幅1440・16:9（実寸2880x1620）。
  帯の中身は736pxなので、足りない分はその帯の地の色で上下に足して16:9にする。
  ブログやOGPなど、横に広い置き場用。

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
CARDS_PAGE = ROOT / "resources" / "call_sheet_cards.html"
OUT_DIR = ROOT / "resources" / "img"
LANDSCAPE_WIDTH = 1440
LANDSCAPE_RATIO = 9 / 16
# 実寸の倍率。3段構成にして縦が伸びたので、2倍だと高さが8000pxを超えて
# X の上限（8192px）に迫る。1.5倍でも幅2700pxあり、SNSには十分な解像度。
SCALE = 1.5
FONT = "Noto Sans JP"

# フォントが無い環境で撮ろうとしたときに出す直し方
INSTALL = "  bash resources/install_capture_font.sh"


async def check_font(page, selector: str) -> None:
    """指定ではなく、実際に描画に使われたフォントを見る。"""
    cdp = await page.context.new_cdp_session(page)
    await cdp.send("DOM.enable")
    await cdp.send("CSS.enable")
    document = await cdp.send("DOM.getDocument")
    node = await cdp.send(
        "DOM.querySelector", {"nodeId": document["root"]["nodeId"], "selector": selector}
    )
    used = [
        font["familyName"]
        for font in (await cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]}))["fonts"]
    ]
    if FONT not in used:
        sys.exit(
            f"描画に使われたフォントが {FONT} ではない（{'、'.join(used) or '取得できず'}）。\n"
            f"このまま撮ると字形の違う画像になるので中断した。{FONT} を入れてから撮り直す:\n"
            f"{INSTALL}\n"
            "詳しくは CLAUDE.md「実行環境の注意」。"
        )


async def capture_portrait(browser) -> list[Path]:
    """縦型カード。カードはHTML側で幅を決めているので、そのまま撮る。

    ビューポートはカードより広く取る。狭いとカードがはみ出し、切れた画像が
    書き出される。しかも切れた画像も寸法だけは正しいので、出力の大きさを見ても
    気づけない（実際に見逃した）。だから撮る前に、カードが横方向で
    ビューポートに収まっているかを確かめる。
    """
    page = await browser.new_page(viewport={"width": 1200, "height": 1600}, device_scale_factor=SCALE)
    await page.goto(CARDS_PAGE.as_uri())
    await page.wait_for_timeout(1500)
    await check_font(page, ".line")

    # カードの実寸に合わせてビューポートを広げる（HTML側で幅を変えても追従する）
    card_width = await page.eval_on_selector(".card", "el => el.getBoundingClientRect().width")
    viewport_width = round(card_width) + 160
    await page.set_viewport_size({"width": viewport_width, "height": 1600})
    await page.wait_for_timeout(300)

    written = []
    for card_id in await page.eval_on_selector_all(".card", "els => els.map(el => el.id)"):
        key = card_id.removeprefix("card-")  # id は card-<色>
        card = await page.query_selector(f"#{card_id}")
        box = await card.bounding_box()
        if box["x"] < 0 or box["x"] + box["width"] > viewport_width:
            sys.exit(
                f"カード（幅{round(box['width'])}）がビューポート（幅{viewport_width}）に収まっていない。"
                "このまま撮ると切れた画像になる。"
            )
        path = OUT_DIR / f"call_sheet_{key}.png"
        await card.screenshot(path=path)
        written.append(path)
    await page.close()
    return written


async def capture_landscape(browser) -> list[Path]:
    page = await browser.new_page(
        viewport={"width": LANDSCAPE_WIDTH, "height": round(LANDSCAPE_WIDTH * LANDSCAPE_RATIO)},
        device_scale_factor=SCALE,
    )
    await page.goto(PAGE.as_uri())
    await page.wait_for_timeout(1500)
    await check_font(page, ".call__line")

    written = []
    for key in await page.eval_on_selector_all(".sheet-band", "els => els.map(el => el.id)"):
        band = await page.query_selector(f"#{key}")
        # 帯そのものを16:9に伸ばす。地の色ごと伸びるので、余白は背景に溶ける
        await band.evaluate(
            """(el, height) => {
                el.style.minHeight = height + 'px';
                el.style.display = 'flex';
                el.style.flexDirection = 'column';
                el.style.justifyContent = 'center';
            }""",
            round(LANDSCAPE_WIDTH * LANDSCAPE_RATIO),
        )
        path = OUT_DIR / f"call_sheet_{key}.png"
        await band.screenshot(path=path)
        await band.evaluate(
            "el => { el.style.minHeight = el.style.display = el.style.justifyContent = ''; }"
        )
        written.append(path)
    await page.close()
    return written


async def capture(chromium_path: str | None, what: str) -> list[Path]:
    from playwright.async_api import async_playwright

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    async with async_playwright() as playwright:
        launch = {"args": ["--no-sandbox"]}
        if chromium_path:
            launch["executable_path"] = chromium_path
        browser = await playwright.chromium.launch(**launch)
        if what in ("portrait", "both"):
            written += await capture_portrait(browser)
        if what in ("landscape", "both"):
            written += await capture_landscape(browser)
        await browser.close()
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--format",
        choices=("portrait", "landscape", "both"),
        default="portrait",
        help="縦型カード（既定）／横長／両方",
    )
    parser.add_argument(
        "--chromium", default=None, help="Chromium の実行ファイル（Playwright の既定を使わないとき）"
    )
    args = parser.parse_args()

    needed = [CARDS_PAGE] if args.format == "portrait" else [PAGE]
    if args.format == "both":
        needed = [PAGE, CARDS_PAGE]
    for path in needed:
        if not path.exists():
            sys.exit(f"{path.relative_to(ROOT)} が無い。先に build_call_sheet.py を実行する")

    for path in asyncio.run(capture(args.chromium, args.format)):
        print(f"{path.relative_to(ROOT)} ({size(path)})")


def size(path: Path) -> str:
    """PNGヘッダから実寸を読む（画像ライブラリを足さずに確かめるため）。"""
    header = path.read_bytes()[16:24]
    width = int.from_bytes(header[:4], "big")
    height = int.from_bytes(header[4:], "big")
    return f"{width}x{height}"


if __name__ == "__main__":
    main()
