"""Trailer de cada jogo numa telinha dentro do app.

Pega o trailer principal da página do jogo na Steam (.mp4), converte uma vez para .wmv com o ffmpeg
(o Windows toca .wmv sozinho, sem instalar nada) e guarda em data/trailers. Quem toca é o MCI do Windows,
desenhando o vídeo dentro de um quadro da janela.
"""
import ctypes
import json
import subprocess
import urllib.request

from .paths import DATA

TRAILERS = DATA / "trailers"
FFMPEG = DATA / "ferramentas" / "ffmpeg.exe"
ALIAS = "rehub_trailer"
UA = {"User-Agent": "RE-Hub/1.0 (launcher pessoal)"}


def _mci(cmd):
    buf = ctypes.create_unicode_buffer(256)
    r = ctypes.windll.winmm.mciSendStringW(cmd, buf, 256, 0)
    return r, buf.value


def movie(appid):
    """(id, nome, miniatura) do trailer em destaque na Steam, ou None."""
    url = f"https://store.steampowered.com/api/appdetails?appids={appid}&filters=movies&l=brazilian"
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        data = json.load(r).get(str(appid), {}).get("data", {})
    movies = data.get("movies") or []
    if not movies:
        return None
    m = next((m for m in movies if m.get("highlight")), movies[0])
    return m["id"], m.get("name", ""), m.get("thumbnail")


def ensure(appid):
    """Baixa e converte (uma vez). Devolve o caminho do .wmv. Lança RuntimeError com mensagem para o usuário."""
    out = TRAILERS / f"{appid}.wmv"
    if out.exists() and out.stat().st_size > 0:
        return out
    if not FFMPEG.exists():
        raise RuntimeError("Falta o ffmpeg em data/ferramentas para preparar os trailers.")
    m = movie(appid)
    if not m:
        raise RuntimeError("Esse jogo não tem trailer na Steam.")
    TRAILERS.mkdir(parents=True, exist_ok=True)
    mp4 = TRAILERS / f"{appid}.mp4"
    for src in (f"https://cdn.akamai.steamstatic.com/steam/apps/{m[0]}/movie480.mp4",
                f"https://cdn.akamai.steamstatic.com/steam/apps/{m[0]}/movie_max.mp4"):
        try:
            with urllib.request.urlopen(urllib.request.Request(src, headers=UA), timeout=60) as r:
                mp4.write_bytes(r.read())
            break
        except OSError:
            continue
    else:
        raise RuntimeError("Não deu para baixar o trailer da Steam.")
    tmp = out.with_suffix(".tmp.wmv")
    subprocess.run([str(FFMPEG), "-v", "error", "-y", "-i", str(mp4), "-vf", "scale=640:-2", "-c:v", "wmv2", "-q:v", "5",
                    "-c:a", "wmav2", "-b:a", "128k", str(tmp)], check=True,
                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    tmp.replace(out)
    mp4.unlink(missing_ok=True)
    return out


class Player:
    """Toca um .wmv dentro de um widget (pelo identificador da janela dele). Tudo na thread da interface."""

    def __init__(self):
        self.path = None

    def open(self, path, hwnd, w, h, sound=True):
        self.close()
        if _mci(f'open "{path}" type mpegvideo alias {ALIAS} parent {hwnd} style child')[0] != 0:
            return False
        self.path = path
        self.resize(w, h)
        self.set_sound(sound)
        _mci(f"play {ALIAS} repeat")
        return True

    def resize(self, w, h):
        if self.path:
            _mci(f"put {ALIAS} window at 0 0 {w} {h}")

    def set_sound(self, on):
        if self.path:
            _mci(f"setaudio {ALIAS} volume to {600 if on else 0}")

    def toggle_pause(self):
        if not self.path:
            return False
        mode = _mci(f"status {ALIAS} mode")[1]
        _mci(f"{'resume' if mode == 'paused' else 'pause'} {ALIAS}")
        return mode != "paused"  # True = ficou pausado

    def close(self):
        if self.path:
            _mci(f"close {ALIAS}")
            self.path = None
