#!/usr/bin/env python3
"""songs/call_list.md の1曲分から、SNSキャプチャ用の1枚もののコール表を作る。

    python3 resources/build_call_sheet.py                    # 未完成ヒロイン
    python3 resources/build_call_sheet.py --song 乙女ロック    # 別の曲

コールの内容の正は songs/call_list.md。このスクリプトは表示用に組み立てるだけで、
中身は書き換えない（行頭の全角スペースを表示のときだけ落とすのみ）。

デザインの正はリポジトリルートの design.md（実装: resources/css/style.css）。
出力は単一ファイル完結のページなので、design.md のトークン値を転記している
（セトリ白書・成長戦略ノートと同じ扱い）。

ページの作り:
- 1曲まるごとが1バンドに収まる。ワードマーク・非公式・時点までが同じ面にあるので、
  バンドを1枚キャプチャすればそれだけで出典つきの画像になる。
- 広い画面では BLOCKS の「かたまり」がそのまま列になる（1番 / 2番 / ラスト）。
  列の切れ目が曲の切れ目と一致するので、どこから読むか迷わない。
  狭い画面では、かたまりを縦に積む。
- メンバー名は担当カラーのドット付き（design.md: メンバーカラーは装飾専用）。
"""

from __future__ import annotations

import argparse
import html
import re
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "songs" / "call_list.md"
DEFAULT_SONG = "未完成ヒロイン"
DEFAULT_OUTPUT = ROOT / "resources" / "call_sheet.html"

# 曲の「かたまり」。曲の構造そのものなので曲ごとに書く。
# ここに無いパートは直前のかたまりの末尾に入り、実行時に警告を出す（行は落とさない）。
BLOCKS = {
    "未完成ヒロイン": [
        ("1番", ["イントロ", "Aメロ", "Bメロ", "サビ", "間奏"]),
        ("2番", ["2Aメロ", "2Bメロ", "2サビ", "Cメロ"]),
        # 2間奏（行！く！ぞー！のMIX）はラスサビへの助走なので、ラスト側の頭に置く
        ("ラスト", ["2間奏", "3Bメロ", "ラスサビ", "アウトロ"]),
    ],
}

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

SONG_RE = re.compile(r"^## +(.+?)\s*$")
PART_RE = re.compile(r"^- \*\*(.+?)\*\*\s*$")
SUB_RE = re.compile(r"^ {6}- +(.*\S)\s*$")
ITEM_RE = re.compile(r"^ {4}- +(.*\S)\s*$")

_names = "|".join(sorted(MEMBER_COLORS, key=len, reverse=True))
ROUTE_RE = re.compile(rf"^(?P<prefix>歌パート)?(?P<route>(?:{_names})(?:→(?:{_names}))*)$")


class Item:
    def __init__(self, text: str) -> None:
        # 資料に混ざっている行頭の全角スペースは表示のときだけ落とす（md は直さない）
        self.text = text.strip("　")
        self.subs: list[str] = []


class Part:
    def __init__(self, name: str) -> None:
        self.name = name
        self.items: list[Item] = []


class Song:
    def __init__(self, title: str) -> None:
        self.title = title
        self.parts: list[Part] = []


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
            part.items[-1].subs.append(sub_match.group(1).strip("　"))
            continue

        item_match = ITEM_RE.match(line)
        if item_match:
            part.items.append(Item(item_match.group(1)))
    return songs


def group(song: Song) -> list[tuple[str, list[Part]]]:
    """曲のパートを「かたまり」に振り分ける。中身のないパートは落とす。"""
    parts = [part for part in song.parts if part.items]
    plan = BLOCKS.get(song.title)
    if not plan:
        return [("", parts)]

    where = {
        name: index for index, (_, names) in enumerate(plan) for name in names
    }
    blocks: list[tuple[str, list[Part]]] = [(label, []) for label, _ in plan]
    unplaced: list[str] = []
    current = 0
    for part in parts:
        if part.name in where:
            current = where[part.name]
        else:
            unplaced.append(part.name)
        blocks[current][1].append(part)

    if unplaced:
        print(
            f"警告: かたまりの定義に無いパートを直前のかたまりに入れた: {'、'.join(unplaced)}\n"
            f"      BLOCKS['{song.title}'] を更新してください",
            file=sys.stderr,
        )
    return [(label, members) for label, members in blocks if members]


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
    for index, name in enumerate(match.group("route").split("→")):
        # 矢印は次の名前と同じ塊に入れる。行末で「→」だけが取り残されないように
        arrow = '<span class="chip__arrow" aria-hidden="true">→</span>' if index else ""
        color_var, outline = MEMBER_COLORS[name]
        chips.append(
            f'<span class="chip">{arrow}{dot(color_var, outline)}{html.escape(name)}</span>'
        )
    return f'<span class="chips">{"".join(chips)}</span>'


