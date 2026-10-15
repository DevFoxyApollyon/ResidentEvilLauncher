"""Gera re_hub.ico: octógono de fatias vermelhas e brancas, no estilo do símbolo da Umbrella."""
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

S = 1024  # desenha grande e reduz, para ficar liso em todos os tamanhos
OUT = Path(__file__).resolve().parent.parent / "re_hub.ico"


def octagon(cx, cy, r):
    return [(cx + r * math.cos(math.radians(22.5 + 45 * k)), cy + r * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]


img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
c, r = S / 2, S * 0.46

# sombra suave
shadow = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(shadow).polygon(octagon(c, c + S * 0.02, r), fill=(0, 0, 0, 140))
img.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(S * 0.02)))

# fatias alternadas: cada uma vai do centro até um lado do octógono
wedges = Image.new("RGBA", (S, S), (0, 0, 0, 0))
d = ImageDraw.Draw(wedges)
pts = octagon(c, c, r)
for k in range(8):
    color = (200, 16, 30, 255) if k % 2 == 0 else (245, 243, 240, 255)
    d.polygon([(c, c), pts[k], pts[(k + 1) % 8]], fill=color)
img.alpha_composite(wedges)

# contorno escuro fino e um leve brilho em cima
d = ImageDraw.Draw(img)
d.polygon(pts, outline=(40, 6, 10, 255), width=int(S * 0.018))
gloss = Image.new("RGBA", (S, S), (0, 0, 0, 0))
ImageDraw.Draw(gloss).ellipse((c - r * 0.9, c - r * 1.15, c + r * 0.9, c - r * 0.05), fill=(255, 255, 255, 38))
mask = Image.new("L", (S, S), 0)
ImageDraw.Draw(mask).polygon(pts, fill=255)
img.paste(Image.alpha_composite(img, gloss), (0, 0), mask)

img.save(OUT, sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
img.resize((256, 256), Image.LANCZOS).save(OUT.with_suffix(".png"))
print("ícone salvo em", OUT)
