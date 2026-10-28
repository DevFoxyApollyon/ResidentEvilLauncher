"""Janela "Gerenciar" de um jogo: situação do jogo, mods pelo Fluffy Mod Manager e projetos da comunidade.

No topo, a arte do jogo com o título e as ações principais; embaixo, abas (Instalação e Mods).
"""
import os
import tkinter as tk
import webbrowser
from tkinter import filedialog

from PIL import Image, ImageDraw, ImageTk

from .. import fluffy, github, isodl, launcher, sources, steam, store
from ..mods import ModManager
from . import skin, theme as t

CARD = t.PANEL
SOFT = "#9a9186"
PAD = 36
HERO_H = 210
TABS = [("instalar", "Instalação"), ("mods", "Mods")]


def hero_image(path, w, h):
    """A arte à direita, sumindo no fundo da janela para a esquerda e para baixo (onde ficam os textos)."""
    bg = Image.new("RGB", (w, h), t.BG)
    if not path:
        return bg
    try:
        art = Image.open(path).convert("RGB")
    except OSError:
        return bg
    aw = int(w * 0.62)
    scale = max(aw / art.width, h / art.height)
    art = art.resize((max(1, int(art.width * scale)), max(1, int(art.height * scale))), Image.LANCZOS)
    left, top = (art.width - aw) // 2, max(0, (art.height - h) // 3)
    art = art.crop((left, top, left + aw, top + h))
    mask = Image.new("L", (aw, h), 0)
    d = ImageDraw.Draw(mask)
    for x in range(aw):   # da esquerda (some) para a direita (aparece)
        k = min(1.0, x / (aw * 0.55))
        d.line([(x, 0), (x, h)], fill=int(200 * k * k))
    fade = Image.new("L", (aw, h), 255)
    fd = ImageDraw.Draw(fade)
    for y in range(h - 80, h):   # embaixo some no fundo, emendando com a barra de ações
        fd.line([(0, y), (aw, y)], fill=int(255 * (h - y) / 80))
    mask = Image.composite(mask, Image.new("L", (aw, h), 0), fade)
    bg.paste(art, (w - aw, 0), mask)
    return bg


