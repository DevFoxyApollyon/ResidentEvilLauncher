"""Tela principal no estilo PS5: capítulos em ordem da história, arte grande, troféus e DLCs."""
import ctypes
import hashlib
import os
import random
import re
import shutil
import threading
import time
import tkinter as tk
import urllib.parse
import urllib.request
import webbrowser
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

from PIL import Image, ImageChops, ImageDraw, ImageEnhance, ImageFilter, ImageFont, ImageOps, ImageTk

from .. import audio, catalog, fluffy, fonts, github, news, trailer, launcher, steam, store, trophies
from ..mods import ModManager
from ..franchise import FR, hex_rgb
from ..paths import COVERS, DATA, ROOT
from . import theme as t
from .splash import Splash
from .manage import ManageWindow

BG_RGB = (11, 14, 20)
WHITE, MUTED, DIM = "#f2f4f8", "#a7adb8", "#5d6573"
RED = FR["cor"]  # cor de destaque da franquia (franquia.json)
CHIP, CHIP_HI = "#262c38", "#343c4b"
GREEN = "#7ad18a"
TIER_COLORS = {"platina": "#a9c1e8", "ouro": "#e0b04a", "prata": "#c3c7cd", "bronze": "#c27a45"}
TIER_NAMES = {"platina": "Platina", "ouro": "Ouro", "prata": "Prata", "bronze": "Bronze"}
GAP, MARGIN, TILES_Y = 18, 56, 84
HOVER_SCALE, HOVER_LIFT = 1.08, 10  # card sob o mouse: cresce 8% e sobe 10 px
SECTIONS = (("canon", "Linha do tempo"), ("spinoff", "Não canônicos"), ("perdidos", "Perdidos"), ("midia", "Filmes"),
            ("hqs", "HQs e livros"), ("fas", "Feito por fãs"), ("noticias", "Notícias"))
REMOTE = DATA / "imagens"
CARDS = DATA / "cache" / "cards"  # cards já montados (arte recortada ou capa gerada), por tamanho de tela  # ícones de troféus e miniaturas de DLC baixados


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
    ImageDraw.Draw(img).rounded_rectangle((blur * 2, blur * 2 + dy, W - blur * 2, H - blur * 2 + dy), 14, fill=(*color, alpha))
    return img.filter(ImageFilter.GaussianBlur(blur))


def hex_rgb(color):
    return tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))


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
    glass = base.crop((x1, y1, x2, y2)).filter(ImageFilter.GaussianBlur(22))
    glass = Image.blend(glass, Image.new("RGB", glass.size, (14, 17, 24)), 0.55)
    gmask = Image.new("L", glass.size, 0)
    ImageDraw.Draw(gmask).rounded_rectangle((0, 0, glass.width - 1, glass.height - 1), 18, fill=255)
    base.paste(glass, (x1, y1), gmask)
    over = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    ImageDraw.Draw(over).rounded_rectangle(panel_box, 18, outline=(255, 255, 255, 34))
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


