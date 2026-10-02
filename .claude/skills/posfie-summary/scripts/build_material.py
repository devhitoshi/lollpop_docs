#!/usr/bin/env python3
"""posfie まとめ用の素材データを、取得済みの X 投稿から期間で切り出す。

posfie は「ポストを並べてコメントを添える」だけのサービスなので、記事化と違って
本文を書き起こす必要がない。要るのは **どのポストを、どの順で貼るか** の一覧。
このスクリプトはその候補を出すところまでを引き受け、選別と一言コメントは人／LLM が行う。

入力:
  work/x_fetch/<handle>.jsonl                     公式・メンバーの投稿（x-account-fetch の出力）
  work/x_fetch/egosearch_triage_*_final.jsonl     エゴサーチの原文（x-egosearch の出力）
  data/x/egosearch_adopted_*.txt                  上記のうち採用と判定した ID（Claude 判定済み）

出力:
  work/posfie/<since>_<until>_素材データ.md       候補の一覧（時系列／いいね順）
"""

import argparse
import collections
import glob
import json
import os
import re
from datetime import datetime, timedelta, timezone

# x-account-fetch と同じ流儀で、どこから実行してもリポジトリルートを基準にする。
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

JST = timezone(timedelta(hours=9))

# 表示に使う愛称。あだ名の正は members/members.md、絵文字（担当カラー）は
# prompts/write/style_ai_poppar.md。装飾目的で他の絵文字を足さない。
ACCOUNTS = [
    ("lollipop_1116", "公式"),
    ("mana_lpop", "まなてぃー🤍"),
    ("kurumi_lpop", "くるみん❤️"),
    ("mayu_lpop", "おまゆ💛"),
    ("ami_lpop", "あみてん💚"),
    ("mau_lpop", "まう🩵"),
]

# 引用から外すアカウント。data/x/egosearch_*_reactions.md の判定に合わせる。
# @mo_8_c はオーナー本人なので「外部の反応」として扱わない（集計には含める）。
EXCLUDE_HANDLES = {"mo_8_c"}


def parse_created_at(value):
    """twitterapi.io の createdAt（"Sat Sep 06 12:34:56 +0000 2026"）を JST の datetime にする。"""
    try:
        return datetime.strptime(value, "%a %b %d %H:%M:%S %z %Y").astimezone(JST)
    except (ValueError, TypeError):
        return None


def load_jsonl(path):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                yield json.loads(line)
            except json.JSONDecodeError:
                continue


def in_period(tweet, since, until):
    dt = parse_created_at(tweet.get("createdAt"))
    if dt is None:
        return None
    return dt if since <= dt.date() <= until else None


def normalize(text):
    """定型文の重複検出用。URL・ハッシュタグ・記号・空白を落として本文だけ残す。"""
    text = re.sub(r"https?://\S+", "", text)
    text = re.sub(r"[#＃]\S+", "", text)
    text = re.sub(r"[\s　!！?？。、,.…~〜ー・\"'”’]+", "", text)
    return text


def format_tweet(tweet, dt, label=None):
    handle = (tweet.get("author") or {}).get("userName", "?")
    who = f"@{handle}" if label is None else f"{label}（@{handle}）"
    body = (tweet.get("text") or "").replace("\n", "\n      ")
    head = (
        f"- **{dt:%m/%d %H:%M}** {who} ♥{tweet.get('likeCount', 0)} "
        f"RT{tweet.get('retweetCount', 0)}\n"
        f"  {tweet['url']}\n"
    )
    return head + f"      {body}\n"


def collect_accounts(since, until, include_replies):
    """公式・メンバーの投稿を期間で切り、時系列に並べる。"""
    rows, skipped = [], collections.Counter()
    for handle, label in ACCOUNTS:
        for tweet in load_jsonl(os.path.join("work/x_fetch", f"{handle}.jsonl")):
            dt = in_period(tweet, since, until)
            if dt is None:
                continue
            # RT は本人の言葉ではないので posfie には貼らない（元投稿を貼るべきもの）。
            if tweet.get("retweeted_tweet"):
                skipped["RT"] += 1
                continue
            # リプライは文脈が切れて読めないため既定では外す。
            if tweet.get("isReply") and not include_replies:
                skipped["リプライ"] += 1
                continue
            rows.append((dt, label, tweet))
    rows.sort(key=lambda r: r[0])
    return rows, skipped


