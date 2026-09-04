#!/usr/bin/env python3
"""songs/call_list.md の1曲分から、SNSキャプチャ用の1枚もののコール表を作る。

    python3 resources/build_call_sheet.py                      # 未完成ヒロイン・4色
    python3 resources/build_call_sheet.py --song 乙女ロック      # 別の曲
    python3 resources/build_call_sheet.py --colors navy         # 色を選ぶ

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
- 同じ内容を PALETTES の色ちがいで並べる。投稿する色を選ぶためのもの。
  ベージュと紺は design.md の4面（白・ブラッシュ・プラム黒・ピンク）に無い色で、
  このページのキャプチャ用バリアント。採用する色が決まったら design.md に足す。
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
DEFAULT_CARDS_OUTPUT = ROOT / "resources" / "call_sheet_cards.html"

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

# キャプチャ用の色ちがい。帯ごとにトークンを差し替えるだけで、組み方は同じ。
# 白とブラッシュは design.md の面そのもの。ベージュと紺はこのページ用の拡張で、
# 紺は暗い面なので design.md の「暗帯ではアクセントを明るい側へ反転する」に倣い、
# メンバーカラーも明るい方へ振る（濃い赤・緑は暗い面に沈んでドットが読めない）。
PALETTES = {
    "white": {
        "label": "白",
        "tokens": {
            "ground": "#ffffff",
            "title": "#1d1216",
            "text": "#45383e",
            "sub": "#71646b",
            "meta": "#998a92",
            "line": "#f2e2ea",
            "ring": "#f6d3e3",
            "accent": "#d6006e",
            "on-accent": "#ffffff",
        },
    },
    "beige": {
        "label": "ベージュ",
        "tokens": {
            "ground": "#f5efe4",
            "title": "#2a2118",
            "text": "#4a4036",
            "sub": "#77695a",
            "meta": "#9a8d7c",
            "line": "#e6dbc9",
            "ring": "#ddd0ba",
            "accent": "#b0005b",
            "on-accent": "#ffffff",
        },
    },
    "blush": {
        "label": "ピンク",
        "tokens": {
            "ground": "#fbe7f0",
            "title": "#1d1216",
            "text": "#45383e",
            "sub": "#71646b",
            "meta": "#998a92",
            "line": "#f6d3e3",
            "ring": "#f6d3e3",
            "accent": "#d6006e",
            "on-accent": "#ffffff",
        },
    },
    "navy": {
        "label": "紺",
        "tokens": {
            "ground": "#101b2f",
            "title": "#f2f5fb",
            "text": "#ccd6ea",
            "sub": "#a9b7d2",
            "meta": "#8fa0c0",
            "line": "#26334f",
            "ring": "transparent",  # 白いドットは暗い面では輪郭が要らない
            # 暗い面では濃いピンクが沈むので、design.md に倣って明るいピンクに反転する
            "accent": "#ff9ecb",
            "on-accent": "#101b2f",
        },
        "members": {
            "--mc-kurumi": "#ff5f5f",
            "--mc-mayu": "#ffd633",
            "--mc-ami": "#4fd28a",
            "--mc-asaka": "#ff9ec4",
            "--mc-natsumi": "#6f9fe8",
        },
    },
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

    heading = f'          <h3 class="block__label">{html.escape(label)}</h3>\n' if label else ""
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

/* ---------- Sub nav（ページのクローム。design.md の Docs 例外） ---------- */
.sub-nav {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--s-xs) var(--s-lg);
  padding: var(--s-sm) var(--s-lg);
  background-color: var(--canvas);
  border-bottom: 1px solid var(--hairline);
}

.sub-nav__title { margin: 0; color: var(--ink); font-size: 17px; font-weight: 700; line-height: 1.5; }
.sub-nav__note { margin: 0; color: var(--muted); font-size: 13px; line-height: 1.5; }
.sub-nav__colors { display: flex; flex-wrap: wrap; gap: var(--s-md); margin: 0 0 0 auto; padding: 0; list-style: none; font-size: 13px; font-weight: 500; }
.sub-nav__colors a { color: var(--primary); text-decoration: none; }

/* ---------- Band ---------- */
.band { padding: var(--s-band) var(--s-lg); }
.band__inner { max-width: 1200px; margin: 0 auto; }

.band--dark  { background-color: var(--surface-dark); color: var(--on-dark-soft); }
.band--dark a { color: var(--primary-on-dark); text-decoration: none; }

/* コール表の帯。色ちがいはトークンの差し替えだけで、組み方は共通 */
.sheet-band { background-color: var(--ground); color: var(--text); }

/* ---------- 見出し（ワードマーク・非公式・時点まで同じ面に置く） ---------- */
.sheet__mark {
  margin: 0 0 var(--s-xs);
  color: var(--meta);
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 1.6;
}

.sheet__title {
  margin: 0 0 var(--s-xl);
  color: var(--title);
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
  color: var(--title);
  font-size: 15px;
  font-weight: 700;
  line-height: 1.5;
  letter-spacing: 0.06em;
}

/* コール行。1行が1レコードなので、ここは線を引いてよい場所 */
.calls { border-top: 1px solid var(--line); }

.call {
  display: grid;
  grid-template-columns: 4.8em 1fr;
  gap: var(--s-xxs) var(--s-sm);
  padding: var(--s-sm) 0;
  border-bottom: 1px solid var(--line);
}

.call__part {
  margin: 0;
  color: var(--title);
  font-size: 13px;
  font-weight: 700;
  line-height: 1.7;
}

.call__body { min-width: 0; }

.call__line {
  margin: 0;
  color: var(--text);
  font-size: 15px;
  line-height: 1.7;
}

.call__line + .call__line { margin-top: 2px; }

/* メンバー名は担当カラーのドット付きで */
.chips { display: inline-flex; flex-wrap: wrap; align-items: center; gap: var(--s-xxs) var(--s-xs); }
.chip { display: inline-flex; align-items: center; gap: 6px; color: var(--title); font-weight: 700; }
.chip__arrow { margin-right: 2px; color: var(--meta); font-size: 13px; font-weight: 400; }
.chip__label { color: var(--sub); font-size: 13px; }

.dot { width: 12px; height: 12px; border-radius: var(--r-pill); flex: none; }
/* 白（まな）のドットだけ輪郭が要る。明るい面では地より一段濃い線、暗い面では無し */
.dot--outline { box-shadow: inset 0 0 0 1px var(--ring); }

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


STYLE_CARDS = """<style>
/* =====================================================================
   ろりぽっぷ!!!!!!! コール表 — SNSに載せる1枚（1曲 = 1枚）
   このファイルは resources/build_call_sheet.py が生成する。直接編集しない。

   1枚 1080x1920（9:16）。スマホでは 9:16 までの縦画像は画面の幅いっぱい
   （約390px）で表示されるので、縦に伸ばしても文字は小さくならない。
   本文46pxは、幅390pxに縮んだとき約17pxで見える（スマホの本文と同じくらい）。
   だから拡大せずに読めて、1曲を1枚に収められる。

   横長にすると幅が文字数で埋まり、同じ内容が4px相当まで縮む。3枚に割ると
   1曲が散らばってSNSで追えない。どちらも試して却下した（2026-09-04）。

   組み方は横長版（call_sheet.html）と別:
   - パート名は左の細い列。本文は右で、行を折り返しても頭が揃う。
   - 「1番 / 2番 / ラスト」は行の流れを切る見出しとして挟む。
   - 同じ指示の繰り返し（イントロ・間奏・アウトロ）は「〜と同じ」に畳む。
     繰り返しに縦を使うと、その分だけ本文を小さくすることになるため。
   色トークンと配色の考え方は call_sheet.html と共通。デザインの正は design.md。
   ===================================================================== */
