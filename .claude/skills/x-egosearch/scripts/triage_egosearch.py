"""エゴサーチ候補の一次仕分け（機械）。最終判定は Claude が行う。

fetch_egosearch.py の JSONL を読み、投稿ごとに「ろりぽっぷ!!!!!!!（アイドル）の話か」の手がかりを点数化して
3つに分ける。人（Claude）が読むのは「要判定」だけで済むようにするのが目的。

  採用候補  … グループ名の正式表記・公式タグ・メンバー名・曲名など強い手がかりがある
  要判定    … 「ろりぽ」だけ、文脈語だけ、など弱い手がかり
  除外候補  … 同名の別物（ロッテ「爽 夏色ラムネ」、別グループの同名曲、名古屋の Lollipop♡CHU、レンタルサーバー、
              メイドカフェ、らりろりぽっぷん等）や懸賞スパムの語を含む

点数の根拠は本ファイルの表にある。新しいノイズ源を見つけたら NOISE に足す（判定の再現性を保つため、
判定基準はチャットではなくここに残す）。

使い方:
    python3 .claude/skills/x-egosearch/scripts/triage_egosearch.py --since 2026-08-01 --until 2026-08-31
    python3 ... --decisions work/x_fetch/egosearch_decisions_2026-08-01_2026-08-31.txt   # Claude の判定を反映して最終リストを出す

--decisions のファイルは1行1件「<id> adopt|reject [メモ]」。要判定のうち書かれていないものは除外扱い（迷ったら除外）。
判定ファイルと集計は data/x/（追跡）に置く。生データが消えても、復元（x-data-sync）→ このスクリプトで採用リストが戻る。
"""
import argparse
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)
sys.path.insert(0, os.path.join(project_root, '.claude/skills/x-account-fetch/scripts'))
from fetch_accounts import DEFAULT_ACCOUNTS  # noqa: E402

JST = timezone(timedelta(hours=9))
OWN = {h for h, _ in DEFAULT_ACCOUNTS} | {'asaka_lpop', 'natsumi_lpop'}
# 本人と見られる別ハンドル（投稿内容から判断。2026-08 の判定で @Ichii_h77 は苺花なつみ本人の生誕祭告知・お礼を投稿していた）
OWN |= {'Ichii_h77'}
OUT_DIR = 'work/x_fetch'   # 生データと、原文を含む中間ファイル（コミットしない）
DATA_DIR = 'data/x'        # 判定・件数など自分の成果物（コミットする）

# 強い手がかり（+3）: 正式表記・公式/メンバーの固有タグ・公式ハンドル
STRONG = re.compile(r'ろりぽっぷ\s*[!！‼︎]{2,}|#ろりぽっぷ\b|#ろりぽっぷ(?![ぁ-ん])|lollipop_1116|_lpop\b|#ぽっぱー|#くるみるく|#くるみんとKP|#餃子のおまゆ|#まんてんあみてん|#まなてぃータイム|#まうだよ|#苺花庭園|#苺花なつみ生誕祭')
# メンバー名・愛称（+2）
MEMBER = re.compile(r'愛月まな|まなてぃ|やぎくるみ|くるみん|夏川茉夢|おまゆ|松川愛美|あみてん|苺花なつみ|姫杏朝香|まうちゃん|くるみちゃん|あみちゃん|まなちゃん|なっちゃん|なつみちゃん')
# 曲名（+2）。「主人公」「約束」は一般語なので「!」付きか他の手がかりと併用
SONG = re.compile(r'未完成ヒロイン|ぽっぽ♪ポジティブ|始まりの宴|メイク[☆★]?マイダンス|シーソーゲーム|乙女ロック|Singularity|MADOROMI|SHINY DAYS|キミノセイ、|アタックサイン|推し事|むげんの[☆★]Lambie|END THE WORLD|正解の方程式|主人公[!！]{3,}|約束[!！]{3,}')
# グループ名の緩い表記（+1）
LOOSE = re.compile(r'ろりぽっぷ|ろりぽ(?![ぁ-んー])|ろりぽ㌠|ろりぽちゃん|ろりぽっぷちゃん')
# アイドル文脈（+1）
CONTEXT = re.compile(r'アイドル|ライブ|対バン|セトリ|特典会|チェキ|写メ|現場|生誕|ワンマン|物販|出演|レス|フロア|タイテ|トリ|サイリウム|ぽっぱー')
# 会場・イベント（+1）
PLACE = re.compile(r'新宿MARZ|MARZ|中野坂上|SUB TOKYO|VAMPKIN|鴨川|VIDENT|ガルガル|TOKYO GIRLS GIRLS|POPGALAXY|ガラストロメ|クモリニキ|ニキプレ|POP CRUSH|idolliveinfo|SPLASH|立川|DHNoA|ViBlue|Zirco|ReNY|お台場|白絵葵子')
# ノイズ（-3）: 同名の別物・懸賞スパム
NOISE = re.compile(r'爽|アイス|LOTTE|ロッテ|パイン|ソーダ|あいりんく|琴宮あいり|Lollipop♡CHU|ろりちゅ|ろりまじゅ|_LC\b|サーバー|サーバ\b|ドメイン|WordPress|ムームー|レンタル|ホスティング|メイドカフェ|コンカフェ|マジカルロリポップ|らりろりぽっぷん|ぽろりぽろり|魔法少女ろりぽっぷ|ヒロイン.*ルート|夏宮らむね|声劇|ボイストランド|現金|paypay|振り込み|卓球部|保育|幼稚園|小学校|名古屋|ロリポップチェーンソー|チェーンソー|キャンディ|ペロペロ|ろりぽっぷ小学校|ぷりたんぺぺると|ラーメン.*ろりぽ|ろりぽん', re.I)


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--since', required=True)
    p.add_argument('--until', required=True)
    p.add_argument('--decisions', help='Claude の判定ファイル（1行「<id> adopt|reject [メモ]」）。省略時は data/x/egosearch_decisions_<since>_<until>.txt があればそれ')
    p.add_argument('--snippet', type=int, default=110, help='要判定リストの本文の長さ')
    return p.parse_args()


