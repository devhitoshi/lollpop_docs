"""週刊の「現場の反応」の候補を、3 種類だけから集める（2026-10-13 オーナー決定「エゴサは A」）。

1. #ろりぽっぷ
2. メンバー固有のタグ（各メンバーの X プロフィールに書かれたタグ。daily_fetch.member_tags() と同じ）
3. メンバーが返信した相手の投稿（返信先）

1・2 は毎日取得（x-account-fetch/scripts/daily_fetch.py）が work/x_fetch/hashtags_YYYY-MM.jsonl に溜めている分を使う。
毎日取得がまだ取っていない日（今日・PC が止まっていた日）だけ、同じ検索で取り足す。
3 は公式・メンバーの取得データ（work/x_fetch/<handle>.jsonl）の返信から相手の投稿 ID を拾い、手元に無い分だけ ID 指定で取る。

広い検索（fetch_egosearch.py の 3 クエリ）より件数は少ないが、別人の「くるみん」や同名の店・お菓子がほぼ混ざらない。
広い検索は月刊と定点観測（反応の件数を数えるとき）に残す。

出力:
- work/x_fetch/reply_targets_<since>_<until>.jsonl … 返信先の投稿（`_replied_by` に返信したメンバー）。他人の原文なのでコミットしない
- work/x_fetch/reactions3_<since>_<until>.md … 記事用の候補一覧（日時順・本文つき）。コミットしない
- data/x/reactions3_<since>_<until>_summary.txt … 件数だけ（追跡する）

使い方:
    python .claude/skills/x-egosearch/scripts/weekly_reactions.py --since 2026-10-06 --until 2026-10-12 --dry-run
    python .claude/skills/x-egosearch/scripts/weekly_reactions.py --since 2026-10-06 --until 2026-10-12 --yes
"""
import argparse
import glob
import json
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
sys.path.insert(0, os.path.join(project_root, '.claude/skills/x-account-fetch/scripts'))
from fetch_accounts import (  # noqa: E402  import 時にリポジトリルートへ chdir する
    CREDITS_PER_TWEET, DEFAULT_ACCOUNTS, MIN_CREDITS_PER_CALL, OutOfCredits,
    extract, load_api_key, request_json, tweet_id, usd,
)
from daily_fetch import fetch_hashtags, member_tags, MAX_TAG_TWEETS_PER_DAY  # noqa: E402

JST = timezone(timedelta(hours=9))
OUT_DIR = os.path.join('work', 'x_fetch')
DATA_DIR = os.path.join('data', 'x')
DAILY_STATE_PATH = os.path.join(OUT_DIR, '.daily_state.json')
TWEETS_PATH = '/twitter/tweets'
IDS_PER_CALL = 20

# 関係者の投稿は「反応」ではないので外す（fetch_egosearch.OWN_HANDLES と同じ顔ぶれ）
OWN_HANDLES = {h for h, _ in DEFAULT_ACCOUNTS} | {'asaka_lpop', 'natsumi_lpop', 'nanotabiyori'}
# 一覧には残すが、記事では引用しないアカウント（オーナー本人と見られる。週刊 README の運用）
NO_QUOTE_HANDLES = {'mo_8_c'}


def jst(t):
    return datetime.strptime(t['createdAt'], '%a %b %d %H:%M:%S %z %Y').astimezone(JST)


def in_period(t, since, until):
    return since <= jst(t).strftime('%Y-%m-%d') <= until


def handle_of(t):
    return ((t.get('author') or {}).get('userName') or '').lower()


def plus_days(d, n):
    return (datetime.strptime(d, '%Y-%m-%d') + timedelta(days=n)).strftime('%Y-%m-%d')


def read_jsonl(path):
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    rows.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return rows


def months_between(since, until):
    months, d = [], since[:7] + '-01'
    while d[:7] <= until[:7]:
        months.append(d[:7])
        d = plus_days(d, 32)[:7] + '-01'
    return months


def tag_gap(since, until):
    """毎日取得が取っていない日の範囲（since〜until の中）。無ければ None。"""
    if not os.path.exists(DAILY_STATE_PATH):
        return since, until
    with open(DAILY_STATE_PATH, encoding='utf-8') as f:
        st = json.load(f)
    cf, lu = st.get('covered_from'), st.get('last_until')
    if not cf or not lu or cf > since:
        return since, until
    if lu >= until:
        return None
    return max(since, plus_days(lu, 1)), until


