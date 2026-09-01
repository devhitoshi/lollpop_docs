#!/usr/bin/env python3
"""「ろりぽっぷ!!!!!!!」周囲の反応（エゴサーチ）を twitterapi.io で取得する。

`prompts/collect/x_collect.md` の手順2（2-1〜2-5）のクエリをそのまま叩き、生データを
クエリ単位でローカルキャッシュ（`x_cache/egosearch/`、Git管理外）に保存する。
同じ期間・同じクエリは2回目以降キャッシュから読み、APIを叩かない（課金なし）。

ノイズ判定（同名レンタルサーバー「ロリポップ!」との混同、無関係の別グループとの重複など）は
ここではやらない。人間かLLM（Claude本体・サブエージェント）が別途行う。

`fetch_accounts.py`（アカウント別の`from:`検索）と同じ twitterapi.io
`GET /twitter/tweet/advanced_search` を使うが、こちらはキーワード検索。

依存なし（標準ライブラリのみ）。
"""

import argparse
import json
import os
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

# 既存スキル（x-account-fetch, setlist-analysis）と同じ流儀で、どこから実行してもリポジトリルートを基準にする。
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, "../../../../"))
os.chdir(project_root)

BASE_URL = "https://api.twitterapi.io"
SEARCH_PATH = "/twitter/tweet/advanced_search"

CREDITS_PER_TWEET = 15
CREDITS_PER_USD = 100_000
MIN_CREDITS_PER_CALL = 15
SECONDS_PER_CALL = 5.0

CACHE_ROOT = os.path.join("x_cache", "egosearch")

EXCLUDED_HANDLES = ["lollipop_1116", "mana_lpop", "kurumi_lpop", "mayu_lpop", "ami_lpop", "mau_lpop"]


def load_api_key(env_path):
    key = os.environ.get("TWITTERAPI_IO_KEY")
    if key:
        return key.strip()
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.startswith("TWITTERAPI_IO_KEY="):
                    return line.split("=", 1)[1].strip().strip("'\"")
    sys.exit(f"APIキーが見つかりません（{env_path} または環境変数 TWITTERAPI_IO_KEY）")


class OutOfCredits(Exception):
    pass


def request_json(params, api_key, max_retries=5):
    url = f"{BASE_URL}{SEARCH_PATH}?{urllib.parse.urlencode(params)}"
    for attempt in range(max_retries):
        req = urllib.request.Request(url, headers={"x-api-key": api_key})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:400]
            if e.code in (401, 403):
                sys.exit(f"認証エラー {e.code}: {body}")
            if e.code == 402:
                raise OutOfCredits(body)
            if e.code == 404:
                sys.exit(f"404: {body}")
            if e.code != 429 and e.code < 500:
                sys.exit(f"HTTP {e.code}: {body}")
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"    HTTP {e.code} — {wait:.1f}秒待って再試行 ({attempt + 1}/{max_retries})")
            time.sleep(wait)
        except urllib.error.URLError as e:
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"    接続失敗 ({e.reason}) — {wait:.1f}秒待って再試行 ({attempt + 1}/{max_retries})")
            time.sleep(wait)
    sys.exit("リトライ上限に達しました")


def extract(payload):
    tweets = None
    for key in ("tweets", "data", "results", "items"):
        value = payload.get(key)
        if isinstance(value, list):
            tweets = value
            break
        if isinstance(value, dict) and isinstance(value.get("tweets"), list):
            tweets = value["tweets"]
            break
    if tweets is None:
        tweets = []
    cursor = None
    for key in ("next_cursor", "nextCursor", "cursor"):
        value = payload.get(key)
        if isinstance(value, str) and value and value != "0":
            cursor = value
            break
    has_next = payload.get("has_next_page", payload.get("hasNextPage"))
    if has_next is False:
        cursor = None
    return tweets, cursor


def tweet_id(tweet):
    for key in ("id", "id_str", "tweet_id", "rest_id"):
        value = tweet.get(key)
        if value:
            return str(value)
    return None


