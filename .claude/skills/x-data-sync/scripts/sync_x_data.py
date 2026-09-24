"""X の取得データ（work/x_fetch/*.jsonl）を、非公開のデータリポジトリと往復させる。

リモートの Claude Code はコンテナが使い捨てで、.gitignore 対象の work/x_fetch/ は次のセッションで消える。
他人の投稿の原文は公開リポジトリ（lollpop_docs）に入れない方針なので、非公開リポジトリ lollpop_data に
「必要な項目だけに絞った圧縮版」を置き、セッション開始時に復元する。

  push   work/x_fetch/*.jsonl → <data>/x/（項目を絞る）。commit と push まで行う
  pull   <data>/x/ → work/x_fetch/*.jsonl（既存のスクリプトが読める形に戻す）。無いものだけ復元
  status 両側にあるファイルと件数を並べる

データ側の置き方:
  - 名前に期間が入っていないファイル（公式・メンバーのアカウント別）は月ごとに分ける: x/<handle>/YYYY-MM.jsonl.gz
    毎朝の自動退避（タスクスケジューラ）で毎日 push するため。過去の月は変わらないので、毎日コミットされるのは当月分だけ
  - egosearch_<期間> / hashtags_YYYY-MM は既に期間で分かれているので x/<name>.jsonl.gz のまま
  - push は上書きではなく「データ側の既存行 ＋ work の行」の ID での和集合。同じ ID は work 側を採る。退避で行は減らない
  - gzip は時刻を入れずに書き、中身が同じなら書き換えない（変わっていないファイルをコミットしないため）

データリポジトリの場所は環境変数 LOLLPOP_DATA_DIR（既定: リポジトリの隣の ../lollpop_data）。
無ければ `git clone https://github.com/devhitoshi/lollpop_data ../lollpop_data`（リモート環境では先に add_repo）。

使い方:
    python3 .claude/skills/x-data-sync/scripts/sync_x_data.py status
    python3 .claude/skills/x-data-sync/scripts/sync_x_data.py push
    python3 .claude/skills/x-data-sync/scripts/sync_x_data.py push --log work/x_fetch/logs/daily_data_push.log  # 毎朝のタスク
    python3 .claude/skills/x-data-sync/scripts/sync_x_data.py pull
"""
import argparse
import glob
import gzip
import io
import json
import os
import re
import subprocess
import sys
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

WORK = 'work/x_fetch'
DATA_DIR = os.environ.get('LOLLPOP_DATA_DIR') or os.path.abspath(os.path.join(project_root, '..', 'lollpop_data'))
DATA_SUB = 'x'
DAILY_STATE = os.path.join(WORK, '.daily_state.json')
# 保存する項目。下流のスクリプト（build_material / triage / profile_stats / check_event_consistency / collect_metrics）が読むもの
KEEP = ('id', 'url', 'text', 'createdAt', 'likeCount', 'retweetCount', 'replyCount', 'quoteCount', 'viewCount',
        'bookmarkCount', 'isReply', 'inReplyToId', 'lang', '_queries')
# メディアは slim_media() で URL・寸法・動画の変種まで残す（x-media-collect の索引を作り直せるように）
MONTHS = {'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04', 'May': '05', 'Jun': '06',
          'Jul': '07', 'Aug': '08', 'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'}


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


def is_partitioned(name):
    """名前に期間（YYYY-MM）が無いファイル＝アカウント別の累積ファイル。データ側では月ごとに分ける。"""
    return not re.search(r'\d{4}-\d{2}', name)


def month_of(s):
    """投稿の月（YYYY-MM）。createdAt（例: Wed Sep 23 10:00:00 +0000 2026）の表記どおりに取る（fetch_accounts.tweet_date と同じ）。"""
    m = re.search(r'\w{3} (\w{3}) \d{2} .* (\d{4})', s.get('createdAt') or '')
    return f"{m.group(2)}-{MONTHS[m.group(1)]}" if m and m.group(1) in MONTHS else 'unknown'


def sort_key(s):
    # ID はスノーフレーク（時系列に増える数値）。並びを毎回同じにして、書き直しても差分が出ないようにする
    i = str(s.get('id') or '')
    return (len(i), i)


def read_gz(path):
    with gzip.open(path, 'rt', encoding='utf-8') as g:
        return [json.loads(line) for line in g if line.strip()]


