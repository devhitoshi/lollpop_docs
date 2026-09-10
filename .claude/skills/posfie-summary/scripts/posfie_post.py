#!/usr/bin/env python3
"""posfie のまとめ作成を Playwright で半自動化する。

**X の自動ログインはしない。** X 側の自動化検知と 2FA があり、規約上も避けたいので、
ログインだけは人がブラウザで通し、そのセッションを保存して以降の操作に使い回す。

posfie の編集画面はポストを「左カラムから中央カラムへドラッグ&ドロップ」して組み立てる作りで、
DnD は DOM の構造に強く依存する。**壊れても作業が止まらないよう、失敗しても例外にせず
ブラウザを開いたまま人に渡す**（素材 md があれば手で貼っても完成する）。

    # 1. ログイン（人が X 認証を通す。完了を自動検知してセッションを保存する）
    python .claude/skills/posfie-summary/scripts/posfie_post.py --login

    # 2. 画面構造を見る（セレクタが変わったとき用。編集画面の要素を一覧にする）
    python .claude/skills/posfie-summary/scripts/posfie_post.py --inspect

    # 3. 素材 md の URL を順に投入する（タイトル・説明も入れる。公開は押さない）
    python .claude/skills/posfie-summary/scripts/posfie_post.py --build articles/posfie/2026-09-01_2026-09-07.md
"""

import argparse
import os
import re
import sys
import time

# x-account-fetch と同じ流儀で、どこから実行してもリポジトリルートを基準にする。
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

STATE_PATH = "work/.posfie_state.json"   # 認証済みセッション。.gitignore 済み
TOP_URL = "https://posfie.com/"
POST_URL_RE = re.compile(r"https://x\.com/\w+/status/\d+")


def load_material(path):
    """素材 md からポスト URL・タイトル・説明を取り出す。URL は出現順、重複は落とす。"""
    text = open(path, encoding="utf-8").read()

    urls, seen = [], set()
    for url in POST_URL_RE.findall(text):
        if url not in seen:
            seen.add(url)
            urls.append(url)

    title = ""
    m = re.search(r"^-\s+\*\*タイトル\*\*:\s*(.+)$", text, re.M)
    if m:
        title = m.group(1).strip()

    # 「- **説明文**:」の次の行から、次の「- **」までを説明文とする。
    desc = ""
    m = re.search(r"^-\s+\*\*説明文\*\*:\s*\n((?:\s{2,}.+\n)+)", text, re.M)
    if m:
        desc = "\n".join(line.strip() for line in m.group(1).splitlines())

    return urls, title, desc


def click_first(page, selectors, what, timeout=4000):
    """候補セレクタを順に試す。posfie 側の DOM が変わっても止まらないようにするため。"""
    for sel in selectors:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=timeout)
            loc.click()
            print(f"  {what}: '{sel}' をクリック")
            return True
        except Exception:
            continue
    print(f"  {what}: 見つからなかった（候補 {len(selectors)} 件すべて不一致）")
    return False


def cmd_login(pw, args):
    """人が X 認証を通すのを待ち、完了を検知してセッションを保存する。"""
    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(locale="ja-JP")
    page = context.new_page()
    page.goto(TOP_URL)

    print("ブラウザを開きました。posfie に X アカウントでログインしてください。")
    print(f"（完了を自動で検知します。最大 {args.login_timeout} 秒待ちます）")

    deadline = time.time() + args.login_timeout
    logged_in = False
    while time.time() < deadline:
        time.sleep(3)
        try:
            # ログインすると「ログイン / 会員登録」の導線が消える。それを完了の合図にする。
            if page.get_by_text("会員登録", exact=False).count() == 0:
                logged_in = True
                break
        except Exception:
            continue

    if logged_in:
        time.sleep(2)  # 認証直後の cookie 書き込みを待つ
        os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
        context.storage_state(path=STATE_PATH)
        print(f"ログインを検知しました。セッションを {STATE_PATH} に保存しました。")
    else:
        print("時間内にログインを検知できませんでした。--login をやり直してください。")

    browser.close()
    return 0 if logged_in else 1


def open_editor(pw, args):
    """保存済みセッションで編集画面まで進む。(browser, page) を返す。"""
    if not os.path.exists(STATE_PATH):
        print(f"{STATE_PATH} がありません。先に --login を実行してください。")
        sys.exit(1)

    browser = pw.chromium.launch(headless=False)
    context = browser.new_context(storage_state=STATE_PATH, locale="ja-JP")
    page = context.new_page()
    page.goto(TOP_URL)

    # 「まとめる」「まとめを作る」のラベル揺れと、直リンクの両方を試す。
    ok = click_first(page, [
        "a:has-text('まとめを作る')",
        "a:has-text('まとめる')",
        "button:has-text('まとめる')",
    ], "まとめ作成への導線")
    if not ok:
        print("  トップから入れなかったので /create を直接開きます")
        page.goto("https://posfie.com/create")
    page.wait_for_load_state("networkidle")
    return browser, page


