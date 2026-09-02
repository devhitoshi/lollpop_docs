"""週刊・月刊まとめ記事の素材ファイルを組み立てる。

x-account-fetch で取得した公式・メンバーの投稿（work/x_fetch/*.jsonl）と、公演データ（events/data_event.csv）を
期間で切り出し、`prompts/collect/x_collect.md` の出力形式に寄せた1本の Markdown にまとめる。
執筆側（Claude）はこのファイルだけを読めば、事実の材料が揃う状態にするのが目的。

- 判断はしない。投稿の分類はキーワードの当たりで、見出しの下に候補を並べるだけ
- 原文はそのまま入れる（要旨にしない）。記事に使うときに選んで短くする
- エゴサーチ（周囲の反応）は含まれない。Grok の結果を「## 外部の反応」に貼り足す
- 出力先は既定で work/x_fetch/（.gitignore 済み）。他人の投稿原文を含むのでコミットしない

使い方:
    python3 .claude/skills/weekly-monthly-draft/scripts/build_material.py --since 2026-08-25 --until 2026-08-31
    python3 .claude/skills/weekly-monthly-draft/scripts/build_material.py --since 2026-08-01 --until 2026-08-31 --type monthly
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, os.path.join(project_root, '.claude/skills/x-account-fetch/scripts'))
sys.path.insert(0, os.path.join(project_root, '.claude/skills/setlist-analysis/scripts'))
from fetch_accounts import DEFAULT_ACCOUNTS  # noqa: E402
from check_event_consistency import looks_like_setlist, dates_mentioned  # noqa: E402

JST = timezone(timedelta(hours=9))
OFFICIAL = 'lollipop_1116'
FORMER_ACCOUNTS = [("asaka_lpop", "姫杏朝香"), ("natsumi_lpop", "苺花なつみ")]
NEW_SONG = re.compile(r'新曲|初披露|🆕|配信|リリース|MV|ミュージックビデオ', re.I)
ANNOUNCE = re.compile(r'出演|チケット|予約|グッズ|開催|OPEN|START|生誕|発売|お知らせ|決定|解禁|情報', re.I)
PRICE_TIME = re.compile(r'OPEN|START|円|¥|料金|チケット|開場|開演|無料|特典会', re.I)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--since', required=True, help='開始日 YYYY-MM-DD')
    p.add_argument('--until', required=True, help='終了日 YYYY-MM-DD（この日を含む）')
    p.add_argument('--type', choices=['weekly', 'monthly'], default='weekly')
    p.add_argument('--x-dir', default='work/x_fetch', help='取得済み JSONL のディレクトリ')
    p.add_argument('--out', help='出力先（既定: <x-dir>/draft_material_<since>_<until>.md）')
    return p.parse_args()


# ---------- 投稿の読み込み ----------

def get(t, *keys, default=None):
    for k in keys:
        v = t.get(k)
        if v not in (None, ''):
            return v
    return default


def parse_created(t):
    created = get(t, 'createdAt', 'created_at', default='')
    for fmt in ('%a %b %d %H:%M:%S %z %Y', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S%z'):
        try:
            return datetime.strptime(created, fmt).astimezone(JST)
        except ValueError:
            continue
    return None


def load_posts(path, handle):
    posts = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            dt = parse_created(t)
            if dt is None:
                continue
            text = get(t, 'text', 'full_text', default='')
            tid = str(get(t, 'id', 'id_str', 'tweet_id', 'rest_id', default=''))
            url = get(t, 'url', 'twitterUrl', default=f"https://x.com/{handle}/status/{tid}" if tid else '')
            posts.append({
                'dt': dt, 'date': dt.date(), 'text': text, 'url': url,
                'likes': get(t, 'likeCount', 'favorite_count', 'like_count', default=''),
                'rts': get(t, 'retweetCount', 'retweet_count', default=''),
                'is_reply': bool(get(t, 'isReply', 'inReplyToId', 'in_reply_to_status_id', default=False)),
                'is_rt': bool(t.get('retweeted_tweet')) or text.startswith('RT @'),
            })
    posts.sort(key=lambda p: p['dt'])
    return posts


def one_line(text, limit=None):
    s = ' '.join(text.split())
    return s if limit is None else s[:limit]


def fmt_post(p, with_metrics=True):
    tags = ''.join(f"[{t}]" for t, on in (('返信', p['is_reply']), ('RT', p['is_rt'])) if on)
    metrics = f"／いいね{p['likes']}" if with_metrics and p['likes'] != '' else ''
    return f"- [{p['date']} {p['dt'].strftime('%H:%M')}]{tags} {one_line(p['text'])}{metrics}／出典: {p['url']}"


# ---------- 組み立て ----------

def main():
    args = parse_args()
    since = datetime.strptime(args.since, '%Y-%m-%d').date()
    until = datetime.strptime(args.until, '%Y-%m-%d').date()
    out = args.out or os.path.join(args.x_dir, f"draft_material_{args.since}_{args.until}.md")

    accounts = list(DEFAULT_ACCOUNTS) + [a for a in FORMER_ACCOUNTS if os.path.exists(os.path.join(args.x_dir, f"{a[0]}.jsonl"))]
    status = []
    posts_by = {}
    for handle, label in accounts:
        path = os.path.join(args.x_dir, f"{handle}.jsonl")
        if not os.path.exists(path):
            status.append(f"- {label}（@{handle}）: **未取得**（{path} が無い）")
            posts_by[handle] = []
            continue
        all_posts = load_posts(path, handle)
        in_range = [p for p in all_posts if since <= p['date'] <= until]
        cover = f"{all_posts[0]['date']}〜{all_posts[-1]['date']}" if all_posts else 'なし'
        status.append(f"- {label}（@{handle}）: 期間内 {len(in_range)} 件（ファイル全体 {len(all_posts)} 件、{cover}）")
        posts_by[handle] = in_range

    official = posts_by.get(OFFICIAL, [])
    events = []
    with open('events/data_event.csv', 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if args.since <= row['date'] <= args.until:
                events.append(row)
    event_dates = {e['date'] for e in events}

    lines = []
    w = lines.append
    w(f"# 収集データ ろりぽっぷ!!!!!!! {args.since} 〜 {args.until}")
    w("")
    w("> このファイルは build_material.py が機械的に組み立てた素材。判断・要約はしていない。")
    w("> 記事に使うときは `prompts/collect/x_collect.md` の記録ルール（特徴的な一文を選ぶ、要旨は1〜2文、原文の丸写しは避ける）に従う。")
    w("> 他人の投稿原文を含むのでコミットしない（work/x_fetch/ は .gitignore 済み）。")
    w("")
    w("## 取得状況")
    lines.extend(status)
    w("- 外部の反応（エゴサーチ）: このファイルには含まれない。`prompts/collect/x_collect.md` の手順2を Grok で実行し、結果を「## 外部の反応」に貼る")
    w("")

    # ライブ・イベント
    w("## ライブ・イベント")
    w("（`events/data_event.csv` の期間内の行。公式投稿は同日・翌日のものを候補として添えた）")
    w("")
    for e in events:
        w(f"### [{e['date']}] {e['event']}")
        w(f"- 会場: {e['venue']}")
        w("- 時間: ")
        w("- 料金: ")
        w("- セトリ:")
        for part in (e['setlist'] or '').split('|'):
            for item in part.split(';'):
                if item.strip():
                    w(f"  - {item.strip()}")
        d = datetime.strptime(e['date'], '%Y-%m-%d').date()
        related = [p for p in official if p['date'] in (d, d + timedelta(days=1)) and not p['is_rt']]
        setlist_posts = [p for p in related if looks_like_setlist(p['text'])]
        hints = [p for p in related if p not in setlist_posts and (PRICE_TIME.search(p['text']) or d in dates_mentioned(p['text'], d.year))]
        if setlist_posts:
            w("- 公式のライブ後投稿（セトリらしきもの）:")
            for p in setlist_posts:
                w("  " + fmt_post(p, with_metrics=False))
        if hints:
            w("- 公式の同日投稿（時間・料金・当日の告知の手がかり）:")
            for p in hints:
                w("  " + fmt_post(p, with_metrics=False))
        w("- 公式の記述: ")
        w("- 出典: " + (setlist_posts[0]['url'] if setlist_posts else ''))
        w("")
    if not events:
        w("（期間内の公演行なし）")
        w("")
    # CSV に無い公演の疑い
    orphan = []
    for p in official:
        if p['is_rt'] or not looks_like_setlist(p['text']):
            continue
        mentioned = sorted(d for d in dates_mentioned(p['text'], p['date'].year) if d <= p['date'])
        # 本文に過去の日付が1つだけ書かれていればそれが公演日（check_event_consistency.py と同じ規則）
        cands = {mentioned[0]} if len(mentioned) == 1 else {p['date'], p['date'] - timedelta(days=1)}
        if not any(c.isoformat() in event_dates for c in cands):
            orphan.append(p)
    if orphan:
        w("### CSV に無い公演の疑い（セトリらしき公式投稿に該当する行が無い）")
        for p in orphan:
            w(fmt_post(p, with_metrics=False))
        w("")

    # 新曲・初披露 / アナウンス / その他
    used = set()
    w("## 新曲・初披露（候補）")
    for p in official:
        if not p['is_rt'] and NEW_SONG.search(p['text']) and not looks_like_setlist(p['text']):
            w(fmt_post(p)); used.add(p['url'])
    w("")
    w("## アナウンス・告知（候補）")
    for p in official:
        if p['url'] in used or p['is_rt'] or looks_like_setlist(p['text']):
            continue
        if ANNOUNCE.search(p['text']):
            w(fmt_post(p)); used.add(p['url'])
    w("")
    w("## その他の公式投稿")
    for p in official:
        if p['url'] not in used and not looks_like_setlist(p['text']):
            w(fmt_post(p))
    w("")

    # メンバーの投稿
    w("## メンバーの投稿")
    w("（原文そのまま・全件。記事では1人あたり3〜8件に絞り、特徴的な一文を選ぶ）")
    w("")
    for handle, label in accounts:
        if handle == OFFICIAL:
            continue
        w(f"### {label}（@{handle}）")
        ps = posts_by.get(handle, [])
        if not ps:
            w("- （期間内の投稿なし、または未取得）")
        for p in ps:
            w(fmt_post(p))
        w("")

    # 外部の反応（プレースホルダ）
    w("## 外部の反応")
    w("- （エゴサーチ未実施。Grok の結果をここに貼る。無ければ記事の該当節は「未実施」と明記し、README の未解決に載せる）")
    w("")

    # 今後の予定
    label = '来週' if args.type == 'weekly' else '来月以降'
    w(f"## 今後の予定（期間内に告知された、{args.until} より後の日付を含む投稿）")
    future = []
    for handle, _ in accounts:
        for p in posts_by.get(handle, []):
            if p['is_rt']:
                continue
            for d in dates_mentioned(p['text'], p['date'].year):
                if d > until:
                    future.append((d, handle, p))
    future.sort(key=lambda x: (x[0], x[2]['dt']))
    seen = set()
    for d, handle, p in future:
        key = (d, p['url'])
        if key in seen:
            continue
        seen.add(key)
        w(f"- {d} ← @{handle} [{p['date']}] {one_line(p['text'], 120)}／出典: {p['url']}")
    if not future:
        w("- （該当なし）")
    w("")
    w("## 確認できなかった項目")
    w("- ")
    w("")
    w("## 判断に迷った点")
    w("- ")
    w("")

    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
    n_posts = sum(len(v) for v in posts_by.values())
    print(f"素材を書き出した: {out}")
    print(f"  公演 {len(events)} 件 / 投稿 {n_posts} 件（公式 {len(official)} 件）/ CSV に無い公演の疑い {len(orphan)} 件 / 予定候補 {len(seen)} 件")
    missing = [s for s in status if '未取得' in s]
    if missing:
        print(f"  未取得アカウント {len(missing)}: 先に x-account-fetch で取得するか、記事側で扱いを揃える")


if __name__ == '__main__':
    main()
