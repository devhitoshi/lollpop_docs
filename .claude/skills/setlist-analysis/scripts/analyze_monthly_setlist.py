import csv
import re
import os
import sys
import argparse
from collections import defaultdict

# Ensure script runs from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

parser = argparse.ArgumentParser()
parser.add_argument('--all', action='store_true', help='Re-calculate all months')
parser.add_argument('--months', type=str, help='Comma separated list of months (YYYY-MM)')
args = parser.parse_args()

if not args.all and not args.months:
    print("Please specify --all or --months=YYYY-MM")
    sys.exit(1)

target_months = []
if args.months:
    target_months = args.months.split(',')

sys.path.insert(0, script_dir)
from song_names import load_canonical_songs, normalize_song_name, is_non_song_item, split_setlist  # noqa: E402

# 曲名の正表記と名寄せルールは song_names.py に集約（check_event_consistency.py と共用）
canonical_songs = load_canonical_songs()

month_data = defaultdict(lambda: defaultdict(lambda: {'total': 0, 'first': 0, 'middle': 0, 'last': 0}))

with open('events/data_event.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        date_str = row['date']
        setlist_str = row['setlist']
        if not date_str or not setlist_str or 'セトリ投稿確認' in setlist_str: continue

        m = re.match(r'^(\d{4}-\d{2})', date_str)
        if not m:
            continue
        ym = m.group(1)

        if not args.all and ym not in target_months:
            continue

        for items in split_setlist(setlist_str):
            songs = []
            for item in items:
                if is_non_song_item(item): continue
                song_name = normalize_song_name(item, canonical_songs)
                if song_name and song_name in canonical_songs:
                    songs.append(song_name)

            n = len(songs)
            for i, song in enumerate(songs):
                month_data[ym][song]['total'] += 1
                if i == 0: month_data[ym][song]['first'] += 1
                elif i == n - 1: month_data[ym][song]['last'] += 1
                else: month_data[ym][song]['middle'] += 1

results = []
for ym in sorted(month_data.keys()):
    songs_in_month = month_data[ym]
    sorted_songs = sorted(songs_in_month.items(), key=lambda x: (x[1]['total'], x[1]['first']), reverse=True)
    
    rank = 1
    for i, (song, counts) in enumerate(sorted_songs):
        if i > 0 and counts['total'] < sorted_songs[i-1][1]['total']:
            rank = i + 1
        results.append({
            '年月': ym,
            '順位': rank,
            '楽曲名': song,
            '披露回数(全体)': counts['total'],
            '最初': counts['first'],
            '中盤': counts['middle'],
            '終盤': counts['last']
        })

existing_results = []
csv_columns = ['年月', '順位', '楽曲名', '披露回数(全体)', '最初', '中盤', '終盤']

if not args.all and os.path.exists('events/monthly_setlist_ranking.csv'):
    with open('events/monthly_setlist_ranking.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['年月'] not in target_months:
                existing_results.append(row)

final_results = existing_results + results
# Sort by Year-Month, then by total (descending rank) but since they already have '順位' we sort by Year-Month and then by '順位' logically
final_results.sort(key=lambda x: (x['年月'], int(x['順位'])))

os.makedirs('events', exist_ok=True)
with open('events/monthly_setlist_ranking.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=csv_columns)
    writer.writeheader()
    writer.writerows(final_results)

print("Successfully generated events/monthly_setlist_ranking.csv")
