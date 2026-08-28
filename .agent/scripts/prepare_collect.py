"""収集フェーズの準備。

期間を半月刻みに分割し、チャンクごとに Grok へ投げるプロンプトを生成する。
`prompts/x_collect.md` の実測どおり、1回の投入は半月までに抑える。

使い方:
    python3 .agent/scripts/prepare_collect.py --month 2026-08
    python3 .agent/scripts/prepare_collect.py --from 2026-08-01 --to 2026-08-31
    python3 .agent/scripts/prepare_collect.py --week 2026-08-24
    python3 .agent/scripts/prepare_collect.py --month 2026-08 --population timetree.ics
"""
import argparse
import calendar
import csv
import json
import os
import re
import sys
from datetime import date, datetime, timedelta

# Ensure script runs from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../'))
os.chdir(project_root)

X_COLLECT_TEMPLATE = 'prompts/x_collect.md'
EVENT_GET_TEMPLATE = 'prompts/event_get.md'


# --- 期間の分割 ---------------------------------------------------------

def half_month_bounds(d):
    """d を含む半月の (開始日, 終了日) を返す。1〜15日 と 16日〜月末。"""
    if d.day <= 15:
        return date(d.year, d.month, 1), date(d.year, d.month, 15)
    last = calendar.monthrange(d.year, d.month)[1]
    return date(d.year, d.month, 16), date(d.year, d.month, last)


