"""メンバーの投稿統計を出し、members/*.md（パーソナリティデータ）を更新する根拠にする。

x-account-fetch で取得した work/x_fetch/<handle>.jsonl を読み、判断を挟まずに数える:
- 投稿数（うち返信・リポスト）、投稿時間帯、曜日
- ハッシュタグ、絵文字、メンション先の頻度
- 冒頭の定型句（あいさつ）と末尾の定型句
- 伸びた投稿 上位5件（いいね）
- よく出る語（2〜4文字の連続。形態素解析なしの簡易版なので目安）

出力は work/x_fetch/profile_stats_<handle>_<since>_<until>.md（他人の投稿原文を含むのでコミットしない）。
members/*.md へは、Claude がこの統計と原文を読んで「根拠がある範囲」だけを書く。

使い方:
    python3 .claude/skills/member-profile-refresh/scripts/profile_stats.py --since 2026-08-01 --until 2026-08-31
    python3 ... --accounts kurumi_lpop,mau_lpop
"""
import argparse
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
X_DIR = 'work/x_fetch'
EMOJI = re.compile(r'[\U0001F300-\U0001FAFF☀-➿⭐❤]️?')
WORD = re.compile(r'[ぁ-んァ-ン一-龥ー]{2,4}')
STOP = {'ありがとう', 'ござい', 'ました', 'します', 'ください', 'よろしく', 'お願い', 'こと', 'これ', 'それ', 'ので', 'から', 'まで', 'です', 'ます', 'たい', 'てる', 'った', 'って', 'ない', 'いる', 'ある', 'する', 'した', 'ろりぽっぷ', 'ろりぽ', 'ライブ', 'みんな', 'きょう', '今日', '明日'}


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--since', required=True)
    p.add_argument('--until', required=True, help='この日を含む')
    p.add_argument('--accounts', help='ハンドルのカンマ区切り（省略時は現メンバー5人）')
    p.add_argument('--x-dir', default=X_DIR)
    return p.parse_args()


def jst(t):
    created = t.get('createdAt') or t.get('created_at') or ''
    for fmt in ('%a %b %d %H:%M:%S %z %Y', '%Y-%m-%dT%H:%M:%S%z'):
        try:
            return datetime.strptime(created, fmt).astimezone(JST)
        except ValueError:
            continue
    return None


def load(path, since, until):
    posts = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            d = jst(t)
            if d and since <= d.date().isoformat() <= until:
                t['_dt'] = d
                posts.append(t)
    posts.sort(key=lambda t: t['_dt'])
    return posts


def head(text, n=8):
    line = next((l.strip() for l in text.splitlines() if l.strip()), '')
    return re.sub(r'https?://\S+', '', line)[:n]


def tail(text, n=8):
    line = next((l.strip() for l in reversed(text.splitlines()) if l.strip() and not l.strip().startswith('#') and not l.strip().startswith('http')), '')
    return line[-n:]


