"""収集データ Markdown（prompts/x_collect.md の出力形式）の読み取り。

merge_collect.py と archive_collect.py から使う。
"""
import re

# prompts/x_collect.md の出力形式に対応。この順で出力する。
SECTIONS = [
    'ライブ・イベント',
    '新曲・初披露',
    'アナウンス・告知',
    'メンバーの投稿',
    '外部の反応',
    '今後の予定',
    '確認できなかった項目',
    '判断に迷った点',
]
# 出力の末尾側にある節。欠けていたら打ち切りを疑う。
TAIL_SECTIONS = {'今後の予定', '確認できなかった項目', '判断に迷った点'}

DATE_RE = re.compile(r'(\d{4}-\d{2}-\d{2})')


def norm_key(text):
    """重複判定用のキー。表記そのものは絶対に書き換えない（キーだけ正規化）。"""
    return re.sub(r'\s+', ' ', text.strip()).casefold()


def first_date(text):
    m = DATE_RE.search(text)
    return m.group(1) if m else None


def parse_chunk(path):
    """収集データ Markdown を {節名: 本文行リスト} に分解する。"""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.read().replace('\r\n', '\n').split('\n')

    sections, order, current = {}, [], None
    title = None
    for line in lines:
        if line.startswith('# ') and title is None and current is None:
            title = line[2:].strip()
            continue
        m = re.match(r'^##\s+(.+?)\s*$', line)
        if m and not line.startswith('###'):
            current = m.group(1)
            if current not in sections:
                sections[current] = []
                order.append(current)
            continue
        if current is not None:
            sections[current].append(line)

    return {'path': path, 'title': title, 'sections': sections, 'order': order}


def split_entries(body):
    """本文を `### ` 見出しごとのブロックに割る。見出し前の行は前文として返す。"""
    preamble, entries, current = [], [], None
    for line in body:
        if line.startswith('### '):
            if current:
                entries.append(current)
            current = {'heading': line, 'lines': []}
        elif current is None:
            preamble.append(line)
        else:
            current['lines'].append(line)
    if current:
        entries.append(current)
    return preamble, entries


def strip_blanks(lines):
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def is_absent(body):
    """節の中身が `なし` だけ（＝該当なし）かどうか。"""
    text = '\n'.join(strip_blanks(list(body))).strip()
    return text in ('なし', '- なし', 'なし。', '')
