#!/usr/bin/env python3
"""triage_egosearch.py の仕分け結果を、スワイプで判定する1枚もののHTMLにする。

`_review.txt`（要判定）と `_adopt.txt`（採用候補）を読んで、
`.claude/skills/x-egosearch/assets/triage_app.template.html` にデータを埋め込むだけ。判定はしない。

出来た HTML は Artifact として公開して使う（スマホで右スワイプ＝ろりぽっぷ関連／左スワイプ＝別物）。
判定は artifact の db に `decisions/<since>_<until>` として溜まり、アプリの「判定をコピー」で
`data/x/egosearch_decisions_<since>_<until>.txt` の中身がそのまま出る。

出力は work/x_fetch/（.gitignore 済み）。**他人の投稿の原文を含むので、リポジトリにも公開 URL にも置かない**
（Artifact は db を宣言すると組織内限定になり、既定で非公開）。

    python3 .claude/skills/x-egosearch/scripts/build_triage_app.py --since 2026-09-07 --until 2026-09-15
"""

import argparse
import json
import os
import re
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

OUT_DIR = os.path.join('work', 'x_fetch')
TEMPLATE = os.path.join('.claude', 'skills', 'x-egosearch', 'assets', 'triage_app.template.html')

# 関係者（本人以外だが「外部の反応」ではない人）。fetch_egosearch.py の OWN_HANDLES で
# 除外されるようになったが、それ以前に取った素材にはまだ混ざっているので、ここでも落とす。
STAFF_HANDLES = {'@nanotabiyori'}

LINE = re.compile(r'^(?:\[([^\]]*)\]\s*)?(\d+)\|([^|]*)\|(@[^|]*)\|([^|]*)\|(.*)$')


def parse(path):
    """triage の出力（1行1件）を読む。読めない行は数えて報告する。"""
    items, skipped = [], 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line or line.startswith('#'):
                continue
            m = LINE.match(line)
            if not m:
                skipped += 1
                continue
            tag, tid, dt, handle, metrics, text = m.groups()
            likes = re.search(r'♥(\d+)', metrics)
            views = re.search(r'👁(\d+)', metrics)
            items.append({
                'id': tid,
                'tag': (tag or '').strip(),
                'dt': dt.strip(),
                'handle': handle.strip(),
                'likes': int(likes.group(1)) if likes else 0,
                'views': int(views.group(1)) if views else 0,
                'text': text.strip(),
            })
    return items, skipped


def main():
    p = argparse.ArgumentParser(description='エゴサ仕分けのスワイプアプリ（HTML）を作る')
    p.add_argument('--since', required=True, help='開始日 YYYY-MM-DD（triage と同じ）')
    p.add_argument('--until', required=True, help='終了日 YYYY-MM-DD（triage と同じ）')
    p.add_argument('--out', default=None, help='出力先HTML（既定: work/x_fetch/triage_app_<since>_<until>.html）')
    args = p.parse_args()

    base = os.path.join(OUT_DIR, f'egosearch_triage_{args.since}_{args.until}')
    review_path, adopt_path = base + '_review.txt', base + '_adopt.txt'
    for path in (review_path, adopt_path):
        if not os.path.exists(path):
            sys.exit(f'{path} がありません。先に triage_egosearch.py を実行してください。')

    review, skipped_r = parse(review_path)
    adopt, skipped_a = parse(adopt_path)

    staff = [it for it in review if it['handle'] in STAFF_HANDLES]
    review = [it for it in review if it['handle'] not in STAFF_HANDLES]

    deck = {'review': review, 'adopt': adopt, 'staff_removed': len(staff)}
    # </script> で早期に閉じられるのと、実体参照の取り違えを防ぐ
    payload = (json.dumps(deck, ensure_ascii=False)
               .replace('<', '\\u003c')
               .replace('&', '\\u0026'))

    html = open(TEMPLATE, encoding='utf-8').read()
    html = (html
            .replace('__DECK_JSON__', payload)
            .replace('__PERIOD_LABEL__', f'{args.since} → {args.until}')
            .replace('__PERIOD__', f'{args.since}_{args.until}'))

    out = args.out or os.path.join(OUT_DIR, f'triage_app_{args.since}_{args.until}.html')
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)

    print(f'要判定 {len(review)} 件 / 採用候補 {len(adopt)} 件 → {out}')
    if staff:
        print(f'  関係者として除外: {len(staff)} 件（{", ".join(sorted({it["handle"] for it in staff}))}）')
    if skipped_r or skipped_a:
        print(f'  読めなかった行: 要判定 {skipped_r} / 採用候補 {skipped_a}')
    print('  Artifact として公開して使う（capabilities は db。判定は decisions/<期間> に入る）')


if __name__ == '__main__':
    main()
