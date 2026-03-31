import csv
import re
import os

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../'))
os.chdir(project_root)

existing_months = set()
if os.path.exists('work/monthly_setlist_ranking.csv'):
    with open('work/monthly_setlist_ranking.csv', 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if '年月' in row:
                existing_months.add(row['年月'])

all_months = set()
with open('data_event.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        date_str = row['date']
        setlist_str = row['setlist']
        if not date_str or not setlist_str or 'セトリ投稿確認' in setlist_str: continue
        m = re.match(r'^(\d{4}-\d{2})', date_str)
        if m:
            all_months.add(m.group(1))

missing = sorted(list(all_months - existing_months))
if missing:
    print(f"MISSING_MONTHS: {','.join(missing)}")
else:
    print("NO_MISSING_MONTHS")
