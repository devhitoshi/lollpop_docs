#!/usr/bin/env python3
"""公式・メンバーの投稿と、ハッシュタグだけのエゴサを毎日取得する（Windows タスクスケジューラから呼ぶ）。

- 期間は「前回取得した最後の日の翌日〜昨日」。今日は取らない（途中で取ると翌日に同じ日を取り直して二重に課金されるため）
- アカウント: fetch_accounts.fetch_account() をそのまま使い、work/x_fetch/<handle>.jsonl に追記する
- タグ: #ろりぽっぷ ＋ メンバーのプロフィールに書かれたタグ（取得済み投稿の author.profile_bio から拾う。
  追加の API 呼び出しは無い）。1 本の OR 検索で work/x_fetch/hashtags_YYYY-MM.jsonl に追記する
- 状態は work/x_fetch/.daily_state.json、ログは work/x_fetch/logs/daily_fetch.log
- 週刊のフル・エゴサ（x-egosearch）はここでは回さない

使い方:
    python .claude/skills/x-account-fetch/scripts/daily_fetch.py --dry-run
    python .claude/skills/x-account-fetch/scripts/daily_fetch.py
    python .claude/skills/x-account-fetch/scripts/daily_fetch.py --since 2026-09-10   # 期間の開始を手で指定
"""

import argparse
import glob
import json
import os
import sys
import time
import traceback
from datetime import date, datetime, timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, script_dir)
from fetch_accounts import (  # noqa: E402  fetch_accounts が import 時にリポジトリルートへ chdir する
    CREDITS_PER_TWEET, DEFAULT_ACCOUNTS, MIN_CREDITS_PER_CALL, QUERY_PARAM, SEARCH_PATH, SECONDS_PER_CALL,
    OutOfCredits, extract, fetch_account, load_api_key, request_json, tweet_date, tweet_id, usd,
)

OUT_DIR = os.path.join("work", "x_fetch")
STATE_PATH = os.path.join(OUT_DIR, ".daily_state.json")
LOG_PATH = os.path.join(OUT_DIR, "logs", "daily_fetch.log")

GROUP_TAG = "ろりぽっぷ"
# プロフィールからタグを拾えなかったとき（lollpop_data から復元したデータは profile_bio を持たない）の予備。
# 2026-09-09 時点の各メンバーのプロフィールから転記。
FALLBACK_MEMBER_TAGS = ["まなてぃータイム", "くるみるく", "くるみんとKP", "餃子のおまゆ", "まんてんあみてん", "まうだよ"]

MAX_GAP_DAYS = 31
MAX_PER_ACCOUNT_PER_DAY = 100
MAX_TAG_TWEETS_PER_DAY = 200


class Tee:
    """コンソール（pythonw では無い）とログファイルの両方に書く。"""

    def __init__(self, console, log):
        self.console, self.log = console, log

    def write(self, s):
        if self.console:
            try:
                self.console.write(s)
            except UnicodeEncodeError:
                pass
        self.log.write(s)

    def flush(self):
        if self.console:
            self.console.flush()
        self.log.flush()


def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state):
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=1)


def latest_account_dates():
    """アカウントごとの取得済み最新日。状態ファイルが無い初回に、どこから取るかを決めるのに使う。"""
    dates = {}
    for handle, _ in DEFAULT_ACCOUNTS:
        path = os.path.join(OUT_DIR, f"{handle}.jsonl")
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as f:
            ds = [tweet_date(json.loads(line)) for line in f if line.strip()]
        if ds:
            dates[handle] = max(ds)
    return dates


