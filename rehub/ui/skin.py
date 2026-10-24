"""Visual desenhado do app: botões, ícones, menus e janelas feitos com o PIL (cantos suaves, gradiente, brilho),
no lugar dos widgets retos do Tk. Tudo é desenhado em 3x e reduzido (antialias) e fica em cache.

button_photo(): imagem de botão (com transparência) para Label do Tk ou para o canvas.
icon_photo(): ícone de linha (play, lixeira, lápis...).
Menu: menu flutuante (Opções e listas de escolha), desenhado num canvas só (abre na hora, sem dezenas de widgets).
"""
import math
import tkinter as tk

from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont, ImageTk

from ..franchise import FR, hex_rgb

SS = 3   # supersampling
KEY = "#010203"   # cor que vira transparente nas janelas com cantos arredondados
TEXT, MUTED, DIM = (236, 230, 218), (168, 160, 148), (107, 100, 91)
PANEL = (23, 21, 19)
_fonts, _photos, _pil = {}, {}, {}


def font(size, weight="SemiBold"):
    key = (size, weight)
    if key not in _fonts:
        try:
            f = ImageFont.truetype("bahnschrift.ttf", size)
            f.set_variation_by_name(weight)
        except (OSError, ValueError):
            f = ImageFont.truetype("segoeuib.ttf" if weight in ("SemiBold", "Bold") else "segoeui.ttf", size)
        _fonts[key] = f
    return _fonts[key]


def rgb(color):
    return hex_rgb(color) if isinstance(color, str) else tuple(color[:3])


def lighten(c, k):
    return tuple(min(255, int(v + (255 - v) * k)) for v in rgb(c))


def darken(c, k):
    return tuple(int(v * (1 - k)) for v in rgb(c))


def _text_width(text, f, track):
    return sum(f.getlength(ch) for ch in text) + track * max(0, len(text) - 1)


def _draw_text(d, xy, text, f, fill, track):
    x, y = xy
    for ch in text:
        d.text((x, y), ch, font=f, fill=fill)
        x += f.getlength(ch) + track


def _vgrad(size, top, bottom):
    """Gradiente vertical RGBA."""
    w, h = size
    col = Image.new("RGBA", (1, h))
    n = max(1, h - 1)
    col.putdata([tuple(int(a + (b - a) * y / n) for a, b in zip(top, bottom)) for y in range(h)])
    return col.resize((w, h))


def _rounded_mask(size, r):
    m = Image.new("L", size, 0)
    ImageDraw.Draw(m).rounded_rectangle((0, 0, size[0] - 1, size[1] - 1), r, fill=255)
    return m


