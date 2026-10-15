"""Onde cada jogo está instalado e como abrir."""
import hashlib
import shlex
import subprocess
from pathlib import Path

from . import steam
from .paths import RECOMPS


def game_dir(game, cfg, installed):
    """Pasta do jogo (onde os mods são instalados), ou None se ainda não existe."""
    if game["tipo"] == "steam":
        return installed.get(game["appid"])
    c = cfg.get(game["id"])
    if c.get("pasta"):
        return Path(c["pasta"])
    if c.get("exe"):
        return Path(c["exe"]).parent
    return None


def download_dir(game):
    return RECOMPS / game["id"] / "jogo"


def find_exe(game):
    """Depois de baixar, acha o executável indicado no catálogo (campo 'exe')."""
    name = game.get("exe")
    if not name:
        return None
    return next(download_dir(game).rglob(name), None)


def is_ready(game, cfg, installed):
    if game["tipo"] == "steam":
        return game["appid"] in installed
    return bool(cfg.get(game["id"]).get("exe"))


def play(game, cfg):
    """Abre o jogo. Lança RuntimeError com uma mensagem para o usuário se faltar algo."""
    if game["tipo"] == "steam":
        steam.run(game["appid"])
        return
    c = cfg.get(game["id"])
    exe = Path(c.get("exe", ""))
    if not exe.is_file():
        raise RuntimeError(f"Executável não encontrado:\n{exe}\n\nUse Configurar para escolher de novo.")
    args = game.get("args", "")
    if "{iso}" in args and not c.get("iso"):
        raise RuntimeError("Esse jogo precisa da sua ISO. Clique em Configurar.")
    # troca {iso} depois de separar, para caminhos com espaço continuarem um argumento só
    argv = [t.strip('"').replace("{iso}", c.get("iso", "")) for t in shlex.split(args, posix=False)]
    subprocess.Popen([str(exe), *argv], cwd=exe.parent)


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
