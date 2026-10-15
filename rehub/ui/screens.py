"""Telas por cima do hub (estilo PS5): Extras, Perfil, Linha da história, Personagens, Ofertas, visualizador de
prints, e a foto do card. Tudo desenhado no mesmo canvas da tela principal; o Hub herda daqui (mixin)."""
import hashlib
import math
import os
import re
import threading
import time
import webbrowser
from datetime import datetime

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageTk

from .. import catalog, characters, deals, library, steam, store, trophies
from ..franchise import FR
from ..paths import DATA, ROOT
from . import app as A
from .lore_screens import LORE_KINDS

THUMBS = DATA / "cache" / "prints"
EXTRAS = (("perfil", "Perfil", "Troféus, horas e progresso na franquia", "P"),
          ("historia", "Linha da história", "Todos os capítulos em ordem, ano a ano", "H"),
          ("personagens", "Personagens", "Quem é quem e em quais jogos aparece", "C"),
          ("ofertas", "Ofertas e lançamentos", "Promoções da Steam, lista de desejos e contagem regressiva", "L"),
          ("foto", "Foto do card", "Salva uma imagem do jogo selecionado para postar", "F"))


class Screens:
    # ---------- abrir, fechar, teclas ----------
    def open_overlay(self, kind, **state):
        if kind == "foto":
            return self.photo_card()
        self._trailer_stop()
        self.overlay = {"kind": kind, "sel": 0, "scroll": 0, **state}
        if kind == "personagens":
            self._fetch_portraits()
        elif kind == "historia":
            self.overlay["items"] = self._story_items()
            cur = self.chapter["id"] if self.chapter and self.section == "canon" else None
            self.overlay["sel"] = next((i for i, it in enumerate(self.overlay["items"]) if it["ch"]["id"] == cur), 0)
        elif kind == "ofertas":
            self.refresh_deals()
        elif kind in LORE_KINDS:
            self._lore_open(kind)
        self._sound("open")
        self.refresh()

    def close_overlay(self):
        if self.overlay:
            self.overlay = None
            self._sound("back")
            self.refresh()

    def _ov_press(self, action):
        ov = self.overlay
        kind = ov["kind"]
        if action == "back":
            return self.close_overlay()
        if kind == "viewer":
            if action in ("left", "right"):
                return self._viewer_go(-1 if action == "left" else 1)
            if action == "enter":
                return self._viewer_open()
            if action == "photo":
                return self._viewer_set_bg()
            return
        if kind in LORE_KINDS:
            return self._lore_press(kind, action)
        if kind == "extras":
            items = self._extras()
            n, cols = len(items), 5
            if action == "left":
                ov["sel"] = (ov["sel"] - 1) % n
            elif action == "right":
                ov["sel"] = (ov["sel"] + 1) % n
            elif action in ("up", "down"):
                ov["sel"] = max(0, min(n - 1, ov["sel"] + (cols if action == "down" else -cols)))
            elif action == "enter":
                return self.open_overlay(items[ov["sel"]][0])
            self._sound("select")
            return self.refresh()
        if kind == "historia":
            n = len(ov["items"])
            if action in ("left", "right", "up", "down") and n:
                ov["sel"] = max(0, min(n - 1, ov["sel"] + (-1 if action in ("left", "up") else 1)))
                self._sound("select")
            elif action == "enter" and n:
                return self._story_open(ov["sel"])
            return self.refresh()
        if kind == "personagens":
            people = self._people()
            cols = ov.get("cols", 4)
            delta = {"left": -1, "right": 1, "up": -cols, "down": cols}.get(action)
            if delta and people:
                ov["sel"] = max(0, min(len(people) - 1, ov["sel"] + delta))
                self._sound("select")
            elif action in ("next_section", "prev_section"):  # Tab / LB / RB: troca o filtro
                keys = [k for k, _ in self._people_filters()]
                self._set_people_filter(keys[(keys.index(ov.get("filtro", "todos")) + (1 if action == "next_section" else -1)) % len(keys)])
            elif action in ("tab_prev", "tab_next") and people:  # PageUp / PageDown / LT / RT: troca a versão
                self._step_version(people[min(ov["sel"], len(people) - 1)], -1 if action == "tab_prev" else 1)
            elif action == "enter" and people:
                apps = people[ov["sel"]].get("aparicoes", [])
                if apps:
                    return self.goto_chapter(apps[0])
            return self.refresh()
        if kind in ("ofertas", "perfil"):
            if action in ("up", "down", "left", "right", "scroll_up", "scroll_down"):
                ov["sel"] = max(0, ov["sel"] + (-1 if action in ("up", "left", "scroll_up") else 1))
                self._sound("select")
            elif action == "enter" and kind == "ofertas":
                rows = ov.get("rows") or []
                if rows:
                    steam.store(rows[min(ov["sel"], len(rows) - 1)]["appid"])
            return self.refresh()

    def _ov_wheel(self, delta):
        kind = self.overlay["kind"]
        if kind == "viewer":
            return self._viewer_go(1 if delta < 0 else -1)
        if kind in LORE_KINDS:
            return self._lore_wheel(kind, delta)
        if kind == "personagens":
            self.overlay["scroll"] = max(0, self.overlay["scroll"] + (1 if delta < 0 else -1))
            self.overlay["scroll_by_wheel"] = True
            return self.refresh()
        self._ov_press("down" if delta < 0 else "up")

    def goto_chapter(self, cid, version_id=None):
        """Fecha a tela por cima e abre o capítulo (em qualquer seção) no hub."""
        for sec, _ in A.SECTIONS:
            if sec == "noticias":
                continue
            chs = catalog.load_timeline(self.games, sec)
            if self.only_installed and sec in ("canon", "spinoff"):
                self.only_installed = False
            idx = next((i for i, ch in enumerate(chs) if ch["id"] == cid), None)
            if idx is None:
                continue
            self.overlay = None
            if sec != self.section:
                self.set_section(sec)
            i = next((k for k, ch in enumerate(self.chapters) if ch["id"] == cid), 0)
            self.select(i)
            if version_id:
                ch = self.chapters[i]
                j = next((k for k, v in enumerate(ch["versoes"]) if v["id"] == version_id), None)
                if j is not None:
                    self.version_idx[ch["id"]] = j
            self._queue_music()
            self.refresh()
            return True
        return False

    # ---------- desenho comum ----------
    def _dim_bg(self):
        """O fundo da tela principal desfocado e escurecido, para as telas por cima."""
        key = self._bg_key
        if getattr(self, "_dim_key", None) != key or self._dim_photo is None:
            img = self._bg_pil.filter(ImageFilter.GaussianBlur(10))
            self._dim_photo = ImageTk.PhotoImage(ImageEnhance.Brightness(img).enhance(0.32))
            self._dim_key = key
        return self._dim_photo

    def _draw_overlay(self, W, H):
        c, ov = self.c, self.overlay
        kind = ov["kind"]
        if kind == "viewer":
            return self._draw_viewer(W, H)
        c.create_image(0, 0, image=self._dim_bg(), anchor="nw")
        self._draw_header(W)
        titles = {"extras": ("Extras", "Escolha com as setas (ou o controle) e Enter"),
                  "perfil": (self.persona or "Perfil", f"Seu progresso em {FR['nome']}"),
                  "historia": ("Linha da história", "Os capítulos na ordem dos acontecimentos. Enter abre no hub"),
                  "personagens": ("Personagens", "Tab troca o filtro · PageUp/PageDown (ou LT/RT) troca a versão · "
                                                 "clique num jogo para abrir no hub"),
                  "ofertas": ("Ofertas e lançamentos", "Preços da Steam Brasil. Clique para abrir na loja"),
                  **self._lore_titles()}
        title, sub = titles[kind]
        tx = A.MARGIN
        avatar = self._avatar() if kind == "perfil" else None
        if avatar:  # foto do perfil da Steam ao lado do nome
            c.create_image(tx, 98, image=avatar, anchor="nw")
            tx += 104
        c.create_text(tx, 100, anchor="nw", text=title, fill=A.WHITE, font=self.f["big"])
        c.create_text(tx, 160, anchor="nw", text=sub, fill=A.MUTED, font=self.f["body"])
        self._chip(W - A.MARGIN, 112, "✕  Fechar (Esc)", self.close_overlay, "ov_close", anchor="e")
        top, bottom = 206, H - 40
        getattr(self, f"_draw_{kind}")(A.MARGIN, top, W - 2 * A.MARGIN, bottom)

    def _photo_fit(self, path_or_img, size, cache, key, radius=10, contain=False, bg=(20, 24, 32)):
        """PhotoImage de uma imagem (caminho ou PIL) cortada ou contida no tamanho, com cantos arredondados."""
        k = (key, size, contain)
        if k in cache:
            return cache[k]
        try:
            img = path_or_img if isinstance(path_or_img, Image.Image) else Image.open(path_or_img)
            if contain:
                img = img.convert("RGBA")
                img.thumbnail(size, Image.LANCZOS)
                out = Image.new("RGBA", size, (*bg, 255))
                out.alpha_composite(img, ((size[0] - img.width) // 2, size[1] - img.height))
                img = A.rounded(out, radius)
            else:
                img = A.rounded(A.fit_cover(img.convert("RGB"), size, 0.2), radius)
        except OSError:
            return None
        if len(cache) > 300:
            cache.clear()
        cache[k] = ImageTk.PhotoImage(img)
        return cache[k]

    def _mini(self, g, size):
        """Capa pequena de um jogo/versão (para listas)."""
        key = store.art_key(g)
        p = store.art_path(key, "capa") if key else None
        if not p:
            return None
        return self._photo_fit(p, size, self._minis, ("capa", key), 5)

    # ---------- Extras ----------
    def _extras(self):
        return list(EXTRAS[:4]) + self._lore_extras() + [EXTRAS[4]]

    def _draw_extras(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        items = self._extras()
        cols, gap = 5, 18
        cw = (w - gap * (cols - 1)) / cols
        ch = min(170, (bottom - y - 90 - gap) / 2)
        for i, (kind, title, desc, key) in enumerate(items):
            cx = x + (i % cols) * (cw + gap)
            cy = y + (i // cols) * (ch + gap)
            on = i == ov["sel"]
            tag = f"ov_ex_{kind}"
            self._round_rect(cx, cy, cx + cw, cy + ch, 18, fill=A.CHIP_HI if on else "#141922",
                             outline=self.accent if on else "#262d3a", width=3 if on else 1, tags=(tag,))
            self._extra_icon(kind, cx + 28, cy + 34, A.WHITE if on else A.MUTED, tag)
            c.create_text(cx + 22, cy + 66, anchor="nw", text=title, fill=A.WHITE, font=self.f["h"], width=cw - 40, tags=(tag,))
            c.create_text(cx + 22, cy + 94, anchor="nw", text=desc, fill=A.MUTED, font=self.f["small"], width=cw - 40, tags=(tag,))
            c.create_text(cx + cw - 18, cy + ch - 14, anchor="se", text=key, fill=A.DIM, font=self.f["h"], tags=(tag,))
            self._clickable(tag, lambda k=kind: self.open_overlay(k))
        ty = y + ((len(items) + cols - 1) // cols) * (ch + gap) + 16
        tips = ["Teclado: P perfil · H história · C personagens · L ofertas · M mapa · A arquivos · R relações · V vírus · "
                "K conquistas · F foto · Ctrl+Alt+H traz o hub de volta",
                "Controle: Start abre Extras · View abre o Perfil · Y tira a foto do card · segurar o botão Xbox traz o hub"]
        for k, tip in enumerate(tips):
            c.create_text(x, ty + k * 24, anchor="nw", text=tip, fill=A.DIM, font=self.f["small"])

    def _extra_icon(self, kind, x, y, color, tag):
        c = self.c
        if kind == "perfil":
            c.create_oval(x - 9, y - 16, x + 9, y + 2, outline=color, width=2, tags=(tag,))
            c.create_arc(x - 17, y + 4, x + 17, y + 30, start=0, extent=180, style="arc", outline=color, width=2, tags=(tag,))
        elif kind == "historia":
            c.create_line(x - 16, y, x + 22, y, fill=color, width=2, tags=(tag,))
            for k in range(3):
                c.create_oval(x - 14 + k * 16, y - 4, x - 6 + k * 16, y + 4, fill=color, outline="", tags=(tag,))
        elif kind == "personagens":
            for dx in (-10, 10):
                c.create_oval(x + dx - 7, y - 14, x + dx + 7, y, outline=color, width=2, tags=(tag,))
                c.create_arc(x + dx - 12, y + 2, x + dx + 12, y + 24, start=0, extent=180, style="arc", outline=color,
                             width=2, tags=(tag,))
        elif kind == "ofertas":
            c.create_polygon(x - 14, y - 10, x + 6, y - 10, x + 18, y + 2, x + 6, y + 14, x - 14, y + 14,
                             outline=color, fill="", width=2, tags=(tag,))
            c.create_oval(x - 9, y - 1, x - 3, y + 5, outline=color, width=2, tags=(tag,))
        elif kind == "mapa":
            c.create_oval(x - 16, y - 16, x + 16, y + 16, outline=color, width=2, tags=(tag,))
            c.create_line(x - 16, y, x + 16, y, fill=color, tags=(tag,))
            c.create_oval(x - 7, y - 16, x + 7, y + 16, outline=color, tags=(tag,))
        elif kind == "arquivos":
            c.create_rectangle(x - 12, y - 16, x + 12, y + 16, outline=color, width=2, tags=(tag,))
            for k in range(3):
                c.create_line(x - 6, y - 7 + k * 7, x + 6, y - 7 + k * 7, fill=color, tags=(tag,))
        elif kind == "relacoes":
            pts = ((x - 14, y + 10), (x + 14, y + 10), (x, y - 14))
            c.create_line(*pts[0], *pts[1], *pts[2], *pts[0], fill=color, width=2, tags=(tag,))
            for px, py in pts:
                c.create_oval(px - 5, py - 5, px + 5, py + 5, fill=color, outline="", tags=(tag,))
        elif kind == "virus":
            c.create_oval(x - 10, y - 10, x + 10, y + 10, outline=color, width=2, tags=(tag,))
            for k in range(8):
                a = k * math.pi / 4
                c.create_line(x + 10 * math.cos(a), y + 10 * math.sin(a),
                              x + 17 * math.cos(a), y + 17 * math.sin(a), fill=color, width=2, tags=(tag,))
        elif kind == "conquistas":
            self._cup(x, y, 14, color)
        else:
            c.create_rectangle(x - 16, y - 8, x + 18, y + 16, outline=color, width=2, tags=(tag,))
            c.create_oval(x - 6, y - 3, x + 8, y + 11, outline=color, width=2, tags=(tag,))
            c.create_rectangle(x - 8, y - 13, x + 2, y - 8, fill=color, outline="", tags=(tag,))

    # ---------- Perfil ----------
    def _steam_games(self):
        """Um item por jogo da Steam (sem repetir appid), na ordem do catálogo."""
        seen, out = set(), []
        for g in self.games:
            if g["tipo"] == "steam" and g["appid"] not in seen:
                seen.add(g["appid"])
                out.append(g)
        return out

    def _draw_perfil(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        games = self._steam_games()
        loaded = {g["appid"]: s for g in games if (s := self.trophy_state.get(g["appid"])) and "erro" not in s}
        with_trophies = [s for s in loaded.values() if s.get("total")]
        plats = sum(1 for s in with_trophies if s["platina"])
        got, total = sum(s["conquistados"] for s in with_trophies), sum(s["total"] for s in with_trophies)
        tiers = {tier: sum(s["por_tier"][tier][0] for s in with_trophies) for tier in trophies.TIERS}
        play = self.playtimes()
        minutes = sum(play.get(g["appid"], {}).get("minutos", 0) for g in games)
        played = sum(1 for g in games if play.get(g["appid"], {}).get("minutos") or play.get(g["appid"], {}).get("ultima"))

        stats = ((f"{plats}", f"de {len(with_trophies)} platinas", A.TIER_COLORS["platina"]),
                 (f"{got}", f"de {total} troféus", A.WHITE),
                 (library.hours(minutes) or "0 h", "jogadas na franquia", A.WHITE),
                 (f"{played}", f"de {len(games)} jogos da Steam já jogados", A.WHITE))
        sw = (w - 3 * 16) / 4
        for k, (big, small, color) in enumerate(stats):
            sx = x + k * (sw + 16)
            self._round_rect(sx, y, sx + sw, y + 96, 16, fill="#141922", outline="#262d3a")
            c.create_text(sx + 20, y + 14, anchor="nw", text=big, fill=color, font=self.f["big"])
            c.create_text(sx + 20, y + 66, anchor="nw", text=small, fill=A.MUTED, font=self.f["small"])
        by = y + 116
        pct = got / total if total else 0
        self._round_rect(x, by, x + w, by + 8, 4, fill=A.CHIP, outline="")
        if pct:
            self._round_rect(x, by, x + max(8, w * pct), by + 8, 4, fill=self.accent, outline="")
        tx = x
        for tier in trophies.TIERS:
            self._cup(tx + 8, by + 30, 7, A.TIER_COLORS[tier])
            label = f"{tiers[tier]} {A.TIER_NAMES[tier].lower()}"
            c.create_text(tx + 22, by + 30, anchor="w", text=label, fill=A.WHITE, font=self.f["small"])
            tx += self.f["small"].measure(label) + 48
        c.create_text(x + w, by + 30, anchor="e", text=f"{round(pct * 100)}% de todos os troféus da franquia",
                      fill=A.MUTED, font=self.f["small"])

        ly = by + 62
        lw = w * 0.58
        c.create_text(x, ly, anchor="nw", text="SEUS JOGOS", fill=A.MUTED, font=self.f["tiny"])
        rows = sorted(games, key=lambda g: (-(loaded.get(g["appid"], {}).get("progresso", 0)),
                                            -play.get(g["appid"], {}).get("minutos", 0)))
        fits = max(1, int((bottom - ly - 24) // 58))
        ov["sel"] = min(ov["sel"], max(0, len(rows) - fits))
        for k, g in enumerate(rows[ov["sel"]:ov["sel"] + fits]):
            ry = ly + 24 + k * 58
            tag = f"ov_pg_{g['appid']}"
            mini = self._mini(g, (34, 50))
            if mini:
                c.create_image(x, ry, image=mini, anchor="nw", tags=(tag,))
            else:
                self._round_rect(x, ry, x + 34, ry + 50, 5, fill=A.CHIP, outline="", tags=(tag,))
            s = loaded.get(g["appid"])
            p = play.get(g["appid"], {})
            c.create_text(x + 48, ry + 2, anchor="nw", text=self._elide(g["nome"], self.f["btn"], lw - 220), fill=A.WHITE,
                          font=self.f["btn"], tags=(tag,))
            info = "  ·  ".join(v for v in (library.hours(p.get("minutos")), library.ago(p.get("ultima")) and
                                            f"jogado {library.ago(p.get('ultima'))}") if v) or "nunca jogado"
            c.create_text(x + 48, ry + 24, anchor="nw", text=info, fill=A.MUTED, font=self.f["small"], tags=(tag,))
            bx = x + lw - 160
            prog = s["progresso"] if s and s.get("total") else None
            self._round_rect(bx, ry + 14, bx + 110, ry + 20, 3, fill=A.CHIP, outline="")
            if prog:
                self._round_rect(bx, ry + 14, bx + max(6, 110 * prog / 100), ry + 20, 3,
                                 fill=A.TIER_COLORS["platina"] if s["platina"] else A.WHITE, outline="")
            c.create_text(bx + 120, ry + 17, anchor="w", text=f"{prog}%" if prog is not None else "—",
                          fill=A.WHITE if prog else A.DIM, font=self.f["small"])
            if s and s.get("platina"):
                self._cup(bx + 150, ry + 17, 7, A.TIER_COLORS["platina"])
            self._clickable(tag, lambda gg=g: self.goto_chapter(gg.get("capitulo") or gg["id"], gg["id"]))
            self._row_rects.append((x - 12, ry - 4, x + lw - 10, ry + 54))
        if len(rows) > fits:
            c.create_text(x, bottom, anchor="sw", text=f"role para ver mais ({len(rows)} jogos)", fill=A.DIM, font=self.f["small"])

        rx, rw = x + lw + 30, w - lw - 30
        c.create_text(rx, ly, anchor="nw", text="SEUS TROFÉUS MAIS RAROS", fill=A.MUTED, font=self.f["tiny"])
        rare = []
        for g in games:
            s = loaded.get(g["appid"])
            if not s:
                continue
            for it in (s.get("raros") or []) + (s.get("recentes") or []):
                if it.get("conquistado") and it.get("raridade") is not None:
                    rare.append((it["raridade"], it["nome"], g["nome"], it))
        seen, best = set(), []
        for r in sorted(rare, key=lambda r: r[0]):
            if (r[1], r[2]) not in seen:
                seen.add((r[1], r[2]))
                best.append(r)
        if not best:
            self._note(rx, ly + 26, rw, "Carregando troféus (ou nenhum conquistado ainda)...")
        for k, (pct_, name, game_name, it) in enumerate(best[:max(1, int((bottom - ly - 24) // 58))]):
            ry = ly + 24 + k * 58
            icon = self._remote_img(it.get("icone"), (40, 40))
            if icon:
                c.create_image(rx, ry, image=icon, anchor="nw")
            else:
                self._round_rect(rx, ry, rx + 40, ry + 40, 6, fill=A.CHIP, outline="")
            c.create_text(rx + 52, ry, anchor="nw", text=self._elide(name, self.f["btn"], rw - 90), fill=A.WHITE, font=self.f["btn"])
            c.create_text(rx + 52, ry + 22, anchor="nw", text=self._elide(f"{pct_:.1f}% dos jogadores  ·  {game_name}",
                                                                         self.f["small"], rw - 90),
                          fill=A.MUTED, font=self.f["small"])
            self._cup(rx + rw - 10, ry + 18, 8, A.TIER_COLORS[it.get("tier", "bronze")])

    def _avatar(self):
        """Foto do perfil da Steam (perfil público), baixada uma vez."""
        if not self.steamid:
            return None
        if getattr(self, "_avatar_url", None) is None:
            self._avatar_url = ""
            p = DATA / "cache" / "avatar.txt"
            try:
                self._avatar_url = p.read_text(encoding="utf-8").strip()
            except OSError:
                def fetch():
                    import urllib.request
                    try:
                        req = urllib.request.Request(f"https://steamcommunity.com/profiles/{self.steamid}?xml=1",
                                                     headers={"User-Agent": "RE-Hub"})
                        with urllib.request.urlopen(req, timeout=15) as r:
                            m = re.search(rb"<avatarFull><!\[CDATA\[(.*?)\]\]>", r.read())
                        if m:
                            p.parent.mkdir(parents=True, exist_ok=True)
                            p.write_text(m.group(1).decode(), encoding="utf-8")
                            self._avatar_url = m.group(1).decode()
                            self.after(0, self.refresh)
                    except OSError:
                        pass
                threading.Thread(target=fetch, daemon=True).start()
        return self._remote_img(self._avatar_url, (84, 84), 42) if self._avatar_url else None

    # ---------- Linha da história ----------
    def _story_items(self):
        """Capítulos da história oficial e, encaixados pelo ano, os filmes que se passam dentro dela."""
        items = [{"ch": ch, "sec": "canon", "ano": self._year_of(ch)} for ch in catalog.load_timeline(self.games, "canon")]
        for ch in catalog.load_timeline(self.games, "midia"):
            m = re.search(r"(\d{4}) na hist", ch.get("quando", ""))
            if not m:
                continue
            year = int(m.group(1))
            pos = len(items)
            for i, it in enumerate(items):
                if it["ano"] and it["ano"] > year:
                    pos = i
                    break
            items.insert(pos, {"ch": ch, "sec": "midia", "ano": year})
        return items

    @staticmethod
    def _year_of(ch):
        m = re.search(r"\d{4}", ch.get("quando", ""))
        return int(m.group(0)) if m else None

    @staticmethod
    def _story_label(it):
        if it["ano"]:
            return str(it["ano"])
        q = it["ch"].get("quando", "")
        return re.split(r"\s[—–·-]\s", q)[0].strip() if q else ""

    def _story_open(self, i):
        it = self.overlay["items"][i]
        self.goto_chapter(it["ch"]["id"])

    def _draw_historia(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        items = ov["items"]
        if not items:
            return self._note(x, y, w, "Nada na linha do tempo ainda.")
        step, size, big = 190, (112, 168), (150, 225)
        center = x + w / 2
        base = center - ov["sel"] * step - big[0] / 2
        line_y = y + 40
        c.create_line(x - A.MARGIN, line_y, x + w + A.MARGIN, line_y, fill=A.DIM, width=2)
        last = None
        for i, it in enumerate(items):
            on = i == ov["sel"]
            ix = base + i * step + (0 if i <= ov["sel"] else big[0] - size[0])
            sz = big if on else size
            if ix + sz[0] < -20 or ix > x + w + A.MARGIN + 20:
                last = self._story_label(it)
                continue
            label = self._story_label(it)
            if label != last:
                c.create_text(ix, y + 8, anchor="w", text=self._elide(label, self.f["h"], step - 14),
                              fill=A.WHITE if on else A.MUTED, font=self.f["h"])
            last = label
            cx = ix + sz[0] / 2
            r = 7 if on else 4
            c.create_oval(cx - r, line_y - r, cx + r, line_y + r, fill=self.accent if on else
                          (A.MUTED if it["sec"] == "canon" else A.DIM), outline="")
            tag = f"ov_st_{i}"
            ty = line_y + 26
            if on:
                c.create_image(ix - 24, ty - 24, image=self._halo(sz, A.hex_rgb(self.accent), 200, 0), anchor="nw")
            c.create_image(ix, ty, image=self._tile(it["ch"], sz, dim=not on), anchor="nw", tags=(tag,))
            if it["sec"] != "canon":
                c.create_text(ix + 8, ty + 8, anchor="nw", text="FILME", fill=A.WHITE, font=self.f["tiny"], tags=(tag,))
            c.create_text(ix, ty + sz[1] + 10, anchor="nw", text=it["ch"]["titulo"], fill=A.WHITE if on else A.MUTED,
                          font=self.f["small"], width=sz[0] + 30, tags=(tag,))
            self._clickable(tag, lambda i=i: self._story_open(i) if i == self.overlay["sel"] else
                            (self.overlay.__setitem__("sel", i), self._sound("select"), self.refresh()))
        it = items[ov["sel"]]
        ch = it["ch"]
        dy = line_y + 26 + big[1] + 70
        c.create_text(x, dy, anchor="nw", text=ch["titulo"], fill=A.WHITE, font=self._title_font(ch), width=w)
        where = "   ·   ".join(p for p in (ch.get("quando"), ch.get("onde")) if p)
        c.create_text(x, dy + 52, anchor="nw", text=where, fill=self.accent, font=self.f["small"], width=w)
        if ch.get("sinopse") and dy + 80 < bottom - 20:
            c.create_text(x, dy + 80, anchor="nw", text=ch["sinopse"], fill="#d5d9e0", font=self.f["body"], width=min(w, 900))
        c.create_text(x + w, bottom, anchor="se", text="← →  andar na linha do tempo    Enter  abrir no hub",
                      fill=A.DIM, font=self.f["small"])

    # ---------- Personagens ----------
    def _people_filters(self):
        return (("todos", "Todos"), ("heroi", "Heróis e aliados"), ("vilao", "Vilões"),
                ("criatura", FR.get("rotulo_criaturas", "Criaturas")))

    def _people(self):
        f = (self.overlay or {}).get("filtro", "todos")
        return [p for p in characters.load() if f == "todos" or p.get("tipo", "heroi") == f]

    def _set_people_filter(self, f):
        self.overlay.update(filtro=f, sel=0, scroll=0)
        self._sound("tab")
        self.refresh()

    def _fetch_portraits(self):
        """Baixa os retratos que faltam, seis de cada vez (são mais de cem)."""
        missing = [p for p in characters.load() if not characters.portrait_path(p)]
        if not missing or getattr(self, "_portraits_busy", False):
            return
        self._portraits_busy = True

        def one(p):
            if characters.download_portrait(p):
                self.after(0, self.refresh)

        def work():
            from concurrent.futures import ThreadPoolExecutor
            with ThreadPoolExecutor(6) as pool:
                list(pool.map(one, missing))
            self._portraits_busy = False
        threading.Thread(target=work, daemon=True).start()

    def _versions_of(self, p):
        """Versões do personagem (uma imagem por jogo). Se ainda não buscou, pede para uma thread buscar."""
        got = characters.versions(p)
        if got is None:
            self._want_versions(p)
        return got or []

    def _want_versions(self, p):
        """Fila de downloads de versões: atende primeiro o personagem pedido por último (o que está na tela)."""
        if p["id"] in getattr(self, "_ver_done", set()):
            return
        queue = self.__dict__.setdefault("_ver_queue", [])
        if p in queue:
            queue.remove(p)
        queue.append(p)
        if getattr(self, "_ver_busy", False):
            return
        self._ver_busy = True
        self._ver_done = getattr(self, "_ver_done", set())

        def work():
            while queue:
                q = queue.pop()
                try:
                    characters.download_versions(q)
                except Exception:
                    pass
                self._ver_done.add(q["id"])
                self.after(0, self.refresh)
            self._ver_busy = False
        threading.Thread(target=work, daemon=True).start()

    def _version_index(self, p, versions):
        ov = self.overlay
        if ov.get("ver_of") != p["id"]:  # personagem novo: começa pela versão mais recente
            ov["ver_of"], ov["ver"] = p["id"], len(versions) - 1
        ov["ver"] = max(0, min(ov.get("ver", 0), len(versions) - 1))
        return ov["ver"]

    def _step_version(self, p, d):
        versions = self._versions_of(p)
        if len(versions) < 2:
            return
        i = self._version_index(p, versions)
        self.overlay["ver"] = (i + d) % len(versions)
        self._sound("select")

    def _draw_personagens(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        everyone = characters.load()
        if not everyone:
            return self._note(x, y, w, "Ainda não há fichas de personagens. Elas ficam em games/_personagens.json.")
        # filtro: todos / heróis / vilões / criaturas
        fx = x
        cur = ov.get("filtro", "todos")
        for key, label in self._people_filters():
            n = len(everyone) if key == "todos" else sum(1 for p in everyone if p.get("tipo", "heroi") == key)
            if not n:
                continue
            fx = self._chip(fx, y - 8, f"{label}  {n}", lambda k=key: self._set_people_filter(k), f"ov_pf_{key}",
                            primary=key == cur) + 8
        y += 40
        people = self._people()
        if not people:
            return
        ov["sel"] = min(ov["sel"], len(people) - 1)
        gw = w * 0.5
        cell_w, cell_h, pw, ph = 112, 172, 102, 134
        cols = max(2, int(gw // cell_w))
        ov["cols"] = cols
        rows_fit = max(1, int((bottom - y) // cell_h))
        sel_row = ov["sel"] // cols
        total_rows = (len(people) + cols - 1) // cols
        if ov.pop("scroll_by_wheel", False):
            ov["scroll"] = min(ov["scroll"], max(0, total_rows - rows_fit))
        elif sel_row < ov["scroll"]:
            ov["scroll"] = sel_row
        elif sel_row >= ov["scroll"] + rows_fit:
            ov["scroll"] = sel_row - rows_fit + 1
        first = ov["scroll"] * cols
        for k, p in enumerate(people[first:first + rows_fit * cols]):
            i = first + k
            px, py = x + (k % cols) * cell_w, y + (k // cols) * cell_h
            on = i == ov["sel"]
            tag = f"ov_pp_{p['id']}"
            path = characters.portrait_path(p)
            img = self._photo_fit(path, (pw, ph), self._portraits, p["id"], 10, contain=True) if path else None
            if on:
                c.create_image(px - 24, py - 24, image=self._halo((pw, ph), A.hex_rgb(self.accent), 210, 0), anchor="nw")
            if img:
                c.create_image(px, py, image=img, anchor="nw", tags=(tag,))
            else:
                self._round_rect(px, py, px + pw, py + ph, 10, fill="#141922", outline="#262d3a", tags=(tag,))
                c.create_text(px + pw / 2, py + ph / 2, text=p["nome"][:1], fill=A.DIM, font=self.f["big"], tags=(tag,))
            c.create_text(px + pw / 2, py + ph + 8, anchor="n", text=self._elide(p["nome"], self.f["small"], cell_w - 6),
                          fill=A.WHITE if on else A.MUTED, font=self.f["small"], tags=(tag,))
            self._clickable(tag, lambda i=i: (self.overlay.__setitem__("sel", i), self._sound("select"), self.refresh()))
        if total_rows > rows_fit:
            track = rows_fit * cell_h - 30
            bh = max(24, track * rows_fit / total_rows)
            by = y + (track - bh) * ov["scroll"] / max(1, total_rows - rows_fit)
            c.create_rectangle(x + cols * cell_w + 4, y, x + cols * cell_w + 6, y + track, fill="#232a36", outline="")
            c.create_rectangle(x + cols * cell_w + 4, by, x + cols * cell_w + 6, by + bh, fill=A.MUTED, outline="")
        self._draw_person(people[ov["sel"]], x + gw + 40, y, x + w, bottom)

    def _draw_person(self, p, dx, y, right, bottom):
        """Ficha do personagem: imagem da versão escolhida, texto, todas as versões e onde aparece."""
        c = self.c
        self._round_rect(dx - 20, y - 10, right + 20, bottom, 18, fill="#10141c", outline="#262d3a")
        dw = right - dx
        versions = self._versions_of(p)
        vi = self._version_index(p, versions) if versions else None
        big = (min(250, int(dw * 0.42)), min(320, int((bottom - y) * 0.48)))
        if versions:
            v = versions[vi]
            path, key = characters.version_path(v), ("ver", v["arquivo"])
        else:
            path, key = characters.portrait_path(p), p["id"]
        img = self._photo_fit(path, big, self._portraits, key, 14, contain=True, bg=(16, 20, 28)) if path else None
        if img:
            c.create_image(dx, y + 6, image=img, anchor="nw")
        if versions:
            c.create_text(dx + big[0] / 2, y + big[1] + 14, anchor="n", text=versions[vi]["rotulo"], fill=self.accent,
                          font=self.f["small"], width=big[0])
        tx = dx + big[0] + 24
        tw = right - tx
        tipo = {"heroi": "HERÓI / ALIADO", "vilao": "VILÃO", "criatura": FR.get("rotulo_criaturas", "Criatura").upper()}
        c.create_text(tx, y + 8, anchor="nw", text=tipo.get(p.get("tipo", "heroi"), ""), fill=A.MUTED, font=self.f["tiny"])
        name = c.create_text(tx, y + 26, anchor="nw", text=p["nome"], fill=A.WHITE, font=self.f["title"], width=tw)
        ty = c.bbox(name)[3] + 4
        wiki = self.wiki_page(p.get("pt"))  # texto da Resident Evil Wiki em português
        papel = p.get("papel") or (wiki or {}).get("papel", "")
        if papel:
            c.create_text(tx, ty, anchor="nw", text=self._elide(papel, self.f["btn"], tw), fill=self.accent, font=self.f["btn"])
            ty += 30
        text = self.wiki_summary(wiki, 520 if p.get("fraqueza") else 760) or p.get("descricao", "")
        if p.get("pt") and wiki is None:
            text = text or "Buscando na Resident Evil Wiki..."
        desc = c.create_text(tx, ty, anchor="nw", text=text, fill="#d5d9e0", font=self.f["body"], width=tw)
        ty = c.bbox(desc)[3] + 8
        if wiki and wiki.get("link"):
            c.create_text(tx, ty, anchor="nw", text="Resident Evil Wiki (pt-br)  ›", fill=A.MUTED, font=self.f["tiny"],
                          tags=("ov_pwiki",))
            self._clickable("ov_pwiki", lambda u=wiki["link"]: webbrowser.open(u))
            ty += 20
        ty += 4
        self.stat_add("fichas", p["id"])
        if p.get("fraqueza") or p.get("arma") or p.get("chefe"):  # bestiário
            for label, key in (("PONTO FRACO", "fraqueza"), ("MELHOR ARMA", "arma"), ("ONDE É CHEFE", "chefe")):
                if not p.get(key):
                    continue
                c.create_text(tx, ty, anchor="nw", text=label, fill=A.MUTED, font=self.f["tiny"])
                t = c.create_text(tx, ty + 16, anchor="nw", text=p[key], fill=A.WHITE, font=self.f["small"], width=tw)
                ty = c.bbox(t)[3] + 8

        # todas as versões (uma por jogo/filme), da mais antiga à mais nova
        vy = max(y + big[1] + 46, ty + 10)
        if characters.versions(p) is None and p["id"] not in getattr(self, "_ver_done", set()):
            c.create_text(dx, vy, anchor="nw", text="VERSÕES  ·  buscando na wiki...", fill=A.MUTED, font=self.f["tiny"])
            vy += 26
        elif len(versions) > 1:
            c.create_text(dx, vy, anchor="nw", text=f"VERSÕES  ·  {len(versions)}", fill=A.MUTED, font=self.f["tiny"])
            tw_, th_, gap = 58, 78, 8
            fits = max(1, int((dw + gap) // (tw_ + gap)))
            start = min(max(0, vi - fits // 2), max(0, len(versions) - fits))
            for k, v in enumerate(versions[start:start + fits]):
                j = start + k
                vx = dx + k * (tw_ + gap)
                tag = f"ov_pv_{p['id']}_{j}"
                if j == vi:
                    self._round_rect(vx - 3, vy + 19, vx + tw_ + 3, vy + 22 + th_ + 3, 9, fill=self.accent, outline="")
                th = self._photo_fit(characters.version_path(v), (tw_, th_), self._portraits, ("ver", v["arquivo"]), 7,
                                     contain=True, bg=(24, 29, 39))
                if th:
                    c.create_image(vx, vy + 22, image=th, anchor="nw", tags=(tag,))
                else:
                    self._round_rect(vx, vy + 22, vx + tw_, vy + 22 + th_, 7, fill="#141922", outline="", tags=(tag,))
                self._clickable(tag, lambda j=j: (self.overlay.__setitem__("ver", j), self._sound("select"), self.refresh()))
            if start > 0:
                c.create_text(dx - 12, vy + 22 + th_ / 2, text="‹", fill=A.WHITE, font=self.f["h"])
            if start + fits < len(versions):
                c.create_text(right + 10, vy + 22 + th_ / 2, text="›", fill=A.WHITE, font=self.f["h"])
            vy += 22 + th_ + 20

        # onde aparece
        c.create_text(dx, vy, anchor="nw", text="APARECE EM", fill=A.MUTED, font=self.f["tiny"])
        ay, ax = vy + 22, dx
        titles = self._chapter_titles()
        for cid in p.get("aparicoes", []):
            label = titles.get(cid)
            if not label:
                continue
            pre = FR["prefixo_titulo"]
            short = label[len(pre):].strip(" :–") if pre and label.startswith(pre) else label
            if len(short) < 4:  # "Resident Evil 3" virava só "3"
                short = label
            cw = self.f["small"].measure(short) + 26
            if ax + cw > right:
                ax, ay = dx, ay + 36
            if ay + 28 > bottom - 10:
                break
            ax = self._chip(ax, ay, short, lambda c_=cid: self.goto_chapter(c_), f"ov_pa_{cid}") + 8

    def _chapter_titles(self):
        if not hasattr(self, "_titles_cache"):
            self._titles_cache = {ch["id"]: ch["titulo"] for sec, _ in A.SECTIONS if sec != "noticias"
                                  for ch in catalog.load_timeline(self.games, sec)}
        return self._titles_cache

    # ---------- Ofertas e lançamentos ----------
    def refresh_deals(self, force=False):
        if getattr(self, "_deals_busy", False):
            return
        self._deals_busy = True
        appids = [g["appid"] for g in self._steam_games()]

        def work():
            try:
                result = deals.refresh(self.steamid, appids, force=force)
                self.after(0, lambda: self._deals_arrived(result))
            except Exception:
                pass
            finally:
                self._deals_busy = False
        threading.Thread(target=work, daemon=True).start()

    def _deals_arrived(self, result):
        first = not self.deals_state
        self.deals_state = result
        if first or self.prefs.get("_avisou_ofertas") != int(result.get("buscado_em", 0) // 86400):
            sales = [g for g in self._steam_games() if (p := self.price_of(g)) and p["desconto"] and not self.owned(g)]
            if sales:  # avisa uma vez por dia
                self._save_prefs(_avisou_ofertas=int(result.get("buscado_em", 0) // 86400))
                g = sales[0]
                p = self.price_of(g)
                more = f" e mais {len(sales) - 1}" if len(sales) > 1 else ""
                self.toast(f"Promoção: {g['nome']} -{p['desconto']}%{more}", f"Agora por {p['texto']}. Clique para ver",
                           lambda: self.open_overlay("ofertas"))
        self.refresh()

    def price_of(self, g):
        if g.get("tipo") != "steam" or not self.deals_state:
            return None
        return self.deals_state.get("precos", {}).get(str(g["appid"]))

    def wished(self, g):
        return bool(self.deals_state) and g.get("tipo") == "steam" and g["appid"] in self.deals_state.get("desejos", [])

    def owned(self, g):
        """Tem o jogo? Instalado ou já jogado nesta conta (a Steam não mostra a biblioteca sem login)."""
        if g.get("tipo") != "steam":
            return False
        p = self.playtimes().get(g["appid"], {})
        return g["appid"] in self.installed or bool(p.get("minutos") or p.get("ultima"))

    def release(self, ch, g=None):
        """Lançamento futuro (contagem regressiva): (timestamp, precisão) ou None.
        Vem de "data_lancamento" no catálogo ("2027-03-12", "2027-03" ou "2027") ou da página da Steam."""
        when = str((g or {}).get("data_lancamento") or ch.get("data_lancamento") or "")
        for fmt, prec in (("%Y-%m-%d", "date_full"), ("%Y-%m", "date_month"), ("%Y", "date_year")):
            try:
                ts = datetime.strptime(when, fmt).timestamp()
            except ValueError:
                continue
            if prec == "date_year":
                ts = datetime(int(when), 12, 31).timestamp()
            return (ts, prec) if ts > time.time() else None
        if g and g.get("tipo") == "steam":
            info = self.store_info.get(g["appid"]) or {}
            if info.get("precisao") and (info.get("lancamento") or 0) > time.time():
                return info["lancamento"], info["precisao"]
        return None

    MONTHS = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
              "novembro", "dezembro")

    def countdown(self, rel, short=False):
        """'em 12 dias', 'amanhã', 'em março de 2027', 'em 2027'... conforme a precisão da data."""
        ts, prec = rel
        d = datetime.fromtimestamp(ts)
        if prec == "date_full":
            days = (d.date() - datetime.now().date()).days
            text = "hoje" if days <= 0 else "amanhã" if days == 1 else f"em {days} dias"
            return text if short else f"{text} ({d:%d/%m/%Y})"
        if prec == "date_month":
            return f"{self.MONTHS[d.month - 1][:3]}/{d.year}" if short else f"em {self.MONTHS[d.month - 1]} de {d.year}"
        if prec == "date_quarter":
            return f"{(d.month - 1) // 3 + 1}º tri {d.year}" if short else f"no {(d.month - 1) // 3 + 1}º trimestre de {d.year}"
        if prec == "date_year":
            return f"em {d.year}"
        return "em breve"

    def _upcoming(self):
        out = []
        for sec, _ in A.SECTIONS:
            if sec == "noticias":
                continue
            for ch in catalog.load_timeline(self.games, sec):
                for g in ch["versoes"]:
                    rel = self.release(ch, g)
                    if rel:
                        out.append((rel, ch, g))
                        break
        return sorted(out, key=lambda r: r[0][0])

    def _draw_ofertas(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        st = self.deals_state
        cy = y
        upcoming = self._upcoming()
        if upcoming:
            c.create_text(x, cy, anchor="nw", text="EM BREVE", fill=A.MUTED, font=self.f["tiny"])
            cx = x
            for rel, ch, g in upcoming[:4]:
                tag = f"ov_up_{ch['id']}"
                cw = 300
                self._round_rect(cx, cy + 22, cx + cw, cy + 92, 14, fill="#141922", outline="#262d3a", tags=(tag,))
                c.create_text(cx + 18, cy + 34, anchor="nw", text=self._elide(ch["titulo"], self.f["btn"], cw - 36),
                              fill=A.WHITE, font=self.f["btn"], tags=(tag,))
                c.create_text(cx + 18, cy + 58, anchor="nw", fill=self.accent, font=self.f["h"], tags=(tag,),
                              text=f"Lança {self.countdown(rel)}")
                self._clickable(tag, lambda cid=ch["id"]: self.goto_chapter(cid))
                cx += cw + 14
            cy += 116
        if not st:
            return self._note(x, cy, w, "Buscando os preços na Steam...")
        games = self._steam_games()
        rows = []
        for g in games:
            p = self.price_of(g)
            rows.append({"g": g, "appid": g["appid"], "p": p, "wish": self.wished(g), "own": self.owned(g)})
        rows.sort(key=lambda r: (not (r["p"] and r["p"]["desconto"] and not r["own"]), not r["wish"], r["own"],
                                 -(r["p"]["desconto"] if r["p"] else 0)))
        ov["rows"] = rows
        sales = sum(1 for r in rows if r["p"] and r["p"]["desconto"])
        head = f"{sales} em promoção agora" if sales else "Nenhum jogo da franquia em promoção agora"
        c.create_text(x, cy, anchor="nw", text=head, fill=A.WHITE, font=self.f["h"])
        c.create_text(x, cy + 24, anchor="nw", fill=A.DIM, font=self.f["small"],
                      text=f"Preços buscados {library.ago(st.get('buscado_em'))}. Os da sua lista de desejos da Steam têm ★.")
        bx = self._chip(x + w, cy, "Atualizar", lambda: self.refresh_deals(force=True), "ov_deals_ref", anchor="e")
        self._chip(bx - 8, cy, "Lista de desejos na Steam  ›", lambda: os.startfile(
            "steam://openurl/https://store.steampowered.com/wishlist/"), "ov_deals_wl", anchor="e")
        ly, row_h = cy + 60, 62
        fits = max(1, int((bottom - ly) // row_h))
        ov["sel"] = min(ov["sel"], max(0, len(rows) - 1))
        start = min(max(0, ov["sel"] - fits + 1), max(0, len(rows) - fits))
        for k, r in enumerate(rows[start:start + fits]):
            i = start + k
            g, p = r["g"], r["p"]
            ry = ly + k * row_h
            tag = f"ov_dl_{r['appid']}"
            if i == ov["sel"]:
                self._round_rect(x - 12, ry - 6, x + w + 12, ry + row_h - 10, 12, fill="#18202c", outline="", tags=(tag,))
            mini = self._mini(g, (34, 50))
            if mini:
                c.create_image(x, ry, image=mini, anchor="nw", tags=(tag,))
            name = ("★  " if r["wish"] else "") + g["nome"]
            c.create_text(x + 48, ry + 4, anchor="nw", text=self._elide(name, self.f["btn"], w - 360), fill=A.WHITE,
                          font=self.f["btn"], tags=(tag,))
            sub = "Você já tem" if r["own"] else ("Na sua lista de desejos" if r["wish"] else "")
            if sub:
                c.create_text(x + 48, ry + 26, anchor="nw", text=sub, fill=A.GREEN if r["own"] else A.MUTED,
                              font=self.f["small"], tags=(tag,))
            rx = x + w
            if p:
                c.create_text(rx, ry + 14, anchor="e", text=p["texto"], fill=A.WHITE, font=self.f["h"], tags=(tag,))
                rx -= self.f["h"].measure(p["texto"]) + 14
                if p["desconto"]:
                    if p.get("texto_inicial"):
                        c.create_text(rx, ry + 15, anchor="e", text=p["texto_inicial"], fill=A.DIM, tags=(tag,),
                                      font=(self.f["small"].actual("family"), 9, "overstrike"))
                        rx -= self.f["small"].measure(p["texto_inicial"]) + 14
                    bw = self.f["tiny"].measure(f"-{p['desconto']}%") + 16
                    self._round_rect(rx - bw, ry + 3, rx, ry + 25, 8, fill="#4c7a1f", outline="", tags=(tag,))
                    c.create_text(rx - bw / 2, ry + 14, text=f"-{p['desconto']}%", fill="#d6f5a8", font=self.f["tiny"], tags=(tag,))
            else:
                c.create_text(rx, ry + 14, anchor="e", text="sem preço na loja", fill=A.DIM, font=self.f["small"], tags=(tag,))
            self._clickable(tag, lambda a=r["appid"]: steam.store(a))
            self._row_rects.append((x - 12, ry - 4, x + w + 4, ry + row_h - 8))

    # ---------- visualizador de prints ----------
    def open_viewer(self, items, idx):
        self._trailer_stop()
        self.overlay = {"kind": "viewer", "items": items, "sel": idx}
        self._sound("open")
        self.refresh()

    def _viewer_go(self, d):
        ov = self.overlay
        ov["sel"] = (ov["sel"] + d) % len(ov["items"])
        self._sound("select")
        self.refresh()

    def _viewer_open(self):
        os.startfile(self.overlay["items"][self.overlay["sel"]]["path"])

    def _viewer_set_bg(self):
        """Usa a print como fundo do jogo selecionado (fica salvo; dá para voltar ao original)."""
        it = self.overlay["items"][self.overlay["sel"]]
        g = self.game
        if it["video"] or not g:
            return
        key = store.art_key(g) or g["id"]
        cur = self.cfg.get("_fundos").get(key)
        self.cfg.set("_fundos", **{key: None if cur == str(it["path"]) else str(it["path"])})
        self.toast("Fundo trocado" if cur != str(it["path"]) else "Fundo original de volta",
                   f"{self.chapter['titulo']}" if self.chapter else "")
        self.refresh()

    def _draw_viewer(self, W, H):
        c, ov = self.c, self.overlay
        c.create_rectangle(0, 0, W, H, fill="#000000", outline="")
        it = ov["items"][ov["sel"]]
        area = (W, H - 70)
        key = (str(it["path"]), area)
        if getattr(self, "_viewer_key", None) != key:
            self._viewer_key, self._viewer_photo = key, None
            if not it["video"]:
                try:
                    img = Image.open(it["path"])
                    img.draft("RGB", area)
                    img = img.convert("RGB")
                    img.thumbnail(area, Image.LANCZOS)
                    self._viewer_photo = ImageTk.PhotoImage(img)
                except OSError:
                    pass
        if self._viewer_photo:
            c.create_image(W / 2, (H - 70) / 2, image=self._viewer_photo)
        else:
            c.create_text(W / 2, H / 2 - 40, text="▶", fill=A.WHITE, font=self.f["big"])
            c.create_text(W / 2, H / 2 + 10, text=it["path"].name, fill=A.MUTED, font=self.f["body"])
        y = H - 46
        when = datetime.fromtimestamp(it["quando"]).strftime("%d/%m/%Y %H:%M")
        c.create_text(A.MARGIN, y, anchor="w", text=f"{ov['sel'] + 1} de {len(ov['items'])}   ·   {when}",
                      fill=A.MUTED, font=self.f["small"])
        x = W - A.MARGIN
        x = self._chip(x, y - 14, "✕  Fechar (Esc)", self.close_overlay, "ov_v_close", anchor="e") - 8
        x = self._chip(x, y - 14, "Abrir pasta", lambda: os.startfile(it["path"].parent), "ov_v_dir", anchor="e") - 8
        if it["video"]:
            x = self._chip(x, y - 14, "▶  Assistir (Enter)", self._viewer_open, "ov_v_play", anchor="e", primary=True) - 8
        else:
            g = self.game
            cur = self.cfg.get("_fundos").get((store.art_key(g) or g["id"]) if g else "")
            label = "Voltar ao fundo original" if cur == str(it["path"]) else "Usar como fundo (Y)"
            x = self._chip(x, y - 14, label, self._viewer_set_bg, "ov_v_bg", anchor="e") - 8
        x = self._chip(x, y - 14, "Próxima  ›", lambda: self._viewer_go(1), "ov_v_next", anchor="e") - 8
        self._chip(x, y - 14, "‹  Anterior", lambda: self._viewer_go(-1), "ov_v_prev", anchor="e")

    # ---------- aba Prints do painel ----------
    def media_of(self, g):
        """Prints e vídeos do jogo selecionado (Steam + Game Bar/Radeon/NVIDIA)."""
        sg = self.steam_game()
        appid = sg["appid"] if sg else None
        names = {g["nome"], self.chapter["titulo"] if self.chapter else ""} | set(g.get("nomes_janela", []))
        if sg:
            names |= {sg["nome"], library.manifest(appid).get("nome", "")}
        key = (appid, tuple(sorted(n for n in names if n)))
        now = time.time()
        hit = self._media_cache.get(key)
        if not hit or now - hit[0] > 10:  # relê a pasta de vez em quando (prints novas aparecem sozinhas)
            hit = (now, library.media_for(self.steamid, appid, names), appid)
            self._media_cache[key] = hit
        return hit[1], appid

    def _thumb(self, item, size):
        """Miniatura de uma print (feita numa thread e guardada em data/cache/prints)."""
        key = (str(item["path"]), size)
        if key in self._thumbs:
            return self._thumbs[key]
        name = hashlib.sha1(f"{item['path']}|{item['quando']}".encode()).hexdigest()[:20] + ".jpg"
        cached = THUMBS / name
        if cached.exists():
            try:
                self._thumbs[key] = ImageTk.PhotoImage(A.rounded(A.fit_cover(Image.open(cached).convert("RGB"), size), 8))
                return self._thumbs[key]
            except OSError:
                pass
        if key not in self._thumb_pending:
            self._thumb_pending.add(key)

            def work():
                try:
                    img = Image.open(item["path"])
                    img.draft("RGB", (480, 270))
                    img = img.convert("RGB")
                    img.thumbnail((480, 270), Image.LANCZOS)
                    THUMBS.mkdir(parents=True, exist_ok=True)
                    img.save(cached, quality=85)
                    self.after(0, self.refresh)
                except OSError:
                    pass
            threading.Thread(target=work, daemon=True).start()
        return None

    def _draw_prints(self, g, x, y, w, bottom):
        c = self.c
        media, appid = self.media_of(g)
        shots = sum(1 for m in media if not m["video"])
        vids = len(media) - shots
        head = " · ".join(p for p in (f"{shots} print{'s' if shots != 1 else ''}" if shots else "",
                                      f"{vids} vídeo{'s' if vids != 1 else ''}" if vids else "") if p) or "Nenhuma captura"
        c.create_text(x, y - 4, anchor="nw", text=head, fill=A.WHITE, font=self.f["h"])
        folder = library.steam_screens_dir(self.steamid, appid) if appid else None
        if folder and folder.is_dir():
            self._chip(x + w, y - 8, "Abrir pasta", lambda: os.startfile(folder), "pr_dir", anchor="e")
        elif appid and self.steamid:
            self._chip(x + w, y - 8, "Prints na Steam  ›", lambda: os.startfile(
                f"steam://open/screenshots/{appid}"), "pr_steam", anchor="e")
        if not media:
            return self._note(x, y + 34, w, "Nenhuma print deste jogo ainda.\n\nNa Steam, aperte F12 durante o jogo. "
                                            "No Windows, Win+Alt+PrtScn tira print e Win+Alt+R grava vídeo "
                                            "(Xbox Game Bar). Elas aparecem aqui sozinhas.")
        cols = 3
        gap = 10
        tw = int((w - gap * (cols - 1)) / cols)
        th = int(tw * 9 / 16)
        top = y + 32
        rows_fit = max(1, int((bottom - top + gap) // (th + gap)))
        total_rows = (len(media) + cols - 1) // cols
        self.panel_scroll = min(self.panel_scroll, max(0, total_rows - rows_fit))
        first = self.panel_scroll * cols
        for k, m in enumerate(media[first:first + rows_fit * cols]):
            i = first + k
            tx, ty = x + (k % cols) * (tw + gap), top + (k // cols) * (th + gap)
            tag = f"pr_{i}"
            img = None if m["video"] else self._thumb(m, (tw, th))
            if img:
                c.create_image(tx, ty, image=img, anchor="nw", tags=(tag,))
            else:
                self._round_rect(tx, ty, tx + tw, ty + th, 8, fill="#141922", outline="#262d3a", tags=(tag,))
            if m["video"]:
                c.create_oval(tx + tw / 2 - 18, ty + th / 2 - 18, tx + tw / 2 + 18, ty + th / 2 + 18, fill="#000000",
                              outline=A.WHITE, width=2, tags=(tag,))
                c.create_polygon(tx + tw / 2 - 6, ty + th / 2 - 9, tx + tw / 2 - 6, ty + th / 2 + 9, tx + tw / 2 + 10,
                                 ty + th / 2, fill=A.WHITE, outline="", tags=(tag,))
            self._clickable(tag, lambda i=i, md=media: self.open_viewer(md, i))
        if total_rows > rows_fit:
            track = bottom - top
            bh = max(24, track * rows_fit / total_rows)
            by = top + (track - bh) * self.panel_scroll / max(1, total_rows - rows_fit)
            c.create_rectangle(x + w + 12, top, x + w + 14, bottom, fill="#232a36", outline="")
            c.create_rectangle(x + w + 12, by, x + w + 14, by + bh, fill=A.MUTED, outline="")

    # ---------- avisos (canto de cima, como as notificações da PS5) ----------
    def toast(self, text, sub="", action=None, seconds=7):
        self._toasts.append({"text": text, "sub": sub, "action": action, "until": time.time() + seconds,
                             "id": int(time.time() * 1000) % 10 ** 9})
        self._toasts = self._toasts[-3:]
        self._sound("trophy" if action else "open")
        self.after(int(seconds * 1000) + 50, self.refresh)
        self.refresh()

    def _draw_toasts(self, W):
        now = time.time()
        self._toasts = [tt for tt in self._toasts if tt["until"] > now]
        y = 74
        for tt in self._toasts:
            tw = max(self.f["btn"].measure(tt["text"]), self.f["small"].measure(tt["sub"])) + 44
            tw = min(tw, 520)
            x2 = W - A.MARGIN
            tag = f"toast{tt['id']}"
            self._round_rect(x2 - tw, y, x2, y + 60, 14, fill="#1b212c", outline=self.accent, tags=(tag, "toast"))
            self.c.create_text(x2 - tw + 22, y + 12, anchor="nw", text=self._elide(tt["text"], self.f["btn"], tw - 40),
                               fill=A.WHITE, font=self.f["btn"], tags=(tag, "toast"))
            self.c.create_text(x2 - tw + 22, y + 34, anchor="nw", text=self._elide(tt["sub"], self.f["small"], tw - 40),
                               fill=A.MUTED, font=self.f["small"], tags=(tag, "toast"))

            def click(tt=tt):
                self._toasts = [o for o in self._toasts if o is not tt]
                if tt["action"]:
                    tt["action"]()
                self.refresh()
            self._clickable(tag, click)
            y += 70

    # ---------- foto do card ----------
    def photo_card(self):
        """Imagem 1920x1080 do jogo selecionado (arte, card, troféus, horas) em Imagens/<app>."""
        ch, g = self.chapter, self.game
        if not ch or not g:
            return
        self._sound("prompt_enter")
        W, H = 1920, 1080
        hero = self._art(g, "fundo")
        accent = A.hex_rgb(self.accent)
        if hero is not None:
            base = A.fit_cover(hero.convert("RGB"), (W, H), 0.3)
        else:
            base = Image.new("RGB", (W, H), A.BG_RGB)
        grad = Image.linear_gradient("L").rotate(90, expand=True).resize((W, H))  # escurece da esquerda para a direita
        base = Image.composite(base, Image.new("RGB", (W, H), A.BG_RGB), grad.point(lambda v: int(60 + v * 0.55)))
        img = base.convert("RGBA")
        art = self._image(store.art_key(g), "capa")
        if art is None and not g.get("poster"):
            other = next((v for v in ch["versoes"] if self._image(store.art_key(v), "capa") is not None), None)
            art = self._image(store.art_key(other), "capa") if other else None
        tile = self._tile_base[self._ensure_tile_base(ch, g, art)]
        th = 640
        tile = tile.resize((int(tile.width * th / tile.height), th), Image.LANCZOS)
        glow = A.make_halo(tile.size, accent, 230, 22, 0)
        tx, ty = 130, (H - th) // 2 - 20
        img.alpha_composite(glow, (tx - 44, ty - 44))
        img.alpha_composite(tile, (tx, ty))
        d = ImageDraw.Draw(img)
        x = tx + tile.width + 90
        y = ty + 10
        logo_p = store.art_path(store.art_key(g), "logo")
        if logo_p:
            logo = Image.open(logo_p).convert("RGBA")
            logo = logo.crop(logo.getbbox() or (0, 0, *logo.size))
            logo.thumbnail((820, 200), Image.LANCZOS)
            img.alpha_composite(logo, (x, y))
            y += logo.height + 30
        else:
            f = A.pil_font(72, self._title_font_file(ch) or "seguisb.ttf")
            for line in A.wrap(d, ch["titulo"], f, W - x - 100):
                d.text((x, y), line, font=f, fill=(244, 244, 246))
                y += f.size + 10
            y += 20
        where = "  ·  ".join(p for p in (ch.get("quando"), ch.get("onde")) if p)
        if where:
            d.text((x, y), where, font=A.pil_font(30, "segoeui.ttf"), fill=(200, 205, 214))
            y += 64
        sg = self.steam_game()
        s = self.trophy_state.get(sg["appid"]) if sg else None
        if s and "erro" not in s and s.get("total"):
            d.text((x, y), f"{s['progresso']}%", font=A.pil_font(110, "segoeuil.ttf"), fill=(244, 244, 246))
            fx = x + int(d.textlength(f"{s['progresso']}%", font=A.pil_font(110, "segoeuil.ttf"))) + 36
            d.text((fx, y + 26), f"{s['conquistados']} de {s['total']} troféus", font=A.pil_font(38, "seguisb.ttf"),
                   fill=(244, 244, 246))
            d.text((fx, y + 76), "PLATINA CONQUISTADA" if s["platina"] else "conquistados",
                   font=A.pil_font(26, "seguisb.ttf"), fill=A.hex_rgb(A.TIER_COLORS["platina"]) if s["platina"] else (170, 176, 188))
            y += 150
            d.rounded_rectangle((x, y, x + 760, y + 12), 6, fill=(38, 44, 56))
            if s["progresso"]:
                d.rounded_rectangle((x, y, x + max(12, int(760 * s["progresso"] / 100)), y + 12), 6,
                                    fill=A.hex_rgb(A.TIER_COLORS["platina"]) if s["platina"] else accent)
            y += 50
        p = self.playtimes().get(sg["appid"], {}) if sg else {}
        line = "  ·  ".join(v for v in (p.get("minutos") and f"{library.hours(p['minutos'])} jogadas",
                                        p.get("ultima") and f"jogado {library.ago(p['ultima'])}") if v)
        if line:
            d.text((x, y), line, font=A.pil_font(32, "segoeui.ttf"), fill=(214, 218, 226))
        # rodapé: símbolo + nome do app, jogador e data
        fy = H - 90
        icon = ROOT / f"{FR['icone']}.png"
        fx = 130
        if icon.exists():
            ic = Image.open(icon).convert("RGBA").resize((52, 52), Image.LANCZOS)
            img.alpha_composite(ic, (fx, fy - 6))
            fx += 70
        d.text((fx, fy), FR["app"], font=A.pil_font(34, "seguisb.ttf"), fill=(244, 244, 246))
        right = "  ·  ".join(v for v in (self.persona, datetime.now().strftime("%d/%m/%Y")) if v)
        rf = A.pil_font(30, "segoeui.ttf")
        d.text((W - 130 - d.textlength(right, font=rf), fy + 4), right, font=rf, fill=(190, 196, 206))
        out_dir = library.pictures_dir() / FR["app"]
        out_dir.mkdir(parents=True, exist_ok=True)
        out = out_dir / f"{ch['id']}_{datetime.now():%Y-%m-%d_%H-%M-%S}.png"
        img.convert("RGB").save(out)
        self.stat_count("fotos")
        self.toast("Foto do card salva", f"Imagens\\{FR['app']}\\{out.name} · clique para abrir", lambda: os.startfile(out))
        return out
