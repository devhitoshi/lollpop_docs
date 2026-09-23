#!/usr/bin/env python3
"""公式のセトリ投稿から events/data_event.csv の空欄を埋め、PR を作るところまでを毎朝やる。

**マージはしない。** 自動で main に入れず、朝に人が PR を見て判断する。公式投稿は自由文なので、
同日2部制のどちらの行か・表記ゆれ・中止や順延の判断は機械では詰め切れないため。

- **同日2公演は全体の3分の1あるので、投稿を行に割り当てて埋める。**手がかりは会場（🍬の行）、
  何公演目か（1️⃣本目・2部）、公演名の類似度。どれを当てるか決めきれない日はその日ごと触らない
- CSV に行が無い／投稿の方が多い／項目を取り出せない／対応する投稿が無く空欄が残った、は
  PR 本文に「自動では触らなかったもの」として並べるだけで触らない
- 作業は origin/main から作るテンポラリのワークツリーで行う。**手元の作業ツリーには触らない**
  （未コミットの変更を巻き込まないため。ローカルが毎日 main と同じとは限らない）
- 未マージの auto/setlist-* が既にあるときは何もしない（PR が積み上がって競合するのを避ける）
- 状態ファイルを持たない。毎回「直近 --days 日の投稿」と CSV の現物を突き合わせて考える
- ログは work/x_fetch/logs/daily_setlist_pr.log

使い方:
    python .claude/skills/setlist-analysis/scripts/daily_setlist_pr.py --dry-run
    python .claude/skills/setlist-analysis/scripts/daily_setlist_pr.py
"""

import argparse
import csv
import difflib
import io
import os
import re
import shutil
import subprocess
import sys
import tempfile
import traceback
from datetime import date, datetime, timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, script_dir)

# 投稿の判定（告知を除く・本文の日付の拾い方）は整合性チェックと同じものを使う。
# ここで作り直すと「片方だけ直して食い違う」が起きるため
from check_event_consistency import (  # noqa: E402
    dates_mentioned, load_setlist_posts, looks_like_non_song,
)
from song_names import (  # noqa: E402
    is_non_song_item, load_canonical_songs, normalize_song_name,
)

EVENT_CSV = 'events/data_event.csv'
RANKING_CSV = 'events/monthly_setlist_ranking.csv'
TWEETS = os.path.join(project_root, 'work', 'x_fetch', 'lollipop_1116.jsonl')
LOG_PATH = os.path.join(project_root, 'work', 'x_fetch', 'logs', 'daily_setlist_pr.log')
BRANCH_PREFIX = 'auto/setlist-'

# セトリの項目らしい行。「SE」「MC」「01 曲名」「アンコール」。
# 1桁の番号は区切り（空白・ドット・コロン）を必須にする。「5月一発目ありがとう」「2本ライブ」のような
# 文を曲と取り違えないため。2桁は「04約束!!!!!!!」と詰めて書かれることがあるので区切り無しも許す
ITEM = re.compile(r'^(?:SE|MC|W?アンコール|ダブルアンコール|'
                  r'(?:\d[\s.．:：]\s*|\d{2}[\s.．:：]?\s*)(?!本|部|曲|月|日|周年|現場|公演)\S)', re.I)
# 「1️⃣本目」「2⃣部」「①本目」。セトリではなく、その日の何公演目かを表す行
MARKER = re.compile(r'^\s*(?:[0-9０-９][️]?[⃣]|[①-⑨]|[0-9]\s*(?:本目|部|現場目))')
PART = re.compile(r'([0-9０-９])[️⃣]?\s*(?:本目|部)')
VENUE = re.compile(r'^\s*🍬\s*(.+)$')
# 会場も公演名も似ていて、これ以上の差がつかないときは割り当てを決めない。
# 2024-11 以降の同日2公演の実データ124行で、0.15 なら間違いゼロ（0.05 まで下げると2行間違えた）
MARGIN = 0.15


class Tee:
    """コンソール（pythonw では無い）とログファイルの両方に書く。daily_fetch.py と同じ。"""

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


def run(cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding='utf-8',
                       errors='replace', env={**os.environ, 'PYTHONIOENCODING': 'utf-8'})
    if check and p.returncode != 0:
        raise RuntimeError("失敗（%d）: %s\n%s\n%s" % (p.returncode, ' '.join(cmd), p.stdout, p.stderr))
    return (p.stdout or '') + (p.stderr or '')


