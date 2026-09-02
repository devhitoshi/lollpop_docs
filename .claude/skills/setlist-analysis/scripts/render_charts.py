"""セトリ白書の図表を events/data_event.csv から再生成する。

articles/セトリ白書/img/ の 01〜05 と同じ意味の図を、design.md の色トークンで描く。
公演が増えるたびに手で描き直さなくて済むようにするためのもの。

  01_ranking.png   楽曲別 通算披露回数（ルーツ別に色分け）
  02_heatmap.png   月別披露回数ヒートマップ（曲はセトリ初登場順）
  03_roots.png     ルーツ別披露シェアの推移（月次・100%積み上げ）
  04_position.png  オープナー率とクローザー率（披露 N 回以上の曲）
  05_shows.png     月別の集計対象公演数

使い方:
    python3 .claude/skills/setlist-analysis/scripts/render_charts.py                 # work/charts/ に出す（確認用）
    python3 .claude/skills/setlist-analysis/scripts/render_charts.py --out articles/セトリ白書/img --until 2026-08-31
    python3 ... --min-plays 25 --font "Noto Sans JP"

前提: matplotlib（`python3 -m pip install matplotlib`）と日本語フォント。
フォントは --font で指定。省略時は Noto Sans JP → Noto Sans CJK JP → WenQuanYi Zen Hei → IPAexGothic の順に探す。
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter, OrderedDict, defaultdict

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, script_dir)
from song_names import load_canonical_songs, normalize_song_name, is_non_song_item, split_setlist  # noqa: E402

import matplotlib  # noqa: E402
matplotlib.use('Agg')
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

# design.md の色トークン（chart-* と面の色）。変えるときは design.md を先に直す
C = {
    'primary': '#d6006e', 'ink': '#1d1216', 'body': '#45383e', 'muted': '#71646b', 'muted-soft': '#998a92',
    'canvas': '#ffffff', 'surface-soft': '#fff5f9', 'hairline': '#f2e2ea',
    'orig': '#d6006e', 'stk': '#2a6fd6', 'hpst': '#eda100', 'open': '#2a6fd6', 'close': '#eb6834',
    'seq': ['#fcdfee', '#f6b7d7', '#ee8abc', '#e0539b', '#c21b74', '#8f0050'],
    'grid': '#f0e2e9', 'axis': '#dcc8d2',
}
ROOTS = OrderedDict([('オリジナル', C['orig']), ('ストクレ', C['stk']), ('ハピスト', C['hpst'])])
FOOTER = "ろりぽっぷ!!!!!!!セトリ白書 ／ 集計・作図: AIぽっぱー ／ データ: 公式Xのライブ後投稿（{span}・{n}公演）"


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--out', default='work/charts', help='出力ディレクトリ（既定 work/charts。白書に反映するときだけ articles/セトリ白書/img）')
    p.add_argument('--since', help='集計開始日 YYYY-MM-DD')
    p.add_argument('--until', help='集計終了日 YYYY-MM-DD（含む）')
    p.add_argument('--min-plays', type=int, default=25, help='04 の対象にする最低披露回数')
    p.add_argument('--font', help='日本語フォント名')
    p.add_argument('--dpi', type=int, default=110)
    return p.parse_args()


def setup_font(name):
    candidates = [name] if name else []
    candidates += ['Noto Sans JP', 'Noto Sans CJK JP', 'WenQuanYi Zen Hei', 'IPAexGothic', 'Hiragino Sans', 'Yu Gothic']
    available = {f.name for f in font_manager.fontManager.ttflist}
    for c in candidates:
        if c in available:
            plt.rcParams['font.family'] = c
            return c
    print("日本語フォントが見つからない。--font で指定するか、fonts-noto-cjk を入れる", file=sys.stderr)
    return None


def load_roots(canonical):
    roots = {}
    section = None
    with open('songs/楽曲一覧.md', encoding='utf-8') as f:
        for line in f:
            if line.startswith('## 音楽配信先'):
                break
            m = re.match(r'^## \d\.\s*(オリジナル|ストクレ|ハピスト)', line)
            if m:
                section = m.group(1)
            m = re.match(r'^- \*\*(.+)\*\*', line)
            if m and section:
                roots[m.group(1).strip()] = section
    return roots


def load_data(since, until):
    canonical = load_canonical_songs()
    stages = []  # (date, ym, [songs])
    with open('events/data_event.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            d, sl = row['date'], row['setlist'] or ''
            if not d or not sl or 'セトリ投稿確認' in sl:
                continue
            if since and d < since or until and d > until:
                continue
            for items in split_setlist(sl):
                songs = []
                for it in items:
                    if is_non_song_item(it):
                        continue
                    s = normalize_song_name(it, canonical)
                    if s and s in canonical:
                        songs.append(s)
                if songs:
                    stages.append((d, d[:7], songs))
    return canonical, stages


def month_range(stages):
    months = sorted({ym for _, ym, _ in stages})
    y0, m0 = map(int, months[0].split('-'))
    y1, m1 = map(int, months[-1].split('-'))
    out = []
    y, m = y0, m0
    while (y, m) <= (y1, m1):
        out.append(f"{y}-{m:02d}")
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def y_in(fig, inches_from_top):
    """図の高さに関係なく、上端から一定インチの位置（figure 座標）。見出しの重なりを防ぐ。"""
    return 1 - inches_from_top / fig.get_size_inches()[1]


def frame(fig, title, subtitle, footer):
    fig.patch.set_facecolor(C['surface-soft'])
    fig.text(0.03, y_in(fig, 0.35), title, fontsize=17, fontweight='bold', color=C['ink'], va='top')
    fig.text(0.03, y_in(fig, 0.75), subtitle, fontsize=11.5, color=C['muted'], va='top')
    fig.text(0.03, 0.012, footer, fontsize=9.5, color=C['muted-soft'], va='bottom')


def legend(fig, y, items):
    y = y_in(fig, 1.25)  # 呼び出し側の y は無視して、上端から一定の位置に置く
    x = 0.03
    for label, color in items:
        fig.patches.append(FancyBboxPatch((x, y), 0.012, 0.018, boxstyle='round,pad=0.002,rounding_size=0.006',
                                          transform=fig.transFigure, color=color, lw=0))
        fig.text(x + 0.018, y + 0.009, label, fontsize=11.5, color=C['body'], va='center')
        x += 0.02 + 0.011 * (len(label) + 2)


def style_axes(ax, xgrid=True, ygrid=False):
    ax.set_facecolor(C['surface-soft'])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(colors=C['muted'], length=0, labelsize=10.5)
    if xgrid:
        ax.xaxis.grid(True, color=C['grid'], lw=1)
    if ygrid:
        ax.yaxis.grid(True, color=C['grid'], lw=1)
    ax.set_axisbelow(True)


def chart_ranking(stages, roots, out, footer, dpi):
    total = Counter(s for _, _, songs in stages for s in songs)
    rows = sorted(total.items(), key=lambda x: -x[1])
    fig = plt.figure(figsize=(16, 0.52 * len(rows) + 3.6))
    frame(fig, "楽曲別 通算披露回数", f"{footer['span']}・{footer['n']}公演。数字はのべ披露回数。", FOOTER.format(**footer))
    legend(fig, 0.885, list(ROOTS.items()))
    ax = fig.add_axes([0.31, 0.06, 0.64, 0.79])
    style_axes(ax, xgrid=True)
    names = [s for s, _ in rows][::-1]
    vals = [v for _, v in rows][::-1]
    colors = [ROOTS.get(roots.get(s, 'オリジナル'), C['orig']) for s in names]
    ax.barh(names, vals, color=colors, height=0.55)
    for i, v in enumerate(vals):
        ax.text(v + max(vals) * 0.008, i, str(v), va='center', fontsize=10.5, color=C['body'])
    ax.xaxis.tick_top()
    ax.set_xlim(0, max(vals) * 1.08)
    ax.tick_params(axis='y', labelsize=12, colors=C['ink'])
    fig.savefig(os.path.join(out, '01_ranking.png'), dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)


def chart_heatmap(stages, roots, out, footer, dpi):
    months = month_range(stages)
    first = {}
    count = defaultdict(Counter)
    for d, ym, songs in sorted(stages):
        for s in songs:
            first.setdefault(s, d)
            count[s][ym] += 1
    order = sorted(first, key=lambda s: first[s])
    bins = [(1, 1, '1回'), (2, 3, '2–3回'), (4, 6, '4–6回'), (7, 9, '7–9回'), (10, 12, '10–12回'), (13, 10 ** 6, '13+回')]
    fig = plt.figure(figsize=(16, 0.5 * len(order) + 4.2))
    frame(fig, "月別披露回数ヒートマップ（曲はセトリ初登場順）", "色が濃いほど、その月にたくさん披露されている。", FOOTER.format(**footer))
    legend(fig, 0.9, [(lab, C['seq'][i]) for i, (_, _, lab) in enumerate(bins)])
    ax = fig.add_axes([0.32, 0.08, 0.65, 0.76])
    ax.set_facecolor(C['surface-soft'])
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_xlim(0, len(months))
    ax.set_ylim(len(order), 0)
    for i, s in enumerate(order):
        for j, ym in enumerate(months):
            if ym < first[s][:7]:
                continue
            n = count[s].get(ym, 0)
            if n == 0:
                ax.add_patch(Rectangle((j + 0.08, i + 0.1), 0.84, 0.8, facecolor='none', edgecolor=C['hairline'], lw=1))
                continue
            k = next(idx for idx, (lo, hi, _) in enumerate(bins) if lo <= n <= hi)
            ax.add_patch(FancyBboxPatch((j + 0.1, i + 0.12), 0.8, 0.76, boxstyle='round,pad=0,rounding_size=0.12',
                                        facecolor=C['seq'][k], lw=0))
    ax.set_yticks([i + 0.5 for i in range(len(order))])
    ax.set_yticklabels(order, fontsize=12, color=C['ink'])
    ax.tick_params(axis='y', pad=16)
    for i, s in enumerate(order):
        ax.plot(-0.32, i + 0.5, 'o', color=ROOTS.get(roots.get(s, 'オリジナル'), C['orig']), ms=6, clip_on=False)
    ax.set_xticks([j + 0.5 for j in range(len(months))])
    ax.set_xticklabels([str(int(m[5:])) for m in months], fontsize=10.5, color=C['muted'])
    ax.xaxis.tick_top()
    ax.tick_params(length=0)
    prev_year = None
    for j, m in enumerate(months):
        if m[:4] != prev_year:
            ax.text(j + 0.1, -0.9, m[:4], fontsize=10.5, color=C['muted'], va='bottom')
            ax.plot([j, j], [-1.2, -0.6], color=C['axis'], lw=1, clip_on=False)
            prev_year = m[:4]
    fig.text(0.03, 0.045, "空白＝その曲のセトリ初登場前。枠のみ＝レパートリー入り後、その月は披露なし。", fontsize=10.5, color=C['muted'])
    fig.savefig(os.path.join(out, '02_heatmap.png'), dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)


def chart_roots(stages, roots, out, footer, dpi):
    months = month_range(stages)
    share = {ym: Counter() for ym in months}
    for _, ym, songs in stages:
        for s in songs:
            share[ym][roots.get(s, 'オリジナル')] += 1
    fig = plt.figure(figsize=(16, 8))
    frame(fig, "ルーツ別披露シェアの推移（月次・披露回数ベース）", "各月ののべ披露回数に占める割合。", FOOTER.format(**footer))
    legend(fig, 0.86, list(ROOTS.items()))
    ax = fig.add_axes([0.06, 0.12, 0.91, 0.66])
    style_axes(ax, xgrid=False, ygrid=True)
    bottoms = [0.0] * len(months)
    pct = {}
    for name, color in ROOTS.items():
        vals = []
        for ym in months:
            tot = sum(share[ym].values()) or 1
            vals.append(100.0 * share[ym][name] / tot)
        pct[name] = vals
        ax.bar(range(len(months)), vals, bottom=bottoms, color=color, width=0.92, edgecolor=C['surface-soft'], linewidth=2)
        bottoms = [b + v for b, v in zip(bottoms, vals)]
    for j in (0, len(months) - 1):
        v = pct['オリジナル'][j]
        if v > 6:
            ax.text(j, v / 2, f"{v:.0f}%", ha='center', va='center', color='white', fontsize=12, fontweight='bold')
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ticks, labels = [], []
    for j, m in enumerate(months):
        y, mo = m[:4], int(m[5:])
        if j == 0 or mo == 1:
            ticks.append(j); labels.append(f"'{y[2:]}/{mo}")
        elif mo in (4, 7, 10):
            ticks.append(j); labels.append(str(mo))
    ax.set_xticks(ticks)
    ax.set_xticklabels(labels)
    fig.savefig(os.path.join(out, '03_roots.png'), dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)


def chart_position(stages, out, footer, dpi, min_plays):
    total, opener, closer = Counter(), Counter(), Counter()
    for _, _, songs in stages:
        for i, s in enumerate(songs):
            total[s] += 1
            if i == 0:
                opener[s] += 1
            elif i == len(songs) - 1:
                closer[s] += 1
    songs = [s for s, n in total.items() if n >= min_plays]
    songs.sort(key=lambda s: closer[s] / total[s])
    op = [100.0 * opener[s] / total[s] for s in songs]
    cl = [100.0 * closer[s] / total[s] for s in songs]
    fig = plt.figure(figsize=(16, 0.52 * len(songs) + 4))
    frame(fig, f"オープナー率とクローザー率（披露{min_plays}回以上の{len(songs)}曲・クローザー率順）",
          "1曲目・ラストは各ステージ単位で判定（2部制は部ごと）。残りは中盤。", FOOTER.format(**footer))
    legend(fig, 0.88, [('← 1曲目に置かれた割合', C['open']), ('ラストに置かれた割合 →', C['close'])])
    ax = fig.add_axes([0.3, 0.06, 0.66, 0.78])
    style_axes(ax, xgrid=True)
    ax.barh(songs, [-v for v in op], color=C['open'], height=0.55)
    ax.barh(songs, cl, color=C['close'], height=0.55)
    lim = max(max(op), max(cl)) * 1.15
    ax.set_xlim(-lim, lim)
    ax.xaxis.tick_top()
    ticks = [t for t in range(-60, 61, 20) if abs(t) <= lim]
    ax.set_xticks(ticks)
    ax.set_xticklabels([f"{abs(t)}%" if t else '0' for t in ticks])
    ax.tick_params(axis='y', labelsize=12, colors=C['ink'])
    for i, s in enumerate(songs):
        if op[i] >= 25:
            ax.text(-op[i] - lim * 0.01, i, f"{op[i]:.0f}%", ha='right', va='center', fontsize=10.5, color=C['body'])
        if cl[i] >= 25:
            ax.text(cl[i] + lim * 0.01, i, f"{cl[i]:.1f}%", ha='left', va='center', fontsize=10.5, color=C['body'])
    fig.savefig(os.path.join(out, '04_position.png'), dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)


def chart_shows(stages, out, footer, dpi):
    months = month_range(stages)
    n = Counter(ym for _, ym, _ in stages)
    fig = plt.figure(figsize=(16, 6.5))
    frame(fig, "月別の集計対象公演数", "セトリが公式投稿で確認できたステージの数（2部制は部ごとに1）。", FOOTER.format(**footer))
    ax = fig.add_axes([0.06, 0.14, 0.91, 0.66])
    style_axes(ax, xgrid=False, ygrid=True)
    vals = [n[m] for m in months]
    ax.bar(range(len(months)), vals, color=C['primary'], width=0.7)
    for j, v in enumerate(vals):
        ax.text(j, v + 0.3, str(v), ha='center', va='bottom', fontsize=10.5, color=C['body'])
    ax.set_xticks(range(len(months)))
    ax.set_xticklabels([f"'{m[2:4]}/{int(m[5:])}" if (j == 0 or m.endswith('-01')) else str(int(m[5:])) for j, m in enumerate(months)])
    fig.savefig(os.path.join(out, '05_shows.png'), dpi=dpi, facecolor=fig.get_facecolor())
    plt.close(fig)


def main():
    args = parse_args()
    font = setup_font(args.font)
    canonical, stages = load_data(args.since, args.until)
    if not stages:
        sys.exit("集計対象のステージが無い")
    roots = load_roots(canonical)
    dates = sorted(d for d, _, _ in stages)
    footer = {'span': f"{dates[0]}〜{dates[-1]}", 'n': len(stages)}
    os.makedirs(args.out, exist_ok=True)
    chart_ranking(stages, roots, args.out, footer, args.dpi)
    chart_heatmap(stages, roots, args.out, footer, args.dpi)
    chart_roots(stages, roots, args.out, footer, args.dpi)
    chart_position(stages, args.out, footer, args.dpi, args.min_plays)
    chart_shows(stages, args.out, footer, args.dpi)
    print(f"出力: {args.out}/01_ranking.png 〜 05_shows.png（{footer['span']}・{footer['n']}ステージ、フォント: {font}）")


if __name__ == '__main__':
    main()