def write_gz_if_changed(path, rows):
    """時刻とファイル名をヘッダに入れずに圧縮し、既存と同じバイト列なら書かない。戻り値は書いたかどうか。"""
    buf = io.BytesIO()
    with gzip.GzipFile(filename='', mode='wb', fileobj=buf, mtime=0) as g:
        for s in rows:
            g.write((json.dumps(s, ensure_ascii=False) + '\n').encode('utf-8'))
    data = buf.getvalue()
    if os.path.exists(path):
        with open(path, 'rb') as f:
            if f.read() == data:
                return False
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    return True


def data_path():
    d = os.path.join(DATA_DIR, DATA_SUB)
    if not os.path.isdir(DATA_DIR):
        sys.exit(f"データリポジトリが無い: {DATA_DIR}\n  git clone https://github.com/devhitoshi/lollpop_data {DATA_DIR}"
                 "（リモート環境では先に add_repo で devhitoshi/lollpop_data を取り込む）")
    os.makedirs(d, exist_ok=True)
    return d


def data_sources(d, name):
    """データ側で name（例: mana_lpop.jsonl）に当たる gz ファイル。月ごとのファイルと、分ける前の旧ファイルの両方。"""
    stem = name[:-len('.jsonl')]
    paths = sorted(glob.glob(os.path.join(d, stem, '*.jsonl.gz')))
    legacy = os.path.join(d, name + '.gz')
    if os.path.exists(legacy):
        paths.append(legacy)
    return paths


def data_names(d):
    """データ側にある論理ファイル名（work 側の名前: <name>.jsonl）の一覧。"""
    names = {os.path.basename(p)[:-3] for p in glob.glob(os.path.join(d, '*.jsonl.gz'))}
    names |= {os.path.basename(os.path.dirname(p)) + '.jsonl' for p in glob.glob(os.path.join(d, '*', '*.jsonl.gz'))}
    return sorted(names)


def count_lines(path, opener=open):
    n = 0
    with opener(path, 'rt', encoding='utf-8') as f:
        for _ in f:
            n += 1
    return n


def git(*args, check=True):
    return subprocess.run(['git', *args], cwd=DATA_DIR, capture_output=True, text=True, encoding='utf-8', check=check)


def cmd_status(_):
    print(f"work: {WORK}")
    for p in sorted(glob.glob(os.path.join(WORK, '*.jsonl'))):
        print(f"  {os.path.basename(p):55s} {count_lines(p):>6} 件")
    if not os.path.isdir(DATA_DIR):
        print(f"data: {DATA_DIR}（無い）")
        return 0
    d = os.path.join(DATA_DIR, DATA_SUB)
    print(f"data: {d}")
    for name in data_names(d):
        paths = data_sources(d, name)
        n = sum(count_lines(p, gzip.open) for p in paths)
        where = f"{len(paths)} ファイル（月ごと）" if len(paths) > 1 or os.path.dirname(paths[0]) != d else ''
        print(f"  {name:55s} {n:>6} 件 {where}")
    return 0


