#!/usr/bin/env python3
"""曲の印象（かわいい↔かっこいい × 湧き↔エモい）の一覧と、十字マトリクスの図を作る。

入力（songs/analysis/character/）:
    raw/[曲名]__run1.json   1 曲ずつ聴かせた採点（listen_agy.py）
    raw/_ranking.json       全曲を聴き比べさせた採点（rank_agy.py）
    owner_check.json        2 回が食い違った曲について、オーナーがどちらが近いかを答えた記録
    lyrics_scores.json      歌詞だけを読んで付けた採点

出力:
    songs/analysis/song_character.md    人が読む一覧（自動生成。手で直さない）
    songs/analysis/song_character.csv   位置の数値
    work/charts/song_character.html     図の確認用（リポジトリには入らない）

    python3 .claude/skills/music-analysis/scripts/build_character.py
"""

import csv
import datetime
import html
import json
import sys
from pathlib import Path

project_root = Path(__file__).resolve().parents[4]

ANALYSIS_DIR = project_root / "songs" / "analysis"
CHARACTER_DIR = ANALYSIS_DIR / "character"
RAW_DIR = CHARACTER_DIR / "raw"
OUT_MD = ANALYSIS_DIR / "song_character.md"
OUT_CSV = ANALYSIS_DIR / "song_character.csv"
OUT_CHART = project_root / "work" / "charts" / "song_character.html"

X_AXIS, Y_AXIS = "cute_cool", "waki_emo"
X_WORDS, Y_WORDS = ("かわいい", "かっこいい"), ("湧き", "エモい")

# 2 回の採点がこれ以上離れた曲は、オーナーの確認が要る。
GAP_LIMIT = 1.5

SIZE, PAD = 720, 64
SPAN = 3.4  # 図の軸の表示範囲（±）


def fail(message):
    print(f"ERROR: {message}", file=sys.stderr)
    sys.exit(1)


def read_json(path):
    if not path.exists():
        fail(f"{path.relative_to(project_root)} がありません。")
    return json.loads(path.read_text(encoding="utf-8"))


def in_words(value, words):
    """位置の数値を、記事で使える言葉にする。"""
    low, high = words
    if value <= -2:
        return low
    if value <= -0.75:
        return f"{low}寄り"
    if value < 0.75:
        return "中間"
    if value < 2:
        return f"{high}寄り"
    return high


def load():
    ranking = {t["song"]: t for t in read_json(RAW_DIR / "_ranking.json")["tracks"]}
    owner = read_json(CHARACTER_DIR / "owner_check.json")
    lyrics = read_json(CHARACTER_DIR / "lyrics_scores.json")["songs"]

    songs = []
    for song in sorted(ranking):
        solo_axes = read_json(RAW_DIR / f"{song}__run1.json")["axes"]
        solo = (solo_axes[X_AXIS], solo_axes[Y_AXIS])
        rank = (ranking[song][X_AXIS], ranking[song][Y_AXIS])
        check = owner.get(song, {})
        trust = check.get("trust")
        gap = max(abs(solo[0] - rank[0]), abs(solo[1] - rank[1]))

        # オーナーが「こちらが近い」と答えた曲はその回の値、ほかは 2 回の平均。
        sound = {"solo": solo, "rank": rank}.get(trust, ((solo[0] + rank[0]) / 2, (solo[1] + rank[1]) / 2))
        # オーナーの言葉に合わせて手で動かした位置があれば、それを優先する。
        over = check.get("override", {})
        sound = (over.get(X_AXIS, sound[0]), over.get(Y_AXIS, sound[1]))
        moved = "（オーナーの言葉に合わせて手で移動）" if over else ""

        if trust:
            status = "確認済み"
        elif gap < GAP_LIMIT:
            status = "2回一致"
        else:
            status = "要確認"

        if song not in lyrics:
            fail(f"lyrics_scores.json に {song} がありません。")
        words = (lyrics[song][X_AXIS], lyrics[song][Y_AXIS])
        songs.append(
            {
                "song": song,
                "solo": solo,
                "rank": rank,
                "gap": gap,
                "trust": trust,
                "moved": moved,
                "status": status,
                "sound": sound,
                "lyrics": words,
                "lyrics_reason": lyrics[song].get("reason", ""),
                "distance": ((sound[0] - words[0]) ** 2 + (sound[1] - words[1]) ** 2) ** 0.5,
                "confirmed": check.get("confirmed", ""),
                "owner_comment": check.get("owner_comment", ""),
                "rejected": check.get("rejected", ""),
            }
        )
    return songs


