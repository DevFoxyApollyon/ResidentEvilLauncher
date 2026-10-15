"""Som do RE Hub.

- Efeitos da interface: os sons do PS5 em data/sons/ps5 (se existirem); senão, tons gerados pelo próprio app.
- Trilha de cada capítulo: o app NÃO traz as músicas oficiais (são da Capcom). Ele toca, nesta ordem:
  1) arquivos seus em data/musica/<id do capítulo>/ (mp3, wav, wma, m4a);
  2) trilhas sonoras compradas como DLC na Steam (steamapps/music);
  3) um tema original composto pelo próprio app para o capítulo (compose.py).
Tudo pelo áudio do próprio Windows (MCI), sem instalar nada.
"""
import ctypes
import json
import math
import queue
import random
import struct
import threading
import time
import wave
import winsound
from pathlib import Path

from . import compose, steam
from .paths import DATA

SOUNDS = DATA / "sons"
PS5 = SOUNDS / "ps5"
MUSIC = DATA / "musica"
MENU = MUSIC / "_menu"  # tema do menu: seções sem jogo (perdidos, filmes, HQs, fãs)
EXTS = {".mp3", ".wav", ".wma", ".m4a"}
ALIAS = "rehub_trilha"


# ---------- efeitos ----------
def _write_tone(path, parts, rate=22050):
    """parts: lista de (freq_inicial, freq_final, duração_s, volume)."""
    frames = bytearray()
    for f0, f1, dur, vol in parts:
        n = int(rate * dur)
        phase = 0.0
        for i in range(n):
            t = i / n
            phase += 2 * math.pi * (f0 + (f1 - f0) * t) / rate
            env = min(1.0, i / (rate * 0.004)) * (1 - t) ** 2  # ataque rápido, queda suave
            frames += struct.pack("<h", int(32767 * vol * env * math.sin(phase)))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(bytes(frames))


EFFECTS = {
    "hover": [(2300, 1700, 0.035, 0.16)],
    "select": [(520, 880, 0.09, 0.22), (1320, 1320, 0.05, 0.10)],
    "open": [(880, 880, 0.07, 0.22), (1320, 1320, 0.12, 0.20)],
    "tab": [(1500, 1100, 0.04, 0.14)],
}


def ensure_effects():
    SOUNDS.mkdir(parents=True, exist_ok=True)
    for name, parts in EFFECTS.items():
        p = SOUNDS / f"{name}.wav"
        if not p.exists():
            _write_tone(p, parts)


_starts = None


