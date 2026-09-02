#!/bin/bash
# セッション引き継ぎに必要な現状を1画面にまとめる（読み取り専用。何も変更しない）。
# 使い方: bash .claude/skills/session-handoff/scripts/handoff_status.sh
cd "$(dirname "$0")/../../../.." || exit 1

echo "## ブランチと未コミットの変更"
echo "branch: $(git branch --show-current)"
git status --short | head -40
echo
echo "## origin/main に無いコミット"
git fetch -q origin main 2>/dev/null
git log --oneline origin/main..HEAD 2>/dev/null | head -20 || echo "(origin/main を取得できず)"
echo
echo "## work/ の中身（空が正常）"
files=$(find work -type f ! -name README.md 2>/dev/null)
if [ -n "$files" ]; then echo "$files"; else echo "(空)"; fi
echo
echo "## 各シリーズ README の「未解決」節"
for f in articles/*/README.md; do
  awk -v fn="$f" '/^## 未解決/{p=1; print "### " fn; next} p && /^## /{p=0} p' "$f"
done
echo
echo "## CLAUDE.md の進行中セクション"
awk '/^## .*（進行中）/{p=1} /^## 実行環境/{p=0} p' CLAUDE.md
echo
echo "## セトリ集計の不足月"
python3 .claude/skills/setlist-analysis/scripts/check_missing_months.py
echo
echo "## 取得済みの X 投稿（work/x_fetch）"
if ls work/x_fetch/*.jsonl >/dev/null 2>&1; then
  for j in work/x_fetch/*.jsonl; do echo "$(basename "$j"): $(wc -l < "$j") 件"; done
else
  echo "なし"
fi
