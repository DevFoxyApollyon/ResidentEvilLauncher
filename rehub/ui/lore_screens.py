"""Mais telas por cima do hub: Mapa, Arquivos dos jogos, Relações, Vírus (ou Substâncias), Conquistas do hub,
e a aba Speedrun do painel. Como screens.py, é um mixin do Hub (usa o mesmo canvas e as mesmas primitivas)."""
import math
import threading
import webbrowser

from PIL import Image, ImageTk

from .. import catalog, characters, lore
from ..franchise import FR
from . import app as A

LORE_KINDS = ("mapa", "arquivos", "relacoes", "virus", "conquistas")
EDGE_COLORS = {"familia": None, "aliados": "#6fbf8a", "inimigos": "#d0575b"}  # None = cor de destaque


class LoreScreens:
    # ---------- estatísticas (para as conquistas) ----------
    def stat_add(self, key, value):
        """Guarda que algo foi visto (ficha, arquivo, local...). Conta cada item uma vez só."""
        stats = self.cfg.get("_stats")
        seen = list(stats.get(key, []))
        if value in seen:
            return
        seen.append(value)
        self.cfg.set("_stats", **{key: seen})
        self.after(300, self.check_achievements)

    def stat_count(self, key):
        stats = self.cfg.get("_stats")
        self.cfg.set("_stats", **{key: int(stats.get(key, 0)) + 1})
        self.after(300, self.check_achievements)

    def _stat(self, key):
        v = self.cfg.get("_stats").get(key, [])
        return v if isinstance(v, int) else len(v)

    # ---------- entrada / teclas ----------
    def _lore_extras(self):
        out = []
        if lore.load("mapa"):
            out.append(("mapa", "Mapa", "Onde cada capítulo acontece, no mundo e na cidade", "M"))
        if any(lore.has_files(ch["id"]) for ch in catalog.load_timeline(self.games, "canon")):
            out.append(("arquivos", "Arquivos dos jogos", "Documentos e diários de cada jogo, para ler aqui", "A"))
        if lore.load("relacoes"):
            out.append(("relacoes", "Relações", "Famílias, parceiros e inimigos ligados por linhas", "R"))
        virus = lore.load("virus")
        if virus:
            out.append(("virus", virus.get("titulo", "Vírus"), "Quem criou, como age e quem foi infectado", "V"))
        out.append(("conquistas", "Conquistas do hub", "Metas do próprio hub: linha do tempo, versões, horas...", "K"))
        return out

    def _lore_titles(self):
        virus = lore.load("virus")
        return {"mapa": ("Mapa", "Setas escolhem o lugar · Tab troca entre o mundo e a cidade · clique num jogo para abrir"),
                "arquivos": ("Arquivos dos jogos", "Tab troca o jogo · ↑ ↓ escolhem o arquivo · PageUp/PageDown rolam o texto"),
                "relacoes": ("Relações", "↑ ↓ trocam o grupo · clique num personagem para ver a ficha"),
                "virus": (virus.get("titulo", "Vírus"), "↑ ↓ escolhem · clique num personagem ou jogo para abrir"),
                "conquistas": ("Conquistas do hub", "Metas que o hub acompanha sozinho, a partir do que você joga")}

    def _lore_open(self, kind):
        ov = self.overlay
        if kind == "arquivos":
            chapters = self._file_chapters()
            cur = self.chapter["id"] if self.chapter else None
            ov["cap"] = next((i for i, ch in enumerate(chapters) if ch["id"] == cur), 0)
            ov["text_scroll"] = 0
        elif kind == "mapa":
            ov["aba"] = "mundo"
            threading.Thread(target=lambda: lore.world_map() and self.after(0, self.refresh), daemon=True).start()
        elif kind == "virus":
            self._fetch_virus_images()
        elif kind == "relacoes":
            self._fetch_portraits()
        elif kind == "conquistas":
            self.check_achievements()

    def _lore_press(self, kind, action):
        ov = self.overlay
        step = {"up": -1, "left": -1, "down": 1, "right": 1, "scroll_up": -1, "scroll_down": 1}.get(action)
        if kind == "mapa":
            places = self._places()
            if action in ("next_section", "prev_section"):
                ov.update(aba="cidade" if ov["aba"] == "mundo" else "mundo", sel=0)
                self._sound("tab")
            elif step and places:
                ov["sel"] = (ov["sel"] + step) % len(places)
                self._sound("select")
            elif action == "enter" and places and places[ov["sel"]].get("capitulos"):
                return self.goto_chapter(places[ov["sel"]]["capitulos"][0])
        elif kind == "arquivos":
            chapters = self._file_chapters()
            if action in ("next_section", "prev_section") and chapters:
                ov.update(cap=(ov["cap"] + (1 if action == "next_section" else -1)) % len(chapters), sel=0, text_scroll=0)
                self._sound("tab")
            elif action in ("up", "down"):
                ov.update(sel=max(0, ov["sel"] + step), text_scroll=0)
                self._sound("select")
            elif action in ("tab_prev", "tab_next", "left", "right"):
                ov["text_scroll"] = max(0, ov["text_scroll"] + (-8 if action in ("tab_prev", "left") else 8))
            elif action == "enter":
                link = ov.get("link")
                if link:
                    webbrowser.open(link)
        elif kind in ("relacoes", "virus", "conquistas"):
            if step:
                ov["sel"] = max(0, ov["sel"] + step)
                self._sound("select")
        self.refresh()

    def _lore_wheel(self, kind, delta):
        ov = self.overlay
        if kind == "arquivos" and self.winfo_pointerx() - self.c.winfo_rootx() > ov.get("reader_x", 10 ** 6):
            ov["text_scroll"] = max(0, ov["text_scroll"] + (3 if delta < 0 else -3))
            return self.refresh()
        self._lore_press(kind, "down" if delta < 0 else "up")

    # ---------- Mapa ----------
    def _places(self):
        data = lore.load("mapa")
        ov = self.overlay
        return data.get("mundo", []) if ov.get("aba") == "mundo" else data.get("cidade", {}).get("locais", [])

    def _world_photo(self, size):
        """Mapa-múndi nas cores do app (terra escura, mar mais escuro), no tamanho pedido."""
        key = ("mundo", size)
        if key in self._map_cache:
            return self._map_cache[key]
        p = lore.world_map()
        if not p:
            return None
        try:
            src = Image.open(p).convert("RGBA")
        except OSError:
            return None
        land = src.getchannel("A").point(lambda v: 255 if v > 40 else 0)
        img = Image.new("RGB", src.size, (13, 17, 25))
        img.paste((44, 52, 68), (0, 0), land)
        self._map_cache[key] = ImageTk.PhotoImage(img.resize(size, Image.LANCZOS))
        return self._map_cache[key]

    def _draw_mapa(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        data = lore.load("mapa")
        city = data.get("cidade", {})
        tabs = [("mundo", "Mundo")] + ([("cidade", city.get("nome", "Cidade"))] if city.get("locais") else [])
        fx = x
        for key, label in tabs:
            fx = self._chip(fx, y - 8, label, lambda k=key: (self.overlay.update(aba=k, sel=0), self.refresh()),
                            f"ov_map_{key}", primary=ov["aba"] == key) + 8
        y += 40
        places = self._places()
        if not places:
            return self._note(x, y, w, "Sem lugares cadastrados (games/_mapa.json).")
        ov["sel"] = min(ov["sel"], len(places) - 1)
        mw = int(w * 0.66)
        mh = min(int(mw / 2), int(bottom - y))
        mw = mh * 2
        if ov["aba"] == "mundo":
            photo = self._world_photo((mw, mh))
            if photo:
                c.create_image(x, y, image=photo, anchor="nw")
            else:
                self._round_rect(x, y, x + mw, y + mh, 14, fill="#0d1119", outline="#262d3a")
                c.create_text(x + mw / 2, y + mh / 2, text="Baixando o mapa...", fill=A.MUTED, font=self.f["body"])

            def pos(pl):
                return x + (pl["lon"] + 180) / 360 * mw, y + (90 - pl["lat"]) / 180 * mh
        else:
            self._draw_city(x, y, mw, mh, city.get("nome", ""))

            def pos(pl):
                return x + 30 + pl["x"] * (mw - 60), y + 30 + pl["y"] * (mh - 60)
        for i, pl in enumerate(places):
            px, py = pos(pl)
            on = i == ov["sel"]
            tag = f"ov_pl_{ov['aba']}_{i}"
            if on:
                c.create_oval(px - 16, py - 16, px + 16, py + 16, outline=self.accent, width=2)
            r = 8 if on else 6
            c.create_oval(px - r, py - r, px + r, py + r, fill=self.accent if on else A.WHITE, outline="#0b0e14", width=2, tags=(tag,))
            if ov["aba"] == "cidade" or on:
                c.create_text(px + 12, py, anchor="w", text=pl["nome"], fill=A.WHITE if on else A.MUTED,
                              font=self.f["small"], tags=(tag,))
            self._clickable(tag, lambda i=i: (self.overlay.__setitem__("sel", i), self._sound("select"), self.refresh()))
        pl = places[ov["sel"]]
        self.stat_add("locais", f"{ov['aba']}:{pl['nome']}")
        # detalhes do lugar e lista
        dx, dw = x + mw + 30, w - mw - 30
        c.create_text(dx, y, anchor="nw", text=pl["nome"], fill=A.WHITE, font=self.f["h"], width=dw)
        c.create_text(dx, y + 26, anchor="nw", text=pl.get("regiao", ""), fill=self.accent, font=self.f["small"], width=dw)
        ay, ax = y + 56, dx
        titles = self._chapter_titles()
        for cid in pl.get("capitulos", []):
            label = titles.get(cid)
            if not label:
                continue
            cw = self.f["small"].measure(label) + 26
            if ax + cw > dx + dw:
                ax, ay = dx, ay + 34
            ax = self._chip(ax, ay, label, lambda c_=cid: self.goto_chapter(c_), f"ov_plc_{cid}") + 8
        ly = ay + 52
        c.create_text(dx, ly, anchor="nw", text="TODOS OS LUGARES", fill=A.MUTED, font=self.f["tiny"])
        ly += 20
        fits = max(1, int((bottom - ly) // 26))
        start = min(max(0, ov["sel"] - fits // 2), max(0, len(places) - fits))
        for k, p in enumerate(places[start:start + fits]):
            i = start + k
            tag = f"ov_pll_{ov['aba']}_{i}"
            c.create_text(dx, ly + k * 26, anchor="nw", text=self._elide(p["nome"], self.f["small"], dw),
                          fill=A.WHITE if i == ov["sel"] else A.MUTED, font=self.f["small"], tags=(tag,))
            self._clickable(tag, lambda i=i: (self.overlay.__setitem__("sel", i), self._sound("select"), self.refresh()))

    def _draw_city(self, x, y, w, h, name):
        """Planta da cidade desenhada pelo app (as cidades dos jogos são inventadas)."""
        c = self.c
        self._round_rect(x, y, x + w, y + h, 16, fill="#10151f", outline="#262d3a")
        for k in range(1, 12):  # ruas
            gx = x + k * w / 12
            c.create_line(gx, y + 8, gx, y + h - 8, fill="#18202c")
        for k in range(1, 6):
            gy = y + k * h / 6
            c.create_line(x + 8, gy, x + w - 8, gy, fill="#18202c")
        c.create_line(x + w * 0.05, y + h * 0.9, x + w * 0.45, y + h * 0.35, x + w * 0.95, y + h * 0.2,
                      fill="#1f2a3a", width=6, smooth=True)  # avenida principal
        c.create_text(x + w - 20, y + h - 16, anchor="se", text=f"{name.upper()}  ·  planta ilustrativa",
                      fill=A.DIM, font=self.f["tiny"])

    # ---------- Arquivos dos jogos ----------
    def _file_chapters(self):
        out = []
        for sec in ("canon", "spinoff", "midia"):
            out += [ch for ch in catalog.load_timeline(self.games, sec) if lore.has_files(ch["id"])]
        return out

    def _async(self, store, key, fn):
        """Busca algo numa thread uma vez só; store[key] fica None (carregando), o resultado ou {"erro": ...}."""
        if key in store:
            return store[key]
        store[key] = None

        def work():
            try:
                store[key] = fn()
            except Exception as e:
                store[key] = {"erro": str(e)}
            self.after(0, self.refresh)
        threading.Thread(target=work, daemon=True).start()
        return None

    def _draw_arquivos(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        chapters = self._file_chapters()
        if not chapters:
            return self._note(x, y, w, "Nenhum jogo com arquivos cadastrados.")
        ov["cap"] = min(ov["cap"], len(chapters) - 1)
        ch = chapters[ov["cap"]]
        # coluna 1: jogos
        cw1 = int(w * 0.2)
        fits = max(1, int((bottom - y) // 30))
        start = min(max(0, ov["cap"] - fits // 2), max(0, len(chapters) - fits))
        for k, chp in enumerate(chapters[start:start + fits]):
            i = start + k
            tag = f"ov_fc_{chp['id']}"
            on = i == ov["cap"]
            if on:
                self._round_rect(x - 10, y + k * 30 - 4, x + cw1, y + k * 30 + 24, 10, fill="#1b2230", outline="")
            c.create_text(x, y + k * 30, anchor="nw", text=self._elide(chp["titulo"], self.f["small"], cw1 - 8),
                          fill=A.WHITE if on else A.MUTED, font=self.f["small"], tags=(tag,))
            self._clickable(tag, lambda i=i: (self.overlay.update(cap=i, sel=0, text_scroll=0), self._sound("tab"), self.refresh()))
        # coluna 2: arquivos do jogo
        x2, cw2 = x + cw1 + 24, int(w * 0.27)
        groups = self._async(self._files, ch["id"], lambda: lore.file_groups(ch["id"]))
        if groups is None:
            return self._note(x2, y, cw2, "Buscando os arquivos na wiki...")
        if isinstance(groups, dict):
            return self._note(x2, y, cw2, "Não consegui buscar os arquivos (sem internet?).")
        rows = []
        for label, titles in groups:
            rows.append(("h", label))
            rows += [("f", t) for t in titles]
        files = [r[1] for r in rows if r[0] == "f"]
        if not files:
            return self._note(x2, y, cw2, "A wiki não tem arquivos deste jogo.")
        ov["sel"] = min(ov["sel"], len(files) - 1)
        title = files[ov["sel"]]
        sel_row = next(k for k, r in enumerate(rows) if r == ("f", title))
        fits = max(1, int((bottom - y) // 26))
        start = min(max(0, sel_row - fits // 2), max(0, len(rows) - fits))
        fi = sum(1 for r in rows[:start] if r[0] == "f")
        for k, (kind, text) in enumerate(rows[start:start + fits]):
            ry = y + k * 26
            if kind == "h":
                c.create_text(x2, ry + 4, anchor="nw", text=text.upper(), fill=self.accent, font=self.f["tiny"])
                continue
            i = fi
            fi += 1
            on = i == ov["sel"]
            tag = f"ov_ff_{abs(hash(text)) % 10 ** 9}"
            if on:
                self._round_rect(x2 - 10, ry - 3, x2 + cw2, ry + 22, 9, fill="#1b2230", outline="")
            c.create_text(x2, ry, anchor="nw", text=self._elide(text, self.f["small"], cw2 - 8),
                          fill=A.WHITE if on else A.MUTED, font=self.f["small"], tags=(tag,))
            self._clickable(tag, lambda i=i: (self.overlay.update(sel=i, text_scroll=0), self._sound("select"), self.refresh()))
        # coluna 3: o texto
        x3 = x2 + cw2 + 30
        w3 = x + w - x3
        ov["reader_x"] = x3
        self._round_rect(x3 - 20, y - 10, x + w + 20, bottom, 18, fill="#10141c", outline="#262d3a")
        pt = self.prefs.get("arquivos_pt", True)
        doc = self._async(self._file_texts, (title, pt), lambda: lore.read_file_pt(title) if pt else lore.read_file(title))
        c.create_text(x3, y + 4, anchor="nw", text=self._elide(title, self.f["h"], w3 - 290), fill=A.WHITE, font=self.f["h"])
        bx = self._chip(x + w, y - 2, "Abrir na wiki  ›", lambda: webbrowser.open(ov["link"]) if ov.get("link") else None,
                        "ov_f_wiki", anchor="e") - 8
        self._chip(bx, y - 2, "Português" if pt else "Original (inglês)", self._toggle_files_lang, "ov_f_lang",
                   anchor="e", primary=pt)
        if doc is None:
            return self._note(x3, y + 44, w3, "Traduzindo..." if pt else "Abrindo...")
        if "erro" in doc:
            if pt:  # sem tradução (sem internet ou o tradutor recusou): mostra o original
                doc = self._file_texts.get((title, False)) or self._async(self._file_texts, (title, False), lambda: lore.read_file(title))
            if not doc or "erro" in doc:
                return self._note(x3, y + 44, w3, "Não consegui abrir este arquivo.")
            pt = False
        self.stat_add("arquivos", title)
        ov["link"] = doc["link"]
        lines = self._wrap_lines(doc["texto_pt"] if pt else doc["texto"], self.f["body"], w3 - 10)
        top = y + 44
        fits = max(1, int((bottom - top - 30) // 20))
        ov["text_scroll"] = min(ov["text_scroll"], max(0, len(lines) - fits))
        for k, line in enumerate(lines[ov["text_scroll"]:ov["text_scroll"] + fits]):
            c.create_text(x3, top + k * 20, anchor="nw", text=line, fill="#d5d9e0", font=self.f["body"])
        c.create_text(x3, bottom - 14, anchor="sw", fill=A.DIM, font=self.f["tiny"],
                      text=("Tradução automática (Google Tradutor) do texto da wiki" if pt else "Texto da wiki da franquia (em inglês)") + (f"  ·  linhas {ov['text_scroll'] + 1}–"
                                                                      f"{min(len(lines), ov['text_scroll'] + fits)} de {len(lines)}"
                                                                      if len(lines) > fits else ""))

    def _toggle_files_lang(self):
        self._save_prefs(arquivos_pt=not self.prefs.get("arquivos_pt", True))
        self.overlay["text_scroll"] = 0
        self._sound("tab")
        self.refresh()

    def _wrap_lines(self, text, font, width):
        key = (text, width)
        if self._wrap_cache.get("key") == key:
            return self._wrap_cache["lines"]
        lines = []
        for para in text.split("\n"):
            line = ""
            for word in para.split(" "):
                test = f"{line} {word}" if line else word
                if font.measure(test) > width and line:
                    lines.append(line)
                    line = word
                else:
                    line = test
            lines.append(line)
        self._wrap_cache = {"key": key, "lines": lines}
        return lines

    # ---------- Relações ----------
    def _draw_relacoes(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        groups = lore.load("relacoes").get("grupos", [])
        if not groups:
            return
        ov["sel"] = min(ov["sel"], len(groups) - 1)
        lw = int(w * 0.22)
        for k, g in enumerate(groups):
            on = k == ov["sel"]
            tag = f"ov_rg_{k}"
            if on:
                self._round_rect(x - 10, y + k * 34 - 5, x + lw, y + k * 34 + 25, 10, fill="#1b2230", outline="")
            c.create_text(x, y + k * 34, anchor="nw", text=g["nome"], fill=A.WHITE if on else A.MUTED,
                          font=self.f["btn"], tags=(tag,))
            self._clickable(tag, lambda k=k: (self.overlay.__setitem__("sel", k), self._sound("select"), self.refresh()))
        g = groups[ov["sel"]]
        self.stat_add("grupos", g["nome"])
        people = {p["id"]: p for p in characters.load()}
        members = [m for m in g["membros"] if m in people]
        gx, gw = x + lw + 30, w - lw - 30
        self._round_rect(gx - 10, y - 10, gx + gw + 10, bottom, 18, fill="#10141c", outline="#262d3a")
        cx, cy = gx + gw / 2, y + (bottom - y) / 2
        rx, ry = gw / 2 - 110, (bottom - y) / 2 - 90
        pos = {}
        for k, m in enumerate(members):
            ang = -math.pi / 2 + 2 * math.pi * k / len(members)
            pos[m] = (cx + rx * math.cos(ang), cy + ry * math.sin(ang))
        for a, b, label, kind in g.get("ligacoes", []):  # linhas primeiro, rostos por cima
            if a not in pos or b not in pos:
                continue
            (x1, y1), (x2, y2) = pos[a], pos[b]
            color = EDGE_COLORS.get(kind) or self.accent
            c.create_line(x1, y1, x2, y2, fill=color, width=2, dash=(6, 4) if kind == "inimigos" else None)
            mx, my = (x1 + x2) / 2, (y1 + y2) / 2
            tw = self.f["tiny"].measure(label) + 14
            self._round_rect(mx - tw / 2, my - 10, mx + tw / 2, my + 10, 9, fill="#0b0e14", outline=color)
            c.create_text(mx, my, text=label, fill=A.WHITE, font=self.f["tiny"])
        size = (72, 72)
        for m in members:
            px, py = pos[m]
            p = people[m]
            tag = f"ov_rn_{m}"
            path = characters.portrait_path(p)
            img = self._photo_fit(path, size, self._portraits, ("rel", m), 36, contain=False) if path else None
            if img:
                c.create_image(px, py, image=img, tags=(tag,))
            else:
                c.create_oval(px - 36, py - 36, px + 36, py + 36, fill="#1b2230", outline="", tags=(tag,))
            c.create_oval(px - 37, py - 37, px + 37, py + 37, outline=A.MUTED, width=2, tags=(tag,))
            c.create_text(px, py + 46, text=p["nome"], fill=A.WHITE, font=self.f["small"], tags=(tag,))
            self._clickable(tag, lambda m=m: self._open_person(m))
        lx = gx + 10
        for kind, label in (("familia", "família"), ("aliados", "aliados"), ("inimigos", "inimigos")):
            color = EDGE_COLORS.get(kind) or self.accent
            c.create_line(lx, bottom - 22, lx + 26, bottom - 22, fill=color, width=2, dash=(6, 4) if kind == "inimigos" else None)
            c.create_text(lx + 32, bottom - 22, anchor="w", text=label, fill=A.MUTED, font=self.f["tiny"])
            lx += 110

    def _open_person(self, pid):
        """Abre a ficha do personagem na tela Personagens."""
        people = characters.load()
        i = next((k for k, p in enumerate(people) if p["id"] == pid), 0)
        self.open_overlay("personagens")
        self.overlay.update(filtro="todos", sel=i)
        self.refresh()

    # ---------- Vírus / substâncias ----------
    def _fetch_virus_images(self):
        items = [dict(v, id="virus_" + v["id"]) for v in lore.load("virus").get("itens", [])]
        missing = [v for v in items if not characters.portrait_path(v)]
        if not missing:
            return

        def work():
            for v in missing:
                if characters.download_portrait(v):
                    self.after(0, self.refresh)
        threading.Thread(target=work, daemon=True).start()

    def _person_chips(self, ids, x, y, right, bottom, prefix):
        people = {p["id"]: p for p in characters.load()}
        ax, ay = x, y
        for pid in ids:
            p = people.get(pid)
            if not p:
                continue
            cw = self.f["small"].measure(p["nome"]) + 26
            if ax + cw > right:
                ax, ay = x, ay + 34
            if ay + 28 > bottom:
                break
            ax = self._chip(ax, ay, p["nome"], lambda m=pid: self._open_person(m), f"{prefix}_{pid}") + 8
        return ay + 34

    def _draw_virus(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        items = lore.load("virus").get("itens", [])
        if not items:
            return
        ov["sel"] = min(ov["sel"], len(items) - 1)
        lw = int(w * 0.24)
        for k, v in enumerate(items):
            on = k == ov["sel"]
            tag = f"ov_vl_{v['id']}"
            ry = y + k * 40
            if ry + 30 > bottom:
                break
            if on:
                self._round_rect(x - 10, ry - 6, x + lw, ry + 30, 10, fill="#1b2230", outline="")
            c.create_text(x, ry, anchor="nw", text=v["nome"], fill=A.WHITE if on else A.MUTED, font=self.f["btn"], tags=(tag,))
            if v.get("ano"):
                c.create_text(x + lw - 14, ry + 2, anchor="ne", text=v["ano"], fill=A.DIM, font=self.f["small"], tags=(tag,))
            self._clickable(tag, lambda k=k: (self.overlay.__setitem__("sel", k), self._sound("select"), self.refresh()))
        v = items[ov["sel"]]
        self.stat_add("virus", v["id"])
        dx, right = x + lw + 40, x + w
        self._round_rect(dx - 20, y - 10, right + 20, bottom, 18, fill="#10141c", outline="#262d3a")
        path = characters.portrait_path({"id": "virus_" + v["id"]})
        big = (220, 220)
        img = self._photo_fit(path, big, self._portraits, ("virus", v["id"]), 14, contain=True, bg=(16, 20, 28)) if path else None
        if img:
            c.create_image(dx, y + 6, image=img, anchor="nw")
        tx = dx + big[0] + 26
        tw = right - tx
        name = c.create_text(tx, y + 6, anchor="nw", text=v["nome"], fill=A.WHITE, font=self.f["title"], width=tw)
        ty = c.bbox(name)[3] + 6
        if v.get("ano"):
            c.create_text(tx, ty, anchor="nw", text=f"Desde {v['ano']}", fill=self.accent, font=self.f["btn"])
            ty += 28
        for label, key in (("ORIGEM", "origem"), ("COMO AGE", "efeito")):
            if v.get(key):
                c.create_text(tx, ty, anchor="nw", text=label, fill=A.MUTED, font=self.f["tiny"])
                t = c.create_text(tx, ty + 18, anchor="nw", text=v[key], fill="#d5d9e0", font=self.f["body"], width=tw)
                ty = c.bbox(t)[3] + 14
        sy = max(ty, y + big[1] + 24)
        for label, key, prefix in (("CRIADO POR", "criadores", "ov_vc"), ("INFECTADOS E HOSPEDEIROS", "infectados", "ov_vi")):
            if v.get(key):
                c.create_text(dx, sy, anchor="nw", text=label, fill=A.MUTED, font=self.f["tiny"])
                sy = self._person_chips(v[key], dx, sy + 22, right, bottom - 10, prefix) + 6
        if v.get("aparicoes"):
            c.create_text(dx, sy, anchor="nw", text="APARECE EM", fill=A.MUTED, font=self.f["tiny"])
            ax, ay = dx, sy + 22
            titles = self._chapter_titles()
            for cid in v["aparicoes"]:
                label = titles.get(cid)
                if not label:
                    continue
                cw = self.f["small"].measure(label) + 26
                if ax + cw > right:
                    ax, ay = dx, ay + 34
                if ay + 28 > bottom - 10:
                    break
                ax = self._chip(ax, ay, label, lambda c_=cid: self.goto_chapter(c_), f"ov_va_{cid}") + 8

    # ---------- Conquistas do hub ----------
    def achievements(self):
        """[(id, nome, descrição, atual, meta)] calculadas a partir do que o hub sabe."""
        games = [g for g in self.games if g.get("tipo") != "info"]
        canon = [ch for ch in catalog.load_timeline(self.games, "canon") if any(v.get("tipo") != "info" for v in ch["versoes"])]
        played = lambda g: bool(self.last_played(g))  # noqa: E731
        played_canon = sum(1 for ch in canon if any(played(v) for v in ch["versoes"]))
        states = [s for s in self.trophy_state.values() if s and "erro" not in s and s.get("total")]
        plats = sum(1 for s in states if s["platina"])
        got = sum(s["conquistados"] for s in states)
        rare = min((it["raridade"] for s in states for it in (s.get("raros") or []) + (s.get("recentes") or [])
                    if it.get("conquistado") and it.get("raridade") is not None), default=None)
        appids = {g.get("appid") for g in games}
        minutes = sum(p.get("minutos", 0) for appid, p in self.playtimes().items() if appid in appids)
        out = [("primeiro", "Primeiro passo", f"Jogar um jogo de {FR['nome']}", min(1, sum(map(played, games))), 1),
               ("linha", "Linha do tempo completa", "Jogar todos os capítulos da história oficial", played_canon, len(canon) or 1),
               ("platina1", "Platina!", "Conseguir a primeira platina", min(plats, 1), 1),
               ("platina5", "Mestre da franquia", "Conseguir 5 platinas", min(plats, 5), 5),
               ("trofeus100", "Caçador de troféus", "Conquistar 100 troféus", min(got, 100), 100),
               ("trofeus500", "Colecionador de troféus", "Conquistar 500 troféus", min(got, 500), 500),
               ("raro", "Raridade", "Conseguir um troféu que menos de 5% dos jogadores têm", int(rare is not None and rare < 5), 1),
               ("horas10", "Sobrevivente", "Jogar 10 horas da franquia", min(minutes // 60, 10), 10),
               ("horas50", "Veterano", "Jogar 50 horas da franquia", min(minutes // 60, 50), 50),
               ("horas100", "Lenda", "Jogar 100 horas da franquia", min(minutes // 60, 100), 100),
               ("foto", "Fotógrafo", "Tirar uma foto do card", min(self._stat("fotos"), 1), 1),
               ("fichas", "Enciclopédia", "Ver 25 fichas de personagens", min(self._stat("fichas"), 25), 25)]
        if self._file_chapters():
            out.append(("arquivos", "Arquivista", "Ler 10 arquivos dos jogos", min(self._stat("arquivos"), 10), 10))
        mapa = lore.load("mapa")
        if mapa:
            total = len(mapa.get("mundo", [])) + len(mapa.get("cidade", {}).get("locais", []))
            out.append(("mapa", "Turista", "Visitar todos os lugares do mapa", min(self._stat("locais"), total), total))
        virus = lore.load("virus").get("itens", [])
        if virus:
            out.append(("virus", "Cientista", "Ler todas as fichas de " + lore.load("virus").get("titulo", "vírus").lower(),
                        min(self._stat("virus"), len(virus)), len(virus)))
        groups = lore.load("relacoes").get("grupos", [])
        if groups:
            out.append(("relacoes", "Genealogista", "Ver todos os grupos de relações", min(self._stat("grupos"), len(groups)), len(groups)))
        out.append(("speedrun", "De olho no recorde", "Ver os recordes de speedrun de 5 jogos", min(self._stat("speedrun"), 5), 5))
        for ch in catalog.load_timeline(self.games, "canon") + catalog.load_timeline(self.games, "spinoff"):
            vs = [v for v in ch["versoes"] if v.get("tipo") != "info"]
            if len(vs) >= 2:  # "jogou todas as versões do RE2"
                out.append((f"versoes_{ch['id']}", f"Todas as versões: {ch['titulo']}",
                            f"Jogar as {len(vs)} versões de {ch['titulo']}", sum(map(played, vs)), len(vs)))
        return out

    def check_achievements(self):
        """Avisa (com som de troféu) as conquistas do hub que acabaram de ser liberadas."""
        try:
            done = set(self.cfg.get("_conquistas").get("ids", []))
            new = [a for a in self.achievements() if a[3] >= a[4] and a[0] not in done]
        except Exception:
            return
        if not new:
            return
        self.cfg.set("_conquistas", ids=sorted(done | {a[0] for a in new}))
        if done or len(new) < 4:  # na primeira vez não enche a tela de avisos
            for a in new[:3]:
                self.toast(f"Conquista do hub: {a[1]}", a[2], lambda: self.open_overlay("conquistas"))
        else:
            self.toast(f"{len(new)} conquistas do hub liberadas", "Clique para ver", lambda: self.open_overlay("conquistas"))

    def _draw_conquistas(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        items = self.achievements()
        done = sum(1 for a in items if a[3] >= a[4])
        c.create_text(x, y - 6, anchor="nw", text=f"{done} de {len(items)} conquistas", fill=A.WHITE, font=self.f["h"])
        y += 34
        cols = 3
        gap = 16
        cw = (w - gap * (cols - 1)) / cols
        ch = 78
        rows_fit = max(1, int((bottom - y + gap) // (ch + gap)))
        total_rows = (len(items) + cols - 1) // cols
        ov["sel"] = min(ov["sel"], max(0, total_rows - rows_fit))
        for k, (aid, name, desc, cur, goal) in enumerate(items[ov["sel"] * cols:(ov["sel"] + rows_fit) * cols]):
            ax, ay = x + (k % cols) * (cw + gap), y + (k // cols) * (ch + gap)
            ok = cur >= goal
            self._round_rect(ax, ay, ax + cw, ay + ch, 14, fill="#161c27" if ok else "#11151d",
                             outline=self.accent if ok else "#232a36")
            self._cup(ax + 30, ay + 36, 13, A.TIER_COLORS["ouro"] if ok else A.DIM, dim=not ok)
            c.create_text(ax + 58, ay + 12, anchor="nw", text=self._elide(name, self.f["btn"], cw - 70),
                          fill=A.WHITE if ok else A.MUTED, font=self.f["btn"])
            c.create_text(ax + 58, ay + 34, anchor="nw", text=self._elide(desc, self.f["small"], cw - 70),
                          fill=A.MUTED, font=self.f["small"])
            bw = cw - 70 - 60
            self._round_rect(ax + 58, ay + 58, ax + 58 + bw, ay + 63, 3, fill=A.CHIP, outline="")
            if cur:
                self._round_rect(ax + 58, ay + 58, ax + 58 + max(5, bw * min(1, cur / goal)), ay + 63, 3,
                                 fill=self.accent if not ok else A.TIER_COLORS["ouro"], outline="")
            c.create_text(ax + cw - 14, ay + 60, anchor="e", text=f"{cur}/{goal}", fill=A.MUTED, font=self.f["tiny"])
        if total_rows > rows_fit:
            c.create_text(x + w, bottom, anchor="se", text="role para ver mais", fill=A.DIM, font=self.f["small"])

    # ---------- aba Speedrun do painel ----------
    def _draw_speedrun(self, g, x, y, w, bottom):
        c = self.c
        data = self._async(self._speedruns, g["id"], lambda: lore.speedrun(g))
        if data is None:
            return self._note(x, y, w, "Buscando os recordes no speedrun.com...")
        if "erro" in data:
            self._note(x, y, w, "Não consegui falar com o speedrun.com agora (sem internet ou muitas consultas).")
            self._chip(x, y + 56, "Tentar de novo", lambda: (self._speedruns.pop(g["id"], None), self.refresh()), "sr_retry")
            return
        if not data.get("jogo"):
            return self._note(x, y, w, "Não encontrei este jogo no speedrun.com.")
        self.stat_add("speedrun", g["id"])
        c.create_text(x, y - 4, anchor="nw", text=self._elide(data["jogo"], self.f["h"], w - 150), fill=A.WHITE, font=self.f["h"])
        if data.get("link"):
            self._chip(x + w, y - 8, "speedrun.com  ›", lambda: webbrowser.open(data["link"]), "sr_site", anchor="e")
        recs = data.get("recordes", [])
        if not recs:
            return self._note(x, y + 34, w, "Ainda não há recordes neste jogo.")

        def row(r, ry):
            tag = f"sr_{abs(hash(r['link'])) % 10 ** 9}"
            tt = lore.fmt_time(r["tempo"])
            c.create_text(x + w, ry, anchor="ne", text=tt, fill=self.accent, font=self.f["h"], tags=(tag,))
            tw = w - self.f["h"].measure(tt) - 14
            c.create_text(x, ry, anchor="nw", text=self._elide(r["categoria"], self.f["btn"], tw), fill=A.WHITE,
                          font=self.f["btn"], tags=(tag,))
            who = f"{r['jogador']}" + (f"  ·  {r['data'][8:10]}/{r['data'][5:7]}/{r['data'][:4]}" if r.get("data") else "")
            c.create_text(x, ry + 22, anchor="nw", text=self._elide(who, self.f["small"], w), fill=A.MUTED,
                          font=self.f["small"], tags=(tag,))
            if r.get("link"):
                self._clickable(tag, lambda u=r["link"]: webbrowser.open(u))
        self._list_window(recs, x, y + 30, w, bottom, 50, row)

    def _lore_init(self):
        self._map_cache, self._files, self._file_texts, self._speedruns = {}, {}, {}, {}
        self._wrap_cache = {}
