"""Compositor de temas originais para cada capítulo.

Nada aqui é música da Capcom: cada tema é sintetizado na hora (notas, timbres e efeitos gerados por código),
em um de cinco climas inspirados no estilo da série. A mesma semente gera sempre o mesmo tema para o capítulo.
"""
import hashlib
import wave

import numpy as np

from .franchise import FR
from .paths import DATA

OUT = DATA / "musica_gerada"
SR = 22050
VERSION = 1  # mude para gerar todos os temas de novo

MOODS = {
    "saferoom": ["re0", "re1", "veronica", "rev1", "shadows_of_rose", "re1_5", "re_gbc", "re0_n64", "re_portable"],
    "tension": ["re2", "re3", "outbreak", "darkside_chronicles", "umbrella_chronicles", "survivor", "survivor2"],
    "gothic": ["re4", "village", "rev2", "re4_perdidos", "requiem"],
    "action": ["re5", "re6", "orc", "umbrella_corps", "resistance", "mercenaries3d", "dead_aim"],
    "dread": ["re7", "gaiden"],
}
MOOD_OF = {cid: mood for mood, ids in MOODS.items() for cid in ids}
MOOD_OF.update({cid: mood for mood, ids in FR["temas"].items() for cid in ids})  # capítulos de outra franquia
SCALES = {"minor": [0, 2, 3, 5, 7, 8, 10], "harmonic": [0, 2, 3, 5, 7, 8, 11], "phrygian": [0, 1, 3, 5, 7, 8, 10]}


# ---------- timbres ----------
def _env(n, attack, release):
    e = np.ones(n)
    a, r = min(n, int(attack * SR)), min(n, int(release * SR))
    if a:
        e[:a] = np.linspace(0, 1, a)
    if r:
        e[-r:] *= np.linspace(1, 0, r)
    return e


def tone(freq, dur, kind):
    n = int(dur * SR)
    t = np.arange(n) / SR
    if kind == "piano":
        s = sum(np.sin(2 * np.pi * freq * k * (1 + 0.0004 * k * k) * t) * np.exp(-t * 2.2 * k ** 0.6) / k ** 1.3 for k in range(1, 7))
        return s * _env(n, 0.004, 0.08)
    if kind == "musicbox":
        s = np.sin(2 * np.pi * freq * t) + 0.25 * np.sin(2 * np.pi * freq * 4.01 * t) * np.exp(-t * 6)
        return s * np.exp(-t * 3.2) * _env(n, 0.002, 0.05)
    if kind == "bell":
        parts = [(1, 1.0, 1.1), (2.76, 0.5, 2.0), (5.4, 0.3, 3.0), (8.93, 0.15, 4.5)]
        return sum(a * np.sin(2 * np.pi * freq * p * t) * np.exp(-t * d) for p, a, d in parts) * _env(n, 0.002, 0.2)
    if kind == "organ":
        s = sum(a * np.sin(2 * np.pi * freq * k * t) for k, a in ((1, 0.6), (2, 0.35), (3, 0.2), (4, 0.12), (6, 0.06)))
        return s * (1 + 0.05 * np.sin(2 * np.pi * 5.5 * t)) * _env(n, 0.35, 0.8)
    if kind == "pad":  # cordas: três vozes levemente desafinadas
        s = sum(np.sin(2 * np.pi * freq * k * dt * t) / k for dt in (0.997, 1.0, 1.003) for k in range(1, 9))
        return s * _env(n, dur * 0.4, dur * 0.4) / 3
    if kind == "bass":
        s = np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
        return s * np.exp(-t * 3) * _env(n, 0.005, 0.05)
    if kind == "heart":  # batida de coração: "tum" grave que desce de tom
        f = 75 * np.exp(-t * 6) + 40
        return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t * 9)
    raise ValueError(kind)


def noise_wind(n, rng, amount):
    w = rng.standard_normal(n)
    k = np.ones(220) / 220  # passa-baixa simples: vento abafado
    w = np.convolve(w, k, mode="same")
    swell = 0.5 + 0.5 * np.sin(2 * np.pi * np.arange(n) / SR / 11 + rng.uniform(0, 6))
    return w * swell * amount / (np.abs(w).max() + 1e-9)