def member_tags():
    """各アカウントの最新投稿に付いているプロフィールからハッシュタグを拾う。"""
    tags = [GROUP_TAG]
    found_any = False
    for handle, _ in DEFAULT_ACCOUNTS:
        path = os.path.join(OUT_DIR, f"{handle}.jsonl")
        if not os.path.exists(path):
            continue
        best = None
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    t = json.loads(line)
                except json.JSONDecodeError:
                    continue
                bio = (t.get("author") or {}).get("profile_bio") or {}
                if not bio:
                    continue
                created = datetime.strptime(t["createdAt"], "%a %b %d %H:%M:%S %z %Y")
                if best is None or created > best[0]:
                    best = (created, bio)
        if not best:
            continue
        found_any = True
        for h in (best[1].get("entities", {}).get("description", {}).get("hashtags") or []):
            if h.get("text") and h["text"] not in tags:
                tags.append(h["text"])
    if not found_any:
        print("  プロフィールが取得データに無いので、予備のタグ一覧を使う")
        tags += [t for t in FALLBACK_MEMBER_TAGS if t not in tags]
    return tags


def fetch_hashtags(tags, since, until_excl, max_tweets, api_key):
    """タグの OR 検索を全件取り、投稿日の月ごとのファイルに追記する。戻り値は (新規件数, 応答件数, コール数, クレジット)。"""
    query = "(" + " OR ".join(f"#{t}" for t in tags) + f") since:{since} until:{until_excl}"
    print(f"\n[タグ] {query}")

    seen = set()
    for path in glob.glob(os.path.join(OUT_DIR, "hashtags_*.jsonl")):
        with open(path, encoding="utf-8") as f:
            for line in f:
                try:
                    tid = tweet_id(json.loads(line))
                except json.JSONDecodeError:
                    continue
                if tid:
                    seen.add(tid)

    cursor, calls, returned, new, credits = None, 0, 0, 0, 0
    handles = {}
    try:
        while returned < max_tweets:
            params = {QUERY_PARAM: query, "queryType": "Latest"}
            if cursor:
                params["cursor"] = cursor
            payload = request_json(SEARCH_PATH, params, api_key)
            calls += 1
            tweets, cursor = extract(payload)
            returned += len(tweets)
            credits += max(MIN_CREDITS_PER_CALL, len(tweets) * CREDITS_PER_TWEET)
            for t in tweets:
                tid = tweet_id(t)
                if not tid or tid in seen:
                    continue
                seen.add(tid)
                text = (t.get("text") or "").lower()
                t["_tags"] = [tag for tag in tags if f"#{tag}".lower() in text]
                month = tweet_date(t)[:7]
                if month not in handles:
                    handles[month] = open(os.path.join(OUT_DIR, f"hashtags_{month}.jsonl"), "a", encoding="utf-8")
                handles[month].write(json.dumps(t, ensure_ascii=False) + "\n")
                new += 1
            print(f"  {calls:>3}ページ目: 応答{len(tweets):>3}件 / 累計新規{new:>4}件")
            if not cursor or not tweets:
                break
            time.sleep(SECONDS_PER_CALL)
    finally:
        for h in handles.values():
            h.close()
    if returned >= max_tweets and cursor:
        print(f"  上限 {max_tweets} 件で打ち切り。実数はこれより多い")
    return new, returned, calls, credits


