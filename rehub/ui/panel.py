"""Painel da direita da tela principal: abas Troféus, Trailer, Versões, DLCs (Wiki, Prints e Speedrun vêm
das telas por cima). Mixin do Hub (rehub/ui/app.py)."""
import os
import tkinter as tk
import urllib.parse
import webbrowser

from .. import sources, steam, trailer, trophies
from ..franchise import FR
from . import skin, theme as t
from .art import CHIP, DIM, MUTED, TIER_COLORS, TIER_NAMES, WHITE


class Panel:
    # ---------- painel da direita ----------
    def steam_game(self):
        """Versão selecionada se for da Steam; senão, a versão Steam do mesmo capítulo."""
        g = self.game
        return g if g["tipo"] == "steam" else next((v for v in self.chapter["versoes"] if v["tipo"] == "steam"), None)

    def _draw_panel(self, x1, y1, x2, y2):
        c, pad = self.c, 24
        x, y, w = x1 + pad, y1 + 18, x2 - x1 - 2 * pad
        tabs = self._panel_tabs()  # filmes, HQs e perdidos: só os detalhes
        active = self.panel_tab if any(k == self.panel_tab for k, _ in tabs) else tabs[0][0]
        if active != "trailer":
            self._trailer_stop()
        # abas como fichas de arquivo: texto em maiusculas, a ativa sublinhada na cor do capitulo,
        # todas dentro do painel (a folga encolhe para caberem)
        font = self.f["tiny"]
        labels = [label.upper() for _, label in tabs]
        texts = [font.measure(label) for label in labels]
        inner = w
        pad = max(12, min(30, (inner - sum(texts)) // len(tabs)))
        widths = [tw + pad for tw in texts]
        if sum(widths) > inner:
            widths = [inner / len(tabs)] * len(tabs)
        c.create_line(x, y + 25, x + w, y + 25, fill="#2c2723")
        tx = x
        for (key, _), label, tw in zip(tabs, labels, widths):
            on = active == key
            tag = f"tab_{key}"
            c.create_rectangle(tx, y - 4, tx + tw, y + 25, fill="", outline="", tags=(tag,))   # área do clique
            txt = c.create_text(tx + tw / 2, y + 11, text=self._elide(label, font, tw - 6),
                                fill=WHITE if on else MUTED, font=font, tags=(tag,))
            if on:
                c.create_rectangle(tx + 4, y + 23, tx + tw - 4, y + 26, fill=self.accent, outline="")
            self._clickable(tag, lambda k=key: self.set_tab(k), hover=None if on else [(txt, MUTED, WHITE)])
            tx += tw
        body = (x, y + 44, w, y2 - 14)
        if active == "trailer":
            return self._draw_trailer(*body)
        if active == "versoes":
            return self._draw_versions(self.chapter, *body)
        if active == "prints":
            return self._draw_prints(self.game, *body)
        if active == "speedrun":
            return self._draw_speedrun(self.game, *body)
        if active == "wiki":
            return self._draw_wiki(self.chapter, self.game, *body)
        g = self.steam_game()
        if g is not None and g is not self.game:  # embaixo das abas (antes ficava por cima delas)
            right = x + w - (self.f["tiny"].measure("Atualizar") + 16 if self.panel_tab == "trofeus" else 0)
            c.create_text(right, y + 44, anchor="ne", text=f"de {g['versao']} (Steam)", fill=DIM, font=self.f["tiny"])
            body = (x, y + 68, w, y2 - 14)
        if self.panel_tab == "trofeus":  # o "Atualizar" fica numa linha própria, embaixo das abas
            body = (x, y + 68, w, y2 - 14)
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
        hub = [v for v in ch.get("versoes", []) if v.get("tipo") in ("steam", "local")]
        if hub:   # as versoes deste hub e de onde vem cada uma (clique abre a loja ou o GitHub)
            c.create_text(x, y - 4, anchor="nw", text=f"NO {FR['app'].upper()}", fill=WHITE, font=self.f["tiny"])
            yy = y + 16
            for k, v in enumerate(hub):
                src = sources.sources(v)
                tag = f"src_{v['id']}"
                name = v.get("versao") or v["nome"]
                where = " / ".join(s[0].split(":")[0] for s in src[:2]) or "Seu arquivo"
                c.create_rectangle(x - 4, yy - 2, x + w, yy + 20, fill="", outline="", tags=(tag,))
                t1 = c.create_text(x, yy, anchor="nw", text=self._elide(name, self.f["small"], w - 120), fill="#d9d2c5",
                                   font=self.f["small"], tags=(tag,))
                c.create_text(x + w, yy, anchor="ne", text=where, fill=self.accent if src else DIM, font=self.f["small"], tags=(tag,))
                if src:
                    self._clickable(tag, lambda u=src[0][1]: webbrowser.open(u), hover=[(t1, "#d9d2c5", WHITE)])
                yy += 22
            c.create_line(x, yy + 4, x + w, yy + 4, fill="#2c2723")
            y = yy + 20
        if not items:
            return self._note(x, y, w, "Ainda não há lista de versões para este jogo.")
        n = len(items)
        c.create_text(x, y - 4, anchor="nw", text={"noticias": "Notícia", "canais": "Ao vivo" if ch.get("ao_vivo") else "Vídeo"}.get(self.section) or f"{n} {'versões' if n > 1 else 'versão'}", fill=WHITE, font=self.f["h"])
        hint = {"midia": "onde assistir", "hqs": "onde ler", "perdidos": "o que sobrou", "fas": "onde encontrar", "noticias": FR["noticias"].get("fonte", ""),
                "canais": "Twitch" if ch.get("plataforma") == "twitch" else "YouTube"}.get(self.section, "onde jogar hoje")
        c.create_text(x + w, y - 2, anchor="ne", text=hint, fill=DIM, font=self.f["small"])

        def row(v, ry):
            yw = self.f["btn"].measure(str(v["ano"]))
            c.create_text(x, ry, anchor="nw", text=self._elide(v["nome"], self.f["btn"], w - yw - 16), fill=WHITE, font=self.f["btn"])
            c.create_text(x + w, ry, anchor="ne", text=str(v["ano"]), fill=MUTED, font=self.f["btn"])
            c.create_text(x, ry + 21, anchor="nw", text=self._elide(v["plataformas"], self.f["small"], w), fill=MUTED, font=self.f["small"])
            c.create_oval(x, ry + 43, x + 6, ry + 49, fill=self.accent, outline="")
            c.create_text(x + 12, ry + 38, anchor="nw", text=self._elide(v["onde"], self.f["small"], w - 12), fill="#d9d2c5",
                          font=self.f["small"])
        self._list_window(items, x, y + 30, w, bottom, 68, row)

    def _chip(self, x, y, label, cmd, tag, primary=False, anchor="w"):
        """Botão pequeno desenhado. anchor='e' alinha pela direita. Retorna a outra ponta."""
        icon = "x" if label.startswith("✕") else None
        text = label.lstrip("✕ ").strip() if icon else label
        opts = dict(style="primary" if primary else "plain", accent=self.accent, icon=icon, height=28, size=9, glow=6,
                    pad=12, radius=6, track=0.6)
        normal = skin.button_photo(text, state="normal", **opts)
        hot = lambda: skin.button_photo(text, state="hover", **opts)
        w = normal.width() - 12
        x1 = x - w if anchor == "e" else x
        item = self.c.create_image(x1 - 6, y - 6, image=normal, anchor="nw", tags=(tag,))
        self._clickable(tag, cmd, hover=[(item, normal, hot)])
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
            c.create_rectangle(x + w + 12, y, x + w + 14, bottom, fill="#26221f", outline="")
            c.create_rectangle(x + w + 12, by, x + w + 14, by + bar_h, fill=MUTED, outline="")

    def _draw_trophies(self, g, x, y, w, bottom):
        c = self.c
        if g is None:
            return self._note(x, y, w, "Este capítulo não tem versão na Steam, então não há troféus para mostrar.")
        if not self.steamid:
            return self._note(x, y, w, "Não encontrei sua conta Steam neste PC.")
        s = self.trophy_state.get(g["appid"])
        tag = "trophy_refresh"
        txt = c.create_text(x + w, y - 24, anchor="ne", text="Atualizar", fill=MUTED, font=self.f["tiny"], tags=(tag,))
        self._clickable(tag, self.refresh_trophies, hover=[(txt, MUTED, WHITE)])
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
