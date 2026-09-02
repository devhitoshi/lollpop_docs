"""許諾済みの素材だけをダウンロードする（縦型動画の素材用）。

`data/x/media_permissions.md` の表で「OK」と記録されているアカウントの分だけを、索引 CSV から落とす。
記録に無いアカウントは落とさない。**許諾の記録が唯一の判断基準**で、コマンドラインで上書きできないようにしてある
（「今回だけ」で記録の無い素材が混ざるのを防ぐため。許諾を得たら先に permissions.md に足す）。

出力: work/x_media/<日付>_<アカウント>_<投稿ID>_<n>.<拡張子>（.gitignore 済み。リポジトリに入れない）
     work/x_media/manifest.csv … ファイルと出典（投稿URL・撮影者・公演）の対応。クレジット表記に使う

使い方:
    python3 .claude/skills/x-media-collect/scripts/fetch_media.py --index data/x/media_index_2026-08-01_2026-08-31.csv --dry-run
    python3 ... --index <csv> --orientation 縦 --type video
"""
import argparse
import csv
import os
import re
import sys
import time
import urllib.error
import urllib.request

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

PERMISSIONS = 'data/x/media_permissions.md'
OUT_DIR = 'work/x_media'
OFFICIAL = 'lollipop_1116'
UA = 'Mozilla/5.0 (compatible; lollpop-docs/1.0)'


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--index', required=True, help='build_media_index.py が作った CSV')
    p.add_argument('--orientation', choices=['縦', '横', '正方形'])
    p.add_argument('--type', dest='mtype', choices=['photo', 'video'])
    p.add_argument('--source', choices=['公式', 'メンバー', '他人'], help='この出どころだけ')
    p.add_argument('--date', help='この日付だけ YYYY-MM-DD（カンマ区切りで複数可）')
    p.add_argument('--post-id', help='この投稿だけ（カンマ区切りで複数可）。1本の動画を狙って落とすとき用')
    p.add_argument('--limit', type=int, help='件数の上限（試すとき用）')
    p.add_argument('--max-total-mb', type=int, default=2000,
                   help='今回の実行で落とす合計サイズの上限 MB（既定 2000）。超えたら打ち切る。'
                        '4K の動画は1本 300MB 近くあるので、まず --dry-run で概算を見る')
    p.add_argument('--dry-run', action='store_true', help='落とさずに対象を表示するだけ')
    p.add_argument('--out', default=OUT_DIR)
    return p.parse_args()


HANDLE = re.compile(r'@([A-Za-z0-9_]{1,15})')


def allowed_handles():
    """permissions.md の表から、可否が OK の行に出てくるアカウントをすべて読む。

    行のどの列に書かれていても拾う（「メンバー個人アカウントの投稿」の行のように、
    対象欄が日本語でハンドルがメモ欄に並ぶ書き方も許諾として効かせるため）。
    可否が OK 以外（「都度」「未確認」など）の行のハンドルは対象にしない。
    """
    if not os.path.exists(PERMISSIONS):
        sys.exit(f"{PERMISSIONS} が無い。許諾を記録してから実行する")
    ok, other = set(), []
    for line in open(PERMISSIONS, encoding='utf-8'):
        cells = [c.strip() for c in line.split('|')]
        if len(cells) < 4:
            continue          # 表の行ではない（箇条書きや本文）
        verdict = cells[2]
        handles = [h.lower() for h in HANDLE.findall(line)]
        if not handles or verdict in ('可否', '---'):
            continue
        if verdict == 'OK':
            ok.update(handles)
        else:
            other += [(h, verdict) for h in handles]
    return ok, [o for o in other if o[0] not in ok]


# 実測（2026-09-02、この索引の素材で計測）: 3840x2160 の mp4 が 88秒で 282MB ＝ 約 3.2 MB/秒。
# ビットレートは解像度におおむね比例するので、画素数で按分して概算する。写真は元解像度で 0.8MB 前後。
MB_PER_SEC_4K = 3.2
PIXELS_4K = 3840 * 2160


def est_mb(row):
    """1件あたりの概算サイズ（MB）。--dry-run の見積もりと、落とす前の判断に使う。"""
    if row['type'] != 'video':
        return 0.8
    secs = int(row['duration_s']) if row['duration_s'] else 30
    try:
        px = int(row['width']) * int(row['height'])
    except (ValueError, TypeError):
        px = 1920 * 1080
    return secs * MB_PER_SEC_4K * max(px / PIXELS_4K, 0.08)


def ext_for(row):
    url = row['best_mp4'] or row['media_url']
    m = re.search(r'\.(mp4|jpg|jpeg|png|gif)(?:\?|$)', url)
    return m.group(1) if m else ('mp4' if row['type'] == 'video' else 'jpg')


class EmptyDownload(Exception):
    """0バイト、または Content-Length に足りない応答。成功扱いにしない。"""


def download(url, path):
    """1件を落とす。中身が空・途中で切れたものは例外にして、壊れたファイルを残さない。"""
    req = urllib.request.Request(url, headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=300) as r, open(path, 'wb') as f:
        expected = r.headers.get('Content-Length')
        expected = int(expected) if expected and expected.isdigit() else None
        got = 0
        while True:
            chunk = r.read(1024 * 256)
            if not chunk:
                break
            f.write(chunk)
            got += len(chunk)
    if got == 0:
        raise EmptyDownload('応答が空（0バイト）')
    if expected is not None and got < expected:
        raise EmptyDownload(f'途中で切れた（{got}/{expected} バイト）')
    return got


