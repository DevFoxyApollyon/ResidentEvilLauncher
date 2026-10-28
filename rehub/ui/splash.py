"""Abertura do hub, por cima da tela principal (que vai montando por baixo):

- O vídeo de fundo (data/video/fundo.wmv) toca em loop pelo próprio Windows (MCI), liso, em tela cheia, com o som
  dele; aos 30 segundos o som do vídeo some e entra data/sons/abertura/antes_intro.mp3 em loop.
- Aos 15 segundos aparece o símbolo; aos 20 o logo vai se revelando da esquerda para a direita; quando ele termina,
  "PRESSIONE QUALQUER BOTÃO" pulsa.
- Qualquer tecla, clique ou botão do controle antes disso pula direto para o aviso (e começa o antes_intro);
  pulando, o símbolo e o nome aparecem na hora, devagar, e o aviso vem logo depois.
  Com o aviso na tela, toca intro.mp3, a tela escurece e o hub aparece.

O símbolo e o logo ficam numa janela transparente por pixel (UpdateLayeredWindow) por cima do vídeo nativo.
"""
import ctypes
import math
import os
import time
import tkinter as tk
from ctypes import wintypes

from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import audio
from ..franchise import FR, hex_rgb
from ..paths import COVERS, DATA, ROOT
from . import skin

VIDEO = DATA / "video" / "fundo.wmv"
SYMBOL_AT = 15.0   # segundos até o símbolo aparecer
LOGO_AT = 20.0     # o logo começa a se revelar
LOGO_TIME = 2.6
PROMPT_AT = LOGO_AT + LOGO_TIME   # a partir daqui dá para apertar
SKIP_LOGO = 1.4    # pulando a abertura: o logo começa a se revelar este tanto depois do símbolo
FADE = 2.5         # escurecer até o preto, depois clarear até o hub: 5 s ao todo depois de apertar
MUSIC_AT = 30.0    # o som do vídeo dá lugar ao antes_intro
VIDEO_VOL = 800    # volume do som do vídeo (0 a 1000)
FPS = 30
RED = hex_rgb(FR["cor"])
ALIAS = "rehub_abertura"

# camada com transparência por pixel por cima do vídeo
OW, OH = 900, 720          # tamanho da camada
SYM, GAP = 300, 70         # símbolo e espaço até o logo


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


def symbol(size):
    """O símbolo da franquia (franquia.json: "simbolo"): um .png ao lado do .exe ou o desenho pronto."""
    kind = FR.get("simbolo", "umbrella")
    if kind.lower().endswith(".png") and (ROOT / kind).exists():
        return Image.open(ROOT / kind).convert("RGBA").resize((size, size), Image.LANCZOS)
    return umbrella(size)


def series_logo(box=(600, 140)):
    """O logo da série com as cores dele (franquia.json: "logo_arquivo"), ou o baixado da Wikimedia."""
    for p in (ROOT / FR["logo_arquivo"] if FR.get("logo_arquivo") else None, COVERS / "_serie_logo.png"):
        if p and p.exists():
            try:
                img = Image.open(p).convert("RGBA")
                img = img.crop(img.getbbox() or (0, 0, *img.size))
                img.thumbnail(box, Image.LANCZOS)
                return img
            except OSError:
                pass
    return None


