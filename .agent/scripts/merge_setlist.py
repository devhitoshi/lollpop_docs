"""event_get.md の出力（CSV）を data_event.csv にマージする。

半月刻みで収集すると CSV が複数に分かれるため、まとめて取り込む。
既定は dry-run。実際に書き込むには --apply を付ける。

使い方:
    python3 .agent/scripts/merge_setlist.py --period 20260801-20260831
    python3 .agent/scripts/merge_setlist.py a/response.csv b/response.csv --apply
"""
import argparse
import csv
import glob
import io
import os
import re
import sys

# Ensure script runs from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../'))
os.chdir(project_root)

TARGET = 'data_event.csv'
COLUMNS = ['date', 'event', 'venue', 'setlist']
DATE_RE = re.compile(r'^\d{4}-\d{2}-\d{2}$')
# セトリが未確定であることを示す置き方。これらは新しい行で上書きしてよい。
PLACEHOLDERS = ('セトリ投稿確認', '画像参照（テキストなし）', '（会場未記載）')


def norm_key(text):
    """重複判定用のキー。表記そのものは書き換えない（`!` の数や `☆`/`★` は保持）。"""
    return re.sub(r'\s+', '', (text or '')).casefold()


def is_placeholder(setlist):
    s = (setlist or '').strip()
    return not s or any(p in s for p in PLACEHOLDERS)


def format_row(row):
    """既存 data_event.csv の体裁に合わせる（date は素、他3列は必ず引用）。"""
    def q(v):
        return '"' + (v or '').replace('"', '""') + '"'
    return f"{row['date']},{q(row['event'])},{q(row['venue'])},{q(row['setlist'])}"


def read_csv_text(text, source):
    """CSV 本文を読む。Grok が ```csv フェンスごと返しても剥がす。"""
    lines = text.replace('\r\n', '\n').split('\n')
    cleaned = [l for l in lines if not l.strip().startswith('```')]
    rows, problems = [], []
    reader = csv.DictReader(io.StringIO('\n'.join(cleaned)))
    if not reader.fieldnames:
        problems.append(f'{source}: 中身が空です')
        return rows, problems
    missing = [c for c in COLUMNS if c not in [f.strip() for f in reader.fieldnames]]
    if missing:
        problems.append(f'{source}: 列が足りません → {", ".join(missing)}'
                        f'（実際: {", ".join(reader.fieldnames)}）')
        return rows, problems
    for i, raw in enumerate(reader, 2):
        row = {c: (raw.get(c) or '').strip() for c in COLUMNS}
        if not any(row.values()):
            continue
        if not DATE_RE.match(row['date']):
            problems.append(f'{source}:{i}: date が YYYY-MM-DD ではありません → "{row["date"]}"')
            continue
        if not row['event']:
            problems.append(f'{source}:{i}: event が空です（{row["date"]}）')
            continue
        rows.append({'row': row, 'source': f'{source}:{i}'})
    return rows, problems


def read_target(path):
    """data_event.csv を1行=1レコードとして読み、元の行文字列を保持する。

    既存ファイルには `\\"` でクォートを書いた行が混じっており、csv で読み直して
    書き戻すと体裁が変わってしまう。触らない行は元の行をそのまま出すことで、
    無関係な差分が出ないようにする。
    """
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.read().replace('\r\n', '\n').rstrip('\n').split('\n')
    if not lines:
        return [], [], ''
    header = lines[0]
    records, problems = [], []
    for i, line in enumerate(lines[1:], 2):
        if not line.strip():
            continue
        fields = next(csv.reader(io.StringIO(line)), [])
        if len(fields) != len(COLUMNS):
            problems.append(f'{path}:{i}: 列数が {len(fields)} です（{line[:60]}…）')
            records.append({'row': None, 'raw': line, 'date': line.split(',', 1)[0],
                            'key': None, 'origin': f'{path}:{i}'})
            continue
        row = dict(zip(COLUMNS, (f.strip() for f in fields)))
        if not DATE_RE.match(row['date']):
            problems.append(f'{path}:{i}: date が YYYY-MM-DD ではありません → "{row["date"]}"')
            records.append({'row': None, 'raw': line, 'date': row['date'],
                            'key': None, 'origin': f'{path}:{i}'})
            continue
        records.append({'row': row, 'raw': line, 'date': row['date'],
                        'key': (row['date'], norm_key(row['event'])),
                        'origin': f'{path}:{i}'})
    return records, problems, header


