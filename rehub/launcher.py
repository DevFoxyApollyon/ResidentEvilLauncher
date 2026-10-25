"""Onde cada jogo está instalado e como abrir."""
import hashlib
import shlex
import shutil
import subprocess
import threading
import webbrowser
from pathlib import Path

from . import emulators, steam
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
    if game.get("mobile"):   # port para celular: joga-se no aparelho, nunca conta como instalado no PC
        return False
    c = cfg.get(game["id"])
    if game.get("url"):   # versao que abre um site (adicionada pela pessoa)
        return True
    if game.get("emulador"):   # emulador baixado pelo hub: precisa tambem da ISO da pessoa
        return bool(c.get("exe") and c.get("iso"))
    return bool(c.get("exe"))


def play(game, cfg):
    """Abre o jogo. Lança RuntimeError com uma mensagem para o usuário se faltar algo. Retorna um aviso
    quando o jogo só abre depois do passo 'preparar' (que roda em segundo plano)."""
    if game["tipo"] == "steam":
        steam.run(game["appid"])
        return None
    if game.get("url"):   # versao adicionada pela pessoa que e um site: abre direto no navegador
        webbrowser.open(game["url"])
        return None
    c = cfg.get(game["id"])
    exe = Path(c.get("exe", ""))
    if not exe.is_file():
        raise RuntimeError(f"Executável não encontrado:\n{exe}\n\nUse Configurar para escolher de novo.")
    args = emulators.args_for(game) or game.get("args", "")
    if "{iso}" in args and not c.get("iso"):
        raise RuntimeError("Esse jogo precisa da sua ISO. Clique em Configurar.")
    argv = split_args(args, c)
    prep = prepare_cmd(game, c, exe)
    if not prep:
        subprocess.Popen([str(exe), *argv], cwd=exe.parent)
        return None

    def run():
        with open(exe.parent / "preparar.log", "w", encoding="utf-8") as log:
            subprocess.run(prep, cwd=exe.parent, stdout=log, stderr=subprocess.STDOUT, creationflags=NO_WINDOW)
        subprocess.Popen([str(exe), *argv], cwd=exe.parent)
    threading.Thread(target=run).start()
    return game["preparar"].get("aviso")


NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def split_args(args, c):
    # troca {iso} depois de separar, para caminhos com espaço continuarem um argumento só
    return [t.strip('"').replace("{iso}", c.get("iso", "")) for t in shlex.split(args, posix=False)]


def prepare_cmd(game, c, exe):
    """O passo 'preparar' do catálogo (um script Python na pasta do jogo que roda antes dele, ex.: gerar
    os mods de tradução a partir do disco), ou None se não houver, faltar o Python ou já estiver feito.
    O script recebe --check para dizer (código 0) que não precisa rodar."""
    prep = game.get("preparar")
    if not prep:
        return None
    argv = split_args(prep["cmd"], c)
    python = shutil.which("python") or shutil.which("py")
    if not python or not (exe.parent / argv[0]).is_file():
        return None
    cmd = [python, *argv]
    done = subprocess.run([*cmd, "--check"], cwd=exe.parent, capture_output=True, creationflags=NO_WINDOW)
    return None if done.returncode == 0 else cmd


def sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()
