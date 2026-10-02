"""embed_x.js からブックマークレット（bookmarklet.txt）を作る。embed_x.js を直したら実行する。"""
import re
from pathlib import Path
from urllib.parse import quote

here = Path(__file__).parent
src = (here / 'embed_x.js').read_text(encoding='utf-8')
src = re.sub(r'/\*.*?\*/', '', src, flags=re.S)  # 先頭のコメントを落とす（// コメントは使わない）
code = ' '.join(line.strip() for line in src.splitlines() if line.strip())
(here / 'bookmarklet.txt').write_text('javascript:' + quote(code, safe="()=>{}[];,.:'!*/-_~ &|?+$@"), encoding='utf-8')
print(f'bookmarklet.txt: {len(code)} chars')