def main():
    p = argparse.ArgumentParser(description='セトリCSVを data_event.csv にマージする')
    p.add_argument('files', nargs='*', help='取り込む CSV（省略時は --period で探す）')
    p.add_argument('--period', help='work/collect 配下の期間ディレクトリ名')
    p.add_argument('--collect-dir', default='work/collect')
    p.add_argument('--apply', action='store_true', help='実際に data_event.csv を書き換える')
    p.add_argument('--prefer', choices=['existing', 'new'], default='existing',
                   help='既存行と中身が食い違ったときどちらを残すか（既定 existing）')
    args = p.parse_args()

    files = list(args.files)
    if args.period:
        period_dir = os.path.join(args.collect_dir, args.period)
        if not os.path.isdir(period_dir):
            sys.exit(f'期間ディレクトリがありません: {period_dir}')
        files = sorted(glob.glob(os.path.join(period_dir, '*', 'response.csv')))
        if not files:
            sys.exit(f'response.csv が見つかりません: {period_dir}/*/response.csv')
    if not files:
        sys.exit('取り込む CSV を指定するか --period を渡してください')

    if not os.path.exists(TARGET):
        sys.exit(f'{TARGET} がありません')
    records, existing_problems, header = read_target(TARGET)
    if existing_problems:
        print(f'⚠ {TARGET} にそのまま読めない行があります（触らずに残します）:')
        for msg in existing_problems:
            print(f'    {msg}')
        print()

    index = {}
    for rec in records:
        if rec['key']:
            index.setdefault(rec['key'], rec)
    existing_count = len(records)

    added, updated, conflicts, duplicates, problems = [], [], [], [], []
    for path in files:
        if not os.path.exists(path):
            sys.exit(f'ファイルがありません: {path}')
        with open(path, 'r', encoding='utf-8-sig') as f:
            rows, probs = read_csv_text(f.read(), path)
        problems.extend(probs)
        for item in rows:
            row, source = item['row'], item['source']
            key = (row['date'], norm_key(row['event']))
            found = index.get(key)
            if found is None:
                rec = {'row': row, 'raw': None, 'date': row['date'],
                       'key': key, 'origin': source}
                records.append(rec)
                index[key] = rec
                added.append((source, row))
                continue
            same = all(found['row'][c] == row[c] for c in COLUMNS)
            if same:
                duplicates.append((source, row))
            elif is_placeholder(found['row']['setlist']) and not is_placeholder(row['setlist']):
                before = dict(found['row'])
                found['row'], found['raw'] = row, None
                updated.append((source, before, row))
            elif args.prefer == 'new':
                before = dict(found['row'])
                found['row'], found['raw'] = row, None
                updated.append((source, before, row))
            else:
                conflicts.append((source, found['row'], row))

    records.sort(key=lambda r: r['date'])

    print(f'取り込み対象: {len(files)}ファイル')
    for path in files:
        print(f'  - {path}')
    print()
    print(f'既存 {existing_count}行 → 結合後 {len(records)}行')
    print(f'  新規追加   {len(added)}')
    print(f'  上書き更新 {len(updated)}')
    print(f'  完全重複   {len(duplicates)}（変更なし）')
    print(f'  衝突       {len(conflicts)}')

    if added:
        print()
        print('■ 新規追加')
        for source, row in added:
            print(f'    {row["date"]} {row["event"]}  [{source}]')
    if updated:
        print()
        print('■ 上書き更新（既存が未確定だった、または --prefer new）')
        for source, before, after in updated:
            print(f'    {after["date"]} {after["event"]}  [{source}]')
            print(f'      before: {before["setlist"][:60]}')
            print(f'      after : {after["setlist"][:60]}')
    if conflicts:
        print()
        print('■ 衝突（既存を残しました。取り込むなら --prefer new）')
        for source, old, new in conflicts:
            print(f'    {new["date"]} {new["event"]}  [{source}]')
            for col in COLUMNS:
                if old[col] != new[col]:
                    print(f'      {col}:')
                    print(f'        既存: {old[col][:70]}')
                    print(f'        新規: {new[col][:70]}')
    if problems:
        print()
        print('■ 読み飛ばした行')
        for msg in problems:
            print(f'    {msg}')

    if not args.apply:
        print()
        print('dry-run です。書き込むには --apply を付けてください。')
        return

    if not (added or updated):
        print()
        print(f'変更がないため {TARGET} は書き換えませんでした。')
        return

    out = [header] + [r['raw'] if r['raw'] is not None else format_row(r['row'])
                      for r in records]
    with open(TARGET, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(out) + '\n')
    print()
    print(f'{TARGET} を更新しました（{len(records)}行）。')
    print('セトリ集計を更新する場合:')
    print('  python3 .agent/scripts/check_missing_months.py')


if __name__ == '__main__':
    main()
