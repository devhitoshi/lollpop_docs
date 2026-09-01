#!/usr/bin/env python3
"""twitterapi.io で公式・メンバーアカウントの投稿を全件取得する（仕事Aのスクリプト化）。

`work/x_ugc_probe.py` の検証（2026-09-01）で確認した仕様をそのまま使う:
  - 検索 GET /twitter/tweet/advanced_search, パラメータ query / queryType / cursor
  - 単価 $0.15/1,000ツイート、最低課金15クレジット/リクエスト
  - 未課金は 0.2 QPS（5秒/コール・逐次のみ）
  - `-from:` 除外オペレーターは信用しない（除外漏れが実測されている）。
    このスクリプトは各アカウントを個別に `from:` 検索するので、そもそも除外に頼らない

目的は prompts/collect/x_collect.md の「1. 公式・メンバーの投稿を取得」を置き換えること。
Grok の「1クエリ10件の壁」を避け、原文をそのまま保存する。
「2. 周囲の反応（エゴサーチ）」はここでは扱わない。文脈判断が要るため引き続きGrok。

依存なし（標準ライブラリのみ）。python3 fetch_accounts.py --help
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

# 既存スキル（setlist-analysis）と同じ流儀で、どこから実行してもリポジトリルートを基準にする。
# スクリプトを別階層へ移した場合はこの階層数を直すこと。
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

BASE_URL = "https://api.twitterapi.io"
SEARCH_PATH = "/twitter/tweet/advanced_search"
QUERY_PARAM = "query"

# 課金レート。2026-09-01、docs.twitterapi.io/introduction.md で確認済み。
CREDITS_PER_TWEET = 15
CREDITS_PER_USD = 100_000
MIN_CREDITS_PER_CALL = 15

# 未課金アカウントは 0.2 QPS。並列化はしない（禁止事項）。
SECONDS_PER_CALL = 5.0

# prompts/collect/x_collect.md の「収集対象アカウント」と一致させること。
DEFAULT_ACCOUNTS = [
    ("lollipop_1116", "公式"),
    ("mana_lpop", "愛月まな"),
    ("kurumi_lpop", "やぎくるみ"),
    ("mayu_lpop", "夏川茉夢"),
    ("ami_lpop", "松川愛美"),
    ("mau_lpop", "まう"),
]


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
    sys.exit(
        f"APIキーが見つかりません。{env_path} に次の1行を置いてください:\n"
        "  TWITTERAPI_IO_KEY=（ダッシュボードのAPIキー）\n"
        "（.env は .gitignore 済み。環境変数 TWITTERAPI_IO_KEY でも可）"
    )


class OutOfCredits(Exception):
    """クレジット切れ。取得は打ち切るが、ここまでに取れた分は保存してドラフトまで出す。"""


def request_json(path, params, api_key, max_retries=5):
    url = f"{BASE_URL}{path}?{urllib.parse.urlencode(params)}"
    for attempt in range(max_retries):
        req = urllib.request.Request(url, headers={"x-api-key": api_key})
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")[:400]
            if e.code in (401, 403):
                sys.exit(f"認証エラー {e.code}: APIキーを確認してください。\n{body}")
            if e.code == 402:
                raise OutOfCredits(body)
            if e.code == 404:
                sys.exit(f"404: エンドポイント {path} が見つかりません。\n{body}")
            if e.code != 429 and e.code < 500:
                sys.exit(f"HTTP {e.code}: {body}")
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"    HTTP {e.code} — {wait:.1f}秒待って再試行 ({attempt + 1}/{max_retries})")
            time.sleep(wait)
        except urllib.error.URLError as e:
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"    接続失敗 ({e.reason}) — {wait:.1f}秒待って再試行 ({attempt + 1}/{max_retries})")
            time.sleep(wait)
    sys.exit(f"リトライ上限に達しました: {path}")


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


def tweet_text(tweet):
    return tweet.get("text") or tweet.get("full_text") or ""


def tweet_url(tweet, handle):
    url = tweet.get("url") or tweet.get("twitterUrl")
    if url:
        return url
    tid = tweet_id(tweet)
    return f"https://x.com/{handle}/status/{tid}" if tid else ""


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


def usd(credits):
    return credits / CREDITS_PER_USD


def fetch_account(handle, since, until, max_tweets, out_dir, api_key):
    """1アカウント分を全件列挙して JSONL に保存する。中断・再開対応。"""
    out_path = os.path.join(out_dir, f"{handle}.jsonl")
    query = f"from:{handle} since:{since} until:{until}"

    seen = set()
    if os.path.exists(out_path):
        with open(out_path, encoding="utf-8") as f:
            for line in f:
                try:
                    tid = tweet_id(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if tid:
                    seen.add(tid)

    print(f"\n[{handle}] {query}")
    if seen:
        print(f"  既存 {len(seen)}件を読み込み（重複はスキップ）")

    cursor, page, new_count, calls = None, 0, 0, 0
    with open(out_path, "a", encoding="utf-8") as out:
        while len(seen) < max_tweets:
            params = {QUERY_PARAM: query, "queryType": "Latest"}
            if cursor:
                params["cursor"] = cursor

            payload = request_json(SEARCH_PATH, params, api_key)
            calls += 1
            page += 1
            tweets, cursor = extract(payload)

            if page == 1 and not tweets:
                print("  0件")
                break

            fresh = 0
            for t in tweets:
                tid = tweet_id(t)
                if tid and tid in seen:
                    continue
                if tid:
                    seen.add(tid)
                out.write(json.dumps(t, ensure_ascii=False) + "\n")
                fresh += 1
                new_count += 1
                if len(seen) >= max_tweets:
                    break
            out.flush()
            print(f"  {page:>3}ページ目: 応答{len(tweets):>3}件 / 新規{fresh:>3}件 / 累計{len(seen):>4}件")

            if not cursor:
                break
            if len(seen) < max_tweets:
                time.sleep(SECONDS_PER_CALL)

    hit_cap = len(seen) >= max_tweets and cursor
    if hit_cap:
        print(f"  --max-tweets-per-account に達して打ち切り。{handle} の実数はこれより多い")

    return out_path, len(seen), new_count, calls


def write_draft(out_dir, since, until, accounts, results):
    """prompts/collect/x_collect.md の「メンバーの投稿」節に沿ったドラフトを書く。

    原文はそのまま保存する。「要旨・特徴的な一文」への絞り込みは記事化の段階で人間かLLMが行う
    （文脈判断が要るため、ここでは省略しない）。
    """
    draft_path = os.path.join(out_dir, "draft_member_posts.md")
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write(f"# メンバーの投稿（ドラフト・原文そのまま） {since} 〜 {until}\n\n")
        f.write(
            "取得した全件を日付順・原文のまま列挙している。記事化する際は"
            "`prompts/collect/x_collect.md` の記録ルールに従い、特徴的な一文を選ぶこと。\n"
            "ライブ・イベント／新曲・初披露／アナウンス・告知の各節は、ここから該当する投稿を"
            "拾って人間かLLMが判断して作ること（スクリプトは取得のみ）。\n\n"
        )
        for handle, label in accounts:
            jsonl_path, total, _, _ = results[handle]
            f.write(f"## {label}（@{handle}）\n\n")
            if not os.path.exists(jsonl_path):
                f.write("- 取得結果なし\n\n")
                continue
            rows = []
            with open(jsonl_path, encoding="utf-8") as jf:
                for line in jf:
                    try:
                        t = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    rows.append(t)
            rows.sort(key=lambda t: tweet_date(t))
            if not rows:
                f.write("- 該当期間の投稿なし\n\n")
                continue
            for t in rows:
                date = tweet_date(t)
                text = tweet_text(t).replace("\n", " ")
                likes = t.get("likeCount", t.get("favorite_count", ""))
                url = tweet_url(t, handle)
                f.write(f"- [{date}] {text}／いいね{likes}／出典: {url}\n")
            f.write("\n")
    return draft_path


def main():
    p = argparse.ArgumentParser(
        description="twitterapi.io で公式・メンバーアカウントの投稿を全件取得する"
    )
    p.add_argument("--since", required=True, help="開始日 YYYY-MM-DD")
    p.add_argument("--until", required=True,
                   help="終了日+1日 YYYY-MM-DD（x_collect.md の慣習と同じ。終了日を含めるなら+1日を渡す）")
    p.add_argument("--max-tweets-per-account", type=int, required=True,
                   help="1アカウントあたりの取得上限（必須・デフォルトなし）。暴走と課金の歯止め")
    p.add_argument("--accounts", default=None,
                   help="handle:ラベル のカンマ区切り（例 lollipop_1116:公式,mana_lpop:愛月まな）。"
                        "省略時は現メンバー5人+公式")
    p.add_argument("--out-dir", default=os.path.join("work", "x_fetch"))
    p.add_argument("--env", default=".env")
    p.add_argument("--yes", action="store_true", help="事前確認を省略する")
    p.add_argument("--draft-only", action="store_true",
                   help="APIを叩かず、取得済みのJSONLからドラフトだけ作り直す（課金なし）")
    args = p.parse_args()

    if args.max_tweets_per_account <= 0:
        sys.exit("--max-tweets-per-account は1以上にしてください。")

    accounts = DEFAULT_ACCOUNTS
    if args.accounts:
        accounts = []
        for item in args.accounts.split(","):
            if ":" in item:
                handle, label = item.split(":", 1)
            else:
                handle, label = item, item
            accounts.append((handle.strip().lstrip("@"), label.strip()))

    os.makedirs(args.out_dir, exist_ok=True)

    if args.draft_only:
        # 課金なし。クレジット切れで途中終了したときなど、取得済み分だけで作り直すため。
        results = {}
        for handle, _ in accounts:
            path = os.path.join(args.out_dir, f"{handle}.jsonl")
            got = 0
            if os.path.exists(path):
                with open(path, encoding="utf-8") as f:
                    got = sum(1 for _ in f)
            results[handle] = (path, got, 0, 0)
        draft_path = write_draft(args.out_dir, args.since, args.until, accounts, results)
        for handle, label in accounts:
            print(f"  @{handle}（{label}）: {results[handle][1]}件")
        print(f"\nドラフト: {draft_path}（APIは叩いていません）")
        return

    api_key = load_api_key(args.env)

    est_calls_per_account = max(1, -(-args.max_tweets_per_account // 20))
    est_calls = est_calls_per_account * len(accounts)
    est_credits = max(
        args.max_tweets_per_account * len(accounts) * CREDITS_PER_TWEET,
        est_calls * MIN_CREDITS_PER_CALL,
    )
    print(f"対象アカウント : {', '.join(f'@{h}({l})' for h, l in accounts)}")
    print(f"期間           : {args.since} 〜 {args.until}（until は exclusive）")
    print(f"上限           : アカウントあたり{args.max_tweets_per_account}件（最大 約{est_calls}コール）")
    print(f"推定コスト     : 最大 {est_credits:,}クレジット = 約${usd(est_credits):.4f}")
    print(f"推定所要時間   : 最大 約{est_calls * SECONDS_PER_CALL / 60:.1f}分（0.2 QPS・逐次）")
    print(f"保存先         : {args.out_dir}")

    if not args.yes:
        if input("\n実行しますか？ [y/N] ").strip().lower() not in ("y", "yes"):
            sys.exit("中止しました。")

    results = {}
    total_calls = 0
    total_new = 0
    incomplete = []
    for i, (handle, label) in enumerate(accounts):
        try:
            out_path, total, new_count, calls = fetch_account(
                handle, args.since, args.until, args.max_tweets_per_account, args.out_dir, api_key
            )
        except OutOfCredits:
            # 残高切れ。ここまでに保存できた分は活かし、残りは未取得として報告する。
            print(f"\n  クレジット残高が尽きました。@{handle} は取得途中、以降のアカウントは未取得です。")
            incomplete = [h for h, _ in accounts[i:]]
            for h, _ in accounts[i:]:
                path = os.path.join(args.out_dir, f"{h}.jsonl")
                got = 0
                if os.path.exists(path):
                    with open(path, encoding="utf-8") as f:
                        got = sum(1 for _ in f)
                results.setdefault(h, (path, got, 0, 0))
            break
        results[handle] = (out_path, total, new_count, calls)
        total_calls += calls
        total_new += new_count
        if i < len(accounts) - 1:
            time.sleep(SECONDS_PER_CALL)

    draft_path = write_draft(args.out_dir, args.since, args.until, accounts, results)

    spent = max(total_calls * MIN_CREDITS_PER_CALL, total_new * CREDITS_PER_TWEET)
    print("\n" + "=" * 56)
    for handle, label in accounts:
        _, total, new_count, _ = results[handle]
        print(f"  @{handle}（{label}）: 累計{total}件（今回新規{new_count}件）")
    print(f"コール数計           : {total_calls}")
    print(f"概算コスト           : {spent:,}クレジット = 約${usd(spent):.4f}")
    print(f"ドラフト             : {draft_path}")
    if incomplete:
        print(f"\n未完了（クレジット切れ）: {', '.join('@' + h for h in incomplete)}")
        print("残高を足したうえで同じコマンドを再実行すると、取得済みはスキップして続きから取れます。")
    print("=" * 56)


if __name__ == "__main__":
    main()