def main():
    args = parse_args()
    ok, other = allowed_handles()
    if not ok:
        sys.exit(f"{PERMISSIONS} に「OK」のアカウントが無い")

    rows = list(csv.DictReader(open(args.index, encoding='utf-8')))
    if args.orientation:
        rows = [r for r in rows if r['orientation'] == args.orientation]
    if args.mtype:
        rows = [r for r in rows if r['type'] == args.mtype]
    if args.source:
        rows = [r for r in rows if r['source'] == args.source]
    if args.date:
        days = set(args.date.split(','))
        rows = [r for r in rows if r['date'] in days]
    if args.post_id:
        ids = set(args.post_id.split(','))
        rows = [r for r in rows if r['post_url'].rsplit('/', 1)[-1] in ids]

    permitted = [r for r in rows if r['author'].lower() in ok]
    skipped = [r for r in rows if r['author'].lower() not in ok]
    by_skipped = {}
    for r in skipped:
        by_skipped[r['author']] = by_skipped.get(r['author'], 0) + 1

    print(f"許諾済み: {', '.join(sorted(ok))}")
    if other:
        print("記録はあるが OK ではない: " + ', '.join(f"@{h}（{v}）" for h, v in other))
    print(f"対象 {len(permitted)} 件 / 索引の絞り込み後 {len(rows)} 件")
    if by_skipped:
        top = sorted(by_skipped.items(), key=lambda x: -x[1])[:8]
        print(f"許諾の記録が無いので落とさない: {len(skipped)} 件（{len(by_skipped)} 人）"
              " 例: " + ', '.join(f"@{h}×{n}" for h, n in top))
        print("  使いたいものがあれば、撮影者に依頼して data/x/media_permissions.md に追記する")

    if args.limit:
        permitted = permitted[:args.limit]
    if args.dry_run:
        for r in permitted[:20]:
            print(f"  [dry] {r['date']} @{r['author']:18s} {r['type']:5s} {r['orientation']} "
                  f"{r['width']}x{r['height']} {r['duration_s'] and str(r['duration_s'])+'秒'}")
        n_v = sum(1 for r in permitted if r['type'] == 'video')
        secs = sum(int(r['duration_s']) for r in permitted if r['duration_s'])
        est = sum(est_mb(r) for r in permitted)
        print(f"（--dry-run。{len(permitted)} 件が対象。写真 {len(permitted) - n_v} / 動画 {n_v}・計 {secs // 60}分{secs % 60}秒）")
        print(f"  概算 {est:.0f} MB。--max-total-mb（既定 {args.max_total_mb}）を超えると打ち切る")
        return

    os.makedirs(args.out, exist_ok=True)
    manifest_path = os.path.join(args.out, 'manifest.csv')
    have = set()
    if os.path.exists(manifest_path):
        have = {r['file'] for r in csv.DictReader(open(manifest_path, encoding='utf-8'))}
    fields = ['file', 'date', 'source', 'author', 'event', 'type', 'orientation', 'width', 'height',
              'duration_s', 'post_url', 'media_url', '許諾']
    new_rows, ok_n, fail_n, skip_n, total_bytes = [], 0, 0, 0, 0
    cap = args.max_total_mb * 1024 * 1024
    seq = {}
    for r in permitted:
        pid = r['post_url'].rsplit('/', 1)[-1]
        seq[pid] = seq.get(pid, 0) + 1
        name = f"{r['date']}_{r['author']}_{pid}_{seq[pid]}.{ext_for(r)}"
        path = os.path.join(args.out, name)
        if name in have:
            skip_n += 1
            continue
        if os.path.exists(path):
            # 落とし直さないが、出典の対応表には残す（クレジットの根拠を欠かさない）
            skip_n += 1
            new_rows.append({**{k: r.get(k, '') for k in fields if k in r}, 'file': name,
                             '許諾': 'permissions.md'})
            continue
        url = r['best_mp4'] or r['media_url']
        if r['type'] == 'photo' and r['media_url']:
            url = r['media_url'] + '?name=orig'   # 元解像度で取る
        try:
            size = download(url, path)
            ok_n += 1
            total_bytes += size
            print(f"  取得 {name}  {size/1024/1024:.1f} MB（累計 {total_bytes/1024/1024:.0f} MB）")
        except (urllib.error.URLError, urllib.error.HTTPError, OSError, EmptyDownload) as e:
            fail_n += 1
            print(f"  失敗 {name}: {e}")
            if os.path.exists(path):
                os.remove(path)
            continue
        new_rows.append({**{k: r.get(k, '') for k in fields if k in r}, 'file': name,
                         '許諾': 'permissions.md'})
        if total_bytes >= cap:
            print(f"  合計 {total_bytes/1024/1024:.0f} MB が上限（--max-total-mb {args.max_total_mb}）に達したので打ち切る。"
                  "\n  続きは同じコマンドで再実行すると、取得済みを飛ばして続きから落とす")
            break
        time.sleep(0.3)

    if new_rows:
        exists = os.path.exists(manifest_path)
        with open(manifest_path, 'a', encoding='utf-8', newline='') as f:
            w = csv.DictWriter(f, fieldnames=fields)
            if not exists:
                w.writeheader()
            w.writerows(new_rows)
    print(f"\n取得 {ok_n}（{total_bytes/1024/1024:.0f} MB）/ 既にある {skip_n} / 失敗 {fail_n} → {args.out}")
    print(f"出典の対応表: {manifest_path}（クレジット表記に使う）")
    print("注意: work/x_media/ は .gitignore 済み。他人の著作物なのでリポジトリに入れない・再配布しない")


if __name__ == '__main__':
    main()
