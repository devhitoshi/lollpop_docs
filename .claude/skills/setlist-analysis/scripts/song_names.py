"""曲名の正表記と名寄せ。

`analyze_monthly_setlist.py`（集計）と `check_event_consistency.py`（整合性チェック）が
同じルールで曲名を扱うために切り出した共通モジュール。
名寄せルールを直すときはここだけを直す。
"""
import re


def load_canonical_songs(path='songs/楽曲一覧.md'):
    """`songs/楽曲一覧.md` から曲名の正表記を読む。"""
    songs = []
    with open(path, 'r', encoding='utf-8') as f:
        for line in f:
            # 「## 音楽配信先」以降は配信アカウントの名義一覧なので曲名ではない。
            if line.startswith('## 音楽配信先'):
                break
            # 行頭の箇条書きだけを曲名として拾う。インデントを許すと、曲の下にぶら下がる
            # 「作詞」「初披露」「配信先」などの見出しまで曲名として登録されてしまう。
            m = re.match(r'^- \*\*(.+)\*\*', line)
            if m:
                songs.append(m.group(1).strip())
    return songs


def normalize_song_name(name, canonical_songs):
    """セトリの1項目を正表記に寄せる。寄せられなければ None。"""
    name = name.strip()
    name = re.sub(r'^[0-9]+[\s\.]*', '', name)
    name = re.sub(r'🆕✨?', '', name)
    name = re.sub(r'❤️\s*', '', name)
    name = re.sub(r'🍭\s*', '', name)
    name = re.sub(r'💙\s*', '', name)
    name = re.sub(r'（.*?）', '', name)
    name = re.sub(r'\(.*?\)', '', name)
    name = name.replace('飴入れ', '').replace('飴投げ', '')
    name = name.strip()

    if 'ろりぽっぷ' in name and '単独' not in name: return next((c for c in canonical_songs if 'ろりぽっぷ' in c), None)
    if '始まりの宴' in name: return next((c for c in canonical_songs if '始まりの宴' in c), None)
    if '主人公' in name: return next((c for c in canonical_songs if '主人公' in c), None)
    if '約束' in name: return next((c for c in canonical_songs if '約束' in c), None)
    if 'ぽっぽ' in name and 'ポジティブ' in name: return next((c for c in canonical_songs if 'ぽっぽ' in c), None)
    if 'Lambie' in name: return next((c for c in canonical_songs if 'Lambie' in c), None)
    if 'Say Hello' in name: return next((c for c in canonical_songs if 'Say Hello' in c), None)
    if '推し事' in name: return next((c for c in canonical_songs if '推し事' in c), None)
    if '正解の方程式' in name: return next((c for c in canonical_songs if '正解の方程式' in c), None)
    if 'キミノセイ' in name: return next((c for c in canonical_songs if 'キミノセイ' in c), None)

    for c in canonical_songs:
        if name.lower() == c.lower(): return c
    # デビュー初期（2024年末〜）の投稿は「ShinyDays」のようにスペースを詰めた表記が混在する。
    # 空白と大小文字を無視して照合しないと SHINY DAYS が丸ごと集計から漏れる。
    squashed = re.sub(r'\s+', '', name).lower()
    for c in canonical_songs:
        if squashed == re.sub(r'\s+', '', c).lower(): return c
    for c in canonical_songs:
        if c in name: return c
    return None


def is_non_song_item(item):
    """SE・MC・企画コーナー・区切り行など、曲ではないセトリ項目なら True。"""
    if re.search(r'^(SE|MC)', item) or item.startswith('MC(') or item.startswith('MC（'): return True
    if 'ラジオ体操' in item or 'クイズ' in item: return True
    # 【🏮宴衣装】《🍭ソロコーナー》などの区切り行。曲ではないので除外する
    if item.startswith('【') or item.startswith('《'): return True
    return False


def split_setlist(setlist_str):
    """`data_event.csv` の setlist 文字列を、部ごとの項目リストに分解する。

    戻り値は [[項目, ...], ...]（`|` 区切りの部ごと）。メドレー（→）は展開済み。
    SE/MC などの非曲項目は残す（呼び出し側で is_non_song_item を使って除く）。
    """
    parts = []
    for part in setlist_str.split('|'):
        part = re.sub(r'\d+部:\s*', '', part)
        part = re.sub(r'アンコール;?', '', part)
        items = [item.strip() for item in part.split(';') if item.strip()]

        # ワンマン等のメドレーは「《①メドレー》曲A→曲B→曲C」形式で1項目に収まっている。
        # 分解しないと先頭の1曲しか計上されず、残りが丸ごと欠落する。
        expanded = []
        for item in items:
            if '→' in item:
                item = re.sub(r'^《.*?》', '', item)
                expanded.extend(p.strip() for p in item.split('→') if p.strip())
            else:
                expanded.append(item)
        parts.append(expanded)
    return parts
