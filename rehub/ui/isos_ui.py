"""ISOs pela interface: achar no PC, converter, baixar pelos links, importar lista e organizar uma pasta.
Mixin do Hub (rehub/ui/app.py)."""
import os
import time
import tkinter as tk
import webbrowser
from tkinter import filedialog, messagebox

from .. import isodl, isofind
from ..franchise import FR
from . import theme as t
from .progress import Progress
from ..log import log


class IsoActions:
    def ask_iso(self, g, parent=None, adopt=False):
        """Procura no PC todas as imagens do jogo e mostra numa lista dentro do launcher (sem abrir pasta por pasta).
        Clicar numa usa ela (um .chd que a versão não abre é convertido). Sem nenhuma: avisa e oferece baixar pelos
        links. adopt=True (Gerenciar): a escolhida é movida para data/isos/<jogo>. True se escolheu algo."""
        parent = parent or self
        kinds = {k[1:] for k in isodl.image_types(g).split()} | {".chd"}
        self.config(cursor="watch")
        self.update()
        try:
            found = isofind.find(g.get("iso_busca") or [g["nome"]], kinds, g.get("iso_serial"), limit=12,
                                 extra=[isodl.DEST])
        finally:
            self.config(cursor="")
        found = [f for f in found if isodl.convertible(g, f) or not isodl.bad_image(f, g)]
        opts = [v for v in isodl.VARIANTS if v in isodl.link_for(g)] + [v for v in isodl.link_for(g) if v not in isodl.VARIANTS]
        top, body, bar, close = t.modal(parent, f"ISO de {g['nome']}",
                                        f"{len(found)} encontrada(s) no PC: clique na que quer usar." if found else
                                        "Não achei a ISO deste jogo no PC. Baixe pelo seu link.", width=660)
        result = {"ok": False}

        def use(path):
            close()
            result["ok"] = True
            if isodl.convertible(g, path):
                self.convert_iso(g, path)
            elif adopt:
                self._adopt_iso(g, path)
            else:
                self.cfg.set(g["id"], iso=path)
                self.refresh()

        cur = self.cfg.get(g["id"]).get("iso")
        for path in found:
            size = os.path.getsize(path) / 1024 ** 3
            note = "vai ser convertida para .iso" if isodl.convertible(g, path) else ("em uso agora" if path == cur else "")
            row = tk.Frame(body, bg=t.PANEL_HI, cursor="hand2")
            row.pack(fill="x", pady=3)
            name = t.label(row, os.path.basename(path), 11, bold=True, bg=t.PANEL_HI)
            name.pack(fill="x", padx=14, pady=(9, 0))
            sub = t.label(row, f"{os.path.dirname(path)}  ·  {size:.2f} GB" + (f"  ·  {note}" if note else ""), 9,
                          fg=t.MUTED, bg=t.PANEL_HI, wraplength=580)
            sub.pack(fill="x", padx=14, pady=(2, 9))
            for w in (row, name, sub):
                w.bind("<Button-1>", lambda e, p=path: use(p))
                w.bind("<Enter>", lambda e, ws=(row, name, sub): [x.config(bg="#34302b") for x in ws])
                w.bind("<Leave>", lambda e, ws=(row, name, sub): [x.config(bg=t.PANEL_HI) for x in ws])
        if not found and not opts:
            t.label(body, "Cadastre o link em Opções > ISOs > Editar links das ISOs (Normal, Português ou Dublada).",
                    10, fg=t.MUTED, wraplength=600).pack(fill="x")
        for k, v in enumerate(opts):   # baixar cada opção que a pessoa cadastrou
            t.flat_button(bar, f"Baixar {v}", lambda v=v: (close(), result.update(ok=True), self.download_iso(g, variant=v)),
                          "plain" if found or k else "primary").pack(side="left", padx=(0, 8))
        t.flat_button(bar, "Fechar", close, "ghost").pack(side="right")
        top.place_again()
        top.wait_window()
        return result["ok"]

    def _adopt_iso(self, g, path):
        """Move a ISO escolhida para dentro do launcher (data/isos/<jogo>/, com o nome dela) e deixa escolhida."""
        def done(new):
            self.cfg.set(g["id"], iso=str(new))
            self.refresh()
            t.notice(self, "ISO escolhida", f"Movida para dentro do RE Launcher:\n{new}")
        t.in_background(self, lambda: isodl.adopt(g, path), done,
                        lambda msg: t.notice(self, "Não deu certo", msg, error=True))

    def convert_iso(self, g, path, on_done=None):
        prog = self._task(g, "Convertendo a ISO")

        def work():
            if not isodl.CHDMAN.exists():
                isodl.ensure_chdman(prog.step("Baixando o chdman (MAME, uma vez só)"), prog.cancelled)
            return isodl.convert(g, path, prog.step(".chd para .iso", items="pct"), prog.cancelled)

        def done(iso):
            prog.close()
            self.cfg.set(g["id"], iso=str(iso))
            self.refresh()
            (on_done or (lambda: t.notice(self, "ISO pronta", f"Convertida e escolhida:\n{iso}")))()

        def fail(msg):
            prog.close()
            messagebox.showerror(FR["app"], f"Não deu para converter:\n{msg}")

        t.in_background(self, work, done, fail)

    def download_iso(self, g, on_done=None, variant=None):
        """Baixa a ISO pelo link de data/isos.json (na opção escolhida), com a janela de progresso, e já deixa
        escolhida. Se vier .chd para um port que só lê .iso, converte no fim."""
        variant = variant or isodl.default_variant(g)
        url = isodl.link_for(g).get(variant, "")
        if isodl.needs_browser(url):   # MediaFire etc. recusam o download feito pelo programa (HTTP 403)
            return self.download_iso_browser(g, on_done, variant)
        prog = self._task(g, f"Baixando a ISO ({variant})")

        def done(iso):
            prog.close()
            self.cfg.set(g["id"], iso=str(iso))
            self.refresh()
            (on_done or (lambda: t.notice(self, "ISO pronta", str(iso))))()

        def fail(msg):
            prog.close()
            self.refresh()
            if "403" in msg and t.confirm(self, "O site recusou o download", "Alguns sites só deixam baixar pelo "
                                          "navegador. Abrir o link no navegador? O launcher pega o arquivo quando terminar.",
                                          ok="Abrir no navegador"):
                return self.download_iso_browser(g, on_done, variant)
            messagebox.showerror(FR["app"], f"Falha ao baixar a ISO:\n{msg}")

        def converting(d, total, _speed, _eta):   # se vier .chd para um port que só lê .iso
            prog.state.update(step="Convertendo .chd para .iso", items="pct", done=d, total=total, speed=0, eta=None)

        t.in_background(self, lambda: isodl.download(g, prog.step(f"Baixando a ISO ({variant})"), prog.cancelled,
                                                     variant=variant, convert_progress=converting), done, fail)

    def download_iso_browser(self, g, on_done=None, variant=None):
        """Abre o link no navegador e espera o arquivo aparecer em Downloads; quando termina, leva para
        data/isos/<jogo>/ e já deixa escolhida. A pessoa só clica no botão de download da página."""
        variant = variant or isodl.default_variant(g)
        url = isodl.link_for(g).get(variant)
        if not url:
            return t.notice(self, "Sem link", f"Cadastre o link de {g['nome']} em Opções > ISOs > Editar links.", error=True)
        since = time.time()
        webbrowser.open(url)
        prog = self._task(g, "Esperando o download no navegador")
        self.notify("Clique em Download na página que abriu. O launcher pega o arquivo em Downloads quando terminar.", 8)
        folder = isodl.downloads_dir()

        def work():
            path = isodl.wait_browser_download(g, since, prog.cancelled, prog.step("Baixando pelo navegador"), folder)
            prog.step("Levando a ISO para o launcher")
            return isodl.take_download(g, path, variant, prog.step(".chd para .iso", items="pct"), prog.cancelled)

        def done(iso):
            prog.close()
            self.cfg.set(g["id"], iso=str(iso))
            self.refresh()
            self.summon()
            (on_done or (lambda: t.notice(self, "ISO pronta", str(iso))))()

        def fail(msg):
            prog.close()
            self.refresh()
            if msg != "Cancelado.":
                messagebox.showerror(FR["app"], f"Falha ao pegar a ISO baixada:\n{msg}")
        t.in_background(self, work, done, fail)

    def _iso_games(self, with_link=False):
        """Versoes que abrem a ISO da pessoa e ainda nao tem uma (com link em data/isos.json, se with_link)."""
        return [g for g in self.games if isodl.needs_iso(g) and g["tipo"] != "steam"
                and not os.path.isfile(self.cfg.get(g["id"]).get("iso") or "")
                and (not with_link or isodl.link_for(g))]

    def import_iso_links(self):
        """Le um arquivo de links (.txt ou .json), liga cada link ao jogo certo e guarda em data/isos.json."""
        path = filedialog.askopenfilename(parent=self, title="Arquivo com os links das ISOs (.txt ou .json)",
                                          filetypes=[("Lista de links", "*.txt *.json"), ("Todos", "*.*")])
        if not path:
            return
        try:
            found, missed = isodl.import_links(path, self.games)
        except (OSError, ValueError) as e:
            return t.notice(self, "Não deu certo", str(e), error=True)
        names = {g["id"]: g["nome"] for g in self.games}
        details = [f"{names.get(k, k)}" for k in found][:12] + (["..."] if len(found) > 12 else [])
        if missed:
            details.append(f"Sem jogo reconhecido ({len(missed)}): " + "; ".join(missed[:3]))
        if not found:
            return t.notice(self, "Nenhum link reconhecido", "Use uma linha por jogo: nome do jogo = link.", details, error=True)
        if t.confirm(self, f"{len(found)} link(s) guardado(s)", "Baixar agora as ISOs que ainda faltam?", details, ok="Baixar tudo"):
            self.download_all_isos()

    def download_all_isos(self):
        """Baixa, uma depois da outra, as ISOs que tem link e ainda faltam; cada uma vai para data/isos/<jogo>."""
        todo = self._iso_games(with_link=True)
        if not todo:
            return t.notice(self, "Nada para baixar", "Todos os jogos com link em data/isos.json já têm a ISO.")
        prog = self._task(todo[0], "Baixando as ISOs")   # aparece embaixo de cada jogo enquanto baixa o dele
        self.notify(f"Baixando {len(todo)} ISO(s), uma de cada vez: o progresso aparece embaixo de cada jogo.", 5)

        def work():
            got, errors, by_url = {}, [], {}
            for k, g in enumerate(todo, 1):
                if prog.cancelled():
                    break
                variant = isodl.default_variant(g)   # em lote vai a opção Normal (ou a única que houver)
                url = isodl.link_for(g)[variant]
                if isodl.needs_browser(url):
                    errors.append(f"{g['nome']}: esse site só baixa pelo navegador (use Baixar em Gerenciar > ISO)")
                    continue
                try:
                    if url not in by_url:   # versoes do mesmo jogo com o mesmo link baixam uma vez so
                        by_url[url] = isodl.download(g, prog.step(f"Baixando a ISO ({k}/{len(todo)})", gid=g["id"]),
                                                     prog.cancelled, variant=variant)
                    got[g["id"]] = by_url[url]
                except Exception as e:
                    log.exception("falhou: ISO de %s", g["id"])
                    errors.append(f"{g['nome']}: {e}")
            return got, errors

        def done(result):
            got, errors = result
            prog.close()
            for gid, iso in got.items():
                self.cfg.set(gid, iso=str(iso))
            self.refresh()
            (t.notice(self, "Algumas ISOs falharam", f"{len(got)} pronta(s), {len(errors)} com erro.", errors[:8], error=True)
             if errors else t.notice(self, "ISOs prontas", f"{len(got)} ISO(s) baixada(s) e já escolhida(s) em cada jogo."))

        t.in_background(self, work, done, lambda msg: (prog.close(), t.notice(self, "Não deu certo", msg, error=True)))

    def organize_isos(self):
        """Escolhe uma pasta com ISOs já baixadas: o hub reconhece cada uma, move para data/isos/<jogo> e escolhe."""
        folder = filedialog.askdirectory(parent=self, title="Pasta com as ISOs baixadas",
                                         initialdir=os.path.join(os.path.expanduser("~"), "Downloads"))
        if not folder:
            return
        self.config(cursor="watch")
        self.update()
        try:
            matches = isodl.scan_folder(folder, self.games, self.cfg)
        finally:
            self.config(cursor="")
        if not matches:
            return t.notice(self, "Nenhuma ISO reconhecida", "Nenhum arquivo da pasta parece ser de um jogo que ainda está sem ISO.",
                            ["O nome do arquivo precisa ter o nome do jogo ou o código do disco (ex.: SLUS-20184)."])
        details = [f"{os.path.basename(f)}  →  {', '.join(g['nome'] for g in gs)}" for f, gs in matches[:12]]
        details += ["..."] if len(matches) > 12 else []
        details.append("Os arquivos são movidos para data/isos (um .zip/.rar/.7z é extraído e o original fica onde está).")
        if not t.confirm(self, f"Organizar {len(matches)} arquivo(s)?", "Cada um vai para a pasta do seu jogo e já fica escolhido.",
                         details, ok="Organizar"):
            return
        prog = Progress(self, "Organizando as ISOs")

        def step(k, n, name):
            prog.step(f"Movendo  ·  {name}", items=True)(k, n, 0, None)

        def done(found):
            prog.close()
            for gid, iso in found.items():
                self.cfg.set(gid, iso=str(iso))
            self.refresh()
            t.notice(self, "ISOs organizadas", f"{len(found)} jogo(s) com a ISO escolhida.")

        t.in_background(self, lambda: isodl.organize(matches, step), done,
                        lambda msg: (prog.close(), t.notice(self, "Não deu certo", msg, error=True)))