:root {
  --font: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic Medium", Meiryo, sans-serif;

  /* メンバーカラー（装飾専用）。紺のカードだけ PALETTES 側で明るい方に振り替える */
  --mc-kurumi: #cc0000;
  --mc-mayu: #f5c400;
  --mc-mau: #7fd4e8;
  --mc-ami: #2e9e5b;
  --mc-mana: #ffffff;
  --mc-asaka: #f172a3;
  --mc-natsumi: #2a6fd6;
}

*, *::before, *::after { box-sizing: border-box; }

body {
  margin: 0;
  /* カードの外。撮るのはカードだけなので、境目が分かる中間色にしておく */
  background-color: #9a8f94;
  font-family: var(--font);
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 48px;
  padding: 48px;
}

.card {
  width: 1800px;
  padding: 76px 72px;
  background-color: var(--ground);
  color: var(--text);
  display: flex;
  flex-direction: column;
  letter-spacing: 0.01em;
}

.card__mark {
  margin: 0 0 16px;
  color: var(--meta);
  font-size: 32px;
  font-weight: 700;
  letter-spacing: 0.06em;
  line-height: 1.4;
}

.card__title {
  margin: 0 0 10px;
  color: var(--title);
  font-size: 104px;
  font-weight: 700;
  line-height: 1.15;
  letter-spacing: -0.02em;
}

