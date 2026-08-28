"""Grok から受け取った収集データをリポジトリに積み上げ、軸ごとに整理する。

`work/collect/` は作業場所で、確定した受信データは `data/collected/` に原本として残す。
そこから イベント / メンバー / ファンの声 / 話題 の各軸を毎回まるごと組み立て直す。
派生ファイルは常に原本から再生成されるので、途中で差分がずれていくことがない。

使い方:
    python3 .agent/scripts/archive_collect.py --period 20260801-20260831   # 取り込み＋再構築
    python3 .agent/scripts/archive_collect.py --rebuild                    # 再構築のみ
"""
import argparse
import csv
import glob
import json
import os
import re
import shutil
import sys
from collections import OrderedDict, defaultdict
from datetime import datetime, timezone

# Ensure script runs from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../'))
os.chdir(project_root)
sys.path.insert(0, script_dir)

from _collect_doc import (  # noqa: E402
    first_date, is_absent, norm_key, parse_chunk, split_entries, strip_blanks,
)

DATA = 'data'
COLLECTED = os.path.join(DATA, 'collected')
EVENTS = os.path.join(DATA, 'events')
MEMBERS = os.path.join(DATA, 'members')
REACTIONS = os.path.join(DATA, 'reactions')
TOPICS = os.path.join(DATA, 'topics')
INDEX = os.path.join(DATA, 'INDEX.md')
GENERATED = [EVENTS, MEMBERS, REACTIONS, TOPICS]

BANNER = ('<!-- このファイルは .agent/scripts/archive_collect.py が生成しています。\n'
          '     直接編集しても次回の再構築で消えます。'
          '直すなら data/collected/ の原本を直してください。 -->')


# --- メンバー表 ---------------------------------------------------------

def load_members():
    """prompts/x_collect.md の収集対象アカウントから handle→本名/愛称 を作る。"""
    members, current = OrderedDict(), 'active'
    path = 'prompts/x_collect.md'
    if not os.path.exists(path):
        return members
    for line in open(path, encoding='utf-8'):
        if line.startswith('**元メンバー'):
            current = 'former'
        elif line.startswith('**現メンバー'):
            current = 'active'
        m = re.match(r'^-\s*`@(\w+)`\s*[—-]\s*(.+?)\s*$', line)
        if not m:
            continue
        handle, rest = m.group(1), m.group(2)
        paren = re.match(r'^(.+?)（(.+?)）\s*$', rest)
        name = paren.group(1).strip() if paren else rest.strip()
        nick = ''
        if paren and '卒業' not in paren.group(2):
            nick = paren.group(2).split('・')[0].strip()
        members[handle] = {'handle': handle, 'name': name, 'nick': nick,
                           'status': current}
    return members


def match_member(heading, members):
    """`### まなてぃー（@mana_lpop）` を メンバー表に突き合わせる。"""
    m = re.search(r'@(\w+)', heading)
    if m and m.group(1) in members:
        return members[m.group(1)]
    text = norm_key(heading)
    for info in members.values():
        for label in (info['name'], info['nick']):
            if label and norm_key(label) in text:
                return info
    return None


# --- ファイル名 ---------------------------------------------------------

def safe_name(text, limit=70):
    """イベント名をファイル名に使える形にする（日本語はそのまま残す）。"""
    name = re.sub(r'[\x00-\x1f\x7f]', '', text or '')
    name = name.replace('/', '／').replace('\\', '＼')
    name = re.sub(r'[<>:"|?*]', '', name)
    name = re.sub(r'\s+', '_', name).strip('._ ')
    if len(name) > limit:
        name = name[:limit].rstrip('._ ')
    return name or 'unnamed'


# --- 原本の読み込み -----------------------------------------------------

