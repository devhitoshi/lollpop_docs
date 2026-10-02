"""メンバーの投稿から「話題の在庫」（members/*.md の4層）の候補を機械抽出する。

特典会での会話に使う想定なので、**何を好きだと言ったか**より
**いつ・何回それを話題にしたか**を出す。頻度と最終言及日が判断の材料になる。

- カテゴリは members/README.md の固定分類（食べ物／お出かけ・場所／音楽・アニメ・ゲーム／
  動物／ファッション／美容／体を動かすこと／出身地・地元／苦手なもの）。
  加えて「メンバーとのつながり」を別表で出す（誰を何と呼び、告知以外でどれだけ名前を出しているか）
- 具体語の辞書ヒットに加えて、文脈語（「食べ」「行っ」など）で拾った投稿も出す。
  辞書に無い固有名詞（店名・作品名）は Claude が原文から拾う前提
- 頻度は 継続(3回以上)／複数(2回)／一度(1回)。半年以上言及が無いものには [古い] を付ける

出力は work/x_fetch/topic_inventory_<handle>_<since>_<until>.md（他人の投稿原文を含むのでコミットしない）。

使い方:
    python3 .claude/skills/member-profile-refresh/scripts/topic_inventory.py --since 2024-11-16 --until 2026-09-09
    python3 ... --accounts kurumi_lpop --min-hits 2
"""
import argparse
import os
import re
import sys
from collections import defaultdict
from datetime import date

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, script_dir)
sys.path.insert(0, os.path.join(project_root, '.claude/skills/x-account-fetch/scripts'))
from fetch_accounts import DEFAULT_ACCOUNTS  # noqa: E402
from profile_stats import load  # noqa: E402  日付パースと期間フィルタは既存に合わせる

X_DIR = 'work/x_fetch'
URL_RE = re.compile(r'https?://\S+')

