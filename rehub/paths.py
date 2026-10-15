"""Pastas usadas pelo RE Hub."""
import sys
from pathlib import Path

# como .exe (PyInstaller), os dados ficam ao lado do executável; como script, ao lado do main.py
ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
GAMES_DIR = ROOT / "games"      # um .json por jogo (o catálogo)
DATA = ROOT / "data"            # tudo que o app gera
CONFIG = DATA / "config.json"   # executáveis, ISOs e preferências escolhidos pelo usuário
COVERS = DATA / "covers"
RECOMPS = DATA / "recomps"      # recomps/decomps e ferramentas baixados
MODS = DATA / "mods"            # biblioteca de mods, uma pasta por jogo
ICON = ROOT / "re_hub.ico"