def merge_one(d, name, work_path):
    """データ側の既存行と work の行を ID で和集合にして書く。戻り値は (合計件数, 新規件数, 書いたファイル数, 消した旧ファイル数)。"""
    rows, no_id = {}, 0
    for p in data_sources(d, name):
        for s in read_gz(p):
            if s.get('id'):
                rows[str(s['id'])] = s
    before = len(rows)
    with open(work_path, encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                s = slim(json.loads(line))
            except json.JSONDecodeError:
                continue
            if not s.get('id'):
                no_id += 1
                continue
            rows[str(s['id'])] = s  # 同じ ID は work 側（取得し直した新しい数値）を採る
    if no_id:
        print(f"  {name}: ID の無い行 {no_id} 件は保存しない")
    ordered = sorted(rows.values(), key=sort_key)

    written, removed = 0, 0
    if is_partitioned(name):
        stem = name[:-len('.jsonl')]
        by_month = {}
        for s in ordered:
            by_month.setdefault(month_of(s), []).append(s)
        for month, ms in by_month.items():
            written += write_gz_if_changed(os.path.join(d, stem, f"{month}.jsonl.gz"), ms)
        legacy = os.path.join(d, name + '.gz')
        if os.path.exists(legacy):  # 月ごとに分けたので、分ける前の 1 ファイル版は消す（git の履歴には残る）
            os.remove(legacy)
            removed += 1
    else:
        written += write_gz_if_changed(os.path.join(d, name + '.gz'), ordered)
    return len(ordered), len(ordered) - before, written, removed


def default_message():
    try:
        with open(DAILY_STATE, encoding='utf-8') as f:
            until = json.load(f).get('last_until')
        if until:
            return f"X 取得データを更新（毎日取得: {until} まで）"
    except (OSError, json.JSONDecodeError):
        pass
    return 'X 取得データを更新'


def cmd_push(args):
    d = data_path()
    if not args.no_git:
        # クラウドのセッションが先に push していることがあるので、取り込んでから和集合を取る
        r = git('pull', '--ff-only', '-q', check=False)
        if r.returncode != 0:
            print(f"データリポジトリの pull に失敗。退避を中止する（次回やり直す）: {r.stderr.strip()[-300:]}")
            return 1

    works = [p for p in sorted(glob.glob(os.path.join(WORK, '*.jsonl')))
             if not ('triage' in os.path.basename(p) and 'final' in os.path.basename(p))]  # 判定後の抜粋は再生成できる
    if not works:
        print("push するファイルが無い")
        return 0
    for p in works:
        name = os.path.basename(p)
        total, new, written, removed = merge_one(d, name, p)
        note = f"新規 {new:>4} 件 / 書いた {written} ファイル" + (f" / 旧ファイルを {removed} 個削除" if removed else '')
        print(f"  {name:50s} {total:>6} 件（{note}）")

    if args.no_git:
        return 0
    if not git('status', '--porcelain').stdout.strip():
        print("データリポジトリに変更なし")
        return 0
    git('add', '-A')
    git('commit', '-q', '-m', args.message or default_message())
    r = git('push', check=False)
    if r.returncode != 0:
        print(f"push 失敗（コミットは残っている。次回の push で一緒に送られる）: {r.stderr.strip()[-300:]}")
        return 1
    print("push 済み")
    return 0


def cmd_pull(args):
    d = data_path()
    os.makedirs(WORK, exist_ok=True)
    restored = []
    for name in data_names(d):
        out = os.path.join(WORK, name)
        if os.path.exists(out) and not args.force:
            continue
        rows = {}
        for p in data_sources(d, name):
            for s in read_gz(p):
                rows[str(s.get('id'))] = s
        with open(out, 'w', encoding='utf-8') as f:
            for s in sorted(rows.values(), key=sort_key):
                f.write(json.dumps(fat(s), ensure_ascii=False) + '\n')
        restored.append((name, len(rows)))
    for name, n in restored:
        print(f"  復元 {name:50s} {n:>6} 件")
    if not restored:
        print("復元するものが無い（既にある、またはデータ側が空。--force で上書き）")
    print("注意: 復元したデータは項目を絞った版。本文・日時・投稿者・反応数・メディアの URL と寸法は残るが、"
          "\n      プロフィールの詳細と、動画の低ビットレート版は含まない")
    return 0


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest='cmd', required=True)
    sub.add_parser('status')
    pp = sub.add_parser('push')
    pp.add_argument('--message', '-m', help='コミットメッセージ（省略時は毎日取得の到達日から作る）')
    pp.add_argument('--no-git', action='store_true', help='ファイルを書くだけで pull/commit/push しない')
    pp.add_argument('--log', help='出力をこのファイルに追記する（タスクスケジューラの pythonw は標準出力が無いため）')
    pl = sub.add_parser('pull')
    pl.add_argument('--force', action='store_true', help='work 側に同名があっても上書き')
    args = p.parse_args()

    if getattr(args, 'log', None):
        os.makedirs(os.path.dirname(args.log) or '.', exist_ok=True)
        sys.stdout = sys.stderr = open(args.log, 'a', encoding='utf-8')
        print(f"\n===== {datetime.now().isoformat(timespec='seconds')} sync_x_data {args.cmd} =====")
    try:
        return {'status': cmd_status, 'push': cmd_push, 'pull': cmd_pull}[args.cmd](args)
    except subprocess.CalledProcessError as e:
        print(f"git が失敗: {' '.join(e.cmd)}\n{(e.stderr or '').strip()[-300:]}")
        return 1
    finally:
        sys.stdout.flush()


if __name__ == '__main__':
    sys.exit(main())
