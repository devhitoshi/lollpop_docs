# -*- coding: utf-8 -*-
"""スターターパック（note全3回）の図版を生成する。

design.md のカラートークンをそのまま使う。matplotlib は使わない
（この記事の図版は統計プロットではなくレイアウト主体で、Pillow のほうが制御しやすいため）。
2倍サイズで描いて LANCZOS で縮小し、文字を滑らかにしている。

実行: python articles/スターターパック/img/make_figures.py
"""
from PIL import Image, ImageDraw, ImageFont
import os

OUT = os.path.dirname(os.path.abspath(__file__))
S = 2  # supersampling

# --- design.md のトークン ---
C = {
    "primary": "#d6006e", "primary_active": "#b0005b",
    "ink": "#1d1216", "body": "#45383e", "body_strong": "#2a2026",
    "muted": "#71646b", "muted_soft": "#998a92",
    "hairline": "#f2e2ea", "hairline_soft": "#faeef4",
    "canvas": "#ffffff", "surface_soft": "#fff5f9",
    "surface_blush": "#fbe7f0", "surface_blush_strong": "#f6d3e3",
    "surface_dark": "#1a1113", "on_dark": "#fff5f9", "on_dark_soft": "#d9c4ce",
    "primary_on_dark": "#ff9ecb",
    "chart_orig": "#d6006e", "chart_stk": "#2a6fd6", "chart_hpst": "#eda100",
    "chart_axis": "#dcc8d2",
    "kurumi": "#cc0000", "mayu": "#f5c400", "mau": "#7fd4e8",
    "ami": "#2e9e5b", "mana": "#ffffff",
}
FB = "C:/Windows/Fonts/YuGothB.ttc"   # Bold
FR = "C:/Windows/Fonts/YuGothR.ttc"   # Regular

def f(size, bold=True):
    return ImageFont.truetype(FB if bold else FR, size * S)

def canvas(w, h, bg="canvas"):
    im = Image.new("RGB", (w * S, h * S), C[bg])
    return im, ImageDraw.Draw(im)

