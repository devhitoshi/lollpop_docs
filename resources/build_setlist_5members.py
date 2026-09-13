# -*- coding: utf-8 -*-
"""`resources/setlist_5members.html`（5人体制のセトリ可視化ページ）を組み立てる。

入力は `events/data_event.csv` と `songs/楽曲一覧.md`。曲名の名寄せは
`.claude/skills/setlist-analysis/scripts/song_names.py` の共通ルールを使う。
公演が増えたら CSV を更新してからこれを回す（`python3 resources/build_setlist_5members.py`）。

色・タイポ・バンド構成の正はリポジトリルートの `design.md`。
単一ファイル完結のページなので、同じトークン値を下の CSS に転記している。
"""
import collections
import csv
import html
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / '.claude' / 'skills' / 'setlist-analysis' / 'scripts'))
from song_names import (  # noqa: E402
    is_non_song_item, load_canonical_songs, normalize_song_name, split_setlist,
)

# 5人体制の初公演。苺花なつみの卒業（2026-08-15「POPGALAXY2026」）の次の公演から。
SINCE = '2026-08-22'
OUT = PROJECT_ROOT / 'resources' / 'setlist_5members.html'
TITLE = 'ろりぽっぷ!!!!!!! 5人体制のセトリ'
ROOT_KEY = {'オリジナル': 'orig', 'ストクレ': 'stk', 'ハピスト': 'hpst'}
ROOT_LABEL = {'オリジナル': 'オリジナル曲', 'ストクレ': 'ストクレ曲', 'ハピスト': 'ハピスト曲'}

