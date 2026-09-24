#!/usr/bin/env python3
"""これまでの判定から「ろりぽっぷの話をする常連アカウント」の一覧を作る。

`data/x/egosearch_decisions_*.txt`（判定）と `work/x_fetch/egosearch_*.jsonl`（ID→ハンドルの対応）を突き合わせ、
`data/x/known_accounts.txt` を作り直す。**ハンドルと件数とメモだけ**を書くので、他人の投稿の原文は残らない。

なぜ要るか（2026-09-15 の実測。2026-09-07〜09-15 の候補 593 件）:

| 投稿者 | 候補 | 採用 | 打率 |
| --- | --- | --- | --- |
| 過去に採用されたことがあるアカウント | 144 | 140 | **97%** |
| それ以外 | 449 | 25 | 6% |

採用した投稿の 85% は「前にも採用したアカウント」から出ている。フォロー関係を API で調べるより、
自分の判定履歴のほうが強い手がかりになる（しかも無料で、週を追うごとに効く）。
`triage_egosearch.py` がこの一覧を読んで加点し、常連の投稿は要判定に回さず採用候補に入れる。

メモの出どころは2つ。どちらも消さずに残す:
- 判定ファイルの3列目（`<id> adopt このアカウントはファンのもの`）。スワイプアプリの備考欄がここに出る
- このファイルを直接編集して書いたメモ（`# fixed` を行末に付けると、再生成しても上書きしない）

    python3 .claude/skills/x-egosearch/scripts/build_known_accounts.py
"""

import argparse
import glob
import json
import os
import re
import sys
from collections import defaultdict

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, script_dir)
sys.path.insert(0, os.path.join(project_root, '.claude/skills/x-account-fetch/scripts'))
from fetch_egosearch import OWN_HANDLES  # noqa: E402  公式・メンバー・元メンバー・運営は常連に数えない

OUT_DIR = 'work/x_fetch'
DATA_DIR = 'data/x'
KNOWN_PATH = os.path.join(DATA_DIR, 'known_accounts.txt')

ROW = re.compile(r'^@(\S+)\t(?:adopt=(\d+)\s+reject=(\d+))\t?(.*)$')


def load_existing():
    """手で書いたメモ（行末 `# fixed`）を拾っておく。再生成で消さないため。"""
    fixed = {}
    if not os.path.exists(KNOWN_PATH):
        return fixed
    for line in open(KNOWN_PATH, encoding='utf-8'):
        line = line.rstrip('\n')
        if not line or line.startswith('#'):
            continue
        m = ROW.match(line)
        if m and m.group(4).rstrip().endswith('# fixed'):
            fixed['@' + m.group(1)] = (m.group(4).rstrip(), int(m.group(2)), int(m.group(3)))
    return fixed


def main():
    p = argparse.ArgumentParser(description='判定履歴から常連アカウントの一覧を作る')
    p.add_argument('--min-adopt', type=int, default=1, help='一覧に載せる最低採用数（既定 1）')
    args = p.parse_args()

    # ID → ハンドル（取得済みの生データから。無い期間はその分だけ数えられない）
    id2handle = {}
    for path in sorted(glob.glob(os.path.join(OUT_DIR, 'egosearch_*.jsonl'))):
        if path.endswith('_final.jsonl'):
            continue
        for line in open(path, encoding='utf-8'):
            try:
                t = json.loads(line)
            except json.JSONDecodeError:
                continue
            handle = ((t.get('author') or {}).get('userName') or '').strip()
            if handle:
                id2handle[str(t.get('id'))] = handle

    tally = defaultdict(lambda: {'adopt': 0, 'reject': 0, 'memos': []})
    unmatched = 0
    dec_files = sorted(glob.glob(os.path.join(DATA_DIR, 'egosearch_decisions_*.txt')))
    for path in dec_files:
        for line in open(path, encoding='utf-8'):
            parts = line.strip().split(None, 2)
            if len(parts) < 2 or parts[1] not in ('adopt', 'reject'):
                continue
            handle = id2handle.get(parts[0])
            if not handle:
                unmatched += 1
                continue
            if handle in OWN_HANDLES:
                continue
            row = tally['@' + handle]
            row[parts[1]] += 1
            memo = parts[2].strip() if len(parts) > 2 else ''
            if re.fullmatch(r'review行\d+', memo):
                memo = ''   # 2026-08 の判定ファイルに入っている行番号メモ。意味を持たないので捨てる
            if memo and memo not in row['memos']:
                row['memos'].append(memo)

    # 判定を書いていない採用（score>=3 の自動採用）も常連の根拠になる
    for path in sorted(glob.glob(os.path.join(DATA_DIR, 'egosearch_adopted_*.txt'))):
        for line in open(path, encoding='utf-8'):
            tid = line.strip()
            if not tid or tid.startswith('#'):
                continue
            handle = id2handle.get(tid)
            if handle and handle not in OWN_HANDLES:
                tally['@' + handle]['adopt'] += 1

    fixed = load_existing()
    rows = [(h, v) for h, v in tally.items() if v['adopt'] >= args.min_adopt]
    # `# fixed` の行は、生データが欠けて数えられないアカウントでも前回の件数のまま残す
    for h, (_, adopt, reject) in fixed.items():
        if h not in tally:
            rows.append((h, {'adopt': adopt, 'reject': reject, 'memos': []}))
    rows.sort(key=lambda kv: (-kv[1]['adopt'], kv[0]))

    os.makedirs(DATA_DIR, exist_ok=True)
    with open(KNOWN_PATH, 'w', encoding='utf-8') as f:
        f.write('# ろりぽっぷ!!!!!!! の話をしたことがあるアカウント（判定履歴から自動生成）\n')
        f.write(f'# {os.path.basename(__file__)} が作る。'
                f'元は {len(dec_files)} 本の判定ファイルと採用IDリスト。\n')
        f.write('# 書式: @handle<TAB>adopt=N reject=M<TAB>メモ\n')
        f.write('# メモに「# fixed」と書いておくと、再生成しても上書きしない（手で書いた説明を残すため）\n')
        f.write('# 他人の投稿の原文はここに入れない。\n')
        for h, v in rows:
            memo = fixed[h][0] if h in fixed else '／'.join(v['memos'])
            f.write(f"{h}\tadopt={v['adopt']} reject={v['reject']}\t{memo}\n")

    print(f'{len(rows)} アカウント → {KNOWN_PATH}')
    if unmatched:
        print(f'  生データに見つからず数えられなかった判定: {unmatched} 件'
              f'（その期間の jsonl が work/x_fetch/ に無い。x-data-sync で戻すと数えられる）')


if __name__ == '__main__':
    main()