def reverb(x, rng, seconds=2.4, mix=0.3):
    n = int(seconds * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal(n) * np.exp(-t * 3 / seconds)
    ir = np.convolve(ir, np.ones(12) / 12, mode="same")  # cauda mais escura
    ir[0] = 0
    size = 1 << int(np.ceil(np.log2(len(x) + n)))
    wet = np.fft.irfft(np.fft.rfft(x, size) * np.fft.rfft(ir, size), size)[: len(x) + n]
    wet /= np.abs(wet).max() + 1e-9
    out = np.zeros(len(x) + n)
    out[: len(x)] += x / (np.abs(x).max() + 1e-9)
    return out * (1 - mix) + wet * mix


# ---------- composição ----------
def compose(cid, seconds=48):
    seed = int(hashlib.sha1(f"{cid}:{VERSION}".encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    mood = MOOD_OF.get(cid) or ["saferoom", "tension", "gothic", "dread"][seed % 4]
    scale = SCALES["harmonic" if mood in ("gothic", "saferoom") else "phrygian" if mood == "dread" else "minor"]
    root = 110 * 2 ** (rng.integers(-3, 5) / 12)  # tom de cada capítulo
    bpm = {"saferoom": 66, "tension": 96, "gothic": 72, "action": 112, "dread": 54}[mood] + int(rng.integers(-6, 7))
    beat = 60 / bpm
    total = int(seconds * SR)
    buf = np.zeros(total + 8 * SR)  # sobra para as caudas (depois "dobram" para o começo do loop)

    def put(sig, at, vol):
        i = int(at * SR)
        j = min(len(buf), i + len(sig))
        if i < len(buf):
            buf[i:j] += sig[: j - i] * vol

    def deg(d, octave=0):
        o, d = divmod(d, 7)
        return root * 2 ** ((scale[d] + 12 * (o + octave)) / 12)

    progression = [[0, 5, 2, 6], [0, 3, 4, 0], [0, 5, 3, 4], [0, 1, 0, 4]][int(rng.integers(0, 4))]
    bar = beat * 4
    bars = int(seconds // bar)
    lead = {"saferoom": "musicbox", "tension": "piano", "gothic": "bell", "action": "piano", "dread": "piano"}[mood]
    pad = "organ" if mood == "gothic" else "pad"
    motif = [int(x) for x in rng.choice([0, 2, 4, 3, 5, 6, 7, 9], size=8)]  # tema que se repete com variações

    for b in range(bars):
        start = b * bar
        chord = progression[b % 4]
        for d in (chord, chord + 2, chord + 4):  # acorde de fundo
            put(tone(deg(d, -1), bar * 1.05, pad), start, 0.16 if pad == "pad" else 0.12)
        if mood in ("tension", "action"):  # ostinato no grave
            for k in range(8):
                put(tone(deg(chord, -2) * (1.5 if k % 4 == 3 else 1), beat * 0.45, "bass"), start + k * beat / 2, 0.35)
        if mood == "action" or (mood == "tension" and b % 2):
            for k in range(4):  # batida de coração
                put(tone(0, 0.35, "heart"), start + k * beat, 0.6 if k % 2 == 0 else 0.35)
        if mood == "dread" and rng.random() < 0.5:  # cluster de piano dissonante
            for d in (chord, chord + 1, chord + 3):
                put(tone(deg(d, 0), 3.0, "piano"), start + rng.uniform(0, bar * 0.6), 0.12)
        if mood == "gothic" and b % 2 == 0:  # sino grave
            put(tone(deg(chord, -1), 6.0, "bell"), start, 0.22)
        # melodia: o motivo, transposto para o acorde, com notas que às vezes somem (mais respiro)
        steps = 8 if mood in ("saferoom", "tension") else 4
        for k in range(steps):
            if rng.random() < (0.25 if mood == "dread" else 0.15):
                continue
            d = motif[(k + b) % len(motif)] + chord
            put(tone(deg(d, 1), beat * 2.5, lead), start + k * bar / steps, 0.22 if lead != "bell" else 0.12)

    if mood in ("dread", "tension", "gothic"):
        buf[:total] += noise_wind(total, rng, 0.05 if mood != "dread" else 0.09)

    wet = reverb(buf, rng, mix=0.35 if mood in ("saferoom", "gothic") else 0.25)
    loop = wet[:total].copy()
    tail = wet[total:]
    loop[: len(tail)] += tail[: total]  # o fim do som "dobra" para o início: loop sem emenda
    loop /= np.abs(loop).max() + 1e-9
    return (loop * 0.7 * 32767).astype(np.int16), mood


def ensure(cid):
    """Caminho do tema do capítulo, compondo na primeira vez (leva menos de 1 s)."""
    path = OUT / f"{cid}_v{VERSION}.wav"
    if not path.exists():
        OUT.mkdir(parents=True, exist_ok=True)
        pcm, _ = compose(cid)
        with wave.open(str(path), "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(SR)
            w.writeframes(pcm.tobytes())
    return path