CSS = r'''/* =====================================================================
   ろりぽっぷ!!!!!!! 5人体制のセトリ
   デザインの正はリポジトリルートの design.md（実装: resources/css/style.css）。
   単一ファイル完結のため、同じトークン値をここに転記している。
   フルブリードのバンド構成。カードなし・影なし・角丸は操作要素とバッジのみ。
   ===================================================================== */
:root {
  color-scheme: light;
  --primary: #d6006e;
  --primary-on-dark: #ff9ecb;
  --canvas: #ffffff;
  --surface-blush: #fbe7f0;
  --surface-blush-strong: #f6d3e3;
  --surface-dark: #1a1113;
  --ink: #1d1216;
  --ink-2: #45383e;
  --muted: #71646b;
  --muted-soft: #998a92;
  --on-dark: #fff5f9;
  --on-dark-soft: #d9c4ce;
  --hairline: #f2e2ea;
  --hairline-soft: #faeef4;
  --grid: #f0e2e9;

  /* ルーツ別カテゴリカル（design.md チャートパレット） */
  --c-orig: #d6006e;
  --c-stk:  #2a6fd6;
  --c-hpst: #eda100;

  --r-md: 8px;
  --font: "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic Medium",
          Meiryo, sans-serif;
}

*, *::before, *::after { box-sizing: border-box; }
body {
  margin: 0;
  background: var(--canvas);
  color: var(--ink-2);
  font-family: var(--font);
  font-size: 16px;
  line-height: 1.85;
  letter-spacing: 0.01em;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--primary); }
:focus-visible { outline: 2px solid var(--primary); outline-offset: 3px; }
.sr {
  position: absolute; width: 1px; height: 1px; overflow: hidden;
  clip: rect(0 0 0 0); clip-path: inset(50%); white-space: nowrap;
}

/* ---------- top nav ---------- */
.top-nav {
  position: sticky; top: 0; z-index: 30;
  display: flex; align-items: center;
  height: 56px; padding: 0 24px;
  background: var(--canvas);
  border-bottom: 1px solid var(--hairline);
  font-size: 13px; line-height: 1;
}
.top-nav a { color: var(--ink); text-decoration: none; font-weight: 700; }

/* ---------- バンド ---------- */
.band { padding-block: 96px; padding-inline: 24px; }
.band--tight { padding-block: 64px; }
.band--blush { background: var(--surface-blush); }
.band--dark { background: var(--surface-dark); color: var(--on-dark-soft); }
.band--dark h2, .band--dark strong { color: var(--on-dark); }
.band--dark a { color: var(--primary-on-dark); }
.wrap { max-width: 1000px; margin: 0 auto; }
.wrap--prose { max-width: 720px; margin: 0 auto; }

.eyebrow {
  margin: 0 0 12px;
  font-size: 12px; font-weight: 700; line-height: 1.4; letter-spacing: 0.12em;
  color: var(--muted-soft);
}
.band--dark .eyebrow { color: var(--on-dark-soft); }
h1 {
  margin: 0 0 16px;
  font-size: 40px; font-weight: 700; line-height: 1.25; letter-spacing: -0.02em;
  color: var(--ink);
}
h2 {
  margin: 0 0 8px;
  font-size: 28px; font-weight: 700; line-height: 1.35; letter-spacing: -0.015em;
  color: var(--ink);
}
.lead { margin: 0; font-size: 20px; line-height: 1.6; color: var(--ink-2); max-width: 42em; }
.note { margin: 8px 0 0; font-size: 14px; line-height: 1.8; color: var(--muted); max-width: 46em; }
.band--dark .note { color: var(--on-dark-soft); }
.section-head { margin-bottom: 40px; }

/* ---------- 数字の帯 ---------- */
.stats {
  display: flex; flex-wrap: wrap; gap: 32px 48px;
  max-width: 1000px; margin: 0 auto;
}
.stat { min-width: 120px; }
.stat__n {
  display: block;
  font-size: 44px; font-weight: 700; line-height: 1.1; letter-spacing: -0.02em;
  color: var(--ink);
}
.stat__n em { font-style: normal; font-size: 20px; font-weight: 500; margin-left: 2px; }
.stat__k { display: block; font-size: 13px; font-weight: 500; color: var(--muted); line-height: 1.5; }

/* ---------- 持ち曲マップ ---------- */
.rootgroup + .rootgroup { margin-top: 48px; }
.rootgroup__head {
  display: flex; align-items: center; gap: 10px;
  margin: 0 0 16px; padding-bottom: 10px;
  border-bottom: 1px solid var(--hairline);
  font-size: 15px; font-weight: 700; color: var(--ink); line-height: 1.5;
}
.rootgroup__ratio { margin-left: auto; font-size: 13px; font-weight: 500; color: var(--muted); }
.swatch {
  display: inline-block; width: 12px; height: 12px; flex: none; border-radius: 9999px;
  background: var(--c-orig);
}
.swatch--stk { background: var(--c-stk); }
.swatch--hpst { background: var(--c-hpst); }
.chips { display: flex; flex-wrap: wrap; gap: 8px; margin: 0; padding: 0; list-style: none; }
.chip {
  display: inline-flex; align-items: center; gap: 8px;
  padding: 6px 10px 6px 12px;
  border-radius: 9999px;
  font-size: 14px; line-height: 1.5;
}
.chip--on { color: #ffffff; font-weight: 500; }
.chip--on[data-root="orig"] { background: var(--c-orig); }
.chip--on[data-root="stk"]  { background: var(--c-stk); }
.chip--on[data-root="hpst"] { background: var(--c-hpst); color: #3b2600; }
.chip--off {
  background: transparent; color: var(--muted);
  border: 1px dashed var(--muted-soft);
}
.chip__n {
  display: inline-flex; align-items: center; justify-content: center;
  min-width: 22px; height: 20px; padding: 0 5px;
  border-radius: 9999px;
  background: rgba(255, 255, 255, 0.28);
  font-size: 12px; font-weight: 700; line-height: 1;
}
.chip--on[data-root="hpst"] .chip__n { background: rgba(0, 0, 0, 0.14); }
.chip__n--off { background: transparent; color: var(--muted-soft); }
.legend {
  display: flex; flex-wrap: wrap; gap: 8px 24px;
  margin: 0 0 32px; padding: 0; list-style: none;
  font-size: 13px; color: var(--muted);
}
.legend li { display: flex; align-items: center; gap: 8px; }
.legend .chip { pointer-events: none; }

/* ---------- 横棒（ランキング） ---------- */
.bars { margin: 0; padding: 0; list-style: none; }
.bar {
  display: grid;
  grid-template-columns: minmax(0, 15em) 1fr 3em;
  align-items: center; gap: 16px;
  padding: 8px 0;
  border-bottom: 1px solid var(--hairline-soft);
}
.bar__label { font-size: 14px; color: var(--ink); overflow-wrap: anywhere; }
.bar__track { height: 14px; background: var(--grid); }
.bar__fill { display: block; height: 100%; background: var(--c-orig); }
.bar__fill--stk { background: var(--c-stk); }
.bar__fill--hpst { background: var(--c-hpst); }
.bar__val { font-size: 14px; font-weight: 700; color: var(--ink); text-align: right; font-variant-numeric: tabular-nums; }

/* ---------- 公演×曲マトリクス ---------- */
.matrix-scroll { overflow-x: auto; padding-bottom: 8px; }
.matrix { border-collapse: collapse; font-size: 13px; background: var(--canvas); }
.matrix th, .matrix td { padding: 0; }
.matrix thead th {
  vertical-align: bottom; padding: 0 0 10px;
  border-bottom: 1px solid var(--hairline);
  font-size: 11px; font-weight: 700; color: var(--muted);
  white-space: nowrap;
}
.matrix thead th span { display: block; width: 40px; text-align: center; }
.matrix thead th small { display: block; font-size: 11px; font-weight: 400; }
.matrix__corner { text-align: left !important; padding-left: 16px !important; }
.matrix thead th:first-child { padding-left: 0 !important; }
.matrix__corner span { width: auto !important; }
.matrix tbody th, .matrix tfoot th {
  position: sticky; left: 0; z-index: 1;
  padding: 0 16px 0 0;
  background: var(--canvas);
  font-weight: 400; text-align: left; white-space: nowrap;
  color: var(--ink);
}
.matrix tbody tr { border-bottom: 1px solid var(--hairline-soft); }
.matrix tfoot th, .matrix tfoot td {
  padding-top: 8px; border-top: 1px solid var(--hairline);
  font-size: 12px; color: var(--muted);
}
/* .sr（読み上げ用テキスト）は position:absolute。セルを位置決めの基準にしないと
   ページ全体の右端に飛び出して、横スクロールが生まれる。 */
.cell { position: relative; height: 30px; text-align: center; }
.cell--sum { font-weight: 700; color: var(--ink); font-variant-numeric: tabular-nums; padding-left: 16px; }
.dot { display: inline-block; width: 12px; height: 12px; border-radius: 9999px; background: var(--c-orig); }
.dot--stk { background: var(--c-stk); }
.dot--hpst { background: var(--c-hpst); }
.dot--off { background: var(--grid); width: 6px; height: 6px; }
.dot--twice { box-shadow: 0 0 0 3px var(--canvas), 0 0 0 5px currentColor; color: var(--muted-soft); }

/* ---------- 一覧行 ---------- */
.evlist { margin: 0; padding: 0; list-style: none; }
.ev {
  display: flex; align-items: baseline; gap: 16px;
  padding: 16px 0;
  border-bottom: 1px solid var(--hairline);
  font-size: 16px;
}
.ev__date { flex: none; width: 6.5em; font-size: 14px; color: var(--muted); font-variant-numeric: tabular-nums; }
.ev__root { align-self: center; }
.ev__name { flex: 1 1 auto; color: var(--ink); overflow-wrap: anywhere; }
.ev__venue { display: block; font-size: 13px; color: var(--muted); }
.ev__n { flex: none; font-size: 14px; font-weight: 700; color: var(--ink); }

.two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 48px; }
.band--dark dt { font-weight: 700; color: var(--on-dark); margin-top: 20px; font-size: 15px; }
.band--dark dd { margin: 4px 0 0; font-size: 14px; line-height: 1.8; }

@media (max-width: 780px) {
  .band { padding-block: 64px; }
  h1 { font-size: 30px; }
  h2 { font-size: 23px; }
  .lead { font-size: 17px; }
  .stat__n { font-size: 34px; }
  .stats { gap: 24px 32px; }
  .bar { grid-template-columns: minmax(0, 9.5em) 1fr 2.4em; gap: 10px; }
  .two-col { grid-template-columns: 1fr; gap: 32px; }
  .ev { flex-wrap: wrap; gap: 4px 12px; }
  .ev__date { width: auto; }
}

/* ---------- 前後比較（ダンベル） ---------- */
.db__axis {
  display: grid; grid-template-columns: 15rem minmax(0, 1fr) 4.5rem; gap: 16px;
  margin: 0 0 6px; font-size: 11px; color: var(--muted-soft); line-height: 1;
}
.db__axis-in { grid-column: 2; display: flex; justify-content: space-between; margin: 0 7px; }
.dbs { margin: 0; padding: 0; list-style: none; }
.db {
  display: grid; grid-template-columns: 15rem minmax(0, 1fr) 4.5rem;
  align-items: center; gap: 16px;
  padding: 7px 0;
  border-bottom: 1px solid rgba(255, 255, 255, 0.6);
}
.db__label { font-size: 14px; color: var(--ink); overflow-wrap: anywhere; }
.db__track {
  position: relative; height: 14px; margin: 0 7px;
  background: linear-gradient(to bottom, transparent 6px, rgba(255,255,255,0.85) 6px,
              rgba(255,255,255,0.85) 8px, transparent 8px);
}
.db__line {
  position: absolute; top: 6px; height: 2px;
  background: var(--muted-soft);
}
.db__pt {
  position: absolute; top: 1px;
  width: 12px; height: 12px; margin-left: -6px;
  border-radius: 9999px;
  background: var(--canvas);
  border: 2px solid var(--muted-soft);
}
.db__pt--after { border: 0; background: var(--c-orig); }
.db__pt--stk { background: var(--c-stk); }
.db__pt--hpst { background: var(--c-hpst); }
.db__val {
  font-size: 13px; font-weight: 700; text-align: right;
  font-variant-numeric: tabular-nums; color: var(--muted);
}
.db__val--up, .db__val--down, .db__val--flat { color: var(--ink); }
.db__unit { font-size: 10px; font-weight: 500; margin-left: 1px; }
.db__key {
  display: flex; align-items: center; gap: 6px;
  margin: 20px 0 0; font-size: 13px; color: var(--muted);
}
.db__key .db__pt { position: static; margin: 0 2px 0 12px; }
.db__key .db__pt:first-child { margin-left: 0; }

/* ---------- ランキングの通算 ---------- */
.bar { grid-template-columns: minmax(0, 15em) 1fr 2.6em 5em; }
.bar__sub { font-size: 12px; color: var(--muted-soft); text-align: right; font-variant-numeric: tabular-nums; }

/* ---------- 本文の細部 ---------- */
code {
  font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
  font-size: 0.88em;
  background: var(--hairline-soft);
  padding: 1px 5px;
}
.band--dark code { background: rgba(255, 255, 255, 0.1); }
dl { margin: 0; }
dt:first-of-type { margin-top: 0; }

@media (max-width: 780px) {
  .bar { grid-template-columns: minmax(0, 9.5em) 1fr 2.2em 4.2em; gap: 8px; }
  .db, .db__axis { grid-template-columns: 8.5rem minmax(0, 1fr) 3.6rem; gap: 8px; }
  .db__label, .bar__label { font-size: 13px; }
}

/* ---------- セトリ全文 ---------- */
.sets {
  display: grid; grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 48px 64px;
}
.set__meta {
  display: flex; align-items: baseline; gap: 12px;
  margin: 0 0 2px;
  font-size: 13px; color: var(--muted); font-variant-numeric: tabular-nums;
}
.set__n { margin-left: auto; font-weight: 700; color: var(--ink); }
.set__title {
  margin: 0; font-size: 17px; font-weight: 700; line-height: 1.5; color: var(--ink);
  overflow-wrap: anywhere;
}
.set__venue {
  margin: 2px 0 12px; padding-bottom: 12px;
  border-bottom: 1px solid var(--hairline);
  font-size: 13px; color: var(--muted);
}
.set__list { margin: 0; padding: 0; list-style: none; }
.si {
  display: grid; grid-template-columns: 2em 12px 1fr;
  align-items: baseline; gap: 10px;
  padding: 3px 0;
  font-size: 15px; color: var(--ink);
}
.si__no { font-size: 12px; color: var(--muted-soft); font-variant-numeric: tabular-nums; text-align: right; }
.si .swatch { align-self: center; }
.si__name { overflow-wrap: anywhere; }
.si--marker { grid-template-columns: 2em 1fr; }
.si--marker .si__name {
  grid-column: 2 / -1;
  font-size: 12px; font-weight: 700; letter-spacing: 0.12em; color: var(--muted-soft);
}
.si--other .si__name { color: var(--muted); }
.si__tag {
  margin-left: 8px; padding: 2px 8px;
  border-radius: 9999px; background: var(--hairline);
  font-size: 11px; font-weight: 500; color: var(--muted); white-space: nowrap;
}
.swatch--none { background: transparent; border: 1px solid var(--hairline); }
.evlist--two { columns: 2; column-gap: 48px; }
.evlist--two .ev { break-inside: avoid; }

@media (max-width: 780px) {
  .sets { grid-template-columns: 1fr; gap: 40px; }
  .evlist--two { columns: 1; }
}
'''