def render_block(label: str, parts: list[Part]) -> str:
    rows = []
    for part in parts:
        lines = []
        for item in part.items:
            lines.append(f'<p class="call__line">{render_text(item.text)}</p>')
            for sub in item.subs:
                lines.append(f'<p class="call__line">{render_text(sub)}</p>')
        rows.append(
            '            <div class="call">\n'
            f'              <p class="call__part">{html.escape(part.name)}</p>\n'
            '              <div class="call__body">\n'
            + "".join(f"                {line}\n" for line in lines)
            + "              </div>\n"
            "            </div>"
        )

    heading = f'          <h2 class="block__label">{html.escape(label)}</h2>\n' if label else ""
    return (
        '        <section class="block">\n'
        + heading
        + '          <div class="calls">\n'
        + "\n".join(rows)
        + "\n          </div>\n"
        "        </section>"
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
   ろりぽっぷ!!!!!!! コール表（1曲）
   このファイルは resources/build_call_sheet.py が songs/call_list.md から
   生成する。直接編集しない。

   デザインの正はリポジトリルートの design.md（実装: resources/css/style.css）。
   単一ファイル完結のため、同じトークン値をここに転記している。
   フルブリードのバンド構成。カードなし・影なし・角丸は操作要素のみ。
   線を引くのは「各行が別レコード」のコール行だけ（design.md: list-row）。
   曲のかたまり（1番 / 2番 / ラスト）は枠線ではなく、見出しと余白で分ける。
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

/* ---------- Top nav（キャプチャには入らないページのクローム） ---------- */
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

/* ---------- Band ---------- */
.band { padding: var(--s-band) var(--s-lg); }
.band__inner { max-width: 1200px; margin: 0 auto; }

.band--blush { background-color: var(--surface-blush); color: var(--body); }
.band--dark  { background-color: var(--surface-dark); color: var(--on-dark-soft); }
.band--dark a { color: var(--primary-on-dark); text-decoration: none; }

/* ---------- 見出し（ワードマーク・非公式・時点まで同じ面に置く） ---------- */
.sheet__mark {
  margin: 0 0 var(--s-xs);
  color: var(--muted-soft);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 1.6;
}

.sheet__title {
  margin: 0 0 var(--s-xl);
  color: var(--ink);
  font-size: 40px;
  font-weight: 700;
  line-height: 1.25;
  letter-spacing: -0.02em;
  text-wrap: balance;
}

/* ---------- かたまり（広い画面ではそのまま列になる） ---------- */
.sheet {
  display: grid;
  grid-template-columns: 1fr;
  gap: var(--s-xl);
  align-items: start;
}

.block__label {
  margin: 0 0 var(--s-xs);
  color: var(--ink);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.5;
  letter-spacing: 0.06em;
}

/* コール行。1行が1レコードなので、ここは線を引いてよい場所 */
.calls { border-top: 1px solid var(--surface-blush-strong); }

.call {
  display: grid;
  grid-template-columns: 4.8em 1fr;
  gap: var(--s-xxs) var(--s-sm);
  padding: var(--s-sm) 0;
  border-bottom: 1px solid var(--surface-blush-strong);
}

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

/* メンバー名は担当カラーのドット付きで */
.chips { display: inline-flex; flex-wrap: wrap; align-items: center; gap: var(--s-xxs) var(--s-xs); }
.chip { display: inline-flex; align-items: center; gap: 6px; color: var(--ink); font-weight: 700; }
.chip__arrow { margin-right: 2px; color: var(--muted-soft); font-size: 13px; font-weight: 400; }
.chip__label { color: var(--muted); font-size: 13px; }

.dot { width: 12px; height: 12px; border-radius: var(--r-pill); flex: none; }
/* 白（まな）のドットだけ輪郭が要る。ヘアラインより一段濃い桜で描く */
.dot--outline { box-shadow: inset 0 0 0 1px var(--surface-blush-strong); }

/* ---------- 注記（暗帯。design.md: 記事ページではフッターを兼ねてよい） ---------- */
.notes__title { margin: 0 0 var(--s-md); color: var(--on-dark); font-size: 20px; font-weight: 700; }
.notes__list { margin: 0; padding-left: 1.2em; font-size: 14px; line-height: 1.9; }
.notes__list li { margin-bottom: var(--s-xxs); }
.notes__list li::marker { color: var(--primary-on-dark); }
.notes__links { display: flex; flex-wrap: wrap; gap: var(--s-xs) var(--s-lg); margin: var(--s-xl) 0 var(--s-lg); padding: 0; list-style: none; font-size: 14px; }
.notes__foot { margin: 0; font-size: 12px; line-height: 1.8; }

/* ---------- Responsive ---------- */
@media (min-width: 900px) {
  /* かたまりが列になる。列の切れ目＝曲の切れ目 */
  .sheet { grid-template-columns: repeat(3, 1fr); gap: var(--s-xxl); }
}

@media (max-width: 640px) {
  .top-nav { padding: 0 var(--s-md); }
  .top-nav__links { gap: var(--s-md); overflow-x: auto; }
  .band { padding: var(--s-xxl) var(--s-md); }
  .sheet__title { font-size: 30px; margin-bottom: var(--s-lg); }
  .sheet { gap: var(--s-xxl); }
  .call { grid-template-columns: 4.6em 1fr; }
  .call__part { font-size: 12px; }
  .call__line { font-size: 14px; }
}
</style>"""


def build(song: Song) -> str:
    blocks = "\n\n".join(render_block(label, parts) for label, parts in group(song))
    title = html.escape(song.title)

    return f"""<!DOCTYPE html>
<html lang="ja">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} コール表</title>
    <meta name="description" content="アイドルグループ『ろりぽっぷ!!!!!!!』の楽曲「{title}」のコールとメンバーパートをまとめた、ファンによる非公式のコール表です。">
    <meta name="theme-color" content="#ffffff">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap">
{STYLE}
</head>