def split_period(start, end, max_days):
    """期間を半月境界で分割する。

    - 期間全体が max_days 以内なら分割しない（週次はここで1チャンクになる）
    - それを超える場合のみ半月境界で切り、なお長いチャンクは均等に再分割する
    """
    if (end - start).days + 1 <= max_days:
        return [(start, end)]

    chunks = []
    cursor = start
    while cursor <= end:
        _, h_end = half_month_bounds(cursor)
        chunk_end = min(h_end, end)
        chunks.append((cursor, chunk_end))
        cursor = chunk_end + timedelta(days=1)

    result = []
    for c_start, c_end in chunks:
        span = (c_end - c_start).days + 1
        if span <= max_days:
            result.append((c_start, c_end))
            continue
        parts = -(-span // max_days)  # 切り上げ
        size = -(-span // parts)
        sub = c_start
        while sub <= c_end:
            sub_end = min(sub + timedelta(days=size - 1), c_end)
            result.append((sub, sub_end))
            sub = sub_end + timedelta(days=1)
    return result


def slug(start, end):
    return f"{start:%Y%m%d}-{end:%Y%m%d}"


# --- 母集団（TimeTree 由来）の読み込み ----------------------------------

def _norm_event(title, start_at, venue):
    return {
        'title': (title or '').strip(),
        'start_at': start_at,
        'venue': (venue or '').strip() or None,
    }


def _parse_date(value):
    """よくある表記から YYYY-MM-DD を取り出す。取れなければ None。"""
    if not value:
        return None
    value = str(value).strip()
    m = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', value)
    if m:
        y, mo, d = (int(g) for g in m.groups())
        try:
            return date(y, mo, d).isoformat()
        except ValueError:
            return None
    m = re.match(r'^(\d{4})(\d{2})(\d{2})', value)
    if m:
        try:
            return date(*(int(g) for g in m.groups())).isoformat()
        except ValueError:
            return None
    return None


def _pick(row, keys):
    for k in keys:
        for actual in row:
            if actual and actual.strip().lower() == k:
                return row[actual]
    return None


def load_population(path):
    """TimeTree 由来の出演イベント一覧を読み込み、共通形式に正規化する。

    .ics / .json / .csv に対応。いずれも {title, start_at, venue} に落とす。
    """
    ext = os.path.splitext(path)[1].lower()
    with open(path, 'r', encoding='utf-8-sig') as f:
        raw = f.read()

    events = []
    if ext == '.ics':
        events = _load_ics(raw)
    elif ext == '.json':
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get('events') or data.get('items') or []
        for row in data:
            start = _parse_date(_pick(row, ['start_at', 'date', 'start', 'dtstart']))
            if not start:
                continue
            events.append(_norm_event(
                _pick(row, ['title', 'event', 'summary', 'name']),
                start,
                _pick(row, ['venue', 'location', 'place']),
            ))
    elif ext in ('.csv', '.tsv'):
        delim = '\t' if ext == '.tsv' else ','
        for row in csv.DictReader(raw.splitlines(), delimiter=delim):
            start = _parse_date(_pick(row, ['start_at', 'date', 'start']))
            if not start:
                continue
            events.append(_norm_event(
                _pick(row, ['title', 'event', 'summary', 'name']),
                start,
                _pick(row, ['venue', 'location', 'place']),
            ))
    else:
        sys.exit(f"母集団ファイルの拡張子に対応していません: {ext}（.ics / .json / .csv）")

    events.sort(key=lambda e: (e['start_at'], e['title']))
    return events


def _ics_unescape(value):
    return (value.replace('\\n', '\n').replace('\\N', '\n')
                 .replace('\\,', ',').replace('\\;', ';').replace('\\\\', '\\'))


def _load_ics(raw):
    # 行折り返し（次行が空白始まり）を先に畳む
    lines = []
    for line in raw.replace('\r\n', '\n').replace('\r', '\n').split('\n'):
        if line[:1] in (' ', '\t') and lines:
            lines[-1] += line[1:]
        else:
            lines.append(line)

    events, current = [], None
    for line in lines:
        if line.strip() == 'BEGIN:VEVENT':
            current = {}
            continue
        if line.strip() == 'END:VEVENT':
            if current is not None:
                start = _parse_date(current.get('dtstart'))
                if start:
                    events.append(_norm_event(current.get('summary'), start,
                                              current.get('location')))
            current = None
            continue
        if current is None or ':' not in line:
            continue
        name, value = line.split(':', 1)
        key = name.split(';', 1)[0].strip().lower()
        if key in ('summary', 'location', 'dtstart'):
            current[key] = _ics_unescape(value.strip())
    return events


# --- プロンプト生成 -----------------------------------------------------

def render_x_collect(template, start, end):
    text = template
    text = text.replace('[終了日+1日]', (end + timedelta(days=1)).isoformat())
    text = text.replace('[開始日]', start.isoformat())
    text = text.replace('[終了日]', end.isoformat())
    return text


def render_event_get(template, events):
    payload = json.dumps(events, ensure_ascii=False, indent=2)
    if '[ここにJSONを貼る]' in template:
        return template.replace('[ここにJSONを貼る]', payload)
    return template.rstrip() + '\n\n```json\n' + payload + '\n```\n'


def main():
    p = argparse.ArgumentParser(description='収集プロンプトを半月刻みで生成する')
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument('--month', help='対象月 YYYY-MM')
    g.add_argument('--week', help='対象週に含まれる日 YYYY-MM-DD（月曜起点の7日間）')
    g.add_argument('--from', dest='date_from', help='開始日 YYYY-MM-DD')
    p.add_argument('--to', dest='date_to', help='終了日 YYYY-MM-DD（--from と併用）')
    p.add_argument('--max-days', type=int, default=16,
                   help='1チャンクの上限日数（既定16。半月境界での分割が優先）')
    p.add_argument('--population',
                   help='TimeTree 由来の出演イベント一覧（.ics / .json / .csv）')
    p.add_argument('--outdir', default='work/collect', help='出力先（既定 work/collect）')
    args = p.parse_args()

    if args.month:
        y, m = (int(x) for x in args.month.split('-'))
        start = date(y, m, 1)
        end = date(y, m, calendar.monthrange(y, m)[1])
    elif args.week:
        d = datetime.strptime(args.week, '%Y-%m-%d').date()
        start = d - timedelta(days=d.weekday())
        end = start + timedelta(days=6)
    else:
        if not args.date_to:
            sys.exit('--from を使う場合は --to も指定してください')
        start = datetime.strptime(args.date_from, '%Y-%m-%d').date()
        end = datetime.strptime(args.date_to, '%Y-%m-%d').date()

    if end < start:
        sys.exit('終了日が開始日より前です')
    if args.max_days < 1:
        sys.exit('--max-days は1以上を指定してください')

    if not os.path.exists(X_COLLECT_TEMPLATE):
        sys.exit(f'テンプレートが見つかりません: {X_COLLECT_TEMPLATE}')
    with open(X_COLLECT_TEMPLATE, 'r', encoding='utf-8') as f:
        x_collect = f.read()

    event_get = None
    if args.population:
        if not os.path.exists(EVENT_GET_TEMPLATE):
            sys.exit(f'テンプレートが見つかりません: {EVENT_GET_TEMPLATE}')
        with open(EVENT_GET_TEMPLATE, 'r', encoding='utf-8') as f:
            event_get = f.read()

    population = load_population(args.population) if args.population else None

    chunks = split_period(start, end, args.max_days)
    period_dir = os.path.join(args.outdir, slug(start, end))
    os.makedirs(period_dir, exist_ok=True)

    print(f'対象期間: {start} 〜 {end}（{(end - start).days + 1}日） → {len(chunks)}チャンク')
    if population is not None:
        in_range = [e for e in population
                    if start.isoformat() <= e['start_at'] <= end.isoformat()]
        print(f'母集団: {args.population} から {len(population)}件読み込み'
              f'（うち期間内 {len(in_range)}件）')

    for i, (c_start, c_end) in enumerate(chunks, 1):
        c_dir = os.path.join(period_dir, slug(c_start, c_end))
        os.makedirs(c_dir, exist_ok=True)

        with open(os.path.join(c_dir, 'x_collect.md'), 'w', encoding='utf-8') as f:
            f.write(render_x_collect(x_collect, c_start, c_end))

        meta = {
            'index': i, 'total': len(chunks),
            'from': c_start.isoformat(), 'to': c_end.isoformat(),
            'days': (c_end - c_start).days + 1,
            'period_from': start.isoformat(), 'period_to': end.isoformat(),
        }

        n_events = ''
        if population is not None:
            c_events = [e for e in population
                        if c_start.isoformat() <= e['start_at'] <= c_end.isoformat()]
            meta['population_count'] = len(c_events)
            n_events = f' / 母集団 {len(c_events)}件'
            with open(os.path.join(c_dir, 'population.json'), 'w', encoding='utf-8') as f:
                json.dump(c_events, f, ensure_ascii=False, indent=2)
                f.write('\n')
            with open(os.path.join(c_dir, 'event_get.md'), 'w', encoding='utf-8') as f:
                f.write(render_event_get(event_get, c_events))

        with open(os.path.join(c_dir, 'chunk.json'), 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
            f.write('\n')

        print(f'  [{i}/{len(chunks)}] {c_start} 〜 {c_end}'
              f'（{meta["days"]}日{n_events}） → {c_dir}/')

    print()
    print('次の手順:')
    print('  1. 各チャンクの x_collect.md を Grok（エキスパート・新規チャット）に貼る')
    if population is not None:
        print('     セトリCSVが要るチャンクは event_get.md も別チャットで投げる')
    print('  2. 返ってきた本文を同じディレクトリの response.md として保存する')
    if population is not None:
        print('     event_get.md の返り値（CSV）は response.csv として保存する')
    print(f'  3. python3 .agent/scripts/merge_collect.py --period {slug(start, end)}')


if __name__ == '__main__':
    main()