def start_ms(path):
    """Onde o som começa (medido por tools/audio_inicio.py, em data/musica/_inicio.json); 0 se não souber."""
    global _starts
    if _starts is None:
        try:
            _starts = json.loads((MUSIC / "_inicio.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _starts = {}
    try:
        return int(_starts.get(Path(path).resolve().relative_to(DATA.resolve()).as_posix(), 0))
    except ValueError:
        return 0


_last_effect = {}
PS5_SOUNDS = {  # efeito do app: arquivo em data/sons/ps5
    "hover": "Navigation", "select": "Navigation", "tab": "Navigation", "enter": "Navigation_Enter",
    "back": "Navigation_Back", "open": "Prompt", "prompt_enter": "Prompt_Enter", "prompt_back": "Prompt_Back",
    "menu_on": "Control_Center_On", "menu_off": "Control_Center_Off", "trophy": "Trophy_Notification",
    "inicio": "inicio",
}
FALLBACK = {"enter": "select", "back": "tab", "prompt_enter": "select", "prompt_back": "tab", "menu_on": "open",
            "menu_off": "tab", "trophy": "open"}


class _Fx:
    """Toca os mp3 dos efeitos pelo MCI numa thread só (cada arquivo fica aberto e é tocado do começo)."""

    def __init__(self):
        self._q = queue.Queue()
        self._open = set()
        threading.Thread(target=self._worker, daemon=True).start()

    def play(self, name, path, volume=1.0):
        self._q.put(("play", name, path, volume))

    def stop(self, name, fade=0.8):
        self._q.put(("stop", name, None, fade))

    def _worker(self):
        mci = ctypes.windll.winmm.mciSendStringW
        while True:
            cmd, name, path, arg = self._q.get()
            alias = f"rehub_fx_{name}"
            if cmd == "stop":
                if name in self._open:
                    for i in range(10, -1, -1):
                        mci(f"setaudio {alias} volume to {i * 100}", None, 0, 0)
                        time.sleep(arg / 10)
                    mci(f"stop {alias}", None, 0, 0)
                continue
            if name not in self._open:
                if mci(f'open "{path}" type mpegvideo alias {alias}', None, 0, 0) != 0:
                    continue
                self._open.add(name)
            mci(f"setaudio {alias} volume to {int(arg * 1000)}", None, 0, 0)
            mci(f"play {alias} from {start_ms(path)}", None, 0, 0)


_fx = None


def effect(name, min_gap=0.05, volume=0.8):
    """Toca um efeito sem travar a interface (ignora repetições muito rápidas)."""
    global _fx
    now = time.time()
    if now - _last_effect.get(name, 0) < min_gap:
        return
    _last_effect[name] = now
    mp3 = PS5 / f"{PS5_SOUNDS.get(name, name)}.mp3"
    if mp3.exists():
        _fx = _fx or _Fx()
        _fx.play(name, mp3, volume)
        return
    p = SOUNDS / f"{FALLBACK.get(name, name)}.wav"
    if p.exists():
        winsound.PlaySound(str(p), winsound.SND_FILENAME | winsound.SND_ASYNC | winsound.SND_NODEFAULT)


def stop_effect(name, fade=0.8):
    if _fx:
        _fx.stop(name, fade)


# ---------- trilha sonora ----------
def chapter_tracks(chapter, game=None):
    """Músicas disponíveis para o capítulo: pasta do usuário primeiro, depois trilhas da Steam.
    Itens sem jogo (perdidos, filmes, HQs, fãs) sem pasta própria tocam o tema do menu (data/musica/_menu)."""
    folders = [MUSIC / chapter["id"]]
    if game and game["id"] != chapter["id"]:  # música só desta versão (ex.: data/musica/re4_2005)
        folders.insert(0, MUSIC / game["id"])
    if chapter.get("secao") in ("perdidos", "midia", "hqs", "fas", "noticias"):
        folders.append(MENU)
    for own in folders:
        if own.is_dir():
            files = sorted(p for p in own.rglob("*") if p.suffix.lower() in EXTS)
            if files:
                return files
    keys = [k.lower() for k in chapter.get("trilha_busca", [])]
    root = steam.steam_path()
    if keys and root:
        for lib in steam.library_folders(root):
            music = lib / "steamapps" / "music"
            if not music.is_dir():
                continue
            for folder in sorted(music.iterdir()):
                name = folder.name.lower()
                if folder.is_dir() and any(k in name for k in keys):
                    files = sorted(p for p in folder.rglob("*") if p.suffix.lower() in EXTS)
                    if files:
                        return files
    try:  # sem trilha sua: o tema original que o app compõe para o capítulo
        return [compose.ensure(chapter["id"])]
    except Exception:
        return []


class Music:
    """Toca em loop a trilha do capítulo, com fade, numa thread própria (o MCI não gosta de várias threads)."""

    def __init__(self, volume=0.55):
        self.volume = volume
        self.enabled = True
        self.current = None
        self._q = queue.Queue()
        self._buf = ctypes.create_unicode_buffer(256)
        threading.Thread(target=self._worker, daemon=True).start()

    def play_chapter(self, chapter, game=None):
        self._q.put(("chapter", (chapter, game)))

    def set_enabled(self, on):
        self.enabled = on
        self._q.put(("enabled", on))

    def stop(self):
        self._q.put(("stop", None))

    # tudo abaixo roda só na thread de áudio
    def _mci(self, cmd):
        return ctypes.windll.winmm.mciSendStringW(cmd, self._buf, 256, 0)

    def _set_vol(self, v):
        self._mci(f"setaudio {ALIAS} volume to {int(max(0, min(1, v)) * 1000)}")

    def _fade(self, start, end, secs=0.6):
        steps = 15
        for i in range(1, steps + 1):
            self._set_vol(start + (end - start) * i / steps)
            time.sleep(secs / steps)

    def _close(self):
        if self.current:
            self._fade(self.volume, 0)
            self._mci(f"close {ALIAS}")
            self.current = None

    def _open(self, path):
        self._mci(f"close {ALIAS}")  # nunca duas trilhas ao mesmo tempo
        if self._mci(f'open "{path}" type mpegvideo alias {ALIAS}') != 0:
            return False
        self._set_vol(0)
        self._mci(f"set {ALIAS} time format milliseconds")
        self._mci(f"play {ALIAS} from {start_ms(path)} repeat")  # começa onde o som aparece (sem silêncio no início)
        self.current = path
        self._fade(0, self.volume, 1.0)
        return True

    def _worker(self):
        wanted = None
        while True:
            kind, value = self._q.get()
            while not self._q.empty():  # pulando capítulos rápido: só o último importa
                kind, value = self._q.get()
            if kind == "chapter":
                wanted = value
            elif kind == "stop":
                wanted = None
            if not self.enabled or wanted is None:
                self._close()
                continue
            try:
                tracks = chapter_tracks(*wanted)
            except OSError:
                tracks = []
            if not tracks:
                self._close()
            elif self.current not in tracks:  # várias músicas na pasta: uma diferente a cada visita
                self._close()
                self._open(random.choice(tracks))
