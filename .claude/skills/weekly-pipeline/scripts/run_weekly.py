"""週刊記事1本の「収集→素材化→仕上げ」を連結する。

既存の6スキル・8スクリプトの責務とdescriptionは変えない。このスクリプトは呼び出す順番と、
毎回書き直されていたワンライナー（鮮度確認、いいね数を最新化するための行削除、3段階の件数表示）
だけを引き受ける。各段階の実体は必ず本物のスクリプトを subprocess で呼ぶ（import しない）。

  --stage collect  : 鮮度表示 → (--refresh) → fetch_accounts.py → fetch_egosearch.py → triage_egosearch.py（初回）
  --stage material : triage_egosearch.py（--decisions・最終）→ build_material.py → check_event_consistency.py
  --stage finish   : check_article.py → analyze_monthly_setlist.py → sync_x_data.py push → (article-refresh/check_stale.py があれば)

期間の既定は「前回実行の翌日〜今日」。状態は work/x_fetch/.pipeline_state.json に持つ（無ければ
work/x_fetch/*.jsonl の最新投稿日から推定し、確認を求める）。

使い方:
    python .claude/skills/weekly-pipeline/scripts/run_weekly.py --stage collect --dry-run
    python .claude/skills/weekly-pipeline/scripts/run_weekly.py --stage collect --since 2026-09-01 --until 2026-09-07 --yes
    python .claude/skills/weekly-pipeline/scripts/run_weekly.py --stage material --since 2026-09-01 --until 2026-09-07
    python .claude/skills/weekly-pipeline/scripts/run_weekly.py --stage finish --since 2026-09-01 --until 2026-09-07
"""
import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, os.path.join(project_root, '.claude/skills/x-account-fetch/scripts'))
from fetch_accounts import DEFAULT_ACCOUNTS, tweet_date  # noqa: E402  読み取り専用の定数・日付整形だけを再利用（実行はsubprocess）

X_FETCH_DIR = 'work/x_fetch'
DATA_X_DIR = 'data/x'
STATE_PATH = os.path.join(X_FETCH_DIR, '.pipeline_state.json')
ARTICLE_DIR = os.path.join('articles', '週刊まとめ')
FORMER_ACCOUNTS = [('asaka_lpop', '姫杏朝香'), ('natsumi_lpop', '苺花なつみ')]
# x-account-fetch SKILL.md の例（週1回・100件）と x-egosearch の例（月1回・600〜1500件）の中間。
# 未着手期間が空くと1回で追いつく運用（期間不定）なので、暴走を避けつつ週次相当より少し余裕を見た値にした。
DEFAULT_MAX = 200

CHECK_STALE = '.claude/skills/article-refresh/scripts/check_stale.py'


# ---------- 小道具 ----------

def py(*parts):
    return [sys.executable] + list(parts)


def run(cmd, dry_run, capture=False):
    print("$ " + ' '.join(cmd))
    if dry_run:
        return None
    if capture:
        result = subprocess.run(cmd, capture_output=True, text=True)
        if result.stdout:
            print(result.stdout, end='' if result.stdout.endswith('\n') else '\n')
        if result.stderr:
            print(result.stderr, end='' if result.stderr.endswith('\n') else '\n', file=sys.stderr)
    else:
        result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(f"停止: 次のコマンドが失敗した（exit {result.returncode}）\n  {' '.join(cmd)}")
    return result


def plus_one_day(d):
    return (datetime.strptime(d, '%Y-%m-%d') + timedelta(days=1)).strftime('%Y-%m-%d')


def count_lines(path):
    n = 0
    with open(path, encoding='utf-8') as f:
        for line in f:
            if line.strip():
                n += 1
    return n


def parse_created_dt(created):
    for fmt in ('%a %b %d %H:%M:%S %z %Y', '%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%d %H:%M:%S%z'):
        try:
            return datetime.strptime(created, fmt)
        except ValueError:
            continue
    return None


# ---------- 状態ファイル ----------

def load_state():
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, encoding='utf-8') as f:
            return json.load(f)
    return None


def save_state(until, stage):
    os.makedirs(X_FETCH_DIR, exist_ok=True)
    state = {'last_until': until, 'last_run_at': datetime.now().isoformat(timespec='seconds'), 'stage': stage}
    with open(STATE_PATH, 'w', encoding='utf-8') as f:
        json.dump(state, f, ensure_ascii=False, indent=1)
    print(f"状態ファイル更新: {STATE_PATH}（last_until={until}, stage={stage}）")


