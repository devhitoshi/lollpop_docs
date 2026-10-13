#!/usr/bin/env python3
"""毎朝のタスクから呼ぶ入口。このワークツリーを origin/main に合わせてから daily_setlist_pr.py を回す。

手元のチェックアウト（projects/lollpop_docs）は別のセッションがブランチを切り替えて使うので、
そこのスクリプトを直接呼ぶと main に入れた修正が効かない（2026-10-13、自動マージと誤カウントの修正が効かなかった）。
そこでタスク専用のワークツリー（projects/lollpop_docs_wt_cron）に置いたこのファイルを呼び、毎回 origin/main に合わせてから回す。

**このワークツリーでは作業しない。** 毎回 `git checkout --force` で origin/main に戻すので、変更は消える。
消してしまったら register_daily_task.ps1 を再実行すると作り直す。

使い方（タスクスケジューラから）:
    pythonw <wt_cron>/.claude/skills/setlist-analysis/scripts/run_latest.py --data-root <手元のチェックアウト>
試すとき:
    python  <wt_cron>/.claude/skills/setlist-analysis/scripts/run_latest.py --data-root <手元のチェックアウト> --dry-run
--data-root 以外の引数は daily_setlist_pr.py にそのまま渡す。
"""

import os
import subprocess
import sys
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
wt_root = os.path.abspath(os.path.join(script_dir, '../../../../'))


def log_line(data_root, text):
    """daily_setlist_pr.py が動く前に失敗したときの記録。pythonw は画面を出さないので、ログにしか残せない。"""
    path = os.path.join(data_root, 'work', 'x_fetch', 'logs', 'daily_setlist_pr.log')
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write("\n===== %s run_latest =====\n%s\n" % (datetime.now().isoformat(timespec='seconds'), text))


def git(*args):
    return subprocess.run(['git', '-C', wt_root] + list(args), capture_output=True, text=True,
                          encoding='utf-8', errors='replace')


def main():
    argv = sys.argv[1:]
    if '--data-root' not in argv or argv.index('--data-root') + 1 >= len(argv):
        sys.stderr.write("--data-root <手元のチェックアウト> が要る\n")
        return 2
    data_root = os.path.abspath(argv[argv.index('--data-root') + 1])

    for cmd in (['fetch', 'origin', 'main'], ['checkout', '--detach', '--force', 'origin/main']):
        p = git(*cmd)
        if p.returncode != 0:
            log_line(data_root, "git %s に失敗（%d）。今日は回さない\n%s%s"
                     % (' '.join(cmd), p.returncode, p.stdout, p.stderr))
            return 1

    # checkout で daily_setlist_pr.py が新しくなっているので、別のプロセスとして呼ぶ（このファイルの古い中身に依存しない）
    target = os.path.join(wt_root, '.claude', 'skills', 'setlist-analysis', 'scripts', 'daily_setlist_pr.py')
    return subprocess.run([sys.executable, target] + argv).returncode


if __name__ == '__main__':
    sys.exit(main())