def collect_reactions(since, until, limit):
    """エゴサーチの採用済み投稿を期間で切り、いいね数の多い順に返す。"""
    adopted = set()
    for path in glob.glob("data/x/egosearch_adopted_*.txt"):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.isdigit():
                    adopted.add(line)

    rows, skipped = [], collections.Counter()
    seen_ids = set()
    by_norm = collections.defaultdict(set)  # 正規化本文 -> 投稿者の集合

    for path in glob.glob("work/x_fetch/egosearch_triage_*_final.jsonl"):
        for tweet in load_jsonl(path):
            tid = str(tweet.get("id", ""))
            if tid not in adopted or tid in seen_ids:
                continue
            dt = in_period(tweet, since, until)
            if dt is None:
                continue
            handle = (tweet.get("author") or {}).get("userName", "")
            if handle in EXCLUDE_HANDLES:
                skipped["オーナー本人"] += 1
                continue
            seen_ids.add(tid)
            by_norm[normalize(tweet.get("text") or "")].add(handle)
            rows.append((dt, tweet))

    # 「文章ガチャ」（9/3 公開）の生成文は同じ文面が複数アカウントに現れる。
    # 個々のファンの生の言葉として引用できないので落とす（data/x/..._reactions.md の判断に合わせる）。
    kept = []
    for dt, tweet in rows:
        norm = normalize(tweet.get("text") or "")
        if len(norm) >= 15 and len(by_norm[norm]) >= 2:
            skipped["定型文（複数アカウントで同一文面）"] += 1
            continue
        kept.append((dt, tweet))

    kept.sort(key=lambda r: r[1].get("likeCount", 0), reverse=True)
    return kept[:limit], skipped, len(seen_ids)


def main():
    p = argparse.ArgumentParser(description="posfie まとめ用の素材データを切り出す")
    p.add_argument("--since", required=True, help="開始日 YYYY-MM-DD（この日を含む）")
    p.add_argument("--until", required=True, help="終了日 YYYY-MM-DD（この日を含む）")
    p.add_argument("--reactions", type=int, default=60,
                   help="現場の反応の候補数（いいね数の多い順・既定60）")
    p.add_argument("--include-replies", action="store_true",
                   help="メンバーのリプライも含める（既定は除外）")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    since = datetime.strptime(args.since, "%Y-%m-%d").date()
    until = datetime.strptime(args.until, "%Y-%m-%d").date()

    accounts, acc_skipped = collect_accounts(since, until, args.include_replies)
    reactions, rea_skipped, rea_total = collect_reactions(since, until, args.reactions)

    out_path = args.out or os.path.join(
        "work/posfie", f"{args.since}_{args.until}_素材データ.md")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(f"# posfie 素材データ {args.since} 〜 {args.until}\n\n")
        f.write(
            f"公式・メンバー {len(accounts)} 件（除外: "
            + "／".join(f"{k} {v}件" for k, v in acc_skipped.items())
            + f"）／現場の反応 候補 {len(reactions)} 件（採用済み {rea_total} 件から、"
            + "／".join(f"{k} {v}件" for k, v in rea_skipped.items())
            + " を除いていいね順）\n\n"
            "**この一覧から貼るポストを選ぶ。URL は取得データそのままなので組み立て直さない。**\n\n"
        )

        f.write("## 公式・メンバー（時系列）\n\n")
        current_day = None
        for dt, label, tweet in accounts:
            if dt.date() != current_day:
                current_day = dt.date()
                weekday = "月火水木金土日"[dt.weekday()]
                f.write(f"\n### {dt:%m/%d}（{weekday}）\n\n")
            f.write(format_tweet(tweet, dt, label))

        f.write("\n## 現場の反応（いいね順・候補）\n\n")
        for dt, tweet in reactions:
            f.write(format_tweet(tweet, dt))

    print(f"公式・メンバー: {len(accounts)} 件  除外: {dict(acc_skipped)}")
    print(f"現場の反応    : {len(reactions)} 件（採用済み {rea_total} 件から）  除外: {dict(rea_skipped)}")
    print(f"出力          : {out_path}")


if __name__ == "__main__":
    main()
