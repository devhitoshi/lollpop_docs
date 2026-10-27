"""note記事の機械チェック（article-review エージェントの下請け）。

記事1本を読み、リポジトリの資料と突き合わせて「人（またはエージェント）が判断すべき箇所」を列挙する。
自動では直さない。判定の根拠になる資料:

- prompts/write/style_ai_poppar.md  … 文体ルール（! の連打、オタク語彙の回数、絵文字、使わない言葉、常套句、言い過ぎ、文末の単調さ）
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
# 使わない言葉（style_ai_poppar.md 末尾。全媒体で禁止）
BANNED_WORDS = {'地下アイドル': '「アイドル」にする', 'レア曲': 'コールに触れるなら「コールが独特な曲」'}
# 前のグループでの経歴として書くことはあるので、こちらは WARN で確認を促す
CHECK_WORDS = {'リーダー': '現グループに役職は無い。前のグループの経歴として書くなら、そう分かる書き方か'}
STOCK_PHRASES = ['まとめると', '結論から言うと']
# 事実の言い過ぎ。データで確かめていれば使ってよいので WARN で確認を促すだけ
OVERSTATEMENT = ['5人とも', '全員', 'そろって', '毎回', '必ず', 'いつも']
OTAKU_LIMIT = 3  # 1記事の合計（全シリーズ共通）
COLOR_EMOJI = {'赤': '❤️', '黄': '💛', '水色': '🩵', '緑': '💚', '白': '🤍', 'ピンク': '🩷', '青': '💙'}
MEMBER_EMOJI = set(COLOR_EMOJI.values())
URL_RE = re.compile(r'https?://\S+')
QUOTE_RE = re.compile(r'「[^「」]*」|『[^『』]*』|“[^”]*”')
TWIMG_RE = re.compile(r'https?://(?:[\w-]+\.)?twimg\.com\S*', re.I)


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

DISCLAIMER = '> ※Xの投稿を中心にAIで分析して限界オタクの性格づけして本記事を書き上げてます。'


def check_disclaimer(body, rep):
    """タイトル直後の注意書き（style_ai_poppar.md「冒頭の注意書き」）。"""
    lines = body.splitlines()
    idx = next((i for i, l in enumerate(lines) if l.startswith('# ')), None)
    if idx is None:
        rep.warn('DISCLAIMER', "H1 見出しが無いので注意書きの位置を判定できない")
        return
    first = next((l.strip() for l in lines[idx + 1:] if l.strip()), '')
    if first != DISCLAIMER:
        rep.error('DISCLAIMER', f"タイトル直後に注意書き「{DISCLAIMER}」が無い（引用ブロック `> ※` で、文面は変えない）")
    elif body.count(DISCLAIMER[3:]) > 1:
        rep.warn('DISCLAIMER', "注意書きが2回以上ある（冒頭の1回だけ）")


def check_note_constraints(body, rep):
    lines = body.splitlines()
    table_lines = [i + 1 for i, l in enumerate(lines) if l.strip().startswith('|')]
    if table_lines:
        rep.error('NOTE_TABLE', f"表組みがある（note は表を使えない。箇条書きに直す）: {table_lines[:5]} 行目")
    # 本文の見出しは ##（大見出し）と ###（小見出し）の2段まで。# はタイトル（2026-10-27 に読み直し）
    deep = [(i + 1, l.strip()[:40]) for i, l in enumerate(lines) if re.match(r'^#{4,}\s', l)]
    if deep:
        rep.error('NOTE_HEADING', f"`####` 以下の見出しがある（note の本文は ## と ### の2段まで）: " + ', '.join(f"{n}行目「{t}」" for n, t in deep[:5]))


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


def load_bang_names():
    """公演名に出てくる「!」付きの語（他グループ名・イベント名。例: るるぱにっく!!）。表記ママなので連打の検査から外す。"""
    names = set()
    with open('events/data_event.csv', encoding='utf-8') as f:
        for row in csv.DictReader(f):
            names.update(re.findall(r'[^\s『』「」（）()/／・×,、]+[!！‼︎]{2,}', row.get('event', '')))
    return sorted(names, key=len, reverse=True)


def check_style(plain, kind, songs, rep):
    # 曲名・グループ名・公演名の「!」は（表記ゆれも含めて）除外してから連打を探す
    scrubbed = re.sub(r'ろりぽっぷ[!！‼︎]+', '', plain)
    for name in load_bang_names():
        scrubbed = scrubbed.replace(name, '')
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
    total = sum(used.values())
    if total > OTAKU_LIMIT:
        rep.warn('OTAKU_WORDS', f"オタク語彙は1記事に合計{OTAKU_LIMIT}回まで。現在 {total} 回: {used}")
    if used:
        rep.info('OTAKU_WORDS', f"オタク語彙の使用回数: {used}")


def check_members(body, plain, kind, members, rep):
    emoji_alt = '(?:' + '|'.join(re.escape(e) for e in sorted(MEMBER_EMOJI, key=len, reverse=True)) + ')'
    # 2026-10-27〜 名前のあとに絵文字を付けない。引用の中は原文のままなので plain で見る。
    # 愛称が重なる（まなてぃー／まな）ので、絵文字の位置で重複を除いて1記事1件にまとめる
    emoji_hits = {}
    for mem in members:
        for alias in sorted(mem['aliases'], key=len, reverse=True):
            if not alias:
                continue
            for m in re.finditer(re.escape(alias) + r'\s*(' + emoji_alt + ')', plain):
                emoji_hits.setdefault(m.start(1), m.start())
        if mem['graduated']:
            hits = [a for a in mem['aliases'] if a and len(a) >= 3 and a in plain]
            if hits:
                rep.info('GRADUATED', f"卒業メンバー {mem['name']} への言及あり（在籍時の事実のみか、卒業後の活動・私生活に踏み込んでいないか読んで確認）")
    if emoji_hits:
        first = min(emoji_hits.values())
        rep.warn('MEMBER_EMOJI', f"名前のあとに絵文字を付けない: {len(emoji_hits)} か所（初出 …{snippet(plain, first)}…）")
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


def check_image_rights(body, rep):
    """twimg.com の直リンクの疑い。pbs.twimg.com / video.twimg.com などは、Markdown画像（![]()）でも生URLでも検出する。
    メンバー写真は載せてよい（2026-09-29 改訂）が、直リンクは元の投稿が消えると画像も消えるので、保存して note に上げる。
    """
    for m in TWIMG_RE.finditer(body):
        rep.warn('IMAGE_RIGHTS',
                  f"twimg.com の画像URLを直リンクしている疑い（写真は載せてよいが、保存して note にアップロードする。"
                  f"クレジット ©FLAP entertainment も忘れずに）: …{snippet(body, m.start())}…")


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


EMBED_RE = re.compile(r'^https?://(?:x|twitter)\.com/[^/\s]+/status/\d+/?$')


def check_embeds(body, kind, rep):
    """本文に置いた X の投稿の埋め込み（weekly.md「埋め込みの置き方」）。

    note は URL を単独行に貼ると埋め込みになる。出典節の URL 一覧は数に入れない。
    """
    if kind != 'weekly':
        return
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    main = re.split(r'^##\s*出典', body, flags=re.M)[0]
    n = sum(1 for l in main.split('\n') if EMBED_RE.match(l.strip()))
    if n == 0:
        rep.warn('EMBED', "本文に X の投稿の埋め込みが無い（単独行の URL で置く）")
    elif n > 8:
        rep.warn('EMBED', f"埋め込みが {n} 本（6〜8本まで。多いと note の表示が重くなる）")
    else:
        rep.info('EMBED', f"埋め込み {n} 本")


def check_wording(plain, rep):
    """使わない言葉・常套句・言い過ぎ（style_ai_poppar.md）。引用の中は見ない。"""
    for w, why in BANNED_WORDS.items():
        for m in re.finditer(re.escape(w), plain):
            rep.error('BANNED_WORD', f"「{w}」は使わない（{why}）: …{snippet(plain, m.start())}…")
    for w, why in CHECK_WORDS.items():
        for m in re.finditer(re.escape(w), plain):
            rep.warn('BANNED_WORD', f"「{w}」: {why}: …{snippet(plain, m.start())}…")
    for w in STOCK_PHRASES:
        for m in re.finditer(re.escape(w), plain):
            rep.warn('STOCK_PHRASE', f"「{w}」で書き出さない。要点そのものから書く: …{snippet(plain, m.start())}…")
    for w in OVERSTATEMENT:
        for m in re.finditer(re.escape(w), plain):
            rep.warn('OVERSTATEMENT', f"「{w}」: データで確かめた範囲か（1人の投稿を全員に広げていないか）: …{snippet(plain, m.start())}…")


# 文末の分類。伝聞・語りかけで終わる文は「報告調」に数えない
# 「〜と書いています」「〜と言っていました」は誰の投稿かを示す言い方なので、報告調に数えない
HEARSAY_END = re.compile(r'((みたい|そう|らしい|とのこと|よう|ん)(です|でした)?|と(書い|言っ)て(い)?(ます|ました)|かも|ね|よ|な)$')
REPORT_END = re.compile(r'(ました|でした|います|ます|です|た|だ)$')


def report_run(paragraph):
    """段落の中で、報告調（〜ました／〜です／〜た）の文が続く最大の数。体言止め・伝聞・問いで途切れる。"""
    best = cur = 0
    for sent in re.split(r'(?<=[。！!？?])', re.sub(r'。(?=[』」）\)])', '', paragraph)):
        sent = re.sub(r'[。！!？?\s]+$', '', sent.strip())
        if len(sent) < 6:
            continue
        if REPORT_END.search(sent) and not HEARSAY_END.search(sent):
            cur += 1
            best = max(best, cur)
        else:
            cur = 0
    return best


def check_monotone(plain, rep):
    """報告調が3文続く段落（2026-10-27 オーナー指摘「てるてる坊主を作って待った」のような報告調が不自然）。"""
    hits = [para.strip() for para in re.split(r'\n\s*\n', plain)
            if para.strip() and not para.lstrip().startswith(('#', '-', '*', '|', '>', 'http', '<!--'))
            and report_run(para) >= 3]
    if hits:
        rep.warn('MONOTONE', f"報告調（〜ました／〜です）が3文続く段落が {len(hits)} つ。出来事は伝聞（〜みたいです）や体言止めを混ぜて語る: 「{hits[0][:40]}…」")


# 構成の目安（style_ai_poppar.md「構成の目安」。2026-10-27〜）
PARA_MAX = 120         # 1段落の字数（スマホで約6行）
SENT_MAX = 60          # 1文の字数
LONG_SENT_SHARE = 0.2  # 60字を超える文の割合の上限
QUOTES_PER_PARA = 2    # 1段落の引用の数
PROSE_RUN_MAX = 450    # 地の文が途切れずに続く字数（スマホで約1画面）


def prose_blocks(body):
    """空行で区切ったブロックを、地の文（True）とそれ以外（見出し・箇条書き・URL・引用・区切り線）に分ける。"""
    out = []
    for blk in re.split(r'\n\s*\n', re.sub(r'<!--.*?-->', '', body, flags=re.S)):
        b = blk.strip()
        if not b:
            continue
        is_prose = not (b.startswith(('#', '-', '*', '|', '>', '【')) or re.match(r'^https?://\S+$', b))
        out.append((is_prose, b.replace('**', '')))
    return out


def split_sentences(text):
    """鉤括弧の中の句点では切らずに文に分ける（括弧の中も字数には数える）。"""
    masked = re.sub(r'「[^「」]*」|『[^『』]*』', lambda m: '「' + 'x' * (len(m.group(0)) - 2) + '」', text)
    sents, start = [], 0
    for m in re.finditer(r'[。！？!?]+', masked):
        sents.append(text[start:m.end()].strip())
        start = m.end()
    if text[start:].strip():
        sents.append(text[start:].strip())
    return [x for x in sents if len(x) >= 6]


def check_structure(body, memo, kind, rep, songs=()):
    blocks = prose_blocks(body)
    paras = [b for is_p, b in blocks if is_p]
    long_paras = [p for p in paras if len(p) > PARA_MAX]
    if long_paras:
        rep.warn('PARAGRAPH', f"{PARA_MAX}字を超える段落が {len(long_paras)} / {len(paras)} 段落（スマホで6行超）: 「{long_paras[0][:40]}…」")
    sents = [x for p in paras for x in split_sentences(p)]
    long_sents = [x for x in sents if len(x) > SENT_MAX]
    if sents and len(long_sents) / len(sents) > LONG_SENT_SHARE:
        rep.warn('LONG_SENTENCE', f"{SENT_MAX}字を超える文が {len(long_sents)} / {len(sents)} 文（2割まで）。「〜と書いていて、」の所で切る: 「{long_sents[0][:40]}…」")
    song_set = set(songs)

    def n_quotes(p):
        return sum(1 for q in re.findall(r'「([^「」]*)」', p) if q not in song_set)
    dense = [p for p in paras if n_quotes(p) > QUOTES_PER_PARA]
    if dense:
        rep.warn('QUOTE_DENSITY', f"引用が {QUOTES_PER_PARA + 1} つ以上の段落が {len(dense)} つ（3つ目の言葉は次の段落へ）: 「{dense[0][:40]}…」")
    runs, cur, head = [], 0, ''
    for is_p, b in blocks:
        if is_p:
            if cur == 0:
                head = b[:30]
            cur += len(b)
        else:
            if cur:
                runs.append((cur, head))
            cur = 0
    if cur:
        runs.append((cur, head))
    over = [r for r in runs if r[0] >= PROSE_RUN_MAX]
    if over:
        rep.warn('PROSE_RUN', f"地の文が {PROSE_RUN_MAX}字以上続く箇所が {len(over)} つ（最長 {max(over)[0]}字。小見出し・カード・箇条書き・区切り線で切る）: 「{max(over)[1]}…」")
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
    # Windows の既定（cp932）だと絵文字の出力で落ちるので、UTF-8 に固定する
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
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

    check_disclaimer(body, rep)
    check_embeds(body, kind, rep)
    check_note_constraints(body, rep)
    check_group_name(plain, rep)
    check_style(plain, kind, songs, rep)
    check_members(body, plain, kind, members, rep)
    check_content(plain, kind, rep)
    check_wording(plain, rep)
    check_monotone(plain, rep)
    check_songs(body, songs, rep)
    check_image_rights(body, rep)
    check_events(body, kind, start, end, rep)
    check_structure(body, memo, kind, rep, songs)

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
