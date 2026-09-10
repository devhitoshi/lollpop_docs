#!/usr/bin/env python3
"""PreToolUse(Bash) hook: 秘密情報と他人の著作物のコミットを止める。

止めるもの:
- `git add -f/--force`（.gitignore を無視して .env や取得データを入れる操作）
- `git commit` のときに、ステージ済み（-a なら変更済みも）に次が含まれる場合
    .env / work/x_fetch/ / *.jsonl / audio/ 配下（README 以外） / 音源・動画ファイル
- `git push` の force 系（-f / --force / --force-with-lease / --mirror / +refspec）
- `git push` で main を書き換える操作（明示・現在ブランチ・--all のいずれも）

push の2つは GitHub 側のブランチ保護（main は PR 必須・non-fast-forward 禁止）と二重にかけている。
ブランチ保護がサーバ側の最終防御で、こちらは push する前に日本語の理由付きで止める一次防御。
Discord 経由のセッションでは、この理由文がそのままチャットに出る。

それ以外の git コマンドは何もしない（exit 0・出力なし）。
"""
import json
import os
import re
import subprocess
import sys

FORBIDDEN = re.compile(r'^\.env$|^work/x_fetch/|(^|/)\.openacp/|\.jsonl$|^audio/(?!README\.md$).+|\.(mp3|wav|flac|m4a|aac|ogg|opus|mp4|mov|m4v|webm|mkv|avi)$', re.I)


def deny(reason):
    # Windows の Python は、パイプへ書くとき既定でロケール（cp932）に落ちる。
    # Claude Code は hook の stdout を UTF-8 として読むので、明示しないと理由文が化ける。
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
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


PROTECTED = 'main'
FORCE_FLAG = re.compile(r'^(-f|--force|--force-with-lease(=.*)?|--force-if-includes|--mirror)$')
# git 本体のグローバルオプションのうち、値を次のトークンに取るもの（`git -C <path> push` を読み飛ばすため）
GLOBAL_OPT_ARG = {'-C', '-c', '--namespace', '--exec-path', '--git-dir', '--work-tree'}
# git push のオプションのうち、値を次のトークンに取るもの（値を refspec と取り違えないため）
PUSH_OPT_ARG = {'-o', '--push-option', '--receive-pack', '--exec', '--repo'}


def subcommand(seg):
    """`git [global-opts] <sub> [args...]` から、サブコマンド名と以降の引数を返す。"""
    toks = seg.split()[1:]
    i = 0
    while i < len(toks):
        t = toks[i]
        if t in GLOBAL_OPT_ARG:
            i += 2
            continue
        if t.startswith('-'):
            i += 1
            continue
        return t, toks[i + 1:]
    return None, []


def current_branch():
    root = os.environ.get('CLAUDE_PROJECT_DIR') or os.getcwd()
    try:
        return subprocess.run(['git', 'rev-parse', '--abbrev-ref', 'HEAD'], cwd=root,
                              capture_output=True, text=True, timeout=10).stdout.strip()
    except Exception:
        return ''


def check_push(seg):
    """force push と、main を書き換える push を止める。"""
    sub, args = subcommand(seg)
    if sub != 'push':
        return
    if any(FORCE_FLAG.match(a) for a in args):
        deny("force push は禁止。履歴を壊すと、他のセッションと Discord 側で進んでいる作業が巻き戻る。"
             "やり直したいなら、打ち消しのコミットを積むか、作業ブランチを作り直す。")
    if '--all' in args:
        deny("`git push --all` は main も一緒に書き換えうる。ブランチを名指しして push する。")

    # オプションを除いた位置引数（[0] がリモート、[1:] が refspec）
    positional = []
    i = 0
    while i < len(args):
        a = args[i]
        if a in PUSH_OPT_ARG:
            i += 2
            continue
        if not a.startswith('-'):
            positional.append(a)
        i += 1

    if any(a.startswith('+') for a in positional):
        deny("`+<refspec>` は force push と同じ意味なので禁止。")

    refspecs = positional[1:]
    targets = []
    for r in refspecs:
        dst = r.split(':')[-1]
        if dst in ('HEAD', ''):
            dst = current_branch()
        targets.append(dst.replace('refs/heads/', ''))
    if not refspecs:
        # refspec を書かない push は、現在のブランチが対象になる
        targets.append(current_branch())

    if PROTECTED in targets:
        deny("main への直接 push は禁止。作業ブランチを push して PR を作り、`gh pr merge` でマージする"
             "（GitHub 側のブランチ保護でも同じものを弾いているので、押し切っても通らない）。")


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
    for g in gits:
        check_push(g)
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