def stats(label, handle, posts):
    L = []
    w = L.append
    w(f"## {label}（@{handle}）")
    if not posts:
        w("- 期間内の投稿なし")
        w("")
        return L
    texts = [t.get('text') or t.get('full_text') or '' for t in posts]
    replies = sum(1 for t in posts if t.get('isReply') or t.get('inReplyToId'))
    rts = sum(1 for t in posts if t.get('retweeted_tweet') or (t.get('text') or '').startswith('RT @'))
    own = [t for t in posts if not (t.get('retweeted_tweet') or (t.get('text') or '').startswith('RT @'))]
    likes = [t.get('likeCount', 0) or 0 for t in own]
    w(f"- 投稿数: {len(posts)}（返信 {replies}、リポスト {rts}）。1日平均 {len(posts) / max(1, (posts[-1]['_dt'].date() - posts[0]['_dt'].date()).days + 1):.1f} 件")
    if likes:
        w(f"- いいね: 平均 {sum(likes) / len(likes):.1f}、中央値 {sorted(likes)[len(likes) // 2]}、最大 {max(likes)}")
    hours = Counter(t['_dt'].hour for t in posts)
    band = Counter()
    for h, n in hours.items():
        band['朝(5-10)' if 5 <= h < 11 else '昼(11-16)' if 11 <= h < 17 else '夜(17-23)' if 17 <= h < 24 else '深夜(0-4)'] += n
    w("- 投稿時間帯: " + '、'.join(f"{k} {v}" for k, v in band.most_common()))
    w("- 曜日: " + '、'.join(f"{d} {n}" for d, n in sorted(Counter('月火水木金土日'[t['_dt'].weekday()] for t in posts).items(), key=lambda x: -x[1])))
    tags = Counter(h for tx in texts for h in re.findall(r'#\S+', tx))
    w("- ハッシュタグ上位: " + ('、'.join(f"{h} ×{n}" for h, n in tags.most_common(8)) or 'なし'))
    emo = Counter(e for tx in texts for e in EMOJI.findall(tx))
    w("- 絵文字上位: " + ('、'.join(f"{e} ×{n}" for e, n in emo.most_common(10)) or 'なし'))
    mentions = Counter(m for tx in texts for m in re.findall(r'@\w+', tx))
    w("- メンション先上位: " + ('、'.join(f"{m} ×{n}" for m, n in mentions.most_common(6)) or 'なし'))
    heads = Counter(head(tx) for tx in texts if head(tx))
    w("- 冒頭の定型句（先頭8文字）: " + '、'.join(f"「{h}」×{n}" for h, n in heads.most_common(6) if n >= 2))
    tails = Counter(tail(tx) for tx in texts if tail(tx))
    w("- 末尾の定型句（末尾8文字）: " + '、'.join(f"「{h}」×{n}" for h, n in tails.most_common(6) if n >= 2))
    words = Counter(wd for tx in texts for wd in WORD.findall(tx) if wd not in STOP)
    w("- よく出る語（簡易）: " + '、'.join(f"{wd} ×{n}" for wd, n in words.most_common(15) if n >= 3))
    w("- 伸びた投稿 上位5件（いいね順・原文の先頭60字）:")
    for t in sorted(own, key=lambda t: t.get('likeCount', 0) or 0, reverse=True)[:5]:
        tx = ' '.join((t.get('text') or '').split())
        url = t.get('url') or f"https://x.com/{handle}/status/{t.get('id')}"
        w(f"  - [{t['_dt'].strftime('%Y-%m-%d')}] いいね{t.get('likeCount', 0)}／{tx[:60]}／{url}")
    w("")
    return L


def main():
    args = parse_args()
    handles = [h.strip() for h in args.accounts.split(',')] if args.accounts else [h for h, _ in DEFAULT_ACCOUNTS if h != 'lollipop_1116']
    labels = dict(DEFAULT_ACCOUNTS)
    out_lines = [f"# メンバー投稿統計 {args.since} 〜 {args.until}", "",
                 "> profile_stats.py の機械集計。判断は入っていない。members/*.md に書くときは原文（<handle>.jsonl）で裏を取る。",
                 "> 他人の投稿原文を含むのでコミットしない。", ""]
    missing = []
    for h in handles:
        path = os.path.join(args.x_dir, f"{h}.jsonl")
        if not os.path.exists(path):
            missing.append(h)
            out_lines += [f"## {labels.get(h, h)}（@{h}）", f"- **未取得**（{path} が無い）", ""]
            continue
        out_lines += stats(labels.get(h, h), h, load(path, args.since, args.until))
    out = os.path.join(args.x_dir, f"profile_stats_{args.since}_{args.until}.md")
    os.makedirs(args.x_dir, exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out_lines) + '\n')
    print(f"書き出した: {out}")
    if missing:
        print(f"未取得: {', '.join(missing)}（x-account-fetch で取得する）")


if __name__ == '__main__':
    main()
