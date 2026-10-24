"""Janela "Gerenciar" de um jogo: situação do jogo, mods pelo Fluffy Mod Manager e projetos da comunidade."""
import os
import tkinter as tk
import webbrowser
from tkinter import filedialog

from PIL import Image, ImageTk

from .. import fluffy, github, launcher, sources, steam, store
from ..mods import ModManager
from . import theme as t

CARD = t.PANEL


class ManageWindow(tk.Toplevel):
    def __init__(self, hub, game):
        super().__init__(hub)
        self.hub, self.g = hub, game
        self.title(f"Gerenciar — {game['nome']}")
        self.geometry("860x720")
        self.minsize(760, 560)
        self.configure(bg=t.BG)
        self.transient(hub)
        self.bind("<Destroy>", lambda e: e.widget is self and hub._sound("prompt_back"))
        self._cover = None

        tk.Frame(self, bg=t.RED, height=3).pack(fill="x")
        t.brand_row(self, t.BG, t.MUTED, "Gerenciar").pack(anchor="w", padx=26, pady=(14, 0))
        self.head = tk.Frame(self, bg=t.BG)
        self.head.pack(fill="x", padx=26, pady=(20, 4))
        self.busy = tk.Label(self, text="", fg=t.GREEN, bg=t.BG, font=(t.FONT, 9))
        self.busy.pack(anchor="w", padx=24)
        self.body = t.ScrollFrame(self)
        self.body.pack(fill="both", expand=True, padx=(26, 10), pady=(4, 18))
        self.refresh()
        self.lift()
        self.focus_force()  # na frente da tela cheia
        self.attributes("-topmost", True)
        self.after(300, lambda: self.winfo_exists() and self.attributes("-topmost", False))

    # ---------- montagem ----------
    def refresh(self):
        self.gdir = launcher.game_dir(self.g, self.hub.cfg, self.hub.installed)
        self._header()
        self.body.clear()
        self._steps_section()
        self._sources_section()
        if self.g.get("github"):
            self._project_download()
        self._fluffy_section()
        if fluffy.old_mods(self.g["id"]):
            self._old_mods_section()


    def _header(self):
        for w in self.head.winfo_children():
            w.destroy()
        g = self.g
        p = store.art_path(store.art_key(g), "capa")
        if p:
            try:
                img = Image.open(p).convert("RGB")
                img.thumbnail((96, 144), Image.LANCZOS)
                self._cover = ImageTk.PhotoImage(img)
                tk.Label(self.head, image=self._cover, bg=t.BG, highlightthickness=1,
                         highlightbackground=t.LINE).pack(side="left", anchor="n", padx=(0, 20))
            except OSError:
                pass
        info = tk.Frame(self.head, bg=t.BG)
        info.pack(side="left", fill="both", expand=True)
        tk.Label(info, text=(g.get("versão") or "").upper(), fg=t.RED, bg=t.BG, font=(t.FONT, 9, "bold"),
                 anchor="w").pack(fill="x")
        t.label(info, g["nome"], 19, bold=True, bg=t.BG, wraplength=600).pack(fill="x", pady=(2, 0))
        ready = bool(self.gdir and self.gdir.is_dir())
        row = tk.Frame(info, bg=t.BG)
        row.pack(fill="x", pady=(8, 2))
        dot = tk.Canvas(row, width=10, height=10, bg=t.BG, highlightthickness=0)
        dot.create_rectangle(1, 1, 9, 9, fill=t.GREEN if ready else "#8a4a44", outline="")
        dot.pack(side="left", padx=(0, 8))
        t.label(row, "Instalado" if ready else "Não instalado", 10, fg=t.TEXT, bg=t.BG).pack(side="left")
        where = str(self.gdir) if ready else ("Instale pela Steam." if g["tipo"] == "steam" else "Use Instalar na tela principal.")
        t.label(info, where, 9, fg=t.MUTED, bg=t.BG, wraplength=600).pack(fill="x")
        btns = tk.Frame(info, bg=t.BG)
        btns.pack(fill="x", pady=(12, 0))

        def add(text, cmd, style="plain"):
            t.flat_button(btns, text, cmd, style).pack(side="left", padx=(0, 8))
        if ready:
            add("Abrir pasta do jogo", lambda: os.startfile(self.gdir))
        if g["tipo"] == "steam":
            if not ready:
                add("Instalar pela Steam", lambda: steam.install(g["appid"]), "primary")
            add("Loja", lambda: steam.store(g["appid"]))
        elif not g.get("andamento"):
            add("Configurar", self._choose_exe, "primary" if not self.hub.cfg.get(g["id"]).get("exe") else "plain")
        if ready or (g["tipo"] != "steam" and self.hub.cfg.get(g["id"])):
            add("Desinstalar", self._uninstall_game, "danger")

    def _section(self, title, hint=None):
        top = tk.Frame(self.body.inner, bg=t.BG)
        top.pack(fill="x", pady=(20, 4))
        tk.Label(top, text=title.upper(), fg=t.TEXT, bg=t.BG, font=(t.FONT, 11, "bold")).pack(side="left")
        tk.Frame(top, bg=t.LINE, height=1).pack(side="left", fill="x", expand=True, padx=(12, 0), pady=(4, 0))
        if hint:
            t.label(self.body.inner, hint, 9, fg=t.MUTED, bg=t.BG, wraplength=760).pack(fill="x", pady=(0, 8))

    def _card(self, title, lines, actions=()):
        """lines: [(texto, cor)]. actions: [(texto, comando, 'primary'|'plain'|'danger')]."""
        card = tk.Frame(self.body.inner, bg=CARD, highlightthickness=1, highlightbackground=t.LINE)
        card.pack(fill="x", pady=4)
        tk.Frame(card, bg=t.RED if any(s == "primary" for _, _, s in actions) else t.LINE, width=3).pack(side="left", fill="y")
        btns = tk.Frame(card, bg=CARD)
        btns.pack(side="right", padx=14, pady=12)
        for text, cmd, style in actions:
            t.flat_button(btns, text, cmd, style).pack(side="left", padx=(6, 0))
        info = tk.Frame(card, bg=CARD)
        info.pack(side="left", fill="x", expand=True, padx=14, pady=12)
        t.label(info, title, 11, bold=True, bg=CARD).pack(fill="x")
        for text, color in lines:
            if text:
                t.label(info, text, 9, fg=color, bg=CARD, wraplength=400).pack(fill="x", pady=(2, 0))

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
            self._card("Fluffy Mod Manager", [("Não baixado", t.MUTED), ("Gratuito, de FluffyQuack (fluffyquack.com).", "#9a9186")],
                       [("Baixar", self._download_fluffy, "primary"), ("Site", lambda: webbrowser.open(fluffy.SITE), "plain")])
            return
        code = fluffy.CODES.get(g["id"])
        chosen = self._chosen()
        self._card("Fluffy Mod Manager", [(f"Instalado  ·  {fluffy.version() or 'versão ?'}", t.GREEN),
                                          ("Na primeira vez, escolha o jogo no Fluffy e confira se ele achou a pasta da Steam.",
                                           "#9a9186")],
                   [("Abrir Fluffy", self._open_fluffy, "primary"), ("Atualizar", self._download_fluffy, "plain")])
        folder_note = (f"Games\\{code}\\Mods" if code else chosen or
                       "Escolha o jogo no Fluffy uma vez (ele cria a pasta) e depois indique a pasta Mods dele aqui")
        self._card("Mods deste jogo", [(folder_note, t.MUTED),
                                      ("Aceita .zip, .rar, .7z ou pasta. Depois é só ativar no Fluffy.", "#9a9186")],
                   [("+ Adicionar mod", self._add_mod, "primary"),
                    ("Abrir pasta de mods", lambda: fluffy.open_folder(fluffy.mods_dir(g["id"], self._chosen())), "plain")]
                   + ([] if code else [("Indicar pasta", self._pick_mods_dir, "plain")]))
        if g["id"] in fluffy.RE_ENGINE:
            self._card("REFramework (nightly)", [("Base para scripts e muitos mods. A versão nightly acompanha as "
                                                  "atualizações do jogo (a estável, de 2025, trava nos jogos atualizados).",
                                                  "#9a9186")],
                       [("Pôr no Fluffy", self._add_reframework, "plain"),
                        ("GitHub", lambda: webbrowser.open("https://github.com/praydog/REFramework-nightly/releases"), "plain")])
        self._links()

    def _links_only(self):
        self._section("Mods", "O Fluffy Mod Manager não tem suporte para este jogo. Estes sites têm mods e as instruções "
                              "de cada um.")
        if not self._links():
            t.label(self.body.inner, "Nenhum site de mods cadastrado para este jogo.", 10, fg=t.MUTED, bg=t.BG).pack(fill="x")

    def _links(self):
        g = self.g
        links = [s for s in g.get("sugestoes", []) if s.get("url")]
        if g.get("nexus"):
            links.insert(0, {"nome": "Nexus Mods", "url": f"https://www.nexusmods.com/{g['nexus']}/mods/",
                             "descricao": "O maior site de mods. Baixe o arquivo e use + Adicionar mod."})
        for s in links:
            self._card(f"Onde achar mods: {s['nome']}", [(s.get("descricao", ""), "#9a9186")],
                       [("Abrir página", lambda u=s["url"]: webbrowser.open(u), "plain")])
        return bool(links)

    def _old_mods_section(self):
        names = fluffy.old_mods(self.g["id"])
        self._section("Mods do sistema antigo", "Estes mods foram ativados pelo app antes da troca para o Fluffy e "
                                                "continuam no jogo. Se quiser, o app desfaz e devolve os arquivos originais.")
        self._card(f"{len(names)} mod(s) ativo(s)", [(n, t.MUTED) for n in names],
                   [("Desfazer e devolver originais", self._undo_old_mods, "danger")])

    def _project_download(self):
        g = self.g
        self._section("Projeto")
        exists = launcher.download_dir(g).exists()
        self._card(f"{'Atualizar' if exists else 'Baixar'} o projeto",
                   [(f"github.com/{g['github']}  ·  não apaga saves nem assets já colocados", t.MUTED)],
                   [("Atualizar" if exists else "Baixar", self._download_game, "plain" if exists else "primary"),
                    ("GitHub", lambda: webbrowser.open(f"https://github.com/{g['github']}"), "plain")])

    def _steps_section(self):
        """Como instalar e jogar esta versão, passo a passo (cada tipo de versão tem o seu caminho)."""
        steps = sources.steps(self.g)
        if not steps:
            return
        self._section("Como instalar")
        box = tk.Frame(self.body.inner, bg=CARD, highlightthickness=1, highlightbackground=t.LINE)
        box.pack(fill="x", pady=4)
        for k, text in enumerate(steps, 1):
            row = tk.Frame(box, bg=CARD)
            row.pack(fill="x", padx=14, pady=(10 if k == 1 else 3, 10 if k == len(steps) else 3))
            tk.Label(row, text=f"{k:02d}", fg=t.RED, bg=CARD, font=(t.FONT, 11, "bold"), width=3, anchor="nw").pack(side="left", anchor="n")
            t.label(row, text, 10, fg=t.TEXT, bg=CARD, wraplength=640).pack(side="left", fill="x", expand=True)

    def _sources_section(self):
        """Onde conseguir esta versão: loja oficial, GitHub do port, projeto ou emulador indicado."""
        src = sources.sources(self.g)
        if not src:
            return
        self._section("Onde baixar", "De onde vem esta versão. O hub nunca traz o jogo: compre na loja ou use a sua cópia.")
        for name, url, detail in src:
            self._card(name, [(url.replace("https://", ""), t.MUTED)] + ([(detail, "#9a9186")] if detail else []),
                       [("Abrir", lambda u=url: webbrowser.open(u), "plain")])

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

    def _choose_exe(self):
        if self.hub.configure_local(self.g, parent=self):
            self.refresh()

    def _download_game(self):
        self._working("Baixando...")
        self.hub.download_game(self.g, on_done=lambda: self._done())

    def _working(self, text):
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