# 具体語（words）＝在庫表にそのまま載る候補。文脈語（context）＝辞書に無い話題を拾うための網。
CATEGORIES = {
    '食べ物': {
        'words': ['ラーメン', '寿司', 'すし', '焼肉', '焼き肉', '鳥貴族', '唐揚げ', 'からあげ', 'カレー',
                  'パスタ', 'ピザ', 'ハンバーグ', 'オムライス', 'うどん', 'そば', '餃子', 'たこ焼き',
                  'お好み焼き', '焼きそば', 'クレープ', 'パンケーキ', 'かき氷', 'アイス', 'チョコ',
                  'ケーキ', 'プリン', 'ドーナツ', 'クロワッサン', 'おにぎり', '納豆', '味噌汁', '鍋',
                  'しゃぶしゃぶ', '焼き鳥', 'ホットク', 'タピオカ', 'コーヒー', '抹茶', 'いちご',
                  'みかん', 'ぶどう', 'メロン', 'スイカ', 'バナナ', '団子', 'だんご', 'わたあめ',
                  'ポテト', 'マック', 'スタバ', 'セブン', 'ファミマ', 'ローソン', 'ラムネ',
                  'ビール', 'お酒', 'サワー', 'ハイボール', '梅酒', 'ワイン', 'パフェ', '弁当'],
        'context': ['食べ', 'たべ', '美味し', 'おいし', 'ごはん', 'ご飯', 'ランチ', 'ディナー',
                    'カフェ', 'スイーツ', '飲ん', '呑ん', '甘い', 'お腹すい'],
    },
    'お出かけ・場所': {
        'words': ['渋谷', '新宿', '池袋', '原宿', '秋葉原', '浅草', '上野', '銀座', '六本木', 'お台場',
                  '横浜', '川崎', '大宮', '舞浜', 'ディズニー', 'USJ', '水族館', '動物園', '遊園地',
                  '温泉', '銭湯', 'サウナ', '花火', '祭り', '神社', 'お寺', '映画館', 'カラオケ',
                  'ボウリング', '新大久保', '中野', '吉祥寺', '下北沢', '大阪', '京都', '名古屋',
                  '福岡', '北海道', '沖縄', 'プール', 'キャンプ', 'BBQ'],
        'context': ['行っ', '行き', '来た', 'お出かけ', 'おでかけ', '旅行', '観光', '散歩'],
    },
    '音楽・アニメ・ゲーム': {
        'words': ['アニメ', '漫画', 'マンガ', '声優', 'ゲーム', 'Switch', 'スイッチ', 'ポケモン',
                  'スプラ', 'あつ森', 'マイクラ', '原神', 'ウマ娘', 'プロセカ', '音ゲー', 'ボカロ',
                  'K-POP', 'KPOP', '韓国', 'BTS', 'TWICE', 'NewJeans', 'IVE', 'YouTube', 'TikTok',
                  'Netflix', 'ドラマ', '映画', '主題歌', 'カバー', 'ヒトカラ', '推し'],
        'context': ['見てる', '観てる', '見た', '観た', 'ハマ', 'はま', '聴い', '聞い', 'プレイ'],
    },
    '動物': {
        'words': ['犬', '猫', 'ねこ', 'ネコ', 'いぬ', 'わんこ', 'ハムスター', 'うさぎ', 'ウサギ',
                  'インコ', '金魚', 'ペット', 'パンダ', 'カピバラ', 'ぬいぐるみ', 'ハリネズミ',
                  'フクロウ', 'ペンギン', 'イルカ', 'カワウソ'],
        'context': ['かわいすぎ', '飼っ', 'もふ'],
    },
    'ファッション': {
        'words': ['コーデ', '私服', '古着', 'ワンピ', 'スカート', 'パンツ', 'デニム', 'ニット',
                  'パーカー', 'Tシャツ', 'シャツ', 'カーディガン', 'ジャケット', 'セットアップ',
                  '浴衣', '着物', '制服', '靴', 'スニーカー', 'ブーツ', 'サンダル', 'ヒール',
                  'バッグ', 'リュック', '帽子', 'キャップ', 'ピアス', 'イヤリング', 'アクセ',
                  '指輪', 'ネックレス', '腕時計', '眼鏡', 'メガネ', 'ブランド', '古着屋',
                  'GU', 'ユニクロ', 'ZARA', 'しまむら', '韓国系', '地雷系', '量産型', 'サブカル'],
        'context': ['着てる', '着た', '買った', '似合', 'おしゃれ', 'オシャレ', 'コーディネート'],
    },
    '美容': {
        'words': ['ヘアアレンジ', '巻き髪', 'ネイル', 'まつげ', 'まつ毛', 'マツエク', 'メイク',
                  'コスメ', 'リップ', 'アイシャドウ', 'チーク', 'ファンデ', '化粧', 'スキンケア',
                  'パック', '日焼け', '香水', 'ダイエット', '痩せ', '体重', '美容室', '髪色',
                  '前髪', 'ヘアカラー', 'カラコン', 'まつパ', '脱毛'],
        'context': ['肌', '可愛くな', 'かわいくな', '整え'],
    },
    '体を動かすこと': {
        'words': ['筋トレ', 'ジム', 'ランニング', 'ヨガ', 'ストレッチ', 'ボイトレ', '縄跳び',
                  '水泳', 'スポーツ', '野球', 'サッカー', 'バスケ', 'バレー', '腹筋'],
        'context': ['走っ', '鍛え', '体力', 'レッスン'],
    },
    '出身地・地元': {
        'words': ['群馬', '静岡', '鹿児島', '東京', '神奈川', '埼玉', '実家', '地元', '帰省',
                  '高崎', '前橋', '伊勢崎', '太田', '浜松', '沼津', '静岡市', '富士山',
                  '桜島', '天文館', '指宿', '屋久島', '上京', '方言', 'なまり', '訛り',
                  '焼きまんじゅう', '下仁田', 'うなぎ', '白くま', '黒豚', 'さつまいも'],
        'context': ['出身', '育っ', '田舎', '生まれ', '帰る', '母', '父', '家族', '兄', '姉', '妹', '弟'],
    },
    '苦手なもの': {
        'words': [],
        'context': ['苦手', '嫌い', 'きらい', '怖い', 'こわい', '無理すぎ', '出来ない', 'できない'],
    },
}

