#!/usr/bin/env python3
"""twitterapi.io で「1クエリ10件の壁」を検証するための最小スクリプト。

目的は移行ではなく、判断材料をひとつ取ること:
  Grok が「下限20件」と報告した直近30日のファン投稿は、実数で何件あるのか。

`work/x収集ルートの検討.md` の「提案する次の一手」に対応する。
使い方は同ディレクトリの x_ugc_probe.md を参照。

依存なし（標準ライブラリのみ）。python3 work/x_ugc_probe.py --help
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

BASE_URL = "https://api.twitterapi.io"

# ダッシュボードのcURL例で確認済み: 認証は x-api-key ヘッダ、user/info は userName クエリ。
USER_INFO_PATH = "/twitter/user/info"

# 未検証。引き継ぎ文書の記載をそのまま使っている。
# 404 が返ったら docs.twitterapi.io/llms.txt を見て --search-path / --query-param で上書きする。
DEFAULT_SEARCH_PATH = "/twitter/tweet/advanced_search"
DEFAULT_QUERY_PARAM = "query"

# 課金レート（引き継ぎ文書より・未検証）。$1 = 100,000クレジット、$0.15/1,000ツイート。
CREDITS_PER_TWEET = 15
CREDITS_PER_USD = 100_000
MIN_CREDITS_PER_CALL = 15

# 未課金アカウントは 0.2 QPS。並列化は 429 を誘発するだけなので逐次で待つ。
SECONDS_PER_CALL = 5.0


def load_api_key(env_path):
    """.env から API キーを読む。コードにも引数にも書かせない。"""
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


def request_json(path, params, api_key, max_retries=5):
    """GET して JSON を返す。429/5xx はジッタ付き指数バックオフでリトライ。"""
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
            if e.code == 404:
                sys.exit(
                    f"404: エンドポイント {path} が見つかりません。\n{body}\n"
                    "docs.twitterapi.io/llms.txt で正しいパスを確認し、"
                    "--search-path / --query-param で上書きしてください。"
                )
            if e.code != 429 and e.code < 500:
                sys.exit(f"HTTP {e.code}: {body}")
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"  HTTP {e.code} — {wait:.1f}秒待って再試行 ({attempt + 1}/{max_retries})")
            time.sleep(wait)
        except urllib.error.URLError as e:
            wait = (2 ** attempt) + random.uniform(0, 1)
            print(f"  接続失敗 ({e.reason}) — {wait:.1f}秒待って再試行 ({attempt + 1}/{max_retries})")
            time.sleep(wait)
    sys.exit(f"リトライ上限に達しました: {path}")


def extract(payload):
    """レスポンス形状に幅を持たせて、ツイート配列と次カーソルを取り出す。"""
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


def usd(credits):
    return credits / CREDITS_PER_USD


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    p = argparse.ArgumentParser(
        description="twitterapi.io の advanced_search を全件列挙して件数を数える（検証用）"
    )
    p.add_argument("--query", required=True, help="x.com/search-advanced と同じ文法の検索クエリ")
    p.add_argument("--max-tweets", type=int, required=True,
                   help="取得上限（必須・デフォルトなし）。暴走と課金の歯止め")
    p.add_argument("--out", default=os.path.join(here, "probe_raw.jsonl"),
                   help="生JSONの保存先（JSONL）")
    p.add_argument("--env", default=os.path.join(os.path.dirname(here), ".env"))
    p.add_argument("--search-path", default=DEFAULT_SEARCH_PATH,
                   help=f"検索エンドポイント（既定 {DEFAULT_SEARCH_PATH}・未検証）")
    p.add_argument("--query-param", default=DEFAULT_QUERY_PARAM,
                   help=f"クエリのパラメータ名（既定 {DEFAULT_QUERY_PARAM}・未検証）")
    p.add_argument("--check-user", metavar="USERNAME",
                   help="検索の前に user/info を1回叩いて疎通とキーを確認する（例 lollipop_1116）")
    p.add_argument("--yes", action="store_true", help="事前確認を省略する")
    args = p.parse_args()

    if args.max_tweets <= 0:
        sys.exit("--max-tweets は1以上にしてください。")

    api_key = load_api_key(args.env)

    # 見積もりを先に出す。0.2 QPS 制約があるので時間も金額と同じくらい重要。
    est_calls = max(1, -(-args.max_tweets // 20))
    est_credits = max(args.max_tweets * CREDITS_PER_TWEET, est_calls * MIN_CREDITS_PER_CALL)
    print(f"クエリ         : {args.query}")
    print(f"取得上限       : {args.max_tweets}件（最大 約{est_calls}コール）")
    print(f"推定コスト     : 最大 {est_credits:,}クレジット = 約${usd(est_credits):.4f}")
    print(f"推定所要時間   : 最大 約{est_calls * SECONDS_PER_CALL / 60:.1f}分（0.2 QPS・逐次）")
    print(f"保存先         : {args.out}")
    print("※ 残高はダッシュボードで確認してください（残高APIは未検証のため叩きません）")

    if not args.yes:
        if input("\n実行しますか？ [y/N] ").strip().lower() not in ("y", "yes"):
            sys.exit("中止しました。")

    if args.check_user:
        print(f"\n[疎通確認] {USER_INFO_PATH}?userName={args.check_user}")
        info = request_json(USER_INFO_PATH, {"userName": args.check_user}, api_key)
        blob = json.dumps(info, ensure_ascii=False)
        followers = re.search(r'"followers(?:_count)?"\s*:\s*(\d+)', blob)
        print(f"  OK — フォロワー数: {followers.group(1) if followers else '（キー名不明・生JSON参照）'}")
        if not followers:
            print(f"  生JSON(先頭400字): {blob[:400]}")
        time.sleep(SECONDS_PER_CALL)

    # 中断・再開: 既に保存済みのIDは数え直さない。
    seen = set()
    if os.path.exists(args.out):
        with open(args.out, encoding="utf-8") as f:
            for line in f:
                try:
                    tid = tweet_id(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if tid:
                    seen.add(tid)
        if seen:
            print(f"\n既存の {args.out} から {len(seen)}件を読み込みました（重複はスキップします）")

    print(f"\n[検索] {args.search_path}")
    cursor, page, new_count, calls = None, 0, 0, 0
    started = time.time()

    with open(args.out, "a", encoding="utf-8") as out:
        while len(seen) < args.max_tweets:
            params = {args.query_param: args.query, "queryType": "Latest"}
            if cursor:
                params["cursor"] = cursor

            payload = request_json(args.search_path, params, api_key)
            calls += 1
            page += 1
            tweets, cursor = extract(payload)

            if page == 1 and not tweets:
                print("  0件。クエリを x.com のUIで先に確認してください。")
                print(f"  生JSON(先頭400字): {json.dumps(payload, ensure_ascii=False)[:400]}")
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
                if len(seen) >= args.max_tweets:
                    break
            out.flush()

            spent = max(calls * MIN_CREDITS_PER_CALL, new_count * CREDITS_PER_TWEET)
            print(f"  {page:>3}ページ目: 応答{len(tweets):>3}件 / 新規{fresh:>3}件 / "
                  f"累計{len(seen):>4}件 / 約{spent:,}クレジット(${usd(spent):.4f})")

            if not cursor:
                print("  カーソルが尽きました（全件列挙の完了）")
                break
            if len(seen) < args.max_tweets:
                time.sleep(SECONDS_PER_CALL)

    elapsed = time.time() - started
    spent = max(calls * MIN_CREDITS_PER_CALL, new_count * CREDITS_PER_TWEET)
    hit_cap = len(seen) >= args.max_tweets and cursor

    print("\n" + "=" * 56)
    print(f"総件数（重複排除後） : {len(seen)}")
    print(f"今回の新規取得       : {new_count}")
    print(f"コール数             : {calls}")
    print(f"概算コスト           : {spent:,}クレジット = 約${usd(spent):.4f}")
    print(f"所要時間             : {elapsed / 60:.1f}分")
    print(f"生JSON               : {args.out}")
    if hit_cap:
        print("\n--max-tweets に達して打ち切りました。実数はこれより多いので、"
              "上限を上げて再実行してください（取得済みはスキップされます）。")
    print("=" * 56)
    print("\n判断の目安（work/x収集ルートの検討.md より）")
    print("  20〜30件程度 → Grokの「下限20件」はほぼ実数。現状維持で確定")
    print("  100件以上    → KPIベースラインが実態より低い。併用案に進む価値あり")


if __name__ == "__main__":
    main()