# ---------- ícones (linhas, desenhados em 3x) ----------
def draw_icon(d, name, cx, cy, s, color, w):
    """Ícone de linha centrado em (cx, cy) com meio-tamanho s."""
    L = lambda *pts: d.line(pts, fill=color, width=w, joint="curve")
    if name == "play":
        d.polygon([(cx - s * 0.55, cy - s * 0.8), (cx - s * 0.55, cy + s * 0.8), (cx + s * 0.85, cy)], fill=color)
    elif name == "down":
        L((cx, cy - s), (cx, cy + s * 0.35))
        L((cx - s * 0.6, cy - s * 0.2), (cx, cy + s * 0.4), (cx + s * 0.6, cy - s * 0.2))
        L((cx - s * 0.8, cy + s * 0.9), (cx + s * 0.8, cy + s * 0.9))
    elif name == "link":
        d.rounded_rectangle((cx - s, cy - s * 0.55, cx + s * 0.45, cy + s), s * 0.2, outline=color, width=w)
        L((cx - s * 0.1, cy + s * 0.1), (cx + s, cy - s))
        L((cx + s * 0.25, cy - s), (cx + s, cy - s), (cx + s, cy - s * 0.25))
    elif name == "eye":
        d.ellipse((cx - s, cy - s * 0.55, cx + s, cy + s * 0.55), outline=color, width=w)
        d.ellipse((cx - s * 0.28, cy - s * 0.28, cx + s * 0.28, cy + s * 0.28), fill=color)
    elif name == "trash":
        L((cx - s, cy - s * 0.6), (cx + s, cy - s * 0.6))
        L((cx - s * 0.35, cy - s * 0.6), (cx - s * 0.3, cy - s), (cx + s * 0.3, cy - s), (cx + s * 0.35, cy - s * 0.6))
        d.line([(cx - s * 0.75, cy - s * 0.45), (cx - s * 0.6, cy + s), (cx + s * 0.6, cy + s), (cx + s * 0.75, cy - s * 0.45)],
               fill=color, width=w, joint="curve")
        for dx in (-0.25, 0.25):
            L((cx + s * dx, cy - s * 0.2), (cx + s * dx, cy + s * 0.65))
    elif name == "edit":
        L((cx - s * 0.85, cy + s * 0.85), (cx - s * 0.75, cy + s * 0.3), (cx + s * 0.5, cy - s * 0.95),
          (cx + s * 0.95, cy - s * 0.5), (cx - s * 0.3, cy + s * 0.75), (cx - s * 0.85, cy + s * 0.85))
        L((cx + s * 0.2, cy - s * 0.65), (cx + s * 0.65, cy - s * 0.2))
    elif name == "plus":
        L((cx - s * 0.8, cy), (cx + s * 0.8, cy))
        L((cx, cy - s * 0.8), (cx, cy + s * 0.8))
    elif name == "x":
        L((cx - s * 0.65, cy - s * 0.65), (cx + s * 0.65, cy + s * 0.65))
        L((cx - s * 0.65, cy + s * 0.65), (cx + s * 0.65, cy - s * 0.65))
    elif name == "check":
        L((cx - s * 0.8, cy), (cx - s * 0.2, cy + s * 0.6), (cx + s * 0.85, cy - s * 0.6))
    elif name == "gear":
        d.ellipse((cx - s * 0.38, cy - s * 0.38, cx + s * 0.38, cy + s * 0.38), outline=color, width=w)
        for k in range(8):
            a = k * math.pi / 4
            L((cx + math.cos(a) * s * 0.62, cy + math.sin(a) * s * 0.62), (cx + math.cos(a) * s, cy + math.sin(a) * s))
        d.ellipse((cx - s * 0.68, cy - s * 0.68, cx + s * 0.68, cy + s * 0.68), outline=color, width=w)
    elif name == "bag":
        d.rounded_rectangle((cx - s * 0.85, cy - s * 0.35, cx + s * 0.85, cy + s), s * 0.15, outline=color, width=w)
        d.arc((cx - s * 0.45, cy - s * 1.0, cx + s * 0.45, cy - s * 0.1), 180, 360, fill=color, width=w)
    elif name == "folder":
        d.line([(cx - s, cy + s * 0.8), (cx - s, cy - s * 0.75), (cx - s * 0.3, cy - s * 0.75), (cx - s * 0.1, cy - s * 0.45),
                (cx + s, cy - s * 0.45), (cx + s, cy + s * 0.8), (cx - s, cy + s * 0.8)], fill=color, width=w, joint="curve")
    elif name == "music":
        L((cx - s * 0.3, cy + s * 0.6), (cx - s * 0.3, cy - s * 0.9), (cx + s * 0.85, cy - s * 0.6), (cx + s * 0.85, cy + s * 0.4))
        d.ellipse((cx - s * 0.95, cy + s * 0.3, cx - s * 0.25, cy + s * 0.95), fill=color)
        d.ellipse((cx + s * 0.2, cy + s * 0.1, cx + s * 0.9, cy + s * 0.75), fill=color)
    elif name == "refresh":
        d.arc((cx - s * 0.85, cy - s * 0.85, cx + s * 0.85, cy + s * 0.85), 30, 320, fill=color, width=w)
        d.polygon([(cx + s * 0.95, cy - s * 0.95), (cx + s * 0.95, cy - s * 0.15), (cx + s * 0.2, cy - s * 0.55)], fill=color)
    elif name == "image":
        d.rounded_rectangle((cx - s, cy - s * 0.75, cx + s, cy + s * 0.75), s * 0.15, outline=color, width=w)
        L((cx - s * 0.8, cy + s * 0.55), (cx - s * 0.2, cy - s * 0.05), (cx + s * 0.15, cy + s * 0.3), (cx + s * 0.45, cy + s * 0.05),
          (cx + s * 0.8, cy + s * 0.5))
        d.ellipse((cx + s * 0.25, cy - s * 0.5, cx + s * 0.55, cy - s * 0.2), fill=color)
    elif name == "user":
        d.ellipse((cx - s * 0.4, cy - s * 0.95, cx + s * 0.4, cy - s * 0.15), outline=color, width=w)
        d.arc((cx - s * 0.85, cy + s * 0.05, cx + s * 0.85, cy + s * 1.7), 180, 360, fill=color, width=w)
    elif name == "users":
        for dx in (-0.4, 0.45):
            d.ellipse((cx + s * (dx - 0.3), cy - s * 0.9, cx + s * (dx + 0.3), cy - s * 0.3), outline=color, width=w)
            d.arc((cx + s * (dx - 0.6), cy - s * 0.1, cx + s * (dx + 0.6), cy + s * 1.3), 180, 360, fill=color, width=w)
    elif name == "timeline":
        L((cx - s, cy), (cx + s, cy))
        for dx in (-0.6, 0, 0.6):
            d.ellipse((cx + s * dx - s * 0.2, cy - s * 0.2, cx + s * dx + s * 0.2, cy + s * 0.2), fill=color)
    elif name == "tag":
        d.line([(cx - s, cy - s * 0.5), (cx + s * 0.2, cy - s * 0.5), (cx + s, cy + s * 0.1), (cx + s * 0.2, cy + s * 0.75),
                (cx - s, cy + s * 0.75), (cx - s, cy - s * 0.5)], fill=color, width=w, joint="curve")
        d.ellipse((cx - s * 0.65, cy - s * 0.15, cx - s * 0.35, cy + s * 0.15), fill=color)
    elif name == "grid":
        for dx in (-1, 0.15):
            for dy in (-1, 0.15):
                d.rounded_rectangle((cx + s * dx, cy + s * dy, cx + s * (dx + 0.85), cy + s * (dy + 0.85)), s * 0.12, outline=color, width=w)
    elif name == "trophy":
        d.line([(cx - s * 0.65, cy - s * 0.9), (cx + s * 0.65, cy - s * 0.9), (cx + s * 0.5, cy + s * 0.05), (cx, cy + s * 0.3),
                (cx - s * 0.5, cy + s * 0.05), (cx - s * 0.65, cy - s * 0.9)], fill=color, width=w, joint="curve")
        L((cx, cy + s * 0.3), (cx, cy + s * 0.75))
        L((cx - s * 0.5, cy + s * 0.9), (cx + s * 0.5, cy + s * 0.9))
    elif name == "live":
        d.ellipse((cx - s * 0.3, cy - s * 0.3, cx + s * 0.3, cy + s * 0.3), fill=color)
        d.arc((cx - s * 0.75, cy - s * 0.75, cx + s * 0.75, cy + s * 0.75), 135, 225, fill=color, width=w)
        d.arc((cx - s * 0.75, cy - s * 0.75, cx + s * 0.75, cy + s * 0.75), -45, 45, fill=color, width=w)
        d.arc((cx - s * 1.1, cy - s * 1.1, cx + s * 1.1, cy + s * 1.1), 140, 220, fill=color, width=w)
        d.arc((cx - s * 1.1, cy - s * 1.1, cx + s * 1.1, cy + s * 1.1), -40, 40, fill=color, width=w)
    elif name == "tv":
        d.rounded_rectangle((cx - s, cy - s * 0.65, cx + s, cy + s * 0.6), s * 0.15, outline=color, width=w)
        d.polygon([(cx - s * 0.25, cy - s * 0.3), (cx - s * 0.25, cy + s * 0.25), (cx + s * 0.35, cy - s * 0.02)], fill=color)
        L((cx - s * 0.45, cy + s * 0.95), (cx + s * 0.45, cy + s * 0.95))
    elif name == "screen":
        L((cx - s, cy - s * 0.35), (cx - s, cy - s), (cx - s * 0.35, cy - s))
        L((cx + s * 0.35, cy - s), (cx + s, cy - s), (cx + s, cy - s * 0.35))
        L((cx + s, cy + s * 0.35), (cx + s, cy + s), (cx + s * 0.35, cy + s))
        L((cx - s * 0.35, cy + s), (cx - s, cy + s), (cx - s, cy + s * 0.35))
    elif name == "doc":
        d.line([(cx - s * 0.7, cy - s), (cx + s * 0.3, cy - s), (cx + s * 0.75, cy - s * 0.55), (cx + s * 0.75, cy + s),
                (cx - s * 0.7, cy + s), (cx - s * 0.7, cy - s)], fill=color, width=w, joint="curve")
        for dy in (-0.25, 0.15, 0.55):
            L((cx - s * 0.4, cy + s * dy), (cx + s * 0.45, cy + s * dy))
    elif name == "power":
        d.arc((cx - s * 0.85, cy - s * 0.75, cx + s * 0.85, cy + s * 0.95), -60, 240, fill=color, width=w)
        L((cx, cy - s), (cx, cy - s * 0.05))
    elif name == "puzzle":
        d.rounded_rectangle((cx - s * 0.8, cy - s * 0.5, cx + s * 0.6, cy + s * 0.9), s * 0.15, outline=color, width=w)
        d.ellipse((cx - s * 0.35, cy - s * 1.0, cx + s * 0.15, cy - s * 0.45), outline=color, width=w)
        d.ellipse((cx + s * 0.45, cy - s * 0.05, cx + s * 1.0, cy + s * 0.45), outline=color, width=w)
    elif name == "chevron":
        L((cx - s * 0.6, cy - s * 0.3), (cx, cy + s * 0.35), (cx + s * 0.6, cy - s * 0.3))
    elif name == "alert":
        L((cx, cy - s * 0.6), (cx, cy + s * 0.2))
        d.ellipse((cx - s * 0.13, cy + s * 0.5, cx + s * 0.13, cy + s * 0.76), fill=color)
    elif name == "question":
        d.arc((cx - s * 0.5, cy - s * 0.85, cx + s * 0.5, cy + s * 0.1), 180, 90, fill=color, width=w)
        L((cx, cy + s * 0.1), (cx, cy + s * 0.3))
        d.ellipse((cx - s * 0.13, cy + s * 0.55, cx + s * 0.13, cy + s * 0.81), fill=color)
    else:   # ponto
        d.ellipse((cx - s * 0.25, cy - s * 0.25, cx + s * 0.25, cy + s * 0.25), fill=color)


