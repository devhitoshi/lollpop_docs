"""戦略の定点観測データを twitterapi.io で集め、strategy/metrics_YYYY-MM-DD.md の下書きを作る。

`prompts/collect/strategy_metrics.md`（Grok 用）の計測1〜5のうち、API で確定値が取れるものを自動化する。

- 計測1・2: フォロワー数（自グループ6アカウント＋競合5組）… /twitter/user/info
- 計測4: 公式の直近30日の投稿数・動画付き本数・反応上位3件 … advanced_search from:lollipop_1116
- 計測3・5: UGC 量と初見反応 … x-egosearch の候補/判定ファイルがあれば集計し、無ければ「未計測」と書く
  （ノイズ判定は Claude の仕事。このスクリプトは判定済みファイルを読むだけ）
- 前回の metrics ファイルを読み、フォロワー数の増減を付ける

使い方:
    python3 .claude/skills/strategy-metrics/scripts/collect_metrics.py            # 実行日を基準日にする
    python3 .claude/skills/strategy-metrics/scripts/collect_metrics.py --date 2026-09-02 --days 30
"""
import argparse
import glob
import json
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, os.path.join(project_root, '.claude/skills/x-account-fetch/scripts'))
from fetch_accounts import (  # noqa: E402
    DEFAULT_ACCOUNTS, SEARCH_PATH, QUERY_PARAM, SECONDS_PER_CALL, OutOfCredits, load_api_key, request_json, extract,
    tweet_id, tweet_text, tweet_url,
)

JST = timezone(timedelta(hours=9))
OFFICIAL = 'lollipop_1116'
USER_INFO_PATH = '/twitter/user/info'
# 計測2 の競合。ハンドルは metrics_2026-09-01.md で特定済みのもの
BENCHMARKS = [
    ('ストロボグリッター', 'stgli_info', '同期（2024年11月デビュー）'),
    ('踊れ！神風', 'odorekamikaze', 'ほぼ同期・お祭り系の直接競合'),
    ('メリーパレード', 'merryparade0513', '400人箱ワンマンのベンチマーク'),
    ('戦国アニマル極楽浄土', 'senkyoku_info', '半段上の目標像'),
    ('AZの理由', 'az_reason', '後発・フェス枠獲得の比較'),
]
FIRST_TIME = re.compile(r'初めて|初見|初現場|気になる')


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--date', help='基準日 YYYY-MM-DD（省略時は今日・JST）')
    p.add_argument('--days', type=int, default=30, help='直近何日を対象にするか（既定 30）')
    p.add_argument('--env', default='.env')
    p.add_argument('--out', help='出力先（既定: strategy/metrics_<基準日>.md）')
    p.add_argument('--skip-official', action='store_true', help='公式投稿の取得を省く（検索クレジットを使わない）')
    p.add_argument('--egosearch', help='UGC に使う x-egosearch の期間 "YYYY-MM-DD:YYYY-MM-DD"（省略時は基準日の直近 --days 日）')
    return p.parse_args()


def user_info(handle, api_key):
    payload = request_json(USER_INFO_PATH, {'userName': handle}, api_key)
    data = payload.get('data') or payload
    return {
        'followers': data.get('followers'),
        'following': data.get('following'),
        'statuses': data.get('statusesCount'),
        'name': data.get('name'),
        'userName': data.get('userName') or handle,
    }


def jst_dt(t):
    created = t.get('createdAt') or t.get('created_at') or ''
    for fmt in ('%a %b %d %H:%M:%S %z %Y', '%Y-%m-%dT%H:%M:%S%z'):
        try:
            return datetime.strptime(created, fmt).astimezone(JST)
        except ValueError:
            continue
    return None


def has_video(t):
    ee = t.get('extendedEntities') or {}
    return any((m.get('type') in ('video', 'animated_gif')) for m in (ee.get('media') or []))


def fetch_official(since, until_excl, api_key, cap=400):
    """公式の期間内の投稿を全件（リポストは除く）。"""
    query = f"from:{OFFICIAL} since:{since} until:{until_excl}"
    tweets, seen, cursor = [], set(), None
    while len(tweets) < cap:
        params = {QUERY_PARAM: query, 'queryType': 'Latest'}
        if cursor:
            params['cursor'] = cursor
        page, cursor = extract(request_json(SEARCH_PATH, params, api_key))
        for t in page:
            tid = tweet_id(t)
            if tid and tid not in seen:
                seen.add(tid)
                tweets.append(t)
        if not cursor or not page:
            break
        time.sleep(SECONDS_PER_CALL)
    since_d = datetime.strptime(since, '%Y-%m-%d').date()
    until_d = datetime.strptime(until_excl, '%Y-%m-%d').date()
    out = []
    for t in tweets:
        d = jst_dt(t)
        if d and since_d <= d.date() < until_d and not t.get('retweeted_tweet') and not tweet_text(t).startswith('RT @'):
            out.append(t)
    return out