/* かたまりの見出し。1番 / 2番 / ラストを色の帯にして、上に間を空けて積む。
   帯があると3つのまとまりが一目で分かり、どこを見ているか迷わない */
.block {
  margin: 56px 0 0;
  padding: 14px 26px;
  background-color: var(--accent);
  color: var(--on-accent);
  font-size: 42px;
  font-weight: 700;
  line-height: 1.3;
  letter-spacing: 0.12em;
}

.block:first-child { margin-top: 0; }

.card__sub {
  margin: 0 0 34px;
  color: var(--sub);
  font-size: 40px;
  font-weight: 700;
  letter-spacing: 0.1em;
  line-height: 1.4;
}

.card__note {
  margin: 34px 0 0;
  color: var(--meta);
  font-size: 32px;
  font-weight: 500;
  line-height: 1.6;
}

.rows { border-top: 3px solid var(--line); }

/* 1行 = 1パート。左にパート名、右に中身 */
.row {
  display: grid;
  grid-template-columns: 190px 1fr;
  gap: 0 26px;
  padding: 18px 0;
  border-bottom: 3px solid var(--line);
}



.row__part {
  margin: 0;
  color: var(--meta);
  font-size: 36px;
  font-weight: 700;
  line-height: 1.9;
  letter-spacing: 0.02em;
}

.row__body { min-width: 0; }

/* 合図とメンバーの並び。ここが一番大きい＝一番先に目に入る */
.line {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 6px 22px;
  margin: 0;
  color: var(--text);
  font-size: 54px;
  font-weight: 500;
  line-height: 1.4;
}

/* 説明文は一段小さく。読むのは目を留めたときでいい */
.line--note {
  display: block;
  font-size: 38px;
  font-weight: 400;
  line-height: 1.5;
  color: var(--sub);
}

/* 「イントロと同じ」の繰り返しは、本文より落として流し読みできるように */
.line--same { font-size: 40px; font-weight: 400; color: var(--sub); }

.line + .line { margin-top: 4px; }

/* メンバー名は担当カラーのドット付きで */
.chips { display: inline-flex; flex-wrap: wrap; align-items: center; gap: 6px 18px; }
.chip { display: inline-flex; align-items: center; gap: 15px; color: var(--title); font-weight: 700; }
.chip__arrow { margin-right: 6px; color: var(--meta); font-size: 38px; font-weight: 400; }
.chip__label { color: var(--sub); font-size: 40px; }

