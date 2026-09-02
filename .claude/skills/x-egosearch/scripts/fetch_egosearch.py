"""エゴサーチ（周囲の反応）の候補を twitterapi.io で集める。

`prompts/collect/x_collect.md` の「2. 周囲の反応を取得」を、Grok の1クエリ10件の壁を越えて全件取る版。
判断はしない。候補を漏れなく集めて、ノイズ判定（レンタルサーバー「ロリポップ!」等）は Claude が読んで行う。

- 検索クエリは x_collect.md の 2-1〜2-4 をそのまま使う（2-5 の filter:media は 2-1/2-4 に含まれるので省く）
- `-from:` 除外は twitterapi.io で信用できない（x-account-fetch の知見）ので、公式・メンバーの投稿は
  取得後に投稿者ハンドルで除外する
- 出力は work/x_fetch/（.gitignore 済み）。他人の投稿原文なのでコミットしない
- 期間は --since/--until とも「その日を含む」（build_material.py と同じ。x-account-fetch だけが翌日指定）

使い方:
    python3 .claude/skills/x-egosearch/scripts/fetch_egosearch.py --since 2026-08-01 --until 2026-08-31 --max-tweets-per-query 600
    python3 ... --terms "夏色ラムネ,POP CRUSH" （2-4 の固有名詞を足す。省略時は data_event.csv の期間内イベント名を使う）
"""
import argparse
import csv
import json
import os
import re
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, os.path.join(project_root, '.claude/skills/x-account-fetch/scripts'))
from fetch_accounts import (  # noqa: E402
    DEFAULT_ACCOUNTS, SEARCH_PATH, QUERY_PARAM, SECONDS_PER_CALL, CREDITS_PER_TWEET, MIN_CREDITS_PER_CALL,
    OutOfCredits, load_api_key, request_json, extract, tweet_id, tweet_text, usd,
)

JST = timezone(timedelta(hours=9))
OWN_HANDLES = {h for h, _ in DEFAULT_ACCOUNTS} | {'asaka_lpop', 'natsumi_lpop'}
OUT_DIR = 'work/x_fetch'

# x_collect.md の 2-1〜2-3 をそのまま
BASE_QUERIES = {
    '2-1 基本形': '("ろりぽっぷ" OR "#ろりぽっぷ" OR "ろりぽ" OR @lollipop_1116)',
    '2-2 カタカナ・英字': '("ロリポップ" OR "ロリポ" OR "lollipop") (アイドル OR ライブ OR 対バン OR セトリ OR 特典会 OR チェキ OR 現場)',
    '2-3 メンバー名': '("愛月まな" OR "まなてぃー" OR "やぎくるみ" OR "くるみん" OR "夏川茉夢" OR "おまゆ" OR "松川愛美" OR "あみてん" '
                  'OR @mana_lpop OR @kurumi_lpop OR @mayu_lpop OR @ami_lpop OR @mau_lpop)',
}
NOISE_WORDS = re.compile(r'サーバー|サーバ|ドメイン|WordPress|ムームー|障害|契約|レンタル|ホスティング|チェーンソー|キャンディ|飴|ペロペロ|lollipop chainsaw', re.I)
SIGNAL_WORDS = re.compile(r'ろりぽっぷ!|#ろりぽっぷ|アイドル|ライブ|対バン|セトリ|特典会|チェキ|現場|生誕|ワンマン|lollipop_1116|_lpop')


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--since', required=True, help='開始日 YYYY-MM-DD（含む）')
    p.add_argument('--until', required=True, help='終了日 YYYY-MM-DD（含む）')
    p.add_argument('--max-tweets-per-query', type=int, required=True, help='クエリごとの取得上限（必須。暴走防止）')
    p.add_argument('--terms', default='', help='2-4 用の固有名詞（カンマ区切り）。省略時は期間内のイベント名')
    p.add_argument('--no-auto-terms', action='store_true', help='data_event.csv からの固有名詞の自動追加をしない')
    p.add_argument('--all-event-terms', action='store_true', help='対バン・フェスの名前も 2-4 に含める（件数と費用が跳ねる）')
    p.add_argument('--env', default='.env')
    p.add_argument('--yes', action='store_true', help='コスト確認を省略')
    p.add_argument('--sleep', type=float, default=SECONDS_PER_CALL, help='呼び出し間隔（秒）。既定は x-account-fetch と同じ')
    p.add_argument('--dry-run', action='store_true', help='クエリを表示するだけで取得しない')
    return p.parse_args()