def previous_metrics():
    files = sorted(glob.glob('strategy/metrics_*.md'))
    if not files:
        return None, {}
    path = files[-1]
    followers = {}
    with open(path, encoding='utf-8') as f:
        for line in f:
            m = re.match(r'\|\s*@?(\w+)[^|]*\|\s*([\d,]+)\s*\|', line)
            if m:
                followers[m.group(1)] = int(m.group(2).replace(',', ''))
            m2 = re.match(r'\|\s*[^|]+\|\s*@(\w+)\s*\|\s*([\d,]+)\s*\|', line)
            if m2:
                followers[m2.group(1)] = int(m2.group(2).replace(',', ''))
    return path, followers


def egosearch_summary(since, until_incl):
    """x-egosearch の出力（判定済み reactions があればそれ、無ければ候補）を読んで UGC の集計に使う。"""
    base = f"work/x_fetch/egosearch_{since}_{until_incl}"
    judged = f"data/x/egosearch_{since}_{until_incl}_reactions.md"   # 判定済みの要約は追跡ディレクトリにある
    cands = base + '_candidates.md'
    raw = base + '.jsonl'
    result = {'source': None}
    if os.path.exists(judged):
        result['source'] = judged
        text = open(judged, encoding='utf-8').read()
        m = re.search(r'採用\s*(\d+)', text)
        result['adopted'] = int(m.group(1)) if m else None
        m = re.search(r'除外\s*(\d+)', text)
        result['rejected'] = int(m.group(1)) if m else None
        entries = [l.strip() for l in text.splitlines() if l.startswith('- ') and '出典:' in l]

        def likes(line):
            m = re.search(r'いいね\s*([\d,]+)', line)
            return int(m.group(1).replace(',', '')) if m else 0
        # 同じ投稿が複数の節に出ることがあるので URL で重複を除く
        seen, uniq = set(), []
        for l in entries:
            url = l.rsplit('出典:', 1)[-1].strip()
            if url not in seen:
                seen.add(url)
                uniq.append(l)
        result['top'] = sorted(uniq, key=likes, reverse=True)[:3]
        result['first_time'] = [l for l in uniq if FIRST_TIME.search(l)][:5]
    elif os.path.exists(raw):
        result['source'] = cands if os.path.exists(cands) else raw
        n = media = 0
        for line in open(raw, encoding='utf-8'):
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            n += 1
            if (t.get('extendedEntities') or {}).get('media'):
                media += 1
        result['raw_total'] = n
        result['raw_media'] = media
    return result


def fmt(n):
    return f"{n:,}" if isinstance(n, int) else '—'


def delta(cur, prev):
    if not isinstance(cur, int) or not isinstance(prev, int):
        return '—'
    d = cur - prev
    return f"{d:+,}"


