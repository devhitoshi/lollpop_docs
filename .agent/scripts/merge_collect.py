"""複数チャンクの収集結果（x_collect.md の出力）を1本に結合する。

Grok は半月ずつしか収集できないため、月刊記事では前半・後半の2つの出力が返る。
これを節ごとにマージし、日付順に並べ直し、出力が途中で切れているチャンクを検出する。

使い方:
    python3 .agent/scripts/merge_collect.py --period 20260801-20260831
    python3 .agent/scripts/merge_collect.py a/response.md b/response.md -o merged.md
"""
import argparse
import glob
import json
import os
import re
import sys

# Ensure script runs from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../'))
os.chdir(project_root)

# prompts/x_collect.md の出力形式に対応。この順で出力する。
SECTIONS = [
    'ライブ・イベント',
    '新曲・初披露',
    'アナウンス・告知',
    'メンバーの投稿',
    '外部の反応',
    '今後の予定',
    '確認できなかった項目',
    '判断に迷った点',
]
# 出力の末尾側にある節。欠けていたら打ち切りを疑う。
TAIL_SECTIONS = {'今後の予定', '確認できなかった項目', '判断に迷った点'}

DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')


def norm_key(text):
    """重複判定用のキー。表記そのものは絶対に書き換えない（キーだけ正規化）。"""
    return re.sub(r'\s+', ' ', text.strip()).casefold()


def first_date(text):
    m = DATE_RE.search(text)
    return m.group(1) if m else None


def parse_chunk(path):
    """収集データ Markdown を {節名: 本文行リスト} に分解する。"""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.read().replace('\r\n', '\n').split('\n')

    sections, order, current = {}, [], None
    title = None
    for line in lines:
        if line.startswith('# ') and title is None and current is None:
            title = line[2:].strip()
            continue
        m = re.match(r'^##\s+(.+?)\s*$', line)
        if m and not line.startswith('###'):
            current = m.group(1)
            if current not in sections:
                sections[current] = []
                order.append(current)
            continue
        if current is not None:
            sections[current].append(line)

    return {'path': path, 'title': title, 'sections': sections, 'order': order}


def split_entries(body):
    """本文を `### ` 見出しごとのブロックに割る。見出し前の行は前文として返す。"""
    preamble, entries, current = [], [], None
    for line in body:
        if line.startswith('### '):
            if current:
                entries.append(current)
            current = {'heading': line, 'lines': []}
        elif current is None:
            preamble.append(line)
        else:
            current['lines'].append(line)
    if current:
        entries.append(current)
    return preamble, entries


def strip_blanks(lines):
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def is_absent(body):
    """節の中身が `なし` だけ（＝該当なし）かどうか。"""
    text = '\n'.join(strip_blanks(list(body))).strip()
    return text in ('なし', '- なし', 'なし。', '')


def merge_entry_section(chunks, name, sort_by_date):
    """`### 見出し` 単位の節をマージする（ライブ・イベント / 新曲・初披露）。"""
    merged, seen, dropped = [], {}, 0
    for chunk in chunks:
        body = chunk['sections'].get(name)
        if body is None or is_absent(body):
            continue
        _, entries = split_entries(body)
        for entry in entries:
            key = norm_key(entry['heading'])
            if key in seen:
                dropped += 1
                continue
            block = [entry['heading']] + strip_blanks(list(entry['lines']))
            seen[key] = True
            merged.append({'date': first_date(entry['heading']), 'block': block})

    if sort_by_date:
        # 日付なしの項目は元の順序のまま末尾へ
        merged.sort(key=lambda e: (e['date'] is None, e['date'] or ''))

    out = []
    for e in merged:
        out.extend(e['block'])
        out.append('')
    return strip_blanks(out), len(merged), dropped


def merge_member_section(chunks, name):
    """メンバーごとの `### 愛称（@handle）` をまとめ、投稿を日付順に並べる。"""
    members, order, dropped = {}, [], 0
    for chunk in chunks:
        body = chunk['sections'].get(name)
        if body is None or is_absent(body):
            continue
        _, entries = split_entries(body)
        for entry in entries:
            key = norm_key(entry['heading'])
            if key not in members:
                members[key] = {'heading': entry['heading'], 'lines': [], 'seen': set()}
                order.append(key)
            bucket = members[key]
            for line in strip_blanks(list(entry['lines'])):
                if not line.strip():
                    continue
                lk = norm_key(line)
                if lk in bucket['seen']:
                    dropped += 1
                    continue
                bucket['seen'].add(lk)
                bucket['lines'].append(line)

    out, total = [], 0
    for key in order:
        bucket = members[key]
        bucket['lines'].sort(key=lambda l: (first_date(l) is None, first_date(l) or ''))
        out.append(bucket['heading'])
        out.extend(bucket['lines'])
        out.append('')
        total += len(bucket['lines'])
    return strip_blanks(out), total, dropped


