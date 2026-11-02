"""Tela principal no estilo PS5: capítulos em ordem da história, arte grande, troféus e DLCs.

O Hub junta os mixins: home.py (desenho da tela principal), panel.py (painel da direita), actions.py (ações de
cada jogo), isos_ui.py (ISOs), screens.py, lore_screens.py e more_screens.py (telas por cima), channels_ui.py
(Canais) e system_ui.py (atualização, cache, modo sofá, backups)."""
import ctypes
import hashlib
import os
import random
import shutil
import threading
import time
import tkinter as tk
import urllib.request
from tkinter import filedialog

from PIL import Image, ImageTk

from .. import audio, cache, catalog, gamepad, isodl, library, news, launcher, sofa, steam, store, trophies
from .. import log as logmod
from ..franchise import FR
from ..paths import COVERS, DATA, ROOT
from . import skin, theme as t
from .actions import GameActions
from .art import (BG_RGB, CHIP, CHIP_HI, DIM, GAP, GREEN, HOVER_LIFT, HOVER_SCALE, MARGIN, MUTED, RED,  # noqa: F401
                  TIER_COLORS, TIER_NAMES, TILES_Y, WHITE, Font, accent_from, compose_background, fit_cover, hex_rgb,
                  make_halo, pil_font, rounded, wrap)
from .home import Home
from .isos_ui import IsoActions
from .panel import Panel
from .splash import Splash
from .lore_screens import LoreScreens
from .more_screens import MoreScreens
from .screens import Screens
from .system_ui import SystemActions
from .channels_ui import ChannelsUI
from ..log import log

SECTIONS = (("canon", "Linha do tempo"), ("spinoff", "Não canônicos"), ("perdidos", "Perdidos"), ("midia", "Filmes"),
            ("hqs", "HQs e livros"), ("fas", "Feito por fãs"), ("noticias", "Notícias"),
            ("canais", "Canais"))
REMOTE = DATA / "imagens"
CARDS = DATA / "cache" / "cards"  # cards já montados (arte recortada ou capa gerada), por tamanho de tela  # ícones de troféus e miniaturas de DLC baixados