def cmd_inspect(pw, args):
    """編集画面の操作できる要素を一覧にする。セレクタを詰めるための下調べ。"""
    browser, page = open_editor(pw, args)
    print(f"\nURL: {page.url}\n")
    for tag in ("button", "a", "input", "textarea"):
        loc = page.locator(tag)
        n = min(loc.count(), 60)
        print(f"--- {tag}（{loc.count()} 件、先頭 {n} 件）")
        for i in range(n):
            el = loc.nth(i)
            try:
                label = (el.inner_text() or "").strip().replace("\n", " ")[:40]
                attrs = {k: el.get_attribute(k) for k in ("id", "class", "placeholder", "aria-label", "href")}
                attrs = {k: v[:60] for k, v in attrs.items() if v}
                print(f"  [{i}] {label!r} {attrs}")
            except Exception:
                continue
    print(f"\nブラウザは {args.keep_open} 秒後に閉じます。")
    time.sleep(args.keep_open)
    browser.close()
    return 0


def cmd_build(pw, args):
    """素材 md の URL を編集画面に投入する。仕上げと公開は人に渡す。"""
    urls, title, desc = load_material(args.build)
    print(f"素材: {args.build}")
    print(f"  ポスト {len(urls)} 件／タイトル: {title}")

    browser, page = open_editor(pw, args)

    # URL 取得。posfie の「URLボタン」は貼り付けたポストだけを読み込む。
    # 複数行をまとめて受け付ける想定でいったん全件を貼り、だめなら 1 件ずつに落とす。
    click_first(page, [
        "button:has-text('URL')",
        "a:has-text('URL')",
        "[aria-label*='URL']",
    ], "URLボタン")

    box = None
    for sel in ["textarea", "input[type='text']", "input[type='url']"]:
        try:
            loc = page.locator(sel).first
            loc.wait_for(state="visible", timeout=3000)
            box = loc
            print(f"  入力欄: '{sel}'")
            break
        except Exception:
            continue

    if box is None:
        print("  URL の入力欄が見つかりませんでした。素材 md を見ながら手で貼ってください。")
    else:
        try:
            box.fill("\n".join(urls))
            print(f"  {len(urls)} 件の URL をまとめて入力しました")
        except Exception as e:
            print(f"  まとめての入力に失敗（{e}）。1 件ずつ試します")
            for url in urls:
                try:
                    box.fill(url)
                    page.keyboard.press("Enter")
                    time.sleep(0.4)
                except Exception:
                    print(f"    失敗: {url}")
        click_first(page, [
            "button:has-text('取得')",
            "button:has-text('読み込')",
            "button[type='submit']",
        ], "取得ボタン")

    # タイトル・説明は入れられれば入れる（入らなくても人が貼れる程度の手間）。
    for sel, value, what in (
        ("input[placeholder*='タイトル']", title, "タイトル"),
        ("textarea[placeholder*='説明']", desc, "説明文"),
    ):
        if not value:
            continue
        try:
            page.locator(sel).first.fill(value)
            print(f"  {what}を入力しました")
        except Exception:
            print(f"  {what}は自動で入れられませんでした（素材 md からコピーしてください）")

    print("\n--- ここから先は人の作業 ---")
    print("1. 左カラムのポストを中央へドラッグ&ドロップして、素材 md の順に並べる")
    print("2. 見出し・コメントを素材 md からコピーして差し込む")
    print("3. プレビューを確認して公開する（このスクリプトは公開ボタンを押しません）")
    print(f"\nブラウザは {args.keep_open} 秒後に閉じます。")
    time.sleep(args.keep_open)
    browser.close()
    return 0


def main():
    p = argparse.ArgumentParser(description="posfie のまとめ作成を半自動化する")
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--login", action="store_true", help="人が X 認証を通し、セッションを保存する")
    g.add_argument("--inspect", action="store_true", help="編集画面の要素を一覧にする")
    g.add_argument("--build", metavar="素材md", help="素材 md の URL を編集画面に投入する")
    p.add_argument("--login-timeout", type=int, default=300, help="ログイン待ちの秒数（既定300）")
    p.add_argument("--keep-open", type=int, default=900,
                   help="操作後にブラウザを開いたままにする秒数（既定900）")
    args = p.parse_args()

    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("playwright が入っていません。`pip install playwright` を実行してください。")
        return 1

    with sync_playwright() as pw:
        if args.login:
            return cmd_login(pw, args)
        if args.inspect:
            return cmd_inspect(pw, args)
        return cmd_build(pw, args)


if __name__ == "__main__":
    sys.exit(main())