def icon_image(name, size=16, color=TEXT, stroke=1.6):
    key = ("icon", name, size, rgb(color), stroke)
    if key not in _pil:
        big = size * SS
        img = Image.new("RGBA", (big, big), (0, 0, 0, 0))
        draw_icon(ImageDraw.Draw(img), name, big / 2, big / 2, big * 0.4, (*rgb(color), 255), max(2, int(stroke * SS)))
        _pil[key] = img.resize((size, size), Image.LANCZOS)
    return _pil[key]


def icon_photo(name, size=16, color=TEXT, stroke=1.6):
    key = ("iconp", name, size, rgb(color), stroke)
    if key not in _photos:
        _photos[key] = ImageTk.PhotoImage(icon_image(name, size, color, stroke))
    return _photos[key]


# ---------- botões ----------
def _style(style, accent, state):
    """(fundo topo, fundo base, borda, texto, brilho) em RGBA para o estilo e o estado."""
    a = rgb(accent)
    hot, down = state == "hover", state == "press"
    if style == "primary":
        top, bot = (lighten(a, 0.22 if hot else 0.1), darken(a, 0.12 if hot else 0.22))
        if down:
            top, bot = darken(a, 0.15), darken(a, 0.3)
        return (*top, 255), (*bot, 255), (*lighten(a, 0.35), 200), (255, 255, 255, 255), (*a, 150 if hot else 0)
    if style in ("danger", "alert"):
        red = (214, 58, 48)
        if style == "alert" or hot:
            top, bot = (lighten(red, 0.12 if hot else 0), darken(red, 0.25))
            if down:
                top, bot = darken(red, 0.2), darken(red, 0.4)
            return (*top, 255), (*bot, 255), (255, 140, 125, 200), (255, 255, 255, 255), (*red, 130 if hot else 0)
        return (58, 20, 18, 235), (40, 14, 13, 235), (170, 64, 54, 170), (255, 170, 158, 255), (0, 0, 0, 0)
    if style == "ghost":
        if hot or down:
            return (255, 255, 255, 18 if hot else 10), (255, 255, 255, 12), (255, 255, 255, 30), (*TEXT, 255), (0, 0, 0, 0)
        return (0, 0, 0, 0), (0, 0, 0, 0), (0, 0, 0, 0), (*MUTED, 255), (0, 0, 0, 0)
    # plain: vidro escuro
    if hot:
        return (52, 46, 41, 240), (34, 30, 27, 240), (*lighten(a, 0.25), 210), (255, 255, 255, 255), (*a, 70)
    if down:
        return (22, 20, 18, 240), (28, 25, 22, 240), (*a, 200), (*TEXT, 255), (0, 0, 0, 0)
    return (40, 36, 32, 225), (24, 21, 19, 225), (255, 255, 255, 38), (*TEXT, 230), (0, 0, 0, 0)


