#!/bin/bash
# SessionStart hook: 環境の準備と、引き継ぎに要る現状の要約を出す。
# 出力はそのままセッションの文脈に入るので、短く事実だけ。
cd "${CLAUDE_PROJECT_DIR:-$(dirname "$0")/../..}" || exit 0

# 曲調解析（librosa）は重いので、audio/ に音源があるときだけ入れる
if ls audio/*.{mp3,wav,flac,m4a,aac,ogg,opus} >/dev/null 2>&1; then
  if ! python3 -c "import librosa, soundfile" >/dev/null 2>&1; then
    python3 -m pip install -q -r .claude/skills/music-analysis/scripts/requirements.txt >/dev/null 2>&1 \
      && echo "librosa/soundfile をインストールした（audio/ に音源あり）" \
      || echo "librosa のインストールに失敗。曲調解析の前に手動で pip install する"
  fi
fi

# X の取得データを非公開リポジトリから復元する（work/x_fetch/ はコンテナが変わると消えるため）
DATA_DIR="${LOLLPOP_DATA_DIR:-$(cd .. && pwd)/lollpop_data}"
if [ ! -d "$DATA_DIR" ]; then
  git clone -q https://github.com/devhitoshi/lollpop_data "$DATA_DIR" >/dev/null 2>&1 || true
fi
if [ -d "$DATA_DIR/x" ]; then
  python3 .claude/skills/x-data-sync/scripts/sync_x_data.py pull 2>/dev/null | grep -c '^  復元' | { read -r n; [ "$n" -gt 0 ] && echo "X 取得データ: lollpop_data から ${n} ファイル復元"; } || true
else
  echo "X 取得データの退避先 lollpop_data が無い（必要なら add_repo → git clone ../lollpop_data → x-data-sync pull）"
fi

echo "[lollpop_docs 起動時サマリ]"
echo "ブランチ: $(git branch --show-current 2>/dev/null)"
dirty=$(git status --short 2>/dev/null | wc -l | tr -d ' ')
echo "未コミットの変更: ${dirty} 件"
echo "セトリ集計: $(python3 .claude/skills/setlist-analysis/scripts/check_missing_months.py 2>/dev/null)"
if [ -n "${TWITTERAPI_IO_KEY:-}" ] || [ -f .env ]; then echo "twitterapi.io キー: あり（.env または環境変数）"; else echo "twitterapi.io キー: なし"; fi
if ls work/x_fetch/*.jsonl >/dev/null 2>&1; then
  echo "取得済み X 投稿: $(ls work/x_fetch/*.jsonl | xargs -n1 basename | tr '\n' ' ')"
else
  echo "取得済み X 投稿: なし（週刊・月刊を書くなら先に x-account-fetch）"
fi
echo "引き継ぎの正: articles/*/README.md の「未解決」節と CLAUDE.md の進行中セクション（終わりに session-handoff で更新）"
exit 0
