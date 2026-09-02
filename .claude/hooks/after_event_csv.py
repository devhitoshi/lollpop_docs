#!/usr/bin/env python3
"""PostToolUse(Write|Edit) hook: events/data_event.csv を編集したら集計と整合性チェックを自動で回す。

- monthly_setlist_ranking.csv を全期間で再生成する（手で再集計し忘れて記事の数字がずれるのを防ぐ）
- check_event_consistency.py --quiet の結果（名寄せできない曲名・重複行・公式投稿との食い違い）を
  additionalContext としてモデルに返す
data_event.csv 以外の編集では何もしない。
"""
import json
import os
import subprocess
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    ti = data.get('tool_input') or {}
    path = ti.get('file_path') or (data.get('tool_response') or {}).get('filePath') or ''
    if not path.replace('\\', '/').endswith('events/data_event.csv'):
        return
    root = os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd()
    scripts = os.path.join(root, '.claude/skills/setlist-analysis/scripts')
    notes = []
    r = subprocess.run([sys.executable, os.path.join(scripts, 'analyze_monthly_setlist.py'), '--all'],
                       cwd=root, capture_output=True, text=True, timeout=120)
    if r.returncode == 0:
        notes.append("events/data_event.csv の編集を受けて events/monthly_setlist_ranking.csv を全期間で再集計した。")
    else:
        notes.append("再集計に失敗: " + (r.stderr or r.stdout).strip()[-500:])
    r = subprocess.run([sys.executable, os.path.join(scripts, 'check_event_consistency.py'), '--quiet'],
                       cwd=root, capture_output=True, text=True, timeout=120)
    out = (r.stdout or '').strip()
    if out:
        notes.append("整合性チェック（check_event_consistency.py --quiet）:\n" + out[-3000:])
    else:
        notes.append("整合性チェック: 問題候補なし。")
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": "\n".join(notes),
        }
    }, ensure_ascii=False))


if __name__ == '__main__':
    main()