def load_collected():
    """data/collected/<期間>/ を古い順に読む。"""
    periods = []
    for d in sorted(glob.glob(os.path.join(COLLECTED, '*'))):
        if not os.path.isdir(d):
            continue
        slug = os.path.basename(d)
        meta_path = os.path.join(d, 'meta.json')
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, encoding='utf-8') as f:
                meta = json.load(f)
        doc_path = os.path.join(d, 'merged.md')
        if not os.path.exists(doc_path):
            found = sorted(glob.glob(os.path.join(d, '*.md')))
            found = [p for p in found if os.path.basename(p) != 'README.md']
            if not found:
                continue
            doc_path = found[0]
        doc = parse_chunk(doc_path)
        periods.append({'slug': slug, 'dir': d, 'meta': meta, 'doc': doc,
                        'doc_path': doc_path,
                        'from': meta.get('from') or slug.split('-')[0],
                        'to': meta.get('to') or slug.split('-')[-1]})
    return periods


def entries_of(doc, section):
    body = doc['sections'].get(section)
    if body is None or is_absent(body):
        return []
    _, entries = split_entries(body)
    return entries


def bullets_of(doc, section):
    body = doc['sections'].get(section)
    if body is None or is_absent(body):
        return []
    return [l for l in strip_blanks(list(body)) if l.strip()]


