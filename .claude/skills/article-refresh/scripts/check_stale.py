"""公開済み note 記事のうち、更新から時間が経ったものを一覧する（article-refresh の見落とし防止）。

articles/公開一覧.md の表（シリーズ／記事ファイル／note URL／公開日／最終同期日／備考）を読み、
「最終同期日」（無ければ「公開日」）から --days 日以上経った行を表示する。判定するだけで、
記事にも公開一覧.md にも書き込まない。

イベント駆動（メンバーの加入・卒業／新曲リリース／コール表の更新／ワンマン等の大きな公演／
料金・会場ルールの変更）だけだと見落としがちなので、.claude/skills/weekly-pipeline の
finish 段からも呼ばれる（存在すれば呼ぶ・情報表示のみでパイプラインを止めない）。

使い方:
    python .claude/skills/article-refresh/scripts/check_stale.py
    python .claude/skills/article-refresh/scripts/check_stale.py --days 30
    python .claude/skills/article-refresh/scripts/check_stale.py --json

exit code は常に 0（情報表示のみで、パイプラインを止めない）。
"""
import argparse
import json
import os
import re
from datetime import date

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

LIST_PATH = os.path.join('articles', '公開一覧.md')


def find_col(headers, keyword):
    for h in headers:
        if keyword in h:
            return h
    return None


def parse_table(path):
    """公開一覧.md の中から「シリーズ」「URL」を含むヘッダの表を1つ拾い、行を辞書のリストにする。

    見つからない・読めないときは (None, エラーメッセージ) を返す（例外を投げて呼び出し側を
    落とさないため）。
    """
    if not os.path.exists(path):
        return None, f"{path} が無い"

    with open(path, encoding='utf-8') as f:
        lines = f.readlines()

    header_idx = None
    headers = []
    for i, line in enumerate(lines):
        s = line.strip()
        if s.startswith('|') and 'シリーズ' in s and 'URL' in s:
            headers = [c.strip() for c in s.strip('|').split('|')]
            header_idx = i
            break
    if header_idx is None:
        return None, f"{path} に表が見つからない（「シリーズ」「URL」を含む | 区切りのヘッダ行が無い）"

    rows = []
    for line in lines[header_idx + 2:]:  # ヘッダの次は区切り線（--- ...）なので、その次から
        s = line.strip()
        if not s.startswith('|'):
            break
        cells = [c.strip() for c in s.strip('|').split('|')]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return {'headers': headers, 'rows': rows}, None


def parse_date(s):
    s = (s or '').strip().strip('`')
    m = re.match(r'^(\d{4})-(\d{2})-(\d{2})$', s)
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def classify(rows, headers, days, today):
    col_series = find_col(headers, 'シリーズ')
    col_file = find_col(headers, '記事ファイル')
    col_url = find_col(headers, 'URL')
    col_published = find_col(headers, '公開日')
    col_synced = find_col(headers, '最終同期日')
    col_note = find_col(headers, '備考')

    stale, unrecorded, ok = [], [], []

    for row in rows:
        series = row.get(col_series, '') if col_series else ''
        article = row.get(col_file, '') if col_file else ''
        url = row.get(col_url, '') if col_url else ''
        note = row.get(col_note, '') if col_note else ''

        if not url or url == '-':
            unrecorded.append({'series': series, 'file': article, 'note': note})
            continue

        base_str = row.get(col_synced, '') if col_synced else ''
        base = parse_date(base_str)
        used_fallback = False
        if base is None:
            base_str = row.get(col_published, '') if col_published else ''
            base = parse_date(base_str)
            used_fallback = True

        if base is None:
            unrecorded.append({'series': series, 'file': article,
                                'note': f"日付が読めない（最終同期日・公開日とも空欄か不正な形式）"})
            continue

        elapsed = (today - base).days
        entry = {
            'series': series, 'file': article, 'url': url,
            'base_date': base.isoformat(), 'base_is_fallback_published_date': used_fallback,
            'elapsed_days': elapsed,
        }
        (stale if elapsed >= days else ok).append(entry)

    stale.sort(key=lambda e: -e['elapsed_days'])
    return stale, unrecorded, ok


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--days', type=int, default=60, help='この日数以上経った記事を「stale」とする（既定 60）')
    p.add_argument('--json', action='store_true', help='JSON で出力する')
    args = p.parse_args()

    today = date.today()
    table, err = parse_table(LIST_PATH)

    if err:
        if args.json:
            print(json.dumps({'checked_at': today.isoformat(), 'error': err}, ensure_ascii=False, indent=2))
        else:
            print(f"article-refresh check_stale: {err}")
        return  # exit code は常に0

    stale, unrecorded, ok = classify(table['rows'], table['headers'], args.days, today)

    if args.json:
        print(json.dumps({
            'checked_at': today.isoformat(),
            'threshold_days': args.days,
            'stale': stale,
            'unrecorded': unrecorded,
            'ok_count': len(ok),
        }, ensure_ascii=False, indent=2))
        return

    print(f"公開一覧チェック（{LIST_PATH}、{today.isoformat()} 時点、閾値 {args.days} 日）")

    print(f"\n## 最終同期日から{args.days}日以上（{len(stale)}件）")
    if stale:
        for e in stale:
            fallback = "（最終同期日が空欄のため公開日で代用）" if e['base_is_fallback_published_date'] else ''
            print(f"- {e['series']} / {e['file'] or '-'} / {e['url']} / 経過{e['elapsed_days']}日"
                  f"（基準日 {e['base_date']}{fallback}）")
    else:
        print("該当なし")

    print(f"\n## URL 未記録（{len(unrecorded)}件）")
    if unrecorded:
        for e in unrecorded:
            note = f"（{e['note']}）" if e.get('note') else ''
            print(f"- {e['series']} / {e['file'] or '-'} {note}")
    else:
        print("該当なし")

    print(f"\n最終同期日から{args.days}日未満: {len(ok)}件")


if __name__ == '__main__':
    main()
