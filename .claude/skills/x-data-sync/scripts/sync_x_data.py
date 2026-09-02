"""X の取得データ（work/x_fetch/*.jsonl）を、非公開のデータリポジトリと往復させる。

リモートの Claude Code はコンテナが使い捨てで、.gitignore 対象の work/x_fetch/ は次のセッションで消える。
他人の投稿の原文は公開リポジトリ（lollpop_docs）に入れない方針なので、非公開リポジトリ lollpop_data に
「必要な項目だけに絞った圧縮版」を置き、セッション開始時に復元する。

  push   work/x_fetch/*.jsonl → <data>/x/<name>.jsonl.gz（項目を絞る）。commit と push まで行う
  pull   <data>/x/*.jsonl.gz → work/x_fetch/*.jsonl（既存のスクリプトが読める形に戻す）。無いものだけ復元
  status 両側にあるファイルと件数を並べる

データリポジトリの場所は環境変数 LOLLPOP_DATA_DIR（既定: リポジトリの隣の ../lollpop_data）。
無ければ `git clone https://github.com/devhitoshi/lollpop_data ../lollpop_data`（リモート環境では先に add_repo）。

使い方:
    python3 .claude/skills/x-data-sync/scripts/sync_x_data.py status
    python3 .claude/skills/x-data-sync/scripts/sync_x_data.py push
    python3 .claude/skills/x-data-sync/scripts/sync_x_data.py pull
"""
import argparse
import glob
import gzip
import json
import os
import subprocess
import sys

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

WORK = 'work/x_fetch'
DATA_DIR = os.environ.get('LOLLPOP_DATA_DIR') or os.path.abspath(os.path.join(project_root, '..', 'lollpop_data'))
DATA_SUB = 'x'
# 保存する項目。下流のスクリプト（build_material / triage / profile_stats / check_event_consistency / collect_metrics）が読むもの
KEEP = ('id', 'url', 'text', 'createdAt', 'likeCount', 'retweetCount', 'replyCount', 'quoteCount', 'viewCount',
        'bookmarkCount', 'isReply', 'inReplyToId', 'lang', '_queries')
# メディアは slim_media() で URL・寸法・動画の変種まで残す（x-media-collect の索引を作り直せるように）


def slim_media(m):
    """メディアは x-media-collect の索引に要る項目まで残す（URL・寸法・動画の変種・長さ）。

    画像や動画そのものは保存しない。素材探しは索引でやり、実物は必要になったときに取りに行く。
    """
    oi = m.get('original_info') or {}
    vi = m.get('video_info') or {}
    out = {'type': m.get('type'), 'media_url_https': m.get('media_url_https'),
           'original_info': {'width': oi.get('width'), 'height': oi.get('height')},
           'allow_download_status': m.get('allow_download_status')}
    if vi:
        mp4 = [v for v in (vi.get('variants') or []) if v.get('content_type') == 'video/mp4']
        best = max(mp4, key=lambda v: v.get('bitrate') or 0) if mp4 else None
        out['video_info'] = {'duration_millis': vi.get('duration_millis'), 'aspect_ratio': vi.get('aspect_ratio'),
                             'variants': [best] if best else []}
    return out


def slim(t):
    a = t.get('author') or {}
    s = {k: t.get(k) for k in KEEP if k in t}
    s['author'] = {'userName': a.get('userName'), 'name': a.get('name'), 'id': a.get('id')}
    media = (t.get('extendedEntities') or {}).get('media') or []
    s['media'] = [slim_media(m) for m in media]
    s['is_rt'] = bool(t.get('retweeted_tweet'))
    return s


def fat(s):
    """復元: 既存スクリプトが参照する形（author, extendedEntities.media, retweeted_tweet）に戻す。"""
    t = dict(s)
    t['extendedEntities'] = {'media': [dict(m, restored=True) for m in s.get('media') or []]}
    if s.get('is_rt'):
        t['retweeted_tweet'] = {'restored': True}
    t.pop('media', None)
    t.pop('is_rt', None)
    return t