def main():
    args = parse_args()
    api_key = load_api_key(args.env)
    today = datetime.strptime(args.date, '%Y-%m-%d').date() if args.date else datetime.now(JST).date()
    since = (today - timedelta(days=args.days)).isoformat()
    until_incl = today.isoformat()
    until_excl = (today + timedelta(days=1)).isoformat()
    now = datetime.now(JST).strftime('%Y-%m-%d %H:%M JST')
    out = args.out or f"strategy/metrics_{until_incl}.md"

    prev_path, prev = previous_metrics()

    print("フォロワー数を取得中…")
    own, bench = [], []
    for handle, label in DEFAULT_ACCOUNTS:
        own.append((label, handle, user_info(handle, api_key)))
        time.sleep(1)
    for label, handle, note in BENCHMARKS:
        try:
            bench.append((label, handle, note, user_info(handle, api_key)))
        except SystemExit as e:
            bench.append((label, handle, note + f"（取得失敗: {e}）", {}))
        time.sleep(1)

    official = []
    if not args.skip_official:
        print("公式の投稿を取得中…")
        try:
            official = fetch_official(since, until_excl, api_key)
        except OutOfCredits as e:
            print(f"クレジット切れ: {e}")
    top = sorted(official, key=lambda t: t.get('likeCount', 0), reverse=True)[:3]
    videos = [t for t in official if has_video(t)]

    ego_since, ego_until = (args.egosearch.split(':') if args.egosearch else (since, until_incl))
    ego = egosearch_summary(ego_since, ego_until)

    L = []
    w = L.append
    w(f"# 戦略定点観測データ ろりぽっぷ!!!!!!! {until_incl}")
    w("")
    w(f"`.claude/skills/strategy-metrics/scripts/collect_metrics.py` による API 取得。計測時刻: **{now}**。")
    w(f"期間: 直近{args.days}日 = {since} 〜 {until_incl}。前回: {prev_path or 'なし'}。")
    w("")
    w("## フォロワー数（自グループ）")
    w("| アカウント | フォロワー数 | 前回比 | 確認日時 |")
    w("| --- | --- | --- | --- |")
    for label, handle, info in own:
        w(f"| @{handle}（{label}） | {fmt(info.get('followers'))} | {delta(info.get('followers'), prev.get(handle))} | {now} |")
    members_total = sum(i.get('followers') or 0 for _, h, i in own if h != OFFICIAL)
    w("")
    w(f"メンバー個人合計: {members_total:,}（参考値・重複フォロワーを含む）")
    w("")
    w("## フォロワー数（競合・ベンチマーク）")
    w("| グループ | アカウント | フォロワー数 | 前回比 | 確認日時 | メモ |")
    w("| --- | --- | --- | --- | --- | --- |")
    for label, handle, note, info in bench:
        w(f"| {label} | @{handle} | {fmt(info.get('followers'))} | {delta(info.get('followers'), prev.get(handle))} | {now} | {note} |")
    w("")
    w(f"## UGC量（{ego_since} 〜 {ego_until}）")
    if ego.get('source') and 'adopted' in ego:
        w(f"| 計測 | 件数 | 数え方のメモ |")
        w(f"| --- | --- | --- |")
        w(f"| グループ名・メンバー名でのファン投稿（判定済み） | {fmt(ego.get('adopted'))} | x-egosearch 全件取得 → Claude がノイズ判定（除外 {fmt(ego.get('rejected'))}）。出典: `{ego['source']}` |")
        w("")
        w("### 伸びたファン投稿 上位3件")
        for l in ego.get('top') or ['- （判定済みファイルに「出典」付きの行が無い）']:
            w(l)
    elif ego.get('source'):
        w(f"| 計測 | 件数 | 数え方のメモ |")
        w(f"| --- | --- | --- |")
        w(f"| 検索に当たった投稿（未判定・本人投稿除外前） | {fmt(ego.get('raw_total'))} | x-egosearch の生データ。ノイズ判定前なので上限値。出典: `{ego['source']}` |")
        w(f"| うちメディア付き | {fmt(ego.get('raw_media'))} | 同上 |")
        w("")
        w("### 伸びたファン投稿 上位3件")
        w("- （x-egosearch の判定を行ってから `_reactions.md` を作ると自動で埋まる）")
    else:
        w(f"- 未計測。`.claude/skills/x-egosearch` を `--since {since} --until {until_incl}` で実行し、判定してから再実行する")
    w("")
    w(f"## 公式の発信（直近{args.days}日）")
    if args.skip_official:
        w("- （--skip-official のため未取得）")
    else:
        w(f"- 投稿数: **{len(official)}件**（{since}〜{until_incl}・リポスト除く・API全件取得）")
        w(f"- 動画付き投稿数: {len(videos)}件" + (f"（{', '.join(sorted({jst_dt(t).strftime('%m/%d') for t in videos}))}）" if videos else ''))
        w("- 反応上位3件:")
        for t in top:
            d = jst_dt(t)
            w(f"  - {d.strftime('%Y-%m-%d') if d else '----'}／{' '.join(tweet_text(t).split())[:50]}／いいね{t.get('likeCount', 0)}・RT{t.get('retweetCount', 0)}・表示{t.get('viewCount', '—')}／{tweet_url(t, OFFICIAL)}")
    w("")
    w(f"## 初見・新規らしき反応（直近{args.days}日）")
    if ego.get('first_time'):
        w(f"- 件数: {len(ego['first_time'])} 件（判定済みファイル内で「初めて」「初見」「初現場」「気になる」を含む行）")
        w("- 代表例:")
        for l in ego['first_time']:
            w("  " + l)
    else:
        w("- 判定済みの反応ファイルが無い、または該当なし。x-egosearch の判定時に「初見」の投稿へ印を付けると拾える")
    w("")
    w("## 確認できなかった項目")
    w("- （ここに書く）")
    w("")
    w("## 判断に迷った点（収集時メモ）")
    w("- （ここに書く）")
    w("")
    w("---")
    w("※次回実行時は同形式で `strategy/metrics_YYYY-MM-DD.md` に保存し、`strategy/growth_strategy.md` のKPI表を更新する。")

    with open(out, 'w', encoding='utf-8') as f:
        f.write('\n'.join(L) + '\n')
    print(f"書き出した: {out}")


if __name__ == '__main__':
    main()
