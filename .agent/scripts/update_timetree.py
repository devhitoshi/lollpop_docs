"""出演イベント一覧（data_timetree.csv）を更新する。

TimeTree は毎回見に行かず、エクスポートをこのファイルに取り込んで使い回す。
`prepare_collect.py` は既定でこのファイルを母集団として読む。

使い方:
    python3 .agent/scripts/update_timetree.py timetree.ics            # dry-run
    python3 .agent/scripts/update_timetree.py timetree.ics --apply
    python3 .agent/scripts/update_timetree.py data_event.csv --source data_event --apply
"""
import argparse
import csv
import io
import os
import sys

# Ensure script runs from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../'))
os.chdir(project_root)
sys.path.insert(0, script_dir)

from _population import load_population, norm_key  # noqa: E402

TARGET = 'data_timetree.csv'
COLUMNS = ['date', 'event', 'venue', 'source']
# source の優先順位。強いものが弱いものを上書きする。
PRECEDENCE = {'data_event': 1, 'timetree': 2, 'manual': 3}


def format_row(row):
    def q(v):
        return '"' + (v or '').replace('"', '""') + '"'
    return f"{row['date']},{q(row['event'])},{q(row['venue'])},{q(row['source'])}"


def read_target(path):
    if not os.path.exists(path):
        return [], ','.join(COLUMNS)
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.read().replace('\r\n', '\n').rstrip('\n').split('\n')
    if not lines or not lines[0].strip():
        return [], ','.join(COLUMNS)
    header, records = lines[0], []
    for line in lines[1:]:
        if not line.strip():
            continue
        fields = next(csv.reader(io.StringIO(line)), [])
        if len(fields) != len(COLUMNS):
            sys.exit(f'{path} の列数が想定と違います: {line[:80]}')
        records.append(dict(zip(COLUMNS, (f.strip() for f in fields))))
    return records, header


def main():
    p = argparse.ArgumentParser(description='出演イベント一覧を更新する')
    p.add_argument('files', nargs='+', help='取り込むファイル（.ics / .json / .csv）')
    p.add_argument('--source', default='timetree',
                   choices=sorted(PRECEDENCE), help='取り込む行の出所（既定 timetree）')
    p.add_argument('--apply', action='store_true', help=f'実際に {TARGET} を書き換える')
    p.add_argument('--target', default=TARGET)
    args = p.parse_args()

    records, header = read_target(args.target)
    # 同じ日・同じイベント名でも会場が違えば別公演（サーキット系で実際に起きる）。
    # 会場まで見て突き合わせる。
    index = {}
    for rec in records:
        index.setdefault((rec['date'], norm_key(rec['event'])), []).append(rec)

    added, updated, same, same_day, ambiguous = [], [], 0, [], []
    for path in args.files:
        if not os.path.exists(path):
            sys.exit(f'ファイルがありません: {path}')
        for ev in load_population(path):
            row = {'date': ev['start_at'], 'event': ev['title'],
                   'venue': ev['venue'] or '', 'source': args.source}
            key = (row['date'], norm_key(row['event']))
            candidates = index.get(key, [])

            found = None
            if candidates:
                if not row['venue']:
                    # 会場が取れていない行。候補が1つに絞れるときだけ同じ公演とみなす
                    if len(candidates) == 1:
                        found = candidates[0]
                    else:
                        ambiguous.append((row, [c['venue'] for c in candidates]))
                        same += 1
                        continue
                else:
                    found = next((c for c in candidates
                                  if norm_key(c['venue']) == norm_key(row['venue'])), None)
                    if found is None:
                        # 会場が空のまま入っていた行があれば、そこを埋める
                        found = next((c for c in candidates if not c['venue']), None)

            if found is None:
                # 同じ日に別タイトルの行がある場合は知らせる（複数公演か表記ゆれか判断が要る）
                siblings = [r['event'] for r in records
                            if r['date'] == row['date'] and norm_key(r['event']) != key[1]]
                if siblings:
                    same_day.append((row, siblings))
                records.append(row)
                index.setdefault(key, []).append(row)
                added.append(row)
                continue

            changes = []
            if row['venue'] and not found['venue']:
                changes.append(f"venue: （空）→「{row['venue']}」")
                found['venue'] = row['venue']
            if PRECEDENCE[args.source] > PRECEDENCE.get(found['source'], 0):
                changes.append(f"source: {found['source']} → {args.source}")
                found['source'] = args.source
            if changes:
                updated.append((found, changes))
            else:
                same += 1

    records.sort(key=lambda r: r['date'])

    print(f'取り込み: {", ".join(args.files)}（source={args.source}）')
    print(f'{args.target}: {len(records) - len(added)}行 → {len(records)}行')
    print(f'  新規追加 {len(added)} / 更新 {len(updated)} / 変更なし {same}')

    if added:
        print()
        print('■ 新規追加')
        for row in added[:40]:
            print(f"    {row['date']} {row['event']}")
        if len(added) > 40:
            print(f'    …ほか {len(added) - 40}件')
    if updated:
        print()
        print('■ 更新')
        for row, changes in updated:
            print(f"    {row['date']} {row['event']}")
            for c in changes:
                print(f'      {c}')
    if same_day:
        print()
        print('■ 同じ日に別タイトルの行があります（複数公演なら正常。表記ゆれなら片方を消す）')
        for row, siblings in same_day:
            print(f"    {row['date']} 追加: {row['event']}")
            for s in siblings:
                print(f"             既存: {s}")

    if ambiguous:
        print()
        print('■ 会場が取れておらず、同名の候補が複数あるため突き合わせできませんでした')
        for row, venues in ambiguous:
            print(f"    {row['date']} {row['event']}")
            print(f"      既存の候補: {' / '.join(v or '（会場なし）' for v in venues)}")

    if not args.apply:
        print()
        print('dry-run です。書き込むには --apply を付けてください。')
        return
    if not (added or updated):
        print()
        print(f'変更がないため {args.target} は書き換えませんでした。')
        return

    out = [header] + [format_row(r) for r in records]
    with open(args.target, 'w', encoding='utf-8', newline='') as f:
        f.write('\n'.join(out) + '\n')
    print()
    print(f'{args.target} を更新しました（{len(records)}行）。')


if __name__ == '__main__':
    main()