def tweet_author_handle(tweet):
    author = tweet.get("author") or {}
    handle = author.get("userName") or author.get("screen_name") or ""
    return handle.lower()


def is_excluded_author(tweet):
    # `-from:` は信頼しない既知の癖がある（除外指定してもそのアカウント自身の投稿が紛れ込むことが
    # 実測されている）ので、クエリ側の除外に加えてここでも著者ハンドルで弾く。
    return tweet_author_handle(tweet) in {h.lower() for h in EXCLUDED_HANDLES}


def tweet_date(tweet):
    created = tweet.get("createdAt") or tweet.get("created_at") or ""
    m = re.search(r"(\w{3}) (\w{3}) (\d{2}) .* (\d{4})", created)
    if not m:
        return created
    months = {
        "Jan": "01", "Feb": "02", "Mar": "03", "Apr": "04", "May": "05", "Jun": "06",
        "Jul": "07", "Aug": "08", "Sep": "09", "Oct": "10", "Nov": "11", "Dec": "12",
    }
    _, mon, day, year = m.groups()
    return f"{year}-{months.get(mon, '??')}-{day}"


def cache_path(period_dir, label):
    safe_label = re.sub(r'[\\/:*?"<>|]', "_", label)
    return os.path.join(period_dir, f"{safe_label}.jsonl")


def load_cache(path):
    rows = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def run_query_live(label, query, max_tweets, api_key):
    print(f"\n[{label}] {query}")
    cursor, page, rows = None, 0, []
    seen = set()
    calls = 0
    while len(rows) < max_tweets:
        params = {"query": query, "queryType": "Latest"}
        if cursor:
            params["cursor"] = cursor
        payload = request_json(params, api_key)
        calls += 1
        page += 1
        tweets, cursor = extract(payload)
        if page == 1 and not tweets:
            print("  0件")
            break
        fresh = 0
        for t in tweets:
            if is_excluded_author(t):
                continue
            tid = tweet_id(t)
            if tid and tid in seen:
                continue
            if tid:
                seen.add(tid)
            t["_query_label"] = label
            rows.append(t)
            fresh += 1
            if len(rows) >= max_tweets:
                break
        print(f"  {page:>2}ページ目: 応答{len(tweets):>3}件 / 新規{fresh:>3}件 / 累計{len(rows):>4}件")
        if not cursor:
            break
        if len(rows) < max_tweets:
            time.sleep(SECONDS_PER_CALL)
    return rows, calls


def build_queries(since, until, event_terms):
    excl = " ".join(f"-from:{h}" for h in EXCLUDED_HANDLES)
    q = []
    q.append((
        "2-1_基本形",
        f'("ろりぽっぷ" OR "#ろりぽっぷ" OR "ろりぽ" OR @lollipop_1116) {excl} since:{since} until:{until}',
    ))
    q.append((
        "2-2_カタカナ英字",
        f'("ロリポップ" OR "ロリポ" OR "lollipop") (アイドル OR ライブ OR 対バン OR セトリ OR 特典会 OR チェキ OR 現場) {excl} since:{since} until:{until}',
    ))
    q.append((
        "2-3_メンバー名",
        f'("愛月まな" OR "まなてぃー" OR "やぎくるみ" OR "くるみん" OR "夏川茉夢" OR "おまゆ" OR "松川愛美" OR "あみてん" OR @mana_lpop OR @kurumi_lpop OR @mayu_lpop OR @ami_lpop OR @mau_lpop) {excl} since:{since} until:{until}',
    ))
    for term in event_terms:
        q.append((f"2-4_固有名詞_{term}", f'"{term}" {excl} since:{since} until:{until}'))
    event_or = " OR ".join('"{}"'.format(t) for t in event_terms)
    q.append((
        "2-5_画像動画",
        f'("ろりぽっぷ" OR {event_or}) filter:media {excl} since:{since} until:{until}',
    ))
    return q