.dot { width: 38px; height: 38px; border-radius: 9999px; flex: none; }
.dot--outline { box-shadow: inset 0 0 0 2px var(--ring); }
</style>"""


def palette_css(colors: list[str]) -> str:
    """色ちがいの帯ごとにトークンを差し替えるCSSを組む。"""
    rules = []
    for key in colors:
        palette = PALETTES[key]
        decls = "".join(f"  --{name}: {value};\n" for name, value in palette["tokens"].items())
        decls += "".join(f"  {name}: {value};\n" for name, value in palette.get("members", {}).items())
        rules.append(f".sheet-band--{key} {{\n{decls}}}")
    return "\n/* ---------- 色ちがい ---------- */\n" + "\n\n".join(rules) + "\n"


def render_sheet(song: Song, blocks: str, key: str, mark: str) -> str:
    return (
        f'        <!-- {PALETTES[key]["label"]}: この1バンドだけでキャプチャが完結する -->\n'
        f'        <section class="band sheet-band sheet-band--{key}" id="{key}">\n'
        '          <div class="band__inner">\n'
        f'            <p class="sheet__mark">{mark}</p>\n'
        f'            <h2 class="sheet__title">{html.escape(song.title)}</h2>\n'
        '            <div class="sheet">\n'
        f"{blocks}\n"
        "            </div>\n"
        "          </div>\n"
        "        </section>"
    )


# 「見出しになる短い指示」の目安。これ以下は本文サイズ、超えたら説明文サイズ。
# 振りコピとか / メンバーコール / ケチャ のような合図は大きく、
# 長い説明は一段小さくして、1枚に収まる密度にする。
SHORT = 20


def part_lines(part: Part) -> list[str]:
    """1パート分の表示行。"""
    lines = []
    for item in part.items:
        lines.append(item.text)
        lines.extend(item.subs)
    return lines


def render_lines(lines: list[str]) -> str:
    """行をまとめる。パートの1行目とメンバーの並びは大きく、補足は一段小さく。

    1行目は「そのパートで何をするか」なので必ず大きくする。長い説明でも小さくすると、
    イントロや2間奏（MIXの掛け声）のように文で書かれたパートだけ弱く見えてしまう。
    2行目以降の補足（コツや但し書き）は一段落として、目を留めたときに読めればいい。

    「メンバーコール」と「あみ→くるみ」は別々の行にすると縦を倍使うので、
    横に並べて入るなら1行に流す（入らなければ折り返す）。
    """
    out = []
    index = 0
    while index < len(lines):
        line = lines[index]
        first = not out
        is_route = bool(ROUTE_RE.match(line))

        if not first and not is_route and len(line) > SHORT:
            out.append(f'<p class="line line--note">{render_text(line)}</p>')
            index += 1
            continue

        chunk = [render_text(line)]
        index += 1
        while index < len(lines) and ROUTE_RE.match(lines[index]):
            chunk.append(render_text(lines[index]))
            index += 1
        out.append(f'<p class="line">{"".join(chunk)}</p>')
    return "".join(out)


def render_card(song: Song, colors_key: str, mark: str) -> str:
    """1曲まるごとを1枚に。SNSに載せるのはこれ1枚。"""
    # 同じ指示の繰り返しは「〜と同じ」に畳む。イントロ・間奏・アウトロは同じ44文字で、
    # そのまま3回出すと縦が埋まり、その分だけ本文を小さくすることになる。
    seen: dict[tuple[str, ...], str] = {}
    body = []
    for label, parts in group(song):
        if label:
            body.append(f'        <p class="block">{html.escape(label)}</p>')
        for part in parts:
            lines = part_lines(part)
            key = tuple(lines)
            if key in seen:
                content = f'<p class="line line--same">{html.escape(seen[key])}と同じ</p>'
            else:
                seen[key] = part.name
                content = render_lines(lines)
            body.append(
                '        <div class="row">\n'
                f'          <p class="row__part">{html.escape(part.name)}</p>\n'
                f'          <div class="row__body">{content}</div>\n'
                "        </div>"
            )

    return (
        f'    <section class="card sheet-band--{colors_key}" id="card-{colors_key}">\n'
        f'      <p class="card__mark">{mark}</p>\n'
        f'      <h2 class="card__title">{html.escape(song.title)}</h2>\n'
        '      <p class="card__sub">コール表</p>\n'
        '      <div class="rows">\n'
        + "\n".join(body)
        + "\n      </div>\n"
        '      <p class="card__note">コールは現場やその日の煽りで変わります。まわりに合わせるのがいちばん確実です。</p>\n'
        "    </section>"
    )


def build_cards(song: Song, colors: list[str]) -> str:
    """SNS用の縦型カードを色ちがいで並べたページ。1曲 = 1枚。撮るのはカードだけ。"""
    mark = f"🍭 ろりぽっぷ!!!!!!! 非公式コール表 ・ {last_updated()}時点"
    cards = "\n\n".join(render_card(song, key, mark) for key in colors)
    style = STYLE_CARDS.replace("</style>", palette_css(colors) + "</style>")

    return f"""<!DOCTYPE html>