def merge_bullet_section(chunks, name, sort_by_date):
    """箇条書きの節をマージする（アナウンス・告知 / 外部の反応）。"""
    items, seen, dropped = [], set(), 0
    for chunk in chunks:
        body = chunk['sections'].get(name)
        if body is None or is_absent(body):
            continue
        for line in strip_blanks(list(body)):
            if not line.strip():
                continue
            key = norm_key(line)
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            items.append(line)
    if sort_by_date:
        items.sort(key=lambda l: (first_date(l) is None, first_date(l) or ''))
    return items, len(items), dropped


def merge_note_section(chunks, name):
    """編集メモ（確認できなかった項目 / 判断に迷った点）はチャンク別に残す。

    どのチャンクで取りこぼしたのかが分からなくなると追跡できないため、
    まとめずにチャンク見出しをつけて並べる。
    """
    out, total = [], 0
    labelled = len(chunks) > 1
    for chunk in chunks:
        body = chunk['sections'].get(name)
        if body is None:
            continue
        content = strip_blanks(list(body))
        if is_absent(content):
            continue
        if labelled:
            out.append(f"**{chunk['label']}**")
            out.append('')
        out.extend(content)
        out.append('')
        total += sum(1 for l in content if l.strip().startswith('-'))
    return strip_blanks(out), total, 0


def merge_table_section(chunks, name, period_end):
    """`今後の予定` の表をマージする。行を日付順に並べ、期間内に入った行を報告する。"""
    header, rows, seen, dropped = None, [], set(), 0
    for chunk in chunks:
        body = chunk['sections'].get(name)
        if body is None or is_absent(body):
            continue
        for line in strip_blanks(list(body)):
            stripped = line.strip()
            if not stripped:
                continue
            if not stripped.startswith('|'):
                # 表以外の記述（注記など）は行としてそのまま残す
                key = norm_key(line)
                if key not in seen:
                    seen.add(key)
                    rows.append({'date': first_date(line), 'line': line, 'table': False})
                continue
            if re.fullmatch(r'\|[\s:\-|]+\|', stripped):
                continue  # 区切り行
            if header is None and not DATE_RE.search(stripped):
                header = line  # 最初に出てきた見出し行
                continue
            if not DATE_RE.search(stripped) and norm_key(stripped) == norm_key(header or ''):
                continue  # 2つめ以降のチャンクの見出し行
            key = norm_key(stripped)
            if key in seen:
                dropped += 1
                continue
            seen.add(key)
            rows.append({'date': first_date(line), 'line': line, 'table': True})

    rows.sort(key=lambda r: (r['date'] is None, r['date'] or ''))
    stale = [r['line'].strip() for r in rows
             if r['date'] and period_end and r['date'] <= period_end]

    out = []
    if header:
        out.append(header)
        cols = header.count('|') - 1
        out.append('|' + '|'.join(['---'] * max(cols, 1)) + '|')
    out.extend(r['line'] for r in rows)
    return out, len(rows), dropped, stale


