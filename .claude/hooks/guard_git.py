#!/usr/bin/env python3
"""PreToolUse(Bash) hook: 秘密情報と他人の著作物のコミットを止める。

止めるもの:
- `git add -f/--force`（.gitignore を無視して .env や取得データを入れる操作）
- `git commit` のときに、ステージ済み（-a なら変更済みも）に次が含まれる場合
    .env / work/x_fetch/ / *.jsonl / audio/ 配下（README 以外） / 音源ファイル
それ以外の git コマンドは何もしない（exit 0・出力なし）。
"""
import json
import os
import re
import subprocess
import sys

FORBIDDEN = re.compile(r'^\.env$|^work/x_fetch/|\.jsonl$|^audio/(?!README\.md$).+|\.(mp3|wav|flac|m4a|aac|ogg|opus)$', re.I)


def deny(reason):
    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }, ensure_ascii=False))
    sys.exit(0)


HEREDOC = re.compile(r"<<-?\s*['\"]?(\w+)['\"]?[^\n]*\n.*?\n\s*\1\s*(?=\n|$)", re.S)
SEPARATOR = re.compile(r'\n|;|&&|\|\||\||\$\(|`')


def git_commands(cmd):
    """コマンド文字列から、実際に実行される git コマンド（各セグメントの先頭）だけを取り出す。

    ヒアドキュメントの中身や引用符の中（ドキュメントに「git add -f」と書く場合など）を
    誤って止めないため、本文を落としてから区切り文字で分割し、`git` で始まるものだけを見る。
    """
    stripped = HEREDOC.sub('', cmd)
    stripped = re.sub(r"'[^']*'", "''", stripped)
    stripped = re.sub(r'"[^"]*"', '""', stripped)
    out = []
    for seg in SEPARATOR.split(stripped):
        seg = seg.strip()
        seg = re.sub(r'^(sudo\s+|env\s+(\S+=\S*\s+)*|\S+=\S*\s+)+', '', seg)
        if seg.startswith('git ') or seg == 'git':
            out.append(seg)
    return out


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        return
    cmd = (data.get('tool_input') or {}).get('command') or ''
    if 'git' not in cmd:
        return
    gits = git_commands(cmd)
    if any(re.match(r'git\s+add\b.*(\s-f\b|\s--force\b)', g) for g in gits):
        deny("git add -f は使わない。.gitignore 済みのファイル（.env、work/x_fetch/、音源）を入れる操作になる。"
             "本当に必要なら、ユーザーに確認してから行う。")
    commits = [g for g in gits if re.match(r'git\s+commit\b', g)]
    if not commits:
        return
    root = os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd()
    try:
        staged = subprocess.run(['git', 'diff', '--cached', '--name-only'], cwd=root,
                                capture_output=True, text=True, timeout=10).stdout.splitlines()
        if any(re.search(r'\s(-a|--all|-am|-a[a-z]*)\b', g) for g in commits):
            staged += subprocess.run(['git', 'diff', '--name-only'], cwd=root,
                                     capture_output=True, text=True, timeout=10).stdout.splitlines()
    except Exception:
        return
    bad = sorted({p for p in staged if FORBIDDEN.search(p)})
    if bad:
        deny("コミットに入れてはいけないファイルが含まれている: " + ', '.join(bad) +
             "。git restore --staged で外してからコミットする（.env は APIキー、work/x_fetch と *.jsonl は他人の投稿、audio/ は購入音源）。")


if __name__ == '__main__':
    main()