def button_image(text, style="plain", accent=None, icon=None, state="normal", height=38, size=11, radius=7,
                 pad=18, glow=6, min_width=0, track=1.2):
    """Botão com transparência em volta (margem 'glow' para o brilho do hover)."""
    accent = tuple(v // 12 * 12 for v in rgb(accent or FR["cor"]))   # cores quase iguais reaproveitam a imagem
    if state == "normal" and style in ("plain", "ghost", "danger", "alert"):
        accent = rgb(FR["cor"])   # parados, esses nao usam a cor do capitulo: uma imagem so para todos
    key = ("btn", text, style, rgb(accent), icon, state, height, size, radius, pad, glow, min_width)
    if key in _pil:
        return _pil[key]
    f = font(size * SS, "SemiBold")
    label = text.upper()
    tw = _text_width(label, f, track * SS) / SS
    iw = (size + 6) if icon else 0
    w = max(min_width, int(tw + iw + pad * 2))
    W, H = (w + glow * 2) * SS, (height + glow * 2) * SS
    top, bot, border, fg, shine = _style(style, accent, state)
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    box = (glow * SS, glow * SS, (glow + w) * SS, (glow + height) * SS)
    if shine[3] and glow:   # brilho em volta (hover)
        halo = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        ImageDraw.Draw(halo).rounded_rectangle(box, radius * SS, fill=shine)
        img = Image.alpha_composite(img, halo.filter(ImageFilter.GaussianBlur(glow * SS * 0.6)))
    bw, bh = box[2] - box[0], box[3] - box[1]
    fill = _vgrad((bw, bh), top, bot)
    mask = _rounded_mask((bw, bh), radius * SS)
    body = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    body.paste(fill, (0, 0), mask)
    d = ImageDraw.Draw(body)
    if border[3]:
        d.rounded_rectangle((0, 0, bw - 1, bh - 1), radius * SS, outline=border, width=max(1, SS))
    if style in ("primary", "alert") or (style == "danger" and state != "normal"):   # fio de luz no alto
        d.line((radius * SS, SS * 1.5, bw - radius * SS, SS * 1.5), fill=(255, 255, 255, 70), width=SS)
    img.alpha_composite(body, (box[0], box[1]))
    d = ImageDraw.Draw(img)
    x = box[0] + (bw - (tw + iw) * SS) / 2
    cy = box[1] + bh / 2
    if icon:
        s = size * SS * 0.5
        draw_icon(d, icon, x + s, cy, s, fg, max(2, int(1.7 * SS)))
        x += iw * SS
    asc, desc = f.getmetrics()
    _draw_text(d, (x, cy - (asc + desc) / 2 + desc * 0.15), label, f, fg, track * SS)
    out = img.resize((W // SS, H // SS), Image.LANCZOS)
    _pil[key] = out
    return out


def button_photo(*a, **kw):
    if kw.get("accent") is not None:
        kw["accent"] = tuple(v // 12 * 12 for v in rgb(kw["accent"]))
        if kw.get("state", "normal") == "normal" and kw.get("style", a[1] if len(a) > 1 else "plain") in ("plain", "ghost", "danger", "alert"):
            kw["accent"] = rgb(FR["cor"])
    key = ("btnp", a, tuple(sorted(kw.items())))
    if key not in _photos:
        if len(_photos) > 600:
            _photos.clear()
        _photos[key] = ImageTk.PhotoImage(button_image(*a, **kw))
    return _photos[key]


def badge_photo(icon, color, size=44):
    """Ícone num círculo com brilho (janelas de aviso)."""
    key = ("badge", icon, rgb(color), size)
    if key not in _photos:
        S = size * SS
        img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        c = rgb(color)
        d.ellipse((0, 0, S - 1, S - 1), fill=(*darken(c, 0.55), 255), outline=(*c, 255), width=SS * 2)
        draw_icon(d, icon, S / 2, S / 2, S * 0.24, (*lighten(c, 0.3), 255), int(2.2 * SS))
        _photos[key] = ImageTk.PhotoImage(img.resize((size, size), Image.LANCZOS))
    return _photos[key]


def panel_image(w, h, accent=None, radius=14, header=0):
    key = ("panel", w, h, rgb(accent or FR["cor"]), radius, header)
    if key not in _pil:
        _pil[key] = _panel_image(w, h, accent, radius, header)
    return _pil[key]


def _panel_image(w, h, accent=None, radius=14, header=0):
    """Fundo de menu/janela: cantos arredondados, gradiente sutil, borda fina e o fio na cor da franquia no topo.
    Desenhado sobre a cor KEY, que a janela torna transparente."""
    accent = rgb(accent or FR["cor"])
    S = SS
    img = Image.new("RGBA", (w * S, h * S), (*hex_rgb(KEY), 255))
    body = _vgrad((w * S, h * S), (32, 29, 26, 255), (*PANEL, 255))
    if header:   # o alto (cabeçalho) um pouco mais claro e o resto liso, para os widgets por cima casarem
        body = Image.new("RGBA", (w * S, h * S), (*PANEL, 255))
        body.paste(_vgrad((w * S, header * S), (34, 30, 27, 255), (*PANEL, 255)), (0, 0))
    img.paste(body, (0, 0), _rounded_mask((w * S, h * S), radius * S))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, w * S - 1, h * S - 1), radius * S, outline=(66, 59, 52, 255), width=S)
    alpha = Image.new("L", (w * S, 1))   # fio colorido que some para a direita
    alpha.putdata([int(255 * max(0.0, 1 - x / (w * S * 0.85))) for x in range(w * S)])
    line = Image.new("RGBA", (w * S, 2 * S), (*accent, 255))
    line.putalpha(alpha.resize((w * S, 2 * S)))
    edge = _rounded_mask((w * S, h * S), radius * S).crop((0, S, w * S, 3 * S))   # não passa dos cantos
    line.putalpha(ImageChops.multiply(line.getchannel("A"), edge))
    img.alpha_composite(line, (0, S))
    return img.resize((w, h), Image.LANCZOS)


def hilite_image(w, h, accent, radius=7):
    """Faixa do item sob o mouse nos menus: tinta da cor da franquia e uma barrinha à esquerda."""
    key = ("hl", w, h, rgb(accent), radius)
    if key not in _photos:
        a = rgb(accent)
        S = SS
        img = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        g = Image.new("RGBA", (w * S, h * S), (0, 0, 0, 0))
        ga = Image.new("L", (w * S, 1))   # mais forte à esquerda
        ga.putdata([int(30 + 40 * (1 - x / (w * S))) for x in range(w * S)])
        g = Image.new("RGBA", (w * S, h * S), (*a, 255))
        g.putalpha(ga.resize((w * S, h * S)))
        img.paste(g, (0, 0), _rounded_mask((w * S, h * S), radius * S))
        ImageDraw.Draw(img).rounded_rectangle((0, h * S * 0.22, 3 * S, h * S * 0.78), S, fill=(*a, 255))
        _photos[key] = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
    return _photos[key]


def keycap_photo(text, bg=PANEL):
    key = ("cap", text)
    if key not in _photos:
        f = font(9 * SS, "SemiBold")
        tw = _text_width(text, f, SS) / SS
        w, h = int(max(22, tw + 12)), 20
        img = Image.new("RGBA", (w * SS, h * SS), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        d.rounded_rectangle((0, 0, w * SS - 1, h * SS - 1), 5 * SS, fill=(38, 34, 30, 255), outline=(78, 70, 62, 255), width=SS)
        d.line((5 * SS, h * SS - 2 * SS, w * SS - 5 * SS, h * SS - 2 * SS), fill=(20, 18, 16, 255), width=SS)
        asc, desc = f.getmetrics()
        _draw_text(d, ((w * SS - tw * SS) / 2, (h * SS - asc - desc) / 2 - SS), text, f, (*MUTED, 255), SS)
        _photos[key] = ImageTk.PhotoImage(img.resize((w, h), Image.LANCZOS))
    return _photos[key]


def warm():
    """Desenha antes (em segundo plano) os ícones dos menus, para o primeiro clique em Opções abrir na hora."""
    for name in ("grid", "user", "timeline", "users", "tag", "image", "plus", "edit", "live", "tv", "trophy", "refresh",
                 "music", "folder", "puzzle", "screen", "doc", "power", "dot", "x", "chevron"):
        icon_image(name, 16, MUTED)


# ---------- menu flutuante ----------
class Menu:
    """Menu flutuante desenhado num canvas só. groups: [(titulo, [(texto, atalho, ação, ícone), ...]), ...].
    columns: quantas colunas. Abre com um leve deslize e esmaecer; setas/Enter/Esc funcionam."""
    ROW, COL_W, PAD = 34, 300, 14

    def __init__(self, master, groups, x, y, accent, title=None, columns=1, anchor="nw", on_close=None, width=None,
                 max_height=None, selected=None):
        self.master, self.accent, self.on_close = master, accent, on_close
        self.top = top = tk.Toplevel(master)
        top.overrideredirect(True)
        top.configure(bg=KEY)
        top.attributes("-topmost", True)
        try:
            top.attributes("-transparentcolor", KEY)
            top.attributes("-alpha", 0.0)
        except tk.TclError:
            pass
        col_w = width or self.COL_W
        # monta as colunas: grupos repartidos para alturas parecidas
        rows_per = [1 + len(items) for _, items in groups]
        cols, cur, target = [[] for _ in range(columns)], 0, sum(rows_per) / columns
        acc = 0
        for g, n in zip(groups, rows_per):
            if acc + n / 2 > target * (cur + 1) and cur < columns - 1:
                cur += 1
            cols[cur].append(g)
            acc += n
        head = 50 if title else 10
        self.items, y0 = [], head
        heights = []
        for ci, col in enumerate(cols):
            yy = y0
            for gi, (gtitle, items) in enumerate(col):
                if gtitle:
                    yy += 8 if gi else 4
                    self.items.append(("h", ci, yy, gtitle))
                    yy += 26
                for it in items:
                    self.items.append(("i", ci, yy, it))
                    yy += self.ROW
            heights.append(yy)
        W = self.PAD * 2 + col_w * columns + 8 * (columns - 1)
        H = max(heights) + 12
        view_h = min(H, max_height) if max_height else H
        self.W, self.H, self.view_h, self.col_w = W, H, view_h, col_w
        c = self.c = tk.Canvas(top, width=W, height=view_h, bg=KEY, highlightthickness=0)
        c.pack()
        self._bg = ImageTk.PhotoImage(panel_image(W, view_h, accent))
        c.create_image(0, 0, image=self._bg, anchor="nw", tags=("fixed",))
        if title:
            logo = _umbrella()
            tx = self.PAD + 6
            if logo:
                c.create_image(tx, 28, image=logo, anchor="w", tags=("fixed",))
                tx += 26
            c.create_text(tx, 28, anchor="w", text=title.upper(), fill="#ece6da", font=("Bahnschrift SemiBold", 11), tags=("fixed",))
            c.create_text(W - self.PAD - 6, 28, anchor="e", text="Esc fecha", fill="#6b645b", font=("Bahnschrift", 9), tags=("fixed",))
            c.create_line(self.PAD, 46, W - self.PAD, 46, fill="#2e2925", tags=("fixed",))
        self._hl = c.create_image(-999, 0, image=hilite_image(col_w - 8, self.ROW - 4, accent), anchor="nw")
        self.rows, self.labels = [], {}
        for kind, ci, yy, data in self.items:
            rx = self.PAD + ci * (col_w + 8)
            if kind == "h":
                tw = len(data) * 7 + 8
                c.create_oval(rx + 8, yy + 9, rx + 13, yy + 14, fill=accent, outline="", tags=("scroll",))
                c.create_text(rx + 20, yy + 11, anchor="w", text=data.upper(), fill=accent, font=("Bahnschrift SemiBold", 8),
                              tags=("scroll",))
                c.create_line(rx + 26 + tw, yy + 11, rx + col_w - 10, yy + 11, fill="#2e2925", tags=("scroll",))
                continue
            label, key, cmd, icon = (tuple(data) + (None,))[:4]
            k = len(self.rows)
            ic = c.create_image(rx + 22, yy + self.ROW / 2 - 2, image=icon_photo(icon or "dot", 16, MUTED), tags=("scroll",))
            tx = c.create_text(rx + 40, yy + self.ROW / 2 - 2, anchor="w", text=label, fill="#d9d2c5",
                               font=("Bahnschrift", 10), tags=("scroll",))
            if key:
                c.create_image(rx + col_w - 16, yy + self.ROW / 2 - 2, image=keycap_photo(key), anchor="e", tags=("scroll",))
            self.rows.append((rx + 4, yy, cmd, ic, tx, icon or "dot"))
        self.sel = None
        self.scroll = 0
        c.bind("<Motion>", self._motion)
        c.bind("<Leave>", lambda e: self._select(None))
        c.bind("<Button-1>", self._click)
        c.bind("<MouseWheel>", self._wheel)
        for k, fn in (("<Escape>", lambda e: self.close()), ("<Up>", lambda e: self._step(-1)), ("<Down>", lambda e: self._step(1)),
                      ("<Return>", lambda e: self._run(self.sel))):
            top.bind(k, fn)
        top.bind("<FocusOut>", lambda e: self.top.after(60, self._maybe_close))
        # posição (dentro da janela do app)
        mx, my = master.winfo_rootx(), master.winfo_rooty()
        mw, mh = master.winfo_width(), master.winfo_height()
        if anchor == "se":
            x, y = x - W, y - view_h
        x = max(mx + 8, min(x, mx + mw - W - 8))
        y = max(my + 8, min(y, my + mh - view_h - 8))
        self._x, self._y = x, y
        top.geometry(f"{W}x{view_h}+{x}+{y + 8}")
        top.focus_force()
        if selected is not None:
            self._select(selected, see=True)
        self._fade(0)

    def _fade(self, k):
        if not self.top.winfo_exists():
            return
        t = min(1.0, k / 7)
        e = 1 - (1 - t) ** 3
        try:
            self.top.attributes("-alpha", e)
        except tk.TclError:
            pass
        self.top.geometry(f"+{self._x}+{int(self._y + 8 * (1 - e))}")
        if t < 1:
            self.top.after(14, self._fade, k + 1)

    def _hit(self, x, y):
        y += self.scroll
        for k, (rx, ry, *_rest) in enumerate(self.rows):
            if rx <= x <= rx + self.col_w - 8 and ry <= y < ry + self.ROW:
                return k
        return None

    def _select(self, k, see=False):
        if k == self.sel:
            return
        c = self.c
        if self.sel is not None:
            _, _, _, ic, tx, icon = self.rows[self.sel]
            c.itemconfigure(tx, fill="#d9d2c5")
            c.itemconfigure(ic, image=icon_photo(icon, 16, MUTED))
        self.sel = k
        if k is None:
            c.coords(self._hl, -999, 0)
            return
        rx, ry, _, ic, tx, icon = self.rows[k]
        if see and self.view_h < self.H:
            self._scroll_to(max(0, min(self.H - self.view_h, ry - self.view_h / 2)))
        c.coords(self._hl, rx, ry + 1 - self.scroll)
        c.itemconfigure(tx, fill="#ffffff")
        c.itemconfigure(ic, image=icon_photo(icon, 16, self.accent))

    def _scroll_to(self, s):
        d = s - self.scroll
        self.scroll = s
        self.c.move("scroll", 0, -d)
        if self.sel is not None:
            self.c.coords(self._hl, self.rows[self.sel][0], self.rows[self.sel][1] + 1 - self.scroll)

    def _wheel(self, e):
        if self.view_h < self.H:
            self._scroll_to(max(0, min(self.H - self.view_h, self.scroll - e.delta / 120 * self.ROW * 2)))

    def _motion(self, e):
        self.c.config(cursor="hand2" if self._hit(e.x, e.y) is not None else "")
        self._select(self._hit(e.x, e.y))

    def _step(self, d):
        n = len(self.rows)
        self._select(((self.sel if self.sel is not None else -1) + d) % n, see=True)

    def _click(self, e):
        self._run(self._hit(e.x, e.y))

    def _run(self, k):
        if k is None:
            return
        cmd = self.rows[k][2]
        self.close()
        self.master.after(10, cmd)

    def _maybe_close(self):
        try:
            f = self.top.focus_get()
            if self.top.winfo_exists() and (f is None or f.winfo_toplevel() is not self.top):   # foco foi para outra janela
                self.close()
        except (tk.TclError, KeyError):
            self.close()

    def close(self):
        if self.top.winfo_exists():
            self.top.destroy()
            if self.on_close:
                self.on_close()


def _umbrella():
    from . import theme
    return theme.umbrella(18)
