"""note記事の機械チェック（article-review エージェントの下請け）。

記事1本を読み、リポジトリの資料と突き合わせて「人（またはエージェント）が判断すべき箇所」を列挙する。
自動では直さない。判定の根拠になる資料:

- prompts/write/style_ai_poppar.md  … 文体ルール（! の連打、オタク語彙の回数、絵文字）
- prompts/write/weekly.md / monthly.md … 構成と読者（月刊は愛称の初出に本名、専門用語に注釈）
- articles/週刊まとめ/README.md     … note の制約（表組み不可・見出し2階層まで）
- members/members.md                 … 名前・あだ名・担当カラー・卒業メンバー
- songs/楽曲一覧.md                   … 曲名の正表記
- events/data_event.csv              … 期間内の公演（記事から抜けている公演を検出）

使い方:
    python3 .claude/skills/article-review/scripts/check_article.py articles/週刊まとめ/2026-08-25_2026-08-31.md
    python3 .claude/skills/article-review/scripts/check_article.py <記事> --type monthly
"""
import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, os.path.join(project_root, '.claude/skills/setlist-analysis/scripts'))
from song_names import load_canonical_songs  # noqa: E402

GROUP_NAME = 'ろりぽっぷ!!!!!!!'
OTAKU_WORDS = ['尊い', '無理', '助かる', '優勝', '解釈一致', '供給', '履修', '沼', '情緒', '語彙力']
JARGON = ['対バン', '特典会', '無銭', 'ワンマン', '生誕祭', 'チェキ', 'セトリ']
SENSITIVE = ['体調', '病', '療養', '入院', '休養', '運営', '事務所', '不仲', '揉め', '炎上',
             '動員', '売上', '集客', '勢い', '今行かないと', '後悔', '比べ']
SPECULATION = ['だろう', 'かもしれない', 'と思われる', 'おそらく', '推測', 'はずだ', 'に違いない']
COLOR_EMOJI = {'赤': '❤️', '黄': '💛', '水色': '🩵', '緑': '💚', '白': '🤍', 'ピンク': '🩷', '青': '💙'}
MEMBER_EMOJI = set(COLOR_EMOJI.values())
URL_RE = re.compile(r'https?://\S+')
QUOTE_RE = re.compile(r'「[^「」]*」|『[^『』]*』|“[^”]*”')


class Report:
    def __init__(self):
        self.items = []

    def add(self, level, code, message):
        self.items.append((level, code, message))

    def error(self, code, msg): self.add('ERROR', code, msg)
    def warn(self, code, msg): self.add('WARN', code, msg)
    def info(self, code, msg): self.add('INFO', code, msg)


# ---------- 資料の読み込み ----------

def load_members():
    """members.md から {name, aliases, nickname, emoji, graduated} のリストを作る。"""
    members = []
    graduated = False
    current = None
    with open('members/members.md', 'r', encoding='utf-8') as f:
        for line in f:
            if line.startswith('## '):
                graduated = '元メンバー' in line
                continue
            m = re.match(r'^### (.+)$', line.strip())
            if m:
                full = re.sub(r'（.*?）', '', m.group(1)).strip()
                current = {'name': full, 'aliases': {full, full.replace(' ', '')}, 'nickname': None,
                           'emoji': None, 'graduated': graduated}
                parts = full.split()
                if len(parts) == 2:
                    current['aliases'].add(parts[1])  # 名前だけ（くるみ、茉夢 など）
                members.append(current)
                continue
            if current is None:
                continue
            m = re.match(r'^- \*\*あだ名\*\*: (.+)$', line.strip())
            if m:
                nick = m.group(1).strip()
                current['nickname'] = nick
                current['aliases'].add(nick)
                current['aliases'].add(nick.replace('～', '').replace('〜', ''))
            m = re.match(r'^- \*\*担当カラー\*\*: (.+?)色?$', line.strip())
            if m:
                current['emoji'] = COLOR_EMOJI.get(m.group(1).strip())
    return members


