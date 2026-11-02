"""Emuladores que o hub baixa e configura sozinho para os jogos que ainda nao tem port de PC.

O jogo no catalogo diz qual usa ("emulador": "pcsx2"), o hub baixa a versao mais nova (GitHub ou, no
caso do Dolphin, o site oficial) para data/recomps/_emuladores/<nome> uma vez so, e a pessoa so
escolhe a ISO dela. Os jogos nunca sao baixados: so o emulador.
"""
import datetime
import fnmatch
import tempfile
import urllib.request
from pathlib import Path

from . import github
from .paths import RECOMPS

EMU_DIR = RECOMPS / "_emuladores"

EMULATORS = {
    "pcsx2": {"nome": "PCSX2", "sistema": "PS2", "repo": "PCSX2/pcsx2", "asset": "pcsx2-v*-windows-x64-qt.7z",
              "exe": "pcsx2-qt.exe", "args": '-fullscreen -nogui "{iso}"', "site": "https://pcsx2.net"},
    "duckstation": {"nome": "DuckStation", "sistema": "PS1", "repo": "stenzek/duckstation",
                    "asset": "duckstation-windows-x64-release.zip", "exe": "duckstation-qt-x64-ReleaseLTCG.exe",
                    "args": '-fullscreen "{iso}"', "site": "https://www.duckstation.org"},
    "dolphin": {"nome": "Dolphin", "sistema": "Wii / GameCube", "exe": "Dolphin.exe", "args": '-b -e "{iso}"',
                "site": "https://dolphin-emu.org"},
    "azahar": {"nome": "Azahar", "sistema": "3DS", "repo": "azahar-emu/azahar", "asset": "azahar-windows-msvc-*[0-9].zip",
               "exe": "azahar.exe", "args": '"{iso}"', "site": "https://azahar-emu.org"},
    "mgba": {"nome": "mGBA", "sistema": "Game Boy Color", "repo": "mgba-emu/mgba", "asset": "mgba-*-win64.7z",
             "exe": "mGBA.exe", "args": '-f "{iso}"', "site": "https://mgba.io"},
}
IMAGE_TYPES = {
    "pcsx2": "*.iso *.chd *.bin *.cso",
    "duckstation": "*.cue *.chd *.bin *.iso *.pbp",
    "dolphin": "*.iso *.wbfs *.rvz *.gcm *.ciso",
    "azahar": "*.3ds *.cci *.cxi *.3dsx *.app",
    "mgba": "*.gbc *.gb *.zip",
}


def of(game):
    return EMULATORS.get(game.get("emulador", ""))


# o que dá para mudar por versão (Gerenciar > Perfil do emulador), só por linha de comando: o emulador não é mexido
PROFILE_OPTIONS = {"pcsx2": ("tela_cheia",), "duckstation": ("tela_cheia",), "mgba": ("tela_cheia",),
                   "dolphin": ("tela_cheia", "escala", "widescreen"), "azahar": ()}
SCALES = (0, 1, 2, 3, 4, 5, 6)   # Dolphin: resolução interna (0 = a do emulador, 1 = nativa, 2 = 2x...)


def args_for(game, profile=None):
    """Argumentos do emulador para a versão, com o perfil dela: {"tela_cheia": bool, "escala": int,
    "widescreen": bool, "extra": "argumentos a mais"}. Sem perfil, os de sempre."""
    e = of(game)
    if not e:
        return None
    args, p, key = e["args"], profile or {}, game["emulador"]
    fs = p.get("tela_cheia")
    if fs is not None:
        if key in ("pcsx2", "duckstation"):
            args = args.replace("-fullscreen", "-fullscreen" if fs else "-nofullscreen")
        elif key == "mgba":
            args = args.replace("-f ", "-f " if fs else "")
        elif key == "dolphin":
            args = f"-C Dolphin.Display.Fullscreen={fs} " + args
    if key == "dolphin":
        if p.get("escala"):
            args = f"-C GFX.Settings.InternalResolution={int(p['escala'])} " + args
        if p.get("widescreen") is not None:
            args = f"-C GFX.Settings.wideScreenHack={bool(p['widescreen'])} " + args
    if p.get("extra", "").strip():
        args = p["extra"].strip() + " " + args
    return args


def folder(key):
    return EMU_DIR / key


def find(key):
    d = folder(key)
    return next(d.rglob(EMULATORS[key]["exe"]), None) if d.exists() else None


def _dolphin_url():
    """O Dolphin publica no próprio site (dl.dolphin-emu.org/releases/AAMM): a mais nova que existir."""
    today = datetime.date.today()
    y, m = today.year % 100, today.month
    for _ in range(24):
        v = f"{y:02d}{m:02d}"
        url = f"https://dl.dolphin-emu.org/releases/{v}/dolphin-{v}-x64.7z"
        try:
            req = urllib.request.Request(url, method="HEAD", headers=github.HEADERS)
            with urllib.request.urlopen(req, timeout=15):
                return url, v
        except Exception:
            pass
        m -= 1
        if m == 0:
            y, m = y - 1, 12
    raise RuntimeError("Não achei a versão mais nova do Dolphin em dl.dolphin-emu.org.")


def install(key):
    """Baixa (ou atualiza) o emulador e devolve (versão, caminho do .exe)."""
    e = EMULATORS[key]
    if e.get("repo"):
        rel = github.latest_release(e["repo"])
        asset = next((a for a in rel["assets"] if fnmatch.fnmatch(a["name"].lower(), e["asset"].lower())), None)
        if not asset:
            raise RuntimeError(f"Nenhum arquivo '{e['asset']}' na release de {e['repo']}.")
        url, name, tag = asset["browser_download_url"], asset["name"], rel.get("tag_name", "?")
        digest = asset.get("digest")
    else:
        url, tag = _dolphin_url()
        name, digest = url.rsplit("/", 1)[1], None
    with tempfile.TemporaryDirectory() as tmp:
        pkg = Path(tmp) / name
        with github._open(url, timeout=600) as r, open(pkg, "wb") as f:
            while True:
                b = r.read(1 << 20)
                if not b:
                    break
                f.write(b)
        github.check_digest(pkg, digest)
        github.extract_archive(pkg, folder(key))
    exe = find(key)
    if not exe:
        raise RuntimeError(f"{e['nome']} baixado, mas {e['exe']} não apareceu na pasta.")
    return tag, exe
