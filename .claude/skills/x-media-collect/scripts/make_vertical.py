"""横向きの素材から、縦型（9:16）の告知動画を組み立てる。

横の映像を切り取らずに 1080x1920 の中央へ置き、上下の帯にテロップを入れる構成。
背景は同じ映像をぼかして敷き詰めるので、黒帯だけの画面より見栄えがする。

構成は JSON で渡す（`--spec`）。1区間＝1つの素材で、区間を順につないで書き出す。

    {
      "out": "work/x_media/vertical_2026-08.mp4",
      "segments": [
        {"file": "...mp4", "start": 3, "duration": 12,
         "top": "2026.8.26 単独ライブ Vol.18", "bottom": "新曲「夏色ラムネ」お披露目"},
        {"file": "...jpg", "duration": 3, "top": "次はここ", "bottom": "9/20（日）単独ライブ Vol.19"}
      ]
    }

- `file` が画像なら静止画の区間になる（`duration` 必須）
- `top` / `bottom` は改行を入れて複数行にできる
- 音は各動画区間のものを使う。`"mute": true` で無音にできる
  （TikTok などでアプリ内の公式音源を選ぶ前提なら消しておく）

色は design.md のトークン。フォントは日本語が出るものを自動で探す（`--font` で指定可）。

使い方:
    python3 .claude/skills/x-media-collect/scripts/make_vertical.py --spec work/vertical_spec.json
"""
import argparse
import csv
import glob
import json
import os
import shutil
import subprocess
import sys
import tempfile

script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '../../../../'))
os.chdir(project_root)

W, H = 1080, 1920
FPS = 30
# design.md のトークン
INK = 'white'            # 暗い帯の上なので白。on-dark(#fff5f9) 相当
ACCENT = '0xff9ecb'      # primary-on-dark。暗帯上の唯一のアクセント
BAND = 'black@0.55'
BAND_H = 430             # 上下の帯の高さ。16:9 を中央に置くと上下に 656px ずつ空く
TOP_Y, BOTTOM_Y = 150, 1580
FONT_CANDIDATES = [
    '/usr/share/fonts/opentype/ipafont-gothic/ipag.ttf',
    '/usr/share/fonts/truetype/fonts-japanese-gothic.ttf',
    '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc',
]
IMAGE_EXT = {'.jpg', '.jpeg', '.png', '.webp'}
MANIFEST = 'work/x_media/manifest.csv'
CREDIT_Y = H - 62        # 下帯のいちばん下。テロップとぶつからない位置
CREDIT_SIZE = 30


def parse_args():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('--spec', required=True, help='構成を書いた JSON')
    p.add_argument('--font', help='日本語フォントの ttf/ttc')
    p.add_argument('--keep-temp', action='store_true', help='中間ファイルを残す（不具合を追うとき）')
    return p.parse_args()


def find_font(explicit):
    for f in ([explicit] if explicit else []) + FONT_CANDIDATES:
        if f and os.path.exists(f):
            return f
    for f in glob.glob('/usr/share/fonts/**/*.tt[cf]', recursive=True):
        if any(k in f.lower() for k in ('ipa', 'noto', 'jp', 'cjk', 'gothic')):
            return f
    sys.exit('日本語フォントが見つからない。--font で指定する')


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"ffmpeg 失敗:\n{' '.join(cmd[:14])} ...\n{r.stderr[-1500:]}")


def esc(text):
    """drawtext 用の退避。バックスラッシュ・コロン・引用符・パーセント。"""
    return (text.replace('\\', r'\\').replace(':', r'\:')
                .replace("'", r"\'").replace('%', r'\%'))


def drawtext_filters(text, font, y, size, color, line_gap=14):
    """複数行を中央寄せで置く drawtext の並びを返す。y は1行目の上端。"""
    out = []
    for i, line in enumerate([l for l in text.split('\n') if l.strip()]):
        out.append(
            f"drawtext=fontfile='{font}':text='{esc(line)}':fontcolor={color}:fontsize={size}"
            f":x=(w-text_w)/2:y={y + i * (size + line_gap)}:borderw=3:bordercolor=black@0.6"
        )
    return out


def load_manifest():
    """ファイル名 → 出典（撮影者・出どころ）。fetch_media.py が書いたもの。"""
    if not os.path.exists(MANIFEST):
        return {}
    return {r['file']: r for r in csv.DictReader(open(MANIFEST, encoding='utf-8'))}


def credit_for(seg, manifest):
    """区間のクレジット文字列を決める。決められない区間は書き出さない。

    クレジットは「あとで付ける」ものにすると必ず抜けるので、
    素材と同じところ（manifest.csv ＝ fetch_media が残した出典）から機械的に作り、
    映像に焼き込む。manifest に無い素材（自分で撮ったものなど）は spec に
    `"credit"` を明記してもらう。省略は許さない。
    """
    if seg.get('credit'):
        return str(seg['credit'])
    row = manifest.get(os.path.basename(seg['file']))
    if not row:
        sys.exit(
            f"クレジットが決められない: {seg['file']}\n"
            f"  {MANIFEST} に出典が無い。fetch_media.py で落とした素材ならそこに載る。\n"
            f"  自分で撮ったものなど手元の素材は、spec のその区間に "
            f'"credit": "撮影: 自分" のように明記する'
        )
    author = row.get('author', '')
    if row.get('source') == '公式':
        return f"提供: ろりぽっぷ!!!!!!! 公式（@{author}）"
    if row.get('source') == 'メンバー':
        return f"提供: @{author}（メンバー）"
    return f"撮影: @{author}"