def setlist_items(text):
    """投稿本文からセトリの項目を順番に取り出す。

    最初の項目行から始め、項目でない行（「ありがとうございました」など）が来たら打ち切る。
    項目の間の空行は読み飛ばす（「MC」のあとに空行が入る投稿が多い）。
    冒頭の「1️⃣本目」は公演の区切りなので項目に入れない。
    """
    items, started = [], False
    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if MARKER.match(line):
            if started:
                break    # 1本の投稿に次の公演が続いている（古い形式）。1公演分だけ返す
            continue
        if ITEM.match(line):
            items.append(re.sub(r'\s+', ' ', line))
            started = True
        elif started:
            break
    return items


def venue_of(text):
    """投稿の「🍬 会場名」から会場を取る。どの公演の投稿かを見分ける一番強い手がかり。"""
    for raw in text.splitlines():
        mm = VENUE.match(raw.strip())
        if mm:
            return mm.group(1).strip()
    return ''


def part_of(text):
    """「1️⃣本目」「2部」から何公演目かを取る。同じ会場の1部/2部を見分けるのに使う。"""
    mm = PART.search(text)
    if not mm:
        return None
    return int(mm.group(1).translate(str.maketrans('０１２３４５６７８９', '0123456789')))


def norm(s):
    return re.sub(r'[\s　『』「」【】\[\]()（）!！?？・,、。~〜～〜～\-‐―–—:：]', '', s).lower()


def score(post, row):
    """投稿と CSV の行の近さ。会場の一致が一番強い根拠、次に何公演目か、最後に公演名の類似度。"""
    head = '\n'.join([l for l in post['text'].splitlines() if l.strip()][:5])
    nh, nv, ne = norm(head), norm(row['venue']), norm(row['event'])
    pv = norm(venue_of(post['text']))
    s = 0.0
    if pv and nv and '会場未記載' not in nv:
        if pv == nv:
            s += 3
        elif pv in nv or nv in pv:
            s += 2
        else:
            s += 2 * difflib.SequenceMatcher(None, pv, nv).ratio()
    s += difflib.SequenceMatcher(None, ne, nh).ratio()
    pp, rp = part_of(head), part_of(row['event'])
    if pp and rp:
        s += 3 if pp == rp else -3
    return s


def assign(posts, rows):
    """投稿を CSV の行に割り当てる。1つに決まらない投稿が1つでもあれば None（その日は触らない）。"""
    pairs, used = [], set()
    for p in sorted(posts, key=lambda x: x['url']):
        cand = sorted(((score(p, r), i) for i, r in enumerate(rows) if i not in used), reverse=True)
        if not cand:
            return None
        if len(cand) > 1 and cand[0][0] - cand[1][0] < MARGIN:
            return None
        used.add(cand[0][1])
        pairs.append((p, cand[0][1]))
    return pairs


def parse_line(line):
    """CSV の1行を dict に。行単位で書き換えたいので、ファイル全体は読み直さない。"""
    date, event, venue, setlist = next(csv.reader([line]))
    return {'date': date, 'event': event, 'venue': venue, 'setlist': setlist}


def event_date_of(post):
    """公演日を決める。冒頭の「🗓2026年9月19日(土)」を最優先で読む。

    本文全体から拾うと、次回告知やスタンプラリーの対象日を一緒に拾って決められなくなる
    （実際 9/19 の投稿は本文に 8/26 と 9/19 の両方が出てくる）。セトリ投稿は必ず日付から始まるので、
    先頭2行に過去の日付が1つだけあればそれを採る。無ければ本文全体で判断し、
    複数あって決まらなければ None を返して「要確認」に回す。
    """
    posted = post['date']
    head = '\n'.join([l for l in post['text'].splitlines() if l.strip()][:2])
    in_head = sorted(d for d in dates_mentioned(head, posted.year) if d <= posted)
    if len(in_head) == 1:
        return in_head[0]
    mentioned = sorted(d for d in dates_mentioned(post['text'], posted.year) if d <= posted)
    if len(mentioned) == 1:
        return mentioned[0]
    if len(mentioned) > 1:
        return None
    return posted


def read_lines(path):
    return io.open(path, encoding='utf-8').read().split('\n')


def unknown_songs(items, canonical):
    """楽曲一覧に名寄せできない項目。ソロ・カバーなら正常なので、止めずに PR 本文へ書くだけ。"""
    out = []
    for it in items:
        if is_non_song_item(it) or looks_like_non_song(it):
            continue
        if normalize_song_name(it, canonical) is None:
            out.append(it)
    return out


