"""取得済みの X 投稿から、画像・動画の索引を作る（縦型動画の素材探し用）。

ダウンロードはしない。「いつ・誰が・どの公演で・どんな向きの素材を上げたか」を一覧にして、
縦型（9:16 寄り）の候補を絞り込み、許諾を取る相手を見つけられるようにする。

出力: data/x/media_index_<since>_<until>.csv（追跡する。URL と数値だけで、画像そのものは含まない）

列:
  date, time, source（公式/メンバー/他人）, author, name, event, 撮影ルール, type（photo/video）,
  orientation（縦/横/正方形）, width, height, duration_s, likes, views, post_url, media_url, best_mp4, dl_flag

- エゴサーチ由来（他人の投稿）は、x-egosearch で「採用」と判定したものだけを入れる。
  絞らないと同名の別グループ（名古屋の Lollipop♡CHU）や対バン相手の写真が混ざる
- event は events/data_event.csv の同日の公演名（複数あれば「/」で連結、無ければ空）
- 撮影ルールは guide/rules.md の区分。主催・単独・ワンマン・生誕は「主催（動画全編可）」、
  それ以外の公演日は「対バン（静止画のみ・動画は指定曲）」、公演の無い日は空。**推定なので現物で確認する**
- dl_flag は X の allow_download_status（true のとき 1）。X 上の保存可否であって、利用許諾ではない

使い方:
    python3 .claude/skills/x-media-collect/scripts/build_media_index.py --since 2026-08-01 --until 2026-08-31
    python3 ... --orientation 縦 --type video      # 絞り込んで表示だけ確認
"""
import argparse
import csv
import glob
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, os.path.join(project_root, '.claude/skills/x-account-fetch/scripts'))
from fetch_accounts import DEFAULT_ACCOUNTS  # noqa: E402

JST = timezone(timedelta(hours=9))
OFFICIAL = 'lollipop_1116'
MEMBERS = {h for h, _ in DEFAULT_ACCOUNTS if h != OFFICIAL} | {'asaka_lpop', 'natsumi_lpop', 'Ichii_h77'}
LABELS = dict(DEFAULT_ACCOUNTS)
# guide/rules.md: 主催ライブは静止画・動画とも全編可（掲載も可）。対バンは静止画のみ全編可、動画は指定曲のみ
SELF_HOSTED = re.compile(r'単独|ワンマン|主催|生誕|定期公演')
DATA_DIR = 'data/x'
COLUMNS = ['date', 'time', 'source', 'author', 'name', 'event', '撮影ルール', 'type', 'orientation',
           'width', 'height', 'duration_s', 'likes', 'views', 'post_url', 'media_url', 'best_mp4', 'dl_flag']


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--since', required=True, help='開始日 YYYY-MM-DD（含む）')
    p.add_argument('--until', required=True, help='終了日 YYYY-MM-DD（含む）')
    p.add_argument('--x-dir', default='work/x_fetch')
    p.add_argument('--out', help='出力先（既定: data/x/media_index_<since>_<until>.csv）')
    p.add_argument('--orientation', choices=['縦', '横', '正方形'], help='この向きだけ集計・出力する')
    p.add_argument('--type', dest='mtype', choices=['photo', 'video'], help='この種別だけ')
    p.add_argument('--source', choices=['公式', 'メンバー', '他人', '公式・メンバー'], help='この出どころだけ')
    p.add_argument('--no-filter-judged', action='store_true',
                   help='エゴサーチの判定で除外した投稿も索引に入れる（既定は除外。別グループの写真が混ざる）')
    return p.parse_args()


def adopted_ids(since, until):
    """エゴサーチで採用と判定した投稿ID。判定ファイル（data/x/）と triage の規則から作る。

    索引に判定を効かせないと、同名の別グループ（名古屋の Lollipop♡CHU）や、対バン相手を撮った写真が
    「ろりぽっぷの素材」として並んでしまう。
    """
    final = os.path.join('work/x_fetch', f"egosearch_triage_{since}_{until}_final.jsonl")
    if os.path.exists(final):
        ids = set()
        for l in open(final, encoding='utf-8'):
            try:
                ids.add(str(json.loads(l).get('id')))
            except json.JSONDecodeError:
                pass
        return ids, final
    return None, None


def jst(t):
    for fmt in ('%a %b %d %H:%M:%S %z %Y', '%Y-%m-%dT%H:%M:%S%z'):
        try:
            return datetime.strptime(t.get('createdAt') or '', fmt).astimezone(JST)
        except ValueError:
            continue
    return None


