#!/usr/bin/env bash
# 公開用の画像を撮る前に Noto Sans JP を入れる（Claude Code のリモート環境用）。
#
#   bash resources/install_capture_font.sh
#
# なぜ要るか: コンテナのヘッドレスChromiumは fonts.googleapis.com に到達できず
# （curl は proxy 経由で通るのにブラウザは ERR_CONNECTION_RESET）、コンテナの
# 日本語フォントは IPAGothic と WenQuanYi しか無い。そのまま撮ると WenQuanYi
# Zen Hei（中国語フォント）で漢字が描画され、字形の違う画像ができる。
# 詳しくは CLAUDE.md「実行環境の注意」。
set -euo pipefail

DEST=/usr/share/fonts/truetype/noto-sans-jp
# 古いUAで叩かないとTTFが返らない（現行UAはwoff2、IE系UAはEOT。
# どちらも fontconfig が読めない）
UA="Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8) AppleWebKit/533.21.1 (KHTML, like Gecko) Version/5.0.5 Safari/533.21.1"

mkdir -p "$DEST"
for weight in 400 500 700; do
    url=$(curl -fsS -H "User-Agent: $UA" \
        "https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@${weight}" \
        | grep -o 'https://fonts.gstatic.com[^)]*')
    if [ -z "$url" ]; then
        echo "weight ${weight} のURLが取れなかった。Google Fonts に到達できているか確認する" >&2
        exit 1
    fi
    curl -fsS -H "User-Agent: $UA" -o "${DEST}/NotoSansJP-${weight}.ttf" "$url"
    file -b "${DEST}/NotoSansJP-${weight}.ttf" | grep -q "TrueType" \
        || { echo "weight ${weight} がTTFで落ちてこなかった（UAを確認する）" >&2; exit 1; }
done

fc-cache -f > /dev/null
count=$(fc-list | grep -c "Noto Sans JP" || true)
echo "Noto Sans JP を ${count} 件登録した（${DEST}）"
[ "$count" -gt 0 ] || { echo "fontconfig に登録されていない" >&2; exit 1; }