def build_segment(seg, idx, font, tmp, credit):
    """1区間を 1080x1920 の mp4 にする。"""
    src = seg['file']
    if not os.path.exists(src):
        sys.exit(f"素材が無い: {src}")
    is_image = os.path.splitext(src)[1].lower() in IMAGE_EXT
    dur = float(seg.get('duration') or 5)
    out = os.path.join(tmp, f"seg{idx:02d}.mp4")

    # 背景: 画面いっぱいに広げてぼかす。前景: 幅 1080 に収めて中央へ置く（切り取らない）
    chain = [
        f"[0:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},"
        "gblur=sigma=28,eq=brightness=-0.18[bg]",
        f"[0:v]scale={W}:-2[fg]",
        "[bg][fg]overlay=(W-w)/2:(H-h)/2[base]",
        f"[base]drawbox=x=0:y=0:w={W}:h={BAND_H}:color={BAND}:t=fill,"
        f"drawbox=x=0:y={H - BAND_H}:w={W}:h={BAND_H}:color={BAND}:t=fill[banded]",
    ]
    texts = []
    if seg.get('top'):
        texts += drawtext_filters(seg['top'], font, TOP_Y, 62, INK)
    if seg.get('bottom'):
        texts += drawtext_filters(seg['bottom'], font, BOTTOM_Y, 58, ACCENT)
    # クレジットは全区間に必ず入れる（外せる引数は用意しない）
    texts += drawtext_filters(credit, font, CREDIT_Y, CREDIT_SIZE, 'white@0.85')
    last = '[banded]'
    if texts:
        chain.append(last + ','.join(texts) + '[out]')
        last = '[out]'
    filt = ';'.join(chain)

    common = ['-r', str(FPS), '-c:v', 'libx264', '-preset', 'medium', '-crf', '20',
              '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-ar', '44100', '-ac', '2']
    if is_image:
        cmd = ['ffmpeg', '-v', 'error', '-loop', '1', '-t', str(dur), '-i', src,
               '-f', 'lavfi', '-t', str(dur), '-i', 'anullsrc=r=44100:cl=stereo',
               '-filter_complex', filt, '-map', last, '-map', '1:a'] + common + ['-shortest', out, '-y']
    elif seg.get('mute'):
        cmd = ['ffmpeg', '-v', 'error', '-ss', str(seg.get('start', 0)), '-t', str(dur), '-i', src,
               '-f', 'lavfi', '-t', str(dur), '-i', 'anullsrc=r=44100:cl=stereo',
               '-filter_complex', filt, '-map', last, '-map', '1:a'] + common + ['-shortest', out, '-y']
    else:
        cmd = ['ffmpeg', '-v', 'error', '-ss', str(seg.get('start', 0)), '-t', str(dur), '-i', src,
               '-filter_complex', filt, '-map', last, '-map', '0:a?'] + common + [out, '-y']
    run(cmd)
    return out


def main():
    args = parse_args()
    spec = json.load(open(args.spec, encoding='utf-8'))
    font = find_font(args.font)
    out = spec.get('out') or 'work/x_media/vertical.mp4'
    os.makedirs(os.path.dirname(out) or '.', exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='vertical_')
    try:
        manifest = load_manifest()
        # 1区間でもクレジットが決まらなければ、1本も書き出さずに止める
        credits = [credit_for(seg, manifest) for seg in spec['segments']]
        parts = []
        for i, seg in enumerate(spec['segments']):
            print(f"  区間 {i + 1}/{len(spec['segments'])}: "
                  f"{os.path.basename(seg['file'])}  [{credits[i]}]")
            parts.append(build_segment(seg, i, font, tmp, credits[i]))
        lst = os.path.join(tmp, 'list.txt')
        with open(lst, 'w', encoding='utf-8') as f:
            for p in parts:
                f.write(f"file '{p}'\n")
        run(['ffmpeg', '-v', 'error', '-f', 'concat', '-safe', '0', '-i', lst, '-c', 'copy', out, '-y'])
    finally:
        if args.keep_temp:
            print(f"  中間ファイル: {tmp}")
        else:
            shutil.rmtree(tmp, ignore_errors=True)
    size = os.path.getsize(out) / 1024 / 1024
    dur = subprocess.run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                          '-of', 'csv=p=0', out], capture_output=True, text=True).stdout.strip()
    print(f"書き出した: {out}（{size:.1f} MB / {float(dur):.1f} 秒 / {W}x{H} / フォント {os.path.basename(font)}）")
    print("クレジットは各区間に焼き込み済み: " + ' / '.join(dict.fromkeys(credits)))
    print("投稿の説明文にも同じ出典を書く。楽曲はアプリ内の公式音源を使う"
          "（data/x/media_permissions.md）")


if __name__ == '__main__':
    main()
