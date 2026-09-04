#!/usr/bin/env python3
"""songs/call_list.md から resources/call_list.html を生成する。

コール表の内容の正は songs/call_list.md。このスクリプトは表示用のHTMLを
組み立てるだけで、コールの中身は書き換えない。md を更新したら実行する:

    python3 resources/build_call_list.py

デザインの正はリポジトリルートの design.md（実装: resources/css/style.css）。
出力は単一ファイル完結のページなので、design.md のトークン値を転記している
（セトリ白書・成長戦略ノートと同じ扱い）。

ページの作り:
- 1曲 = 1バンド。白とブラッシュを交互に置き、面の切り替わりが曲の切れ目になる。
  SNS 用にスクリーンショットを撮ったとき、隣の曲が写り込まない。
- 各バンドの先頭にアイブロウでワードマークと「非公式」を出す。切り取った画像
  だけが出回っても、出どころと非公式である旨が一緒に写る。
- メンバー名は担当カラーのドット付きで出す（design.md: メンバーカラーは
  ドット・凡例だけの装飾用途）。
"""

from __future__ import annotations

import html
import re
import subprocess
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "songs" / "call_list.md"
OUTPUT = ROOT / "resources" / "call_list.html"

# 担当カラーの正は members/members.md、色の値は design.md。
# 表記ゆれ（おひめ）も資料のまま拾えるようにキーにしている。
MEMBER_COLORS = {
    "くるみ": ("--mc-kurumi", False),
    "おまゆ": ("--mc-mayu", False),
    "まう": ("--mc-mau", False),
    "あみ": ("--mc-ami", False),
    "まな": ("--mc-mana", True),  # 白は輪郭線が要る
    "ひめ": ("--mc-asaka", False),
    "おひめ": ("--mc-asaka", False),
    "なつ": ("--mc-natsumi", False),
}

# 現体制の凡例（members/members.md の並び）
LEGEND = [
    ("くるみ", "--mc-kurumi", False),
    ("おまゆ", "--mc-mayu", False),
    ("まう", "--mc-mau", False),
    ("あみ", "--mc-ami", False),
    ("まな", "--mc-mana", True),
]

SONG_RE = re.compile(r"^## +(.+?)\s*$")
PART_RE = re.compile(r"^- \*\*(.+?)\*\*\s*$")
SUB_RE = re.compile(r"^ {6}- +(.*\S)\s*$")
ITEM_RE = re.compile(r"^ {4}- +(.*\S)\s*$")

# 「まだ載せられない」ことを示す資料側の書き方
PENDING_MARKS = ("新体制のため", "(コール内容)")

_names = "|".join(sorted(MEMBER_COLORS, key=len, reverse=True))
ROUTE_RE = re.compile(rf"^(?P<prefix>歌パート)?(?P<route>(?:{_names})(?:→(?:{_names}))*)$")


class Item:
    def __init__(self, text: str) -> None:
        # 資料に混ざっている行頭の全角スペースは表示のときだけ落とす（md は直さない）
        self.text = text.strip("\u3000")
        self.subs: list[str] = []

    @property
    def pending(self) -> bool:
        return any(mark in self.text for mark in PENDING_MARKS)


class Part:
    def __init__(self, name: str) -> None:
        self.name = name
        self.items: list[Item] = []


class Song:
    def __init__(self, title: str) -> None:
        self.title = title
        self.parts: list[Part] = []

    @property
    def items(self) -> list[Item]:
        return [item for part in self.parts for item in part.items]

    @property
    def status(self) -> str:
        """ready = 載せられる / pending = 全部確認中 / empty = 中身なし"""
        items = self.items
        if not items:
            return "empty"
        if all(item.pending for item in items):
            return "pending"
        return "ready"