def main():
    p = argparse.ArgumentParser(description='収集チャンクを1本に結合する')
    p.add_argument('files', nargs='*', help='結合する response.md（省略時は --period で探す）')
    p.add_argument('--period', help='work/collect 配下の期間ディレクトリ名 YYYYMMDD-YYYYMMDD')
    p.add_argument('--collect-dir', default='work/collect')
    p.add_argument('-o', '--output', help='出力先（既定 <期間ディレクトリ>/merged.md）')
    args = p.parse_args()

    period_dir = None
    files = list(args.files)
    if args.period:
        period_dir = os.path.join(args.collect_dir, args.period)
        if not os.path.isdir(period_dir):
            sys.exit(f'期間ディレクトリがありません: {period_dir}')
        found = sorted(glob.glob(os.path.join(period_dir, '*', 'response.md')))
        if not found:
            sys.exit(f'response.md が1つも見つかりません: {period_dir}/*/response.md\n'
                     'Grok の出力を各チャンクの response.md として保存してください。')
        files = found
    if not files:
        sys.exit('結合するファイルを指定するか --period を渡してください')

    chunks = []
    for path in files:
        if not os.path.exists(path):
            sys.exit(f'ファイルがありません: {path}')
        chunk = parse_chunk(path)
        meta_path = os.path.join(os.path.dirname(path), 'chunk.json')
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                chunk['meta'] = json.load(f)
        else:
            chunk['meta'] = {}
        c_from = chunk['meta'].get('from') or first_date(chunk['title'] or '')
        c_to = chunk['meta'].get('to')
        if not c_to and chunk['title']:
            dates = DATE_RE.findall(chunk['title'])
            c_to = dates[-1] if len(dates) > 1 else None
        chunk['from'], chunk['to'] = c_from, c_to
        chunk['label'] = f'{c_from} 〜 {c_to}' if c_from and c_to else os.path.dirname(path)
        chunks.append(chunk)

    chunks.sort(key=lambda c: (c['from'] is None, c['from'] or '', c['path']))

    froms = [c['from'] for c in chunks if c['from']]
    tos = [c['to'] for c in chunks if c['to']]
    period_from = min(froms) if froms else None
    period_to = max(tos) if tos else None

    # --- 打ち切りの検出 ---
    warnings = []
    for chunk in chunks:
        missing = [s for s in SECTIONS if s not in chunk['sections']]
        if missing:
            tail_missing = [s for s in missing if s in TAIL_SECTIONS]
            level = '出力が途中で切れている可能性' if tail_missing else '節が欠けています'
            warnings.append(f"{chunk['path']}: {level} → 不足: {', '.join(missing)}")
        unknown = [s for s in chunk['order'] if s not in SECTIONS]
        if unknown:
            warnings.append(f"{chunk['path']}: 想定外の節: {', '.join(unknown)}")

    # --- 節ごとにマージ ---
    stats, blocks, stale_rows = [], [], []
    for name in SECTIONS:
        if name == 'ライブ・イベント':
            body, count, dropped = merge_entry_section(chunks, name, sort_by_date=True)
            unit = '公演'
        elif name == '新曲・初披露':
            body, count, dropped = merge_entry_section(chunks, name, sort_by_date=False)
            unit = '曲'
        elif name == 'メンバーの投稿':
            body, count, dropped = merge_member_section(chunks, name)
            unit = '投稿'
        elif name in ('アナウンス・告知', '外部の反応'):
            body, count, dropped = merge_bullet_section(chunks, name, sort_by_date=True)
            unit = '件'
        elif name == '今後の予定':
            body, count, dropped, stale_rows = merge_table_section(chunks, name, period_to)
            unit = '行'
        else:
            body, count, dropped = merge_note_section(chunks, name)
            unit = '件'

        blocks.append((name, body if body else ['なし']))
        stats.append((name, count, dropped, unit))

    # 想定外の節は落とさず末尾に回す
    extra = []
    for chunk in chunks:
        for name in chunk['order']:
            if name in SECTIONS:
                continue
            extra.append((f"{name}（{chunk['label']}）",
                          strip_blanks(list(chunk['sections'][name]))))

    period_label = f'{period_from} 〜 {period_to}' if period_from and period_to else '期間不明'
    out = [f'# 収集データ ろりぽっぷ!!!!!!! {period_label}', '']
    out.append('<!-- 自動結合: .agent/scripts/merge_collect.py')
    for chunk in chunks:
        out.append(f'     - {chunk["label"]}: {chunk["path"]}')
    out.append('-->')
    out.append('')
    for name, body in blocks + extra:
        out.append(f'## {name}')
        out.append('')
        out.extend(body)
        out.append('')

    output = args.output
    if not output:
        if period_dir:
            output = os.path.join(period_dir, 'merged.md')
        else:
            output = os.path.join(os.path.dirname(files[0]) or '.', 'merged.md')
    os.makedirs(os.path.dirname(os.path.abspath(output)), exist_ok=True)
    with open(output, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out).rstrip() + '\n')

    print(f'結合: {len(chunks)}チャンク → {output}')
    for chunk in chunks:
        print(f'  - {chunk["label"]}  ({chunk["path"]})')
    print()
    for name, count, dropped, unit in stats:
        note = f'  重複除去 {dropped}' if dropped else ''
        print(f'  {name:12} {count:4}{unit}{note}')

    if stale_rows:
        print()
        print('⚠ 「今後の予定」に、結合後の期間内（〜' + str(period_to) + '）の行があります。')
        print('  前半チャンクの時点では予定だったものです。実施済みなら記事では扱いを変えてください。')
        for line in stale_rows:
            print(f'    {line}')

    if warnings:
        print()
        print('⚠ 確認してください:')
        for w in warnings:
            print(f'    {w}')
        print('  出力が切れている場合は、そのチャンクだけ Grok で取り直してください。')
    else:
        print()
        print('欠けている節はありません。')


if __name__ == '__main__':
    main()
