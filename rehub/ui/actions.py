"""Estado e ações de cada jogo (Jogar, Instalar, Configurar, Desinstalar...) e os jogos e sites da pessoa.
Mixin do Hub (rehub/ui/app.py)."""
import os
import re
import shutil
import threading
import time
import tkinter as tk
import urllib.parse
import webbrowser
from tkinter import filedialog, messagebox
from tkinter import font as tkfont

from .. import audio, catalog, emulators, fluffy, github, isodl, launcher, library, saves, steam, store
from ..log import log
from ..franchise import FR
from ..paths import COVERS
from ..mods import ModManager
from . import theme as t
from .art import DIM, GREEN, MUTED, WHITE
from .manage import ManageWindow


class GameActions:
    # ---------- estado e ações ----------
    def _state(self, g):
        if g["tipo"] == "info":
            return g.get("versao", ""), MUTED
        if g.get("meu"):   # adicionado pela pessoa: diz o que acontece ao clicar
            return ("Site  ·  abre no navegador", "#7fb3ff") if g.get("url") else ("Seu programa  ·  o hub executa o .exe", GREEN)
        if g.get("mobile"):
            return ("Joga-se no iPhone, iPad ou Mac  ·  App Store" if g["mobile"] == "ios" else "Joga-se no Android  ·  APK"), "#7fb3ff"
        ready = launcher.is_ready(g, self.cfg, self.installed)
        if g["tipo"] == "steam":
            text, color = ("Instalado", GREEN) if ready else ("Não instalado", MUTED)
        elif ready:
            text, color = "Pronto para jogar", GREEN
        else:
            text, color = ("Não baixado" if g.get("github") else "Não configurado"), MUTED
        return text, color

    def _extra_state(self, ch, g):
        """Pedaços extras da linha de estado: [(texto, cor, ação ao clicar ou None)]."""
        out = []
        rel = self.release(ch, g)
        if rel:
            out.append((f"lança {self.countdown(rel)}", self.accent, None))
        if g["tipo"] == "info":
            return out
        p = self.playtimes().get(g["appid"], {}) if g["tipo"] == "steam" else self.cfg.get(g["id"])   # fora da Steam: o hub conta
        if p.get("minutos"):
            out.append((f"{library.hours(p['minutos'])} jogadas", WHITE, None))
        last = self.last_played(g)
        if last:
            out.append((f"jogado {library.ago(last)}", MUTED, None))
        if g["tipo"] == "steam" and g["appid"] in self.installed:
            m = library.manifest(g["appid"])
            news_url = f"steam://openurl/https://store.steampowered.com/news/app/{g['appid']}"
            if m.get("precisa_atualizar"):
                out.append(("atualização pendente na Steam", self.accent, lambda: os.startfile(news_url)))
            elif m.get("atualizado") and last and m["atualizado"] > last:
                out.append(("atualizado desde a última vez  ›", self.accent, lambda: os.startfile(news_url)))
            elif m.get("atualizado"):
                out.append((f"atualizado em {time.strftime('%d/%m/%Y', time.localtime(m['atualizado']))}", DIM,
                            lambda: os.startfile(news_url)))
        price = self.price_of(g)
        if price and price["desconto"] and not self.owned(g):
            out.append((f"-{price['desconto']}% na Steam: {price['texto']}", GREEN, lambda: steam.store(g["appid"])))
        return out

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
        if g.get("meu"):   # adicionado pela pessoa: site abre no navegador, .exe o hub executa
            first = ("Abrir site", lambda: self.play(g), True) if g.get("url") else ("Jogar", lambda: self.play(g), True)
            return [first, ("Editar", lambda: self.add_custom(edit=g), False), ("Remover", lambda: self.remove_custom(g), False)]
        if g.get("mobile"):   # port para celular: abre a App Store ou a página do APK (joga-se no aparelho)
            return [(g.get("acao", "Abrir"), lambda: webbrowser.open(g["url"]), True), manage]
        if launcher.is_ready(g, self.cfg, self.installed):
            return [("Jogar", lambda: self.play(g), True), manage, ("Desinstalar", lambda: self.uninstall_game(g), False)]
        if g.get("andamento"):   # port ainda em desenvolvimento: so acompanhar o projeto
            return [("Acompanhar", lambda: webbrowser.open(g["andamento"]["url"]), True), manage]
        where = []   # o hub baixa direto (Instalar); os links de cada projeto ficam em Gerenciar
        if g.get("emulador"):
            return [("Instalar", lambda: self.install_emulated(g), True), *where, manage]
        if g.get("github"):
            return [("Instalar", lambda: self.download_game(g), True), manage]
        return [("Configurar", lambda: self.configure_local(g), True), *where, manage]

    def _custom_chapters(self):
        chapters = [ch for sec in ("canon", "spinoff") for ch in catalog.load_timeline(self.games, sec)]
        return chapters, [ch["titulo"] for ch in chapters]

    @staticmethod
    def _target_kind(alvo):
        """'site', 'exe' ou None: o que o hub faz ao clicar em Jogar."""
        a = alvo.strip().strip('"')
        if not a:
            return None
        if re.match(r"(?i)^(https?://|www\.)", a):
            return "site"
        if os.path.isfile(a):
            return "exe"
        if re.match(r"(?i)^[\w-]+(\.[\w-]+)+(/\S*)?$", a) and not a.lower().endswith(".exe"):
            return "site"   # residentevil.com.br sem o https://
        return None

    def add_custom(self, edit=None):
        """Opcoes > Adicionar jogo ou site: um site (abre no navegador) ou um programa .exe (o hub executa) num
        capitulo. O tipo e descoberto pelo que a pessoa colou. edit: um item ja adicionado, para mudar."""
        chapters, names = self._custom_chapters()
        if not names:
            return
        cur = self.chapter["titulo"] if self.chapter and self.chapter["titulo"] in names else names[0]
        if edit:
            cur = next((ch["titulo"] for ch in chapters if ch["id"] == edit.get("capitulo")), cur)
        top, body, bar, close = t.modal(self, "Editar jogo ou site" if edit else "Adicionar jogo ou site",
                                        "Cole o endereço de um site ou escolha um programa .exe. Ao clicar em Jogar, o hub "
                                        "abre o site no navegador ou executa o programa, conforme o que você colocar.")
        t.section_title(body, "Nome").pack(fill="x", pady=(0, 6))
        nome = tk.StringVar(value=(edit or {}).get("versao", ""))
        e1 = t.entry(body, nome)
        e1.pack(fill="x")
        t.section_title(body, "Site ou programa").pack(fill="x", pady=(16, 6))
        alvo = tk.StringVar(value=(edit or {}).get("url") or (edit or {}).get("exe_fixo", ""))
        row = tk.Frame(body, bg=t.PANEL)
        row.pack(fill="x")
        t.entry(row, alvo, width=40).pack(side="left", fill="x", expand=True)

        def browse():
            exe = filedialog.askopenfilename(parent=top, title="Escolha o programa", filetypes=[("Programa", "*.exe"), ("Todos", "*.*")])
            if exe:
                alvo.set(exe.replace("/", "\\"))
                if not nome.get().strip():
                    nome.set(os.path.splitext(os.path.basename(exe))[0])
        t.flat_button(row, "Procurar .exe", browse).pack(side="left", padx=(8, 0))
        kind = tk.Label(body, text="", bg=t.PANEL, font=(t.FONT, 9, "bold"), anchor="w")
        kind.pack(fill="x", pady=(8, 0))

        def detect(*_):
            k = self._target_kind(alvo.get())
            if k == "site":
                kind.config(text="●  SITE  —  vai abrir no navegador", fg="#7fb3ff")
            elif k == "exe":
                kind.config(text="●  PROGRAMA  —  o hub executa o .exe", fg=GREEN)
            elif alvo.get().strip():
                kind.config(text="●  Não reconheci: use https://... ou um .exe que exista", fg="#e0857f")
            else:
                kind.config(text=" ", fg=MUTED)
        alvo.trace_add("write", detect)
        detect()
        t.section_title(body, "Capítulo").pack(fill="x", pady=(16, 6))
        chv = tk.StringVar(value=cur)
        t.dropdown(body, chv, names, self.accent).pack(fill="x")
        msg = tk.Label(body, text="", fg="#e0857f", bg=t.PANEL, font=(t.FONT, 10), anchor="w")
        msg.pack(fill="x", pady=(10, 0))

        def save(e=None):
            n, a = nome.get().strip(), alvo.get().strip().strip('"')
            k = self._target_kind(a)
            if not n or not a:
                return msg.config(text="Preencha o nome e o site ou o programa.")
            if not k:
                return msg.config(text="O endereço precisa ser um site (https://...) ou um .exe que existe.")
            if k == "site" and not a.lower().startswith(("http://", "https://")):
                a = "https://" + a
            ch = chapters[names.index(chv.get())]
            items = catalog.load_custom()
            gid = edit["id"] if edit else "meu_" + (re.sub(r"[^a-z0-9]+", "_", n.lower()).strip("_") or "app")
            if not edit:
                base, k2 = gid, 2
                while any(i["id"] == gid for i in items):   # dois com o mesmo nome: nao sobrescreve
                    gid, k2 = f"{base}_{k2}", k2 + 1
            entry = {"id": gid, "nome": f"{ch['titulo']} — {n}", "capitulo": ch["id"], "versao": n, "ordem": 9999}
            self.cfg.clear(gid)
            if k == "site":
                entry["url"] = a
            else:
                entry["exe_fixo"] = a
                self.cfg.set(gid, exe=a)
            items = [i for i in items if i.get("id") != gid] + [entry]
            catalog.save_custom([{kk: v for kk, v in i.items() if kk not in ("tipo", "meu")} for i in items])
            close()
            self.rescan()
            self.notify(f"{n} {'atualizado' if edit else 'adicionado em ' + ch['titulo']}.")
        t.flat_button(bar, "Salvar" if edit else "Adicionar", save, "primary", icon=None if edit else "+").pack(side="right")
        t.flat_button(bar, "Cancelar", close, "ghost").pack(side="right", padx=(0, 8))
        if not edit:
            t.flat_button(bar, "Meus jogos e sites", lambda: (close(), self.after(30, self.manage_custom)), "ghost").pack(side="left")
        top.bind("<Return>", save)
        top.after(60, e1.focus_set)

    def manage_custom(self):
        """Opcoes > Meus jogos e sites: tudo que a pessoa adicionou, com Abrir, Editar e Remover."""
        top, body, bar, close = t.modal(self, "Meus jogos e sites", "O que você adicionou ao hub. Remover tira só do hub: "
                                        "o site e o programa continuam no lugar.", width=660)
        listf = tk.Frame(body, bg=t.PANEL)
        listf.pack(fill="both", expand=True)
        chapters, _ = self._custom_chapters()
        titles = {ch["id"]: ch["titulo"] for ch in chapters}
        small = tkfont.Font(family=t.FONT, size=9)

        def draw():
            for w in listf.winfo_children():
                w.destroy()
            items = catalog.load_custom()
            if not items:
                tk.Label(listf, text="Nada adicionado ainda. Use + Adicionar para colocar um site ou um programa.", fg=MUTED,
                         bg=t.PANEL, font=(t.FONT, 11), anchor="w").pack(fill="x", pady=(4, 8))
            for g in items:
                rbg = "#141210"
                row = tk.Frame(listf, bg=rbg, highlightthickness=1, highlightbackground="#2c2723")
                row.pack(fill="x", pady=(0, 8))
                tk.Frame(row, bg="#7fb3ff" if g.get("url") else GREEN, width=3).pack(side="left", fill="y")
                info = tk.Frame(row, bg=rbg)
                info.pack(side="left", fill="x", expand=True, padx=14, pady=10)
                tk.Label(info, text=g.get("versao", g["nome"]), fg=WHITE, bg=rbg, font=(t.FONT, 12, "bold"), anchor="w").pack(fill="x")
                where = ("SITE  ·  " + g["url"]) if g.get("url") else ("PROGRAMA  ·  " + g.get("exe_fixo", ""))
                tk.Label(info, text=self._elide(where, small, 330), fg=MUTED, bg=rbg, font=small, anchor="w").pack(fill="x")
                tk.Label(info, text=titles.get(g["capitulo"], g["capitulo"]).upper(), fg=DIM, bg=rbg,
                         font=(t.FONT, 8, "bold"), anchor="w").pack(fill="x", pady=(2, 0))
                btns = tk.Frame(row, bg=rbg)
                btns.pack(side="right", padx=12)
                t.flat_button(btns, "Remover", lambda g=g: remove(g), "danger").pack(side="right", padx=(6, 0))
                t.flat_button(btns, "Editar", lambda g=g: (close(), self.after(30, lambda: self.add_custom(edit=g)))).pack(side="right", padx=(6, 0))
                t.flat_button(btns, "Abrir", lambda g=g: self.play(g)).pack(side="right")
            top.place_again()

        def remove(g):
            if self.remove_custom(g, parent=top):
                draw()
        draw()
        t.flat_button(bar, "Adicionar", lambda: (close(), self.after(30, self.add_custom)), "primary", icon="+").pack(side="right")
        t.flat_button(bar, "Fechar", close, "ghost").pack(side="right", padx=(0, 8))

    def remove_custom(self, g, parent=None):
        if not t.confirm(parent or self, f"Remover {g.get('versao', g['nome'])}?", "Sai só do hub: o site ou o programa não são apagados.",
                         ok="Remover", danger=True):
            return False
        catalog.save_custom([{k: v for k, v in i.items() if k not in ("tipo", "meu")} for i in catalog.load_custom() if i["id"] != g["id"]])
        self.cfg.clear(g["id"])
        self.version_idx.pop(g.get("capitulo"), None)   # volta para a versão padrão do capítulo
        cid = self.chapter["id"] if self.chapter else None
        self.rescan()
        self.sel = next((i for i, ch in enumerate(self.chapters) if ch["id"] == cid), self.sel)
        self.notify(f"{g.get('versao', g['nome'])} removido.")
        return True

    def install_emulated(self, g):
        """Instalar de um jogo sem port: baixa o emulador certo (uma vez para todos os jogos dele) e pede so a ISO."""
        e = emulators.of(g)
        exe = emulators.find(g["emulador"])

        def ready(path):
            self.cfg.set(g["id"], exe=str(path))
            if self.ask_iso(g):   # procura no PC; se não achar, oferece baixar pelos links ou escolher o arquivo
                messagebox.showinfo(FR["app"], f"{g['nome']} pronto: clique em Jogar ({e['nome']}).")
            self.refresh()

        if exe:
            return ready(exe)
        self.status_text = f"Baixando o {e['nome']}..."
        self.notify(f"Baixando o {e['nome']}... aguarde, nao precisa clicar de novo.", 5)
        self.refresh()

        def done(result):
            self.status_text = ""
            ready(result[1])

        def fail(msg):
            self.status_text = ""
            self.refresh()
            messagebox.showerror(FR["app"], f"Falha ao baixar o {e['nome']}:\n{msg}")

        t.in_background(self, lambda: emulators.install(g["emulador"]), done, fail)

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
                   "Seus arquivos (jogo, ISO, saves) não são apagados; os saves ganham um backup antes (Gerenciar > Saves)."]
        if not t.confirm(parent, f"Desinstalar {g['nome']} do app?", "O jogo volta a aparecer como não configurado.",
                         details, ok="Desinstalar", danger=True):
            return
        for mod_id in active:
            try:
                mm.disable(mod_id)
            except OSError:
                pass
        if dl.exists():
            try:   # o port pode guardar o save dentro da própria pasta: backup antes de apagar
                saves.backup(g["id"], self.save_paths(g), "antes de desinstalar")
            except (OSError, RuntimeError):
                log.exception("falhou: backup antes de desinstalar %s", g["id"])
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
        now = time.time()
        if now - self._launching.get(g["id"], 0) < 10:
            self.notify(f"{g['nome']} ja esta abrindo. Nao precisa clicar de novo.")
            return
        self._launching[g["id"]] = now
        if self.prefs["efeitos"]:   # voz do título do jogo (data/sons/titulos/<capítulo>.mp3, ou _geral.mp3)
            audio.play_file("titulo", audio.title_voice(g.get("capitulo", g["id"])), 0.9)
        self.notify(f"Abrindo {g['nome']}... pode levar alguns segundos.", 5)
        try:
            if g["tipo"] != "steam":  # a Steam já guarda quando você jogou; os outros, o app guarda
                self.cfg.set(g["id"], ultima=int(time.time()))
            aviso = self.launch(g)
            if aviso:
                messagebox.showinfo(FR["app"], aviso)
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
                                             filetypes=[("Imagem", isodl.image_types(g)), ("Todos", "*.*")])
            if not iso:
                return False
            bad = isodl.bad_image(iso, g)
            if bad:
                messagebox.showerror(FR["app"], bad, parent=parent)
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
        # o progresso aparece embaixo do jogo; a ISO vem depois: o hub procura no PC e, se não achar, oferece
        # baixar pelos links (ask_iso)
        prog = self._task(g, "Baixando o port")

        def work():
            if g.get("instalador"):   # o projeto tem instalador proprio: baixa e abre ele
                tag, setup = github.download_asset(g["github"], g.get("asset"), launcher.download_dir(g),
                                                   prog.step(f"{g['nome']}: instalador"), prog.cancelled)
                os.startfile(setup)
                return tag, None
            if launcher.download_dir(g).exists():   # atualizando: backup dos saves antes de copiar por cima
                try:
                    saves.backup(g["id"], self.save_paths(g), "antes de atualizar o port")
                except (OSError, RuntimeError):
                    log.exception("falhou: backup antes de atualizar %s", g["id"])
            tag = github.download_release(g["github"], g.get("asset"), launcher.download_dir(g), merge=True,
                                          progress=prog.step("Baixando o port"), cancelled=prog.cancelled)
            return tag, launcher.find_exe(g)

        def finish():
            prog.close()
            self.refresh()
            if on_done:
                on_done()

        def done(result):
            prog.close()   # terminou: o progresso some antes de pedir a ISO ou avisar
            tag, exe = result
            if exe:
                self.cfg.set(g["id"], exe=str(exe))
                if "{iso}" in g.get("args", "") and not self.cfg.get(g["id"]).get("iso"):
                    self.ask_iso(g)   # o port abre a ISO da pessoa: ja pede agora
            msg = (f"O instalador de {g['nome']} {tag} foi aberto. Termine a instalacao e depois clique em Configurar."
                   if g.get("instalador") else f"{g['nome']} {tag} instalado.")
            if g.get("depois_de_baixar"):
                msg += "\n\nPróximo passo: " + g["depois_de_baixar"]
            elif not exe:
                msg += "\n\nAgora clique em Configurar e escolha o .exe."
            messagebox.showinfo(FR["app"], msg)
            finish()

        def fail(msg):
            prog.close()
            messagebox.showerror(FR["app"], f"Falha ao baixar:\n{msg}")
            finish()

        t.in_background(self, work, done, fail)