class ManageWindow(tk.Toplevel):
    def __init__(self, hub, game):
        super().__init__(hub)
        self.hub, self.g = hub, game
        self.title(f"Gerenciar — {game['nome']}")
        w, h = 960, min(780, hub.winfo_screenheight() - 80)
        on_screen = hub.winfo_viewable() and hub.winfo_width() > 200
        ax, ay, aw, ah = ((hub.winfo_rootx(), hub.winfo_rooty(), hub.winfo_width(), hub.winfo_height()) if on_screen else
                          (0, 0, hub.winfo_screenwidth(), hub.winfo_screenheight()))
        self.geometry(f"{w}x{h}+{ax + (aw - w) // 2}+{ay + max(0, (ah - h) // 2)}")   # no meio do hub
        self.minsize(820, 600)
        # sem a barra de título do Windows: fecha no X desenhado no canto ou com Esc
        self.overrideredirect(True)
        self.bind("<Escape>", lambda e: self.destroy())
        self.configure(bg=t.BG, highlightthickness=1, highlightbackground=t.LINE)
        self.transient(hub)
        self.bind("<Destroy>", lambda e: e.widget is self and hub._sound("prompt_back"))
        self.tab = "instalar"
        self._hero_key, self._hero_photo = None, None

        tk.Frame(self, bg=t.RED, height=3).pack(fill="x")
        self.hero = tk.Canvas(self, height=HERO_H, bg=t.BG, highlightthickness=0)
        self.hero.pack(fill="x")
        self.hero.bind("<Configure>", lambda e: self._draw_hero())
        self.actions = tk.Frame(self, bg=t.BG)
        self.actions.pack(fill="x", padx=PAD, pady=(0, 18))
        self.tabbar = tk.Frame(self, bg=t.BG)
        self.tabbar.pack(fill="x", padx=PAD)
        tk.Frame(self, bg=t.LINE, height=1).pack(fill="x", padx=PAD)
        self.body = t.ScrollFrame(self)
        self.body.pack(fill="both", expand=True, padx=(PAD, 14), pady=(6, 18))
        self.refresh()
        t.own(self, hub)   # por cima só do launcher (sem barra de título ela não tinha dona)
        self.lift()
        self.focus_force()  # na frente da tela cheia

    @property
    def page(self):
        return self.body.inner

    # ---------- montagem ----------
    def refresh(self):
        self.gdir = launcher.game_dir(self.g, self.hub.cfg, self.hub.installed)
        self.ready = bool(self.gdir and self.gdir.is_dir())
        self._draw_hero()
        self._actions()
        self._tabs()
        self.body.clear()
        if self.tab == "mods":
            self._fluffy_section()
            if fluffy.old_mods(self.g["id"]):
                self._old_mods_section()
        else:
            self._steps_section()
            if isodl.needs_iso(self.g) and self.g["tipo"] != "steam":
                self._iso_section()
            if self.g.get("github"):
                self._project_download()
            self._sources_section()
        tk.Frame(self.page, bg=t.BG, height=12).pack(fill="x")

    def _draw_hero(self):
        c, g = self.hero, self.g
        w = max(c.winfo_width(), 400)
        key = store.art_key(g)
        path = store.art_path(key, "fundo") or store.art_path(key, "capa")
        if (w, path) != self._hero_key:
            self._hero_key = (w, path)
            self._hero_photo = ImageTk.PhotoImage(hero_image(path, w, HERO_H))
        c.delete("all")
        c.create_image(0, 0, image=self._hero_photo, anchor="nw")
        logo = t.umbrella(18)
        if logo:
            c.create_image(PAD, 34, image=logo, anchor="w")
        c.create_text(PAD + (26 if logo else 0), 34, text="GERENCIAR", anchor="w", fill=t.MUTED, font=(t.FONT, 9, "bold"))
        # o X no lugar da barra de título (Esc também fecha)
        cx = w - PAD - 2   # botão redondo escuro: lê bem mesmo em cima da parte clara da arte
        c.create_oval(cx - 18, 16, cx + 18, 52, fill="#141210", outline="#3b342d", tags=("close",))
        x_btn = c.create_image(cx, 34, image=skin.icon_photo("x", 16, t.MUTED), tags=("close",))
        c.create_image(cx - 28, 34, image=skin.keycap_photo("Esc"), anchor="e", tags=("close",))
        c.tag_bind("close", "<Button-1>", lambda e: self.destroy())
        c.tag_bind("close", "<Enter>", lambda e: (c.itemconfigure(x_btn, image=skin.icon_photo("x", 16, t.TEXT)),
                                                  c.config(cursor="hand2")))
        c.tag_bind("close", "<Leave>", lambda e: (c.itemconfigure(x_btn, image=skin.icon_photo("x", 16, t.MUTED)),
                                                  c.config(cursor="")))
        y = 74
        if g.get("versao"):
            c.create_text(PAD, y, text=g["versao"].upper(), anchor="w", fill=t.RED, font=(t.FONT, 9, "bold"))
            y += 14
        title = c.create_text(PAD, y, text=g["nome"], anchor="nw", fill=t.TEXT, font=(t.FONT, 24 if len(g["nome"]) < 34 else 20, "bold"),
                              width=int(w * 0.58))
        y = c.bbox(title)[3] + 12
        color = t.GREEN if self.ready else "#b0554b"
        c.create_oval(PAD, y + 3, PAD + 9, y + 12, fill=color, outline="")
        status = c.create_text(PAD + 17, y + 7, anchor="w", fill=t.TEXT, font=(t.FONT, 10, "bold"),
                               text="Instalado" if self.ready else "Não instalado")
        where = (str(self.gdir) if self.ready else
                 "Instale pela Steam." if g["tipo"] == "steam" else "Use Instalar na tela principal ou Baixar abaixo.")
        c.create_text(c.bbox(status)[2] + 14, y + 7, anchor="w", fill=t.MUTED, font=(t.FONT, 9), text=where,
                      width=int(w * 0.5))

    def _actions(self):
        for w in self.actions.winfo_children():
            w.destroy()
        g = self.g

        def add(text, cmd, style="plain"):
            t.flat_button(self.actions, text, cmd, style).pack(side="left", padx=(0, 8))
        if g["tipo"] == "steam":
            if not self.ready:
                add("Instalar pela Steam", lambda: steam.install(g["appid"]), "primary")
            add("Loja", lambda: steam.store(g["appid"]))
        elif not g.get("andamento"):
            add("Configurar", self._choose_exe, "plain" if self.hub.cfg.get(g["id"]).get("exe") else "primary")
        if self.ready:
            add("Abrir pasta", lambda: os.startfile(self.gdir))
        if self.ready or (g["tipo"] != "steam" and self.hub.cfg.get(g["id"])):
            add("Desinstalar", self._uninstall_game, "danger")
        self.busy = tk.Label(self.actions, text=getattr(self, "_busy_text", ""), fg=t.GREEN, bg=t.BG, font=(t.FONT, 9, "bold"))
        self.busy.pack(side="right")

    def _tabs(self):
        for w in self.tabbar.winfo_children():
            w.destroy()
        for key, text in TABS:
            on = key == self.tab
            col = tk.Frame(self.tabbar, bg=t.BG, cursor="hand2")
            col.pack(side="left", padx=(0, 26))
            lab = tk.Label(col, text=text.upper(), fg=t.TEXT if on else t.MUTED, bg=t.BG, font=(t.FONT, 10, "bold"))
            lab.pack(pady=(0, 8))
            tk.Frame(col, bg=t.RED if on else t.BG, height=3).pack(fill="x")
            for wdg in (col, lab):
                wdg.bind("<Button-1>", lambda e, k=key: self._set_tab(k))
                if not on:
                    wdg.bind("<Enter>", lambda e, l=lab: l.config(fg=t.TEXT))
                    wdg.bind("<Leave>", lambda e, l=lab: l.config(fg=t.MUTED))

    def _set_tab(self, key):
        if key != self.tab:
            self.hub._sound("tab")
            self.tab = key
            self.refresh()

    def _section(self, title, hint=None):
        t.section_title(self.page, title, bg=t.BG, color=t.TEXT).pack(fill="x", pady=(24, 6))
        if hint:
            t.label(self.page, hint, 9, fg=t.MUTED, bg=t.BG, wraplength=780).pack(fill="x", pady=(0, 8))

    def _card(self, title, lines, actions=()):
        """lines: [(texto, cor)]. actions: [(texto, comando, 'primary'|'plain'|'danger')]."""
        card = tk.Frame(self.page, bg=CARD)
        card.pack(fill="x", pady=4)
        tk.Frame(card, bg=t.RED if any(s == "primary" for _, _, s in actions) else CARD, width=3).pack(side="left", fill="y")
        btns = tk.Frame(card, bg=CARD)
        btns.pack(side="right", padx=18, pady=14)
        for text, cmd, style in actions:
            t.flat_button(btns, text, cmd, style, height=32, size=9).pack(side="left", padx=(8, 0))
        info = tk.Frame(card, bg=CARD)
        info.pack(side="left", fill="x", expand=True, padx=16, pady=14)
        t.label(info, title, 11, bold=True, bg=CARD).pack(fill="x")
        for text, color in lines:
            if text:
                t.label(info, text, 9, fg=color, bg=CARD, wraplength=440).pack(fill="x", pady=(3, 0))

    # ---------- mods pelo Fluffy Mod Manager ----------
    def _fluffy_section(self):
        g = self.g
        if not fluffy.supported(g["id"]):
            self._links_only()
            return
        self._section("Mods — Fluffy Mod Manager", "Os mods agora são instalados pelo Fluffy Mod Manager: ele ativa, "
                      "desativa, mostra conflitos e faz backup sozinho. Coloque o .zip ou .rar do mod na pasta de mods "
                      "do jogo (botão abaixo) e ative no Fluffy.")
        if not fluffy.installed():
            self._card("Fluffy Mod Manager", [("Não baixado", t.MUTED), ("Gratuito, de FluffyQuack (fluffyquack.com).", SOFT)],
                       [("Baixar", self._download_fluffy, "primary"), ("Site", lambda: webbrowser.open(fluffy.SITE), "plain")])
            return
        code = fluffy.CODES.get(g["id"])
        chosen = self._chosen()
        self._card("Fluffy Mod Manager", [(f"Instalado  ·  {fluffy.version() or 'versão ?'}", t.GREEN),
                                          ("Na primeira vez, escolha o jogo no Fluffy e confira se ele achou a pasta da Steam.",
                                           SOFT)],
                   [("Abrir Fluffy", self._open_fluffy, "primary"), ("Atualizar", self._download_fluffy, "plain")])
        folder_note = (f"Games\\{code}\\Mods" if code else chosen or
                       "Escolha o jogo no Fluffy uma vez (ele cria a pasta) e depois indique a pasta Mods dele aqui")
        self._card("Mods deste jogo", [(folder_note, t.MUTED),
                                      ("Aceita .zip, .rar, .7z ou pasta. Depois é só ativar no Fluffy.", SOFT)],
                   [("+ Adicionar mod", self._add_mod, "primary"),
                    ("Abrir pasta de mods", lambda: fluffy.open_folder(fluffy.mods_dir(g["id"], self._chosen())), "plain")]
                   + ([] if code else [("Indicar pasta", self._pick_mods_dir, "plain")]))
        if g["id"] in fluffy.RE_ENGINE:
            self._card("REFramework (nightly)", [("Base para scripts e muitos mods. A versão nightly acompanha as "
                                                  "atualizações do jogo (a estável, de 2025, trava nos jogos atualizados).",
                                                  SOFT)],
                       [("Pôr no Fluffy", self._add_reframework, "plain"),
                        ("GitHub", lambda: webbrowser.open("https://github.com/praydog/REFramework-nightly/releases"), "plain")])
        self._links()

    def _links_only(self):
        self._section("Mods", "O Fluffy Mod Manager não tem suporte para este jogo. Estes sites têm mods e as instruções "
                              "de cada um.")
        if not self._links():
            t.label(self.page, "Nenhum site de mods cadastrado para este jogo.", 10, fg=t.MUTED, bg=t.BG).pack(fill="x")

    def _links(self):
        g = self.g
        links = [s for s in g.get("sugestoes", []) if s.get("url")]
        if g.get("nexus"):
            links.insert(0, {"nome": "Nexus Mods", "url": f"https://www.nexusmods.com/{g['nexus']}/mods/",
                             "descricao": "O maior site de mods. Baixe o arquivo e use + Adicionar mod."})
        for s in links:
            self._card(f"Onde achar mods: {s['nome']}", [(s.get("descricao", ""), SOFT)],
                       [("Abrir página", lambda u=s["url"]: webbrowser.open(u), "plain")])
        return bool(links)

    def _old_mods_section(self):
        names = fluffy.old_mods(self.g["id"])
        self._section("Mods do sistema antigo", "Estes mods foram ativados pelo app antes da troca para o Fluffy e "
                                                "continuam no jogo. Se quiser, o app desfaz e devolve os arquivos originais.")
        self._card(f"{len(names)} mod(s) ativo(s)", [(n, t.MUTED) for n in names],
                   [("Desfazer e devolver originais", self._undo_old_mods, "danger")])

    def _iso_section(self):
        g = self.g
        iso = self.hub.cfg.get(g["id"]).get("iso")
        link = isodl.link_for(g)
        self._section("ISO do jogo", "Os links ficam em data/isos.json, só neste PC (o instalador do hub não leva). "
                                     "Link direto, MediaFire ou Google Drive.")
        opts = [v for v in isodl.VARIANTS if v in link] + [v for v in link if v not in isodl.VARIANTS]
        actions = [(f"Baixar {v}", lambda v=v: self.hub.download_iso(g, self._done, variant=v), "plain") for v in opts]
        bad = isodl.bad_image(iso, g) if iso else None
        actions.insert(0, ("Editar local da ISO", self._change_iso, "primary" if bad or not iso else "plain"))
        if iso and not bad:
            actions.insert(1, ("Abrir pasta", lambda: os.startfile(os.path.dirname(iso)), "plain"))
        actions.append(("Editar links", lambda: os.startfile(isodl.ensure_file(self.hub.games)), "plain"))   # de onde baixa
        self._card(os.path.basename(iso) if iso else "Nenhuma ISO escolhida",
                   [(iso or "Escolha em Configurar, baixe pelo link ou use Opções > Organizar ISOs.",
                     "#e0857f" if bad else t.GREEN if iso else t.MUTED),
                    (bad.split("\n")[0] if bad else "", "#e0857f"),
                    ("Links: " + ", ".join(opts) if opts else "Sem link para este jogo em data/isos.json", SOFT)], actions)

    def _project_download(self):
        g = self.g
        exists = launcher.download_dir(g).exists()
        self._section("Port de PC")
        self._card(g["github"], [("Já baixado: Atualizar pega a release mais nova sem apagar saves nem assets."
                                  if exists else "Baixa a release mais nova do GitHub para a pasta do hub.", SOFT)],
                   [("Atualizar" if exists else "Baixar", self._download_game, "plain" if exists else "primary"),
                    ("GitHub", lambda: webbrowser.open(f"https://github.com/{g['github']}"), "plain")])

    def _steps_section(self):
        """Como instalar e jogar esta versão, passo a passo (cada tipo de versão tem o seu caminho)."""
        steps = sources.steps(self.g)
        if not steps:
            return
        self._section("Como instalar")
        box = tk.Frame(self.page, bg=CARD)
        box.pack(fill="x", pady=4)
        for k, text in enumerate(steps, 1):
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", padx=18, pady=(16 if k == 1 else 6, 16 if k == len(steps) else 6))
            num = tk.Canvas(row, width=26, height=26, bg=CARD, highlightthickness=0)
            num.create_oval(1, 1, 25, 25, fill=t.RED_DARK, outline="")
            num.create_text(13, 13, text=str(k), fill=t.TEXT, font=(t.FONT, 10, "bold"))
            num.pack(side="left", anchor="n", padx=(0, 14))
            t.label(row, text, 10, fg=t.TEXT, bg=CARD, wraplength=700).pack(side="left", fill="x", expand=True, pady=(3, 0))

    def _sources_section(self):
        """Onde conseguir esta versão: loja oficial, GitHub do port, projeto ou emulador indicado."""
        src = sources.sources(self.g)
        if not src:
            return
        self._section("Onde baixar", "De onde vem esta versão. O hub nunca traz o jogo: compre na loja ou use a sua cópia.")
        box = tk.Frame(self.page, bg=CARD)
        box.pack(fill="x", pady=4)
        for k, (name, url, detail) in enumerate(src):
            if k:
                tk.Frame(box, bg=t.LINE, height=1).pack(fill="x", padx=18)
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", padx=18, pady=12)
            t.flat_button(row, "Abrir", lambda u=url: webbrowser.open(u), "plain", height=30, size=9).pack(side="right")
            info = tk.Frame(row, bg=CARD)
            info.pack(side="left", fill="x", expand=True)
            t.label(info, name, 10, bold=True, bg=CARD).pack(fill="x")
            t.label(info, url.replace("https://", "") + (f"  ·  {detail}" if detail else ""), 9, fg=t.MUTED, bg=CARD,
                    wraplength=620).pack(fill="x", pady=(2, 0))

    # ---------- ações ----------
    def _open_fluffy(self):
        self.hub._sound("prompt_enter")
        fluffy.open_manager()

    def _download_fluffy(self):
        self._run(fluffy.download, "Baixando o Fluffy Mod Manager...",
                  ("Fluffy Mod Manager pronto", "Use Abrir Fluffy. Na primeira vez, escolha o jogo na lista dele."))

    def _chosen(self):
        return self.hub.cfg.get(self.g["id"]).get("fluffy_mods")

    def _pick_mods_dir(self):
        """Jogos sem código conhecido: o usuário indica a pasta Mods que o Fluffy criou (fica guardada)."""
        start = fluffy.HOME / "Games"
        start.mkdir(parents=True, exist_ok=True)
        d = filedialog.askdirectory(parent=self, initialdir=str(start),
                                    title=f"Pasta Mods de {self.g['nome']} no Fluffy (Games > jogo > Mods)")
        if d:
            self.hub.cfg.set(self.g["id"], fluffy_mods=d)
            self.refresh()
        return d

    def _add_mod(self):
        if not fluffy.CODES.get(self.g["id"]) and not self._chosen() and not self._pick_mods_dir():
            return
        path = filedialog.askopenfilename(parent=self, title="Escolha o mod (.zip, .rar ou .7z)", filetypes=github.FILETYPES)
        if path:
            self._run(lambda: fluffy.add_mod(self.g["id"], path, self._chosen()), "Copiando para o Fluffy...",
                      ("Mod na pasta do Fluffy", "Abra o Fluffy e ative o mod na lista do jogo."))

    def _add_reframework(self):
        self._run(lambda: fluffy.add_reframework(self.g["id"]), "Baixando o REFramework nightly...",
                  ("REFramework na pasta do Fluffy", "Abra o Fluffy e ative o REFramework na lista do jogo."))

    def _undo_old_mods(self):
        if t.confirm(self, "Desfazer os mods antigos?", "Os arquivos que eles substituíram no jogo voltam ao original.",
                     ["Depois, se quiser o mod de novo, instale pelo Fluffy."], ok="Desfazer", danger=True):
            def work():
                mm = ModManager(self.g["id"], self.gdir)
                for mod_id in list(mm.state["ativos"]):
                    mm.disable(mod_id)
            self._run(work, "Desfazendo...", ("Pronto", "O jogo voltou aos arquivos originais."))

    def _uninstall_game(self):
        self.hub.uninstall_game(self.g, parent=self)
        self.refresh()

    def _change_iso(self):
        """A lista das imagens do jogo achadas no PC (dentro do launcher); a escolhida é movida para
        data/isos/<jogo>/ com o nome dela (um .chd que a versão não abre é convertido)."""
        if self.hub.ask_iso(self.g, parent=self, adopt=True):
            self.after(800, lambda: self.winfo_exists() and self.refresh())

    def _choose_exe(self):
        if self.hub.configure_local(self.g, parent=self):
            self.refresh()

    def _download_game(self):
        self._working("Baixando...")
        self.hub.download_game(self.g, on_done=lambda: self._done())

    def _working(self, text):
        self._busy_text = text
        self.busy.config(text=text)

    def _done(self, title=None, msg=None):
        self._working("")
        if title:
            self.hub._sound("prompt_enter")
            t.notice(self, title, msg or "")
        self.refresh()
        self.hub.refresh()

    def _fail(self, msg):
        self._working("")
        t.notice(self, "Não deu certo", msg, error=True)
        self.refresh()

    def _run(self, work, busy, msg=None):
        self._working(busy)
        t.in_background(self, work, lambda _: self._done(*(msg or (None, None))), self._fail)
