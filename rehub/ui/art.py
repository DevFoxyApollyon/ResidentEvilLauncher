"""Visual da tela principal: cores, medidas e as imagens montadas com o PIL (capas, sombras, fundo, cor de destaque).
Funções puras (sem Tk, exceto a Font), usadas pelo hub e pelas telas por cima."""
from tkinter import font as tkfont

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps

from ..franchise import FR, hex_rgb

BG_RGB = (11, 10, 9)
WHITE, MUTED, DIM = "#ece6da", "#a8a094", "#6b645b"
RED = FR["cor"]  # cor de destaque da franquia (franquia.json)
CHIP, CHIP_HI = "#29251f", "#3a332c"
GREEN = "#7ad18a"
TIER_COLORS = {"platina": "#a9c1e8", "ouro": "#e0b04a", "prata": "#c3c7cd", "bronze": "#c27a45"}
TIER_NAMES = {"platina": "Platina", "ouro": "Ouro", "prata": "Prata", "bronze": "Bronze"}
GAP, MARGIN, TILES_Y = 18, 56, 84
HOVER_SCALE, HOVER_LIFT = 1.08, 10  # card sob o mouse: cresce 8% e sobe 10 px


class Font(tkfont.Font):
    """Fonte que guarda as medidas de texto (medir no Tk é lento e o app mede os mesmos textos a cada quadro)."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._sizes = {}

    def measure(self, text, displayof=None):
        w = self._sizes.get(text)
        if w is None:
            if len(self._sizes) > 4000:
                self._sizes.clear()
            w = self._sizes[text] = super().measure(text)
        return w


DIM_LUT = [int(v * 0.62) for v in range(256)] * 3 + list(range(256))


def ease(t):
    return 1 - (1 - t) ** 3


# ---------- imagens ----------
def pil_font(size, file="segoeuib.ttf"):
    try:
        return ImageFont.truetype(file, size)
    except OSError:
        return ImageFont.load_default(size)


def fit_cover(img, size, anchor_y=0.5):
    """Redimensiona cobrindo todo o tamanho e corta o excesso."""
    W, H = size
    s = max(W / img.width, H / img.height)
    img = img.resize((max(W, round(img.width * s)), max(H, round(img.height * s))), Image.LANCZOS)
    x, y = (img.width - W) // 2, int((img.height - H) * anchor_y)
    return img.crop((x, y, x + W, y + H))


def rounded(img, radius):
    radius = min(radius, 2)   # cantos retos: capas como fotos impressas, nao como icones de app
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, img.width - 1, img.height - 1), radius, fill=255)
    out = Image.new("RGBA", img.size, (0, 0, 0, 0))
    out.paste(img.convert("RGB"), (0, 0), mask)
    return out


def wrap(draw, text, font, width):
    lines, line = [], ""
    for word in text.split():
        test = f"{line} {word}".strip()
        if draw.textlength(test, font=font) > width and line:
            lines.append(line)
            line = word
        else:
            line = test
    return lines + [line]


def make_poster(title, subtitle, size, stamp=None, title_font=None, bg=None):
    """Capa gerada para o que não tem arte em lugar nenhum (desenhada em 2x para ficar nítida).
    stamp: texto de carimbo (ex.: CANCELADO) para as versões perdidas.
    bg: arte aleatória da série para servir de banner (escurecida embaixo, para o título aparecer)."""
    W, H = size[0] * 2, size[1] * 2
    if bg is not None:
        img = ImageEnhance.Brightness(fit_cover(bg.convert("RGB"), (W, H))).enhance(0.75).convert("RGBA")
        shade = Image.linear_gradient("L").resize((W, H)).point(lambda v: int(max(0, v - 70) * 1.25))
        img.alpha_composite(Image.merge("RGBA", (*Image.new("RGB", (W, H), (8, 4, 6)).split(), shade)))
    else:
        img = ImageOps.colorize(Image.linear_gradient("L").resize((W, H)), black=(96, 8, 14), white=(10, 6, 8))
        grain = ImageOps.colorize(Image.effect_noise((W // 2, H // 2), 48).resize((W, H)).convert("L"),
                                  black=(0, 0, 0), white=(90, 30, 30))
        img = Image.blend(img, grain, 0.14).convert("RGBA")
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    cx, cy, r = W * 0.62, H * 0.36, W * 0.55  # círculos de "alvo" ao fundo
    for k in range(4 if bg is None else 0):
        rr = r * (1 - k * 0.22)
        d.ellipse((cx - rr, cy - rr, cx + rr, cy + rr), outline=(255, 255, 255, 16 + k * 6), width=3)
    img = Image.alpha_composite(img, over)
    d = ImageDraw.Draw(img)
    d.rectangle((22, 26, 70, 31), fill=(209, 18, 27))
    d.text((22, 40), FR["nome"].upper(), font=pil_font(W // 13, "seguibl.ttf"), fill=hex_rgb(RED))
    f = pil_font(W // (11 if title_font and "PressStart" in title_font else 7), title_font or "seguibl.ttf")
    lines = wrap(d, title, f, W - 44)
    sub = pil_font(W // 16, "segoeui.ttf")
    y = H - 30 - sub.size - 12 - len(lines) * (f.size + 6)
    for ln in lines:
        d.text((22, y), ln, font=f, fill=(244, 244, 246))
        y += f.size + 6
    d.text((22, H - 30 - sub.size), subtitle, font=sub, fill=(190, 180, 180))
    if stamp:
        sf = pil_font(W // 10, "seguibl.ttf")
        tw = int(d.textlength(stamp, font=sf))
        st = Image.new("RGBA", (tw + 40, sf.size + 34), (0, 0, 0, 0))
        sd = ImageDraw.Draw(st)
        sd.rounded_rectangle((3, 3, st.width - 4, st.height - 4), 8, outline=(225, 30, 38, 230), width=5)
        sd.text((20, 12), stamp, font=sf, fill=(225, 30, 38, 235))
        st = st.rotate(14, expand=True, resample=Image.BICUBIC)
        img = img.convert("RGBA")
        img.alpha_composite(st, ((W - st.width) // 2, int(H * 0.30)))
    return rounded(img.convert("RGB").resize(size, Image.LANCZOS), 10)


def make_tile(art, size):
    """Capa vertical. Se só existir arte horizontal, coloca sobre um fundo desfocado dela mesma."""
    W, H = size
    if art.height >= art.width:
        return rounded(fit_cover(art.convert("RGB"), size), 10)
    img = fit_cover(art.convert("RGB"), size).filter(ImageFilter.GaussianBlur(14))
    img = Image.blend(img, Image.new("RGB", size, BG_RGB), 0.45)
    fg = art.convert("RGB")
    fg.thumbnail((W - 10, H))
    img.paste(fg, ((W - fg.width) // 2, (H - fg.height) // 2))
    return rounded(img, 10)


def make_halo(size, color=(0, 0, 0), alpha=170, blur=12, dy=6):
    """Sombra (preta) ou brilho (colorido) atrás de um card. A imagem tem 'blur*2' de margem em volta."""
    W, H = size[0] + blur * 4, size[1] + blur * 4
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(img).rounded_rectangle((blur * 2, blur * 2 + dy, W - blur * 2, H - blur * 2 + dy), 2, fill=(*color, alpha))
    return img.filter(ImageFilter.GaussianBlur(blur))


def compose_background(hero, W, H, panel_box):
    """Arte grande escurecida (estilo PS5) e o painel da direita em vidro fosco."""
    if hero is not None:
        small = hero.width < 1000  # telas de título de PS1/PS2: desfoca para não ficar pixelado
        base = fit_cover(hero.convert("RGB"), (W, H), 0.5 if small else 0.25)
        if small:
            base = base.filter(ImageFilter.GaussianBlur(4))
    else:
        base = ImageOps.colorize(Image.linear_gradient("L").resize((W, H)), black=(48, 10, 14), white=BG_RGB)
    g = Image.linear_gradient("L")  # preto em cima, branco embaixo
    left = ImageOps.invert(g.rotate(90, expand=True)).resize((W, H)).point(lambda v: int(80 + v * 0.66))
    bottom = g.resize((W, H)).point(lambda v: int(max(0, v - 100) * 1.55))
    top = ImageOps.invert(g).resize((W, H)).point(lambda v: int(max(0, v - 175) * 2))
    mask = ImageChops.lighter(ImageChops.lighter(left, bottom), top)
    base = Image.composite(Image.new("RGB", (W, H), BG_RGB), base, mask)

    # vidro fosco: desfoca e escurece o que está atrás do painel
    x1, y1, x2, y2 = (int(v) for v in panel_box)
    # painel: uma folha escura sobre a arte (sem vidro fosco), borda fina e um filete na cor da franquia
    glass = base.crop((x1, y1, x2, y2)).filter(ImageFilter.GaussianBlur(6))
    glass = Image.blend(glass, Image.new("RGB", glass.size, (13, 11, 10)), 0.82)
    base.paste(glass, (x1, y1))
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    d.rectangle(panel_box, outline=(236, 230, 218, 30))
    d.rectangle((x1, y1, x2, y1 + 2), fill=(*hex_rgb(RED), 200))
    return Image.alpha_composite(base.convert("RGBA"), over).convert("RGB")  # RGB: transição mais leve


_accents = {}


def accent_from(img):
    """Cor de destaque tirada da arte (como a PS5 faz): o tom mais vivo, clareado. Guardada por imagem."""
    if id(img) in _accents:
        return _accents[id(img)]
    _accents[id(img)] = color = _accent(img)
    return color


def _accent(img):
    import colorsys
    best, score = None, 0
    for r, gg, b in img.resize((24, 24), Image.BILINEAR, reducing_gap=2.0).convert("RGB").getdata():
        h, s, v = colorsys.rgb_to_hsv(r / 255, gg / 255, b / 255)
        if v > 0.3 and s * v > score:
            best, score = (h, s), s * v
    if not best or score < 0.18:
        return RED
    r, gg, b = colorsys.hsv_to_rgb(best[0], min(0.8, max(0.5, best[1])), 0.95)
    return f"#{int(r * 255):02x}{int(gg * 255):02x}{int(b * 255):02x}"