def load_events(start, end):
    rows = []
    with open('events/data_event.csv', 'r', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            if start <= row['date'] <= end:
                rows.append(row)
    return rows


# ---------- 記事の分解 ----------

def split_body_memo(text):
    """本文と編集メモ（末尾の --- 以降で「編集メモ」を含む部分）に分ける。"""
    idx = None
    for m in re.finditer(r'^---\s*$', text, re.M):
        after = text[m.end():m.end() + 200]
        if '編集メモ' in after:
            idx = m.start()
    if idx is None:
        return text, ''
    return text[:idx], text[idx:]


def strip_quotes(text):
    """引用（「」『』）とURLを除いた本文。文体チェックは書き手自身の文だけに掛けたいので。"""
    text = URL_RE.sub('', text)
    return QUOTE_RE.sub('', text)


def snippet(text, pos, width=18):
    s = max(0, pos - width)
    e = min(len(text), pos + width)
    return text[s:e].replace('\n', ' ')


def detect_type(path):
    if '週刊' in path: return 'weekly'
    if '月刊' in path: return 'monthly'
    if '歌詞考察' in path: return 'lyrics'
    return 'generic'


def detect_period(path, kind):
    base = os.path.basename(path)
    if kind == 'weekly':
        m = re.match(r'(\d{4}-\d{2}-\d{2})_(\d{4}-\d{2}-\d{2})\.md$', base)
        if m: return m.group(1), m.group(2)
    if kind == 'monthly':
        m = re.match(r'(\d{4})-(\d{2})\.md$', base)
        if m: return f"{m.group(1)}-{m.group(2)}-01", f"{m.group(1)}-{m.group(2)}-31"
    return None, None


def date_variants(iso):
    d = datetime.strptime(iso, '%Y-%m-%d')
    return [f"{d.month}/{d.day}", f"{d.month:02d}/{d.day:02d}", f"{d.month}月{d.day}日"]


# ---------- 各チェック ----------

def check_note_constraints(body, rep):
    lines = body.splitlines()
    table_lines = [i + 1 for i, l in enumerate(lines) if l.strip().startswith('|')]
    if table_lines:
        rep.error('NOTE_TABLE', f"表組みがある（note は表を使えない。箇条書きに直す）: {table_lines[:5]} 行目")
    deep = [(i + 1, l.strip()[:40]) for i, l in enumerate(lines) if re.match(r'^#{3,}\s', l)]
    if deep:
        rep.error('NOTE_HEADING', f"見出しが3階層以上（note は2階層まで）: " + ', '.join(f"{n}行目「{t}」" for n, t in deep[:5]))


def check_group_name(plain, rep):
    for m in re.finditer(r'ろりぽっぷ([!！‼︎]+)', plain):
        marks = m.group(1)
        count = marks.count('!') + marks.count('！') + marks.count('‼') * 2
        if count != 7:
            rep.error('GROUP_NAME', f"グループ名の「!」が {count} 個（正は7個）: …{snippet(plain, m.start())}…")


def loose_song_pattern(song):
    """「!」の数・☆★・〜～・空白の違いを許した曲名パターン（表記ゆれの検出と除外に使う）。"""
    pat = re.escape(song)
    pat = re.sub(r'(\\!|！)+', '[!！]+', pat)
    pat = pat.replace('☆', '[☆★]').replace('★', '[☆★]')
    pat = pat.replace('〜', '[〜～]').replace('～', '[〜～]').replace('\\ ', '\\s*')
    return pat


def check_style(plain, kind, songs, rep):
    # 曲名・グループ名の「!」は（表記ゆれも含めて）除外してから連打を探す
    scrubbed = re.sub(r'ろりぽっぷ[!！‼︎]+', '', plain)
    for s in sorted(songs, key=len, reverse=True):
        scrubbed = re.sub(loose_song_pattern(s), '', scrubbed)
    for m in re.finditer(r'[!！]{2,}', scrubbed):
        rep.warn('EXCLAMATION', f"「!」の連打: …{snippet(scrubbed, m.start())}…")
    multi = [s for s in re.split(r'[。\n]', scrubbed) if len(re.findall(r'[!！]', s)) > 1]
    if multi:
        rep.warn('EXCLAMATION', f"1文に「!」が2個以上の文が {len(multi)} 文: 例「{multi[0].strip()[:40]}」")
    for pat, label in [(r'w{3,}', '「www」'), (r'[?？]{3,}', '「？？？」'), (r'\(´|ω|orz', '顔文字')]:
        for m in re.finditer(pat, scrubbed):
            rep.warn('KAOMOJI', f"{label} は使わない: …{snippet(scrubbed, m.start())}…")
    counts = {w: plain.count(w) for w in OTAKU_WORDS}
    used = {w: n for w, n in counts.items() if n}
    if kind == 'monthly':
        total = sum(used.values())
        if total > 4:
            rep.warn('OTAKU_WORDS', f"月刊はオタク語彙を記事全体で3〜4回まで。現在 {total} 回: {used}")
    else:
        over = {w: n for w, n in used.items() if n >= 3}
        if over:
            rep.warn('OTAKU_WORDS', f"同じオタク語彙を3回以上使っている: {over}")
    if used:
        rep.info('OTAKU_WORDS', f"オタク語彙の使用回数: {used}")


def check_members(body, plain, kind, members, rep):
    emoji_alt = '(?:' + '|'.join(re.escape(e) for e in sorted(MEMBER_EMOJI, key=len, reverse=True)) + ')'
    norm = lambda e: e.replace('\ufe0f', '')
    for mem in members:
        for alias in sorted(mem['aliases'], key=len, reverse=True):
            if not alias:
                continue
            for m in re.finditer(re.escape(alias) + r'\s*(' + emoji_alt + ')', body):
                if mem['emoji'] and norm(m.group(1)) != norm(mem['emoji']):
                    rep.error('MEMBER_EMOJI', f"{mem['name']} の担当カラーは {mem['emoji']}: …{snippet(body, m.start())}…")
        if mem['graduated']:
            hits = [a for a in mem['aliases'] if a and len(a) >= 3 and a in plain]
            if hits:
                rep.info('GRADUATED', f"卒業メンバー {mem['name']} への言及あり（在籍時の事実のみか、卒業後の活動・私生活に踏み込んでいないか読んで確認）")
    if kind == 'monthly':
        for mem in members:
            if mem['graduated'] or not mem['nickname']:
                continue
            nick = mem['nickname'].replace('～', '').replace('〜', '')
            if not nick or nick == mem['name']:
                continue
            first = body.find(nick)
            if first < 0:
                continue
            full_forms = [mem['name'], mem['name'].replace(' ', '')]
            if not any(body.find(fm) >= 0 and body.find(fm) <= first + len(nick) + 20 for fm in full_forms):
                rep.warn('NICKNAME_FIRST', f"月刊は愛称の初出に本名を添える: 「{nick}」の初出（…{snippet(body, first)}…）に「{mem['name']}」が無い")
    # 担当カラー以外の絵文字（装飾目的の絵文字は使わない）
    others = Counter(ch for ch in body if ord(ch) >= 0x1F300 and ch not in ''.join(MEMBER_EMOJI))
    if others:
        rep.info('OTHER_EMOJI', f"担当カラー以外の絵文字: {dict(others.most_common(5))}（引用や公演名の表記ママなら可）")


def check_content(plain, kind, rep):
    for w in SENSITIVE:
        for m in re.finditer(re.escape(w), plain):
            rep.warn('SENSITIVE', f"「{w}」: 感情・推測を乗せてはいけない対象（数字・運営・体調・人間関係・煽り）に触れていないか: …{snippet(plain, m.start())}…")
    for w in SPECULATION:
        for m in re.finditer(re.escape(w), plain):
            rep.info('SPECULATION', f"推測表現「{w}」: 収集データに根拠があるか: …{snippet(plain, m.start())}…")
    if kind == 'monthly':
        for w in JARGON:
            occ = list(re.finditer(re.escape(w), plain))
            if not occ:
                continue
            def annotated(m):
                after = plain[m.end():m.end() + 14]
                before = plain[max(0, m.start() - 2):m.start()]
                if re.match(r'.{0,12}[（(]', after) or '（' in before or '(' in before:
                    return True
                # 「特典会（ライブ後にチェキ＝その場で撮る…）」のように、別の語の説明の括弧の中で
                # 「＝」「とは」を伴って説明されている場合も注釈ありとみなす
                if re.match(r'\s*(＝|=|とは|という)', after):
                    return True
                open_paren = plain.rfind('（', 0, m.start())
                close_paren = plain.find('）', m.end())
                if open_paren >= 0 and close_paren >= 0 and plain.rfind('）', 0, m.start()) < open_paren:
                    inside = plain[open_paren:close_paren]
                    if '＝' in inside or 'とは' in inside:
                        return True
                return False
            if not any(annotated(m) for m in occ):
                rep.warn('JARGON', f"月刊は専門用語に注釈を付ける: 「{w}」に注釈が無い …{snippet(plain, occ[0].start())}…")
            elif not annotated(occ[0]):
                rep.info('JARGON', f"「{w}」の注釈が初出でなく後の箇所にある（初出: …{snippet(plain, occ[0].start())}…）")


def check_songs(body, songs, rep):
    for song in songs:
        if song == GROUP_NAME:
            continue
        variants = Counter(m.group(0) for m in re.finditer(loose_song_pattern(song), body))
        if not variants:
            continue
        if len(variants) > 1:
            rep.warn('SONG_NOTATION', f"同じ曲が複数の表記で出ている: {dict(variants)}（楽曲一覧の正表記は「{song}」）")
        elif song not in variants:
            rep.info('SONG_NOTATION', f"「{next(iter(variants))}」は楽曲一覧では「{song}」（投稿の表記ママなら可）")


def check_events(body, kind, start, end, rep):
    if not start:
        return
    rows = load_events(start, end)
    if kind == 'weekly':
        for r in rows:
            if not any(v in body for v in date_variants(r['date'])):
                rep.error('MISSING_EVENT', f"CSV にある公演が記事に無い: {r['date']} {r['event']} / {r['venue']}")
        csv_dates = {r['date'] for r in rows}
        y = start[:4]
        extra = []
        for m in re.finditer(r'(?<![\d/])(\d{1,2})/(\d{1,2})(?![\d/])', body):
            try:
                iso = datetime(int(y), int(m.group(1)), int(m.group(2))).strftime('%Y-%m-%d')
            except ValueError:
                continue
            if start <= iso <= end and iso not in csv_dates and m.group(0) not in extra:
                extra.append(m.group(0))
        if extra:
            rep.info('DATE_NOT_IN_CSV', f"期間内で CSV に公演が無い日付への言及: {', '.join(extra)}（告知や投稿の日付なら可。公演なら CSV に追加）")
        rep.info('EVENTS', f"期間 {start}〜{end} の CSV 公演数: {len(rows)}")
    elif kind == 'monthly':
        n = len(rows)
        nums = [(int(m.group(1)), m.group(2)) for m in re.finditer(r'(\d+)\s*(公演|本のライブ|ステージ)', body)]
        rep.info('EVENTS', f"{start[:7]} の CSV 公演数: {n}。記事内の数字: {nums or 'なし'}")
        for k, unit in nums:
            if unit == '公演' and k != n and abs(k - n) <= 5:
                rep.warn('EVENT_COUNT', f"記事の「{k}公演」と CSV の {n} 公演が合わない（数え方が違うだけなら可）")


def count_sentences(text):
    """段落の文の数。引用の中と、閉じ括弧の直前の句点は数えない。

    「クモリノチ。」「『クモリニキ。』」のように句点で終わる固有名詞があるので、
    素朴に「。」を数えると1段落の文数を多く見積もる。引用を落としてから数える。
    """
    t = QUOTE_RE.sub('', text)
    t = re.sub(r'。(?=[』」）\)])', '', t)
    return t.count('。')


def check_structure(body, memo, kind, rep):
    paras = [p for p in re.split(r'\n\s*\n', body) if p.strip() and not p.lstrip().startswith(('#', '-', '*', '|', '>'))]
    long_paras = [p for p in paras if count_sentences(p) > 4]
    if long_paras:
        rep.warn('PARAGRAPH', f"1段落が5文以上の段落が {len(long_paras)} つ（3〜4文まで）: 「{long_paras[0].strip()[:40]}…」")
    if kind in ('weekly', 'monthly'):
        if not re.search(r'^##\s*出典', body, re.M):
            rep.error('SOURCES', "「## 出典」節が無い")
        else:
            urls = len(URL_RE.findall(body))
            rep.info('SOURCES', f"本文中の URL 数: {urls}")
    if memo:
        rep.info('MEMO', "編集メモあり（note 公開時に削除する）")
    else:
        rep.info('MEMO', "編集メモが無い（確認できなかった項目・判断に迷った点を残す運用）")


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('article')
    p.add_argument('--type', choices=['weekly', 'monthly', 'lyrics', 'generic'], help='省略時はパスから判定')
    args = p.parse_args()

    with open(args.article, 'r', encoding='utf-8') as f:
        text = f.read()
    kind = args.type or detect_type(args.article)
    start, end = detect_period(args.article, kind)
    body, memo = split_body_memo(text)
    plain = strip_quotes(body)
    songs = load_canonical_songs()
    members = load_members()
    rep = Report()

    check_note_constraints(body, rep)
    check_group_name(plain, rep)
    check_style(plain, kind, songs, rep)
    check_members(body, plain, kind, members, rep)
    check_content(plain, kind, rep)
    check_songs(body, songs, rep)
    check_events(body, kind, start, end, rep)
    check_structure(body, memo, kind, rep)

    print(f"記事: {args.article}（種別: {kind}" + (f"、期間: {start}〜{end}" if start else '') + "）")
    for level in ('ERROR', 'WARN', 'INFO'):
        items = [(c, m) for l, c, m in rep.items if l == level]
        print(f"\n== {level} ({len(items)})")
        for code, msg in items:
            print(f"- [{code}] {msg}")
    counts = Counter(l for l, _, _ in rep.items)
    print(f"\nRESULT: ERROR {counts['ERROR']} / WARN {counts['WARN']} / INFO {counts['INFO']}")


if __name__ == '__main__':
    main()
