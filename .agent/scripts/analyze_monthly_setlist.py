import csv
import re
import os
import sys
import argparse
from collections import defaultdict

# Ensure script runs from project root
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../'))
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

canonical_songs = []
with open('songs/楽曲一覧.md', 'r', encoding='utf-8') as f:
    for line in f:
        m = re.match(r'^\s*-\s*\*\*(.+)\*\*', line)
        if m:
            canonical_songs.append(m.group(1).strip())

def normalize_song_name(name):
    name = name.strip()
    name = re.sub(r'^[0-9]+[\s\.]*', '', name)
    name = re.sub(r'🆕✨?', '', name)
    name = re.sub(r'❤️\s*', '', name)
    name = re.sub(r'🍭\s*', '', name)
    name = re.sub(r'💙\s*', '', name)
    name = re.sub(r'（.*?）', '', name)
    name = re.sub(r'\(.*?\)', '', name)
    name = name.replace('飴入れ', '').replace('飴投げ', '')
    name = name.strip()

    if 'ろりぽっぷ' in name and '単独' not in name: return next((c for c in canonical_songs if 'ろりぽっぷ' in c), None)
    if '始まりの宴' in name: return next((c for c in canonical_songs if '始まりの宴' in c), None)
    if '主人公' in name: return next((c for c in canonical_songs if '主人公' in c), None)
    if '約束' in name: return next((c for c in canonical_songs if '約束' in c), None)
    if 'ぽっぽ' in name and 'ポジティブ' in name: return next((c for c in canonical_songs if 'ぽっぽ' in c), None)
    if 'Lambie' in name: return next((c for c in canonical_songs if 'Lambie' in c), None)
    if 'Say Hello' in name: return next((c for c in canonical_songs if 'Say Hello' in c), None)
    if '推し事' in name: return next((c for c in canonical_songs if '推し事' in c), None)
    if '正解の方程式' in name: return next((c for c in canonical_songs if '正解の方程式' in c), None)
    if 'キミノセイ' in name: return next((c for c in canonical_songs if 'キミノセイ' in c), None)

    for c in canonical_songs:
        if name.lower() == c.lower(): return c
    for c in canonical_songs:
        if c in name: return c
    return None

month_data = defaultdict(lambda: defaultdict(lambda: {'total': 0, 'first': 0, 'middle': 0, 'last': 0}))

with open('data_event.csv', 'r', encoding='utf-8') as f:
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

        parts = setlist_str.split('|')
        for part in parts:
            part = re.sub(r'\d+部:\s*', '', part)
            part = re.sub(r'アンコール;?', '', part)
            items = [item.strip() for item in part.split(';') if item.strip()]

            songs = []
            for item in items:
                if re.search(r'^(SE|MC)', item) or item.startswith('MC(') or item.startswith('MC（'): continue
                if 'ラジオ体操' in item or 'クイズ' in item: continue
                song_name = normalize_song_name(item)
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

if not args.all and os.path.exists('work/monthly_setlist_ranking.csv'):
    with open('work/monthly_setlist_ranking.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['年月'] not in target_months:
                existing_results.append(row)

final_results = existing_results + results
# Sort by Year-Month, then by total (descending rank) but since they already have '順位' we sort by Year-Month and then by '順位' logically
final_results.sort(key=lambda x: (x['年月'], int(x['順位'])))

os.makedirs('work', exist_ok=True)
with open('work/monthly_setlist_ranking.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=csv_columns)
    writer.writeheader()
    writer.writerows(final_results)

with open('monthly_setlist_ranking.csv', 'w', encoding='utf-8', newline='') as f:
    writer = csv.DictWriter(f, fieldnames=csv_columns)
    writer.writeheader()
    writer.writerows(final_results)
    
print("Successfully generated monthly_setlist_ranking.csv")