def clean_event_name(name):
    name = re.sub(r'[『』「」【】]', '', name)
    name = re.sub(r'（.*?）|\(.*?\)', '', name)
    name = re.sub(r'\s*(1部|2部|昼|夜|DAY\d).*$', '', name)
    return name.strip()


OWN_EVENT_WORDS = re.compile(r'ろりぽ|愛月|まな|やぎ|くるみ|夏川|茉夢|おまゆ|松川|愛美|あみ|まう|苺花|なつみ|姫杏|朝香|生誕|単独|ワンマン|主催')


def auto_terms(since, until, all_events=False):
    """2-4 用の固有名詞を data_event.csv から拾う。

    既定では「ろりぽっぷ自身の固有名詞」だけにする: 期間内に 🆕 が付いた新曲、メンバー名・生誕・単独・主催を含むイベント名。
    対バンやフェスの名前（TOKYO GIRLS GIRLS 等）は出演者全員のファンの投稿が数百件単位で当たり、
    ろりぽっぷへの反応は 2-1/2-3 で既に拾えているので、--all-event-terms を付けたときだけ含める。
    """
    terms, songs = [], []
    with open('events/data_event.csv', 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if not (since <= row['date'] <= until):
                continue
            for m in re.finditer(r'\d+\s*([^;|]+?)🆕', row['setlist'] or ''):
                song = m.group(1).strip()
                if song not in songs:
                    songs.append(song)
            n = clean_event_name(row['event'])
            if len(n) < 4 or n in terms or re.match(r'^(単独ライブ|ワンコイン)', n):
                continue
            if all_events or OWN_EVENT_WORDS.search(n):
                terms.append(n)
    return songs + terms


def term_queries(terms, chunk=4):
    qs = {}
    for i in range(0, len(terms), chunk):
        part = terms[i:i + chunk]
        qs[f'2-4 固有名詞 #{i // chunk + 1}'] = '(' + ' OR '.join(f'"{t}"' for t in part) + ')'
    return qs


def author_handle(t):
    a = t.get('author') or t.get('user') or {}
    return (a.get('userName') or a.get('screen_name') or a.get('username') or '').lstrip('@')


def author_name(t):
    a = t.get('author') or t.get('user') or {}
    return a.get('name') or ''


def jst_dt(t):
    created = t.get('createdAt') or t.get('created_at') or ''
    for fmt in ('%a %b %d %H:%M:%S %z %Y', '%Y-%m-%dT%H:%M:%S%z'):
        try:
            return datetime.strptime(created, fmt).astimezone(JST)
        except ValueError:
            continue
    return None


def has_media(t):
    ee = t.get('extendedEntities') or t.get('extended_entities') or {}
    media = ee.get('media') or t.get('media') or []
    return bool(media)


def save_progress(path, progress):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(progress, f, ensure_ascii=False, indent=1)


def run_query(label, query, api_key, max_tweets, seen, out, since_api, until_api, sleep, progress, progress_path):
    full = f"{query} since:{since_api} until:{until_api}"
    print(f"\n[{label}] {full}")
    state = progress.get(label) or {}
    cursor, page, new, calls, total = state.get('cursor'), 0, 0, state.get('calls', 0), state.get('total', 0)
    if cursor:
        print(f"  前回の続きから再開（累計 {total} 件）")
    while total < max_tweets:
        params = {QUERY_PARAM: full, 'queryType': 'Latest'}
        if cursor:
            params['cursor'] = cursor
        payload = request_json(SEARCH_PATH, params, api_key)
        calls += 1
        page += 1
        tweets, cursor = extract(payload)
        if page == 1 and not tweets:
            print("  0件")
            break
        for t in tweets:
            total += 1
            tid = tweet_id(t)
            if not tid:
                continue
            if tid in seen:
                seen[tid]['_queries'].append(label)
                continue
            t['_queries'] = [label]
            seen[tid] = t
            out.write(json.dumps(t, ensure_ascii=False) + '\n')
            new += 1
            if total >= max_tweets:
                break
        out.flush()
        print(f"  {page:>3}ページ目: 応答{len(tweets):>3}件 / 新規{new:>3}件 / このクエリ累計{total:>4}件", flush=True)
        progress[label] = {'total': total, 'new': new, 'calls': calls, 'cursor': cursor, 'done': not cursor}
        save_progress(progress_path, progress)
        if not cursor:
            break
        time.sleep(sleep)
    capped = bool(total >= max_tweets and cursor)
    if capped:
        print(f"  --max-tweets-per-query に達して打ち切り。実数はこれより多い")
    progress[label] = {'total': total, 'new': new, 'calls': calls, 'cursor': cursor if capped else None, 'done': True, 'capped': capped}
    save_progress(progress_path, progress)
    return total, new, calls


def main():
    args = parse_args()
    api_key = load_api_key(args.env)
    since_api = args.since
    until_api = (datetime.strptime(args.until, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')

    queries = dict(BASE_QUERIES)
    terms = [t.strip() for t in args.terms.split(',') if t.strip()]
    if not args.no_auto_terms:
        terms += [t for t in auto_terms(args.since, args.until, args.all_event_terms) if t not in terms]
    queries.update(term_queries(terms))

    if args.dry_run:
        for label, q in queries.items():
            print(f"[{label}] {q} since:{since_api} until:{until_api}")
        return

    est_calls = len(queries) * max(1, args.max_tweets_per_query // 20)
    est_credits = len(queries) * args.max_tweets_per_query * CREDITS_PER_TWEET
    print(f"クエリ {len(queries)} 本（固有名詞 {len(terms)} 語）、期間 {args.since}〜{args.until}（API: since:{since_api} until:{until_api}）")
    print(f"上限まで取った場合の概算: 最大 {est_credits:,} クレジット（約 ${usd(est_credits):.2f}）、最大 {est_calls} 回・約 {est_calls * SECONDS_PER_CALL / 60:.0f} 分")
    if not args.yes:
        if input("実行しますか？ [y/N] ").strip().lower() != 'y':
            sys.exit("中止")

    os.makedirs(OUT_DIR, exist_ok=True)
    raw_path = os.path.join(OUT_DIR, f"egosearch_{args.since}_{args.until}.jsonl")
    seen = {}
    if os.path.exists(raw_path):
        with open(raw_path, encoding='utf-8') as f:
            for line in f:
                try:
                    t = json.loads(line)
                except json.JSONDecodeError:
                    continue
                tid = tweet_id(t)
                if tid:
                    seen[tid] = t
        print(f"既存 {len(seen)} 件を読み込み（重複はスキップ）")

    progress_path = os.path.join(OUT_DIR, f"egosearch_{args.since}_{args.until}.progress.json")
    progress = {}
    if os.path.exists(progress_path):
        with open(progress_path, encoding='utf-8') as f:
            progress = json.load(f)
    stats = {}
    stopped = None
    try:
        with open(raw_path, 'a', encoding='utf-8') as out:
            for i, (label, q) in enumerate(queries.items()):
                st = progress.get(label) or {}
                if st.get('done') and not st.get('cursor'):
                    print(f"\n[{label}] 取得済み（{st.get('total', 0)} 件）。スキップ")
                    stats[label] = (st.get('total', 0), st.get('new', 0), st.get('calls', 0))
                    continue
                try:
                    stats[label] = run_query(label, q, api_key, args.max_tweets_per_query, seen, out,
                                             since_api, until_api, args.sleep, progress, progress_path)
                except OutOfCredits as e:
                    stopped = f"クレジット切れ（{label} の途中）: {e}"
                    print(stopped)
                    break
                if i < len(queries) - 1:
                    time.sleep(args.sleep)
    except KeyboardInterrupt:
        stopped = "中断（Ctrl-C）。進捗は保存済みで、同じコマンドで続きから再開できる"
        print(stopped)

    # 重複した _queries を既存ファイルにも反映するため書き直す
    with open(raw_path, 'w', encoding='utf-8') as out:
        for t in seen.values():
            out.write(json.dumps(t, ensure_ascii=False) + '\n')

    # 候補リスト（Claude が読んで判定する）
    own, cands = [], []
    for t in seen.values():
        if not set(t.get('_queries', [])) & set(queries):
            continue  # 以前の実行で別のクエリだけに当たったもの（例: 外したイベント名）は候補にしない
        d = jst_dt(t)
        if d is None or not (args.since <= d.date().isoformat() <= args.until):
            continue  # API の since/until は UTC 基準で緩いので、JST の日付で期間を締める
        h = author_handle(t)
        if h in OWN_HANDLES:
            own.append(t)
            continue
        cands.append(t)
    cands.sort(key=lambda t: (jst_dt(t) or datetime.min.replace(tzinfo=JST)))

    cand_path = os.path.join(OUT_DIR, f"egosearch_candidates_{args.since}_{args.until}.md")
    with open(cand_path, 'w', encoding='utf-8') as f:
        f.write(f"# エゴサーチ候補 {args.since} 〜 {args.until}\n\n")
        f.write("> fetch_egosearch.py が集めた候補（公式・メンバー本人の投稿は除外済み）。判断はしていない。\n")
        f.write("> [ノイズ候補] はレンタルサーバー等の語を含み、アイドル文脈の語を含まないもの。最終判断は本文を読んで行う。\n")
        f.write("> 他人の投稿原文。記事には要旨1〜2文＋URLで載せ、長文は転載しない。コミットしない。\n\n")
        f.write("## クエリ別の件数\n\n")
        for label, (total, new, calls) in stats.items():
            f.write(f"- {label}: 応答 {total} 件 / 新規 {new} 件 / {calls} 回\n")
        if stopped:
            f.write(f"- **中断**: {stopped}\n")
        f.write(f"\n合計: 候補 {len(cands)} 件（本人投稿 {len(own)} 件を除外）\n\n")
        f.write("## 候補（日付順）\n\n")
        by_day = defaultdict(list)
        for t in cands:
            d = jst_dt(t)
            by_day[d.date().isoformat() if d else '不明'].append(t)
        for day in sorted(by_day):
            f.write(f"### {day}\n\n")
            for t in by_day[day]:
                text = tweet_text(t)
                d = jst_dt(t)
                noise = bool(NOISE_WORDS.search(text)) and not SIGNAL_WORDS.search(text)
                likes = t.get('likeCount', t.get('favorite_count', ''))
                views = t.get('viewCount', '')
                rts = t.get('retweetCount', '')
                url = t.get('url') or t.get('twitterUrl') or f"https://x.com/{author_handle(t)}/status/{tweet_id(t)}"
                tag = '[ノイズ候補] ' if noise else ''
                media = '📷' if has_media(t) else ''
                q = ','.join(sorted({x.split(' ')[0] for x in t.get('_queries', [])}))
                f.write(f"- {tag}[{d.strftime('%H:%M') if d else '--:--'}] @{author_handle(t)}（{author_name(t)}）"
                        f"／いいね{likes} RT{rts} 表示{views} {media}／Q{q}／{' '.join(text.split())}／{url}\n")
            f.write("\n")

    print(f"\n保存: {raw_path}（{len(seen)} 件）")
    print(f"候補リスト: {cand_path}（候補 {len(cands)} 件、本人投稿 {len(own)} 件除外）")
    if stopped:
        print(stopped)


if __name__ == '__main__':
    main()
