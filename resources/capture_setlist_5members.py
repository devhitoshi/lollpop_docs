#!/usr/bin/env python3
"""5人体制のセトリ可視化ページを画像にする。

    pip install playwright
    python3 resources/capture_setlist_5members.py            # 節ごと＋全体
    python3 resources/capture_setlist_5members.py --only map ranking

`resources/setlist_5members.html` の各バンドを1枚ずつ撮って
`resources/img/setlist_5members_<節>.png` に書き出す。note やSNSに貼る用。
ページ自体は `resources/build_setlist_5members.py` が組み立てる。

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
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
PAGE = ROOT / "resources" / "setlist_5members.html"
OUT_DIR = ROOT / "resources" / "img"
WIDTH = 1200
SCALE = 2
FONT = "Noto Sans JP"
INSTALL = "  bash resources/install_capture_font.sh"

# 節の id → 出力ファイル名の後ろ。ページの並び順。
SECTIONS = [
    ("top", "hero"),
    ("map", "song_map"),
    ("ranking", "ranking"),
    ("change", "before_after"),
    ("matrix", "matrix"),
    ("unplayed", "unplayed"),
    ("setlist", "setlists"),
]
# 全体は縦に長い。X の上限（8192px）を超えないよう等倍で撮る。
FULL_SCALE = 1


def check_font(page, selector: str) -> None:
    """指定ではなく、実際に描画に使われたフォントを見る。"""
    cdp = page.context.new_cdp_session(page)
    cdp.send("DOM.enable")
    cdp.send("CSS.enable")
    document = cdp.send("DOM.getDocument")
    node = cdp.send("DOM.querySelector", {"nodeId": document["root"]["nodeId"], "selector": selector})
    used = [f["familyName"] for f in cdp.send("CSS.getPlatformFontsForNode", {"nodeId": node["nodeId"]})["fonts"]]
    if FONT not in used:
        sys.exit(
            f"描画に使われたフォントが {FONT} ではない（{'、'.join(used) or '取得できず'}）。\n"
            f"このまま撮ると字形の違う画像になるので中断した。{FONT} を入れてから撮り直す:\n"
            f"{INSTALL}\n"
            "詳しくは CLAUDE.md「実行環境の注意」。"
        )


def open_page(browser, scale: int):
    page = browser.new_page(viewport={"width": WIDTH, "height": 1200}, device_scale_factor=scale)
    page.goto(PAGE.as_uri())
    page.wait_for_timeout(1500)
    # sticky のナビは節を撮ると中身に重なる。画像には要らないので消す。
    page.evaluate("document.querySelectorAll('.top-nav').forEach(el => el.remove())")
    # 横スクロールが出ていたら、その節は切れた画像になる（マトリクスで踏みやすい）
    if page.evaluate("document.documentElement.scrollWidth") > WIDTH:
        sys.exit(f"ページが幅{WIDTH}に収まっていない。切れた画像になるので中断した。")
    return page


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--chromium", help="Chromium の実行ファイル（リモート環境では /opt/pw-browsers の下）")
    ap.add_argument("--only", nargs="+", metavar="ID", help="撮る節の id（既定: 全部＋全体）")
    ap.add_argument("--no-full", action="store_true", help="ページ全体の1枚を撮らない")
    args = ap.parse_args()

    if not PAGE.exists():
        sys.exit(f"{PAGE.relative_to(ROOT)} が無い。先に build_setlist_5members.py を回す。")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    targets = [s for s in SECTIONS if not args.only or s[0] in args.only]
    if args.only and not targets:
        sys.exit(f"該当する節が無い。使える id: {'、'.join(i for i, _ in SECTIONS)}")

    written = []
    with sync_playwright() as p:
        launch = {"args": ["--no-sandbox"]}
        if args.chromium:
            launch["executable_path"] = args.chromium
        browser = p.chromium.launch(**launch)

        page = open_page(browser, SCALE)
        check_font(page, "h1")
        for section_id, name in targets:
            el = page.query_selector(f"#{section_id}")
            if el is None:
                sys.exit(f"#{section_id} がページに無い。build 側の id と合っているか確認する。")
            path = OUT_DIR / f"setlist_5members_{name}.png"
            el.screenshot(path=path)
            written.append(path)
        page.close()

        if not args.no_full and not args.only:
            page = open_page(browser, FULL_SCALE)
            path = OUT_DIR / "setlist_5members_full.png"
            page.screenshot(path=path, full_page=True)
            written.append(path)
            page.close()
        browser.close()

    for path in written:
        print(f"{path.relative_to(ROOT)}  {path.stat().st_size // 1024}KB")


if __name__ == "__main__":
    main()