<html lang="ja">

<head>
    <meta charset="UTF-8">
    <title>{html.escape(song.title)} コール表（SNS用）</title>
    <meta name="robots" content="noindex">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap">
{style}
</head>

<body>
{cards}
</body>

</html>
"""


def build(song: Song, colors: list[str]) -> str:
    blocks = "\n\n".join(render_block(label, parts) for label, parts in group(song))
    title = html.escape(song.title)
    mark = f"🍭 ろりぽっぷ!!!!!!! 非公式コール表 ・ {last_updated()}時点"

    sheets = "\n\n".join(render_sheet(song, blocks, key, mark) for key in colors)
    style = STYLE.replace("</style>", palette_css(colors) + "</style>")

    if len(colors) > 1:
        picker = (
            '            <p class="sub-nav__note">背景ちがい。好きな帯をそのままキャプチャしてください</p>\n'
            '            <ul class="sub-nav__colors">\n'
            + "".join(
                f'                <li><a href="#{key}">{PALETTES[key]["label"]}</a></li>\n'
                for key in colors
            )
            + "            </ul>\n"
        )
    else:
        picker = ""

    return f"""<!DOCTYPE html>
<html lang="ja">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} コール表</title>
    <meta name="description" content="アイドルグループ『ろりぽっぷ!!!!!!!』の楽曲「{title}」のコールとメンバーパートをまとめた、ファンによる非公式のコール表です。">
    <meta name="theme-color" content="#ffffff">
    <link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&display=swap">
{style}
</head>

<body>
    <nav class="top-nav">
        <a class="top-nav__brand" href="./index.html">🍭 ろりぽっぷ!!!!!!! Docs</a>
        <ul class="top-nav__links">
            <li><a href="viewer.html?file=../songs/call_list.md">全曲のコール表</a></li>
            <li><a href="viewer.html?file=../guide/starter_pack.md">はじめての方へ</a></li>
        </ul>
    </nav>

    <div class="sub-nav">
        <h1 class="sub-nav__title">{title} コール表</h1>
{picker}    </div>

    <main>
{sheets}

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
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="出力先のHTML（横長のページ）")
    parser.add_argument(
        "--cards-out", type=Path, default=DEFAULT_CARDS_OUTPUT, help="出力先のHTML（SNS用の縦型カード）"
    )
    choices = "、".join(f"{key}={palette['label']}" for key, palette in PALETTES.items())
    parser.add_argument(
        "--colors",
        default=",".join(PALETTES),
        help=f"背景の色をカンマ区切りで（{choices}）",
    )
    args = parser.parse_args()

    colors = [key.strip() for key in args.colors.split(",") if key.strip()]
    unknown = [key for key in colors if key not in PALETTES]
    if unknown or not colors:
        sys.exit(f"知らない色: {'、'.join(unknown) or '(指定なし)'}。選べるのは {'、'.join(PALETTES)}")

    songs = {song.title: song for song in parse(SOURCE.read_text(encoding="utf-8"))}
    song = songs.get(args.song)
    if song is None:
        sys.exit(f"{args.song} が {SOURCE.relative_to(ROOT)} に見つからない")

    args.out.write_text(build(song, colors), encoding="utf-8")
    args.cards_out.write_text(build_cards(song, colors), encoding="utf-8")

    blocks = group(song)
    shape = " / ".join(f"{label or '（かたまりなし）'}{len(parts)}" for label, parts in blocks)
    palette = "・".join(PALETTES[key]["label"] for key in colors)
    for path, what in ((args.out, "横長"), (args.cards_out, f"縦型カード{len(blocks) * len(colors)}枚")):
        resolved = path.resolve()
        where = resolved.relative_to(ROOT) if resolved.is_relative_to(ROOT) else resolved
        print(f"{where} を生成: {song.title}（{shape}）背景: {palette} — {what}")


if __name__ == "__main__":
    main()
