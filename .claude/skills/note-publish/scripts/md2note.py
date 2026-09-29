#!/usr/bin/env python3
"""note 投稿用: 原稿 Markdown からタイトルと本文 HTML を作る（note の編集画面に paste する用）。

    python .claude/skills/note-publish/scripts/md2note.py articles/…/原稿.md > out.json
    python .claude/skills/note-publish/scripts/md2note.py 原稿.md --html-only    # HTML 文字列だけ（JSON 文字列）

出力 JSON: {"title", "html", "stats"}。html は javascript_tool で paste イベントに渡す。

変換の決めごと（2026-09-29 に note の編集画面で確かめた挙動に合わせてある）:
- 先頭の `# ` がタイトル。本文には入れない（タイトル欄に別で入れる）
- HTML コメント（入稿メモ）と「## 編集メモ」以降は落とす
- `> ` は引用ブロック。全記事共通の注意書きもこれ
- 単独行の URL は <p>URL</p> のまま残す（あとで embedBatch がカードにする）
- 【画像…】の行は <p> のまま残す（あとで pasteImgAt が画像に差し替える）
- 【Xポスト埋め込み…】の行は落とす（直後の URL がカードになるので目印は不要）
- 見出し画像の目印（既定「【画像①: 見出し画像】」）は落とす。見出し画像は別の手順で入れる
- 入れ子の箇条書き（2スペース字下げ）、番号付きリスト、**太字**、[文字](URL)、文中の URL をリンクに
- `コード` はバッククォートを外すだけ（note では記号がそのまま出るため）。*斜体* も記号を外す
"""
import argparse
import html
import json
import re
import sys


def inline(t: str) -> str:
    t = html.escape(t, quote=False)
    t = re.sub(r'`([^`]+)`', r'\1', t)
    t = re.sub(r'\[([^\]]+)\]\((https?://[^)\s]+)\)', r'<a href="\2">\1</a>', t)
    t = re.sub(r'(?<!href=")(?<!">)(https?://[^\s<）」]+)', r'<a href="\1">\1</a>', t)
    t = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', t)
    t = re.sub(r'(?<![*\w])\*([^*\n]+?)\*(?![*\w])', r'\1', t)
    return t


def convert(src: str, header_mark: str) -> tuple[str, str]:
    src = re.sub(r'<!--.*?-->', '', src, flags=re.S)
    src = re.split(r'^## 編集メモ', src, flags=re.M)[0]
    lines = src.split('\n')
    h1 = next(i for i, l in enumerate(lines) if l.startswith('# '))
    title = lines[h1][2:].strip()
    body = [l for l in lines[h1 + 1:]
            if not l.strip().startswith('【Xポスト埋め込み') and l.strip() != header_mark]

    out: list[str] = []
    para: list[str] = []
    items: list[tuple[int, str, str]] = []  # (level, kind ul/ol, text)

    def flush_para() -> None:
        nonlocal para
        if para:
            out.append('<p>' + ''.join(inline(x) for x in para) + '</p>')
            para = []

    def flush_list() -> None:
        nonlocal items
        if not items:
            return
        h, stack = '', []  # stack: [(level, kind)]
        for lvl, kind, txt in items:
            while stack and stack[-1][0] > lvl:
                h += f'</li></{stack.pop()[1]}>'
            if stack and stack[-1][0] == lvl:
                h += '</li><li>' + inline(txt)
            else:
                h += f'<{kind}><li>' + inline(txt)
                stack.append((lvl, kind))
        while stack:
            h += f'</li></{stack.pop()[1]}>'
        out.append(h)
        items = []

    for raw in body:
        l = raw.rstrip()
        s = l.strip()
        if not s or s == '---':
            flush_para(); flush_list(); continue
        m = re.match(r'^(#{2,3}) (.*)', l)
        if m:
            flush_para(); flush_list()
            n = len(m.group(1))
            out.append(f'<h{n}>{inline(m.group(2))}</h{n}>')
            continue
        if l.startswith('> '):
            flush_para(); flush_list()
            out.append(f'<blockquote><p>{inline(l[2:])}</p></blockquote>')
            continue
        m = re.match(r'^( *)(- |\d+\. )(.*)', l)
        if m:
            flush_para()
            items.append((len(m.group(1)) // 2, 'ul' if m.group(2) == '- ' else 'ol', m.group(3)))
            continue
        if items and raw.startswith('  '):
            lvl, kind, txt = items[-1]
            items[-1] = (lvl, kind, txt + s)
            continue
        if re.match(r'^https?://\S+$', s) or s.startswith('【画像'):
            flush_para(); flush_list()
            out.append('<p>' + html.escape(s) + '</p>')
            continue
        flush_list()
        para.append(s)
    flush_para(); flush_list()
    return title, ''.join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('markdown')
    ap.add_argument('--header-mark', default='【画像①: 見出し画像】', help='見出し画像の目印（本文から落とす行）')
    ap.add_argument('--html-only', action='store_true', help='HTML を JSON 文字列として出す（javascript_tool に貼る用）')
    args = ap.parse_args()
    title, body = convert(open(args.markdown, encoding='utf-8').read(), args.header_mark)
    stats = {
        'chars': len(body),
        'card_urls': len(re.findall(r'<p>https?://[^<]+</p>', body)),
        'image_marks': re.findall(r'<p>(【画像[^<]*)</p>', body),
        'links': body.count('<a href'),
        'blockquotes': body.count('<blockquote>'),
    }
    if args.html_only:
        print(json.dumps(body, ensure_ascii=False))
    else:
        print(json.dumps({'title': title, 'html': body, 'stats': stats}, ensure_ascii=False))
    print(json.dumps(stats, ensure_ascii=False), file=sys.stderr)


if __name__ == '__main__':
    main()