# 「趣味嗜好の言及」と紛らわしい語。落とさずに注意書きを付け、原文確認を促す。
# 地名は大半がライブ会場で、曲名は歌詞・セトリの話。ここを潰さないと在庫表が会場名で埋まる。
NOISE = {
    'ラムネ': '曲名「夏色ラムネ」',
    'メイク': '曲名「メイク☆マイダンス」',
    'ゲーム': '曲名「シーソーゲーム」',
    'アイス': '「アイスブレイク」等',
    'パック': '「スターターパック」等',
    '推し': '本人が推される側の文脈と衝突',
    '渋谷': 'ライブ会場の可能性',
    '新宿': 'ライブ会場の可能性',
    '池袋': 'ライブ会場の可能性',
    '秋葉原': 'ライブ会場の可能性',
    '原宿': 'ライブ会場の可能性',
    '上野': 'ライブ会場の可能性',
    'お台場': 'ライブ会場の可能性',
    '横浜': 'ライブ会場の可能性',
    '川崎': 'ライブ会場の可能性',
    '大宮': 'ライブ会場の可能性',
    '中野': 'ライブ会場の可能性',
    '大阪': '遠征公演の可能性',
    '名古屋': '遠征公演の可能性',
    '福岡': '遠征公演の可能性',
    '東京': '会場所在地の可能性',
    'レッスン': '仕事としての稽古（趣味ではない）',
    'ボイトレ': '仕事としての稽古（趣味ではない）',
    '浴衣': '衣装・企画の可能性',
    '制服': '衣装の可能性',
    'カラコン': '本人の私物か仕事用か要確認',
    # 2026-09-09 の原文検証で誤検出が確定したもの
    'そば': '「そばに居る」の誤検出（食べ物の用例はほぼ無い）',
    '猫': '「猫の日(2/22)」「猫耳」のライブ企画',
    'ねこ': '「まねきねこ」（カラオケ店）の誤検出',
    '浅草': 'ライブ会場（浅草VAMPKIN）の可能性が高い',
    'ケーキ': '生誕祭のケーキ／「パンケーキ」の部分一致',
    'インコ': '「バレンタインコス」の部分一致',
    'スイッチ': '「掃除スイッチが入る」等の比喩',
    'カバー': '楽曲カバー／「スイカバー」の部分一致',
}

# メンバーとのつながり用。同じ人を指す表記のゆれを正規表現でまとめる。
# 短いあだ名は誤検出しやすいので、語形を限定するか除外している
# （「まう」は「〜してしまう」を弾くため直前の し／ち／じ を除外）。
MEMBER_LINKS = [
    ('mana_lpop', '愛月まな', [r'@mana_lpop', r'まなてぃ[ーぃ]?', r'愛月', r'まなち']),
    ('kurumi_lpop', 'やぎくるみ', [r'@kurumi_lpop', r'くるみん', r'やぎ', r'くるみ']),
    ('mayu_lpop', '夏川茉夢', [r'@mayu_lpop', r'おまゆ', r'夏川', r'茉夢']),
    ('ami_lpop', '松川愛美', [r'@ami_lpop', r'あみてん', r'松川', r'愛美']),
    ('mau_lpop', 'まう', [r'@mau_lpop', r'まうちゃん', r'まうたん', r'まうまう',
                          r'まう[〜~ー]', r'(?<![しちじ])まう(?![くけこ])']),
    ('asaka_lpop', '姫杏朝香（元）', [r'@asaka_lpop', r'お姫ちゃん', r'姫杏', r'朝香']),
    ('natsumi_lpop', '苺花なつみ（元）', [r'@natsumi_lpop', r'なっちゃん', r'苺花', r'なつみ']),
]

