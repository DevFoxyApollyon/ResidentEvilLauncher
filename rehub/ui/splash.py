"""Tela de carregamento: símbolo da Umbrella, logo da série e o som de primeira inicialização do PS5.

Fica por cima da tela principal (que vai carregando por baixo) e some sozinha; qualquer tecla ou clique pula.
"""
import math
import random
import time
import tkinter as tk

from PIL import Image, ImageDraw, ImageFilter, ImageTk

from .. import audio
from ..franchise import FR, hex_rgb
from ..paths import COVERS, ROOT

DURATION = 5.5   # segundos até começar a sumir
FADE_OUT = 0.9
MESSAGES = tuple(FR["mensagens"])
RED = hex_rgb(FR["cor"])


def umbrella(size):
    """Octógono de fatias vermelhas e brancas (o mesmo desenho do ícone), desenhado grande e reduzido."""
    S = size * 2
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    c, r = S / 2, S * 0.46
    pts = [(c + r * math.cos(math.radians(22.5 + 45 * k)), c + r * math.sin(math.radians(22.5 + 45 * k))) for k in range(8)]
    d = ImageDraw.Draw(img)
    for k in range(8):
        d.polygon([(c, c), pts[k], pts[(k + 1) % 8]], fill=RED + (255,) if k % 2 == 0 else (245, 243, 240, 255))
    d.polygon(pts, outline=(40, 6, 10, 255), width=max(2, S // 60))
    return img.resize((size, size), Image.LANCZOS)


def halo(size):
    """Símbolo do Halo do Sol (Silent Hill): círculos concêntricos com marcas, desenhado em linhas."""
    S = size * 2
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    c, col, w = S / 2, RED + (255,), max(3, S // 70)
    for r in (0.46, 0.33, 0.12):
        d.ellipse((c - S * r, c - S * r, c + S * r, c + S * r), outline=col, width=w)
    for k in range(12):
        a = math.radians(30 * k)
        r1, r2 = S * 0.33, S * 0.46
        d.line((c + r1 * math.cos(a), c + r1 * math.sin(a), c + r2 * math.cos(a), c + r2 * math.sin(a)), fill=col, width=w)
    for k in range(4):
        a = math.radians(90 * k + 45)
        d.line((c + S * 0.12 * math.cos(a), c + S * 0.12 * math.sin(a), c + S * 0.33 * math.cos(a), c + S * 0.33 * math.sin(a)),
               fill=col, width=w)
    return img.resize((size, size), Image.LANCZOS)


def symbol(size):
    """O símbolo da franquia (franquia.json: "simbolo"): desenho pronto ou um .png ao lado do .exe."""
    kind = FR.get("simbolo", "umbrella")
    if kind == "halo":
        return halo(size)
    if kind.lower().endswith(".png") and (ROOT / kind).exists():
        img = Image.open(ROOT / kind).convert("RGBA")
        img.thumbnail((size, size), Image.LANCZOS)
        return img
    return umbrella(size)


def glow(size, color=RED):
    """Brilho vermelho redondo e desfocado, para pulsar atrás do símbolo."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    m = size * 0.22
    ImageDraw.Draw(img).ellipse((m, m, size - m, size - m), fill=color + (150,))
    return img.filter(ImageFilter.GaussianBlur(size * 0.12))


def ease(t):
    t = max(0.0, min(1.0, t))
    return 1 - (1 - t) ** 3


class Splash:
    def __init__(self, root, on_done, sound=True):
        self.root, self.on_done = root, on_done
        self.c = tk.Canvas(root, bg="#000000", highlightthickness=0, cursor="none")
        self.c.place(x=0, y=0, relwidth=1, relheight=1)
        self.c.tk.call("raise", self.c._w)  # o widget (Canvas.lift sobe itens, não o widget)
        self.t0 = time.time()
        self.closing_at = None
        self.sym = symbol(300)
        self.halo = glow(540)
        self.logo = self._series_logo()
        self.photo = None
        self.dust = [[random.random(), random.random(), random.uniform(0.6, 2.2), random.uniform(0.004, 0.018),
                      random.random() * math.tau] for _ in range(70)]
        self._sound = sound
        if sound:
            audio.effect("inicio", volume=0.9)
        for seq in ("<Key>", "<Button-1>"):
            root.bind_all(seq, self.skip, add="+")
        self._step()

    @staticmethod
    def _series_logo():
        p = COVERS / "_serie_logo.png"
        try:
            img = Image.open(p).convert("RGBA")
            img.thumbnail((460, 120), Image.LANCZOS)
            return img
        except OSError:
            return None

    def skip(self, _e=None):
        if self.closing_at is None:
            self.closing_at = time.time()

    def _center_image(self, t, fade):
        """Símbolo + brilho + logo numa imagem só, já com o brilho geral (fade) aplicado."""
        SA = 400  # altura da área do símbolo
        W, H = 640, SA + 130
        img = Image.new("RGBA", (W, H), (0, 0, 0, 255))
        pulse = 0.55 + 0.45 * math.sin(t * 2.4)
        a_sym = ease(t / 1.4)
        halo = self.halo.copy()
        halo.putalpha(halo.getchannel("A").point(lambda v: int(v * a_sym * (0.45 + 0.55 * pulse))))
        hy = (SA - halo.height) // 2
        img.alpha_composite(halo.crop((0, -hy, halo.width, halo.height)) if hy < 0 else halo, ((W - halo.width) // 2, max(0, hy)))
        scale = 0.86 + 0.14 * ease(t / 2.0)
        s = int(self.sym.width * scale)
        sym = self.sym.resize((s, s), Image.LANCZOS)
        sym.putalpha(sym.getchannel("A").point(lambda v: int(v * a_sym)))
        img.alpha_composite(sym, ((W - s) // 2, (SA - s) // 2))
        if self.logo:
            a = ease((t - 1.3) / 1.2)
            if a > 0:
                lg = self.logo.copy()
                lg.putalpha(lg.getchannel("A").point(lambda v: int(v * a)))
                img.alpha_composite(lg, ((W - lg.width) // 2, SA + 4 + int(14 * (1 - a))))
        if fade < 1:
            img = Image.blend(Image.new("RGBA", img.size, (0, 0, 0, 255)), img, max(0.0, fade))
        return img

    def _step(self):
        now = time.time()
        t = now - self.t0
        if self.closing_at is None and t >= DURATION:
            self.closing_at = now
        fade = ease(t / 0.8)
        if self.closing_at is not None:
            fade *= 1 - (now - self.closing_at) / FADE_OUT
            if fade <= 0:
                return self._finish()
        c = self.c
        W, H = max(c.winfo_width(), 2), max(c.winfo_height(), 2)
        c.delete("all")
        # poeira no ar
        for p in self.dust:
            p[1] -= p[3] / 30
            p[0] += math.sin(t * 0.7 + p[4]) * 0.0006
            if p[1] < -0.02:
                p[1], p[0] = 1.02, random.random()
            v = int(60 + 120 * (0.5 + 0.5 * math.sin(t * 1.6 + p[4])) * fade)
            x, y, r = p[0] * W, p[1] * H, p[2]
            c.create_oval(x - r, y - r, x + r, y + r, fill=f"#{v:02x}{v // 3:02x}{v // 3:02x}", outline="")
        img = self._center_image(t, fade)
        self.photo = ImageTk.PhotoImage(img)
        cy = H * 0.43
        c.create_image(W / 2, cy, image=self.photo)
        # barra de progresso e mensagens
        bw, by = min(420, W * 0.5), cy + img.height / 2 + 18
        prog = min(1.0, t / DURATION)
        g = int(55 * fade)
        c.create_rectangle(W / 2 - bw / 2, by, W / 2 + bw / 2, by + 3, fill=f"#{g:02x}{g:02x}{g:02x}", outline="")
        rr, gg, bb = (int(v * fade) for v in RED)
        c.create_rectangle(W / 2 - bw / 2, by, W / 2 - bw / 2 + bw * ease(prog), by + 3,
                           fill=f"#{rr:02x}{gg:02x}{bb:02x}", outline="")
        msg = MESSAGES[min(len(MESSAGES) - 1, int(prog * len(MESSAGES)))]
        tv = int(150 * fade)
        c.create_text(W / 2, by + 24, text=msg, fill=f"#{tv:02x}{tv:02x}{tv:02x}", font=("Segoe UI", 10))
        hv = int(85 * fade * (0.6 + 0.4 * math.sin(t * 3)))
        c.create_text(W / 2, H - 40, text="Pressione qualquer tecla para pular", fill=f"#{hv:02x}{hv:02x}{hv:02x}",
                      font=("Segoe UI", 9))
        self.root.after(33, self._step)

    def _finish(self):
        self.root.unbind_all("<Key>")
        self.root.unbind_all("<Button-1>")
        self.c.destroy()
        if self._sound:
            audio.stop_effect("inicio", 1.5)
        self.on_done()