def parse(markdown: str) -> list[Song]:
    songs: list[Song] = []
    for line in markdown.splitlines():
        song_match = SONG_RE.match(line)
        if song_match:
            songs.append(Song(song_match.group(1)))
            continue
        if not songs:
            continue
        song = songs[-1]

        part_match = PART_RE.match(line)
        if part_match:
            song.parts.append(Part(part_match.group(1)))
            continue
        if not song.parts:
            continue
        part = song.parts[-1]

        sub_match = SUB_RE.match(line)
        if sub_match and part.items:
            part.items[-1].subs.append(sub_match.group(1).strip("\u3000"))
            continue

        item_match = ITEM_RE.match(line)
        if item_match:
            part.items.append(Item(item_match.group(1)))
    return songs


def dot(color_var: str, outline: bool) -> str:
    cls = "dot dot--outline" if outline else "dot"
    return f'<span class="{cls}" style="background-color: var({color_var});" aria-hidden="true"></span>'


def render_text(text: str) -> str:
    """メンバー名の並び（あみ→くるみ、歌パートおまゆ）だけドット付きにする。

    地の文に出てくる名前（「まうの指示に従う」など）は資料のまま文字で出す。
    """
    match = ROUTE_RE.match(text)
    if not match:
        return html.escape(text)

    chips = []
    if match.group("prefix"):
        chips.append(f'<span class="chip__label">{html.escape(match.group("prefix"))}</span>')
    names = match.group("route").split("→")
    for index, name in enumerate(names):
        # 矢印は次の名前と同じ塊に入れる。行末で「→」だけが取り残されないように
        arrow = '<span class="chip__arrow" aria-hidden="true">→</span>' if index else ""
        color_var, outline = MEMBER_COLORS[name]
        chips.append(
            f'<span class="chip">{arrow}{dot(color_var, outline)}{html.escape(name)}</span>'
        )
    return f'<span class="chips">{"".join(chips)}</span>'


def render_song(song: Song, surface: str, anchor: str) -> str:
    rows = []
    for part in song.parts:
        if not part.items:
            continue
        lines = []
        for item in part.items:
            muted = " call__line--muted" if item.pending else ""
            lines.append(f'<p class="call__line{muted}">{render_text(item.text)}</p>')
            for sub in item.subs:
                lines.append(f'<p class="call__line">{render_text(sub)}</p>')
        rows.append(
            '        <div class="call">\n'
            f'          <p class="call__part">{html.escape(part.name)}</p>\n'
            '          <div class="call__body">\n'
            + "".join(f"            {line}\n" for line in lines)
            + "          </div>\n"
            "        </div>"
        )

    # 行数の多い曲は広い画面で2段に流す（キャプチャ1枚に収めるため）
    wide = " song--wide" if len(rows) >= 10 else ""

    return (
        f'    <section class="band band--{surface} song{wide}" id="{anchor}">\n'
        '      <div class="band__inner band__inner--sheet">\n'
        '        <p class="song__mark">🍭 ろりぽっぷ!!!!!!! 非公式コール表</p>\n'
        f'        <h2 class="song__title">{html.escape(song.title)}</h2>\n'
        '        <div class="calls">\n'
        + "\n".join(rows)
        + "\n        </div>\n"
        "      </div>\n"
        "    </section>"
    )