# 告知の中の言及は「全員に触れる」だけなので、私的な言及と分けて数える。
ANNOUNCE_MARKERS = ['チケット', 'ご予約', '予約', 'OPEN', 'START', '出演', '物販', '特典会',
                    '販売', 'リリース', 'セトリ', '会場', '開演', '転換', '対バン']


def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--since', required=True)
    p.add_argument('--until', required=True, help='この日を含む')
    p.add_argument('--accounts', help='ハンドルのカンマ区切り（省略時は現メンバー5人）')
    p.add_argument('--min-hits', type=int, default=1, help='在庫表に載せる最小ヒット数')
    p.add_argument('--stale-days', type=int, default=180,
                   help='この日数より古い最終言及に [古い] を付ける')
    p.add_argument('--x-dir', default=X_DIR)
    return p.parse_args()


def clean(text):
    return URL_RE.sub('', text or '').replace('\n', ' ').strip()


def freq_label(n):
    return '継続' if n >= 3 else ('複数' if n == 2 else '一度')


def _matcher(word):
    """英字のみの語は前後を英字で挟まれた場合を弾く（IVE が LIVE に一致するのを防ぐ）。"""
    if re.fullmatch(r'[A-Za-z0-9\-]+', word):
        pat = re.compile(rf'(?<![A-Za-z]){re.escape(word)}(?![A-Za-z])', re.I)
        return lambda s: bool(pat.search(s))
    return lambda s: word in s


MATCHERS = {word: _matcher(word)
            for spec in CATEGORIES.values() for word in spec['words']}


def collect(posts, handle):
    """(カテゴリ, 語) -> [(日付, 本文, URL)] を作る。文脈語ヒットは別に返す。

    照合は URL を除いた本文に対して行う。短縮URL（t.co/...GU... 等）が
    英字の語に一致してしまうため。
    """
    hits = defaultdict(list)
    context_posts = defaultdict(list)
    for t in posts:
        body = clean(t.get('text') or '')
        if not body:
            continue
        d = t['_dt'].date()
        url = t.get('url') or f"https://x.com/{handle}/status/{t.get('id')}"
        for cat, spec in CATEGORIES.items():
            for word in spec['words']:
                if MATCHERS[word](body):
                    hits[(cat, word)].append((d, body, url))
            if any(c in body for c in spec['context']):
                context_posts[cat].append((d, body, url))
    return hits, context_posts


def links(posts, handle):
    """他メンバーへの言及を、呼び方ごとに数える。自分自身は除く。"""
    found = defaultdict(lambda: {'calls': defaultdict(int), 'dates': [],
                                 'private': 0, 'examples': []})
    for t in posts:
        body = clean(t.get('text') or '')
        if not body:
            continue
        d = t['_dt'].date()
        url = t.get('url') or f"https://x.com/{handle}/status/{t.get('id')}"
        is_announce = any(m in body for m in ANNOUNCE_MARKERS)
        for other, name, patterns in MEMBER_LINKS:
            if other == handle:
                continue
            matched = [m.group(0) for p in patterns for m in re.finditer(p, body)]
            if not matched:
                continue
            rec = found[name]
            for m in matched:
                rec['calls'][m] += 1
            rec['dates'].append(d)
            if not is_announce:
                rec['private'] += 1
                rec['examples'].append((d, body, url))
    return found


