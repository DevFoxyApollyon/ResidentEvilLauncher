"""Mods pelo Fluffy Mod Manager (FluffyQuack): o app baixa, abre e mostra a pasta de mods de cada jogo.

Quem instala, desinstala, ordena e faz backup dos mods é o Fluffy. Ele fica em data/ferramentas/FluffyModManager
e guarda os mods de cada jogo em Games/<código>/Mods (aceita .zip, .rar, .7z e pastas).
"""
import os
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

from . import github
from .paths import DATA

URL = "https://fluffyquack.com/tools/modmanager.zip"
HOME = DATA / "ferramentas" / "FluffyModManager"
EXE = HOME / "Modmanager.exe"
SITE = "https://www.fluffyquack.com/"
# id do jogo no catálogo -> pasta do jogo dentro de Games/ no Fluffy (o Fluffy cria a pasta ao escolher o jogo)
CODES = {"re2": "RE2R", "re3": "RE3R", "re4": "RE4R", "re7": "RE7", "village": "RE8", "requiem": "RE9"}
RE_ENGINE = set(CODES)  # jogos em que o REFramework faz sentido
# jogos do catálogo que o Fluffy (v3.084) sabe modar: os acima + RE HD, RE0 HD, RE5, RE6, Revelations 2 e os clássicos
SUPPORTED = RE_ENGINE | {"re1", "re0", "re5", "re6", "rev2", "re2_classic", "re3_classic"}


def supported(game_id):
    return game_id in SUPPORTED


def installed():
    return EXE.exists()


def version():
    """Versão instalada, lida da primeira linha do change-log (ex.: 'v3.084')."""
    try:
        return (HOME / "change-log.txt").read_text(encoding="latin-1").split(":", 1)[0].strip()
    except OSError:
        return ""


def download():
    """Baixa (ou atualiza) o Fluffy. Mantém os mods, os jogos configurados e as preferências dele."""
    with tempfile.TemporaryDirectory() as tmp:
        z = Path(tmp) / "modmanager.zip"
        req = urllib.request.Request(URL, headers={"User-Agent": "RE-Hub/1.0 (launcher pessoal)"})
        with urllib.request.urlopen(req, timeout=120) as r, open(z, "wb") as f:
            shutil.copyfileobj(r, f)
        staged = Path(tmp) / "x"
        github.extract_zip(z, staged)
        HOME.mkdir(parents=True, exist_ok=True)
        shutil.copytree(staged, HOME, dirs_exist_ok=True)  # por cima: Games/ e as configs dele ficam
    return version()


def open_manager():
    subprocess.Popen([str(EXE)], cwd=str(HOME))


def mods_dir(game_id, chosen=None):
    """Pasta de mods do jogo no Fluffy. chosen: a pasta que o usuário indicou (jogos sem código conhecido).
    Sem código nem escolha, devolve a pasta Games."""
    if chosen and Path(chosen).is_dir():
        return Path(chosen)
    code = CODES.get(game_id)
    if code:
        d = HOME / "Games" / code / "Mods"
        d.mkdir(parents=True, exist_ok=True)
        return d
    d = HOME / "Games"
    d.mkdir(parents=True, exist_ok=True)
    return d


def add_mod(game_id, path, chosen=None):
    """Copia um mod (.zip/.rar/.7z ou pasta) para a pasta de mods do jogo no Fluffy."""
    src, dest = Path(path), mods_dir(game_id, chosen)
    if src.is_dir():
        shutil.copytree(src, dest / src.name, dirs_exist_ok=True)
    else:
        shutil.copy2(src, dest / src.name)
    return dest


def add_reframework(game_id):
    """Põe o REFramework nightly (o que acompanha as atualizações dos jogos) na pasta de mods do jogo no Fluffy."""
    dest = mods_dir(game_id)
    with tempfile.TemporaryDirectory() as tmp:
        tag = github.download_release("praydog/REFramework-nightly", "REFramework.zip", Path(tmp) / "x")
        out = dest / "REFramework"
        shutil.rmtree(out, ignore_errors=True)
        shutil.copytree(Path(tmp) / "x", out)
        (out / "modinfo.ini").write_text(f"name=REFramework\nversion={tag}\nauthor=praydog\n"
                                         "description=Base para scripts e mods (nightly).\n", encoding="utf-8")
    return tag


def open_folder(path):
    os.startfile(path)


def old_mods(game_id):
    """Mods que o sistema antigo do app deixou ativos no jogo (para poder desfazer)."""
    import json
    state = DATA / "mods" / game_id / "state.json"
    try:
        return list(json.loads(state.read_text(encoding="utf-8")).get("ativos", {}))
    except (OSError, ValueError):
        return []

