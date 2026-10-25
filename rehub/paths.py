"""Pastas usadas pelo RE Launcher."""
import sys
from pathlib import Path

# como .exe (PyInstaller), os dados ficam ao lado do executável; como script, ao lado do main.py
ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
GAMES_DIR = ROOT / "games"      # um .json por jogo (o catálogo)
DATA = ROOT / "data"            # tudo que o app gera


def _installed_data():
    """A pasta data/ do RE Launcher instalado (o instalador grava onde ficou no registro), ou None."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall\REHub") as k:
            d = Path(winreg.QueryValueEx(k, "InstallLocation")[0]) / "data"
        return d if d.is_dir() else None
    except OSError:
        return None


if not getattr(sys, "frozen", False):   # rodando pelo código: usa os mesmos dados do app instalado (ISOs, config...)
    if (ROOT.parent / "App" / "data").is_dir():
        DATA = ROOT.parent / "App" / "data"
    elif _installed_data():
        DATA = _installed_data()
CONFIG = DATA / "config.json"   # executáveis, ISOs e preferências escolhidos pelo usuário
COVERS = DATA / "covers"
RECOMPS = DATA / "recomps"      # recomps/decomps e ferramentas baixados
MODS = DATA / "mods"            # biblioteca de mods, uma pasta por jogo