def load_setlists():
    """data_event.csv を (日付, 正規化イベント名) と 日付 で引けるようにする。"""
    by_key, by_date = {}, defaultdict(list)
    if not os.path.exists('data_event.csv'):
        return by_key, by_date
    with open('data_event.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            by_key[(row['date'], norm_key(row['event']))] = row
            by_date[row['date']].append(row)
    return by_key, by_date


def find_setlist(date, title, by_key, by_date):
    row = by_key.get((date, norm_key(title)))
    if row:
        return row
    same_day = by_date.get(date, [])
    if len(same_day) == 1:
        return same_day[0]
    key = norm_key(title)
    hits = [r for r in same_day if key and (key in norm_key(r['event'])
                                            or norm_key(r['event']) in key)]
    return hits[0] if len(hits) == 1 else None


# --- 各軸の組み立て -----------------------------------------------------

def period_label(p):
    return f"{p['from']} 〜 {p['to']}"


def rel(from_file, to_file):
    return os.path.relpath(to_file, os.path.dirname(from_file)).replace(os.sep, '/')


def build_events(periods, by_key, by_date):
    """イベント単位。1公演＝1ファイル。"""
    events, used = OrderedDict(), {}
    for p in periods:
        for entry in entries_of(p['doc'], 'ライブ・イベント'):
            heading = entry['heading'][4:].strip()
            date = first_date(heading)
            title = re.sub(r'^\[?' + re.escape(date or '') + r'\]?\s*', '',
                           heading).strip() if date else heading
            key = (date or '0000-00-00', norm_key(title))
            if key not in events:
                events[key] = {'date': date, 'title': title, 'blocks': []}
            events[key]['blocks'].append((p, strip_blanks(list(entry['lines']))))

    written = []
    for (date, _), ev in events.items():
        year = (ev['date'] or '未分類')[:4]
        base = safe_name(f"{ev['date'] or '日付不明'}_{ev['title']}")
        path = os.path.join(EVENTS, year, base + '.md')
        n = 2
        while path in used:
            path = os.path.join(EVENTS, year, f'{base}_{n}.md')
            n += 1
        used[path] = True

        out = [f"# {ev['date'] or '日付不明'} {ev['title']}", '', BANNER, '']
        row = find_setlist(ev['date'], ev['title'], by_key, by_date) if ev['date'] else None
        if row:
            out += ['## セトリ（data_event.csv）', '']
            if row['venue']:
                out.append(f"- 会場: {row['venue']}")
            out.append(f"- 公式表記: {row['event']}")
            out += ['', '```', row['setlist'], '```', '']
        for p, lines in ev['blocks']:
            out.append(f"## 収集データ（{period_label(p)}）")
            out.append('')
            out.extend(lines)
            out += ['', f"出典データ: [{p['slug']}]({rel(path, p['doc_path'])})", '']
        written.append((path, '\n'.join(out).rstrip() + '\n', ev))
    return written


def build_members(periods, members):
    """メンバー単位。期間ごとに投稿を並べる。"""
    buckets, unknown = OrderedDict(), OrderedDict()
    for handle, info in members.items():
        buckets[handle] = {'info': info, 'periods': []}
    for p in periods:
        for entry in entries_of(p['doc'], 'メンバーの投稿'):
            info = match_member(entry['heading'], members)
            lines = [l for l in strip_blanks(list(entry['lines'])) if l.strip()]
            if not lines:
                continue
            lines.sort(key=lambda l: (first_date(l) is None, first_date(l) or ''))
            if info:
                buckets[info['handle']]['periods'].append((p, lines))
            else:
                label = entry['heading'][4:].strip()
                unknown.setdefault(label, []).append((p, lines))

    written = []
    for handle, bucket in buckets.items():
        if not bucket['periods']:
            continue
        info = bucket['info']
        path = os.path.join(MEMBERS, safe_name(info['name']) + '.md')
        title = info['name'] + (f"（{info['nick']}）" if info['nick'] else '')
        out = [f'# {title}', '', BANNER, '',
               f"- アカウント: [@{handle}](https://x.com/{handle})"]
        if info['status'] == 'former':
            out.append('- 元メンバー')
        out.append('')
        total = 0
        for p, lines in bucket['periods']:
            out.append(f'## {period_label(p)}')
            out.append('')
            out.extend(lines)
            out += ['', f"出典データ: [{p['slug']}]({rel(path, p['doc_path'])})", '']
            total += len(lines)
        written.append((path, '\n'.join(out).rstrip() + '\n', {'count': total}))

    for label, chunks in unknown.items():
        path = os.path.join(MEMBERS, '_未対応', safe_name(label) + '.md')
        out = [f'# {label}', '', BANNER, '',
               '> メンバー表（`prompts/x_collect.md` の収集対象アカウント）に'
               '突き合わせられませんでした。', '']
        total = 0
        for p, lines in chunks:
            out += [f'## {period_label(p)}', '']
            out.extend(lines)
            out += ['', f"出典データ: [{p['slug']}]({rel(path, p['doc_path'])})", '']
            total += len(lines)
        written.append((path, '\n'.join(out).rstrip() + '\n', {'count': total}))
    return written


def build_monthly(periods, section, outdir, heading):
    """ファンの声・話題を月ごとにまとめる。"""
    months = OrderedDict()
    for p in periods:
        for line in bullets_of(p['doc'], section):
            date = first_date(line)
            month = (date or p['from'])[:7]
            months.setdefault(month, []).append((date, line, p))

    written = []
    for month, items in sorted(months.items()):
        items.sort(key=lambda t: (t[0] is None, t[0] or ''))
        path = os.path.join(outdir, f'{month}.md')
        out = [f'# {heading} {month}', '', BANNER, '']
        seen_periods = []
        for _, line, p in items:
            out.append(line)
            if p['slug'] not in [s['slug'] for s in seen_periods]:
                seen_periods.append(p)
        out.append('')
        out.append('出典データ: ' + ' / '.join(
            f"[{p['slug']}]({rel(path, p['doc_path'])})" for p in seen_periods))
        written.append((path, '\n'.join(out).rstrip() + '\n', {'count': len(items)}))
    return written


def build_topics(periods):
    """新曲・初披露 と アナウンス・告知 を月ごとに1ファイルへ。"""
    months = OrderedDict()
    for p in periods:
        month_default = p['from'][:7]
        for entry in entries_of(p['doc'], '新曲・初披露'):
            lines = strip_blanks(list(entry['lines']))
            date = first_date('\n'.join(lines)) or month_default
            months.setdefault(date[:7], {'新曲・初披露': [], 'アナウンス・告知': []})
            months[date[:7]]['新曲・初披露'].append((entry['heading'], lines, p))
        for line in bullets_of(p['doc'], 'アナウンス・告知'):
            month = (first_date(line) or month_default)[:7]
            months.setdefault(month, {'新曲・初披露': [], 'アナウンス・告知': []})
            months[month]['アナウンス・告知'].append((first_date(line), line, p))

    written = []
    for month, data in sorted(months.items()):
        path = os.path.join(TOPICS, f'{month}.md')
        out = [f'# 新曲・アナウンス {month}', '', BANNER, '']
        sources, count = [], 0
        if data['新曲・初披露']:
            out += ['## 新曲・初披露', '']
            for heading, lines, p in data['新曲・初披露']:
                out.append(heading)
                out.extend(lines)
                out.append('')
                if p not in sources:
                    sources.append(p)
                count += 1
        if data['アナウンス・告知']:
            out += ['## アナウンス・告知', '']
            for _, line, p in sorted(data['アナウンス・告知'],
                                     key=lambda t: (t[0] is None, t[0] or '')):
                out.append(line)
                if p not in sources:
                    sources.append(p)
                count += 1
            out.append('')
        out.append('出典データ: ' + ' / '.join(
            f"[{p['slug']}]({rel(path, p['doc_path'])})" for p in sources))
        written.append((path, '\n'.join(out).rstrip() + '\n', {'count': count}))
    return written


def build_index(periods, events, member_files, reaction_files, topic_files):
    out = ['# 収集データ 索引', '', BANNER, '',
           '`data/collected/` が Grok から受け取った原本、それ以外は'
           ' `.agent/scripts/archive_collect.py` が組み立てた軸別の索引です。', '',
           '## 収集した期間', '',
           '| 期間 | ライブ | メンバー投稿 | 外部の反応 | 原本 |',
           '|---|---|---|---|---|']
    for p in periods:
        lives = len(entries_of(p['doc'], 'ライブ・イベント'))
        posts = sum(len([l for l in strip_blanks(list(e['lines'])) if l.strip()])
                    for e in entries_of(p['doc'], 'メンバーの投稿'))
        reacts = len(bullets_of(p['doc'], '外部の反応'))
        link = rel(INDEX, p['doc_path'])
        out.append(f"| {period_label(p)} | {lives} | {posts} | {reacts} "
                   f"| [{p['slug']}]({link}) |")

    out += ['', '## イベント', '']
    by_year = defaultdict(list)
    for path, _, ev in events:
        by_year[(ev['date'] or '未分類')[:4]].append((ev['date'], ev['title'], path))
    for year in sorted(by_year):
        out += [f'### {year}', '']
        for date, title, path in sorted(by_year[year], key=lambda t: t[0] or ''):
            out.append(f'- {date} [{title}]({rel(INDEX, path)})')
        out.append('')

    if member_files:
        out += ['## メンバー', '']
        for path, _, info in member_files:
            name = os.path.splitext(os.path.basename(path))[0]
            out.append(f"- [{name}]({rel(INDEX, path)})（{info['count']}件）")
        out.append('')
    for label, files in (('## ファンの声', reaction_files), ('## 新曲・アナウンス', topic_files)):
        if not files:
            continue
        out += [label, '']
        for path, _, info in files:
            month = os.path.splitext(os.path.basename(path))[0]
            out.append(f"- [{month}]({rel(INDEX, path)})（{info['count']}件）")
        out.append('')
    return '\n'.join(out).rstrip() + '\n'


# --- 取り込み -----------------------------------------------------------

def ingest(period, collect_dir):
    """work/collect/<期間>/ の受信データを data/collected/<期間>/ に移す。"""
    src = os.path.join(collect_dir, period)
    if not os.path.isdir(src):
        sys.exit(f'作業ディレクトリがありません: {src}')
    responses = sorted(glob.glob(os.path.join(src, '*', 'response.md')))
    merged = os.path.join(src, 'merged.md')
    if not responses:
        sys.exit(f'受信データがありません: {src}/*/response.md')
    if not os.path.exists(merged):
        sys.exit(f'先に結合してください: python3 .agent/scripts/merge_collect.py '
                 f'--period {period}')

    dest = os.path.join(COLLECTED, period)
    os.makedirs(dest, exist_ok=True)
    chunks = []
    for path in responses:
        slug = os.path.basename(os.path.dirname(path))
        shutil.copyfile(path, os.path.join(dest, f'{slug}.md'))
        meta_path = os.path.join(os.path.dirname(path), 'chunk.json')
        info = {'slug': slug}
        if os.path.exists(meta_path):
            with open(meta_path, encoding='utf-8') as f:
                info.update(json.load(f))
        chunks.append(info)
        csv_path = os.path.join(os.path.dirname(path), 'response.csv')
        if os.path.exists(csv_path):
            shutil.copyfile(csv_path, os.path.join(dest, f'{slug}.csv'))
    shutil.copyfile(merged, os.path.join(dest, 'merged.md'))

    froms = [c['from'] for c in chunks if c.get('from')]
    tos = [c['to'] for c in chunks if c.get('to')]
    meta = {
        'period': period,
        'from': min(froms) if froms else period.split('-')[0],
        'to': max(tos) if tos else period.split('-')[-1],
        'chunks': [{'slug': c['slug'], 'from': c.get('from'), 'to': c.get('to')}
                   for c in chunks],
        'collected_by': 'grok',
        'prompt': 'prompts/x_collect.md',
        'archived_at': datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'),
    }
    with open(os.path.join(dest, 'meta.json'), 'w', encoding='utf-8') as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)
        f.write('\n')
    print(f'取り込み: {src} → {dest}（チャンク {len(chunks)}件）')
    return dest