def write(out, handle, label, posts, hits, context_posts, member_links, args):
    today = date.today()
    with open(out, 'w', encoding='utf-8') as f:
        def w(s=''):
            f.write(s + '\n')

        w(f'# 話題の在庫（候補）— {label} @{handle}')
        w()
        w(f'> 対象: {args.since} 〜 {args.until}／{len(posts)}件。'
          f'`.claude/skills/member-profile-refresh/scripts/topic_inventory.py` の機械抽出。')
        w('> **これは候補であって在庫表ではない。** 辞書のヒットには関係ない用法'
          '（「アイス」＝アイスブレイク等）が混ざるので、原文を読んで確かめてから'
          ' `members/*.md` に写す。')
        w()

        for cat in CATEGORIES:
            rows = sorted(
                ((word, occ) for (c, word), occ in hits.items() if c == cat),
                key=lambda kv: (-len(kv[1]), kv[0]),
            )
            rows = [(k, v) for k, v in rows if len(v) >= args.min_hits]
            w(f'## {cat}')
            w()
            if rows:
                w('| 語 | 回数 | 頻度 | 初出 | 最終言及 | 注意 | 用例（最新） |')
                w('| --- | --- | --- | --- | --- | --- | --- |')
                for word, occ in rows:
                    dates = sorted(d for d, _, _ in occ)
                    last = dates[-1]
                    stale = ' [古い]' if (today - last).days > args.stale_days else ''
                    latest = max(occ, key=lambda o: o[0])[1][:50].replace('|', '｜')
                    w(f'| {word} | {len(occ)} | {freq_label(len(occ))}{stale} | '
                      f'{dates[0]} | {last} | {NOISE.get(word, "")} | {latest} |')
            else:
                w('（辞書ヒットなし）')
            w()
            ctx = context_posts.get(cat, [])
            if ctx:
                recent = sorted(ctx, key=lambda o: o[0], reverse=True)[:15]
                w(f'<details><summary>文脈語で拾った投稿 {len(ctx)}件'
                  f'（最新15件。辞書に無い話題を探す用）</summary>')
                w()
                for d, body, url in recent:
                    w(f'- [{d}] {body[:110]} — {url}')
                w()
                w('</details>')
                w()

        w('## メンバーとのつながり')
        w()
        w('> **言及の多さは仲の良さではない。** 告知では全員に触れるので、判断材料は「私的」列'
          '（告知の語を含まない投稿での言及）のほう。呼び方の表記ゆれは原文のまま出している。')
        w()
        rows = sorted(member_links.items(), key=lambda kv: -kv[1]['private'])
        if rows:
            w('| 相手 | 言及 | うち私的 | 使っている呼び方 | 初出 | 最終言及 |')
            w('| --- | --- | --- | --- | --- | --- |')
            for name, rec in rows:
                dates = sorted(rec['dates'])
                calls = '／'.join(f'{k}({v})' for k, v in
                                 sorted(rec['calls'].items(), key=lambda kv: -kv[1])[:5])
                w(f'| {name} | {len(dates)} | {rec["private"]} | {calls} | '
                  f'{dates[0]} | {dates[-1]} |')
            w()
            for name, rec in rows:
                ex = sorted(rec['examples'], key=lambda o: o[0], reverse=True)[:5]
                if not ex:
                    continue
                w(f'<details><summary>{name} — 私的な言及 {rec["private"]}件（最新5件）</summary>')
                w()
                for d, body, url in ex:
                    w(f'- [{d}] {body[:110]} — {url}')
                w()
                w('</details>')
                w()
        else:
            w('（言及なし）')
            w()


def main():
    a = parse_args()
    handles = [h.strip() for h in a.accounts.split(',')] if a.accounts else \
        [h for h, _ in DEFAULT_ACCOUNTS if h != 'lollipop_1116']
    names = dict(DEFAULT_ACCOUNTS)
    missing = []
    for handle in handles:
        path = os.path.join(a.x_dir, f'{handle}.jsonl')
        if not os.path.exists(path):
            missing.append(handle)
            continue
        posts = load(path, a.since, a.until)
        if not posts:
            missing.append(f'{handle}（期間内0件）')
            continue
        hits, context_posts = collect(posts, handle)
        member_links = links(posts, handle)
        out = os.path.join(a.x_dir, f'topic_inventory_{handle}_{a.since}_{a.until}.md')
        write(out, handle, names.get(handle, handle), posts, hits, context_posts,
              member_links, a)
        print(f'{names.get(handle, handle)} @{handle}: {len(posts)}件 → {out}')
    if missing:
        print(f"未取得: {', '.join(missing)}（x-account-fetch で取得する）")


if __name__ == '__main__':
    main()
