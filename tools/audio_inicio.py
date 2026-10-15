"""Acha onde o som de verdade começa em cada música (pula silêncio e introdução baixinha).

Salva em data/musica/_inicio.json: {"caminho relativo a data/": milissegundos}. O app começa a tocar dali.
Precisa do ffmpeg só aqui (pip install imageio-ffmpeg); o app em si não precisa.
Uso: python tools/audio_inicio.py      (rode de novo depois de colocar músicas novas)
"""
import json
import math
import struct
import subprocess
from pathlib import Path

import imageio_ffmpeg

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = DATA / "musica" / "_inicio.json"
RATE, WIN = 8000, 0.05  # mono 8 kHz, janelas de 50 ms
EXTS = {".mp3", ".wav", ".wma", ".m4a"}


def loudness(path):
    raw = subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(), "-v", "quiet", "-i", str(path), "-ac", "1", "-ar", str(RATE),
                          "-f", "s16le", "-"], capture_output=True, check=True).stdout
    n = int(RATE * WIN)
    out = []
    for i in range(0, len(raw) // 2 - n, n):
        chunk = struct.unpack_from(f"<{n}h", raw, i * 2)
        out.append(math.sqrt(sum(v * v for v in chunk) / n) / 32768)
    return out


def start_ms(levels, frac=0.3):
    """Primeiro ponto em que o volume passa de 30% do nível típico da música (percentil 90)."""
    if not levels:
        return 0
    typical = sorted(levels)[int(len(levels) * 0.9)]
    limit = max(0.01, typical * frac)
    for i, v in enumerate(levels):
        if v >= limit:
            return max(0, int((i * WIN - 0.15) * 1000))  # começa um pouquinho antes, para não cortar o ataque
    return 0


def main():
    files = [p for p in (DATA / "musica").rglob("*") if p.suffix.lower() in EXTS] + [DATA / "sons" / "ps5" / "inicio.mp3"]
    result = {}
    for p in files:
        if p.exists():
            ms = start_ms(loudness(p))
            result[p.relative_to(DATA).as_posix()] = ms
            print(f"{ms / 1000:6.2f}s  {p.relative_to(DATA)}")
    OUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