def main():
    p = argparse.ArgumentParser(description="エゴサーチ生データ取得（クエリ単位でローカルキャッシュ）")
    p.add_argument("--since", required=True)
    p.add_argument("--until", required=True, help="終了日+1日（until は exclusive）")
    p.add_argument("--event-terms", required=True, help="カンマ区切り（例: 夏色ラムネ,クモリニキ）")
    p.add_argument("--max-per-query", type=int, default=40)
    p.add_argument("--out", default=None, help="全クエリを統合したダンプ先。省略時は x_cache 配下のみに保存")
    p.add_argument("--env", default=".env")
    p.add_argument("--yes", action="store_true")
    p.add_argument("--refresh", action="store_true", help="キャッシュを無視して全クエリを再取得する")
    args = p.parse_args()

    event_terms = [t.strip() for t in args.event_terms.split(",") if t.strip()]
    queries = build_queries(args.since, args.until, event_terms)
    period_dir = os.path.join(CACHE_ROOT, f"{args.since}_{args.until}")
    os.makedirs(period_dir, exist_ok=True)

    to_fetch = []
    for label, query in queries:
        path = cache_path(period_dir, label)
        if os.path.exists(path) and not args.refresh:
            continue
        to_fetch.append((label, query))

    if not to_fetch:
        print(f"全{len(queries)}クエリがキャッシュ済みです（{period_dir}）。APIは叩きません。")
    else:
        est_calls = sum(max(1, -(-args.max_per_query // 20)) for _ in to_fetch)
        est_credits = max(args.max_per_query * len(to_fetch) * CREDITS_PER_TWEET, est_calls * MIN_CREDITS_PER_CALL)
        print(f"クエリ数       : {len(queries)}（うちキャッシュ済み {len(queries) - len(to_fetch)}件はスキップ）")
        for label, q in to_fetch:
            print(f"  [取得予定] [{label}] {q}")
        print(f"クエリあたり上限: {args.max_per_query}件")
        print(f"推定コスト     : 最大 {est_credits:,}クレジット = 約${est_credits / CREDITS_PER_USD:.4f}")
        print(f"推定所要時間   : 最大 約{est_calls * SECONDS_PER_CALL / 60:.1f}分")
        print(f"キャッシュ先   : {period_dir}")

        if not args.yes:
            if input("\n実行しますか？ [y/N] ").strip().lower() not in ("y", "yes"):
                sys.exit("中止しました。")

        api_key = load_api_key(args.env)
        total_calls, total_new = 0, 0
        for i, (label, query) in enumerate(to_fetch):
            path = cache_path(period_dir, label)
            try:
                rows, calls = run_query_live(label, query, args.max_per_query, api_key)
            except OutOfCredits:
                print(f"\nクレジット残高が尽きました。[{label}] 以降は未取得です。")
                break
            with open(path, "w", encoding="utf-8") as f:
                for t in rows:
                    f.write(json.dumps(t, ensure_ascii=False) + "\n")
            total_calls += calls
            total_new += len(rows)
            if i < len(to_fetch) - 1:
                time.sleep(SECONDS_PER_CALL)

        spent = max(total_calls * MIN_CREDITS_PER_CALL, total_new * CREDITS_PER_TWEET)
        print("\n" + "=" * 56)
        print(f"新規取得件数   : {total_new}")
        print(f"コール数計     : {total_calls}")
        print(f"概算コスト     : {spent:,}クレジット = 約${spent / CREDITS_PER_USD:.4f}")
        print("=" * 56)

    # キャッシュ済み分（今回読んだ分・元から読んでいた分の両方）を報告し、--out があれば統合する。
    merged = {}
    for label, _ in queries:
        path = cache_path(period_dir, label)
        if not os.path.exists(path):
            continue
        rows = load_cache(path)
        print(f"  [{label}] キャッシュ {len(rows)}件（{path}）")
        for t in rows:
            tid = tweet_id(t)
            if tid and tid not in merged:
                merged[tid] = t

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        rows = sorted(merged.values(), key=tweet_date)
        with open(args.out, "w", encoding="utf-8") as f:
            for t in rows:
                f.write(json.dumps(t, ensure_ascii=False) + "\n")
        print(f"\n統合ダンプ（重複除去済み・{len(rows)}件）: {args.out}")


if __name__ == "__main__":
    main()