def write_all(files):
    for path, content, _ in files:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)


def main():
    p = argparse.ArgumentParser(description='収集データを積み上げ、軸ごとに整理する')
    p.add_argument('--period', help='取り込む期間（work/collect 配下のディレクトリ名）')
    p.add_argument('--collect-dir', default='work/collect')
    p.add_argument('--rebuild', action='store_true',
                   help='取り込みはせず、data/collected/ から派生ファイルを作り直す')
    args = p.parse_args()

    if not args.period and not args.rebuild:
        p.error('--period か --rebuild のどちらかを指定してください')
    if args.period:
        ingest(args.period, args.collect_dir)

    periods = load_collected()
    if not periods:
        print(f'{COLLECTED}/ に原本がありません。')
        return

    # 派生ファイルは毎回まるごと作り直す（消えた項目が残らないように）
    for d in GENERATED:
        if os.path.isdir(d):
            shutil.rmtree(d)

    members = load_members()
    by_key, by_date = load_setlists()
    events = build_events(periods, by_key, by_date)
    member_files = build_members(periods, members)
    reaction_files = build_monthly(periods, '外部の反応', REACTIONS, 'ファンの声')
    topic_files = build_topics(periods)

    write_all(events)
    write_all(member_files)
    write_all(reaction_files)
    write_all(topic_files)
    os.makedirs(DATA, exist_ok=True)
    with open(INDEX, 'w', encoding='utf-8') as f:
        f.write(build_index(periods, events, member_files, reaction_files, topic_files))

    print(f'原本 {len(periods)}期間 から再構築しました。')
    print(f'  {EVENTS}/     {len(events)}件')
    print(f'  {MEMBERS}/    {len(member_files)}件')
    print(f'  {REACTIONS}/  {len(reaction_files)}件')
    print(f'  {TOPICS}/     {len(topic_files)}件')
    print(f'  {INDEX}')
    unknown = [f for f in member_files if os.sep + '_未対応' + os.sep in f[0]]
    if unknown:
        print()
        print('⚠ メンバー表に突き合わせられなかった見出しがあります:')
        for path, _, _ in unknown:
            print(f'    {path}')
        print('  prompts/x_collect.md の収集対象アカウントを確認してください。')


if __name__ == '__main__':
    main()