class Hub(Home, Panel, GameActions, IsoActions, SystemActions, ChannelsUI, Screens, LoreScreens, MoreScreens, tk.Tk):
    def __init__(self):
        super().__init__()
        self.report_callback_exception = lambda *exc: log.error("erro na interface", exc_info=exc)
        self.title(FR["app"])
        self.geometry("1280x800")
        self.minsize(min(1280, self.winfo_screenwidth() - 40), min(900, self.winfo_screenheight() - 80))
        self.configure(bg=t.BG)
        icon = ROOT / f"{FR['icone']}.ico"
        if icon.exists():
            self.iconbitmap(default=str(icon))
        t.dark_titlebar(self)
        self.bind("<Map>", lambda e: e.widget is self and self.after(30, lambda: t.dark_titlebar(self)), add="+")

        self.cfg = catalog.Config()
        self.prefs = {"tela_cheia": True, "trilha": True, "efeitos": True, **self.cfg.get("_prefs")}
        if os.environ.get("REHUB_TESTE"):  # testes automáticos: janela normal e sem som
            self.prefs.update(tela_cheia=False, trilha=False, efeitos=False)
        self.attributes("-fullscreen", not os.environ.get("REHUB_TESTE"))  # sempre abre em tela cheia
        audio.ensure_effects()
        self.music = audio.Music()
        self.splash = None
        self.tasks, self._tasks_job = [], None   # downloads e conversões em andamento (aparecem embaixo do jogo)
        self.music.set_enabled(self.prefs["trilha"])
        self._music_job = None
        self.installed = steam.installed_apps()
        self.steamid, self.persona = trophies.steam_user()
        self.section, self.order, self.only_installed = "canon", "historia", False
        self.sel = 0
        self.version_idx = {}
        self.overlay = None
        self.status_text = ""
        self.panel_tab, self.panel_scroll = "trofeus", 0
        self.games = catalog.load_games()
        self._build_chapters()
        self._start_at_last_played()
        self.trophy_state = {g["appid"]: trophies.cached(g["appid"]) for g in self.games if g["tipo"] == "steam"}
        self.dlc_state = {}
        self._toasts, self.store_info = [], {}
        self.deals_state = None
        self._minis, self._portraits, self._thumbs, self._thumb_pending, self._media_cache = {}, {}, {}, set(), {}
        self._dim_photo = None
        self._lore_init()

        self._pil, self._tiles, self._remote, self._remote_pending = {}, {}, {}, set()
        self._tile_base, self._halos, self._halo_base = {}, {}, {}
        self._clicks, self._bound, self._last_click, self._launching = {}, set(), {}, {}  # ações dos botões (ligadas ao Tk uma vez só)
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
            ("title", "Bahnschrift SemiBold", 30, "normal"), ("h", "Bahnschrift SemiBold", 13, "normal"),
            ("body", "Segoe UI", 11, "normal"), ("small", "Bahnschrift", 10, "normal"),
            ("btn", "Bahnschrift SemiBold", 12, "normal"), ("big", "Bahnschrift Light", 34, "normal"),
            ("logo", "Bahnschrift SemiBold", 15, "normal"), ("tiny", "Bahnschrift SemiBold", 9, "normal"),
            ("nav", "Bahnschrift SemiBold", 11, "normal"), ("clock", "Bahnschrift Light", 16, "normal"))}

        self.c = tk.Canvas(self, bg=t.BG, highlightthickness=0)
        self.c.pack(fill="both", expand=True)
        self.c.bind("<Configure>", lambda e: self.refresh())
        self.c.bind("<Motion>", self._motion)
        self._nav_hover, self._nav_rects, self._peek_rect = None, [], None
        self.nav_focus = False   # teclado/controle no menu do topo (W ou seta para cima)
        self.c.bind("<Leave>", lambda e: self._nav_hover and (setattr(self, "_nav_hover", None), self._draw_nav()), add="+")
        self.c.bind("<Button-1>", self._canvas_click)
        self.c.bind("<Leave>", lambda e: self._set_hover(None))
        self.bind("<MouseWheel>", self._wheel)
        self.protocol("WM_DELETE_WINDOW", self._close_request)
        for key, action in (("<Left>", "left"), ("<Right>", "right"), ("<Up>", "up"), ("<Down>", "down"),
                            ("<Return>", "enter"), ("<g>", "manage"), ("<Tab>", "next_section"), ("<Escape>", "esc"),
                            ("<p>", "profile"), ("<h>", "story"), ("<c>", "people"), ("<l>", "deals"), ("<f>", "photo"),
                            ("<e>", "extras"), ("<Prior>", "tab_prev"), ("<Next>", "tab_next"), ("<m>", "map"),
                            ("<a>", "left"), ("<d>", "right"), ("<w>", "up"), ("<s>", "down"), ("<q>", "files"), ("<r>", "relations"), ("<v>", "virus"), ("<k>", "achievements"),
                            ("<n>", "marathon"), ("<z>", "quiz"), ("<Control-f>", "search"), ("<slash>", "search")):
            self.bind(key, lambda e, a=action: self._press(a))
        self.bind("<F11>", lambda e: self.toggle_fullscreen())
        self.bind("<F5>", lambda e: self.rescan())
        self.pad = gamepad.Pad()
        self.after(500, self._poll_pad)
        if not os.environ.get("REHUB_TESTE"):  # Ctrl+Alt+H de qualquer lugar traz o hub de volta
            self._hotkey = gamepad.global_hotkey(lambda: self.after(0, self.summon))

        threading.Thread(target=self._fetch_art, daemon=True).start()
        threading.Thread(target=self._fetch_news, daemon=True).start()
        threading.Thread(target=self._fetch_channels, daemon=True).start()
        threading.Thread(target=self._fetch_trophies, daemon=True).start()
        self.after(4000, self.refresh_deals)
        self.after(8000, self.check_achievements)
        self.after(2500, self.prepare_wiki)  # Resident Evil Wiki em português: lista de personagens e vírus  # conquistas do hub liberadas desde a última vez  # preços e lista de desejos (avisa se algum jogo estiver em promoção)
        self._tick()
        self._away = self._seen_front = False
        if not os.environ.get("REHUB_TESTE"):
            self.after(300, lambda: (self.lift(), self.focus_force()))
            self.bind("<Map>", lambda e: e.widget is self and self._away and self._come_back())  # voltou pela barra de tarefas
            self.after(1500, self._watch_focus)
        self._sofa, self._sofa_cancel = sofa.started_by_windows(), False   # aberto pelo Windows (modo sofá)
        if os.environ.get("REHUB_TESTE"):
            self._queue_music()
        else:  # tela de carregamento por cima enquanto a principal monta por baixo; a trilha começa depois
            Splash(self, on_done=lambda: (self._queue_music(), self._sofa and self._sofa_go()), sound=self.prefs["efeitos"])
        self._system_start()

    # ---------- dados ----------
    def _build_chapters(self):
        chapters = catalog.load_timeline(self.games, self.section)
        if self.only_installed and self.section in ("canon", "spinoff"):
            chapters = [ch for ch in chapters if any(launcher.is_ready(g, self.cfg, self.installed) for g in ch["versoes"])]
        if self.order == "lancamento":
            chapters.sort(key=lambda ch: ch.get("lancamento", 9999))
        elif self.order == "recentes":  # o que você jogou por último primeiro (como na PS5)
            chapters.sort(key=lambda ch: -max((self.last_played(g) for g in ch["versoes"]), default=0))
        self.chapters = chapters
        self.sel = max(0, min(self.sel, len(chapters) - 1))

    # ---------- horas jogadas e "continuar" ----------
    def playtimes(self):
        now = time.time()
        if now - getattr(self, "_play_at", 0) > 2:  # é lido a cada quadro da animação: confere o arquivo a cada 2 s
            self._play, self._play_at = library.playtimes(self.steamid), now
        return self._play

    def last_played(self, g):
        """Quando a versão foi jogada por último: pela Steam ou pelo próprio app (jogos fora da Steam)."""
        if g.get("tipo") == "steam":
            return self.playtimes().get(g["appid"], {}).get("ultima", 0)
        return self.cfg.get(g["id"]).get("ultima", 0) if g.get("tipo") != "info" else 0

    def continue_target(self):
        """(seção, capítulo, versão) jogado por último, ou None (guardado por 2 s: é usado a cada quadro)."""
        now = time.time()
        if now - getattr(self, "_cont_at", 0) < 2:
            return self._cont
        self._cont_at, self._cont = now, self._find_continue()
        return self._cont

    def _find_continue(self):
        best = None
        for sec in ("canon", "spinoff"):
            for ch in catalog.load_timeline(self.games, sec):
                for g in ch["versoes"]:
                    ts = self.last_played(g)
                    if ts and (best is None or ts > best[0]):
                        best = (ts, sec, ch, g)
        return best[1:] if best else None

    def _start_at_last_played(self):
        """Ao abrir, já para no último jogo que você jogou (se for da linha do tempo)."""
        target = self.continue_target()
        if target and target[0] == self.section:
            _, ch, g = target
            self.sel = next((i for i, c in enumerate(self.chapters) if c["id"] == ch["id"]), 0)
            self.version_idx[ch["id"]] = next((i for i, v in enumerate(ch["versoes"]) if v["id"] == g["id"]), 0)

    def continue_last(self):
        target = self.continue_target()
        if target:
            self.goto_chapter(target[1]["id"], target[2]["id"])

    def rescan(self):
        self.games = catalog.load_games()
        self.installed = steam.installed_apps()
        self._build_chapters()
        self.refresh()

    @property
    def chapter(self):
        return self.chapters[self.sel] if self.chapters else None

    def version_of(self, ch):
        if self.version_idx.get(ch["id"], 0) >= len(ch["versoes"]):   # a versão escolhida saiu (ex.: removida)
            self.version_idx.pop(ch["id"], None)
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
        """Arte da versão; se ela não tiver fundo, usa o da versão Steam do mesmo capítulo.
        Uma print escolhida em "Usar como fundo" vem antes de tudo."""
        if kind == "fundo":
            own = self.cfg.get("_fundos").get(store.art_key(g) or g["id"])
            if own:
                key = ("_fundo_usuario", own)
                if key not in self._pil:
                    try:
                        self._pil[key] = Image.open(own).convert("RGB")
                    except OSError:
                        self._pil[key] = None
                if self._pil[key] is not None:
                    return self._pil[key]
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
                log.exception("falhou: notícias do REVIL")
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
        self.store_info = info  # datas de lançamento (contagem regressiva)
        extras = [v for sec in ("spinoff", "perdidos", "midia", "hqs", "fas", "noticias", "canais") for ch in catalog.load_timeline(self.games, sec)
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
                log.exception("falhou: troféus do appid %s", appid)
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
                log.exception("falhou: DLCs do appid %s", appid)
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

    def _close_request(self):
        """Fechar pelo Windows (X da barra de tarefas, Alt+F4). Com o launcher minimizado ou atrás de outro programa,
        a pergunta abria escondida junto com ele e nada acontecia: aí fecha direto, sem perguntar."""
        if self.state() == "iconic" or self._away or not self._is_front():
            return self.quit_app()
        self.ask_quit()

    def ask_quit(self):
        """O X: pergunta antes de fechar (Cancelar volta para o hub). Uma pergunta por vez."""
        if getattr(self, "_asking_quit", False):
            return
        self._asking_quit = True
        try:
            sair = t.confirm(self, f"Sair do {FR['app']}?", "O hub fecha; os jogos abertos continuam rodando.",
                             ok="Sair", danger=True)
        finally:
            self._asking_quit = False
        if sair:
            self.quit_app()

    def quit_app(self):
        """Fecha de vez. Antes, o Tk era destruído com as threads (capas, troféus, áudio) ainda rodando,
        e uma delas mexendo nele derrubava o Tcl ("alloc: invalid block").
        Com os efeitos ligados, as janelas fecham na hora e o processo só fica vivo o tempo do som de saída
        (data/sons/abertura/sair.mp3). Antes a janela era escondida e esperava: a vigia de foco a reabria minimizada
        e ela ficava travada na área de trabalho."""
        bye = self.prefs["efeitos"] and audio.opening("sair")
        try:
            if getattr(self, "_tplayer", None):
                self._tplayer.close()
            self.music.stop()
            if bye:
                audio.play_file("sair", audio.opening("sair"), 0.9)
            self.destroy()
            if bye:
                time.sleep(2.5)   # sem janela nenhuma: só termina de tocar o som
            ctypes.windll.winmm.mciSendStringW("close all", None, 0, 0)
        finally:
            os._exit(0)

    def go_home(self):
        """Logo do topo: volta para o começo (primeiro capítulo da primeira aba)."""
        self.overlay = None
        self.set_section(SECTIONS[0][0])
        if self.chapters:
            self.select(0)

    def step(self, delta, wrap=False):
        """Setas: anda um capítulo; passando do último (ou do primeiro), vai para a aba seguinte (ou anterior).
        wrap (roda do mouse): não para no fim, segue direto para a aba seguinte."""
        i, now = self.sel + delta, time.time()
        held = not wrap and now - getattr(self, "_last_step", 0) < 0.3  # seta segurada: para no fim; outro toque troca de aba
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

    def _press(self, action):
        """Uma ação do teclado ou do controle. Com uma tela aberta por cima, ela recebe a ação."""
        self._sofa_cancel = True   # modo sofá: qualquer tecla ou botão cancela a abertura automática
        screens = {"profile": "perfil", "story": "historia", "people": "personagens", "deals": "ofertas", "extras": "extras",
                   "map": "mapa", "files": "arquivos", "relations": "relacoes", "virus": "virus", "achievements": "conquistas",
                   "marathon": "maratona", "quiz": "quiz", "search": "busca"}
        if self.overlay and not (self.overlay["kind"] == "viewer" or action not in screens):
            return self.open_overlay(screens[action])  # atalho de outra tela: troca direto
        if self.overlay:
            return self._ov_press("back" if action == "esc" else action)
        keys = self._section_keys()
        if self.nav_focus:   # no menu do topo: A/D (ou setas) trocam a seção, S/seta para baixo volta para os jogos
            if action in ("left", "right", "prev_section", "next_section"):
                d = -1 if action in ("left", "prev_section") else 1
                return self.set_section(keys[(keys.index(self.section) + d) % len(keys)])
            if action in ("down", "enter", "esc", "back"):
                return self._menu_focus(False)
            if action == "up":
                return None
        fn = {"left": lambda: self.step(-1), "right": lambda: self.step(1),
              "up": lambda: self._menu_focus(True), "down": lambda: self.pick_version(1),
              "enter": self.primary_action, "manage": self.manage, "next_section": self.next_section,
              "prev_section": lambda: self.set_section(keys[keys.index(self.section) - 1]),
              "esc": lambda: (self._sound("back"), self.toggle_fullscreen(False)), "back": lambda: self._sound("back"),
              "profile": lambda: self.open_overlay("perfil"), "story": lambda: self.open_overlay("historia"),
              "people": lambda: self.open_overlay("personagens"), "deals": lambda: self.open_overlay("ofertas"),
              "extras": lambda: self.open_overlay("extras"), "photo": self.photo_card,
              **{a: (lambda k=k: self.open_overlay(k)) for a, k in screens.items()},
              "tab_prev": lambda: self.cycle_tab(-1), "tab_next": lambda: self.cycle_tab(1),
              "scroll_up": lambda: self._scroll_panel(-1), "scroll_down": lambda: self._scroll_panel(1),
              "home": self.go_home}.get(action)
        if fn:
            fn()

    def _menu_focus(self, on):
        """W/seta para cima sobe para o menu das seções; S/seta para baixo desce de volta."""
        if self.nav_focus == on:
            return
        self.nav_focus = on
        self._sound("tab" if on else "back")
        self.refresh()

    @staticmethod
    def _section_keys():
        return [k for k, _ in SECTIONS]

    def _scroll_panel(self, d):
        self.panel_scroll = max(0, self.panel_scroll + d)
        self.refresh()

    def _panel_tabs(self):
        if self.game and self.game["tipo"] == "info":
            return (("versoes", "Detalhes"), ("wiki", "Wiki"))
        return (("trofeus", "Troféus"), ("trailer", "Trailer"), ("wiki", "Wiki"), ("prints", "Prints"),
                ("speedrun", "Speedrun"), ("versoes", "Versões"), ("dlcs", "DLCs"))

    def cycle_tab(self, d):
        keys = [k for k, _ in self._panel_tabs()]
        cur = self.panel_tab if self.panel_tab in keys else keys[0]
        self.set_tab(keys[(keys.index(cur) + d) % len(keys)])

    # botão do controle -> ação (Y no visualizador de prints = usar como fundo)
    PAD_ACTIONS = {"left": "left", "right": "right", "up": "up", "down": "down", "a": "enter", "b": "back",
                   "x": "manage", "y": "photo", "lb": "prev_section", "rb": "next_section", "lt": "tab_prev",
                   "rt": "tab_next", "start": "extras", "back": "profile", "rs_up": "scroll_up", "rs_down": "scroll_down",
                   "guide": "home"}

    def _poll_pad(self):
        """Lê o controle. Segurar o botão Xbox/Guide traz o hub de volta mesmo com outro programa na frente."""
        try:
            events = self.pad.poll()
            if self.pad.guide_since and time.time() - self.pad.guide_since > 0.8 and not self._is_front():
                self.pad.guide_since = None
                self.summon()
            elif events and self._is_front() and getattr(self, "splash", None):
                self.splash.press()   # abertura: qualquer botão do controle
            elif events and self._is_front():
                for ev in events:
                    if ev in self.PAD_ACTIONS:
                        self._press(self.PAD_ACTIONS[ev])
        except Exception:
            pass
        self.after(33 if self.pad.connected else 300, self._poll_pad)

    def _is_front(self):
        try:
            fg = ctypes.windll.user32.GetForegroundWindow()
            pid = ctypes.c_ulong()
            ctypes.windll.user32.GetWindowThreadProcessId(fg, ctypes.byref(pid))
            return pid.value == os.getpid()
        except Exception:
            return True

    def summon(self):
        """Traz o hub para a frente em tela cheia (atalho Ctrl+Alt+H ou segurar o botão do controle)."""
        self.deiconify()
        if self._away:
            self._come_back()
        self.attributes("-fullscreen", True)
        self.lift()
        self.focus_force()
        try:
            hwnd = int(self.wm_frame(), 16)
            ctypes.windll.user32.ShowWindow(hwnd, 9)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
        except (ValueError, tk.TclError):
            pass

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
        if self._render_job or self.overlay:  # já vem um redesenho completo (ou o carrossel está escondido)
            pass
        elif moving:
            self._redraw_carousel()
        if active:
            self._kick()

    # ---------- mouse sobre os cards ----------
    def _motion(self, e):
        nav = next((k for k, x1, y1, x2, y2 in getattr(self, "_nav_rects", []) if x1 <= e.x <= x2 and y1 <= e.y <= y2), None)
        pr = self._peek_rect
        if nav is None and pr and pr[0] <= e.x <= pr[2] and pr[1] <= e.y <= pr[3]:
            nav = "canais"   # o mouse desceu para a prévia das lives: ela continua aberta
        if nav != self._nav_hover:   # passou por uma seção do topo: ela abre com o nome (o som é só no clique)
            self._nav_hover = nav
            if not self.overlay:
                self._draw_nav()
        hit = next((i for i, x1, y1, x2, y2 in self._tile_rects if x1 <= e.x <= x2 and y1 <= e.y <= y2), None)
        self._set_hover(hit)
        row = next((r for r in self._row_rects if r[0] <= e.x <= r[2] and r[1] <= e.y <= r[3]), None)
        if row != self._row_hover:  # linha das listas do painel sob o mouse: barrinha de destaque
            self._row_hover = row
            self.c.delete("rowhover")
            if row:
                x1, y1, x2, y2 = row
                self.c.create_rectangle(x1, y1 + 4, x1 + 3, y2 - 4, fill=self.accent, outline="", tags=("rowhover",))
                self.c.create_line(x1 + 10, y2, x2, y2, fill="#38312b", tags=("rowhover",))

    def _set_hover(self, i):
        if i == self._hover:
            return
        self._hover = i   # sem som ao passar o mouse: só cliques e teclas fazem som
        self.c.config(cursor="hand2" if i is not None else "")
        if not self._anim_job:  # começa a animação já, sem esperar o próximo quadro
            self._animate()

    def click_tile(self, i):
        if i == self.sel:  # clique no card que já está aberto: um "pulso" de destaque
            self._grow = 0.55
            self._kick()
        else:
            self.select(i)

    QUIET = ("select", "hover")   # passar de capa em capa e escolher itens de listas não faz som:
                                  # só o menu (seções, telas), as versões e os botões do jogo

    def _tasks_tick(self):
        """Redesenha meio a meio segundo enquanto houver download ou conversão (a barra embaixo do jogo anda)."""
        if self._tasks_job is None and self.tasks:
            def tick():
                self._tasks_job = None
                if self.tasks:
                    self.refresh()
                    self._tasks_tick()
            self._tasks_job = self.after(500, tick)

    def _task(self, g, title=""):
        from .progress import Task
        return Task(self, g["id"] if g else "", title)

    def _sound(self, name, gap=0.05):
        if self.prefs["efeitos"] and name not in self.QUIET:
            audio.effect(name, gap)

    # ---------- música, tela cheia e preferências ----------
    def _queue_music(self):
        """Troca a trilha meio segundo depois de parar num capítulo (não troca a cada capa que passa)."""
        if self._music_job:
            self.after_cancel(self._music_job)
        ch, g = self.chapter, self.game
        audio.set_theme(ch["id"] if ch else None)  # sons de menu do jogo (data/sons/jogos/<capítulo>)
        self._music_job = self.after(500, lambda: self.music.play_chapter(ch, g) if ch else self.music.stop())

    def _save_prefs(self, **values):
        self.prefs.update(values)
        if os.environ.get("REHUB_TESTE"):  # o modo de teste desliga o som so na memoria: nao grava isso
            saved = dict(self.cfg.get("_prefs"), **values)
            self.cfg.set("_prefs", **saved)
            return
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
        if not on:   # fora da tela cheia: maximizada (numa janela pequena os textos e botões se encavalavam)
            self.state("zoomed")
            t.dark_titlebar(self)

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
        self._media_cache.clear()  # prints tiradas durante o jogo
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
        self.order = {"historia": "lancamento", "lancamento": "recentes"}.get(self.order, "historia")
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
        if self.overlay:
            return self._ov_wheel(e.delta)
        x1, y1, x2, y2 = self._panel_box
        if x1 <= e.x_root - self.c.winfo_rootx() <= x2 and y1 <= e.y_root - self.c.winfo_rooty() <= y2:
            self.panel_scroll = max(0, self.panel_scroll + (1 if e.delta < 0 else -1))
            self.refresh()
        else:
            self.step(1 if e.delta < 0 else -1, wrap=True)

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
        self._search_hide()
        self._sync_manage()
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
        self._tile_rects = []
        if self.overlay:  # tela por cima (perfil, história...): o resto da tela principal não é desenhado
            self._live_pill_hide()
            self._draw_overlay(W, H)
            self._draw_toasts(W)
            return
        c.create_image(0, 0, image=self._bg_photo, anchor="nw")

        self._draw_header(W)
        self._draw_bottom_bar(W, H)
        if not self.chapters:
            c.create_text(MARGIN, TILES_Y + 40, anchor="nw", fill=MUTED, font=self.f["h"],
                          text="Nenhum jogo instalado nesta seção. Desligue o filtro 'Só instalados' na barra de baixo."
                          if self.only_installed else
                          "Buscando vídeos e lives dos canais... (Opções > Canais escolhe quais)" if self.section == "canais" else
                          "Nada nesta seção ainda. Os itens vêm de games/_linha_do_tempo.json.")
            return
        self._redraw_carousel()
        self._draw_details()
        self._draw_panel(*panel)
        self._draw_toasts(W)
        c.tag_raise("navitem")

    # ---------- primitivas ----------
    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        r = min(r, 2, (x2 - x1) / 2, (y2 - y1) / 2)   # cantos retos: visual de ficha, nao de capsula
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

    DANGER_ACTIONS = ("DESINSTALAR", "REMOVER")
    ACTION_ICONS = {"JOGAR": "play", "INSTALAR": "down", "BAIXAR": "down", "ACOMPANHAR": "eye", "ABRIR SITE": "link",
                    "GERENCIAR": "gear", "LOJA": "bag", "DESINSTALAR": "trash", "REMOVER": "trash", "EDITAR": "edit",
                    "CONFIGURAR": "gear", "CANAL": "tv", "ASSISTIR AO VIVO": "live", "ASSISTIR NO YOUTUBE": "play",
                    "LER NOTÍCIA": "doc", "PESQUISAR": "eye", "ONDE BAIXAR": "down", "ABRIR NA APP STORE": "link",
                    "BAIXAR APK": "down"}

    def _button(self, x, y, text, cmd, primary, tag):
        """Botao desenhado (skin.py): o principal na cor do capitulo com brilho, os outros em vidro escuro;
        Desinstalar/Remover em vermelho. Com o mouse troca para a versao acesa."""
        c, up = self.c, text.upper()
        style = "primary" if primary else ("danger" if up in self.DANGER_ACTIONS else "plain")
        opts = dict(style=style, accent=self.accent, icon=self.ACTION_ICONS.get(up), height=44, size=12, glow=8,
                    pad=24 if primary else 18)
        normal = skin.button_photo(text, state="normal", **opts)
        hot = lambda: skin.button_photo(text, state="hover", **opts)   # a versao acesa so e desenhada no primeiro hover
        item = c.create_image(x - 8, y - 8, image=normal, anchor="nw", tags=(tag,))
        self._clickable(tag, lambda: (self._sound("prompt_enter" if primary else "enter"), cmd()), hover=[(item, normal, hot)],
                        once=True)
        return x + normal.width() - 16

    def _clickable(self, tag, cmd, shape=None, hover=None, outline=False, once=False):
        """Clique + cursor de mão + reação ao passar o mouse.
        shape: fundo de botão escuro (clareia). hover: [(item, cor normal, cor com o mouse)] para outros itens.

        Cada tag é ligada ao Tk uma vez só; nos redesenhos seguintes só troca a ação guardada.
        (Ligar de novo a cada quadro criava milhares de comandos no Tk e deixava tudo lento.)"""
        changes = list(hover or []) + ([(shape, CHIP, CHIP_HI)] if shape else [])
        self._clicks[tag] = (cmd, changes, outline, once)
        if tag in self._bound:
            return
        self._bound.add(tag)
        c = self.c

        def paint(on):
            entry = self._clicks.get(tag, (None, [], False))
            for item, normal, hi in entry[1]:
                try:
                    if not isinstance(normal, str):   # botao desenhado: troca a imagem (a acesa pode vir de uma funcao)
                        c.itemconfigure(item, image=(hi() if callable(hi) else hi) if on else normal)
                    elif entry[2] and c.type(item) == "rectangle":   # botao de contorno: muda a borda
                        c.itemconfigure(item, outline=hi if on else normal)
                    else:
                        c.itemconfigure(item, fill=hi if on else normal)
                except tk.TclError:  # item de um quadro antigo
                    pass

        def enter(e):
            c.config(cursor="hand2")
            paint(True)

        def leave(e):
            c.config(cursor="")
            paint(False)
        def click(e):
            now = time.time()
            last = self._last_click.get(tag, 0)
            self._last_click[tag] = now
            if self._clicks[tag][3] and now - last < 1.2:   # só nos botões do jogo (Jogar, Instalar...): o primeiro já foi aceito
                self.notify("Um clique ja basta: estou fazendo isso.")
                return
            self._clicks[tag][0]()
        c.tag_bind(tag, "<Button-1>", click)
        c.tag_bind(tag, "<Enter>", enter)
        c.tag_bind(tag, "<Leave>", leave)

    def _canvas_click(self, e):
        """Clique nos cards (pela posição, sem ligar cada card ao Tk a cada quadro)."""
        pr = self._peek_rect
        if pr and pr[0] <= e.x <= pr[2] and pr[1] <= e.y <= pr[3]:
            return   # clique na prévia das lives (por cima dos cards)
        if self.nav_focus:
            self.nav_focus = False
            self.refresh()
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
        """Menu de Opcoes desenhado (cantos suaves, icones, teclas de atalho): abre na hora e fecha com Esc ou clique fora."""
        name = self.chapter["titulo"] if self.chapter else "este capítulo"
        groups = [
            ("Telas", [("Extras", "E", lambda: self.open_overlay("extras"), "grid"),
                       ("Perfil", "P", lambda: self.open_overlay("perfil"), "user"),
                       ("Linha da história", "H", lambda: self.open_overlay("historia"), "timeline"),
                       ("Personagens", "C", lambda: self.open_overlay("personagens"), "users"),
                       ("Ofertas e lançamentos", "L", lambda: self.open_overlay("ofertas"), "tag"),
                       ("Busca", "Ctrl+F", lambda: self.open_overlay("busca"), "eye"),
                       ("Foto do card", "F", self.photo_card, "image")]),
            ("Meus jogos e sites", [("Adicionar jogo ou site", "", self.add_custom, "plus"),
                                    ("Gerenciar e remover", "", self.manage_custom, "edit")]),
            ("Canais", [("Vídeos e lives", "", lambda: (self.set_section("canais"), self.refresh()), "live"),
                        ("Escolher canais do YouTube e Twitch", "", self.channels_menu, "tv")]),
            ("Atualizar", [(f"Procurar versão nova do {FR['app']}", "", self.check_update, "down"),
                           ("Troféus de todos os jogos", "", self.refresh_all_trophies, "trophy"),
                           ("Baixar as artes de novo", "", self.reload_art, "image"),
                           ("Recarregar catálogo e jogos", "F5", self.rescan, "refresh")]),
            ("Música e sons", [(f"Música para {name}", "", self.pick_music, "music"),
                               ("Pasta de músicas", "", lambda: (audio.MUSIC.mkdir(parents=True, exist_ok=True), os.startfile(audio.MUSIC)), "folder")]
             + ([(f"Sons de menu para {name}", "", lambda: os.startfile(audio.theme_folder(self.chapter["id"])), "folder")] if self.chapter else [])
             + [("Fluffy Mod Manager (mods)", "", self.open_fluffy, "puzzle")]),
            ("ISOs", [("Importar lista de links", "", self.import_iso_links, "plus"),
                      ("Baixar todas as ISOs", "", self.download_all_isos, "down"),
                      ("Organizar pasta de ISOs", "", self.organize_isos, "folder"),
                      ("Editar links das ISOs", "", lambda: os.startfile(isodl.ensure_file(self.games)), "doc")]),
            ("Sistema", [("Tela cheia", "F11", self.toggle_fullscreen, "screen"),
                         ("Modo sofá: " + ("ligado" if sofa.enabled() else "desligado"), "", self.toggle_sofa, "screen"),
                         (f"Limite do cache: {self.cache_limit()} GB", "", self.cycle_cache_limit, "refresh"),
                         ("Limpar cache", "", self.clear_cache, "trash"),
                         ("Abrir log de erros", "", self.open_log, "doc"),
                         ("Pasta de dados", "", lambda: (DATA.mkdir(exist_ok=True), os.startfile(DATA)), "folder"),
                         ("Pasta do catálogo", "", lambda: os.startfile(ROOT / "games"), "folder"),
                         ("LEIA-ME", "", lambda: os.startfile(ROOT / "LEIA-ME.md"), "doc"),
                         (f"Sair do {FR['app']}", "", self.ask_quit, "power")]),
        ]
        self._sound("menu_on")
        skin.Menu(self, groups, self.winfo_rootx() + self.winfo_width() - MARGIN, self.winfo_rooty() + self.winfo_height() - 56,
                  self.accent, title="Opções", columns=2, anchor="se", width=310, on_close=lambda: self._sound("menu_off"))

    # ---------- aviso rapido (toast) ----------
    def notify(self, text, secs=3.0):
        """Aviso curto embaixo da tela (ex.: 'Abrindo o jogo...'): some sozinho, nao bloqueia nada."""
        lab = getattr(self, "_toast_lbl", None)
        if lab is None or not lab.winfo_exists():
            box = tk.Frame(self, bg=self.accent)
            lab = tk.Label(box, bg=t.PANEL, fg=WHITE, font=(t.FONT, 12), padx=22, pady=10)
            lab.pack(padx=(4, 0))
            self._toast_lbl, self._toast_box = lab, box
        lab.config(text=text)
        self._toast_box.config(bg=self.accent)
        self._toast_box.place(relx=0.5, rely=1.0, y=-96, anchor="s")
        self._toast_box.lift()
        if getattr(self, "_toast_job", None):
            self.after_cancel(self._toast_job)
        self._toast_job = self.after(int(secs * 1000), self._toast_box.place_forget)



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
    logmod.setup()
    if sofa.started_by_windows() and not _pad_soon():
        return   # modo sofá sem controle ligado: o PC foi ligado para outra coisa, o launcher não aparece
    Hub().mainloop()


def _pad_soon(seconds=12):
    """Espera um controle aparecer (o Windows demora para ligar o Bluetooth/receptor depois do login)."""
    pad = gamepad.Pad()
    end = time.time() + seconds
    while time.time() < end:
        pad.poll()
        if pad.connected:
            return True
        time.sleep(0.5)
    return False
