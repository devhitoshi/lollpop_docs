#!/usr/bin/env python3
"""スワイプアプリ（Artifact）に溜まった判定を、判定ファイルに書き戻す。

Artifact の db の `decisions/<since>_<until>` を JSON で保存したものを読み、
`data/x/egosearch_decisions_<since>_<until>.txt` を作る。

    # 1. Claude が ArtifactData（action: "get"）で db を保存する
    #    collection: decisions / doc_id: <since>_<until> / out_dir: work/x_fetch/db
    # 2. それを渡す
    python3 .claude/skills/x-egosearch-review/scripts/import_decisions.py \\
      --since 2026-09-07 --until 2026-09-15 \\
      --from-json work/x_fetch/db/decisions/2026-09-07_2026-09-15.json

db のドキュメントの形（アプリが書く）:

    {"period": "...", "decisions": {"<投稿ID>": "adopt"|"reject"}, "notes": {"@handle": "備考"}}

`notes` はアカウント単位の備考。判定ファイルの3列目（メモ欄）に入れるので、
そのアカウントの行すべてに同じ文が付き、`build_known_accounts.py` が拾って
`data/x/known_accounts.txt` に残す。ID→ハンドルの対応は triage の出力（`_review.txt` など）から取る。

**アプリの「判定をコピー」を貼ってもらう場合はこのスクリプトは要らない。**
コピーされる中身がそのまま判定ファイルの中身になっている。
"""

import argparse
import json
import os
import re
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

OUT_DIR = 'work/x_fetch'
DATA_DIR = 'data/x'
LINE = re.compile(r'^(?:\[[^\]]*\]\s*)?(\d+)\|[^|]*\|(@[^|]*)\|')


def id_to_handle(since, until):
    """triage の3つの出力から 投稿ID → @handle を作る。"""
    base = os.path.join(OUT_DIR, f'egosearch_triage_{since}_{until}')
    m = {}
    for suffix in ('_review.txt', '_adopt.txt', '_reject.txt'):
        path = base + suffix
        if not os.path.exists(path):
            continue
        for line in open(path, encoding='utf-8'):
            hit = LINE.match(line)
            if hit:
                m[hit.group(1)] = hit.group(2).strip()
    return m


def main():
    p = argparse.ArgumentParser(description='Artifact の db の判定を判定ファイルにする')
    p.add_argument('--since', required=True)
    p.add_argument('--until', required=True)
    p.add_argument('--from-json', required=True, help='ArtifactData が保存した decisions ドキュメントの JSON')
    p.add_argument('--out', default=None, help='既定: data/x/egosearch_decisions_<since>_<until>.txt')
    p.add_argument('--keep-existing', action='store_true',
                   help='既存の判定ファイルにあって db に無い行を残す（手で書いた判定を消さない）')
    args = p.parse_args()

    body = json.load(open(args.from_json, encoding='utf-8'))
    decisions = body.get('decisions') or {}
    notes = body.get('notes') or {}
    if not decisions:
        sys.exit(f'{args.from_json} に decisions がありません。アプリでまだ1件も判定していない可能性があります。')
    period = body.get('period')
    if period and period != f'{args.since}_{args.until}':
        sys.exit(f'期間が合いません: ドキュメントは {period}、指定は {args.since}_{args.until}')

    out = args.out or os.path.join(DATA_DIR, f'egosearch_decisions_{args.since}_{args.until}.txt')
    merged = {}
    if args.keep_existing and os.path.exists(out):
        for line in open(out, encoding='utf-8'):
            parts = line.strip().split(None, 2)
            if len(parts) >= 2 and parts[1] in ('adopt', 'reject'):
                merged[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else '')

    handles = id_to_handle(args.since, args.until)
    unknown = 0
    for tid, verdict in decisions.items():
        if verdict not in ('adopt', 'reject'):
            continue
        handle = handles.get(str(tid))
        if not handle:
            unknown += 1
        memo = (notes.get(handle) or '').strip() if handle else ''
        merged[str(tid)] = (verdict, ' '.join(memo.split()))

    os.makedirs(DATA_DIR, exist_ok=True)
    adopt = sum(1 for v, _ in merged.values() if v == 'adopt')
    with open(out, 'w', encoding='utf-8') as f:
        f.write(f'# ろりぽっぷ!!!!!!! エゴサーチ判定 {args.since} 〜 {args.until}\n')
        for tid in sorted(merged, key=int):
            verdict, memo = merged[tid]
            f.write(f'{tid} {verdict}{" " + memo if memo else ""}\n')

    print(f'{len(merged)} 件（採用 {adopt} / 除外 {len(merged) - adopt}）→ {out}')
    if notes:
        print(f'  アカウントの備考 {len(notes)} 件をメモ欄に入れた')
    if unknown:
        print(f'  ⚠️ triage の出力にIDが見つからず、備考を付けられなかった判定: {unknown} 件'
              f'（triage_egosearch.py を同じ期間で実行し直すと解消する）')
    print('  次: triage_egosearch.py --decisions でこのファイルを反映し、build_known_accounts.py を回す')


if __name__ == '__main__':
    main()