def member_replies(since, until):
    """期間内に公式・メンバーが関係者以外へ送った返信。{返信先ID: [返信したアカウント, ...]} と、アカウント別の件数。"""
    targets, per_member = {}, Counter()
    for handle, _ in DEFAULT_ACCOUNTS:
        for t in read_jsonl(os.path.join(OUT_DIR, f'{handle}.jsonl')):
            if not in_period(t, since, until) or not t.get('inReplyToId'):
                continue
            if (t.get('inReplyToUsername') or '').lower() in OWN_HANDLES:
                continue
            targets.setdefault(t['inReplyToId'], []).append(handle)
            per_member[handle] += 1
    return targets, per_member


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--since', required=True, help='開始日 YYYY-MM-DD（含む）')
    p.add_argument('--until', required=True, help='終了日 YYYY-MM-DD（含む）')
    p.add_argument('--dry-run', action='store_true', help='取る件数と費用の見積もりだけ表示して API を叩かない')
    p.add_argument('--yes', action='store_true', help='費用の確認を省略する')
    p.add_argument('--env', default='.env')
    args = p.parse_args()
    since, until = args.since, args.until

    # --- 返信先: 手元に無い ID を数える ---
    targets, per_member = member_replies(since, until)
    reply_path = os.path.join(OUT_DIR, f'reply_targets_{since}_{until}.jsonl')
    have = {}
    for path in [os.path.join(OUT_DIR, f'egosearch_{since}_{until}.jsonl'), reply_path] + \
            [os.path.join(OUT_DIR, f'hashtags_{m}.jsonl') for m in months_between(plus_days(since, -31), until)]:
        for t in read_jsonl(path):
            tid = tweet_id(t)
            if tid:
                have[tid] = t
    missing = [i for i in targets if i not in have]

    gap = tag_gap(since, until)
    print(f"期間 {since}〜{until}")
    print(f"返信先: {len(targets)} 件（メンバーの返信 {sum(per_member.values())} 件）／手元にある {len(targets) - len(missing)} 件／取得 {len(missing)} 件")
    if gap:
        print(f"タグ: 毎日取得の範囲外 {gap[0]}〜{gap[1]} を取り足す")
    else:
        print("タグ: 期間全体を毎日取得で取得済み（取り足し無し）")

    if missing or gap:
        days = (datetime.strptime(gap[1], '%Y-%m-%d') - datetime.strptime(gap[0], '%Y-%m-%d')).days + 1 if gap else 0
        est = len(missing) * CREDITS_PER_TWEET + max(MIN_CREDITS_PER_CALL, days * 10 * CREDITS_PER_TWEET if days else 0)
        print(f"費用の見積もり: 約 {est:,} クレジット（約 ${usd(est):.3f}）。タグは 1 日 10 件前後の想定")
        if args.dry_run:
            print("（--dry-run のため取得しない）")
            return
        if not args.yes and input("取得しますか？ [y/N] ").strip().lower() not in ('y', 'yes'):
            sys.exit("中止しました。")
        api_key = load_api_key(args.env)
        try:
            if gap:
                fetch_hashtags(member_tags(), gap[0], plus_days(gap[1], 1), MAX_TAG_TWEETS_PER_DAY * days, api_key)
            for i in range(0, len(missing), IDS_PER_CALL):
                payload = request_json(TWEETS_PATH, {'tweet_ids': ','.join(missing[i:i + IDS_PER_CALL])}, api_key)
                for t in extract(payload)[0]:
                    tid = tweet_id(t)
                    if tid:
                        have[tid] = t
        except OutOfCredits as e:
            sys.exit(f"クレジット不足で停止（チャージは承認なしに行わない）: {e}")
    elif args.dry_run:
        print("（--dry-run。取得するものは無い）")
        return

    with open(reply_path, 'w', encoding='utf-8') as f:
        for tid, members in targets.items():
            if tid in have:
                t = dict(have[tid])
                t['_replied_by'] = members
                f.write(json.dumps(t, ensure_ascii=False) + '\n')
    not_found = [i for i in targets if i not in have]

    # --- 3 種類を合わせる ---
    rows = {}
    for m in months_between(since, until):
        for t in read_jsonl(os.path.join(OUT_DIR, f'hashtags_{m}.jsonl')):
            if in_period(t, since, until) and handle_of(t) not in OWN_HANDLES:
                rows[tweet_id(t)] = (t, ['tag:' + '/'.join(t.get('_tags') or [])])
    out_of_period = 0
    for t in read_jsonl(reply_path):
        if handle_of(t) in OWN_HANDLES:
            continue
        if not in_period(t, since, until):
            out_of_period += 1
            continue
        label = 'rep:' + '/'.join(sorted(set(t['_replied_by'])))
        tid = tweet_id(t)
        rows[tid] = (t, (rows[tid][1] if tid in rows else []) + [label])

    tag_n = sum(1 for _, labels in rows.values() if any(l.startswith('tag:') for l in labels))
    rep_n = sum(1 for _, labels in rows.values() if any(l.startswith('rep:') for l in labels))
    authors = {handle_of(t) for t, _ in rows.values()}

    md_path = os.path.join(OUT_DIR, f'reactions3_{since}_{until}.md')
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(f"# 現場の反応の候補（3 種類） {since}〜{until}\n\n")
        f.write("> #ろりぽっぷ・メンバー固有のタグ・メンバーの返信先。他人の投稿原文なのでコミットしない。\n")
        f.write("> 書式: id|日時|投稿者|♥いいね|どこから（tag:タグ名 / rep:返信したアカウント）|本文。〔引用しない〕はオーナー本人と見られるアカウント\n\n")
        for tid, (t, labels) in sorted(rows.items(), key=lambda x: jst(x[1][0])):
            mark = '〔引用しない〕' if handle_of(t) in NO_QUOTE_HANDLES else ''
            text = (t.get('text') or '').replace('\n', ' ')
            f.write(f"- {tid}|{jst(t):%m/%d %H:%M}|@{(t.get('author') or {}).get('userName')}{mark}|"
                    f"♥{t.get('likeCount', 0)}|{' '.join(labels)}|{text}\n")

    summary_path = os.path.join(DATA_DIR, f'reactions3_{since}_{until}_summary.txt')
    lines = [
        f"現場の反応の候補（3 種類） {since}〜{until}",
        f"合計 {len(rows)} 件・{len(authors)} 人（タグ {tag_n} 件・返信先 {rep_n} 件。両方に当たったものは 1 件に数える）",
        f"メンバーの返信（関係者以外あて）: {sum(per_member.values())} 件（"
        + '・'.join(f"{h} {n}" for h, n in per_member.most_common()) + "）",
        f"返信先のうち期間外（{since} より前）の投稿: {out_of_period} 件（一覧から外した）",
        f"返信先を取得できなかった: {len(not_found)} 件（削除・非公開など）",
    ]
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(summary_path, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines) + '\n')
    print('\n'.join(lines))
    print(f"一覧: {md_path}")
    print(f"件数: {summary_path}")


if __name__ == '__main__':
    main()