def jst(t):
    created = t.get('createdAt') or ''
    try:
        return datetime.strptime(created, '%a %b %d %H:%M:%S %z %Y').astimezone(JST)
    except ValueError:
        return None


def score(text):
    s, why = 0, []
    if STRONG.search(text): s += 3; why.append('強')
    if MEMBER.search(text): s += 2; why.append('名')
    if SONG.search(text): s += 2; why.append('曲')
    if LOOSE.search(text): s += 1; why.append('緩')
    if CONTEXT.search(text): s += 1; why.append('文')
    if PLACE.search(text): s += 1; why.append('場')
    if NOISE.search(text): s -= 3; why.append('雑')
    return s, ''.join(why)


def line(t, snippet):
    d = jst(t)
    a = t.get('author') or {}
    txt = ' '.join((t.get('text') or '').split())
    return (f"{t.get('id')}|{d.strftime('%m/%d %H:%M') if d else '--'}|@{a.get('userName', '')}|"
            f"♥{t.get('likeCount', 0)}/👁{t.get('viewCount', 0)}|{txt[:snippet]}")


def main():
    args = parse_args()
    raw = os.path.join(OUT_DIR, f"egosearch_{args.since}_{args.until}.jsonl")
    posts = []
    for l in open(raw, encoding='utf-8'):
        try:
            t = json.loads(l)
        except json.JSONDecodeError:
            continue
        a = t.get('author') or {}
        if a.get('userName') in OWN:
            continue
        d = jst(t)
        if not d or not (args.since <= d.date().isoformat() <= args.until):
            continue
        t['_score'], t['_why'] = score(t.get('text') or '')
        posts.append(t)
    posts.sort(key=lambda t: jst(t))

    # グループの手がかり（強・名・曲・緩）がひとつも無いものは、文脈語や会場名だけでは判定できないので除外
    # （2-2「ロリポップ」や 2-4 のイベント名・曲名だけで当たった、他グループや別物の投稿がここに集まる）
    def has_group_signal(t):
        return any(k in t['_why'] for k in ('強', '名', '曲', '緩'))
    adopt = [t for t in posts if t['_score'] >= 3]
    reject = [t for t in posts if t['_score'] <= -1 or not has_group_signal(t)]
    review = [t for t in posts if 0 <= t['_score'] <= 2 and has_group_signal(t)]

    decisions = {}
    dec_path = args.decisions or os.path.join(DATA_DIR, f"egosearch_decisions_{args.since}_{args.until}.txt")
    if os.path.exists(dec_path):
        print(f"判定ファイル: {dec_path}")
        for l in open(dec_path, encoding='utf-8'):
            parts = l.strip().split(None, 2)
            if len(parts) >= 2 and parts[1] in ('adopt', 'reject'):
                decisions[parts[0]] = (parts[1], parts[2] if len(parts) > 2 else '')

    base = os.path.join(OUT_DIR, f"egosearch_triage_{args.since}_{args.until}")
    with open(base + '_review.txt', 'w', encoding='utf-8') as f:
        f.write("# 要判定（id|日時|投稿者|♥いいね/👁表示|本文）。Claude が読んで decisions に adopt/reject を書く\n")
        for t in review:
            f.write(f"[{t['_score']}{t['_why']}] " + line(t, args.snippet) + '\n')
    with open(base + '_adopt.txt', 'w', encoding='utf-8') as f:
        f.write("# 採用候補（強い手がかりあり）。念のため目を通し、外すものは decisions に reject と書く\n")
        for t in adopt:
            f.write(f"[{t['_score']}{t['_why']}] " + line(t, args.snippet) + '\n')
    with open(base + '_reject.txt', 'w', encoding='utf-8') as f:
        f.write("# 除外候補（同名の別物など）。誤って落としたものがあれば decisions に adopt と書く\n")
        for t in reject:
            f.write(f"[{t['_score']}{t['_why']}] " + line(t, 80) + '\n')

    print(f"候補 {len(posts)} 件 → 採用候補 {len(adopt)} / 要判定 {len(review)} / 除外候補 {len(reject)}")
    print(f"  {base}_adopt.txt / _review.txt / _reject.txt")

    if decisions:
        final = []
        for t in posts:
            dec = decisions.get(str(t.get('id')))
            if dec:
                if dec[0] == 'adopt':
                    final.append(t)
            elif t['_score'] >= 3:
                final.append(t)
        out = base + '_final.jsonl'
        with open(out, 'w', encoding='utf-8') as f:
            for t in final:
                f.write(json.dumps(t, ensure_ascii=False) + '\n')
        # 採用したIDだけを追跡ディレクトリにも残す。final.jsonl は原文を含むので退避対象外＝コンテナが変わると消えるが、
        # ID の一覧があれば x-media-collect の索引は判定を効かせたまま作り直せる
        os.makedirs(DATA_DIR, exist_ok=True)
        adopted_path = os.path.join(DATA_DIR, f"egosearch_adopted_{args.since}_{args.until}.txt")
        with open(adopted_path, 'w', encoding='utf-8') as f:
            f.write(f"# エゴサーチで採用と判定した投稿ID（{args.since}〜{args.until}・{len(final)} 件）\n")
            for t in final:
                f.write(f"{t.get('id')}\n")
        n_rej = len(posts) - len(final)
        print(f"最終: 採用 {len(final)} / 除外 {n_rej}（判定ファイル {len(decisions)} 行を反映） → {out}")
        # 記事・定点観測で使う抜粋: いいね上位と、期間内の日別件数
        os.makedirs(DATA_DIR, exist_ok=True)
        top = sorted(final, key=lambda t: (t.get('likeCount', 0), t.get('viewCount', 0)), reverse=True)[:40]
        with open(base + '_top.txt', 'w', encoding='utf-8') as f:
            f.write("# 採用のうち反応上位40件（要旨を書くときに原文を読む）\n")
            for t in top:
                f.write(line(t, 200) + f"|{t.get('url', '')}\n")
        days = Counter(jst(t).date().isoformat() for t in final)
        media = sum(1 for t in final if (t.get('extendedEntities') or {}).get('media'))
        first = [t for t in final if re.search(r'初めて|初見|初現場', t.get('text') or '')]
        summary_path = os.path.join(DATA_DIR, f"egosearch_triage_{args.since}_{args.until}_summary.txt")
        with open(summary_path, 'w', encoding='utf-8') as f:
            f.write(f"採用 {len(final)} 件／除外 {n_rej} 件（期間 {args.since}〜{args.until}）\n")
            f.write(f"メディア付き {media} 件、初見らしき語を含む {len(first)} 件\n")
            f.write("日別: " + ', '.join(f"{d[5:]}:{n}" for d, n in sorted(days.items())) + '\n')
            f.write("投稿者数: " + str(len({(t.get('author') or {}).get('userName') for t in final})) + '\n')
        print(f"  {base}_top.txt / {summary_path} / {adopted_path}")


if __name__ == '__main__':
    main()
