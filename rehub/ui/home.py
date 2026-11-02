"""Tela principal desenhada no canvas: topo (logo, seções, relógio), barra de baixo, carrossel de capas,
detalhes do jogo escolhido e a troca suave do fundo. Mixin do Hub (rehub/ui/app.py)."""
import hashlib
import random
import re
import threading
import time
import webbrowser

from PIL import Image, ImageTk

from .. import catalog, channels, fonts, store
from ..franchise import FR, hex_rgb
from ..paths import COVERS, ROOT
from . import app as A, skin
from .art import (DIM, DIM_LUT, GAP, GREEN, HOVER_LIFT, HOVER_SCALE, MARGIN, MUTED, RED, TIER_COLORS, TILES_Y, WHITE, Font,
                  accent_from, compose_background, ease, make_halo, make_poster, make_tile)


class Home:
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
        c.tag_raise("toast")  # avisos sempre por cima das capas
        c.tag_raise("navitem")   # a prévia das lives (aberta no menu) fica por cima das capas

    def _preload(self):
        """Em segundo plano: abre do disco as artes e monta as capas grandes, para a troca de capítulo não travar."""
        skin.warm()
        sections = [catalog.load_timeline(self.games, s) for s, _ in A.SECTIONS]
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
                    self._logo_pil_of(key)   # logo já recortado e reduzido: na troca só vira PhotoImage

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
            own = ROOT / FR["logo_arquivo"] if FR.get("logo_arquivo") else None
            logo = own if own and own.exists() else COVERS / "_serie_logo.png"
            if logo.exists():
                img = Image.open(logo).convert("RGBA")
                img = img.crop(img.getbbox() or (0, 0, *img.size))
                h = 30 if img.width / img.height < 6 else 24  # logos bem largos (ex.: SILENT HILL) ficam mais baixos
                img = img.resize((min(220, int(img.width * h / img.height)), h), Image.LANCZOS)
                if logo != own:   # o baixado é pintado na cor do app; o próprio (re_logo.png) fica com as cores dele
                    red = Image.new("RGBA", img.size, (*FR["logo_cor"], 255))
                    red.putalpha(img.getchannel("A"))
                    img = red
                parts.append(img)
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

    NAV_ICONS = {"canon": "timeline", "spinoff": "grid", "perdidos": "question", "midia": "play", "hqs": "image",
                 "fas": "users", "noticias": "doc", "canais": "tv"}

    def _draw_nav(self):
        """Seções do topo em círculos com ícone; a escolhida e a que está sob o mouse abrem com o nome.
        Só estes itens são redesenhados quando o mouse passa (não a tela toda)."""
        c, x = self.c, self._nav_x0
        c.delete("navitem")
        self._nav_rects = []
        for key, label in A.SECTIONS:
            on = self.section == key
            tag = f"nav_{key}"
            ph = skin.nav_photo(self.NAV_ICONS.get(key, "grid"), label, expanded=on or key == self._nav_hover, on=on,
                                focus=on and self.nav_focus)
            c.create_image(x, 38, image=ph, anchor="w", tags=(tag, "navitem"))
            self._nav_rects.append((key, x, 18, x + ph.width(), 58))
            self._clickable(tag, lambda k=key: (setattr(self, "overlay", None), self.set_section(k), self.refresh()))
            if key == "canais" and (self._nav_hover == "canais" or (self.nav_focus and on)):
                self._live_peek(x)
            x += ph.width() + 10
        self._nav_end = x + 18
        if not (self._nav_hover == "canais" or (self.nav_focus and self.section == "canais")):
            self._peek_rect = None

    def _live_peek(self, x):
        """Prévia das lives no ícone de Canais: as primeiras que estão no ar agora, com a imagem de cada uma."""
        st = channels.cached()
        lives = (st.get("lives", []) + st.get("descobertas", []))[:4]
        c, W = self.c, self.c.winfo_width()
        pw, rh = 380, 84
        x1 = max(MARGIN, min(x - 20, W - MARGIN - pw))
        y1 = 66
        y2 = y1 + 46 + (len(lives) * rh if lives else 40)
        self._peek_rect = (x1, 18, x1 + pw, y2)
        self._round_rect(x1, y1, x1 + pw, y2, 8, fill="#121010", outline="#3b342d", tags=("navitem",))
        c.create_text(x1 + 16, y1 + 22, anchor="w", text="AO VIVO AGORA", fill=WHITE, font=self.f["tiny"], tags=("navitem",))
        c.create_oval(x1 + pw - 26, y1 + 18, x1 + pw - 18, y1 + 26, fill="#e0242e", outline="", tags=("navitem",))
        if not lives:
            c.create_text(x1 + 16, y1 + 62, anchor="w", text="Nenhuma live de Resident Evil agora.", fill=MUTED,
                          font=self.f["small"], tags=("navitem",))
            return
        for k, l in enumerate(lives):
            ry = y1 + 44 + k * rh
            tag = f"peek_{k}"
            c.create_rectangle(x1 + 6, ry - 2, x1 + pw - 6, ry + rh - 6, fill="#121010", outline="", tags=(tag, "navitem"))
            url = l.get("imagem")   # a Twitch troca a imagem da live no mesmo endereço: pede de novo a cada 5 min
            img = self._remote_img(f"{url}?t={int(time.time() // 300)}" if url and l["plataforma"] == "twitch" else url, (124, 70), 4)
            if img:
                c.create_image(x1 + 14, ry, image=img, anchor="nw", tags=(tag, "navitem"))
            else:
                c.create_rectangle(x1 + 14, ry, x1 + 138, ry + 70, fill="#1f1b18", outline="", tags=(tag, "navitem"))
            c.create_rectangle(x1 + 18, ry + 4, x1 + 58, ry + 18, fill="#e0242e", outline="", tags=(tag, "navitem"))
            c.create_text(x1 + 38, ry + 11, text="AO VIVO", fill="white", font=self.f["tiny"], tags=(tag, "navitem"))
            title = c.create_text(x1 + 150, ry + 2, anchor="nw", text=self._elide(l["titulo"], self.f["small"], pw - 166),
                                  fill=WHITE, font=self.f["small"], tags=(tag, "navitem"))
            who = l["canal"] + (f"  ·  {l['espectadores']} assistindo" if l.get("espectadores") else "")
            c.create_text(x1 + 150, ry + 24, anchor="nw", text=self._elide(who, self.f["small"], pw - 166), fill=MUTED,
                          font=self.f["small"], tags=(tag, "navitem"))
            plat = "Twitch" if l["plataforma"] == "twitch" else "YouTube"
            c.create_text(x1 + 150, ry + 46, anchor="nw", text=self._elide(f"{plat}  {l.get('categoria') or ''}", self.f["tiny"], pw - 166),
                          fill="#b18cff" if plat == "Twitch" else "#ff6b6b", font=self.f["tiny"], tags=(tag, "navitem"))
            self._clickable(tag, lambda u=l["link"]: webbrowser.open(u), hover=[(title, WHITE, "#ffd9dc")])

    def _draw_header(self, W):
        c = self.c
        brand = self._brand()
        if brand:
            c.create_image(MARGIN, 38, image=brand, anchor="w", tags=("home",))
            x = MARGIN + brand.width() + 34
        else:
            c.create_text(MARGIN, 38, anchor="w", text=FR["nome"].upper(), fill=RED, font=self.f["logo"], tags=("home",))
            x = MARGIN + self.f["logo"].measure(FR["nome"].upper()) + 30
        self._clickable("home", self.go_home)
        self._nav_x0 = x
        self._draw_nav()
        x = self._nav_end
        self._live_pill_show(x - 12, 38)   # selo AO VIVO pulsando quando algum canal está transmitindo

        right = W - MARGIN
        if self.attributes("-fullscreen"):  # sem barra de título: botão para fechar
            tag = "quit"
            x_item = c.create_text(right, 38, anchor="e", text="✕", fill=MUTED, font=self.f["h"], tags=(tag,))
            self._clickable(tag, self.ask_quit, hover=[(x_item, MUTED, WHITE)])
            right -= 34
        c.create_text(right, 38, anchor="e", text=time.strftime("%H:%M"), fill=WHITE, font=self.f["clock"])
        right -= self.f["clock"].measure("00:00") + 28
        loaded = [s for s in self.trophy_state.values() if s and "erro" not in s]
        plats, got = sum(s["platina"] for s in loaded), sum(s["conquistados"] for s in loaded)
        text = f"{plats}   ·   {got} troféus"
        tw = self.f["h"].measure(text) + 40
        if self.trophy_state and right - tw > self._nav_end + 20:  # sem jogos da Steam ou sem espaço: não mostra
            c.create_text(right, 38, anchor="e", text=text, fill=WHITE, font=self.f["h"], tags=("profile",))
            x = right - self.f["h"].measure(text) - 12
            self._cup(x - 8, 38, 9, TIER_COLORS["platina"])
            if self.persona and x - 40 - self.f["body"].measure(self.persona) > self._nav_end + 20:
                c.create_text(x - 28, 38, anchor="e", text=self.persona, fill=MUTED, font=self.f["body"], tags=("profile",))
            self._clickable("profile", lambda: self.open_overlay("perfil"))

    def _draw_bottom_bar(self, W, H):
        c, y = self.c, H - 32
        x = W - MARGIN
        order = {"historia": "História", "lancamento": "Lançamento", "recentes": "Recentes"}[self.order]
        chips = [("Opções", self._options_menu, False), ("Extras", lambda: self.open_overlay("extras"), False),
                 ("Efeitos", self.toggle_effects, self.prefs["efeitos"]),
                 ("Trilha", self.toggle_music, self.prefs["trilha"]),
                 ("Só instalados", self.toggle_installed, self.only_installed),
                 ("Ordem: " + order, self.toggle_order, False)]
        target = self.continue_target()
        if target:
            chips.append(("Continuar", self.continue_last, False))
        for label, cmd, on in chips:
            tag = "opt_" + label.split()[0].lower()
            opts = dict(style="on" if on else "plain", accent=self.accent, icon="dot" if on else None, height=28, size=9,
                        glow=6, pad=13, radius=14, track=0.6)
            normal = skin.button_photo(label, state="normal", **opts)
            hot = lambda label=label, opts=opts: skin.button_photo(label, state="hover", **opts)
            w = normal.width() - 12
            item = c.create_image(x - w - 6, y - 20, image=normal, anchor="nw", tags=(tag,))
            self._clickable(tag, cmd, hover=[(item, normal, hot)])
            x -= w + 8
        # atalhos como teclas: a tecla numa tampinha, o que ela faz ao lado; os que não cabem ficam de fora
        hints = (("A D / ← →", "capítulos"), ("W ↑", "menu"), ("S ↓", "versões"), ("Enter", "jogar"), ("G", "gerenciar"), ("Tab", "seção"),
                 ("E", "extras"), ("F", "foto"), ("F11", "tela cheia"))
        lf = self.f["small"]
        hx, limit = MARGIN, x - 16
        for key, label in hints:
            cap = skin.keycap_photo(key)
            kw = cap.width()
            need = kw + 8 + lf.measure(label) + 22
            if hx + need > limit:
                break
            c.create_image(hx, y - 11, image=cap, anchor="nw")
            c.create_text(hx + kw + 8, y, anchor="w", text=label, fill=MUTED, font=lf)
            hx += need

    def _draw_carousel(self, W):
        c = self.c
        n, s = self.tile_n, self.tile_s
        g = ease(self._grow)  # o card aberto cresce do tamanho normal até o grande
        sel_size = (int(n[0] + (s[0] - n[0]) * g), int(n[1] + (s[1] - n[1]) * g))
        step = n[0] + GAP
        first_x = MARGIN + (step if self.sel > 0 else 0) + self._slide  # mostra um capítulo anterior, como na PS5
        line_y = TILES_Y + s[1] + 30
        centers, self._tile_rects = [], []
        cont = self.continue_target()
        cont = cont[1]["id"] if cont else None
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
                glow = tuple(v // 16 * 16 for v in hex_rgb(self.accent))
                c.create_image(dx - 24, dy - 24, image=self._halo((w2, h2), glow, int(225 * g), 0), anchor="nw")
            c.create_image(dx - 24, dy - 24 + 4 * h, image=self._halo((w2, h2), (0, 0, 0), 150 + int(60 * h), 6), anchor="nw")
            dim = i != self.sel and h < 0.5  # os outros cards ficam um pouco apagados
            c.create_image(dx, dy, image=self._tile(ch, (w2, h2), dim), anchor="nw", tags=(f"tile{i}",))
            self._card_badges(ch, dx, dy, w2, i == self.sel, cont)
            self._tile_rects.append((i, x, TILES_Y - HOVER_LIFT, x + size[0], TILES_Y + size[1]))
            centers.append((x + size[0] / 2, i, ch))

        if centers:  # a linha do tempo embaixo das capas
            c.create_line(max(0, centers[0][0]), line_y, min(W, centers[-1][0]), line_y, fill=DIM, width=2)
            by_release = self.order == "lancamento" or self.section != "canon"  # fora da história oficial: ano de lançamento
            for cx, i, ch in centers:
                sel = i == self.sel
                r = 6 if sel else 4
                c.create_oval(cx - r, line_y - r, cx + r, line_y + r, fill=self.accent if sel else MUTED, outline="")
                if self.section in ("fas", "noticias", "canais"):  # fãs: o tipo; notícias: a data  # projetos de fãs: o tipo (Patch, Remaster, Fan film...)
                    label = ch.get("categoria", "")
                else:
                    label = str(ch.get("lancamento", "")) if by_release else self._story_year(ch)
                c.create_text(cx, line_y + 18, text=label, fill=WHITE if sel else DIM, font=self.f["tiny"])

    def _card_badges(self, ch, x, y, w, selected, cont_id):
        """Selos sobre o card: CONTINUAR (jogado por último), promoção da Steam e contagem regressiva."""
        c = self.c
        if ch["id"] == cont_id:
            c.create_text(x + 2, y - 8, anchor="sw", text="CONTINUAR", fill=self.accent if selected else MUTED,
                          font=self.f["tiny"])
        g = self.version_of(ch)
        badge = None
        rel = self.release(ch, g)
        if rel:
            badge = (self.countdown(rel, short=True), "#3a2a22", "#e9dfc9")
        else:
            sale = next(((v, p) for v in ch["versoes"] if (p := self.price_of(v)) and p["desconto"] and not self.owned(v)), None)
            if sale:
                badge = (f"-{sale[1]['desconto']}%", "#4c7a1f", "#d6f5a8")
        if badge:
            text, bg, fg = badge
            bw = self.f["tiny"].measure(text) + 14
            self._round_rect(x + w - bw - 6, y + 6, x + w - 6, y + 26, 8, fill=bg, outline="")
            c.create_text(x + w - 6 - bw / 2, y + 16, text=text, fill=fg, font=self.f["tiny"])

    def _halo(self, size, color, alpha, dy):
        """Sombra/brilho de card. Desfoca UMA vez no tamanho grande e só redimensiona depois
        (desfocar de novo para cada tamanho da animação era o que mais pesava)."""
        size = (size[0] // 8 * 8, size[1] // 8 * 8)
        alpha = alpha if alpha >= 200 else (alpha // 60 * 60 or (15 if alpha else 0))
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
            if dim:   # escurece RGB e mantém a transparência numa passada só (separar os canais pesava)
                img = img.point(DIM_LUT)
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
        cached = A.CARDS / name
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
                A.CARDS.mkdir(parents=True, exist_ok=True)
                img.save(cached)
            except OSError:
                pass
        self._tile_base[base_key] = img
        return base_key

    def _logo_pil_of(self, key, max_size=(400, 84)):
        """Logo recortado e reduzido (PIL). Pode rodar fora da interface (pré-carga)."""
        if not hasattr(self, "_logo_pil"):
            self._logo_pil = {}
        if key not in self._logo_pil:
            p = store.art_path(key, "logo") if key else None
            img = None
            if p:
                try:
                    img = Image.open(p).convert("RGBA")
                    bbox = img.getbbox()  # corta a margem transparente
                    img = img.crop(bbox) if bbox else img
                    img.thumbnail(max_size, Image.LANCZOS)
                except OSError:
                    img = None
            if img is None:
                return None   # sem logo ainda: tenta de novo quando a arte chegar
            self._logo_pil[key] = img
        return self._logo_pil[key]

    def _logo(self, g, max_size=(400, 84)):
        if g is None:
            return None
        key = store.art_key(g)
        if key not in self._logos:
            img = self._logo_pil_of(key, max_size)
            if img is None:
                return None
            self._logos[key] = ImageTk.PhotoImage(img)
        return self._logos[key]

    def _title_font(self, ch):
        """Título com uma fonte parecida com a do logo do jogo (rehub/fonts.py); sem ela, a fonte padrão."""
        key = fonts.key_for(ch)
        got = fonts.ensure(key) if key else None
        if not got:
            return self.f["title"]
        news = ch.get("secao") in ("noticias", "canais")  # manchetes e títulos de vídeo são longos: letra menor para caber
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
            syn = c.create_text(x, y, anchor="nw", text=ch["sinopse"], fill="#d9d2c5", font=self.f["body"], width=min(w, 640))
            y = c.bbox(syn)[3] + 16

        if len(ch["versoes"]) > 1:  # versoes: pílulas num trilho escuro, a escolhida clara (como na PS5)
            opts = dict(accent=self.accent, height=28, size=9, glow=0, pad=14, radius=14, track=0.6)
            pills = [(skin.button_photo(v["versao"], style="seg_on" if v is g else "seg", state="normal", **opts), v)
                     for v in ch["versoes"]]
            maxw = min(w, 760)
            rows, cur, cw = [], [], 0
            for j, (ph, _v) in enumerate(pills):   # quebra em mais linhas se nao couber
                if cur and cw + ph.width() + 2 > maxw:
                    rows.append(cur); cur, cw = [], 0
                cur.append(j); cw += ph.width() + 2
            rows.append(cur)
            for r in rows:
                total = sum(pills[j][0].width() + 2 for j in r) + 6
                c.create_image(x, y, image=skin.track_photo(total, 36), anchor="nw")
                px = x + 4
                for j in r:
                    ph, v = pills[j]
                    tag = f"ver{j}"
                    item = c.create_image(px, y + 4, image=ph, anchor="nw", tags=(tag,))
                    hot = None if v is g else [(item, ph, lambda t=v["versao"]: skin.button_photo(t, style="seg", state="hover", **opts))]
                    self._clickable(tag, lambda j=j: self.pick_version(0, absolute=j), hover=hot)
                    px += ph.width() + 2
                y += 46
        elif g["tipo"] != "info":  # nos itens de informação o formato já aparece na linha de estado
            c.create_text(x, y, anchor="nw", text=g.get("versao", ""), fill=DIM, font=self.f["small"])
            y += 24

        state, color = self._state(g)
        task = next((tk for tk in self.tasks if tk.gid in (g["id"], ch["id"])), None)
        if task:   # download/conversão deste jogo: a linha de estado vira o progresso, com a barra e Cancelar
            line = c.create_text(x, y, anchor="nw", text=task.line(), fill=GREEN, font=self.f["body"])
            bw = max(320, c.bbox(line)[2] - x)
            c.create_rectangle(x, y + 26, x + bw, y + 29, fill="#2a2522", outline="")
            c.create_rectangle(x, y + 26, x + bw * task.frac(), y + 29, fill=self.accent, outline="")
            cx = c.create_text(x + bw + 16, y + 27, anchor="w", text="Cancelar", fill=MUTED, font=self.f["small"],
                               tags=("task_cancel",))
            self._clickable("task_cancel", lambda tk=task: tk.cancel(), hover=[(cx, MUTED, WHITE)])
            y += 14
        item = c.create_text(x, y, anchor="nw", text="" if task else (self.status_text or state), fill=color,
                             font=self.f["body"])
        if not self.status_text and not task:
            sx = c.bbox(item)[2]
            for text, col, cmd in self._extra_state(ch, g):
                sep = c.create_text(sx, y, anchor="nw", text="   ·   ", fill=DIM, font=self.f["body"])
                sx = c.bbox(sep)[2]
                tag = f"st_{abs(hash(text)) % 10 ** 8}" if cmd else ""
                it = c.create_text(sx, y, anchor="nw", text=text, fill=col, font=self.f["body"], tags=(tag,) if tag else ())
                if cmd:
                    self._clickable(tag, cmd)
                sx = c.bbox(it)[2]
        y += 32
        bx = x
        for k, (text, cmd, primary) in enumerate(self._actions(g)):
            bx = self._button(bx, y, text, cmd, primary, f"btn{k}") + 10