def glow(size, color=RED):
    """Brilho vermelho redondo e desfocado, atrás do símbolo."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    m = size * 0.22
    ImageDraw.Draw(img).ellipse((m, m, size - m, size - m), fill=color + (150,))
    return img.filter(ImageFilter.GaussianBlur(size * 0.12))


def ease(x):
    x = max(0.0, min(1.0, x))
    return 1 - (1 - x) ** 3


def faded(img, a):
    out = img.copy()
    out.putalpha(out.getchannel("A").point(lambda v: int(v * a)))
    return out


def wipe(img, p, soft=90):
    """Revela img da esquerda para a direita (p de 0 a 1), com a borda suave."""
    w, h = img.size
    x0 = int(p * (w + soft)) - soft
    mask = Image.new("L", (w, h), 0)
    if x0 > 0:
        mask.paste(255, (0, 0, min(w, x0), h))
    ramp = Image.linear_gradient("L").rotate(-90, expand=True).resize((soft, h))   # 255 à esquerda, 0 à direita
    mask.paste(ramp, (x0, 0))
    out = img.copy()
    out.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return out


# ---------- janela transparente por pixel ----------
user32, gdi32 = ctypes.windll.user32, ctypes.windll.gdi32
user32.GetDC.restype = wintypes.HDC
user32.GetDC.argtypes = [wintypes.HWND]
user32.ReleaseDC.argtypes = [wintypes.HWND, wintypes.HDC]
gdi32.CreateCompatibleDC.restype = wintypes.HDC
gdi32.CreateCompatibleDC.argtypes = [wintypes.HDC]
gdi32.CreateDIBSection.restype = wintypes.HBITMAP
gdi32.CreateDIBSection.argtypes = [wintypes.HDC, ctypes.c_void_p, wintypes.UINT, ctypes.POINTER(ctypes.c_void_p),
                                   wintypes.HANDLE, wintypes.DWORD]
gdi32.SelectObject.restype = wintypes.HGDIOBJ
gdi32.SelectObject.argtypes = [wintypes.HDC, wintypes.HGDIOBJ]
gdi32.DeleteObject.argtypes = [wintypes.HGDIOBJ]
gdi32.DeleteDC.argtypes = [wintypes.HDC]
user32.GetWindowLongPtrW.restype = ctypes.c_ssize_t
user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_ssize_t]


class _Blend(ctypes.Structure):
    _fields_ = [("op", ctypes.c_byte), ("flags", ctypes.c_byte), ("alpha", ctypes.c_ubyte), ("fmt", ctypes.c_byte)]


class _BIH(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("w", wintypes.LONG), ("h", wintypes.LONG), ("planes", wintypes.WORD),
                ("bits", wintypes.WORD), ("comp", wintypes.DWORD), ("rest", wintypes.DWORD * 5)]


user32.UpdateLayeredWindow.argtypes = [wintypes.HWND, wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       ctypes.POINTER(wintypes.SIZE), wintypes.HDC, ctypes.POINTER(wintypes.POINT),
                                       wintypes.COLORREF, ctypes.POINTER(_Blend), wintypes.DWORD]


def own(win, root):
    """Prende a janela ao launcher (dona = a janela principal): fica por cima só dele, não dos outros programas,
    e some junto quando ele é minimizado. (Com "sempre por cima", a abertura aparecia em cima de tudo.)"""
    root.update_idletasks()
    hwnd = int(win.wm_frame(), 16)
    owner = int(root.wm_frame(), 16)
    user32.SetWindowLongPtrW(hwnd, -8, owner)   # GWLP_HWNDPARENT: a dona da janela


class Layer:
    """Toplevel sem borda cujo conteúdo é uma imagem RGBA (transparência por pixel), sempre por cima."""

    def __init__(self, root, x, y, w, h):
        self.x, self.y, self.w, self.h = x, y, w, h
        self.top = tk.Toplevel(root)
        self.top.overrideredirect(True)
        self.top.geometry(f"{w}x{h}+{x}+{y}")
        self.top.update_idletasks()
        self.hwnd = int(self.top.wm_frame(), 16)
        own(self.top, root)
        ex = user32.GetWindowLongPtrW(self.hwnd, -20)
        user32.SetWindowLongPtrW(self.hwnd, -20, ex | 0x80000 | 0x80)   # WS_EX_LAYERED | WS_EX_TOOLWINDOW
        self.alpha = 255

    def show(self, img):
        """Põe a imagem (RGBA, do tamanho da camada) na janela."""
        r, g, b, a = img.split()
        data = Image.merge("RGBA", (ImageChops.multiply(b, a), ImageChops.multiply(g, a),
                                    ImageChops.multiply(r, a), a)).tobytes()   # BGRA pré-multiplicado
        screen = user32.GetDC(None)
        mdc = gdi32.CreateCompatibleDC(screen)
        bih = _BIH(ctypes.sizeof(_BIH), self.w, -self.h, 1, 32, 0)
        bits = ctypes.c_void_p()
        bmp = gdi32.CreateDIBSection(mdc, ctypes.byref(bih), 0, ctypes.byref(bits), None, 0)
        ctypes.memmove(bits, data, len(data))
        old = gdi32.SelectObject(mdc, bmp)
        user32.UpdateLayeredWindow(self.hwnd, screen, ctypes.byref(wintypes.POINT(self.x, self.y)),
                                   ctypes.byref(wintypes.SIZE(self.w, self.h)), mdc, ctypes.byref(wintypes.POINT(0, 0)),
                                   0, ctypes.byref(_Blend(0, 0, self.alpha, 1)), 2)
        gdi32.SelectObject(mdc, old)
        gdi32.DeleteObject(bmp)
        gdi32.DeleteDC(mdc)
        user32.ReleaseDC(None, screen)

    def set_alpha(self, a):
        """Transparência da camada inteira (0 a 1), sem redesenhar."""
        self.alpha = max(0, min(255, int(a * 255)))
        user32.UpdateLayeredWindow(self.hwnd, None, None, None, None, None, 0, ctypes.byref(_Blend(0, 0, self.alpha, 1)), 2)

    def destroy(self):
        self.top.destroy()


def _mci(cmd):
    return ctypes.windll.winmm.mciSendStringW(cmd, None, 0, 0)


class Splash:
    def __init__(self, root, on_done, sound=True):
        self.root, self.on_done, self._sound = root, on_done, sound
        W, H = self.W, self.H = root.winfo_screenwidth(), root.winfo_screenheight()
        self.t0 = time.time()
        self.pressed_at = None
        # vídeo nativo num quadro que cobre a tela principal
        self.frame = tk.Frame(root, bg="#000000", cursor="none")
        self.frame.place(x=0, y=0, relwidth=1, relheight=1)
        self.frame.tk.call("raise", self.frame._w)
        root.update_idletasks()
        self.video = VIDEO.exists() and _mci(f'open "{VIDEO}" type mpegvideo alias {ALIAS} '
                                             f'parent {self.frame.winfo_id()} style child') == 0
        if self.video:
            _mci(f"put {ALIAS} window at 0 0 {W} {H}")
            _mci(f"setaudio {ALIAS} volume to {VIDEO_VOL if sound else 0}")
            _mci(f"play {ALIAS} repeat")
        self.video_vol = VIDEO_VOL if sound and self.video else 0
        self.music_on = False
        self.sym_at, self.logo_at, self.prompt_at = SYMBOL_AT, LOGO_AT, PROMPT_AT   # mudam ao pular a abertura
        # símbolo, logo e aviso por cima
        self.sym, self.halo, self.logo = symbol(SYM), glow(560), series_logo()
        self.font = skin.font(22, "Bold")
        self.layer = Layer(root, (W - OW) // 2, int(H * 0.42) - SYM // 2 - 130, OW, OH)
        self.layer.show(Image.new("RGBA", (OW, OH), (0, 0, 0, 0)))   # vazia até o símbolo
        self.curtain = None
        root.splash = self
        for w in (self.frame, self.layer.top):
            w.bind("<Key>", self.press)
            w.bind("<Button>", self.press)
        self.layer.top.focus_force()
        self._step()

    # ---------- entrada ----------
    def press(self, _e=None):
        """Qualquer tecla, clique ou botão do controle. Antes do aviso: pula direto para ele (símbolo e logo prontos)
        e começa a música antes_intro. Com o aviso na tela: toca a intro e abre o hub."""
        now = time.time()
        if now - getattr(self, "_last_press", 0) < 0.6:   # o mesmo clique chega pelo Tk e pela leitura do Windows
            return "break"
        self._last_press = now
        tt = now - self.t0
        if self.pressed_at is None and tt < self.prompt_at:
            # pula a espera: o símbolo e o nome começam a aparecer agora (devagar, não de uma vez)
            self.sym_at = min(self.sym_at, tt)
            self.logo_at = min(self.logo_at, max(tt, self.sym_at) + SKIP_LOGO)
            self.prompt_at = self.logo_at + LOGO_TIME
            if self._sound and not self.music_on:
                self.music_on = True
                audio.play_file("antes_intro", audio.opening("antes_intro"), 0.8, loop=True)
            return "break"
        if self.pressed_at is None:
            self.pressed_at = time.time()   # a tela escurece e o hub aparece
            if self._sound:
                audio.stop_effect("antes_intro", 0.5)
                audio.play_file("intro", audio.opening("intro"), 0.9)
        return "break"   # a tela principal por baixo não recebe a tecla

    # ---------- quadro a quadro ----------
    def _compose(self, tt):
        img = Image.new("RGBA", (OW, OH), (0, 0, 0, 0))
        cx, sy = OW // 2, 130 + SYM // 2   # centro do símbolo na camada
        a = ease((tt - self.sym_at) / 1.6)
        if a > 0:
            pulse = 0.55 + 0.45 * math.sin(tt * 2.2)
            h = faded(self.halo, a * (0.3 + 0.4 * pulse))
            img.alpha_composite(h, (cx - h.width // 2, sy - h.height // 2))
            s = int(SYM * (0.88 + 0.12 * a))
            sym = faded(self.sym.resize((s, s), Image.LANCZOS), a)
            img.alpha_composite(sym, (cx - s // 2, sy - s // 2))
        ly = sy + SYM // 2 + GAP
        if self.logo and tt >= self.logo_at:
            lg = wipe(self.logo, ease((tt - self.logo_at) / LOGO_TIME))
            img.alpha_composite(lg, (cx - lg.width // 2, ly))
        if self.logo:
            ly += self.logo.height
        if tt >= self.prompt_at:   # pulsa entre apagado e branco
            k = 0.5 + 0.5 * math.sin((tt - self.prompt_at) * 3.2 - math.pi / 2)
            v = int(80 + 175 * k * ease((tt - self.prompt_at) / 0.6))
            d = ImageDraw.Draw(img)
            text = "P R E S S I O N E   Q U A L Q U E R   B O T Ã O"
            tw = d.textlength(text, font=self.font)
            d.text((cx - tw / 2, ly + 70), text, font=self.font, fill=(v, v, v, 255))
        return img

    def _video_volume(self, target, step=40):
        """Leva o som do vídeo aos poucos até target (um passo por quadro)."""
        if self.video and self.video_vol != target:
            self.video_vol = max(target, self.video_vol - step) if self.video_vol > target else min(target, self.video_vol + step)
            _mci(f"setaudio {ALIAS} volume to {self.video_vol}")

    def _mouse_click(self):
        """Clique em qualquer botão do mouse, lido direto do Windows: o vídeo é uma janela nativa por cima do Tk e
        engolia os cliques. Só conta com o launcher na frente; vale uma vez por aperto."""
        u = ctypes.windll.user32
        down = any(u.GetAsyncKeyState(vk) & 0x8000 for vk in (0x01, 0x02, 0x04, 0x05, 0x06))   # esq, dir, meio, X1, X2
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(u.GetForegroundWindow(), ctypes.byref(pid))
        mine = pid.value == os.getpid()
        clicked = down and mine and not getattr(self, "_was_down", True)
        self._was_down = down
        return clicked

    def _step(self):
        now = time.time()
        tt = now - self.t0
        if self.pressed_at is None and self._mouse_click():
            self.press()
        if self._sound and not self.music_on and tt >= MUSIC_AT and self.pressed_at is None:
            self.music_on = True
            audio.play_file("antes_intro", audio.opening("antes_intro"), 0.8, loop=True)
        if self.music_on or self.pressed_at is not None:
            self._video_volume(0)
        if self.pressed_at is None:
            if self.root.focus_get() is not None and self.root.focus_get() is not self.layer.top:
                self.layer.top.focus_force()   # o hub pede foco ao abrir; as teclas são da abertura até ela sumir
            if tt >= self.sym_at - 0.1:
                self.layer.show(self._compose(tt))
        else:
            if self.curtain is None:   # apertou com o aviso na tela: escurece até o preto e o menu aparece
                self.curtain = tk.Toplevel(self.root, bg="#000000")
                self.curtain.overrideredirect(True)
                self.curtain.geometry(f"{self.W}x{self.H}+0+0")
                self.curtain.attributes("-alpha", 0.0)
                own(self.curtain, self.root)
            k = (now - self.pressed_at) / FADE
            if k < 1:   # escurece até o preto
                self.layer.set_alpha(1 - k)
                self.curtain.attributes("-alpha", ease(k))
            else:
                if self.video:
                    _mci(f"close {ALIAS}")
                    self.video = False
                if self.frame.winfo_exists():
                    self.layer.destroy()
                    self.frame.destroy()
                    self.root.focus_force()
                a = 1 - ease(k - 1)   # clareia até o hub
                if a <= 0:
                    return self._finish()
                self.curtain.attributes("-alpha", a)
        self.root.after(1000 // FPS, self._step)

    def _finish(self):
        self.curtain.destroy()
        self.root.splash = None
        if self._sound:
            audio.stop_effect("antes_intro", 0.3)
        self.on_done()