<body>
    <nav class="top-nav">
        <a class="top-nav__brand" href="./index.html">🍭 ろりぽっぷ!!!!!!! Docs</a>
        <ul class="top-nav__links">
            <li><a href="viewer.html?file=../songs/call_list.md">全曲のコール表</a></li>
            <li><a href="viewer.html?file=../guide/starter_pack.md">はじめての方へ</a></li>
        </ul>
    </nav>

    <main>
        <!-- ブラッシュ: この1バンドだけでキャプチャが完結する -->
        <section class="band band--blush">
            <div class="band__inner">
                <p class="sheet__mark">🍭 ろりぽっぷ!!!!!!! 非公式コール表 ・ {last_updated()}時点</p>
                <h1 class="sheet__title">{title}</h1>
                <div class="sheet">
{blocks}
                </div>
            </div>
        </section>

        <!-- プラム黒: 注記とフッターを兼ねる -->
        <section class="band band--dark">
            <div class="band__inner">
                <h2 class="notes__title">この表について</h2>
                <ul class="notes__list">
                    <li>ファン有志がライブで聞き取ってまとめた非公式のコール表です。運営公認のものではありません。</li>
                    <li>コールは現場やその日の煽りで変わります。まわりに合わせるのがいちばん確実です。</li>
                    <li>メンバーパートは記録した時点のもの。編成や振り入れで変わることがあります。</li>
                </ul>
                <ul class="notes__links">
                    <li><a href="./index.html">🍭 ろりぽっぷ!!!!!!! Docs</a></li>
                    <li><a href="viewer.html?file=../songs/call_list.md">全曲のコール表</a></li>
                    <li><a href="viewer.html?file=../guide/starter_pack.md">はじめての方へ</a></li>
                    <li><a href="viewer.html?file=../members/members.md">メンバー</a></li>
                </ul>
                <p class="notes__foot">
                    ろりぽっぷ!!!!!!! は株式会社FLAP entertainment所属。
                    本サイトはファンによる非公式のドキュメントです。最新情報は公式SNSをご確認ください。
                </p>
            </div>
        </section>
    </main>
</body>

</html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--song", default=DEFAULT_SONG, help="曲名（songs/call_list.md の見出しのまま）")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="出力先のHTML")
    args = parser.parse_args()

    songs = {song.title: song for song in parse(SOURCE.read_text(encoding="utf-8"))}
    song = songs.get(args.song)
    if song is None:
        sys.exit(f"{args.song} が {SOURCE.relative_to(ROOT)} に見つからない")

    args.out.write_text(build(song), encoding="utf-8")
    blocks = group(song)
    shape = " / ".join(f"{label or '（かたまりなし）'}{len(parts)}" for label, parts in blocks)
    print(f"{args.out.relative_to(ROOT)} を生成: {song.title}（{shape}）")


if __name__ == "__main__":
    main()