def data_path():
    d = os.path.join(DATA_DIR, DATA_SUB)
    if not os.path.isdir(DATA_DIR):
        sys.exit(f"データリポジトリが無い: {DATA_DIR}\n  git clone https://github.com/devhitoshi/lollpop_data {DATA_DIR}"
                 "（リモート環境では先に add_repo で devhitoshi/lollpop_data を取り込む）")
    os.makedirs(d, exist_ok=True)
    return d


def count_lines(path, opener=open):
    n = 0
    with opener(path, 'rt', encoding='utf-8') as f:
        for _ in f:
            n += 1
    return n


def cmd_status(_):
    print(f"work: {WORK}")
    for p in sorted(glob.glob(os.path.join(WORK, '*.jsonl'))):
        print(f"  {os.path.basename(p):55s} {count_lines(p):>6} 件")
    if not os.path.isdir(DATA_DIR):
        print(f"data: {DATA_DIR}（無い）")
        return
    print(f"data: {DATA_DIR}/{DATA_SUB}")
    for p in sorted(glob.glob(os.path.join(DATA_DIR, DATA_SUB, '*.jsonl.gz'))):
        print(f"  {os.path.basename(p):55s} {count_lines(p, gzip.open):>6} 件")


def cmd_push(args):
    d = data_path()
    written = []
    for p in sorted(glob.glob(os.path.join(WORK, '*.jsonl'))):
        name = os.path.basename(p)
        if 'triage' in name and 'final' in name:
            continue  # 判定後の抜粋。生データと判定ファイルから再生成できる
        out = os.path.join(d, name + '.gz')
        n = 0
        with open(p, encoding='utf-8') as f, gzip.open(out, 'wt', encoding='utf-8') as g:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    t = json.loads(line)
                except json.JSONDecodeError:
                    continue
                g.write(json.dumps(slim(t), ensure_ascii=False) + '\n')
                n += 1
        written.append((name + '.gz', n, os.path.getsize(out)))
    for name, n, size in written:
        print(f"  {name:55s} {n:>6} 件 {size / 1024:>7.0f} KB")
    if not written:
        print("push するファイルが無い")
        return
    if args.no_git:
        return
    r = subprocess.run(['git', 'status', '--porcelain'], cwd=DATA_DIR, capture_output=True, text=True)
    if not r.stdout.strip():
        print("データリポジトリに変更なし")
        return
    subprocess.run(['git', 'add', '-A'], cwd=DATA_DIR, check=True)
    subprocess.run(['git', 'commit', '-q', '-m', args.message], cwd=DATA_DIR, check=True)
    p = subprocess.run(['git', 'push'], cwd=DATA_DIR, capture_output=True, text=True)
    print("push 済み" if p.returncode == 0 else f"push 失敗（コミットは残っている）: {p.stderr.strip()[-300:]}")


def cmd_pull(args):
    d = data_path()
    os.makedirs(WORK, exist_ok=True)
    restored = []
    for p in sorted(glob.glob(os.path.join(d, '*.jsonl.gz'))):
        name = os.path.basename(p)[:-3]
        out = os.path.join(WORK, name)
        if os.path.exists(out) and not args.force:
            continue
        n = 0
        with gzip.open(p, 'rt', encoding='utf-8') as g, open(out, 'w', encoding='utf-8') as f:
            for line in g:
                line = line.strip()
                if line:
                    f.write(json.dumps(fat(json.loads(line)), ensure_ascii=False) + '\n')
                    n += 1
        restored.append((name, n))
    for name, n in restored:
        print(f"  復元 {name:50s} {n:>6} 件")
    if not restored:
        print("復元するものが無い（既にある、またはデータ側が空。--force で上書き）")
    print("注意: 復元したデータは項目を絞った版。本文・日時・投稿者・反応数・メディアの URL と寸法は残るが、"
          "\n      プロフィールの詳細と、動画の低ビットレート版は含まない")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    pp = sub.add_parser('push')
    pp.add_argument('--message', '-m', default='X 取得データを更新')
    pp.add_argument('--no-git', action='store_true', help='ファイルを書くだけで commit/push しない')
    pl = sub.add_parser('pull')
    pl.add_argument('--force', action='store_true', help='work 側に同名があっても上書き')
    args = p.parse_args()
    {'status': cmd_status, 'push': cmd_push, 'pull': cmd_pull}[args.cmd](args)


if __name__ == '__main__':
    main()
