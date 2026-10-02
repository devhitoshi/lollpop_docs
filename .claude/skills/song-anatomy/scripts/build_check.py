#!/usr/bin/env python3
"""聴きながら解剖図を確かめるページ（check.html）を作る。ローカル専用。

    python build_check.py シーソーゲーム

音源と分離したステムを file:// で読むので、この PC でしか動かない。公開もコミットもしない。
図をクリックするとその位置から再生する。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import build_anatomy as fig
import common


PAGE = """<!doctype html><html lang="ja"><head><meta charset="utf-8"><title>__SONG__ 解剖図の確認</title>
<style>
__CSS__
body { padding:24px; }
#bar { position:sticky; top:0; background:#fff; padding:12px 0; z-index:2; display:flex; gap:16px; align-items:center; flex-wrap:wrap; }
#bar button, #bar select { font:inherit; padding:6px 14px; }
#now { font-size:22px; font-weight:700; color:#1d1216; min-width:5em; }
#where { font-size:16px; }
#wrap { position:relative; width:1152px; cursor:pointer; }
#head { position:absolute; top:0; bottom:0; width:2px; background:#1d1216; pointer-events:none; }
table { border-collapse:collapse; margin-top:24px; font-size:15px; }
td, th { padding:4px 14px 4px 0; text-align:left; } tr.on td { background:#fde6f1; }
td button { font:inherit; padding:2px 10px; }
</style></head><body>
<div id="bar">
  <button id="play">再生 / 停止</button>
  <span id="now">0:00.0</span>
  <label>聴く音 <select id="src">__OPTIONS__</select></label>
  <button data-skip="-5">5 秒戻る</button><button data-skip="5">5 秒進む</button>
  <span id="where"></span>
</div>
<div id="wrap">__SVG__<div id="head"></div></div>
<table><thead><tr><th>区間</th><th>始まり</th><th>終わり</th><th></th></tr></thead><tbody id="rows"></tbody></table>
<audio id="audio" preload="auto"></audio>
<script>
const A = __DATA__;
const audio = document.getElementById('audio'), src = document.getElementById('src');
const wrap = document.getElementById('wrap'), head = document.getElementById('head');
const fmt = t => Math.floor(t / 60) + ':' + (t % 60).toFixed(1).padStart(4, '0');
function load() { const t = audio.currentTime, on = !audio.paused; audio.src = src.value; audio.currentTime = t; if (on) audio.play(); }
src.onchange = load; load();
document.getElementById('play').onclick = () => audio.paused ? audio.play() : audio.pause();
document.querySelectorAll('[data-skip]').forEach(b => b.onclick = () => audio.currentTime += +b.dataset.skip);
wrap.onclick = e => { audio.currentTime = (e.clientX - wrap.getBoundingClientRect().left) / 1152 * A.duration; audio.play(); };
const rows = document.getElementById('rows');
A.sections.forEach((s, i) => {
  const tr = document.createElement('tr');
  tr.innerHTML = `<td>${s.name}</td><td>${fmt(s.start)}</td><td>${fmt(s.end)}</td><td><button>ここから</button> <button>2 秒前から</button></td>`;
  const [b1, b2] = tr.querySelectorAll('button');
  b1.onclick = () => { audio.currentTime = s.start; audio.play(); };
  b2.onclick = () => { audio.currentTime = Math.max(0, s.start - 2); audio.play(); };
  rows.appendChild(tr);
});
function frame() {
  const t = audio.currentTime;
  head.style.left = (t / A.duration * 1152) + 'px';
  document.getElementById('now').textContent = fmt(t);
  const i = A.sections.findIndex(s => t >= s.start && t < s.end);
  const line = A.lines.find(l => t >= l.start && t < l.end);
  document.getElementById('where').textContent = (i >= 0 ? A.sections[i].name : '') + (line ? ' ／ 行 ' + line.line_no + '「' + line.head + '…」' : '');
  [...rows.children].forEach((tr, k) => tr.classList.toggle('on', k === i));
  requestAnimationFrame(frame);
}
frame();
</script></body></html>"""


def main(song: str) -> None:
    a = fig.load(song)
    svg, _ = fig.build_svg(a)
    css = fig.PAGE.split("<style>")[1].split("</style>")[0]
    sources = [("曲全体", common.source_path(song))]
    sources += [(label, common.stems_dir(song) / f"{key}.wav") for key, label, _ in fig.STEMS]
    options = "".join(f'<option value="{p.as_uri()}">{label}</option>' for label, p in sources)
    data = {
        "duration": a["duration_sec"],
        "sections": [{k: s[k] for k in ("name", "start", "end")} for s in a["sections"]],
        "lines": [{k: l[k] for k in ("line_no", "head", "start", "end")} for l in a["lines"]],
    }
    out = PAGE
    for key, value in (("SONG", song), ("CSS", css), ("OPTIONS", options), ("SVG", svg), ("DATA", json.dumps(data, ensure_ascii=False))):
        out = out.replace(f"__{key}__", value)
    dst = common.work_dir(song) / "check.html"
    dst.write_text(out, encoding="utf-8", newline="")
    print("書き出し:", dst)


if __name__ == "__main__":
    main(sys.argv[1])
