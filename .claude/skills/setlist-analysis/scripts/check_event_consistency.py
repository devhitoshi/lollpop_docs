"""公演データの整合性チェック。

`events/data_event.csv` を次の観点で点検し、人が判断すべき候補を列挙する（自動では直さない）。

1. セトリ項目のうち `songs/楽曲一覧.md` に名寄せできないもの（集計から黙って落ちている曲）
2. 同じ日付・イベント名・会場の重複行、日付の書式エラー
3. 公式Xのライブ後投稿（`work/x_fetch/lollipop_1116.jsonl`）にセトリらしき投稿があるのに、
   CSV に該当日の公演が無い、または投稿数より行数が少ない日（＝取りこぼしの疑い）
4. 逆に、取得済み期間内の CSV 行で、公式のセトリ投稿が見つからないもの（出典の再確認用）

3・4 は取得済みの投稿データがあるときだけ行う（無ければスキップして、その旨を出す）。
"""
import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, script_dir)
from song_names import load_canonical_songs, normalize_song_name, is_non_song_item, split_setlist  # noqa: E402

JST = timezone(timedelta(hours=9))
EVENT_CSV = 'events/data_event.csv'
DEFAULT_TWEETS = 'work/x_fetch/lollipop_1116.jsonl'


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--tweets', default=DEFAULT_TWEETS, help='公式アカウントの取得済みJSONL（既定: %(default)s）')
    p.add_argument('--since', help='突き合わせの開始日 YYYY-MM-DD（省略時は投稿データの範囲）')
    p.add_argument('--until', help='突き合わせの終了日 YYYY-MM-DD（この日を含む）')
    p.add_argument('--quiet', action='store_true', help='問題があるものだけを短く出す（hook 用）')
    return p.parse_args()


# ---------- CSV 側 ----------

def load_events():
    rows = []
    with open(EVENT_CSV, 'r', encoding='utf-8') as f:
        for i, row in enumerate(csv.DictReader(f), start=2):
            row['_line'] = i
            rows.append(row)
    return rows


NON_SONG_WORDS = re.compile(
    r'(映像|写真撮影|カバー|画像参照|セトリ投稿なし|企画|ソロコーナー|シャッフル|カウン[トド]ダウン|ラジオ体操|クイズ)'
)
LEADING_DECORATION = re.compile(r'^[\d\s\.．]*|[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B50\uFE0F\u200D]+')


def looks_like_non_song(item):
    """番号や絵文字を剥がしたうえで、SE/MC/企画/記号だけ、と判断できる項目なら True。

    is_non_song_item() は集計側と同じ判定（行頭が SE/MC）。ここでは「01.SE」「06 mc」のように
    番号付きの SE/MC や、絵文字だけの区切り行も除外して、本当に曲名らしいものだけを残す。
    """
    core = LEADING_DECORATION.sub('', item).strip()
    core = re.sub(r'^[～〜~\-－]+|[～〜~\-－]+$', '', core).strip()
    if not core:
        return True
    if re.match(r'^(新?se|mc)(\b|[(（])', core, re.I):
        return True
    if NON_SONG_WORDS.search(item):
        return True
    return False


def check_songs(rows, canonical, since=None):
    """名寄せできないセトリ項目を {項目: [日付, ...]} で返す。since 以降の行だけに絞れる。"""
    unmatched = defaultdict(list)
    for row in rows:
        if since and (row.get('date') or '') < since:
            continue
        setlist = row.get('setlist') or ''
        if not setlist or 'セトリ投稿確認' in setlist:
            continue
        for items in split_setlist(setlist):
            for item in items:
                if is_non_song_item(item) or looks_like_non_song(item):
                    continue
                if normalize_song_name(item, canonical) is None:
                    unmatched[item].append(row['date'])
    return unmatched


def check_rows(rows):
    bad_dates = [r for r in rows if not re.match(r'^\d{4}-\d{2}-\d{2}$', r.get('date') or '')]
    # 日付・イベント名・会場・セトリがすべて同じなら重複。セトリが違えば同名の1部/2部なので正常
    keys = Counter((r['date'], r['event'], r['venue'], r.get('setlist') or '') for r in rows)
    dupes = [((d, e, v), n) for (d, e, v, _), n in keys.items() if n > 1]
    unordered = []
    prev = ''
    for r in rows:
        if r['date'] < prev:
            unordered.append(r)
        prev = max(prev, r['date'])
    return bad_dates, dupes, unordered


# ---------- 公式投稿側 ----------

