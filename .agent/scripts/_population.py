"""出演イベント一覧（母集団）の読み込み。

TimeTree のエクスポートや既存 CSV を、共通形式 {title, start_at, venue} に正規化する。
prepare_collect.py と update_timetree.py から使う。
"""
import csv
import json
import os
import re
import sys
from datetime import date

VENUE_UNKNOWN = '（会場未記載）'


def norm_key(text):
    """重複判定用のキー。表記そのものは書き換えない（`!` の数や `☆`/`★` は保持）。"""
    return re.sub(r'\s+', '', (text or '')).casefold()


def parse_date(value):
    """よくある表記から YYYY-MM-DD を取り出す。取れなければ None。"""
    if not value:
        return None
    value = str(value).strip()
    m = re.search(r'(\d{4})[-/年](\d{1,2})[-/月](\d{1,2})', value)
    if m:
        try:
            return date(*(int(g) for g in m.groups())).isoformat()
        except ValueError:
            return None
    m = re.match(r'^(\d{4})(\d{2})(\d{2})', value)
    if m:
        try:
            return date(*(int(g) for g in m.groups())).isoformat()
        except ValueError:
            return None
    return None


def norm_event(title, start_at, venue):
    venue = (venue or '').strip()
    if venue == VENUE_UNKNOWN:
        venue = ''
    return {'title': (title or '').strip(), 'start_at': start_at, 'venue': venue or None}


def _pick(row, keys):
    for k in keys:
        for actual in row:
            if actual and actual.strip().lower() == k:
                return row[actual]
    return None


TITLE_KEYS = ['title', 'event', 'summary', 'name']
DATE_KEYS = ['start_at', 'date', 'start', 'dtstart']
VENUE_KEYS = ['venue', 'location', 'place']


def load_population(path):
    """出演イベント一覧を読み込む。.ics / .json / .csv / .tsv に対応。"""
    ext = os.path.splitext(path)[1].lower()
    with open(path, 'r', encoding='utf-8-sig') as f:
        raw = f.read()

    if ext == '.ics':
        events = load_ics(raw)
    elif ext == '.json':
        data = json.loads(raw)
        if isinstance(data, dict):
            data = data.get('events') or data.get('items') or []
        events = []
        for row in data:
            start = parse_date(_pick(row, DATE_KEYS))
            if start:
                events.append(norm_event(_pick(row, TITLE_KEYS), start,
                                         _pick(row, VENUE_KEYS)))
    elif ext in ('.csv', '.tsv'):
        events = []
        delim = '\t' if ext == '.tsv' else ','
        for row in csv.DictReader(raw.splitlines(), delimiter=delim):
            start = parse_date(_pick(row, DATE_KEYS))
            if start:
                events.append(norm_event(_pick(row, TITLE_KEYS), start,
                                         _pick(row, VENUE_KEYS)))
    else:
        sys.exit(f'母集団ファイルの拡張子に対応していません: {ext}（.ics / .json / .csv）')

    events = [e for e in events if e['title']]
    events.sort(key=lambda e: (e['start_at'], e['title']))
    return events


def _ics_unescape(value):
    return (value.replace('\\n', '\n').replace('\\N', '\n')
                 .replace('\\,', ',').replace('\\;', ';').replace('\\\\', '\\'))


def load_ics(raw):
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
                start = parse_date(current.get('dtstart'))
                if start:
                    events.append(norm_event(current.get('summary'), start,
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