def write_csv(songs, today):
    header = [
        "song", "status", "sound_cute_cool", "sound_waki_emo", "lyrics_cute_cool", "lyrics_waki_emo",
        "sound_lyrics_distance", "run1_cute_cool", "run1_waki_emo", "ranking_cute_cool", "ranking_waki_emo", "built_at",
    ]
    with OUT_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for s in songs:
            writer.writerow(
                [
                    s["song"], s["status"], f"{s['sound'][0]:.2f}", f"{s['sound'][1]:.2f}", s["lyrics"][0], s["lyrics"][1],
                    f"{s['distance']:.2f}", s["solo"][0], s["solo"][1], s["rank"][0], s["rank"][1], today,
                ]
            )


def write_markdown(songs, today):
    lines = [
        "# 曲の印象（かわいい↔かっこいい × 湧き↔エモい）",
        "",
        "> `.claude/skills/music-analysis/scripts/build_character.py` による自動生成です。**手で直さないでください。**",
        "> 直すのは `character/owner_check.json`（オーナーの確認）と `character/lyrics_scores.json`（歌詞の採点）です。",
        f"> 生成日: {today}",
        "",
        "## 読み方",
        "",
        "- **音の位置**は、AI（Antigravity）に曲名を伏せて 2 回聴かせた採点です（1 曲ずつ／全曲の聴き比べ）。測定値ではなく印象です。",
        "- **歌詞の位置**は、歌詞だけを読んで付けた採点です。音は聴いていません。",
        "- 値は −3〜+3。横はマイナスが「かわいい」、プラスが「かっこいい」。縦はマイナスが「湧き」、プラスが「エモい」。",
        "- **状態**",
        "  - `確認済み`: 2 回の説明が食い違った曲で、オーナーがどちらが近いかを答えた。位置も説明も記事に書いてよい",
        f"  - `2回一致`: 2 回の採点の差が {GAP_LIMIT} 未満。オーナーの個別の確認は無い。位置は書いてよいが、楽器などの説明は確認してから書く",
        "  - `要確認`: 2 回が食い違い、まだ確認していない。記事に書かない",
        "",
        "記事で書いてよい範囲の正は [`README.md`](./README.md) です。",
        "",
        "## 音の位置",
        "",
        "| 曲 | かわいい↔かっこいい | 湧き↔エモい | 状態 | 確認済みの説明 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for s in songs:
        said = "／".join(x for x in (s["confirmed"], f"オーナー:「{s['owner_comment']}」" if s["owner_comment"] else "") if x) or "—"
        lines.append(
            f"| {s['song']} | {in_words(s['sound'][0], X_WORDS)}（{s['sound'][0]:+.1f}） "
            f"| {in_words(s['sound'][1], Y_WORDS)}（{s['sound'][1]:+.1f}） | {s['status']} | {said} |"
        )

    rejected = [s for s in songs if s["rejected"]]
    if rejected:
        lines += [
            "",
            "### AI が外した説明（事実としては書かない）",
            "",
            "2 回のうち片方が出した説明で、オーナーが「違う」と答えたものです。同じ説明が再び出ても採用しないでください。"
            "「AI はこう聴き間違えた」という例として記事で紹介するのは構いません。",
            "",
        ]
        lines += [f"- {s['song']}: {s['rejected']}" for s in rejected]

    lines += [
        "",
        "## 音と歌詞の離れ具合",
        "",
        "距離が大きい曲ほど、音の印象と歌詞の内容が離れています（2 軸の上での直線距離）。",
        "",
        "| 曲 | 音 | 歌詞 | 距離 | 歌詞の採点の根拠 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for s in sorted(songs, key=lambda s: -s["distance"]):
        lines.append(
            f"| {s['song']} | {in_words(s['sound'][0], X_WORDS)}・{in_words(s['sound'][1], Y_WORDS)} "
            f"| {in_words(s['lyrics'][0], X_WORDS)}・{in_words(s['lyrics'][1], Y_WORDS)} | {s['distance']:.1f} | {s['lyrics_reason']} |"
        )

    lines += [
        "",
        "## 2 回の採点の内訳",
        "",
        "| 曲 | 1 曲ずつ（横 / 縦） | 聴き比べ（横 / 縦） | 差 | 採用 |",
        "| --- | --- | --- | --- | --- |",
    ]
    adopted = {"solo": "1 曲ずつ", "rank": "聴き比べ", "both": "平均（どちらも近い）", None: "平均"}
    for s in songs:
        lines.append(
            f"| {s['song']} | {s['solo'][0]:+d} / {s['solo'][1]:+d} | {s['rank'][0]:+.1f} / {s['rank'][1]:+.1f} "
            f"| {s['gap']:.1f} | {adopted[s['trust']]}{s['moved']} |"
        )
    lines.append("")
    OUT_MD.write_text("\n".join(lines), encoding="utf-8", newline="")


# ---- 図（確認用） ----


def px(v):
    return PAD + (v + SPAN) / (2 * SPAN) * (SIZE - 2 * PAD)


def py(v):
    return SIZE - px(v)


def spread_lyrics(songs):
    """歌詞の採点は整数なので、他の点（歌詞どうし・別の曲の音）と重なる点を少しずらして描く。"""
    used = [s["sound"] for s in songs]
    for s in songs:
        x, y = s["lyrics"]
        while any(abs(x - u[0]) < 0.2 and abs(y - u[1]) < 0.2 for u in used):
            x, y = x + 0.24, y - 0.12
        used.append((x, y))
        s["lyrics_draw"] = (x, y)


def place_labels(songs):
    """ラベルを点の周りの候補位置から、他の点・ラベルとの重なりが最も少ない位置に置く。"""
    boxes = []
    for s in songs:
        for key, r in (("sound", 9), ("lyrics_draw", 7)):
            x, y = px(s[key][0]), py(s[key][1])
            boxes.append((x - r, y - r, x + r, y + r))
    for s in sorted(songs, key=lambda s: -s["sound"][1]):
        x, y = px(s["sound"][0]), py(s["sound"][1])
        w, h = sum(7.5 if ord(c) < 128 else 13.5 for c in s["song"]) + 6, 18
        candidates = [
            (x + 12, y - h / 2, "start"), (x - 12 - w, y - h / 2, "end"),
            (x - w / 2, y - 14 - h, "middle"), (x - w / 2, y + 14, "middle"),
            (x + 10, y - 12 - h, "start"), (x + 10, y + 10, "start"),
            (x - 10 - w, y - 12 - h, "end"), (x - 10 - w, y + 10, "end"),
            (x + 26, y - h / 2, "start"), (x + 14, y + 24, "start"), (x - w / 2, y + 34, "middle"),
        ]
        best = None
        for bx, by, anchor in candidates:
            bx = min(max(bx, 4), SIZE - 4 - w)
            by = min(max(by, 4), SIZE - 4 - h)
            box = (bx, by, bx + w, by + h)
            clashes = sum(box[0] < b[2] and box[2] > b[0] and box[1] < b[3] and box[3] > b[1] for b in boxes)
            if best is None or clashes < best[0]:
                best = (clashes, box, anchor)
            if clashes == 0:
                break
        _, box, anchor = best
        boxes.append(box)
        tx = {"start": box[0] + 2, "end": box[2] - 2, "middle": (box[0] + box[2]) / 2}[anchor]
        s["label"] = (tx, box[1] + 13, anchor)


def svg(songs):
    e = html.escape
    lo, hi, mid = px(-SPAN), px(SPAN), px(0)
    parts = [f'<svg viewBox="0 0 {SIZE} {SIZE}" role="img" aria-label="曲の位置。横軸はかわいい〜かっこいい、縦軸は湧き〜エモい">']
    for v in (-3, -2, -1, 1, 2, 3):
        parts.append(f'<line class="grid" x1="{px(v):.1f}" y1="{lo}" x2="{px(v):.1f}" y2="{hi}"/>')
        parts.append(f'<line class="grid" x1="{lo}" y1="{py(v):.1f}" x2="{hi}" y2="{py(v):.1f}"/>')
    parts.append(f'<line class="axis" x1="{lo}" y1="{mid}" x2="{hi}" y2="{mid}"/>')
    parts.append(f'<line class="axis" x1="{mid}" y1="{lo}" x2="{mid}" y2="{hi}"/>')
    parts.append(f'<text class="end" x="{lo}" y="{mid - 10}" text-anchor="start">← {X_WORDS[0]}</text>')
    parts.append(f'<text class="end" x="{hi}" y="{mid - 10}" text-anchor="end">{X_WORDS[1]} →</text>')
    parts.append(f'<text class="end" x="{mid + 10}" y="{lo + 4}" text-anchor="start">↑ {Y_WORDS[1]}</text>')
    parts.append(f'<text class="end" x="{mid + 10}" y="{hi}" text-anchor="start">↓ {Y_WORDS[0]}</text>')
    for s in songs:
        x1, y1, x2, y2 = px(s["sound"][0]), py(s["sound"][1]), px(s["lyrics_draw"][0]), py(s["lyrics_draw"][1])
        parts.append(f'<line class="link" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>')
    for i, s in enumerate(songs):
        x, y = px(s["lyrics_draw"][0]), py(s["lyrics_draw"][1])
        parts.append(f'<circle class="dot lyrics" data-i="{i}" cx="{x:.1f}" cy="{y:.1f}" r="5"/>')
    for i, s in enumerate(songs):
        x, y = px(s["sound"][0]), py(s["sound"][1])
        parts.append(f'<circle class="dot sound" data-i="{i}" cx="{x:.1f}" cy="{y:.1f}" r="7"/>')
        lx, ly, anchor = s["label"]
        parts.append(f'<text class="name" x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}">{e(s["song"])}</text>')
    for i, s in enumerate(songs):
        for key in ("sound", "lyrics_draw"):
            parts.append(f'<circle class="hit" data-i="{i}" cx="{px(s[key][0]):.1f}" cy="{py(s[key][1]):.1f}" r="16"/>')
    parts.append("</svg>")
    return "\n".join(parts)


def table(songs):
    e = html.escape
    return "\n".join(
        f"<tr><th scope='row'>{e(s['song'])}</th><td>{s['sound'][0]:+.1f}</td><td>{s['sound'][1]:+.1f}</td>"
        f"<td>{s['lyrics'][0]:+d}</td><td>{s['lyrics'][1]:+d}</td><td>{s['distance']:.1f}</td><td>{s['status']}</td></tr>"
        for s in songs
    )


# 色は dataviz スキルの基準パレット（青・橙）。明暗どちらも色覚特性つきで検証済み。
PAGE = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>曲の位置（確認用）</title>
<style>
.viz-root {
  color-scheme: light;
  --surface-1: #fcfcfb; --text-primary: #0b0b0b; --text-secondary: #52514e;
  --grid: #e8e7e3; --axis: #a3a29b; --series-1: #2a78d6; --series-2: #eb6834;
}
@media (prefers-color-scheme: dark) {
  :root:where(:not([data-theme="light"])) .viz-root {
    color-scheme: dark;
    --surface-1: #1a1a19; --text-primary: #ffffff; --text-secondary: #c3c2b7;
    --grid: #2e2e2c; --axis: #6f6e68; --series-1: #3987e5; --series-2: #d95926;
  }
}
:root[data-theme="dark"] .viz-root {
  color-scheme: dark;
  --surface-1: #1a1a19; --text-primary: #ffffff; --text-secondary: #c3c2b7;
  --grid: #2e2e2c; --axis: #6f6e68; --series-1: #3987e5; --series-2: #d95926;
}
html, body { margin: 0; }
.viz-root { background: var(--surface-1); color: var(--text-primary); min-height: 100vh; padding: 20px 16px 40px;
  font-family: "Noto Sans JP", "Yu Gothic UI", "Hiragino Sans", Meiryo, sans-serif; box-sizing: border-box; }
.wrap { max-width: 760px; margin: 0 auto; position: relative; }
h1 { font-size: 20px; margin: 0 0 6px; }
p { font-size: 13px; line-height: 1.7; color: var(--text-secondary); margin: 0 0 10px; }
.legend { display: flex; gap: 18px; font-size: 13px; margin: 8px 0 4px; flex-wrap: wrap; }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.key { width: 12px; height: 12px; border-radius: 50%; display: inline-block; }
.key.s1 { background: var(--series-1); } .key.s2 { background: var(--series-2); width: 9px; height: 9px; }
svg { width: 100%; height: auto; display: block; }
.grid { stroke: var(--grid); stroke-width: 1; }
.axis { stroke: var(--axis); stroke-width: 1.5; }
.link { stroke: var(--axis); stroke-width: 1.5; }
.end { font-size: 14px; font-weight: 700; fill: var(--text-secondary); }
.name { font-size: 13px; fill: var(--text-primary); paint-order: stroke; stroke: var(--surface-1); stroke-width: 4px; stroke-linejoin: round; }
.dot { stroke: var(--surface-1); stroke-width: 2; }
.dot.sound { fill: var(--series-1); } .dot.lyrics { fill: var(--series-2); }
.hit { fill: transparent; cursor: pointer; }
.tip { position: absolute; pointer-events: none; background: var(--surface-1); color: var(--text-primary); border: 1px solid var(--axis);
  border-radius: 6px; padding: 8px 10px; font-size: 12px; line-height: 1.6; display: none; max-width: 240px; }
.tip b { font-size: 13px; }
details { margin-top: 14px; font-size: 13px; }
summary { cursor: pointer; color: var(--text-secondary); }
.scroll { overflow-x: auto; }
table { border-collapse: collapse; margin-top: 8px; font-size: 12px; white-space: nowrap; }
th, td { border-bottom: 1px solid var(--grid); padding: 5px 9px; text-align: right; }
th[scope="row"], thead th:first-child { text-align: left; }
thead th { color: var(--text-secondary); font-weight: 600; }
</style>
</head>
<body>
<div class="viz-root"><div class="wrap">
<h1>ろりぽっぷ!!!!!!! __COUNT__曲の位置（確認用）</h1>
<p>青い点は音、橙の点は歌詞。線が長い曲ほど、音の印象と歌詞の内容が離れています。</p>
<div class="legend">
  <span><i class="key s1"></i>音（AI が曲名を伏せて聴いた採点。確認済みの曲は合っていた回、ほかは 2 回の平均）</span>
  <span><i class="key s2"></i>歌詞（歌詞だけを読んだ採点）</span>
</div>
__SVG__
<div class="tip" id="tip"></div>
<details open>
<summary>数値の表</summary>
<div class="scroll"><table>
<thead><tr><th>曲</th><th>音: 横</th><th>音: 縦</th><th>歌詞: 横</th><th>歌詞: 縦</th><th>音と歌詞の距離</th><th>状態</th></tr></thead>
<tbody>
__TABLE__
</tbody></table></div>
<p style="margin-top:10px">値は −3〜+3。横はマイナスが「かわいい」、プラスが「かっこいい」。縦はマイナスが「湧き」、プラスが「エモい」。歌詞の点がほかの点と重なる曲は、少しずらして描いています。生成日: __TODAY__</p>
</details>
</div></div>
<script>
const DATA = __DATA__;
const tip = document.getElementById('tip'), wrap = document.querySelector('.wrap');
const f = v => (v > 0 ? '+' : '') + v.toFixed(1);
document.querySelectorAll('.hit').forEach(el => {
  el.addEventListener('pointermove', ev => {
    const s = DATA[el.dataset.i], r = wrap.getBoundingClientRect();
    tip.innerHTML = `<b>${s.song}</b>（${s.status}）<br>音: 横 ${f(s.sound[0])} ／ 縦 ${f(s.sound[1])}<br>歌詞: 横 ${f(s.lyrics[0])} ／ 縦 ${f(s.lyrics[1])}`;
    tip.style.display = 'block';
    tip.style.left = Math.max(0, Math.min(ev.clientX - r.left + 14, r.width - 250)) + 'px';
    tip.style.top = (ev.clientY - r.top + 14) + 'px';
  });
  el.addEventListener('pointerleave', () => { tip.style.display = 'none'; });
});
</script>
</body>
</html>
"""


def write_chart(songs, today):
    spread_lyrics(songs)
    place_labels(songs)
    data = [{"song": s["song"], "sound": s["sound"], "lyrics": s["lyrics"], "status": s["status"]} for s in songs]
    page = (
        PAGE.replace("__SVG__", svg(songs))
        .replace("__TABLE__", table(songs))
        .replace("__DATA__", json.dumps(data, ensure_ascii=False))
        .replace("__COUNT__", str(len(songs)))
        .replace("__TODAY__", today)
    )
    OUT_CHART.parent.mkdir(parents=True, exist_ok=True)
    OUT_CHART.write_text(page, encoding="utf-8", newline="")


def main():
    today = datetime.date.today().isoformat()
    songs = load()
    write_markdown(songs, today)
    write_csv(songs, today)
    write_chart(songs, today)

    for name in (OUT_MD, OUT_CSV, OUT_CHART):
        print(f"書き出し: {name.relative_to(project_root)}")
    pending = [s["song"] for s in songs if s["status"] == "要確認"]
    if pending:
        print("オーナーの確認が要る曲:", "、".join(pending))


if __name__ == "__main__":
    main()