def save(im, name):
    w, h = im.size
    im.resize((w // S, h // S), Image.LANCZOS).save(os.path.join(OUT, name))
    print("wrote", name)

def text(d, xy, s, font, fill, anchor="la"):
    d.text((xy[0] * S, xy[1] * S), s, font=font, fill=fill, anchor=anchor)

def rect(d, box, fill=None, outline=None, width=1, radius=0):
    b = [v * S for v in box]
    if radius:
        d.rounded_rectangle(b, radius=radius * S, fill=fill, outline=outline, width=width * S)
    else:
        d.rectangle(b, fill=fill, outline=outline, width=width * S)


# ---------------------------------------------------------------- headers
def header(name, kicker, title, sub, accent):
    im, d = canvas(1280, 670)
    rect(d, (0, 0, 1280, 12), fill=accent)                 # 上端のブランドバー
    text(d, (96, 150), kicker, f(28), C["primary"])
    y = 210
    for line in title:
        text(d, (96, y), line, f(72), C["ink"]); y += 92
    text(d, (96, y + 24), sub, f(30, False), C["muted"])
    # 右下にメンバーカラーのドット
    x = 1280 - 96 - 5 * 44
    for key in ["kurumi", "mana", "mau", "mayu", "ami"]:
        col = C[key]
        d.ellipse([x * S, 560 * S, (x + 28) * S, 588 * S], fill=col,
                  outline=C["hairline"] if key == "mana" else None, width=2 * S)
        x += 44
    text(d, (96, 600), "ろりぽっぷ!!!!!!! スターターパック / 非公式ファンドキュメント",
         f(22, False), C["muted_soft"])
    save(im, name)

header("01_header.png", "STARTER PACK 1 / 3", ["まず、", "どんなグループなのか"],
       "ろりぽっぷ!!!!!!! の基本・歩み・楽曲", C["primary"])
header("02_header.png", "STARTER PACK 2 / 3", ["メンバーを知って、", "推しを決める"],
       "5人のキャラクターと、話しかけるときのネタ", C["chart_stk"])
header("03_header.png", "STARTER PACK 3 / 3", ["ライブに行って、", "特典会で話す"],
       "準備・当日の流れ・コール・特典会", C["chart_hpst"])


# ---------------------------------------------------------------- 01 年表
def timeline():
    im, d = canvas(1280, 820)
    text(d, (80, 60), "ろりぽっぷ!!!!!!! の歩み", f(46), C["ink"])
    text(d, (80, 122), "2024年11月のデビューから、5人体制の始動まで", f(26, False), C["muted"])

    rows = [
        ("2024.11.16", "サウンドノート秋葉原でデビューライブ", False),
        ("2025.03.30", "1stワンマン「始まりの宴!!!!!!」代官山UNIT／松川愛美の加入を発表", False),
        ("2025.08", "AFA Creators Super Fest Singapore 2025 に出演", False),
        ("2025.11.24", "1st Anniversary LIVE「ろりぽの挑戦!!!!!!!」赤羽ReNY alpha", False),
        ("2026.04.22", "姫杏朝香が卒業", False),
        ("2026.06.06", "3rdワンマン「全力疾走」新宿ReNY", False),
        ("2026.08.15", "苺花なつみが卒業", False),
        ("2026.08.22", "5人体制が始動（「ガラストロメ!!」）", True),
    ]
    x_line = 300
    y = 200
    step = 74
    d.line([x_line * S, (y - 20) * S, x_line * S, (y + step * (len(rows) - 1) + 20) * S],
           fill=C["hairline"], width=3 * S)
    for date, label, hi in rows:
        col = C["primary"] if hi else C["chart_axis"]
        r = 11 if hi else 7
        d.ellipse([(x_line - r) * S, (y - r) * S, (x_line + r) * S, (y + r) * S],
                  fill=col, outline=C["canvas"], width=3 * S)
        text(d, (x_line - 34, y), date, f(26, hi), C["primary"] if hi else C["muted"], anchor="rm")
        text(d, (x_line + 34, y), label, f(28, hi), C["ink"] if hi else C["body"], anchor="lm")
        y += step

    rect(d, (80, 740, 1200, 744), fill=C["hairline"])
    text(d, (80, 762), "会場は 代官山UNIT → 赤羽ReNY alpha → 新宿ReNY と大きくなっている",
         f(24, False), C["muted"])
    save(im, "01_timeline.png")
timeline()


# ---------------------------------------------------------------- 01 ルーツ
def roots():
    im, d = canvas(1280, 800)
    text(d, (80, 56), "曲は3つの出どころに分かれる", f(46), C["ink"])
    text(d, (80, 118), "ライブ中に「あ、これはストクレの曲だな」と分かるようになります", f(26, False), C["muted"])

    cols = [
        (C["chart_orig"], "オリジナル曲", "ろりぽっぷ!!!!!!! 名義", "結成後に作られた曲",
         ["ろりぽっぷ!!!!!!!", "ぽっぽ♪ポジティブ！！", "始まりの宴!!!!!!!", "乙女ロック", "Unknown",
          "約束!!!!!!!", "主人公!!!!!!!", "未完成ヒロイン", "シーソーゲーム", "メイク☆マイダンス", "夏色ラムネ"]),
        (C["chart_stk"], "ストクレ曲", "元 STRAY SHEEP CLAYMORE", "かっこいい系が多め",
         ["SHINY DAYS", "HELLO", "MY DREAM MY LIFE", "むげんの☆Lambie", "ほか"]),
        (C["chart_hpst"], "ハピスト曲", "元 ハピ☆スト", "かわいい系が多め",
         ["推し事〜女の子アイドル", "　オタクあるある〜", "サクラロード", "アタックサイン", "ほか"]),
    ]
    x = 80
    w = 360
    for col, title, sub, desc, songs in cols:
        rect(d, (x, 190, x + w, 750), fill=C["surface_soft"])
        rect(d, (x, 190, x + w, 198), fill=col)
        text(d, (x + 28, 226), title, f(34), col)
        text(d, (x + 28, 274), sub, f(22, False), C["muted"])
        text(d, (x + 28, 310), desc, f(23, False), C["body"])
        y = 366
        for s in songs:
            text(d, (x + 28, y), s, f(23, False), C["body_strong"]); y += 34
        x += w + 40
    save(im, "01_roots.png")
roots()


# ---------------------------------------------------------------- 01 ランキング
def ranking():
    im, d = canvas(1280, 700)
    text(d, (80, 56), "よく演奏される曲 トップ6", f(46), C["ink"])
    text(d, (80, 118), "2024年11月16日〜2026年8月31日／326公演・のべ1,607回の集計", f(26, False), C["muted"])

    data = [("ろりぽっぷ!!!!!!!", 185, "orig"), ("ぽっぽ♪ポジティブ！！", 166, "orig"),
            ("始まりの宴!!!!!!!", 143, "orig"), ("SHINY DAYS", 118, "stk"),
            ("推し事〜女の子アイドルオタクあるある〜", 105, "hpst"), ("HELLO", 101, "stk")]
    kind = {"orig": C["chart_orig"], "stk": C["chart_stk"], "hpst": C["chart_hpst"]}
    x0, bar_max, y = 560, 560, 210
    for name, v, k in data:
        w = int(bar_max * v / 185)
        text(d, (x0 - 24, y + 22), name, f(26), C["body_strong"], anchor="rm")
        rect(d, (x0, y, x0 + w, y + 44), fill=kind[k])
        text(d, (x0 + w + 16, y + 22), str(v), f(30), kind[k], anchor="lm")
        y += 66

    ly = 630
    text(d, (80, ly), "凡例", f(22), C["muted"])
    lx = 150
    for label, k in [("オリジナル", "orig"), ("ストクレ", "stk"), ("ハピスト", "hpst")]:
        rect(d, (lx, ly + 4, lx + 22, ly + 22), fill=kind[k])
        text(d, (lx + 32, ly), label, f(22, False), C["body"])
        lx += 190
    text(d, (1200, ly), "単位: 回", f(22, False), C["muted_soft"], anchor="ra")
    save(im, "01_ranking.png")
ranking()


# ---------------------------------------------------------------- 02 メンバー早見表
def members():
    im, d = canvas(1280, 850)
    text(d, (80, 56), "現メンバー5人 早見表", f(46), C["ink"])
    text(d, (80, 118), "担当カラーの並びは公式の表記に合わせています（2026年8月22日〜の5人体制）",
         f(26, False), C["muted"])

    rows = [
        ("kurumi", "やぎ くるみ", "くるみん", "赤", "リーダー／群馬県", "群馬の話"),
        ("mana",   "愛月 まな",   "まなてぃー", "白", "癒し系／鹿児島県", "猫の話"),
        ("mau",    "まう",       "まう〜",   "水色", "自由奔放／鹿児島県", "グミの話"),
        ("mayu",   "夏川 茉夢",   "おまゆ",   "黄色", "お姉さん肌／静岡県", "餃子と静岡"),
        ("ami",    "松川 愛美",   "あみてん", "緑", "2025年加入／東京都", "ライブの感想"),
    ]
    # ヘッダ行
    hy = 196
    text(d, (200, hy), "名前", f(24), C["muted"])
    text(d, (470, hy), "あだ名", f(24), C["muted"])
    text(d, (650, hy), "特徴・出身", f(24), C["muted"])
    text(d, (960, hy), "話しかけるなら", f(24), C["muted"])
    rect(d, (80, hy + 40, 1200, hy + 42), fill=C["hairline"])

    y = 264
    for key, name, nick, color, feat, topic in rows:
        rect(d, (80, y - 14, 1200, y + 82), fill=C["surface_soft"])
        rect(d, (80, y - 14, 92, y + 82), fill=C[key],
             outline=C["hairline"] if key == "mana" else None, width=2)
        text(d, (124, y + 6), color, f(26), C["muted"])
        text(d, (200, y), name, f(32), C["ink"])
        text(d, (200, y + 44), "", f(20), C["muted"])
        text(d, (470, y + 12), nick, f(28), C["body_strong"])
        text(d, (650, y + 12), feat, f(25, False), C["body"])
        text(d, (960, y + 12), topic, f(26), C["primary"])
        y += 106

    text(d, (80, 800), "推しは1回で決めなくて大丈夫。グループ全体を推す「箱推し」もこのグループでは多数派です。",
         f(24, False), C["muted"])
    save(im, "02_members.png")
members()


# ---------------------------------------------------------------- 03 お金
def money():
    im, d = canvas(1280, 830)
    text(d, (80, 56), "初回にかかるお金", f(46), C["ink"])
    text(d, (80, 118), "対バン1本＋特典会1回のイメージ", f(26, False), C["muted"])

    items = [
        ("チケット", "イベントによる", "ワンコインライブなら500円"),
        ("ドリンク代", "500〜600円", "多くのライブハウスで別途必要"),
        ("写メ券", "1,000円", "スマホでツーショット＋トーク"),
        ("チェキ券", "1,500円", "チェキ＋トーク＋サイン"),
    ]
    y = 196
    for label, price, note in items:
        rect(d, (80, y, 1200, y + 88), fill=C["surface_soft"])
        text(d, (112, y + 22), label, f(32), C["ink"])
        text(d, (600, y + 20), price, f(32), C["primary"], anchor="ra")
        text(d, (640, y + 30), note, f(23, False), C["muted"])
        y += 100

    rect(d, (80, y + 20, 1200, y + 152), fill=C["surface_blush"])
    text(d, (112, y + 46), "初めての方は、公式Xをフォローするだけで写メ券が1枚無料",
         f(32), C["primary_active"])
    text(d, (112, y + 96), "最初の1回は、チケット代とドリンク代だけでメンバーと話せます",
         f(26, False), C["body"])
    save(im, "03_money.png")
money()


# ---------------------------------------------------------------- 03 当日の流れ
def flow():
    im, d = canvas(1280, 560)
    text(d, (80, 56), "ライブ当日の流れ", f(46), C["ink"])
    text(d, (80, 118), "対バンイベントの場合", f(26, False), C["muted"])

    steps = [
        ("1", "会場に着く", "開演の少し前で十分\n整理番号順に入場"),
        ("2", "ドリンク代", "受付で支払い\nカウンターで交換"),
        ("3", "フロアへ", "好きな場所でOK\n後ろでも数m"),
        ("4", "出番を見る", "20〜30分\n5曲前後"),
        ("5", "特典会", "券を買って\n列に並ぶ"),
    ]
    x, w, gap = 80, 200, 24
    for i, (num, title, note) in enumerate(steps):
        top = 200
        rect(d, (x, top, x + w, top + 250), fill=C["surface_soft"])
        rect(d, (x, top, x + w, top + 6), fill=C["primary"])
        d.ellipse([(x + 20) * S, (top + 28) * S, (x + 64) * S, (top + 72) * S], fill=C["primary"])
        text(d, (x + 42, top + 50), num, f(26), C["canvas"], anchor="mm")
        text(d, (x + 20, top + 96), title, f(25), C["ink"])
        yy = top + 146
        for line in note.split("\n"):
            text(d, (x + 20, yy), line, f(21, False), C["muted"]); yy += 30
        if i < len(steps) - 1:
            cx = x + w + gap // 2
            text(d, (cx, top + 125), "›", f(40), C["chart_axis"], anchor="mm")
        x += w + gap

    text(d, (80, 490), "途中から入っても、目当ての出番だけ見て帰ってもかまいません。普通にいます。",
         f(24, False), C["muted"])
    save(im, "03_flow.png")
flow()


# ---------------------------------------------------------------- 03 コール難易度
def calls():
    im, d = canvas(1280, 690)
    text(d, (80, 56), "覚えるのは3曲でいい", f(46), C["ink"])
    text(d, (80, 118), "コール表26曲のうち、最初から最後まで埋まっていて初見でも入れるのはこの3曲",
         f(26, False), C["muted"])

    rows = [
        ("ぽっぽ♪ポジティブ！！", 1, "初見で参加できます", "「ぽ！」と言うだけ。リズムに合わせれば入れます"),
        ("始まりの宴!!!!!!!", 2, "真似すれば大丈夫", "「ソイヤッ！」を真似する。落ちサビは見るだけでOK"),
        ("ろりぽっぷ!!!!!!!", 3, "覚えなくていい", "メンバーがその場で指示を出します。予習しようがない"),
    ]
    y = 196
    for name, lv, verdict, note in rows:
        rect(d, (80, y, 1200, y + 124), fill=C["surface_soft"])
        text(d, (112, y + 22), name, f(32), C["ink"])
        # 星
        sx = 112
        for i in range(3):
            col = C["primary"] if i < lv else C["hairline"]
            text(d, (sx, y + 74), "★", f(28), col)
            sx += 34
        text(d, (240, y + 74), verdict, f(26), C["primary_active"])
        text(d, (620, y + 46), note, f(23, False), C["body"])
        y += 142

    rect(d, (80, 626, 1200, 628), fill=C["hairline"])
    text(d, (80, 644), "他の曲も記載は増えているが「新体制のため確認中」の箇所が多い。コールは義務ではありません。",
         f(24, False), C["muted"])
    save(im, "03_calls.png")
calls()