BODY = r'''<header class="band" id="top">
  <div class="wrap">
    <p class="eyebrow">5-MEMBER ERA / 2026-08-22 → 2026-09-06</p>
    <h1>5人体制のセトリ<br>持ち曲{{N_SONGS}}曲のうち{{N_DONE}}曲</h1>
    <p class="lead">
      ろりぽっぷ!!!!!!!が5人体制で迎えた最初の{{N_SHOWS}}公演を、
      <code>events/data_event.csv</code> のセットリストから数えました。
      持ち曲{{N_SONGS}}曲のうち{{N_DONE}}曲が舞台にのり、{{N_LEFT}}曲はまだ登場していません。
    </p>
    <p class="note">
      ファンが公式のセットリスト投稿を写しとって数えている<strong>非公式</strong>のページです。
      集計は2026年9月6日の公演まで。{{N_SHOWS}}公演ぶんなので、1公演の増減で割合が大きく動きます。
    </p>
  </div>
</header>

<section class="band band--blush band--tight" id="stats">
  <div class="stats">
    <div class="stat"><span class="stat__n">{{N_SHOWS}}</span><span class="stat__k">5人体制の公演数</span></div>
    <div class="stat"><span class="stat__n">{{N_TOTAL}}</span><span class="stat__k">のべ披露回数</span></div>
    <div class="stat"><span class="stat__n">{{N_SONGS}}</span><span class="stat__k">持ち曲</span></div>
    <div class="stat"><span class="stat__n">{{N_DONE}}<em>／{{N_SONGS}}</em></span><span class="stat__k">披露済み（{{PCT}}%）</span></div>
    <div class="stat"><span class="stat__n">{{N_LEFT}}</span><span class="stat__k">まだ登場していない曲</span></div>
  </div>
</section>

<section class="band" id="map">
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">SONG MAP</p>
      <h2>持ち曲{{N_SONGS}}曲の地図</h2>
      <p class="note">ルーツごとに並べた持ち曲の全体像。色が付いているのが5人体制で披露された曲で、
        数字はこの{{N_SHOWS}}公演での回数です。点線の枠はまだ登場していない曲。</p>
    </div>
    <ul class="legend">
      <li><span class="chip chip--on" data-root="orig"><span class="chip__name">披露済み</span><span class="chip__n">n</span></span>この期間の披露回数</li>
      <li><span class="chip chip--off"><span class="chip__name">未披露</span><span class="chip__n chip__n--off">—</span></span>この期間は登場なし</li>
    </ul>
    {{MAP}}
  </div>
</section>

<section class="band" id="ranking">
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">RANKING</p>
      <h2>5人体制での披露回数</h2>
      <p class="note">棒はこの{{N_SHOWS}}公演での回数、右の薄い数字は通算（{{N_ALLSHOWS}}公演）の回数です。
        色はルーツ（<span class="swatch"></span>オリジナル／<span class="swatch swatch--stk"></span>ストクレ／<span class="swatch swatch--hpst"></span>ハピスト）。</p>
    </div>
    {{RANK}}
  </div>
</section>

<section class="band band--blush" id="change">
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">BEFORE / AFTER</p>
      <h2>出番の変わりかた</h2>
      <p class="note">1公演あたりでその曲が出てくる割合を、5人体制より前（{{N_PRESHOWS}}公演）と
        5人体制（{{N_SHOWS}}公演）で並べました。上ほど出番が増えた曲です。
        右側の丸が5人体制、左の薄い丸が前。{{N_SHOWS}}公演ぶんの数字なので、傾向として読んでください。</p>
    </div>
    {{DUMBBELL}}
  </div>
</section>

<section class="band" id="matrix">
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">MATRIX</p>
      <h2>どの公演で何をやったか</h2>
      <p class="note">縦が曲、横が公演日。丸が付いているところが披露された曲です。
        二重丸は1公演で2回披露された曲（8/26 2部の「夏色ラムネ」）。横にスクロールできます。</p>
    </div>
    {{MATRIX}}
  </div>
</section>

<section class="band band--blush" id="unplayed">
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">NOT YET</p>
      <h2>まだ登場していない{{N_LEFT}}曲</h2>
      <p class="note">この{{N_SHOWS}}公演で出番が無かっただけで、セットリストから外れたかどうかは分かりません。
        公式の告知を確認してください。</p>
    </div>
    <ul class="evlist evlist--two">{{UNPLAYED}}</ul>
  </div>
</section>

<section class="band" id="setlist">
  <div class="wrap">
    <div class="section-head">
      <p class="eyebrow">SETLIST</p>
      <h2>{{N_SHOWS}}公演のセトリ全文</h2>
      <p class="note">記録どおりの並びです。曲名・番号・SE・MC も公式のセットリスト投稿の表記のまま載せています。
        丸の色はルーツ（<span class="swatch"></span>オリジナル／<span class="swatch swatch--stk"></span>ストクレ／<span class="swatch swatch--hpst"></span>ハピスト）。
        「持ち曲外」はソロ曲・カバー曲で、回数の集計には入れていません。</p>
    </div>
    {{SETLISTS}}
  </div>
</section>

<section class="band band--dark band--tight" id="method">
  <div class="wrap--prose">
    <p class="eyebrow">METHOD</p>
    <h2>数えかた</h2>
    <dl>
      <dt>期間</dt>
      <dd>2026年8月22日〜2026年9月6日。8月15日「POPGALAXY2026」を最後に6人体制が終わり、
        次の公演である8月22日「ガラストロメ!!」から5人体制になりました。</dd>
      <dt>出どころ</dt>
      <dd>公式のセットリスト投稿を写した <code>events/data_event.csv</code>（全{{N_ALLSHOWS}}公演）。
        曲名の表記ゆれは <code>.claude/skills/setlist-analysis</code> の名寄せルールで揃えています。</dd>
      <dt>持ち曲{{N_SONGS}}曲</dt>
      <dd><code>songs/楽曲一覧.md</code> の内訳。オリジナル11曲・ストクレ10曲・ハピスト5曲。
        ソロ曲とカバー曲は持ち曲に数えていません。</dd>
      <dt>のべ回数</dt>
      <dd>1公演で2回披露された曲は2回として数えます（8/26 2部の「夏色ラムネ」）。
        SE・MC・企画コーナーは除いています。</dd>
      <dt>気をつけること</dt>
      <dd>母数が{{N_SHOWS}}公演なので、1回の増減が割合を大きく動かします。
        セットリストが公開されていない公演があれば、その分は数に入っていません。</dd>
    </dl>
  </div>
</section>
'''