def main():
    p = argparse.ArgumentParser(description="公式・メンバーの投稿とハッシュタグを毎日取得する")
    p.add_argument("--since", help="開始日 YYYY-MM-DD（省略時は状態ファイルの翌日）")
    p.add_argument("--dry-run", action="store_true", help="期間・タグ・検索文を表示するだけで API を叩かない")
    p.add_argument("--env", default=".env")
    args = p.parse_args()

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    log = open(LOG_PATH, "a", encoding="utf-8")
    sys.stdout = sys.stderr = Tee(sys.__stdout__, log)
    print(f"\n===== {datetime.now().isoformat(timespec='seconds')} daily_fetch{' --dry-run' if args.dry_run else ''} =====")

    state = load_state()
    yesterday = date.today() - timedelta(days=1)
    if args.since:
        since = date.fromisoformat(args.since)
    elif state.get("last_until"):
        since = date.fromisoformat(state["last_until"]) + timedelta(days=1)
    else:
        # 初回: 取得済みデータの続きから。アカウントごとの最新日のうち一番古い日を、取りこぼし防止のため取り直す
        latest = latest_account_dates()
        since = date.fromisoformat(min(latest.values())) if latest else yesterday
        print(f"状態ファイルが無いので、取得済みデータの最新日から開始: {since}（{latest}）")

    if since > yesterday:
        print(f"取得する期間が無い（昨日 {yesterday} まで取得済み）。API は叩かない")
        return 0
    days = (yesterday - since).days + 1
    until_excl = (yesterday + timedelta(days=1)).isoformat()
    print(f"期間: {since} 〜 {yesterday}（{days} 日分）")

    tags = member_tags()
    print(f"タグ: {' '.join('#' + t for t in tags)}")

    if days > MAX_GAP_DAYS:
        msg = f"空きが {days} 日で上限 {MAX_GAP_DAYS} 日を超えた。取りすぎ防止のため取得しない。--since を指定して手動で実行する"
        print(msg)
        state.update(last_run_at=datetime.now().isoformat(timespec="seconds"), last_result=f"中止: {msg}")
        save_state(state)
        return 1

    if args.dry_run:
        for handle, _ in DEFAULT_ACCOUNTS:
            print(f"  from:{handle} since:{since} until:{until_excl}")
        print(f"  ({' OR '.join('#' + t for t in tags)}) since:{since} until:{until_excl}")
        return 0

    api_key = load_api_key(args.env)
    total_calls, total_credits, summary = 0, 0, []
    try:
        for handle, _ in DEFAULT_ACCOUNTS:
            _, _, new_count, calls = fetch_account(
                handle, since.isoformat(), until_excl, days * MAX_PER_ACCOUNT_PER_DAY, OUT_DIR, api_key)
            # 応答件数は返らないので、新規件数とコール数から下限を見積もる（重複分は含まれない）
            total_calls += calls
            total_credits += max(calls * MIN_CREDITS_PER_CALL, new_count * CREDITS_PER_TWEET)
            summary.append(f"{handle}={new_count}")
            time.sleep(SECONDS_PER_CALL)

        tag_new, tag_returned, tag_calls, tag_credits = fetch_hashtags(
            tags, since.isoformat(), until_excl, days * MAX_TAG_TWEETS_PER_DAY, api_key)
        total_calls += tag_calls
        total_credits += tag_credits
        summary.append(f"タグ={tag_new}（応答{tag_returned}）")
    except (OutOfCredits, SystemExit, Exception) as e:  # noqa: BLE001  失敗しても状態を進めずに記録して終わる
        reason = "クレジット切れ" if isinstance(e, OutOfCredits) else f"{type(e).__name__}: {e}"
        if not isinstance(e, (OutOfCredits, SystemExit)):
            traceback.print_exc()
        print(f"\n失敗: {reason}。状態は進めない（次回同じ期間から取り直す）")
        state.update(last_run_at=datetime.now().isoformat(timespec="seconds"), last_result=f"失敗: {reason}")
        save_state(state)
        return 1

    # covered_from〜last_until は途切れずに取れている範囲（run_weekly.py がアカウントの取得を省くのに使う）。
    # 手動の --since で間が空いたら、そこから数え直す
    if not state.get("last_until") or since > date.fromisoformat(state["last_until"]) + timedelta(days=1):
        state["covered_from"] = since.isoformat()
    state.update(
        last_until=yesterday.isoformat(),
        last_run_at=datetime.now().isoformat(timespec="seconds"),
        last_result="成功",
    )
    save_state(state)
    print(f"\n成功: {since}〜{yesterday} / {' '.join(summary)} / {total_calls} コール / "
          f"概算 {total_credits:,} クレジット（約 ${usd(total_credits):.4f}）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