def last_updated() -> str:
    try:
        stamp = subprocess.run(
            ["git", "log", "-1", "--format=%cI", "--", str(SOURCE.relative_to(ROOT))],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()
        day = datetime.fromisoformat(stamp).astimezone().date()
    except Exception:
        day = date.fromtimestamp(SOURCE.stat().st_mtime)
    return f"{day.year}年{day.month}月{day.day}日"


STYLE = """<style>
/* =====================================================================
   ろりぽっぷ!!!!!!! 全曲コール表
   このファイルは resources/build_call_list.py が songs/call_list.md から
   生成する。直接編集しない。

   デザインの正はリポジトリルートの design.md（実装: resources/css/style.css）。
   単一ファイル完結のため、同じトークン値をここに転記している。
   フルブリードのバンド構成。カードなし・影なし・角丸は操作要素のみ。
   線を引くのは「各行が別レコード」のコール行だけ（design.md: list-row）。
   ===================================================================== */
:root {
  color-scheme: light;
  --primary: #d6006e;
  --primary-active: #b0005b;
  --primary-on-dark: #ff9ecb;
  --on-primary: #ffffff;
  --canvas: #ffffff;
  --surface-blush: #fbe7f0;
  --surface-blush-strong: #f6d3e3;
  --surface-dark: #1a1113;
  --ink: #1d1216;
  --body: #45383e;
  --muted: #71646b;
  --muted-soft: #998a92;
  --on-dark: #fff5f9;
  --on-dark-soft: #d9c4ce;
  --hairline: #f2e2ea;

  /* メンバーカラー（装飾専用。リンクやボタンには使わない） */
  --mc-kurumi: #cc0000;
  --mc-mayu: #f5c400;
  --mc-mau: #7fd4e8;
  --mc-ami: #2e9e5b;
  --mc-mana: #ffffff;
  --mc-asaka: #f172a3;
  --mc-natsumi: #2a6fd6;

  --r-md: 8px;
  --r-pill: 9999px;
  --s-xxs: 4px;
  --s-xs: 8px;
  --s-sm: 12px;
  --s-md: 16px;
  --s-lg: 24px;
  --s-xl: 32px;
  --s-xxl: 48px;
  --s-band: 64px;
  --s-section: 96px;
  --font: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic Medium", Meiryo, sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }

body {
  margin: 0;
  background-color: var(--canvas);
  color: var(--body);
  font-family: var(--font);
  font-size: 16px;
  line-height: 1.85;
  letter-spacing: 0.01em;
  -webkit-font-smoothing: antialiased;
}

a { color: var(--primary); }

:focus-visible { outline: 2px solid var(--primary); outline-offset: 3px; }

/* ---------- Top nav ---------- */
.top-nav {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-md);
  height: 56px;
  padding: 0 var(--s-lg);
  background-color: var(--canvas);
  border-bottom: 1px solid var(--hairline);
  font-size: 13px;
  font-weight: 500;
  line-height: 1;
}

.top-nav a { color: var(--ink); text-decoration: none; }
.top-nav__brand { font-weight: 700; white-space: nowrap; }
.top-nav__links { display: flex; gap: var(--s-lg); margin: 0; padding: 0; list-style: none; }
.top-nav__links a:active { color: var(--primary-active); }

/* ---------- Band（唯一のレイアウトコンテナ） ---------- */
.band { padding: var(--s-band) var(--s-lg); }
.band--section { padding: var(--s-section) var(--s-lg); }
.band__inner { max-width: 1200px; margin: 0 auto; }
.band__inner--narrow { max-width: 720px; }
/* 曲のバンドと曲リストは同じ列幅に揃える（左端が全バンドで一致する） */
.band__inner--sheet { max-width: 960px; }

.band--white { background-color: var(--canvas); color: var(--body); }
.band--blush { background-color: var(--surface-blush); color: var(--body); }
.band--dark  { background-color: var(--surface-dark); color: var(--on-dark); }
.band--pink  { background-color: var(--primary); color: var(--on-primary); }

.band__eyebrow {
  display: block;
  margin: 0 0 var(--s-sm);
  color: var(--muted-soft);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 1.4;
}

.band--dark .band__eyebrow { color: var(--on-dark-soft); }
.band--pink .band__eyebrow { color: var(--surface-blush); }

.band__title {
  margin: 0 0 var(--s-md);
  color: var(--ink);
  font-size: 36px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: -0.02em;
  text-wrap: balance;
}

.band--dark .band__title { color: var(--on-dark); }
.band--pink .band__title { color: var(--on-primary); }

.band__lead {
  margin: 0;
  max-width: 40em;
  color: var(--muted);
  font-size: 17px;
  line-height: 1.8;
}

.band--dark .band__lead { color: var(--on-dark-soft); }
.band--pink .band__lead { color: var(--surface-blush); }

.hero { text-align: center; }
.hero .band__title { font-size: 48px; line-height: 1.25; }
.hero .band__lead { margin: var(--s-lg) auto 0; max-width: 30em; }

/* ---------- 凡例（メンバーカラー。装飾であってナビゲーションではない） ---------- */
.legend {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--s-sm) var(--s-lg);
  margin-top: var(--s-xl);
}

.legend__item {
  display: inline-flex;
  align-items: center;
  gap: var(--s-xs);
  color: var(--ink);
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
}

.dot { width: 12px; height: 12px; border-radius: var(--r-pill); flex: none; }
/* 白（まな）のドットだけ輪郭が要る。白い床の上でも消えないよう、
   ヘアラインより一段濃い桜で描く */
.dot--outline { box-shadow: inset 0 0 0 1px var(--surface-blush-strong); }

/* ---------- 曲の見出しリンク ---------- */
.jump {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--s-sm) var(--s-xl);
  margin: var(--s-lg) 0 0;
  padding: 0;
  list-style: none;
}

.jump a { color: var(--ink); text-decoration: none; font-size: 15px; font-weight: 700; }
.jump a:active { color: var(--primary); }

/* ---------- 1曲 = 1バンド ---------- */
.song__mark {
  margin: 0 0 var(--s-xs);
  color: var(--muted-soft);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 1.4;
}

.song__title {
  margin: 0 0 var(--s-lg);
  color: var(--ink);
  font-size: 28px;
  font-weight: 700;
  line-height: 1.35;
  letter-spacing: -0.015em;
  text-wrap: balance;
}

/* コール行。1行が1レコードなので、ここは線を引いてよい場所 */
.calls { max-width: 720px; border-top: 1px solid var(--hairline); }
.band--blush .calls { border-top-color: var(--surface-blush-strong); }

.call {
  display: grid;
  grid-template-columns: 5.5em 1fr;
  gap: var(--s-xxs) var(--s-md);
  padding: var(--s-sm) 0;
  border-bottom: 1px solid var(--hairline);
}

.band--blush .call { border-bottom-color: var(--surface-blush-strong); }

.call__part {
  margin: 0;
  color: var(--ink);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.7;
}

.call__body { min-width: 0; }

.call__line {
  margin: 0;
  color: var(--body);
  font-size: 15px;
  line-height: 1.7;
}

.call__line + .call__line { margin-top: 2px; }
.call__line--muted { color: var(--muted-soft); }

/* パート数の多い曲は、広い画面では2段に流す。
   スクリーンショット1枚に1曲が収まるようにするため。
   multi-column なので、左の段を上から下、次に右の段、と曲順どおりに読める。 */
@media (min-width: 900px) {
  .song--wide .calls { max-width: none; column-count: 2; column-gap: var(--s-xl); }
  .song--wide .call { break-inside: avoid; }
}

/* メンバー名は担当カラーのドット付きで */
.chips { display: inline-flex; flex-wrap: wrap; align-items: center; gap: var(--s-xxs) var(--s-xs); }
.chip { display: inline-flex; align-items: center; gap: 6px; color: var(--ink); font-weight: 700; }
.chip__arrow { margin-right: 2px; color: var(--muted-soft); font-size: 13px; font-weight: 400; }
.chip__label { color: var(--muted); font-size: 13px; }

/* ---------- 整理中の曲 ---------- */
.pending-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--s-xs) var(--s-lg);
  margin: var(--s-lg) 0 0;
  padding: 0;
  list-style: none;
  color: var(--on-dark-soft);
  font-size: 15px;
  line-height: 1.8;
}

.note-list { margin: var(--s-lg) 0 0; padding-left: 1.2em; font-size: 14px; line-height: 1.9; }
.note-list li { margin-bottom: var(--s-xxs); }
.band--dark .note-list { color: var(--on-dark-soft); }
.band--dark .note-list li::marker { color: var(--primary-on-dark); }

/* ---------- Buttons ---------- */
.band__actions { display: flex; flex-wrap: wrap; gap: var(--s-sm); margin-top: var(--s-xl); }
.hero .band__actions { justify-content: center; }

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-height: 44px;
  padding: 12px 20px;
  border: 1px solid transparent;
  border-radius: var(--r-md);
  font-family: inherit;
  font-size: 15px;
  font-weight: 500;
  line-height: 1;
  text-decoration: none;
}

.btn--primary { background-color: var(--primary); color: var(--on-primary); }
.btn--primary:active { background-color: var(--primary-active); }
.btn--secondary { background-color: transparent; border-color: var(--hairline); color: var(--ink); }
.btn--secondary:active { border-color: var(--primary); color: var(--primary); }
.btn--inverse { background-color: var(--canvas); color: var(--ink); }
.btn--inverse:active { background-color: var(--surface-blush); }

/* ---------- Footer ---------- */
.footer {
  padding: var(--s-band) var(--s-lg);
  background-color: var(--surface-dark);
  color: var(--on-dark-soft);
  font-size: 14px;
  line-height: 1.8;
}

.footer__inner { max-width: 1200px; margin: 0 auto; }
.footer__brand { margin: 0 0 var(--s-lg); color: var(--on-dark); font-size: 15px; font-weight: 700; }
.footer__links { display: flex; flex-wrap: wrap; gap: var(--s-xs) var(--s-lg); margin: 0 0 var(--s-lg); padding: 0; list-style: none; }
.footer__links a { color: var(--primary-on-dark); text-decoration: none; }
.footer__note { margin: 0; font-size: 12px; }

/* ---------- Responsive（面はフルブリードのまま、中の列だけ応答する） ---------- */
@media (max-width: 640px) {
  .top-nav { padding: 0 var(--s-md); }
  .top-nav__links { gap: var(--s-md); overflow-x: auto; }
  .band { padding: var(--s-xxl) var(--s-md); }
  .band--section { padding: 56px var(--s-md); }
  .band__title { font-size: 28px; }
  .hero .band__title { font-size: 30px; }
  .band__lead { font-size: 16px; }
  .song__title { font-size: 24px; }
  .call { grid-template-columns: 4.6em 1fr; gap: var(--s-xxs) var(--s-sm); }
  .call__part { font-size: 12px; }
  .call__line { font-size: 14px; }
  .band__actions { flex-direction: column; align-items: stretch; }
  .hero .band__actions { align-items: center; }
}
</style>"""


def build() -> str:
    songs = parse(SOURCE.read_text(encoding="utf-8"))
    ready = [song for song in songs if song.status == "ready"]
    waiting = [song for song in songs if song.status != "ready"]
    updated = last_updated()

    anchors = {song.title: f"s{index:02d}" for index, song in enumerate(ready, start=1)}

    legend = "\n".join(
        f'          <span class="legend__item">{dot(color, outline)}{html.escape(name)}</span>'
        for name, color, outline in LEGEND
    )

    jump = "\n".join(
        f'          <li><a href="#{anchors[song.title]}">{html.escape(song.title)}</a></li>'
        for song in ready
    )

    song_bands = "\n\n".join(
        render_song(song, "white" if index % 2 == 0 else "blush", anchors[song.title])
        for index, song in enumerate(ready)
    )

    waiting_items = "\n".join(
        f"          <li>{html.escape(song.title)}</li>" for song in waiting
    )

    return f"""<!DOCTYPE html>
<html lang="ja">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ろりぽっぷ!!!!!!!全曲コール表</title>
    <meta name="description" content="アイドルグループ『ろりぽっぷ!!!!!!!』の曲ごとのコール・レスポンスとメンバーパートをまとめた、ファンによる非公式のコール表です。">
    <meta name="theme-color" content="#ffffff">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap">
{STYLE}
</head>

<body>
    <nav class="top-nav">
        <a class="top-nav__brand" href="./index.html">🍭 ろりぽっぷ!!!!!!! Docs</a>
        <ul class="top-nav__links">
            <li><a href="./index.html">ポータル</a></li>
            <li><a href="viewer.html?file=../guide/starter_pack.md">はじめての方へ</a></li>
        </ul>
    </nav>

    <main>
        <!-- 白: ヒーロー -->
        <section class="band band--section band--white hero">
            <div class="band__inner">
                <span class="band__eyebrow">CALL SHEET</span>
                <h1 class="band__title">全曲コール表</h1>
                <p class="band__lead">
                    現場で迷わないための、曲ごとのコールとレスポンス。<br>
                    メンバーパートは担当カラーのドットで示しています。
                </p>
                <div class="legend">
{legend}
                </div>
                <div class="band__actions">
                    <a class="btn btn--secondary" href="viewer.html?file=../songs/call_list.md">元データを見る</a>
                </div>
            </div>
        </section>

        <!-- ブラッシュ: 曲を探す -->
        <section class="band band--blush">
            <div class="band__inner band__inner--sheet">
                <span class="band__eyebrow">SONGS</span>
                <h2 class="band__title">この表に載っている曲</h2>
                <ul class="jump">
{jump}
                </ul>
            </div>
        </section>

{song_bands}

        <!-- プラム黒: この表について -->
        <section class="band band--dark">
            <div class="band__inner band__inner--sheet">
                <span class="band__eyebrow">ABOUT</span>
                <h2 class="band__title">この表について</h2>
                <p class="band__lead">最終更新: {updated}</p>
                <ul class="note-list">
                    <li>ファン有志がライブで聞き取ってまとめた非公式のコール表です。運営公認のものではありません。</li>
                    <li>コールは現場やその日の煽りで変わります。まわりに合わせるのがいちばん確実です。</li>
                    <li>メンバーパートは記録した時点のもの。編成や振り入れで変わることがあります。</li>
                </ul>
                <p class="band__lead" style="margin-top: var(--s-xl);">新体制でのコールを確認中の曲</p>
                <ul class="pending-list">
{waiting_items}
                </ul>
            </div>
        </section>

        <!-- ピンク: ページ唯一のCTAの瞬間 -->
        <section class="band band--pink hero">
            <div class="band__inner">
                <h2 class="band__title">コールを知らなくても大丈夫!!!!!!!</h2>
                <p class="band__lead">はじめての現場は、まわりを見て手拍子だけでも<br>十分楽しめます。</p>
                <div class="band__actions">
                    <a class="btn btn--inverse" href="viewer.html?file=../guide/starter_pack.md">スターターパックを読む</a>
                </div>
            </div>
        </section>
    </main>

    <footer class="footer">
        <div class="footer__inner">
            <p class="footer__brand">🍭 ろりぽっぷ!!!!!!! Docs</p>
            <ul class="footer__links">
                <li><a href="./index.html">ポータル</a></li>
                <li><a href="viewer.html?file=../guide/starter_pack.md">はじめての方へ</a></li>
                <li><a href="viewer.html?file=../members/members.md">メンバー</a></li>
                <li><a href="viewer.html?file=../songs/楽曲一覧.md">楽曲一覧</a></li>
                <li><a href="viewer.html?file=../guide/rules.md">ルール</a></li>
            </ul>
            <p class="footer__note">
                ろりぽっぷ!!!!!!! は株式会社FLAP entertainment所属。
                本サイトはファンによる非公式のドキュメントです。最新情報は公式SNSをご確認ください。
            </p>
        </div>
    </footer>
</body>

</html>
"""


def main() -> None:
    OUTPUT.write_text(build(), encoding="utf-8")
    songs = parse(SOURCE.read_text(encoding="utf-8"))
    ready = sum(1 for song in songs if song.status == "ready")
    print(f"{OUTPUT.relative_to(ROOT)} を生成: 掲載 {ready}曲 / 全 {len(songs)}曲")


if __name__ == "__main__":
    main()