def fill_row(lines, day, event, items):
    """その日の、公演名が一致してセトリ列が空の行を埋める。埋めた行番号か None。

    行の並びで指すと、上流で行が足されたときにずれる。公演名で指し直す。
    """
    for i, l in enumerate(lines):
        if not l.startswith(day + ',') or not l.endswith(',""'):
            continue
        if parse_line(l)['event'] == event:
            lines[i] = l[:-2] + '"%s"' % ';'.join(items)
            return i
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--days', type=int, default=7, help='何日前までの投稿を見るか（既定: %(default)s）')
    ap.add_argument('--dry-run', action='store_true', help='CSV も git も触らず、何をするかだけ出す')
    ap.add_argument('--repo', default='devhitoshi/lollpop_docs', help='PR を作るリポジトリ')
    args = ap.parse_args()

    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    log = open(LOG_PATH, 'a', encoding='utf-8')
    sys.stdout = sys.stderr = Tee(sys.__stdout__, log)
    print("\n===== %s daily_setlist_pr =====" % datetime.now().isoformat(timespec='seconds'))

    if not os.path.exists(TWEETS):
        print("公式の取得データが無い（%s）。x-account-fetch を先に回す" % TWEETS)
        return 1

    since = date.today() - timedelta(days=args.days)
    posts = [p for p in load_setlist_posts(TWEETS) if p['date'] >= since]
    print("直近 %d 日のセトリ投稿: %d 本" % (args.days, len(posts)))
    if not posts:
        print("対象なし。終わる")
        return 0

    by_date, review = {}, []
    for p in posts:
        d = event_date_of(p)
        if d is None:
            review.append(("本文の日付が複数あって公演日を決められない", p['url']))
            continue
        by_date.setdefault(d.isoformat(), []).append(p)

    lines = read_lines(EVENT_CSV)
    canonical = load_canonical_songs()
    fills = []
    for day, ps in sorted(by_date.items()):
        rows = [parse_line(l) for l in lines if l.startswith(day + ',')]
        if not rows:
            review.append(("%s: CSV にこの日の行が無い" % day, ps[0]['url']))
            continue
        if not any(not r['setlist'] for r in rows):
            continue  # もう埋まっている。毎日見に来るので普通はここ
        if len(ps) > len(rows):
            review.append(("%s: 投稿 %d 本に対して行が %d 行しかない" % (day, len(ps), len(rows)),
                           ps[0]['url']))
            continue
        # 同日2公演は珍しくない（全体の3分の1）。会場・何公演目か・公演名で投稿を行に割り当てる
        pairs = assign(ps, rows)
        if pairs is None:
            review.append(("%s: 投稿 %d 本をどの行に当てるか決められない" % (day, len(ps)), ps[0]['url']))
            continue
        matched = set()
        for p, k in pairs:
            matched.add(k)
            if rows[k]['setlist']:
                continue  # その公演はもう入っている
            items = setlist_items(p['text'])
            if len(items) < 2:
                review.append(("%s: セトリの項目を取り出せなかった" % day, p['url']))
                continue
            fills.append({'date': day, 'event': rows[k]['event'], 'url': p['url'],
                          'items': items, 'unknown': unknown_songs(items, canonical)})
        for k, r in enumerate(rows):
            if not r['setlist'] and k not in matched:
                review.append(("%s「%s」: 対応する投稿が無く空欄のまま" % (day, r['event'][:40]), ''))

    for f in fills:
        extra = ("／名寄せできない: " + '、'.join(f['unknown'])) if f['unknown'] else ''
        print("埋める %s「%s」: %d 項目%s" % (f['date'], f['event'][:30], len(f['items']), extra))
    for r in review:
        print("要確認 %s" % r[0])
    if not fills:
        print("埋める行なし。PR は作らない")
        return 0
    if args.dry_run:
        print("--dry-run なのでここまで")
        return 0

    # ---- ここから git。手元の作業ツリーを汚さないよう、origin/main から一時ワークツリーを作る ----
    if not shutil.which('gh'):
        print("gh が PATH に無い。PR を作れないので中断する（CSV は書き換えていない）")
        return 1
    run(['git', 'fetch', 'origin', 'main'], cwd=project_root)
    open_prs = run(['gh', 'pr', 'list', '-R', args.repo, '--state', 'open',
                    '--json', 'headRefName', '-q', '.[].headRefName'], cwd=project_root)
    if any(b.startswith(BRANCH_PREFIX) for b in open_prs.split()):
        print("未マージの %s* が残っている。積み上げないので今日は何もしない" % BRANCH_PREFIX)
        return 0

    branch = BRANCH_PREFIX + date.today().strftime('%Y%m%d')
    wt = tempfile.mkdtemp(prefix='lollpop_setlist_')
    try:
        run(['git', 'worktree', 'add', '--detach', wt, 'origin/main'], cwd=project_root)
        # CSV は origin/main の現物に対して開け直す（手元が古い可能性があるため）
        wt_csv = os.path.join(wt, EVENT_CSV)
        wt_lines = read_lines(wt_csv)
        applied = []
        for f in fills:
            if fill_row(wt_lines, f['date'], f['event'], f['items']) is None:
                print("skip %s「%s」: origin/main 側に空欄の行が無い。先に誰かが入れた可能性"
                      % (f['date'], f['event'][:30]))
                continue
            applied.append(f)
        if not applied:
            print("origin/main 側には埋める行が無かった。PR は作らない")
            return 0
        io.open(wt_csv, 'w', encoding='utf-8', newline='').write('\n'.join(wt_lines))

        months = sorted({f['date'][:7] for f in applied})
        sl = os.path.join(wt, '.claude', 'skills', 'setlist-analysis', 'scripts')
        run([sys.executable, os.path.join(sl, 'analyze_monthly_setlist.py'), '--months', ','.join(months)], cwd=wt)
        checks = run([sys.executable, os.path.join(sl, 'check_missing_months.py')], cwd=wt)
        checks += run([sys.executable, os.path.join(sl, 'check_event_consistency.py'),
                       '--tweets', TWEETS, '--quiet'], cwd=wt, check=False)

        days = '・'.join(sorted({f['date'] for f in applied}))
        body = ["公式X（@lollipop_1116）のセトリ投稿から、`events/data_event.csv` の空欄を埋めた。",
                "**毎朝のタスクスケジューラが自動で作った PR。中身を人が確認してからマージする。**",
                "", "## 埋めた公演", ""]
        for f in applied:
            body.append("- **%s「%s」**（%d 項目） %s"
                        % (f['date'], f['event'], len(f['items']), f['url']))
            body.append("  - `%s`" % ';'.join(f['items']))
            if f['unknown']:
                body.append("  - ⚠️ 楽曲一覧に名寄せできない項目: %s"
                            "（ソロ・カバーなら正常。オリジナルなら `songs/楽曲一覧.md` に足す）"
                            % '、'.join(f['unknown']))
        body += ["", "## 自動では触らなかったもの", ""]
        body += [("- %s %s" % r) for r in review] if review else ["なし"]
        body += ["", "## チェック結果", "", "```", checks.strip(), "```", "",
                 "## 判断待ち", "",
                 "- この内容でよければマージする。違っていれば直してからマージする",
                 "- 「自動では触らなかったもの」の公演は、手で行を足すか埋める必要がある"]

        run(['git', 'switch', '-c', branch], cwd=wt)
        run(['git', 'add', EVENT_CSV, RANKING_CSV], cwd=wt)
        if not run(['git', 'diff', '--cached', '--name-only'], cwd=wt).strip():
            # 埋めた内容が origin/main と同じだった（先に人が同じ内容を入れていた等）。空コミットは作らない
            print("差分が無い。PR は作らない")
            return 0
        run(['git', 'commit', '-m', "%s のセトリを公式投稿から取り込む\n\n"
             "毎朝の自動実行（daily_setlist_pr.py）が作ったコミット。その日のセトリ列が空の行と\n"
             "公式のセトリ投稿が1対1だったものだけを埋めている。" % days], cwd=wt)
        run(['git', 'push', '-u', 'origin', branch], cwd=wt)
        out = run(['gh', 'pr', 'create', '-R', args.repo, '--base', 'main', '--head', branch,
                   '--title', "[自動] %s のセトリを取り込む" % days,
                   '--body', '\n'.join(body)], cwd=wt)
        print(out.strip())
        print("PR を作った。マージはしない")
        return 0
    finally:
        run(['git', 'worktree', 'remove', '--force', wt], cwd=project_root, check=False)


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception:  # noqa: BLE001  タスクスケジューラから呼ばれるので、落ちてもログに残す
        traceback.print_exc()
        sys.exit(1)