class Hub(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(FR["app"])
        self.geometry("1280x800")
        self.minsize(1100, 740)
        self.configure(bg=t.BG)
        icon = ROOT / f"{FR['icone']}.ico"
        if icon.exists():
            self.iconbitmap(default=str(icon))

        self.cfg = catalog.Config()
        self.prefs = {"tela_cheia": True, "trilha": True, "efeitos": True, **self.cfg.get("_prefs")}
        if os.environ.get("REHUB_TESTE"):  # testes automáticos: janela normal e sem som
            self.prefs.update(tela_cheia=False, trilha=False, efeitos=False)
        self.attributes("-fullscreen", not os.environ.get("REHUB_TESTE"))  # sempre abre em tela cheia
        audio.ensure_effects()
        self.music = audio.Music()
        self.music.set_enabled(self.prefs["trilha"])
        self._music_job = None
        self.installed = steam.installed_apps()
        self.steamid, self.persona = trophies.steam_user()
        self.section, self.order, self.only_installed = "canon", "historia", False
        self.sel = 0
        self.version_idx = {}
        self.status_text = ""
        self.panel_tab, self.panel_scroll = "trofeus", 0
        self.games = catalog.load_games()
        self._build_chapters()
        self.trophy_state = {g["appid"]: trophies.cached(g["appid"]) for g in self.games if g["tipo"] == "steam"}
        self.dlc_state = {}

        self._pil, self._tiles, self._remote, self._remote_pending = {}, {}, {}, set()
        self._tile_base, self._halos, self._halo_base = {}, {}, {}
        self._clicks, self._bound = {}, set()  # ações dos botões (ligadas ao Tk uma vez só)
        self._bg_key, self._bg_photo, self._bg_pil, self._render_job = None, None, None, None
        self._bg_pending, self._fade, self._preloaded = None, None, False  # troca de fundo com transição suave
        self._panel_box = (0, 0, 0, 0)
        self._logos, self.accent, self._brand_img = {}, RED, None
        # animações: carrossel deslizando, card selecionado crescendo, card sob o mouse
        self._slide, self._grow, self._anim_job = 0.0, 1.0, None
        self._hover, self._hover_amt, self._tile_rects = None, {}, []
        self._row_rects, self._row_hover = [], None
        self.tile_s, self.tile_n, self.details_y = (190, 285), (126, 189), 450
        self.mod_busy = ""
        self._tfonts = {}
        self.f = {name: Font(family=fam, size=size, weight=w) for name, fam, size, w in (
            ("title", "Segoe UI Semibold", 30, "normal"), ("h", "Segoe UI Semibold", 13, "normal"),
            ("body", "Segoe UI", 11, "normal"), ("small", "Segoe UI", 9, "normal"),
            ("btn", "Segoe UI Semibold", 11, "normal"), ("big", "Segoe UI Light", 34, "normal"),
            ("logo", "Segoe UI", 15, "bold"), ("tiny", "Segoe UI Semibold", 9, "normal"),
            ("nav", "Segoe UI Semibold", 11, "normal"), ("clock", "Segoe UI Light", 16, "normal"))}

        self.c = tk.Canvas(self, bg=t.BG, highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        self.c.bind("<Configure>", lambda e: self.refresh())
        self.c.bind("<Motion>", self._motion)
        self.c.bind("<Button-1>", self._canvas_click)
        self.c.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<MouseWheel>", self._wheel)
        for key, fn in (("<Left>", lambda e: self.step(-1)), ("<Right>", lambda e: self.step(1)),
                        ("<Up>", lambda e: self.pick_version(-1)), ("<Down>", lambda e: self.pick_version(1)),
                        ("<Return>", lambda e: self.primary_action()), ("<g>", lambda e: self.manage()),
                        ("<Tab>", lambda e: self.next_section()), ("<F11>", lambda e: self.toggle_fullscreen()),
                        ("<Escape>", lambda e: (self._sound("back"), self.toggle_fullscreen(False))), ("<F5>", lambda e: self.rescan())):
            self.bind(key, fn)

        threading.Thread(target=self._fetch_art, daemon=True).start()
        threading.Thread(target=self._fetch_news, daemon=True).start()
        threading.Thread(target=self._fetch_trophies, daemon=True).start()
        self._tick()
        self._away = self._seen_front = False
        if not os.environ.get("REHUB_TESTE"):
            self.after(300, lambda: (self.lift(), self.focus_force()))
            self.bind("<Map>", lambda e: e.widget is self and self._away and self._come_back())  # voltou pela barra de tarefas
            self.after(1500, self._watch_focus)
        if os.environ.get("REHUB_TESTE"):
            self._queue_music()
        else:  # tela de carregamento por cima enquanto a principal monta por baixo; a trilha começa depois
            Splash(self, on_done=self._queue_music, sound=self.prefs["efeitos"])

    # ---------- dados ----------
    def _build_chapters(self):
        chapters = catalog.load_timeline(self.games, self.section)
        if self.only_installed and self.section in ("canon", "spinoff"):
            chapters = [ch for ch in chapters if any(launcher.is_ready(g, self.cfg, self.installed) for g in ch["versoes"])]
        if self.order == "lancamento":
            chapters.sort(key=lambda ch: ch.get("lancamento", 9999))
        self.chapters = chapters
        self.sel = max(0, min(self.sel, len(chapters) - 1))

    def rescan(self):
        self.games = catalog.load_games()
        self.installed = steam.installed_apps()
        self._build_chapters()
        self.refresh()

    @property
    def chapter(self):
        return self.chapters[self.sel] if self.chapters else None

    def version_of(self, ch):
        if ch["id"] not in self.version_idx:  # começa pela versão pronta para jogar, senão pela da Steam
            vs = ch["versoes"]
            ready = [i for i, g in enumerate(vs) if launcher.is_ready(g, self.cfg, self.installed)]
            steam_ = [i for i, g in enumerate(vs) if g["tipo"] == "steam"]
            self.version_idx[ch["id"]] = (ready or steam_ or [0])[0]
        return ch["versoes"][self.version_idx[ch["id"]]]

    @property
    def game(self):
        return self.version_of(self.chapter) if self.chapter else None

    def _image(self, key, kind):
        if key is None:
            return None
        if (key, kind) not in self._pil:
            p = store.art_path(key, kind)
            if not p:
                return None
            try:
                self._pil[(key, kind)] = Image.open(p).copy()
            except OSError:
                return None
        return self._pil[(key, kind)]

    def _art(self, g, kind):
        """Arte da versão; se ela não tiver fundo, usa o da versão Steam do mesmo capítulo."""
        img = self._image(store.art_key(g), kind)
        if img is None and kind == "fundo":
            ch = self.chapter
            steam_g = next((v for v in ch["versoes"] if v["tipo"] == "steam"), None) if ch else None
            img = self._image(store.art_key(steam_g), kind) if steam_g else None
            if img is None:  # sem fundo nenhum (filmes, HQs): a própria capa, desfocada, vira o fundo
                img = self._image(store.art_key(g), "capa")
            if img is None:  # nem capa: a mesma arte aleatória do banner
                img = self._random_art(g)
        return img

    def _random_art(self, g):
        """Arte aleatória da série (um dos fundos baixados) para o que não tem banner nenhum.
        Sorteada pelo id, então cada item mantém a mesma arte toda vez que o app abre."""
        if not hasattr(self, "_pool"):
            self._pool = sorted(p for p in COVERS.glob("*_fundo.jpg") if p.name.split("_")[0].isdigit())  # artes da Steam
        if not self._pool:
            return None
        p = random.Random(g["id"]).choice(self._pool)
        key = ("_aleatoria", p.name)
        if key not in self._pil:
            try:
                self._pil[key] = Image.open(p).copy()
            except OSError:
                return None
        return self._pil[key]

    def _fetch_news(self):
        """Notícias do REVIL em segundo plano; busca de novo a cada 30 minutos enquanto o app estiver aberto."""
        while True:
            try:
                if news.refresh():
                    for c in catalog.load_timeline(self.games, "noticias"):
                        g = c["versoes"][0]
                        if g.get("arte") and not store.art_path(store.art_key(g), "capa"):
                            store.download_art(g, "capa")
                    self.after(0, self._news_arrived)
            except Exception:  # sem internet: fica com as que já tinha
                pass
            time.sleep(news.MAX_AGE)

    def _news_arrived(self):
        if self.section == "noticias":
            cid = self.chapter["id"] if self.chapter else None
            self._build_chapters()
            self.sel = next((i for i, ch in enumerate(self.chapters) if ch["id"] == cid), 0)
            self.refresh()

    def _fetch_art(self):
        if store.download_series_logo():
            self.after(0, lambda: (setattr(self, "_brand_img", None), self.refresh()))
        try:
            info = store.items([g["appid"] for g in self.games if g["tipo"] == "steam"])
        except (OSError, ValueError):
            info = {}
        extras = [v for sec in ("spinoff", "perdidos", "midia", "hqs", "fas", "noticias") for ch in catalog.load_timeline(self.games, sec)
                  for v in ch["versoes"] if v.get("arte")]  # pôsteres de filmes e HQs
        for g in self.games + extras:
            key = store.art_key(g)
            for kind in ("capa", "fundo", "logo"):
                if key and not store.art_path(key, kind) and store.download_art(g, kind, info.get(g.get("appid"))):
                    self.after(0, self.refresh)

    def _fetch_trophies(self, only=None, force=False):
        if not self.steamid:
            return
        apps = [only] if only else [g["appid"] for g in self.games if g["tipo"] == "steam"]
        for appid in apps:
            old = trophies.cached(appid)
            fresh = not force and old and trophies.is_fresh(old)
            try:
                state = trophies.load(appid, self.steamid, force=force)
            except Exception as e:  # sem internet, perfil privado etc.: mostra no painel
                state = {"erro": str(e)}
            new = bool(old and "erro" not in state and state.get("conquistados", 0) > old.get("conquistados", 0))
            self.after(0, lambda a=appid, s=state, n=new: (self.trophy_state.__setitem__(a, s),
                                                           n and self._sound("trophy"), self.refresh()))
            if not fresh and len(apps) > 1:
                time.sleep(1.5)  # a Steam bloqueia (429) se pedirmos tudo de uma vez

    def _fetch_dlcs(self, appid):
        self.dlc_state[appid] = None

        def work():
            try:
                state = store.dlcs(appid)
            except Exception as e:
                state = {"erro": f"Não consegui buscar as DLCs: {e}"}
            self.after(0, lambda: (self.dlc_state.__setitem__(appid, state), self.refresh()))
        threading.Thread(target=work, daemon=True).start()

    def _remote_img(self, url, size, radius=6):
        """Imagem pequena da internet (ícone de troféu, miniatura de DLC), com cache em disco."""
        if not url:
            return None
        key = (url, size)
        if key in self._remote:
            return self._remote[key]
        path = REMOTE / (hashlib.sha1(url.encode()).hexdigest() + ".jpg")
        if path.exists():
            try:
                self._remote[key] = ImageTk.PhotoImage(rounded(fit_cover(Image.open(path).convert("RGB"), size), radius))
                return self._remote[key]
            except OSError:
                return None
        if url not in self._remote_pending:
            self._remote_pending.add(url)

            def fetch():
                try:
                    REMOTE.mkdir(parents=True, exist_ok=True)
                    req = urllib.request.Request(url, headers={"User-Agent": "RE-Hub"})
                    with urllib.request.urlopen(req, timeout=15) as r:
                        path.write_bytes(r.read())
                    self.after(0, self.refresh)
                except OSError:
                    pass
            threading.Thread(target=fetch, daemon=True).start()
        return None

    # ---------- navegação ----------
    def select(self, i):
        if not self.chapters:
            return
        new = max(0, min(len(self.chapters) - 1, i))
        if new != self.sel:
            self._slide += (new - self.sel) * (self.tile_n[0] + GAP)  # as capas deslizam até o lugar novo
            self.sel, self.panel_scroll, self._grow = new, 0, 0.0      # e o card novo cresce
            self._sound("select")
            self._queue_music()
            self._kick()
        self.refresh()

    def step(self, delta):
        """Setas: anda um capítulo; passando do último (ou do primeiro), vai para a aba seguinte (ou anterior)."""
        i, now = self.sel + delta, time.time()
        held = now - getattr(self, "_last_step", 0) < 0.3  # seta segurada: para no fim; outro toque troca de aba
        self._last_step = now
        if self.chapters and 0 <= i < len(self.chapters):
            return self.select(i)
        if held:
            return
        keys = [k for k, _ in SECTIONS]
        self.set_section(keys[(keys.index(self.section) + (1 if delta > 0 else -1)) % len(keys)])
        if delta < 0 and self.chapters:  # voltando: cai no fim da aba anterior
            self.sel = len(self.chapters) - 1
            self._queue_music()
            self.refresh()

    def _kick(self):
        """Liga o laço de animação (se já não estiver rodando)."""
        if not self._anim_job:
            self._anim_job = self.after(16, self._animate)

    def _animate(self):
        self._anim_job = None
        active = False
        self._slide *= 0.62
        if abs(self._slide) < 0.8:
            self._slide = 0.0
        else:
            active = True
        if self._grow < 1:
            self._grow = min(1.0, self._grow + 0.14)
            active = True
        for i in set(self._hover_amt) | ({self._hover} - {None}):
            target = 1.0 if i == self._hover else 0.0
            cur = self._hover_amt.get(i, 0.0)
            nxt = cur + (target - cur) * 0.45
            if abs(nxt - target) < 0.02:
                nxt = target
            else:
                active = True
            if nxt == 0:
                self._hover_amt.pop(i, None)
            else:
                self._hover_amt[i] = nxt
        moving = active  # só as capas mudaram: redesenha só o carrossel (o resto da tela fica parado)
        if self._fade:
            self._fade_step()
            active = True
        if self._render_job:  # já vem um redesenho completo logo em seguida
            pass
        elif moving:
            self._redraw_carousel()
        if active:
            self._kick()

    # ---------- mouse sobre os cards ----------
    def _motion(self, e):
        hit = next((i for i, x1, y1, x2, y2 in self._tile_rects if x1 <= e.x <= x2 and y1 <= e.y <= y2), None)
        self._set_hover(hit)
        row = next((r for r in self._row_rects if r[0] <= e.x <= r[2] and r[1] <= e.y <= r[3]), None)
        if row != self._row_hover:  # linha das listas do painel sob o mouse: barrinha de destaque
            self._row_hover = row
            self.c.delete("rowhover")
            if row:
                x1, y1, x2, y2 = row
                self.c.create_rectangle(x1, y1 + 4, x1 + 3, y2 - 4, fill=self.accent, outline="", tags=("rowhover",))
                self.c.create_line(x1 + 10, y2, x2, y2, fill="#323a4a", tags=("rowhover",))

    def _set_hover(self, i):
        if i == self._hover:
            return
        self._hover = i
        if i is not None:
            self._sound("hover", 0.04)
        self.c.config(cursor="hand2" if i is not None else "")
        if not self._anim_job:  # começa a animação já, sem esperar o próximo quadro
            self._animate()

    def click_tile(self, i):
        if i == self.sel:  # clique no card que já está aberto: um "pulso" de destaque
            self._grow = 0.55
            self._sound("enter")
            self._kick()
        else:
            self.select(i)

    def _sound(self, name, gap=0.05):
        if self.prefs["efeitos"]:
            audio.effect(name, gap)

    # ---------- música, tela cheia e preferências ----------
    def _queue_music(self):
        """Troca a trilha meio segundo depois de parar num capítulo (não troca a cada capa que passa)."""
        if self._music_job:
            self.after_cancel(self._music_job)
        ch, g = self.chapter, self.game
        self._music_job = self.after(500, lambda: self.music.play_chapter(ch, g) if ch else self.music.stop())

    def _save_prefs(self, **values):
        self.prefs.update(values)
        self.cfg.set("_prefs", **self.prefs)

    def toggle_music(self):
        self._save_prefs(trilha=not self.prefs["trilha"])
        self.music.set_enabled(self.prefs["trilha"])
        self._queue_music()
        self.refresh()

    def toggle_effects(self):
        self._save_prefs(efeitos=not self.prefs["efeitos"])
        self._sound("tab")
        self.refresh()

    def toggle_fullscreen(self, on=None):
        """F11/Esc: só para esta vez. Ao abrir de novo (ou voltar de outra janela), é sempre tela cheia."""
        on = (not self.attributes("-fullscreen")) if on is None else on
        self.attributes("-fullscreen", on)

    # ---------- saiu para outra janela (jogo, navegador, Steam): minimiza e tira o som ----------
    def _watch_focus(self):
        """A cada meio segundo vê se a janela da frente é de outro programa."""
        try:
            fg = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
            ours = pid.value == os.getpid() or not fg
            self._seen_front = self._seen_front or ours
            if not ours and not self._away and self._seen_front:
                self._go_away()
            elif ours and self._away and self.state() != "iconic":
                self._come_back()
        except Exception:
            pass
        self.after(500, self._watch_focus)

    def _go_away(self):
        self._away = True
        self._trailer_stop()
        self.music.set_enabled(False)
        audio.stop_effect("inicio", 0.3)
        self.attributes("-fullscreen", False)  # o Windows não minimiza janela em tela cheia
        self.iconify()

    def _come_back(self):
        self._away = False
        self.installed = steam.installed_apps()  # pode ter instalado/desinstalado algo na Steam enquanto estava fora
        self.attributes("-fullscreen", True)
        self.music.set_enabled(self.prefs["trilha"])
        self._queue_music()
        self.refresh()

    def pick_music(self):
        ch = self.chapter
        if not ch:
            return
        path = filedialog.askopenfilename(parent=self, title=f"Música para {ch['titulo']} (mp3, wav, wma, m4a)",
                                          filetypes=[("Áudio", "*.mp3 *.wav *.wma *.m4a")])
        if not path:
            return
        dest = audio.MUSIC / ch["id"]
        shutil.rmtree(dest, ignore_errors=True)
        dest.mkdir(parents=True)
        shutil.copy2(path, dest)
        self.music.stop()
        self._queue_music()

    def pick_version(self, delta, absolute=None):
        ch = self.chapter
        if not ch or len(ch["versoes"]) < 2:
            return
        cur = self.version_idx.get(ch["id"], 0)
        self.version_idx[ch["id"]] = absolute if absolute is not None else (cur + delta) % len(ch["versoes"])
        self.panel_scroll, self._grow = 0, 0.6
        self._sound("tab")
        self._queue_music()  # versões podem ter trilha própria (ex.: RE4 de 2005 e o Remake)
        self._kick()
        self.refresh()

    def set_section(self, section):
        if section == self.section:
            return
        self.section, self.sel, self.panel_scroll, self._grow = section, 0, 0, 0.0
        self._hover, self._hover_amt = None, {}
        self._build_chapters()
        self._sound("tab")
        self._queue_music()
        self._kick()
        self.refresh()

    def next_section(self):
        keys = [k for k, _ in SECTIONS]
        self.set_section(keys[(keys.index(self.section) + 1) % len(keys)])

    def toggle_order(self):
        self.order = "lancamento" if self.order == "historia" else "historia"
        cid = self.chapter["id"] if self.chapter else None
        self._build_chapters()
        self.sel = next((i for i, ch in enumerate(self.chapters) if ch["id"] == cid), 0)
        self.refresh()

    def toggle_installed(self):
        self.only_installed = not self.only_installed
        self.sel = 0
        self._build_chapters()
        self.refresh()

    def set_tab(self, tab):
        if tab != self.panel_tab:
            self._sound("tab")
        self.panel_tab, self.panel_scroll = tab, 0
        self.refresh()

    def _wheel(self, e):
        x1, y1, x2, y2 = self._panel_box
        if x1 <= e.x_root - self.c.winfo_rootx() <= x2 and y1 <= e.y_root - self.c.winfo_rooty() <= y2:
            self.panel_scroll = max(0, self.panel_scroll + (1 if e.delta < 0 else -1))
            self.refresh()
        else:
            self.select(self.sel + (1 if e.delta < 0 else -1))

    def _tick(self):
        self.refresh()
        self.after(20000, self._tick)  # relógio

    def refresh(self):
        """Agenda um redesenho (vários pedidos seguidos viram um só)."""
        if self._render_job:
            self.after_cancel(self._render_job)
        self._render_job = self.after(16, self.render)

    # ---------- desenho ----------
    def render(self):
        self._render_job = None
        c, W, H = self.c, self.c.winfo_width(), self.c.winfo_height()
        if W < 50 or H < 50:
            return
        c.delete("all")
        self._row_rects, self._row_hover = [], None
        # cards proporcionais à altura da tela (tela cheia em 1080p: card aberto de ~330 px)
        # o card aberto tem ~3x o tamanho dos outros (como a PS5 destaca o jogo escolhido)
        sel_h = int(min(max(H * 0.37, 260), 420))
        self.tile_s = (int(sel_h * 2 / 3), sel_h)
        self.tile_n = (int(self.tile_s[0] * 0.36), int(sel_h * 0.36))
        self.details_y = TILES_Y + sel_h + 74
        panel = (max(int(W * 0.57), W - 520), self.details_y - 6, W - MARGIN, H - 64)
        self._panel_box = panel

        g = self.game
        hero = self._art(g, "fundo") if g else None
        key = (id(hero) if hero is not None else None, W, H, panel)
        if self._bg_photo is None or self._bg_key[1:] != key[1:]:  # primeira vez ou mudou o tamanho: na hora
            self._bg_pil = compose_background(hero, W, H, panel)
            self._bg_photo, self._bg_key, self._fade = ImageTk.PhotoImage(self._bg_pil), key, None
            self.accent = accent_from(hero) if hero is not None else RED
            if not self._preloaded:
                self._preloaded = True
                threading.Thread(target=self._preload, daemon=True).start()
        elif key != self._bg_key and key != self._bg_pending and not (self._fade and self._fade["key"] == key):
            self._start_bg_change(hero, key)
        c.create_image(0, 0, image=self._bg_photo, anchor="nw")

        self._draw_header(W)
        self._draw_bottom_bar(W, H)
        if not self.chapters:
            c.create_text(MARGIN, TILES_Y + 40, anchor="nw", fill=MUTED, font=self.f["h"],
                          text="Nenhum jogo instalado nesta seção. Desligue o filtro 'Só instalados' na barra de baixo."
                          if self.only_installed else "Nada nesta seção ainda. Os itens vêm de games/_linha_do_tempo.json.")
            return
        self._redraw_carousel()
        self._draw_details()
        self._draw_panel(*panel)

    def _redraw_carousel(self):
        """Apaga e redesenha só as capas e a linha do tempo (camada 'car')."""
        c = self.c
        c.delete("car")
        if not self.chapters:
            return
        mark = c.create_line(0, 0, 0, 0, fill="")  # tudo criado depois deste item é do carrossel
        self._draw_carousel(c.winfo_width())
        for item in c.find_all():
            if item >= mark:
                c.addtag_withtag("car", item)

    def _preload(self):
        """Em segundo plano: abre do disco as artes e monta as capas grandes, para a troca de capítulo não travar."""
        sections = [catalog.load_timeline(self.games, s) for s, _ in SECTIONS]
        for chapters in sections:
            for ch in chapters:
                for g in ch["versoes"]:
                    key = store.art_key(g)
                    for kind in ("fundo", "capa"):
                        self._image(key, kind)
                    art = self._image(key, "capa")
                    if art is None and not g.get("poster"):
                        other = next((v for v in ch["versoes"] if self._image(store.art_key(v), "capa") is not None), None)
                        art = self._image(store.art_key(other), "capa") if other else None
                    try:  # capas geradas (filmes, fãs, HQs sem arte) também: abrir essas abas fica instantâneo
                        self._ensure_tile_base(ch, g, art)
                    except Exception:
                        pass

    # ---------- fundo com transição ----------
    def _start_bg_change(self, hero, key):
        """Monta o fundo novo numa thread (é pesado) e depois faz a transição suave."""
        self._bg_pending = key
        W, H, panel = key[1], key[2], key[3]

        def work():
            img = compose_background(hero, W, H, panel)
            accent = accent_from(hero) if hero is not None else RED

            def apply():
                if self._bg_pending != key:  # o usuário já passou para outro capítulo
                    return
                self._bg_pending = None
                self._fade = {"from": self._bg_pil, "to": img, "t": 0.0, "key": key, "accent": accent}
                self._kick()
            self.after(0, apply)
        threading.Thread(target=work, daemon=True).start()

    def _fade_step(self):
        """Um quadro da transição. Escreve na MESMA imagem que já está na tela (bem mais rápido que criar outra)."""
        f = self._fade
        f["t"] = min(1.0, f["t"] + 0.5)
        if f["t"] >= 1 or f["from"] is None or f["from"].size != f["to"].size:
            self._bg_pil, self._bg_key, self._fade = f["to"], f["key"], None
            self._bg_photo.paste(self._bg_pil)
            if f["accent"] != self.accent:  # a cor de destaque mudou: redesenha o resto uma vez
                self.accent = f["accent"]
                self.refresh()
        else:
            self._bg_photo.paste(Image.blend(f["from"], f["to"], ease(f["t"])))

    def _brand(self):
        """Símbolo + logo da série para o topo (montado uma vez)."""
        if self._brand_img is None:
            parts = []
            icon = ROOT / f"{FR['icone']}.png"
            if icon.exists():
                parts.append(Image.open(icon).convert("RGBA").resize((40, 40), Image.LANCZOS))
            logo = COVERS / "_serie_logo.png"
            if logo.exists():
                img = Image.open(logo).convert("RGBA")
                img = img.crop(img.getbbox() or (0, 0, *img.size))
                h = 30 if img.width / img.height < 6 else 24  # logos bem largos (ex.: SILENT HILL) ficam mais baixos
                img = img.resize((min(220, int(img.width * h / img.height)), h), Image.LANCZOS)
                red = Image.new("RGBA", img.size, (*FR["logo_cor"], 255))  # cor do app, menos berrante
                red.putalpha(img.getchannel("A"))
                parts.append(red)
            if not parts:
                return None
            W = sum(p.width for p in parts) + 14 * (len(parts) - 1)
            out = Image.new("RGBA", (W, 40), (0, 0, 0, 0))
            x = 0
            for p in parts:
                out.alpha_composite(p, (x, (40 - p.height) // 2))
                x += p.width + 14
            self._brand_img = ImageTk.PhotoImage(out)
        return self._brand_img

    def _draw_header(self, W):
        c = self.c
        brand = self._brand()
        if brand:
            c.create_image(MARGIN, 38, image=brand, anchor="w")
            x = MARGIN + brand.width() + 34
        else:
            c.create_text(MARGIN, 38, anchor="w", text=FR["nome"].upper(), fill=RED, font=self.f["logo"])
            x = MARGIN + self.f["logo"].measure(FR["nome"].upper()) + 30
        for key, label in SECTIONS:
            on = self.section == key
            tag = f"nav_{key}"
            w = self.f["nav"].measure(label)
            c.create_text(x, 38, anchor="w", text=label, fill=WHITE if on else MUTED, font=self.f["nav"], tags=(tag,))
            if on:
                c.create_rectangle(x, 54, x + w, 57, fill=self.accent, outline="")
            self._clickable(tag, lambda k=key: self.set_section(k))
            x += w + 28
        self._nav_end = x

        right = W - MARGIN
        if self.attributes("-fullscreen"):  # sem barra de título: botão para fechar
            tag = "quit"
            c.create_text(right, 38, anchor="e", text="✕", fill=MUTED, font=self.f["h"], tags=(tag,))
            self._clickable(tag, self.destroy)
            right -= 34
        c.create_text(right, 38, anchor="e", text=time.strftime("%H:%M"), fill=WHITE, font=self.f["clock"])
        right -= self.f["clock"].measure("00:00") + 28
        loaded = [s for s in self.trophy_state.values() if s and "erro" not in s]
        plats, got = sum(s["platina"] for s in loaded), sum(s["conquistados"] for s in loaded)
        text = f"{plats}   ·   {got} troféus"
        tw = self.f["h"].measure(text) + 40
        if self.trophy_state and right - tw > self._nav_end + 20:  # sem jogos da Steam ou sem espaço: não mostra
            c.create_text(right, 38, anchor="e", text=text, fill=WHITE, font=self.f["h"])
            x = right - self.f["h"].measure(text) - 12
            self._cup(x - 8, 38, 9, TIER_COLORS["platina"])
            if self.persona and x - 40 - self.f["body"].measure(self.persona) > self._nav_end + 20:
                c.create_text(x - 28, 38, anchor="e", text=self.persona, fill=MUTED, font=self.f["body"])

    def _draw_bottom_bar(self, W, H):
        c, y = self.c, H - 32
        c.create_text(MARGIN, y, anchor="w", fill=DIM, font=self.f["small"],
                      text="← →  capítulos    ↑ ↓  versões    Enter  jogar    G  gerenciar    Tab  seção    F11  tela cheia")
        x = W - MARGIN
        for label, cmd, on in (("⚙  Opções", self._options_menu, False),
                               ("Efeitos", self.toggle_effects, self.prefs["efeitos"]),
                               ("♪  Trilha", self.toggle_music, self.prefs["trilha"]),
                               ("Só instalados", self.toggle_installed, self.only_installed),
                               ("Ordem: " + ("História" if self.order == "historia" else "Lançamento"), self.toggle_order, False)):
            w = self.f["small"].measure(label) + 28
            tag = "opt_" + label.split()[0].strip("⚙").lower() + str(len(label))
            shape = self._round_rect(x - w, y - 14, x, y + 14, 14, fill=WHITE if on else CHIP, outline="", tags=(tag,))
            c.create_text(x - w / 2, y, text=label, fill=t.BG if on else WHITE, font=self.f["small"], tags=(tag,))
            self._clickable(tag, cmd, shape=None if on else shape)
            x -= w + 8

    def _draw_carousel(self, W):
        c = self.c
        n, s = self.tile_n, self.tile_s
        g = ease(self._grow)  # o card aberto cresce do tamanho normal até o grande
        sel_size = (int(n[0] + (s[0] - n[0]) * g), int(n[1] + (s[1] - n[1]) * g))
        step = n[0] + GAP
        first_x = MARGIN + (step if self.sel > 0 else 0) + self._slide  # mostra um capítulo anterior, como na PS5
        line_y = TILES_Y + s[1] + 30
        centers, self._tile_rects = [], []
        for i, ch in enumerate(self.chapters):
            if i < self.sel:
                x = first_x - (self.sel - i) * step
            elif i == self.sel:
                x = first_x
            else:
                x = first_x + sel_size[0] + GAP + (i - self.sel - 1) * step
            size = sel_size if i == self.sel else n
            if x + size[0] < -40 or x > W + 40:
                continue
            # card sob o mouse: cresce e sobe um pouco, com a sombra ficando maior
            h = ease(self._hover_amt.get(i, 0.0))
            scale = 1 + (HOVER_SCALE - 1) * h
            w2, h2 = int(size[0] * scale), int(size[1] * scale)
            dx, dy = x - (w2 - size[0]) / 2, TILES_Y - (h2 - size[1]) / 2 - HOVER_LIFT * h
            if i == self.sel:  # destaque: brilho forte na cor do jogo (no lugar da borda branca)
                c.create_image(dx - 24, dy - 24, image=self._halo((w2, h2), hex_rgb(self.accent), int(225 * g), 0), anchor="nw")
            c.create_image(dx - 24, dy - 24 + 4 * h, image=self._halo((w2, h2), (0, 0, 0), 150 + int(60 * h), 6), anchor="nw")
            dim = i != self.sel and h < 0.5  # os outros cards ficam um pouco apagados
            c.create_image(dx, dy, image=self._tile(ch, (w2, h2), dim), anchor="nw", tags=(f"tile{i}",))
            self._tile_rects.append((i, x, TILES_Y - HOVER_LIFT, x + size[0], TILES_Y + size[1]))
            centers.append((x + size[0] / 2, i, ch))

        if centers:  # a linha do tempo embaixo das capas
            c.create_line(max(0, centers[0][0]), line_y, min(W, centers[-1][0]), line_y, fill=DIM, width=2)
            by_release = self.order == "lancamento" or self.section != "canon"  # fora da história oficial: ano de lançamento
            for cx, i, ch in centers:
                sel = i == self.sel
                r = 6 if sel else 4
                c.create_oval(cx - r, line_y - r, cx + r, line_y + r, fill=self.accent if sel else MUTED, outline="")
                if self.section in ("fas", "noticias"):  # fãs: o tipo; notícias: a data  # projetos de fãs: o tipo (Patch, Remaster, Fan film...)
                    label = ch.get("categoria", "")
                else:
                    label = str(ch.get("lancamento", "")) if by_release else self._story_year(ch)
                c.create_text(cx, line_y + 18, text=label, fill=WHITE if sel else DIM, font=self.f["tiny"])

    def _halo(self, size, color, alpha, dy):
        """Sombra/brilho de card. Desfoca UMA vez no tamanho grande e só redimensiona depois
        (desfocar de novo para cada tamanho da animação era o que mais pesava)."""
        size = (size[0] // 4 * 4, size[1] // 4 * 4)
        key = (size, color, alpha // 15, dy)
        if key not in self._halos:
            if len(self._halos) > 300:
                self._halos.clear()
            base_key = (color, alpha // 15, dy)
            if base_key not in self._halo_base:
                big = (int(self.tile_s[0] * HOVER_SCALE), int(self.tile_s[1] * HOVER_SCALE))
                self._halo_base[base_key] = make_halo(big, color, alpha // 15 * 15, 12, dy)
            target = (size[0] + 48, size[1] + 48)  # a imagem tem 24 px de margem em volta
            self._halos[key] = ImageTk.PhotoImage(self._halo_base[base_key].resize(target, Image.BILINEAR))
        return self._halos[key]

    @staticmethod
    def _story_year(ch):
        m = re.search(r"\d{4}", ch.get("quando", ""))
        return m.group(0) if m else ch.get("quando", "").split(" ")[0]

    def _tile(self, ch, size, dim=False):
        """Card no tamanho pedido. Monta uma vez em tamanho grande e só redimensiona durante as animações.
        dim=True: versão escurecida (cards que não estão em destaque)."""
        g = self.version_of(ch)
        art = self._image(store.art_key(g), "capa")
        if art is None and not g.get("poster"):  # versão sem arte: usa a de outra versão do capítulo
            other = next((v for v in ch["versoes"] if self._image(store.art_key(v), "capa") is not None), None)
            art = self._image(store.art_key(other), "capa") if other else None
        base_key = self._ensure_tile_base(ch, g, art)
        size = (size[0] // 2 * 2, size[1] // 2 * 2)  # arredonda: mais reaproveitamento durante as animações
        key = (base_key, size, dim)
        if key not in self._tiles:
            if len(self._tiles) > 400:
                self._tiles.clear()
            img = self._tile_base[base_key].resize(size, Image.BILINEAR)
            if dim:
                r, g, b, a = img.split()
                img = Image.merge("RGBA", [band.point(lambda v: int(v * 0.62)) for band in (r, g, b)] + [a])
            self._tiles[key] = ImageTk.PhotoImage(img)
        return self._tiles[key]

    def _ensure_tile_base(self, ch, g, art):
        """Card grande da versão (arte ou capa gerada). Fica na memória e em data/cache/cards, então só é montado
        uma vez por tamanho de tela, mesmo entre uma abertura do app e outra."""
        base_key = (g["id"], id(art) if art is not None else None)
        if base_key in self._tile_base:
            return base_key
        big = (int(self.tile_s[0] * HOVER_SCALE), int(self.tile_s[1] * HOVER_SCALE))
        if art is not None:
            src = store.art_path(store.art_key(g), "capa") or store.art_path(
                store.art_key(next((v for v in ch["versoes"] if store.art_path(store.art_key(v), "capa")), g)), "capa")
            stamp = f"arte|{src.name if src else ''}|{src.stat().st_mtime if src else 0}"
        else:
            short = ch["titulo"].replace(FR["prefixo_titulo"], "").strip(" :–") if FR["prefixo_titulo"] else ch["titulo"]
            if not short or short.startswith("("):  # "Resident Evil (2026)" fica inteiro
                short = ch["titulo"]
            p = g.get("poster") or {"titulo": short.upper(), "subtitulo": g.get("versao", "")}
            bg = self._random_art(g)  # o banner sorteado entra na chave: sem ele a capa é refeita quando houver artes
            pick = random.Random(g["id"]).choice(self._pool).name if bg is not None and self._pool else ""
            stamp = f"poster|{p}|{self._title_font_file(ch)}|{g['id']}|{pick}"
        name = hashlib.sha1(f"{stamp}|{big}|v2".encode()).hexdigest()[:20] + ".png"
        cached = CARDS / name
        img = None
        if cached.exists():
            try:
                img = Image.open(cached).convert("RGBA")
            except OSError:
                img = None
        if img is None:
            img = make_tile(art, big) if art is not None else make_poster(
                p["titulo"], p["subtitulo"], big, p.get("carimbo"), self._title_font_file(ch), bg)
            try:
                CARDS.mkdir(parents=True, exist_ok=True)
                img.save(cached)
            except OSError:
                pass
        self._tile_base[base_key] = img
        return base_key

    def _logo(self, g, max_size=(400, 84)):
        if g is None:
            return None
        key = store.art_key(g)
        if key not in self._logos:
            p = store.art_path(key, "logo")
            if not p:
                return None
            try:
                img = Image.open(p).convert("RGBA")
                bbox = img.getbbox()  # corta a margem transparente
                img = img.crop(bbox) if bbox else img
                img.thumbnail(max_size, Image.LANCZOS)
                self._logos[key] = ImageTk.PhotoImage(img)
            except OSError:
                return None
        return self._logos[key]

    def _title_font(self, ch):
        """Título com uma fonte parecida com a do logo do jogo (rehub/fonts.py); sem ela, a fonte padrão."""
        key = fonts.key_for(ch)
        got = fonts.ensure(key) if key else None
        if not got:
            return self.f["title"]
        news = ch.get("secao") == "noticias"  # manchetes são longas: letra menor para caber
        cache = key + ("_noticia" if news else "")
        if cache not in self._tfonts:
            size = 22 if news else {"pixel": 20, "script": 40, "cartaz": 36, "gibi": 34, "terror": 34}.get(key, 30)
            self._tfonts[cache] = Font(family=got[1], size=size, weight="bold" if key == "trajan" else "normal")
        return self._tfonts[cache]

    def _title_font_file(self, ch):
        key = fonts.key_for(ch)
        got = fonts.ensure(key) if key else None
        return got[0] if got else None

    def _draw_details(self):
        c, ch, g = self.c, self.chapter, self.game
        x, y, w = MARGIN, self.details_y, self._panel_box[0] - MARGIN - 40
        logo = self._logo(g)
        if logo:  # como na PS5: o logo do jogo no lugar do título
            c.create_image(x, y, image=logo, anchor="nw")
            y += logo.height() + 10
        else:
            title = c.create_text(x, y, anchor="nw", text=ch["titulo"], fill=WHITE, font=self._title_font(ch), width=w)
            y = c.bbox(title)[3] + 2
        where = "   ·   ".join(p for p in (ch.get("quando"), ch.get("onde")) if p)
        if ch.get("lancamento") and self.section not in ("perdidos", "fas"):  # perdidos nunca foram lançados
            where += f"   ·   lançado em {ch['lancamento']}"
        c.create_text(x, y, anchor="nw", text=where, fill=MUTED, font=self.f["small"], width=w)
        y += 26
        if ch.get("sinopse"):
            syn = c.create_text(x, y, anchor="nw", text=ch["sinopse"], fill="#d5d9e0", font=self.f["body"], width=min(w, 640))
            y = c.bbox(syn)[3] + 16

        if len(ch["versoes"]) > 1:  # pílulas de versão
            px = x
            for j, v in enumerate(ch["versoes"]):
                on = v is g
                pw = self.f["small"].measure(v["versao"]) + 30
                tag = f"ver{j}"
                shape = self._round_rect(px, y, px + pw, y + 30, 15, fill=WHITE if on else CHIP, outline="", tags=(tag,))
                c.create_text(px + pw / 2, y + 15, text=v["versao"], fill=t.BG if on else WHITE, font=self.f["small"], tags=(tag,))
                self._clickable(tag, lambda j=j: self.pick_version(0, absolute=j), shape=None if on else shape)
                px += pw + 8
            y += 42
        elif g["tipo"] != "info":  # nos itens de informação o formato já aparece na linha de estado
            c.create_text(x, y, anchor="nw", text=g.get("versao", ""), fill=DIM, font=self.f["small"])
            y += 24

        state, color = self._state(g)
        c.create_text(x, y, anchor="nw", text=self.status_text or state, fill=color, font=self.f["body"])
        y += 32
        bx = x
        for k, (text, cmd, primary) in enumerate(self._actions(g)):
            bx = self._button(bx, y, text, cmd, primary, f"btn{k}") + 10
        track = self.music.current
        if track and self.prefs["trilha"]:  # o que está tocando agora
            name = f"Tema original do {FR['app']}" if track.parent.name == "musica_gerada" else track.stem
            c.create_text(x, y + 60, anchor="nw", text=f"♪  {name}", fill=self.accent, font=self.f["small"])

    # ---------- painel da direita ----------
    def steam_game(self):
        """Versão selecionada se for da Steam; senão, a versão Steam do mesmo capítulo."""
        g = self.game
        return g if g["tipo"] == "steam" else next((v for v in self.chapter["versoes"] if v["tipo"] == "steam"), None)

    def _draw_panel(self, x1, y1, x2, y2):
        c, pad = self.c, 24
        x, y, w = x1 + pad, y1 + 18, x2 - x1 - 2 * pad
        tabs = (("trofeus", "Troféus"), ("trailer", "Trailer"), ("versoes", "Versões"), ("dlcs", "DLCs"))
        if self.game["tipo"] == "info":  # filmes, HQs e perdidos: só os detalhes
            tabs = (("versoes", "Detalhes"),)
        active = self.panel_tab if any(k == self.panel_tab for k, _ in tabs) else tabs[0][0]
        if active != "trailer":
            self._trailer_stop()
        # abas em cápsula: a ativa fica em destaque; as outras clareiam ao passar o mouse
        widths = [self.f["small"].measure(label) + 26 for _, label in tabs]
        total = sum(widths) + 4 * (len(tabs) - 1) + 8
        self._round_rect(x, y - 4, x + min(total, w), y + 28, 16, fill="#10141c", outline="#262d3a")
        tx = x + 4
        for (key, label), tw in zip(tabs, widths):
            on = active == key
            tag = f"tab_{key}"
            pill = self._round_rect(tx, y, tx + tw, y + 24, 12, fill=WHITE if on else "#10141c", outline="", tags=(tag,))
            txt = c.create_text(tx + tw / 2, y + 12, text=label, fill=t.BG if on else MUTED,
                                font=self.f["tiny"], tags=(tag,))
            self._clickable(tag, lambda k=key: self.set_tab(k),
                            hover=None if on else [(pill, "#10141c", "#202734"), (txt, MUTED, WHITE)])
            tx += tw + 4
        body = (x, y + 44, w, y2 - 14)
        if active == "trailer":
            return self._draw_trailer(*body)
        if active == "versoes":
            return self._draw_versions(self.chapter, *body)
        g = self.steam_game()
        if g is not None and g is not self.game:  # à esquerda do "Atualizar" para não sobrepor
            right = x + w - (self.f["tiny"].measure("Atualizar") + 16 if self.panel_tab == "trofeus" else 0)
            c.create_text(right, y + 3, anchor="ne", text=f"de {g['versao']} (Steam)", fill=DIM, font=self.f["small"])
        if self.panel_tab == "dlcs":
            self._draw_dlcs(g, *body)
        else:
            self._draw_trophies(g, *body)

    # ---------- trailer ----------
    def _draw_trailer(self, x, y, w, bottom):
        """Telinha com o trailer da Steam do jogo (baixado e convertido uma vez, depois fica guardado)."""
        c, g = self.c, self.steam_game()
        if g is None:
            self._trailer_stop()
            self._note(x, y, w, "Esse jogo não está na Steam, então não há trailer para tocar aqui.")
            q = urllib.parse.quote_plus(f"{self.game['nome']} trailer")
            self._chip(x, y + 54, "Ver trailer no YouTube  ›", lambda: webbrowser.open(
                f"https://www.youtube.com/results?search_query={q}"), "tr_yt", primary=True)
            return
        vh = min(int(w * 9 / 16), int(bottom - y - 44))
        vw = int(vh * 16 / 9)
        if not hasattr(self, "_tframe"):
            self._tframe = tk.Frame(self.c, bg="#000000")
            self._tlabel = tk.Label(self._tframe, bg="#000000", fg=MUTED, font=(t.FONT, 10))
            self._tplayer, self._tstate = trailer.Player(), {"appid": None}
        c.create_window(x, y - 6, window=self._tframe, anchor="nw", width=vw, height=vh)
        st = self._tstate
        if st["appid"] != g["appid"]:
            self._trailer_stop()
            st.update(appid=g["appid"], status="loading", paused=False, sound=False, size=(vw, vh))  # começa mudo: a trilha continua
            self._tlabel.config(text="Preparando o trailer...\n(na primeira vez demora uns segundos)")
            self._tlabel.place(relx=0.5, rely=0.5, anchor="center")
            # só começa depois de parar no jogo por um instante (passar pelos jogos não baixa trailer de todos)
            self.after(900, lambda a=g["appid"]: self._trailer_fetch(a))
        else:
            st["size"] = (vw, vh)
            self._tplayer.resize(vw, vh)
        cy = y - 6 + vh + 10
        if st["status"] == "playing":
            bx = self._chip(x, cy, "▶  Continuar" if st["paused"] else "❚❚  Pausar", self._trailer_pause, "tr_pause") + 8
            bx = self._chip(bx, cy, "Som: ligado" if st["sound"] else "Som: desligado", self._trailer_sound, "tr_sound") + 8
        else:
            bx = x
        self._chip(x + w, cy, "Abrir na Steam  ›", lambda: steam.store(g["appid"]), "tr_store", anchor="e")

    def _trailer_fetch(self, appid):
        """Prepara um trailer por vez; se outro for pedido no meio, prepara o último pedido quando terminar."""
        st = self._tstate
        if st.get("appid") != appid or self.panel_tab != "trailer":
            return
        if getattr(self, "_tbusy", None):
            return  # quando o atual terminar, done() confere qual é o pedido da vez
        self._tbusy = appid

        def finish():
            self._tbusy = None
            want = st.get("appid")
            if want and want != appid and st.get("status") == "loading" and self.panel_tab == "trailer":
                self._trailer_fetch(want)

        def done(path):
            finish()
            if st.get("appid") != appid or self.panel_tab != "trailer":
                return
            self._tlabel.place_forget()
            self._tframe.update_idletasks()
            vw, vh = st["size"]
            if self._tplayer.open(path, self._tframe.winfo_id(), vw, vh, st["sound"]):
                st["status"] = "playing"
                if st["sound"]:
                    self.music.set_enabled(False)  # a trilha do capítulo dá lugar ao som do trailer
            else:
                st["status"] = "error"
                self._tlabel.config(text="O Windows não conseguiu tocar o trailer.")
                self._tlabel.place(relx=0.5, rely=0.5, anchor="center")
            self.refresh()

        def fail(msg):
            finish()
            if st.get("appid") == appid:
                st["status"] = "error"
                self._tlabel.config(text=msg)
                self._tlabel.place(relx=0.5, rely=0.5, anchor="center")
                self.refresh()
        t.in_background(self, lambda: trailer.ensure(appid), done, fail)

    def _trailer_pause(self):
        self._tstate["paused"] = self._tplayer.toggle_pause()
        self.refresh()

    def _trailer_sound(self):
        st = self._tstate
        st["sound"] = not st["sound"]
        self._tplayer.set_sound(st["sound"])
        self.music.set_enabled(self.prefs["trilha"] and not st["sound"])
        if not st["sound"]:
            self._queue_music()
        self.refresh()

    def _trailer_stop(self):
        if not hasattr(self, "_tplayer"):
            return
        was = self._tplayer.path is not None
        self._tplayer.close()
        self._tstate["appid"] = None
        if was:  # a trilha do capítulo volta
            self.music.set_enabled(self.prefs["trilha"])
            self._queue_music()

    def _draw_versions(self, ch, x, y, w, bottom):
        """Todas as edições já lançadas do jogo, com plataformas e onde dá para jogar hoje."""
        c, items = self.c, ch.get("lancamentos", [])
        if not items:
            return self._note(x, y, w, "Ainda não há lista de versões para este jogo.")
        n = len(items)
        c.create_text(x, y - 4, anchor="nw", text="Notícia" if self.section == "noticias" else f"{n} {'versões' if n > 1 else 'versão'}", fill=WHITE, font=self.f["h"])
        hint = {"midia": "onde assistir", "hqs": "onde ler", "perdidos": "o que sobrou", "fas": "onde encontrar", "noticias": FR["noticias"].get("fonte", "")}.get(self.section, "onde jogar hoje")
        c.create_text(x + w, y - 2, anchor="ne", text=hint, fill=DIM, font=self.f["small"])

        def row(v, ry):
            yw = self.f["btn"].measure(str(v["ano"]))
            c.create_text(x, ry, anchor="nw", text=self._elide(v["nome"], self.f["btn"], w - yw - 16), fill=WHITE, font=self.f["btn"])
            c.create_text(x + w, ry, anchor="ne", text=str(v["ano"]), fill=MUTED, font=self.f["btn"])
            c.create_text(x, ry + 21, anchor="nw", text=self._elide(v["plataformas"], self.f["small"], w), fill=MUTED, font=self.f["small"])
            c.create_oval(x, ry + 43, x + 6, ry + 49, fill=self.accent, outline="")
            c.create_text(x + 12, ry + 38, anchor="nw", text=self._elide(v["onde"], self.f["small"], w - 12), fill="#d5d9e0",
                          font=self.f["small"])
        self._list_window(items, x, y + 30, w, bottom, 68, row)

    def _chip(self, x, y, label, cmd, tag, primary=False, anchor="w"):
        """Botão pequeno arredondado. anchor='e' alinha pela direita. Retorna a outra ponta."""
        w = self.f["small"].measure(label) + 26
        x1 = x - w if anchor == "e" else x
        shape = self._round_rect(x1, y, x1 + w, y + 28, 14, fill=WHITE if primary else CHIP, outline="", tags=(tag,))
        self.c.create_text(x1 + w / 2, y + 14, text=label, fill=t.BG if primary else WHITE, font=self.f["small"], tags=(tag,))
        if primary:
            self._clickable(tag, cmd, hover=[(shape, WHITE, "#d9dee8")])
        else:
            self._clickable(tag, cmd, shape=shape)
        return x1 if anchor == "e" else x1 + w

    def _note(self, x, y, w, msg):
        self.c.create_text(x, y, anchor="nw", text=msg, fill=MUTED, font=self.f["body"], width=w)

    def _list_window(self, items, x, y, w, bottom, row_h, draw_row):
        """Desenha uma lista rolável (roda do mouse sobre o painel)."""
        fits = max(1, int((bottom - y) // row_h))
        self.panel_scroll = min(self.panel_scroll, max(0, len(items) - fits))
        for k, it in enumerate(items[self.panel_scroll:self.panel_scroll + fits]):
            draw_row(it, y + k * row_h)
            self._row_rects.append((x - 12, y + k * row_h - 4, x + w + 4, y + (k + 1) * row_h - 8))
        if len(items) > fits:
            c = self.c
            track_h = bottom - y
            bar_h = max(24, track_h * fits / len(items))
            by = y + (track_h - bar_h) * self.panel_scroll / max(1, len(items) - fits)
            c.create_rectangle(x + w + 12, y, x + w + 14, bottom, fill="#232a36", outline="")
            c.create_rectangle(x + w + 12, by, x + w + 14, by + bar_h, fill=MUTED, outline="")

    def _draw_trophies(self, g, x, y, w, bottom):
        c = self.c
        if g is None:
            return self._note(x, y, w, "Este capítulo não tem versão na Steam, então não há troféus para mostrar.")
        if not self.steamid:
            return self._note(x, y, w, "Não encontrei sua conta Steam neste PC.")
        s = self.trophy_state.get(g["appid"])
        tag = "trophy_refresh"
        c.create_text(x + w, y - 41, anchor="ne", text="Atualizar", fill=MUTED, font=self.f["tiny"], tags=(tag,))
        self._clickable(tag, self.refresh_trophies)
        if s is None:
            return self._note(x, y, w, "Carregando troféus...")
        if "erro" in s:
            return self._note(x, y, w, s["erro"])
        if not s["total"]:
            return self._note(x, y, w, "Este jogo não tem conquistas na Steam (ou ainda não foi lançado).")

        plat = s["platina"]
        c.create_text(x, y - 8, anchor="nw", text=f"{s['progresso']}%", fill=WHITE, font=self.f["big"])
        px = x + self.f["big"].measure(f"{s['progresso']}%") + 16
        c.create_text(px, y + 6, anchor="nw", text=f"{s['conquistados']} de {s['total']}", fill=WHITE, font=self.f["h"])
        c.create_text(px, y + 30, anchor="nw", fill=TIER_COLORS["platina"] if plat else MUTED, font=self.f["small"],
                      text="PLATINA CONQUISTADA" if plat else "conquistados")
        by = y + 60
        self._round_rect(x, by, x + w, by + 6, 3, fill=CHIP, outline="")
        if s["progresso"]:
            self._round_rect(x, by, x + max(6, w * s["progresso"] / 100), by + 6, 3,
                             fill=TIER_COLORS["platina"] if plat else WHITE, outline="")

        ty, col = by + 30, w / 4
        for k, tier in enumerate(trophies.TIERS):
            cx = x + col * k
            have, total = s["por_tier"][tier]
            self._cup(cx + 9, ty, 9, TIER_COLORS[tier], dim=not have)
            c.create_text(cx + 26, ty, anchor="w", text=f"{have}/{total}", fill=WHITE, font=self.f["h"])
            c.create_text(cx + 26, ty + 20, anchor="w", text=TIER_NAMES[tier], fill=DIM, font=self.f["small"])

        items, label = (s["recentes"], "CONQUISTADOS RECENTEMENTE") if s["recentes"] else (s["proximos"], "MAIS FÁCEIS PARA COMEÇAR")
        ly = ty + 46
        c.create_text(x, ly, anchor="nw", text=label, fill=MUTED, font=self.f["tiny"])

        def row(it, ry):
            icon = self._remote_img(it["icone"], (36, 36))
            if icon:
                c.create_image(x, ry, image=icon, anchor="nw")
            else:
                self._round_rect(x, ry, x + 36, ry + 36, 6, fill=CHIP, outline="")
            tw = w - 48 - 26
            c.create_text(x + 48, ry + 1, anchor="nw", text=self._elide(it["nome"], self.f["btn"], tw), fill=WHITE, font=self.f["btn"])
            pct = f"{it['raridade']:.1f}% dos jogadores" if it["raridade"] is not None else "raridade indisponível"
            c.create_text(x + 48, ry + 21, anchor="nw", text=self._elide(f"{pct}  ·  {it['descricao']}", self.f["small"], tw),
                          fill=MUTED, font=self.f["small"])
            self._cup(x + w - 8, ry + 18, 7, TIER_COLORS[it["tier"]], dim=not it["conquistado"])
        self._list_window(items, x, ly + 24, w, bottom, 46, row)

    def _draw_dlcs(self, g, x, y, w, bottom):
        c = self.c
        if g is None:
            return self._note(x, y, w, "Este capítulo não tem versão na Steam, então não há DLCs para mostrar.")
        appid = g["appid"]
        if appid not in self.dlc_state:
            self._fetch_dlcs(appid)
        s = self.dlc_state.get(appid)
        if s is None:
            return self._note(x, y, w, "Carregando DLCs...")
        if isinstance(s, dict):
            return self._note(x, y, w, s["erro"])
        if not s:
            return self._note(x, y, w, "Este jogo não tem DLCs na Steam.")
        c.create_text(x, y - 4, anchor="nw", text=f"{len(s)} DLC{'s' if len(s) > 1 else ''}", fill=WHITE, font=self.f["h"])
        tag = "dlc_store"
        c.create_text(x + w, y - 2, anchor="ne", text="Ver todas na loja  ›", fill=MUTED, font=self.f["small"], tags=(tag,))
        self._clickable(tag, lambda: os.startfile(f"steam://openurl/https://store.steampowered.com/dlc/{appid}/"))

        def row(d, ry):
            tagr = f"dlc{d['id']}"
            thumb = self._remote_img(d["imagem"], (92, 43), 5)
            if thumb:
                c.create_image(x, ry, image=thumb, anchor="nw", tags=(tagr,))
            else:
                self._round_rect(x, ry, x + 92, ry + 43, 5, fill=CHIP, outline="", tags=(tagr,))
            tw = w - 104
            c.create_text(x + 104, ry + 2, anchor="nw", text=self._elide(d["nome"], self.f["btn"], tw), fill=WHITE,
                          font=self.f["btn"], tags=(tagr,))
            c.create_text(x + 104, ry + 23, anchor="nw", text=d["preco"] or "Ver na loja", fill=MUTED, font=self.f["small"], tags=(tagr,))
            self._clickable(tagr, lambda i=d["id"]: steam.store(i))
        self._list_window(s, x, y + 30, w, bottom, 54, row)

    # ---------- primitivas ----------
    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        r = min(r, (x2 - x1) / 2, (y2 - y1) / 2)
        pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2,
               x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
        return self.c.create_polygon(pts, smooth=True, **kw)

    def _cup(self, cx, cy, s, color, dim=False):
        """Ícone de troféu desenhado (taça + base)."""
        fill = color if not dim else DIM
        c = self.c
        c.create_polygon(cx - s, cy - s, cx + s, cy - s, cx + s * 0.7, cy + s * 0.2, cx + s * 0.25, cy + s * 0.45,
                         cx - s * 0.25, cy + s * 0.45, cx - s * 0.7, cy + s * 0.2, fill=fill, outline="", smooth=True)
        c.create_rectangle(cx - s * 0.15, cy + s * 0.4, cx + s * 0.15, cy + s * 0.75, fill=fill, outline="")
        c.create_rectangle(cx - s * 0.55, cy + s * 0.75, cx + s * 0.55, cy + s, fill=fill, outline="")

    def _button(self, x, y, text, cmd, primary, tag):
        w, h = self.f["btn"].measure(text) + 48, 44
        fill, fg = (WHITE, t.BG) if primary else (CHIP, WHITE)
        shape = self._round_rect(x, y, x + w, y + h, 22, fill=fill, outline="", tags=(tag,))
        self.c.create_text(x + w / 2, y + h / 2, text=text, fill=fg, font=self.f["btn"], tags=(tag,))
        self._clickable(tag, lambda: (self._sound("prompt_enter" if primary else "enter"), cmd()),
                        shape=None if primary else shape, hover=[(shape, WHITE, "#d9dee8")] if primary else None)
        return x + w

    def _clickable(self, tag, cmd, shape=None, hover=None):
        """Clique + cursor de mão + reação ao passar o mouse.
        shape: fundo de botão escuro (clareia). hover: [(item, cor normal, cor com o mouse)] para outros itens.

        Cada tag é ligada ao Tk uma vez só; nos redesenhos seguintes só troca a ação guardada.
        (Ligar de novo a cada quadro criava milhares de comandos no Tk e deixava tudo lento.)"""
        changes = list(hover or []) + ([(shape, CHIP, CHIP_HI)] if shape else [])
        self._clicks[tag] = (cmd, changes)
        if tag in self._bound:
            return
        self._bound.add(tag)
        c = self.c

        def paint(on):
            for item, normal, hi in self._clicks.get(tag, (None, []))[1]:
                try:
                    c.itemconfigure(item, fill=hi if on else normal)
                except tk.TclError:  # item de um quadro antigo
                    pass

        def enter(e):
            c.config(cursor="hand2")
            paint(True)

        def leave(e):
            c.config(cursor="")
            paint(False)
        c.tag_bind(tag, "<Button-1>", lambda e: self._clicks[tag][0]())
        c.tag_bind(tag, "<Enter>", enter)
        c.tag_bind(tag, "<Leave>", leave)

    def _canvas_click(self, e):
        """Clique nos cards (pela posição, sem ligar cada card ao Tk a cada quadro)."""
        hit = next((i for i, x1, y1, x2, y2 in self._tile_rects if x1 <= e.x <= x2 and y1 <= e.y <= y2), None)
        if hit is not None:
            self.click_tile(hit)

    @staticmethod
    def _elide(text, font, width):
        if font.measure(text) <= width:
            return text
        while text and font.measure(text + "…") > width:
            text = text[:-1]
        return text.rstrip() + "…"

    def _options_menu(self):
        m = tk.Menu(self, tearoff=0, bg=t.PANEL, fg=WHITE, activebackground=t.PANEL_HI, activeforeground=WHITE,
                    font=(t.FONT, 10), bd=0)
        m.add_command(label="Atualizar troféus de todos os jogos", command=self.refresh_all_trophies)
        m.add_command(label="Baixar as artes de novo", command=self.reload_art)
        m.add_command(label="Recarregar catálogo e jogos instalados (F5)", command=self.rescan)
        m.add_separator()
        name = self.chapter["titulo"] if self.chapter else "este capítulo"
        m.add_command(label=f"Escolher música para {name}...", command=self.pick_music)
        m.add_command(label="Abrir pasta de músicas", command=lambda: (audio.MUSIC.mkdir(parents=True, exist_ok=True),
                                                                       os.startfile(audio.MUSIC)))
        m.add_command(label="Abrir Fluffy Mod Manager (mods)", command=self.open_fluffy)
        m.add_separator()
        m.add_command(label="Tela cheia (F11)", command=self.toggle_fullscreen)
        m.add_command(label="Abrir pasta de dados", command=lambda: (DATA.mkdir(exist_ok=True), os.startfile(DATA)))
        m.add_command(label="Abrir pasta do catálogo (games)", command=lambda: os.startfile(ROOT / "games"))
        m.add_command(label="Abrir LEIA-ME", command=lambda: os.startfile(ROOT / "LEIA-ME.md"))
        m.add_separator()
        m.add_command(label=f"Sair do {FR['app']}", command=self.destroy)
        self._sound("menu_on")
        try:
            m.tk_popup(self.winfo_pointerx(), self.winfo_pointery())  # no Windows, volta quando o menu fecha
        finally:
            m.grab_release()
            self._sound("menu_off")

    # ---------- estado e ações ----------
    def _state(self, g):
        if g["tipo"] == "info":
            return g.get("versao", ""), MUTED
        ready = launcher.is_ready(g, self.cfg, self.installed)
        if g["tipo"] == "steam":
            text, color = ("Instalado", GREEN) if ready else ("Não instalado", MUTED)
        elif ready:
            text, color = "Pronto para jogar", GREEN
        else:
            text, color = ("Não baixado" if g.get("github") else "Não configurado"), MUTED
        return text, color

    def _actions(self, g):
        if g["tipo"] == "info":  # filmes, HQs e perdidos: links para saber mais
            links = g.get("links") or []
            return [(lk["nome"], lambda u=lk["url"]: webbrowser.open(u), k == 0) for k, lk in enumerate(links)] or \
                   [("Pesquisar", lambda: webbrowser.open("https://pt.wikipedia.org/wiki/Special:Search?search="
                                                          + urllib.parse.quote(g["nome"])), True)]
        manage = ("Gerenciar", self.manage, False)
        if g["tipo"] == "steam":
            a = g["appid"]
            first = ("Jogar", lambda: self.play(g), True) if a in self.installed else ("Instalar", lambda: steam.install(a), True)
            acts = [first, manage, ("Loja", lambda: steam.store(a), False)]
            if a in self.installed:
                acts.append(("Desinstalar", lambda: self.uninstall_game(g), False))
            return acts
        if launcher.is_ready(g, self.cfg, self.installed):
            return [("Jogar", lambda: self.play(g), True), manage, ("Desinstalar", lambda: self.uninstall_game(g), False)]
        if g.get("github"):
            return [("Baixar", lambda: self.download_game(g), True), manage]
        return [("Configurar", lambda: self.configure_local(g), True), manage]

    def uninstall_game(self, g, parent=None):
        """Desinstalar: na Steam, desativa os mods e abre a confirmação da Steam; nos outros, apaga só o que o app
        baixou (recomps) e esquece executável/ISO. Arquivos do usuário (jogo, ISO, saves) nunca são apagados."""
        parent = parent or self
        mm = ModManager(g["id"], launcher.game_dir(g, self.cfg, self.installed))  # mods do sistema antigo, se sobrou algum
        active = list(mm.state["ativos"])
        if g["tipo"] == "steam":
            details = ["A Steam pede para confirmar e apaga os arquivos do jogo.",
                       "Os saves na nuvem da Steam continuam lá."]
            if active:
                details.insert(0, f"Antes, o app desativa {len(active)} mod(s) e devolve os arquivos originais.")
            details.append("Sua biblioteca de mods no app fica guardada para quando reinstalar.")
            if not t.confirm(parent, f"Desinstalar {g['nome']}?", "Isso tira o jogo do seu PC.", details,
                             ok="Desinstalar", danger=True):
                return
            for mod_id in active:
                try:
                    mm.disable(mod_id)
                except OSError:
                    pass
            steam.uninstall(g["appid"])
            return
        dl = launcher.download_dir(g)
        details = ["Apaga o que o app baixou para este jogo." if dl.exists() else
                   "O app só esquece onde o executável e a ISO estão.",
                   "Seus arquivos (jogo, ISO, saves) não são apagados."]
        if not t.confirm(parent, f"Desinstalar {g['nome']} do app?", "O jogo volta a aparecer como não configurado.",
                         details, ok="Desinstalar", danger=True):
            return
        for mod_id in active:
            try:
                mm.disable(mod_id)
            except OSError:
                pass
        if dl.exists():
            shutil.rmtree(dl.parent, ignore_errors=True)  # data/recomps/<jogo>/
        self.cfg.clear(g["id"])
        self.refresh()
        t.notice(parent, "Desinstalado", f"{g['nome']} saiu do app.")

    def open_fluffy(self):
        """Abre o Fluffy Mod Manager; se ainda não foi baixado, baixa antes."""
        if fluffy.installed():
            return fluffy.open_manager()
        if t.confirm(self, "Baixar o Fluffy Mod Manager?", "Os mods são instalados por ele (gratuito, de FluffyQuack).",
                     ["Fica em data/ferramentas/FluffyModManager."], ok="Baixar"):
            t.in_background(self, fluffy.download, lambda _: fluffy.open_manager(),
                            lambda msg: t.notice(self, "Não deu certo", msg, error=True))

    def primary_action(self):
        if self.game:
            self._sound("prompt_enter")
            self._actions(self.game)[0][1]()

    def manage(self):
        if self.game and self.game["tipo"] != "info":
            self._sound("open")
            ManageWindow(self, self.game)

    def refresh_trophies(self):
        g = self.steam_game()
        if not g:
            return
        self.trophy_state[g["appid"]] = None
        self.refresh()
        threading.Thread(target=self._fetch_trophies, args=(g["appid"], True), daemon=True).start()

    def refresh_all_trophies(self):
        threading.Thread(target=self._fetch_trophies, kwargs={"force": True}, daemon=True).start()

    def reload_art(self):
        shutil.rmtree(COVERS, ignore_errors=True)
        shutil.rmtree(store.CACHE, ignore_errors=True)
        self._pil.clear()
        self._tiles.clear()
        self._tile_base.clear()
        self._logos.clear()
        self._bg_key, self._bg_photo = None, None
        self.refresh()
        threading.Thread(target=self._fetch_art, daemon=True).start()

    def play(self, g):
        try:
            launcher.play(g, self.cfg)
        except RuntimeError as e:
            messagebox.showerror(FR["app"], str(e))

    def configure_local(self, g, parent=None):
        """Escolhe o executável (e a ISO, se o jogo precisar). Retorna True se salvou."""
        parent = parent or self
        start = launcher.download_dir(g) if launcher.download_dir(g).exists() else None
        exe = filedialog.askopenfilename(parent=parent, title=f"{g['nome']}: escolha o executável (jogo, recomp ou emulador)",
                                         initialdir=start, filetypes=[("Executável", "*.exe"), ("Todos", "*.*")])
        if not exe:
            return False
        values = {"exe": exe}
        if "{iso}" in g.get("args", ""):
            iso = filedialog.askopenfilename(parent=parent, title=f"{g['nome']}: escolha a SUA ISO/imagem do jogo",
                                             filetypes=[("Imagem", "*.iso *.bin *.cue *.chd *.gdi *.cdi"), ("Todos", "*.*")])
            if not iso:
                return False
            if g.get("iso_sha1") and launcher.sha1(iso).lower() != g["iso_sha1"].lower():
                if not messagebox.askyesno(FR["app"], "Essa ISO não é a versão esperada. Usar mesmo assim?", parent=parent):
                    return False
            values["iso"] = iso
        self.cfg.set(g["id"], **values)
        self.refresh()
        return True

    def download_game(self, g, on_done=None):
        """Baixa/atualiza o recomp/decomp do GitHub sem apagar saves e assets já colocados."""
        self.status_text = f"Baixando {g['nome']}..."
        self.refresh()

        def work():
            tag = github.download_release(g["github"], g.get("asset"), launcher.download_dir(g), merge=True)
            return tag, launcher.find_exe(g)

        def finish():
            self.status_text = ""
            self.refresh()
            if on_done:
                on_done()

        def done(result):
            tag, exe = result
            if exe:
                self.cfg.set(g["id"], exe=str(exe))
            msg = f"{g['nome']} {tag} baixado."
            if g.get("depois_de_baixar"):
                msg += "\n\nPróximo passo: " + g["depois_de_baixar"]
            elif not exe:
                msg += "\n\nAgora clique em Configurar e escolha o .exe."
            messagebox.showinfo(FR["app"], msg)
            finish()

        def fail(msg):
            messagebox.showerror(FR["app"], f"Falha ao baixar:\n{msg}")
            finish()

        t.in_background(self, work, done, fail)


def main():
    # uma cópia só: o .exe demora uns segundos para abrir, e um segundo clique abria outra (com outra música junto)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateMutexW(None, False, f"{FR['id']}_hub_uma_janela")  # cada franquia abre a sua
    if ctypes.get_last_error() == 183:  # ERROR_ALREADY_EXISTS
        hwnd = ctypes.windll.user32.FindWindowW(None, FR["app"])
        if hwnd:
            ctypes.windll.user32.ShowWindow(hwnd, 9)  # SW_RESTORE
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        return
    Hub().mainloop()