def guess_since_from_jsonl():
    """状態ファイルが無いとき、work/x_fetch/*.jsonl の最新 createdAt/created_at から since を逆算する。"""
    latest = None
    for path in glob.glob(os.path.join(X_FETCH_DIR, '*.jsonl')):
        with open(path, encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    t = json.loads(s)
                except json.JSONDecodeError:
                    continue
                created = t.get('createdAt') or t.get('created_at')
                if not created:
                    continue
                dt = parse_created_dt(created)
                if dt and (latest is None or dt > latest):
                    latest = dt
    return latest


def resolve_period(args):
    until = args.until or date.today().isoformat()
    if args.since:
        return args.since, until

    state = load_state()
    if state and state.get('last_until'):
        since = plus_one_day(state['last_until'])
        print(f"since を状態ファイルから推定: {since}（前回 last_until={state['last_until']}, "
              f"last_run_at={state.get('last_run_at')}）")
        return since, until

    latest = guess_since_from_jsonl()
    if latest is None:
        sys.exit("since を推定できない（状態ファイルも work/x_fetch/*.jsonl も無い）。--since を明示してください。")
    since = plus_one_day(latest.date().isoformat())
    print(f"状態ファイルが無いため、{X_FETCH_DIR}/*.jsonl の最新投稿日 {latest.date().isoformat()} の"
          f"翌日を since と推定: {since}")
    if not args.yes and not args.dry_run:
        if input("この since で進めますか？ [y/N] ").strip().lower() not in ('y', 'yes'):
            sys.exit("中止しました。--since を明示して再実行してください。")
    return since, until


# ---------- collect ----------

def account_list():
    accounts = list(DEFAULT_ACCOUNTS)
    accounts += [a for a in FORMER_ACCOUNTS if os.path.exists(os.path.join(X_FETCH_DIR, f'{a[0]}.jsonl'))]
    return accounts


def print_freshness_table():
    print("\n## 生データの鮮度（アカウントごとの最終日・件数）")
    for handle, label in account_list():
        path = os.path.join(X_FETCH_DIR, f'{handle}.jsonl')
        if not os.path.exists(path):
            print(f"  - {label}（@{handle}）: 未取得")
            continue
        n, last = 0, None
        with open(path, encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                try:
                    t = json.loads(s)
                except json.JSONDecodeError:
                    continue
                n += 1
                d = tweet_date(t)
                if d and (last is None or d > last):
                    last = d
        print(f"  - {label}（@{handle}）: {n} 件、最終 {last or '不明'}")


def do_refresh(since, until):
    """期間内の既存行を各jsonlから削除する（削除前にバックアップ）。9/7 に手作業で行ったのと同じ運用。"""
    paths = sorted(glob.glob(os.path.join(X_FETCH_DIR, '*.jsonl')))
    if not paths:
        print(f"--refresh: {X_FETCH_DIR}/ に jsonl が無いのでスキップ")
        return
    plan = {}
    for path in paths:
        kept, removed = [], 0
        with open(path, encoding='utf-8') as f:
            for line in f:
                s = line.strip()
                if not s:
                    kept.append(line)
                    continue
                try:
                    t = json.loads(s)
                except json.JSONDecodeError:
                    kept.append(line if line.endswith('\n') else line + '\n')
                    continue
                d = tweet_date(t)
                if d and since <= d <= until:
                    removed += 1
                else:
                    kept.append(line if line.endswith('\n') else line + '\n')
        if removed:
            plan[path] = (kept, removed)
    if not plan:
        print(f"--refresh: {since}〜{until} に該当する既存行は無し（削除不要）")
        return
    parent, name = os.path.split(os.path.normpath(X_FETCH_DIR))
    backup_dir = os.path.join(parent, f"{name}_bak_{date.today().isoformat()}")
    os.makedirs(backup_dir, exist_ok=True)
    for path in plan:
        shutil.copy2(path, os.path.join(backup_dir, os.path.basename(path)))
    for path, (kept, removed) in plan.items():
        with open(path, 'w', encoding='utf-8') as f:
            f.writelines(kept)
        print(f"  --refresh: {os.path.basename(path)} から {removed} 件削除")
    print(f"バックアップ: {backup_dir}")


def print_egosearch_counts(since, until, stage):
    """9/1に「5件しか見つからなかった」と誤解された反省で、必ず 生データ→候補→採用 の3段階を出す。"""
    raw_path = os.path.join(X_FETCH_DIR, f'egosearch_{since}_{until}.jsonl')
    raw_n = count_lines(raw_path) if os.path.exists(raw_path) else '不明（未取得）'

    cand_path = os.path.join(X_FETCH_DIR, f'egosearch_candidates_{since}_{until}.md')
    cand_n = '不明'
    if os.path.exists(cand_path):
        text = open(cand_path, encoding='utf-8').read()
        m = re.search(r'合計: 候補 (\d+) 件', text)
        if m:
            cand_n = m.group(1)

    print("\n件数（3段階。1→2は本人投稿の除外、2→3は機械仕分け＋Claudeの判定）:")
    print(f"  1. 生データ: {raw_n} 件")
    print(f"  2. 候補（本人投稿を除外）: {cand_n} 件")

    if stage == 'collect':
        base = os.path.join(X_FETCH_DIR, f'egosearch_triage_{since}_{until}')

        def cnt(suffix):
            p = base + suffix
            if not os.path.exists(p):
                return '不明'
            with open(p, encoding='utf-8') as f:
                return sum(1 for l in f if l.strip() and not l.startswith('#'))
        print(f"  3. 機械仕分け（まだ最終判定前）: 採用候補 {cnt('_adopt.txt')} / "
              f"要判定 {cnt('_review.txt')} / 除外候補 {cnt('_reject.txt')}")
        print("     要判定は Claude が data/x/egosearch_decisions_*.txt に adopt/reject を書くまで未確定。")
    else:
        summary_path = os.path.join(DATA_X_DIR, f'egosearch_triage_{since}_{until}_summary.txt')
        adopted_n, rejected_n = '不明', None
        if os.path.exists(summary_path):
            text = open(summary_path, encoding='utf-8').read()
            m = re.search(r'採用 (\d+) 件／除外 (\d+) 件', text)
            if m:
                adopted_n, rejected_n = m.group(1), m.group(2)
        tail = f"（除外 {rejected_n} 件）" if rejected_n is not None else ''
        print(f"  3. 採用（最終）: {adopted_n} 件{tail}")


def stage_collect(args, since, until):
    print_freshness_table()

    if args.refresh:
        if args.dry_run:
            print(f"\n[dry-run] --refresh: 実行時は {since}〜{until} の既存行をバックアップの上で削除する"
                  "（このモードでは何もしない）")
        else:
            print()
            do_refresh(since, until)

    max_n = args.max or DEFAULT_MAX

    fetch_accounts_cmd = py(
        '.claude/skills/x-account-fetch/scripts/fetch_accounts.py',
        '--since', since, '--until', plus_one_day(until),
        '--max-tweets-per-account', str(max_n),
        '--yes',
    )
    run(fetch_accounts_cmd, args.dry_run)

    fetch_egosearch_cmd = py(
        '.claude/skills/x-egosearch/scripts/fetch_egosearch.py',
        '--since', since, '--until', until,
        '--max-tweets-per-query', str(max_n),
        '--yes',
    )
    run(fetch_egosearch_cmd, args.dry_run)

    triage_cmd = py(
        '.claude/skills/x-egosearch/scripts/triage_egosearch.py',
        '--since', since, '--until', until,
    )
    run(triage_cmd, args.dry_run)

    if args.dry_run:
        print("\n（--dry-run のため件数は表示されない）")
    else:
        print_egosearch_counts(since, until, 'collect')

    if not args.dry_run:
        save_state(until, 'collect')

    decisions_path = os.path.join(DATA_X_DIR, f'egosearch_decisions_{since}_{until}.txt')
    print(f"\n次: {decisions_path} を書いて --stage material")


# ---------- material ----------

def find_orphan_section(material_path):
    if not os.path.exists(material_path):
        return None
    text = open(material_path, encoding='utf-8').read()
    m = re.search(r'### CSV に無い公演の疑い.*?(?=\n## |\Z)', text, re.S)
    return m.group(0) if m else None


def stage_material(args, since, until):
    decisions_path = os.path.join(DATA_X_DIR, f'egosearch_decisions_{since}_{until}.txt')
    if not os.path.exists(decisions_path):
        msg = f"判定ファイルが無い: {decisions_path}\n先に data/x/egosearch_decisions_{since}_{until}.txt を書いてから material に進む。"
        if args.dry_run:
            print(f"[dry-run] 注意: {msg}")
        else:
            sys.exit(msg)

    triage_cmd = py(
        '.claude/skills/x-egosearch/scripts/triage_egosearch.py',
        '--since', since, '--until', until,
        '--decisions', decisions_path,
    )
    run(triage_cmd, args.dry_run)

    if args.dry_run:
        print("\n（--dry-run のため件数は表示されない）")
    else:
        print_egosearch_counts(since, until, 'material')

    material_out = os.path.join(X_FETCH_DIR, f'draft_material_{since}_{until}.md')
    build_cmd = py(
        '.claude/skills/weekly-monthly-draft/scripts/build_material.py',
        '--since', since, '--until', until,
    )
    if args.dry_run:
        run(build_cmd, True)
    else:
        result = run(build_cmd, False, capture=True)
        m = re.search(r'CSV に無い公演の疑い (\d+) 件', result.stdout or '')
        if m and int(m.group(1)) > 0:
            print(f"\n停止: CSV に無い公演の疑いが {m.group(1)} 件ある。{material_out} を確認して events/data_event.csv を直す。")
            section = find_orphan_section(material_out)
            if section:
                print("\n" + section)
            sys.exit(2)

    check_cmd = py(
        '.claude/skills/setlist-analysis/scripts/check_event_consistency.py',
        '--since', since, '--until', until,
    )
    run(check_cmd, args.dry_run)

    if not args.dry_run:
        save_state(until, 'material')

    article_path = os.path.join(ARTICLE_DIR, f'{since}_{until}.md')
    print(f"\n次: 本文を書いて {article_path} に保存し、--stage finish")


# ---------- finish ----------

def stage_finish(args, since, until):
    article_path = args.article or os.path.join(ARTICLE_DIR, f'{since}_{until}.md')
    if not os.path.exists(article_path) and not args.dry_run:
        sys.exit(f"記事が無い: {article_path}。--article で指定するか、先に本文を書く。")

    check_cmd = py('.claude/skills/article-review/scripts/check_article.py', article_path)
    if args.dry_run:
        run(check_cmd, True)
    else:
        result = run(check_cmd, False, capture=True)
        m = re.search(r'RESULT: ERROR (\d+)', result.stdout or '')
        if m and int(m.group(1)) > 0:
            print(f"\n停止: check_article.py が ERROR {m.group(1)} 件を検出。記事を直してから再実行する。")
            sys.exit(1)

    months = sorted({since[:7], until[:7]})
    analyze_cmd = py(
        '.claude/skills/setlist-analysis/scripts/analyze_monthly_setlist.py',
        '--months', ','.join(months),
    )
    run(analyze_cmd, args.dry_run)

    sync_cmd = py(
        '.claude/skills/x-data-sync/scripts/sync_x_data.py', 'push',
        '--message', f'週刊 {since}〜{until} データ更新',
    )
    run(sync_cmd, args.dry_run)

    if os.path.exists(CHECK_STALE):
        run(py(CHECK_STALE), args.dry_run)
    else:
        print(f"（{CHECK_STALE} は無いのでスキップ。別作業で作る予定）")

    if not args.dry_run:
        save_state(until, 'finish')

    print("\n次: README とコミットは手作業。")


# ---------- main ----------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--stage', required=True, choices=['collect', 'material', 'finish'])
    p.add_argument('--since', help='開始日 YYYY-MM-DD（省略時は状態ファイル、無ければ推定）')
    p.add_argument('--until', help='終了日 YYYY-MM-DD（この日を含む。省略時は今日）')
    p.add_argument('--refresh', action='store_true',
                   help='collect: 期間内の既存行をバックアップの上で削除してから取得し直す'
                        '（いいね数などを最新化したいとき）')
    p.add_argument('--max', type=int, default=None,
                   help=f'fetch_accounts.py / fetch_egosearch.py の上限引数に渡す件数（既定 {DEFAULT_MAX}）')
    p.add_argument('--dry-run', action='store_true',
                   help='実行するコマンドを表示するだけで、APIを叩かず状態ファイルも変えない')
    p.add_argument('--yes', action='store_true', help='確認プロンプトを省略する')
    p.add_argument('--article', help='finish: 記事のパス（省略時は articles/週刊まとめ/<since>_<until>.md）')
    return p.parse_args()


def main():
    args = parse_args()
    since, until = resolve_period(args)
    print(f"対象期間: {since} 〜 {until}")

    if args.stage == 'collect':
        stage_collect(args, since, until)
    elif args.stage == 'material':
        stage_material(args, since, until)
    else:
        stage_finish(args, since, until)


if __name__ == '__main__':
    main()