def load_events():
    by_date = {}
    with open('events/data_event.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            by_date.setdefault(row['date'], []).append(row['event'])
    return by_date


def shoot_rule(events):
    if not events:
        return ''
    if any(SELF_HOSTED.search(e) for e in events):
        return '主催（静止画・動画とも全編可・掲載可）'
    return '対バン（静止画は全編可・動画は指定曲のみ）'


def orientation(w, h):
    if not w or not h:
        return ''
    if h > w * 1.1:
        return '縦'
    if w > h * 1.1:
        return '横'
    return '正方形'


def best_mp4(m):
    """動画の変種から、いちばん高ビットレートの mp4 を選ぶ（縦型に切り出す元にする）。"""
    vs = [v for v in ((m.get('video_info') or {}).get('variants') or []) if v.get('content_type') == 'video/mp4']
    if not vs:
        return ''
    return max(vs, key=lambda v: v.get('bitrate') or 0).get('url', '')


def rows_from(path, events_by_date, since, until):
    rows = []
    for line in open(path, encoding='utf-8'):
        line = line.strip()
        if not line:
            continue
        try:
            t = json.loads(line)
        except json.JSONDecodeError:
            continue
        d = jst(t)
        if not d or not (since <= d.date().isoformat() <= until):
            continue
        media = (t.get('extendedEntities') or {}).get('media') or []
        if not media:
            continue
        a = t.get('author') or {}
        handle = a.get('userName') or ''
        source = '公式' if handle == OFFICIAL else ('メンバー' if handle in MEMBERS else '他人')
        date = d.date().isoformat()
        events = events_by_date.get(date, [])
        for m in media:
            oi = m.get('original_info') or {}
            w, h = oi.get('width'), oi.get('height')
            vi = m.get('video_info') or {}
            rows.append({
                'date': date, 'time': d.strftime('%H:%M'), 'source': source,
                'author': handle, 'name': LABELS.get(handle, a.get('name') or ''),
                'event': ' / '.join(events), '撮影ルール': shoot_rule(events),
                'type': m.get('type') or '', 'orientation': orientation(w, h),
                'width': w or '', 'height': h or '',
                'duration_s': round(vi['duration_millis'] / 1000) if vi.get('duration_millis') else '',
                'likes': t.get('likeCount', ''), 'views': t.get('viewCount', ''),
                'post_url': t.get('url') or f"https://x.com/{handle}/status/{t.get('id')}",
                'media_url': m.get('media_url_https') or '', 'best_mp4': best_mp4(m),
                'dl_flag': 1 if (m.get('allow_download_status') or {}).get('allow_download') else '',
            })
    return rows


def main():
    args = parse_args()
    events_by_date = load_events()
    adopted, adopted_src = (None, None) if args.no_filter_judged else adopted_ids(args.since, args.until)
    rows = []
    for p in sorted(glob.glob(os.path.join(args.x_dir, '*.jsonl'))):
        base = os.path.basename(p)
        if 'triage' in base:
            continue
        got = rows_from(p, events_by_date, args.since, args.until)
        # エゴサーチ由来（他人の投稿）だけ、判定で採用したものに絞る。公式・メンバーは判定の対象外
        if adopted is not None and base.startswith('egosearch_'):
            got = [r for r in got if r['post_url'].rsplit('/', 1)[-1] in adopted]
        rows += got
    # 同じメディアが複数のクエリで重複することがある
    seen, uniq = set(), []
    for r in rows:
        key = (r['post_url'], r['media_url'])
        if key not in seen:
            seen.add(key)
            uniq.append(r)
    rows = sorted(uniq, key=lambda r: (r['date'], r['time']))

    if args.orientation:
        rows = [r for r in rows if r['orientation'] == args.orientation]
    if args.mtype:
        rows = [r for r in rows if r['type'] == args.mtype]
    if args.source:
        want = {'公式', 'メンバー'} if args.source == '公式・メンバー' else {args.source}
        rows = [r for r in rows if r['source'] in want]

    out = args.out or f"data/x/media_index_{args.since}_{args.until}.csv"
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8', newline='') as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(rows)

    print(f"書き出した: {out}（{len(rows)} 件）")
    if adopted_src:
        print(f"  エゴサーチ分は判定済みの採用のみ（{adopted_src}）。--no-filter-judged で全件")
    elif not args.no_filter_judged:
        print("  警告: エゴサーチの判定ファイルが無いので絞り込めていない。"
              "別グループ・他グループの写真が混ざる。先に x-egosearch の triage を実行する")
    print("  出どころ: " + ', '.join(f"{k} {v}" for k, v in Counter(r['source'] for r in rows).most_common()))
    print("  種別:     " + ', '.join(f"{k} {v}" for k, v in Counter(r['type'] for r in rows).most_common()))
    print("  向き:     " + ', '.join(f"{k or '不明'} {v}" for k, v in Counter(r['orientation'] for r in rows).most_common()))
    vert_own = [r for r in rows if r['orientation'] == '縦' and r['source'] in ('公式', 'メンバー')]
    vert_video = [r for r in rows if r['orientation'] == '縦' and r['type'] == 'video']
    print(f"  縦型のうち公式・メンバー: {len(vert_own)} 件 / 縦型の動画: {len(vert_video)} 件")
    self_hosted = [r for r in rows if r['撮影ルール'].startswith('主催')]
    print(f"  主催・単独の日の素材（動画も全編撮影可・掲載可の日）: {len(self_hosted)} 件")
    print("\n注意: 索引は公開投稿のメタデータ。他人の投稿の素材を使うには本人の許諾が要る。"
          "\n      dl_flag は X 上の保存可否であって、利用許諾ではない。撮影ルールは公演名からの推定。")


if __name__ == '__main__':
    main()
