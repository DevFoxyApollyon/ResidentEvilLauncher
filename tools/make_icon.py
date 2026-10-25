"""Gera re_hub.ico a partir de re_hub.png (o símbolo da Umbrella sem fundo), em todos os tamanhos do Windows."""
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
img = Image.open(ROOT / "re_hub.png").convert("RGBA")
img.save(ROOT / "re_hub.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("re_hub.ico gerado")
