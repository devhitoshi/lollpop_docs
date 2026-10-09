#!/usr/bin/env python3
"""音源を Demucs でボーカル・ドラム・ベース・その他に分ける。

    .claude/skills/song-anatomy/.venv/Scripts/python .claude/skills/song-anatomy/scripts/separate.py シーソーゲーム

出力は audio/stems/<曲名>/（.gitignore 済みの場所）。音源と同じく、コミットも共有もしない。
"""
from __future__ import annotations

import datetime
import json
import sys
import tempfile
from pathlib import Path

import soundfile as sf
import torch

import demucs
from demucs.apply import apply_model
from demucs.pretrained import get_model

from common import SR, STEMS, sha256, source_path, stems_dir, to_wav

MODEL = "htdemucs"


def main(song: str) -> None:
    src = source_path(song)
    out = stems_dir(song)
    out.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        wav_path = Path(tmp) / "mix.wav"
        to_wav(src, wav_path)
        audio, sr = sf.read(str(wav_path), dtype="float32", always_2d=True)
    assert sr == SR
    wav = torch.from_numpy(audio.T.copy())

    model = get_model(MODEL)
    model.eval()
    device = "cuda" if torch.cuda.is_available() else "cpu"
    # demucs.separate と同じ正規化（曲全体の平均と標準偏差で揃えてから分け、あとで戻す）
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std()
    with torch.no_grad():
        sources = apply_model(model, ((wav - mean) / std)[None], device=device, split=True, overlap=0.25, progress=True)[0]
    sources = sources * std + mean

    for name, source in zip(model.sources, sources):
        sf.write(str(out / f"{name}.wav"), source.T.cpu().numpy(), SR, subtype="PCM_16")
        print("書き出し:", out / f"{name}.wav")
    assert set(model.sources) == set(STEMS)

    meta = {
        "song": song,
        "source_file": src.name,
        "source_sha256": sha256(src),
        "model": MODEL,
        "demucs": demucs.__version__,
        "torch": torch.__version__,
        "device": device,
        "sample_rate": SR,
        "separated_at": datetime.date.today().isoformat(),
    }
    (out / "stems_meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")


if __name__ == "__main__":
    main(sys.argv[1])