def e(s):
    return html.escape(str(s))


def load_roots():
    """`songs/楽曲一覧.md` の見出しから、曲名 → ルーツ（オリジナル/ストクレ/ハピスト）を作る。"""
    roots, current = {}, None
    with open(PROJECT_ROOT / 'songs' / '楽曲一覧.md', encoding='utf-8') as f:
        for line in f:
            if line.startswith('## 音楽配信先'):
                break
            if line.startswith('## 1.'):
                current = 'オリジナル'
            elif line.startswith('## 2.'):
                current = 'ストクレ'
            elif line.startswith('## 3.'):
                current = 'ハピスト'
            m = re.match(r'^- \*\*(.+?)\*\*', line)
            if m and current:
                roots[m.group(1).strip()] = current
    return roots


def read_events():
    """集計対象の公演行（セトリのある行）を日付順に返す。"""
    with open(PROJECT_ROOT / 'events' / 'data_event.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            setlist = row['setlist'].strip()
            if not setlist or 'セトリ投稿確認' in setlist:
                continue
            yield row


def count_songs(canon, rows):
    """公演行から曲名を名寄せして数える（1公演で2回やった曲は2回）。"""
    counts = collections.Counter()
    for row in rows:
        for part in split_setlist(row['setlist']):
            for item in part:
                if is_non_song_item(item):
                    continue
                name = normalize_song_name(item, canon)
                if name:
                    counts[name] += 1
    return counts


def parse_setlist(setlist, canon):
    """セトリを記録どおりの並びで項目に分ける（SE・MC・アンコールも残す）。"""
    items = []
    for raw in setlist.split(';'):
        raw = raw.strip()
        if not raw:
            continue
        m = re.match(r'^(\d+)[\s\.]*(.*)$', raw)
        no, name = (m.group(1), m.group(2).strip()) if m else ('', raw)
        if is_non_song_item(raw) or raw == 'アンコール':
            items.append({'no': no, 'name': name, 'kind': 'marker', 'song': None})
            continue
        song = normalize_song_name(raw, canon)
        # 名寄せできない項目はソロ曲・カバー曲。持ち曲ではないので回数に入れない。
        items.append({'no': no, 'name': name, 'kind': 'song' if song else 'other', 'song': song})
    return items


def build():
    canon = load_canonical_songs(str(PROJECT_ROOT / 'songs' / '楽曲一覧.md'))
    roots = load_roots()
    rows = list(read_events())
    era = [r for r in rows if r['date'] >= SINCE]
    before = [r for r in rows if r['date'] < SINCE]

    counts = count_songs(canon, era)
    pre = count_songs(canon, before)
    total = count_songs(canon, rows)
    performed = set(counts)
    n_shows, n_pre, n_all = len(era), len(before), len(rows)
    n_total = sum(counts.values())
    ranked = sorted(counts.items(), key=lambda kv: (-kv[1], canon.index(kv[0])))

    # 同じ日に2公演あるときは ①② を付けて区別する。
    by_date = collections.Counter(r['date'] for r in era)
    seen = collections.Counter()
    shows = []
    for r in era:
        seen[r['date']] += 1
        items = parse_setlist(r['setlist'], canon)
        shows.append({
            'date': r['date'], 'event': r['event'], 'venue': r['venue'], 'items': items,
            'label': r['date'][5:].replace('-', '/'),
            'part': '①②③'[seen[r['date']] - 1] if by_date[r['date']] > 1 else '',
            'songs': [i['song'] for i in items if i['kind'] == 'song'],
        })

    # ---- 持ち曲の地図（ルーツ別に、披露済みと未披露を並べる） ----
    groups = []
    for rt in ['オリジナル', 'ストクレ', 'ハピスト']:
        songs = [s for s in canon if roots.get(s) == rt]
        chips = []
        for s in songs:
            n = counts.get(s, 0)
            badge = ('<span class="chip__n">%d</span>' % n) if n else '<span class="chip__n chip__n--off">—</span>'
            chips.append('<li class="chip chip--%s" data-root="%s"><span class="chip__name">%s</span>%s</li>'
                         % ('on' if n else 'off', ROOT_KEY[rt], e(s), badge))
        groups.append('<div class="rootgroup"><p class="rootgroup__head">'
                      '<span class="swatch swatch--%s"></span>%s'
                      '<span class="rootgroup__ratio">%d / %d 曲</span></p>'
                      '<ul class="chips">%s</ul></div>'
                      % (ROOT_KEY[rt], ROOT_LABEL[rt],
                         len([s for s in songs if s in performed]), len(songs), ''.join(chips)))
    song_map = '\n'.join(groups)

    # ---- 披露回数ランキング（通算を併記） ----
    top = ranked[0][1]
    rank = '<ol class="bars">%s</ol>' % ''.join(
        '<li class="bar"><span class="bar__label">%s</span>'
        '<span class="bar__track"><span class="bar__fill bar__fill--%s" style="width:%.1f%%"></span></span>'
        '<span class="bar__val">%d</span><span class="bar__sub">通算 %d</span></li>'
        % (e(s), ROOT_KEY[roots[s]], n / top * 100, n, total.get(s, 0)) for s, n in ranked)

    # ---- 5人体制より前との出現率の比較（ダンベル） ----
    changes = sorted(
        ((s, pre.get(s, 0) / n_pre * 100, counts.get(s, 0) / n_shows * 100) for s in canon),
        key=lambda x: -(x[2] - x[1]))
    db_rows = []
    for s, b, a in changes:
        diff = a - b
        sign = '+' if diff > 0 else ('−' if diff < 0 else '±')
        cls = 'up' if diff > 0 else ('down' if diff < 0 else 'flat')
        db_rows.append(
            '<li class="db"><span class="db__label">%s</span><span class="db__track">'
            '<span class="db__line" style="left:%.1f%%;width:%.1f%%"></span>'
            '<span class="db__pt db__pt--before" style="left:%.1f%%" title="5人体制より前 %.0f%%"></span>'
            '<span class="db__pt db__pt--after db__pt--%s" style="left:%.1f%%" title="5人体制 %.0f%%"></span>'
            '</span><span class="db__val db__val--%s">%s%.0f<span class="db__unit">pt</span></span>'
            '<span class="sr">5人体制より前 %.0f%% → 5人体制 %.0f%%</span></li>'
            % (e(s), min(b, a), abs(diff), b, b, ROOT_KEY[roots[s]], a, a, cls, sign, abs(diff), b, a))
    dumbbell = ('<p class="db__axis"><span class="db__axis-in">'
                '<span>0%</span><span>50%</span><span>100%</span></span></p>'
                '<ol class="dbs">' + ''.join(db_rows) + '</ol>'
                '<p class="db__key"><span class="db__pt db__pt--before"></span>'
                '5人体制より前（' + str(n_pre) + '公演）　'
                '<span class="db__pt db__pt--after db__pt--orig"></span>'
                '5人体制（' + str(n_shows) + '公演）</p>')

    # ---- 公演×曲のマトリクス ----
    head = ''.join('<th scope="col"><span>%s<small>%s</small></span></th>'
                   % (e(s['label']), e(s['part']) or '&nbsp;') for s in shows)
    matrix_rows = []
    for s, n in ranked:
        cells = []
        for show in shows:
            c = show['songs'].count(s)
            if not c:
                cells.append('<td class="cell"><span class="dot dot--off"></span><span class="sr">なし</span></td>')
            else:
                cells.append('<td class="cell"><span class="dot dot--%s%s"></span><span class="sr">%s</span></td>'
                             % (ROOT_KEY[roots[s]], ' dot--twice' if c > 1 else '', '2回' if c > 1 else '披露'))
        matrix_rows.append('<tr><th scope="row">%s</th>%s<td class="cell cell--sum">%d</td></tr>'
                           % (e(s), ''.join(cells), n))
    matrix = ('<div class="matrix-scroll"><table class="matrix">'
              '<caption class="sr">公演ごとの披露曲（縦: 曲、横: 公演日）</caption>'
              '<thead><tr><th scope="col" class="matrix__corner">曲 ＼ 公演</th>%s'
              '<th scope="col" class="matrix__corner">計</th></tr></thead><tbody>%s</tbody>'
              '<tfoot><tr><th scope="row">公演ごとの曲数</th>%s<td class="cell cell--sum">%d</td></tr>'
              '</tfoot></table></div>'
              % (head, ''.join(matrix_rows),
                 ''.join('<td class="cell cell--sum">%d</td>' % len(s['songs']) for s in shows), n_total))

    # ---- まだ登場していない曲 ----
    unplayed = ''.join(
        '<li class="ev"><span class="ev__root swatch swatch--%s"></span>'
        '<span class="ev__name">%s<span class="ev__venue">%s ／ 通算 %d回</span></span></li>'
        % (ROOT_KEY[roots[s]], e(s), ROOT_LABEL[roots[s]], total.get(s, 0))
        for s in canon if s not in performed)

    # ---- セトリ全文 ----
    blocks = []
    for s in shows:
        lis = []
        for it in s['items']:
            if it['kind'] == 'marker':
                lis.append('<li class="si si--marker"><span class="si__no"></span>'
                           '<span class="si__name">%s</span></li>' % e(it['name']))
            elif it['kind'] == 'song':
                lis.append('<li class="si"><span class="si__no">%s</span>'
                           '<span class="swatch swatch--%s"></span>'
                           '<span class="si__name">%s</span></li>'
                           % (e(it['no']), ROOT_KEY[roots[it['song']]], e(it['name'])))
            else:
                lis.append('<li class="si si--other"><span class="si__no">%s</span>'
                           '<span class="swatch swatch--none"></span>'
                           '<span class="si__name">%s<span class="si__tag">持ち曲外</span></span></li>'
                           % (e(it['no']), e(it['name'])))
        blocks.append('<article class="set"><p class="set__meta"><span class="set__date">%s</span>'
                      '<span class="set__n">%d曲</span></p><h3 class="set__title">%s</h3>'
                      '<p class="set__venue">%s</p><ol class="set__list">%s</ol></article>'
                      % (e(s['date']), len(s['songs']), e(s['event']), e(s['venue']), ''.join(lis)))
    setlists = '<div class="sets">%s</div>' % ''.join(blocks)

    body = BODY
    for key, value in [
        ('{{MAP}}', song_map), ('{{RANK}}', rank), ('{{DUMBBELL}}', dumbbell),
        ('{{MATRIX}}', matrix), ('{{UNPLAYED}}', unplayed), ('{{SETLISTS}}', setlists),
        ('{{N_SHOWS}}', n_shows), ('{{N_TOTAL}}', n_total), ('{{N_SONGS}}', len(canon)),
        ('{{N_DONE}}', len(performed)), ('{{N_LEFT}}', len(canon) - len(performed)),
        ('{{PCT}}', round(len(performed) / len(canon) * 100)),
        ('{{N_ALLSHOWS}}', n_all), ('{{N_PRESHOWS}}', n_pre),
    ]:
        body = body.replace(key, str(value))
    if '{{' in body:
        raise SystemExit('本文に未置換のプレースホルダが残っている: ' + body[body.index('{{'):body.index('{{') + 40])

    desc = ('ろりぽっぷ!!!!!!!が5人体制になった2026年8月22日以降の%d公演から、持ち曲%d曲のうち'
            '披露済みの%d曲をグラフにしたページです。' % (n_shows, len(canon), len(performed)))
    page = ('<!DOCTYPE html>\n<html lang="ja">\n<head>\n<meta charset="UTF-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            '<title>%s</title>\n<meta name="description" content="%s">\n'
            '<meta name="theme-color" content="#ffffff">\n'
            '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?'
            'family=Noto+Sans+JP:wght@400;500;700&display=swap">\n</head>\n<body>\n'
            '<nav class="top-nav"><a href="./index.html">🍭 ろりぽっぷ!!!!!!! Docs</a></nav>\n'
            '<style>\n%s</style>\n%s\n</body>\n</html>\n' % (e(TITLE), e(desc), CSS, body))
    OUT.write_text(page, encoding='utf-8')
    print('%s を書きました（%d公演 / 持ち曲%d曲 / 披露%d曲 / のべ%d回）'
          % (OUT.relative_to(PROJECT_ROOT), n_shows, len(canon), len(performed), n_total))


if __name__ == '__main__':
    build()
