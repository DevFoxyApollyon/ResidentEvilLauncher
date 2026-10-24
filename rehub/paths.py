"""Pastas usadas pelo RE Hub."""
import sys
from pathlib import Path

# como .exe (PyInstaller), os dados ficam ao lado do executável; como script, ao lado do main.py
ROOT = Path(sys.executable).parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent
GAMES_DIR = ROOT / "games"      # um .json por jogo (o catálogo)
DATA = ROOT / "data"            # tudo que o app gera
if not getattr(sys, "frozen", False) and (ROOT.parent / "App" / "data").is_dir():
    DATA = ROOT.parent / "App" / "data"   # rodando pelo codigo ao lado do app instalado: usa os mesmos dados
CONFIG = DATA / "config.json"   # executáveis, ISOs e preferências escolhidos pelo usuário
COVERS = DATA / "covers"
RECOMPS = DATA / "recomps"      # recomps/decomps e ferramentas baixados
MODS = DATA / "mods"            # biblioteca de mods, uma pasta por jogo