def tweet_text(t):
    return t.get('text') or t.get('full_text') or ''


def tweet_url(t):
    url = t.get('url') or t.get('twitterUrl')
    if url:
        return url
    for key in ('id', 'id_str', 'tweet_id', 'rest_id'):
        if t.get(key):
            return f"https://x.com/lollipop_1116/status/{t[key]}"
    return ''


def tweet_jst_date(t):
    """createdAt（UTC）を JST の日付に直す。深夜の投稿が前日扱いにならないようにするため。"""
    created = t.get('createdAt') or t.get('created_at') or ''
    for fmt in ('%a %b %d %H:%M:%S %z %Y', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S%z'):
        try:
            return datetime.strptime(created, fmt).astimezone(JST).date()
        except ValueError:
            continue
    m = re.search(r'(\d{4})-(\d{2})-(\d{2})', created)
    if m:
        return datetime(int(m[1]), int(m[2]), int(m[3])).date()
    return None


SETLIST_HINT = re.compile(r'(セトリ|setlist|set\s*list)', re.I)
NUMBERED_LINE = re.compile(r'^\s*(SE|M\d|0?\d{1,2})[\s\.．:：、)）]', re.M)


ANNOUNCE_HINT = re.compile(r'ライブ情報|出演情報|出演決定|チケット|予約|OPEN|START', re.I)


def looks_like_setlist(text):
    """ライブ後のセトリ投稿らしさ。「SE」「01 曲名」形式の行が3つ以上、または「セトリ」の語。

    告知（ライブ情報・チケット・OPEN/START）は、番号付きの出演順や「セトリ」の語を含んでも対象外。
    """
    if ANNOUNCE_HINT.search(text) and not re.search(r'ありがとう|お疲れ|楽しかった|セトリ|setlist', text, re.I):
        return False
    if SETLIST_HINT.search(text):
        return True
    return len(NUMBERED_LINE.findall(text)) >= 3


DATE_IN_TEXT = re.compile(r'(?<!\d)(\d{1,2})[/／月](\d{1,2})(?:日)?(?!\d)')


def dates_mentioned(text, year):
    """本文中の 8/29・8月29日 表記を date に。年は投稿日の年で補う。"""
    found = set()
    for m in DATE_IN_TEXT.finditer(text):
        mo, d = int(m[1]), int(m[2])
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                found.add(datetime(year, mo, d).date())
            except ValueError:
                pass
    return found


def load_setlist_posts(path):
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
            text = tweet_text(t)
            if not looks_like_setlist(text):
                continue
            posted = tweet_jst_date(t)
            if posted is None:
                continue
            posts.append({'date': posted, 'text': text, 'url': tweet_url(t)})
    return posts


def match_posts(posts, rows, since, until):
    """各セトリ投稿を CSV の日付と突き合わせる。"""
    rows_by_date = defaultdict(list)
    for r in rows:
        rows_by_date[r['date']].append(r)

    missing = []          # 投稿はあるが CSV に無い
    matched_dates = Counter()
    for p in posts:
        posted = p['date']
        # 本文に過去の日付が1つだけ書かれていればそれを公演日とみなす（「8/29 ありがとうございました」）。
        # 無ければ投稿日の当日か前日（深夜投稿）。未来の日付は次回告知なので使わない。
        mentioned = sorted(d for d in dates_mentioned(p['text'], posted.year) if d <= posted)
        primary = mentioned[0] if len(mentioned) == 1 else None
        candidates = ([primary] if primary else []) + [posted, posted - timedelta(days=1)]
        candidates = [c for c in candidates if (not since or c >= since) and (not until or c <= until)]
        if not candidates:
            continue
        if primary and primary in candidates and not rows_by_date.get(primary.isoformat()):
            p['note'] = f"本文に {primary.month}/{primary.day} とあるが、その日の行が無い"
            missing.append(p)
            continue
        hit = next((c for c in candidates if rows_by_date.get(c.isoformat())), None)
        if hit:
            matched_dates[hit.isoformat()] += 1
        else:
            missing.append(p)

    # 投稿数 > 行数 の日（同日2公演のうち片方だけ入っている疑い）
    more_posts = []
    for d, n in matched_dates.items():
        if n > len(rows_by_date[d]):
            more_posts.append((d, n, len(rows_by_date[d])))

    # 期間内で、セトリ投稿が1本も紐づかなかった CSV 行
    unsourced = []
    if since and until:
        for r in rows:
            d = r['date']
            if since.isoformat() <= d <= until.isoformat() and matched_dates.get(d, 0) == 0:
                unsourced.append(r)
    return missing, more_posts, unsourced


def first_line(text, n=60):
    line = next((l.strip() for l in text.splitlines() if l.strip()), '')
    return line[:n]


def main():
    args = parse_args()
    canonical = load_canonical_songs()
    rows = load_events()
    problems = 0

    # 1. 名寄せ
    recent_since = None
    if args.quiet and rows:
        # hook から呼ぶときは、追記したばかりの行に集中させる（過去のカバー曲まで毎回並べない）
        latest = max((r['date'] for r in rows if re.match(r'^\d{4}-\d{2}-\d{2}$', r['date'] or '')), default=None)
        if latest:
            recent_since = (datetime.strptime(latest, '%Y-%m-%d') - timedelta(days=60)).strftime('%Y-%m-%d')
    unmatched = check_songs(rows, canonical, since=recent_since)
    if unmatched:
        problems += len(unmatched)
        scope = f"（{recent_since} 以降の行）" if recent_since else ""
        print(f"UNMATCHED_SONGS: {len(unmatched)} 種類{scope} 楽曲一覧に名寄せできず集計から落ちている項目。"
              "カバー曲・ソロ曲なら正常。オリジナル曲なら songs/楽曲一覧.md に追加するか名寄せルールを足す")
        for item, dates in sorted(unmatched.items(), key=lambda x: -len(x[1])):
            sample = ', '.join(sorted(set(dates))[:3])
            print(f"  - 「{item}」 ×{len(dates)}（例: {sample}）")
    elif not args.quiet:
        print("UNMATCHED_SONGS: なし")

    # 2. 行の健全性
    bad_dates, dupes, unordered = check_rows(rows)
    if bad_dates or dupes or unordered:
        problems += len(bad_dates) + len(dupes) + len(unordered)
        print("ROW_ISSUES:")
        for r in bad_dates:
            print(f"  - {r['_line']}行目: 日付の書式が YYYY-MM-DD でない → 「{r['date']}」")
        for (d, e, v), n in dupes:
            print(f"  - 重複 ×{n}: {d} {e} / {v}")
        for r in unordered:
            print(f"  - {r['_line']}行目: 日付が前の行より古い（{r['date']}）。並び順を確認")
    elif not args.quiet:
        print("ROW_ISSUES: なし")

    # 3・4. 公式投稿との突き合わせ
    if not os.path.exists(args.tweets):
        if not args.quiet:
            print(f"POST_CHECK: スキップ（{args.tweets} が無い。x-account-fetch で公式投稿を取得すると突き合わせできる）")
    else:
        posts = load_setlist_posts(args.tweets)
        since = datetime.strptime(args.since, '%Y-%m-%d').date() if args.since else (min(p['date'] for p in posts) if posts else None)
        until = datetime.strptime(args.until, '%Y-%m-%d').date() if args.until else (max(p['date'] for p in posts) if posts else None)
        missing, more_posts, unsourced = match_posts(posts, rows, since, until)
        if not args.quiet:
            print(f"POST_CHECK: セトリらしき公式投稿 {len(posts)} 本（{since} 〜 {until}）")
        if missing:
            problems += len(missing)
            print(f"MISSING_EVENTS: {len(missing)} 本（セトリ投稿があるのに CSV に該当日の公演が無い）")
            for p in missing:
                note = f"（{p['note']}）" if p.get('note') else ''
                print(f"  - 投稿日 {p['date']}{note}: {first_line(p['text'])}\n    {p['url']}")
        elif not args.quiet:
            print("MISSING_EVENTS: なし")
        if more_posts:
            problems += len(more_posts)
            print("MORE_POSTS_THAN_ROWS:（同日の投稿数 > CSV 行数。2公演あった日の片方が抜けていないか確認）")
            for d, n, k in more_posts:
                print(f"  - {d}: 投稿 {n} 本 / CSV {k} 行")
        if unsourced and not args.quiet:
            print(f"UNSOURCED_ROWS: {len(unsourced)} 行（期間内で公式のセトリ投稿が紐づかなかった行。出典の再確認用）")
            for r in unsourced:
                print(f"  - {r['date']} {r['event']} / {r['venue']}")

    if args.quiet and problems == 0:
        return
    print(f"CONSISTENCY: {'問題候補 ' + str(problems) + ' 件' if problems else '問題なし'}")


if __name__ == '__main__':
    main()
