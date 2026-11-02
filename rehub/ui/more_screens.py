"""Mais telas por cima do hub: Maratona (zerar a linha do tempo em ordem), Quiz da franquia e Busca (Ctrl+F).
Como screens.py, é um mixin do Hub e desenha no mesmo canvas."""
import tkinter as tk

from .. import catalog, launcher, library, lore, quiz, search
from ..franchise import FR
from . import app as A, theme as t

MORE_KINDS = ("maratona", "quiz", "busca")
QUIZ_SIZE = 10


class MoreScreens:
    # ---------- entrada ----------
    def _more_extras(self):
        return [("maratona", "Maratona", "Zere a linha do tempo em ordem, com o que falta e o próximo jogo", "N"),
                ("quiz", "Quiz", f"{QUIZ_SIZE} perguntas sobre {FR['nome']}, tiradas do catálogo", "Z"),
                ("busca", "Busca", "Jogos, personagens, vírus e lugares numa busca só", "Ctrl+F")]

    def _more_titles(self):
        return {"maratona": ("Maratona", "↑ ↓ escolhem · Enter abre o jogo · X (ou G) marca como zerado"),
                "quiz": ("Quiz", "Setas escolhem a resposta · Enter confirma e passa para a próxima"),
                "busca": ("Busca", "Digite o nome · ↑ ↓ escolhem · Enter abre · Esc fecha")}

    def _more_open(self, kind):
        ov = self.overlay
        if kind == "maratona":
            nxt = self._marathon_next()
            ov["sel"] = next((i for i, ch in enumerate(self._marathon_items()) if nxt and ch["id"] == nxt["id"]), 0)
        elif kind == "quiz":
            self._quiz_new()
        elif kind == "busca":
            ov.update(query="", results=[])
            self._search_index = search.index(self.games)
            self.after(50, self._search_focus)

    def _more_press(self, kind, action):
        ov = self.overlay
        if kind == "maratona":
            items = self._marathon_items()
            if action in ("up", "down", "left", "right", "scroll_up", "scroll_down") and items:
                ov["sel"] = max(0, min(len(items) - 1, ov["sel"] + (-1 if action in ("up", "left", "scroll_up") else 1)))
                self._sound("select")
            elif action == "enter" and items:
                return self.goto_chapter(items[ov["sel"]]["id"])
            elif action == "manage" and items:
                self._marathon_toggle(items[ov["sel"]]["id"])
        elif kind == "quiz":
            self._quiz_press(action)
        elif kind == "busca":
            res = ov.get("results") or []
            if action in ("up", "down", "scroll_up", "scroll_down") and res:
                ov["sel"] = max(0, min(len(res) - 1, ov["sel"] + (-1 if action in ("up", "scroll_up") else 1)))
            elif action == "enter" and res:
                return self._search_open(res[ov["sel"]])
        self.refresh()

    # ---------- Maratona ----------
    def _marathon_items(self):
        return [ch for ch in catalog.load_timeline(self.games, "canon") if any(v.get("tipo") != "info" for v in ch["versoes"])]

    def _marathon_done(self):
        return set(self.cfg.get("_maratona").get("zerados", []))

    def _marathon_next(self):
        done = self._marathon_done()
        return next((ch for ch in self._marathon_items() if ch["id"] not in done), None)

    def _marathon_toggle(self, cid):
        done = self._marathon_done()
        done ^= {cid}
        self.cfg.set("_maratona", zerados=sorted(done))
        self._sound("prompt_enter" if cid in done else "back")
        self.after(300, self.check_achievements)
        self.refresh()

    def _chapter_minutes(self, ch):
        """Minutos jogados no capítulo: as versões da Steam (pela Steam) e as outras (pelo próprio hub)."""
        play = self.playtimes()
        return sum(play.get(v["appid"], {}).get("minutos", 0) if v.get("tipo") == "steam" else
                   self.cfg.get(v["id"]).get("minutos", 0) for v in ch["versoes"])

    def _draw_maratona(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        items, done = self._marathon_items(), self._marathon_done()
        est = lore.load("maratona").get("horas", {})
        left = sum(est.get(ch["id"], 0) for ch in items if ch["id"] not in done)
        nxt = self._marathon_next()
        n_done = sum(1 for ch in items if ch["id"] in done)
        c.create_text(x, y - 6, anchor="nw", text=f"{n_done} de {len(items)} zerados", fill=A.WHITE, font=self.f["h"])
        info = (f"Próximo: {nxt['titulo']}" if nxt else "Linha do tempo completa!") + (f"   ·   faltam ~{left} h" if left else "")
        c.create_text(x + 220, y - 4, anchor="nw", text=info, fill=self.accent if nxt else A.TIER_COLORS["ouro"],
                      font=self.f["body"])
        if done:
            self._chip(x + w, y - 8, "Recomeçar", self._marathon_reset, "mar_reset", anchor="e")
        bar_y = y + 26
        self._round_rect(x, bar_y, x + w, bar_y + 6, 3, fill=A.CHIP, outline="")
        if n_done:
            self._round_rect(x, bar_y, x + max(6, w * n_done / len(items)), bar_y + 6, 3, fill=self.accent, outline="")
        top, row_h = bar_y + 26, 58
        fits = max(1, int((bottom - top) // row_h))
        ov["scroll"] = max(0, min(ov["sel"] - fits // 2, len(items) - fits))
        for k, ch in enumerate(items[ov["scroll"]:ov["scroll"] + fits]):
            i = ov["scroll"] + k
            ry, on, ok = top + k * row_h, i == ov["sel"], ch["id"] in done
            tag = f"mar_{ch['id']}"
            self._round_rect(x, ry, x + w, ry + row_h - 8, 10, fill=A.CHIP_HI if on else "#141210",
                             outline=self.accent if on else "#26221f", tags=(tag,))
            box = f"marbox_{ch['id']}"
            c.create_rectangle(x + 16, ry + 13, x + 40, ry + 37, outline=A.TIER_COLORS["ouro"] if ok else A.MUTED, width=2,
                               fill="#2a2416" if ok else "", tags=(box,))
            if ok:
                c.create_text(x + 28, ry + 25, text="✓", fill=A.TIER_COLORS["ouro"], font=self.f["h"], tags=(box,))
            self._clickable(box, lambda cid=ch["id"]: self._marathon_toggle(cid))
            c.create_text(x + 56, ry + 8, anchor="nw", text=f"{i + 1}. {ch['titulo']}", fill=A.WHITE if not ok else A.MUTED,
                          font=self.f["btn"], tags=(tag,))
            ready = any(launcher.is_ready(v, self.cfg, self.installed) for v in ch["versoes"])
            sub = "   ·   ".join(p for p in (ch.get("quando"), "pronto para jogar" if ready else "nenhuma versão instalada") if p)
            c.create_text(x + 56, ry + 29, anchor="nw", text=sub, fill=A.GREEN if ready and not ok else A.DIM,
                          font=self.f["small"], tags=(tag,))
            mins = self._chapter_minutes(ch)
            hours = "   ·   ".join(p for p in (f"{library.hours(mins)} jogadas" if mins else "",
                                                 f"~{est[ch['id']]} h" if ch["id"] in est else "") if p)
            c.create_text(x + w - 18, ry + 20, anchor="e", text=hours, fill=A.MUTED, font=self.f["small"], tags=(tag,))
            self._clickable(tag, lambda i=i: (self.overlay.update(sel=i), self.refresh()) if self.overlay["sel"] != i
                            else self.goto_chapter(items[i]["id"]))
        c.create_text(x, bottom, anchor="sw", text="Horas estimadas: história principal, aproximadas (HowLongToBeat). "
                      "Clique no quadrado para marcar como zerado.", fill=A.DIM, font=self.f["small"])

    def _marathon_reset(self):
        if t.confirm(self, "Recomeçar a maratona?", "Todos os capítulos voltam a aparecer como não zerados.",
                     ok="Recomeçar", danger=True):
            self.cfg.set("_maratona", zerados=[])
            self.overlay["sel"] = 0
            self.refresh()

    # ---------- Quiz ----------
    def _quiz_new(self):
        qs = quiz.generate(self.games, QUIZ_SIZE)
        self.overlay.update(perguntas=qs, i=0, escolha=0, respondida=None, acertos=0)

    def _quiz_press(self, action):
        ov = self.overlay
        qs = ov["perguntas"]
        if ov["i"] >= len(qs):   # fim: Enter começa outra rodada
            if action == "enter":
                self._quiz_new()
            return
        q = qs[ov["i"]]
        if action in ("left", "right", "up", "down") and ov["respondida"] is None:
            d = {"left": -1, "right": 1, "up": -2, "down": 2}[action]
            ov["escolha"] = (ov["escolha"] + d) % len(q["opcoes"])
            self._sound("select")
        elif action == "enter":
            if ov["respondida"] is None:
                self._quiz_answer(ov["escolha"])
            else:
                self._quiz_next()

    def _quiz_answer(self, k):
        ov = self.overlay
        q = ov["perguntas"][ov["i"]]
        ov.update(escolha=k, respondida=k)
        if k == q["certa"]:
            ov["acertos"] += 1
            self._sound("prompt_enter")
        else:
            self._sound("back")
        self.refresh()

    def _quiz_next(self):
        ov = self.overlay
        ov.update(i=ov["i"] + 1, escolha=0, respondida=None)
        if ov["i"] >= len(ov["perguntas"]):   # fim da rodada: guarda o recorde
            st = self.cfg.get("_quiz")
            self.cfg.set("_quiz", recorde=max(st.get("recorde", 0), ov["acertos"]), partidas=st.get("partidas", 0) + 1)
            self.after(300, self.check_achievements)
        self.refresh()

    def _draw_quiz(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        qs = ov["perguntas"]
        best = self.cfg.get("_quiz").get("recorde", 0)
        if not qs:
            return self._note(x, y, w, "Não há dados suficientes no catálogo para montar perguntas.")
        if ov["i"] >= len(qs):
            n = ov["acertos"]
            c.create_text(x, y + 10, anchor="nw", text=f"{n} de {len(qs)}", fill=A.WHITE, font=self.f["big"])
            msg = ("Perfeito! Você conhece a franquia de cor." if n == len(qs) else "Mandou bem." if n >= len(qs) * 0.7
                   else "Dá para melhorar: as respostas estão nas telas de Extras.")
            c.create_text(x, y + 70, anchor="nw", text=msg, fill=A.MUTED, font=self.f["body"])
            c.create_text(x, y + 100, anchor="nw", text=f"Seu recorde: {best} de {len(qs)}", fill=A.TIER_COLORS["ouro"],
                          font=self.f["h"])
            self._chip(x, y + 150, "Jogar de novo (Enter)", self._quiz_new_refresh, "quiz_again", primary=True)
            return
        q = qs[ov["i"]]
        c.create_text(x, y - 6, anchor="nw", text=f"Pergunta {ov['i'] + 1} de {len(qs)}   ·   {ov['acertos']} certa(s)",
                      fill=A.MUTED, font=self.f["small"])
        c.create_text(x + w, y - 6, anchor="ne", text=f"Recorde: {best}/{len(qs)}", fill=A.DIM, font=self.f["small"])
        qt = c.create_text(x, y + 22, anchor="nw", text=q["pergunta"], fill=A.WHITE, font=self.f["title"], width=w)
        oy = c.bbox(qt)[3] + 28
        gap = 16
        cw, ch = (w - gap) / 2, 74
        for k, opt in enumerate(q["opcoes"]):
            ox, oy2 = x + (k % 2) * (cw + gap), oy + (k // 2) * (ch + gap)
            sel, answered = k == ov["escolha"], ov["respondida"] is not None
            right, picked = k == q["certa"], k == ov["respondida"]
            fill, line = ("#142417", A.GREEN) if answered and right else ("#2a1414", "#d0575b") if answered and picked \
                else (A.CHIP_HI, self.accent) if sel and not answered else ("#141210", "#26221f")
            tag = f"quiz_{k}"
            self._round_rect(ox, oy2, ox + cw, oy2 + ch, 10, fill=fill, outline=line, width=2 if sel or answered else 1,
                             tags=(tag,))
            c.create_text(ox + 20, oy2 + ch / 2, anchor="w", text="ABCD"[k], fill=line if line != "#26221f" else A.DIM,
                          font=self.f["h"], tags=(tag,))
            c.create_text(ox + 48, oy2 + ch / 2, anchor="w", text=opt, fill=A.WHITE, font=self.f["body"], width=cw - 64,
                          tags=(tag,))
            if not answered:
                self._clickable(tag, lambda k=k: self._quiz_answer(k))
        if ov["respondida"] is not None:
            ey = oy + 2 * (ch + gap) + 6
            ok = ov["respondida"] == q["certa"]
            c.create_text(x, ey, anchor="nw", text="Certa!" if ok else "Não foi dessa vez.", fill=A.GREEN if ok else "#e0857f",
                          font=self.f["h"])
            if q.get("explicacao"):
                c.create_text(x, ey + 26, anchor="nw", text=q["explicacao"], fill=A.MUTED, font=self.f["body"], width=w)
            bx = self._chip(x, ey + 86, "Próxima (Enter)", self._quiz_next, "quiz_next", primary=True) + 10
            if q.get("capitulo"):
                self._chip(bx, ey + 86, "Abrir o jogo", lambda: self.goto_chapter(q["capitulo"]), "quiz_open")

    def _quiz_new_refresh(self):
        self._quiz_new()
        self.refresh()

    # ---------- Busca ----------
    def _search_entry(self):
        if getattr(self, "_search_box", None) is None:
            var = tk.StringVar()
            box = t.entry(self.c, var, width=40)
            e = box.winfo_children()[0]
            e.config(font=(t.FONT, 16))
            e.bindtags((str(e), "Entry", "all"))   # sem as teclas do hub (A, D, W, S...) enquanto digita
            e.bind("<KeyRelease>", lambda ev: ev.keysym not in ("Up", "Down", "Return", "Escape") and self._search_typed())
            e.bind("<Return>", lambda ev: self._more_press("busca", "enter"))
            e.bind("<Up>", lambda ev: self._more_press("busca", "up"))
            e.bind("<Down>", lambda ev: self._more_press("busca", "down"))
            e.bind("<Escape>", lambda ev: self.close_overlay())
            self._search_box, self._search_var, self._search_input = box, var, e
        return self._search_box

    def _search_hide(self):
        """Some com o campo de busca quando a tela Busca não está aberta (chamado a cada redesenho)."""
        box = getattr(self, "_search_box", None)
        if box is not None and not (self.overlay and self.overlay["kind"] == "busca"):
            box.place_forget()

    def _search_focus(self):
        if self.overlay and self.overlay["kind"] == "busca" and getattr(self, "_search_input", None):
            self._search_input.focus_set()
        elif self.overlay and self.overlay["kind"] == "busca":
            self.after(50, self._search_focus)

    def _search_typed(self):
        ov = self.overlay
        if not ov or ov["kind"] != "busca":
            return
        ov.update(query=self._search_var.get(), sel=0,
                  results=search.find(self._search_index, self._search_var.get()))
        self.refresh()

    def _search_open(self, e):
        kind = e["alvo"][0]
        self._search_var.set("")
        if kind == "capitulo":
            return self.goto_chapter(e["alvo"][1], e["alvo"][2])
        if kind == "personagem":
            return self._open_person(e["alvo"][1])
        if kind == "virus":
            self.open_overlay("virus")
            self.overlay["sel"] = e["alvo"][1]
        elif kind == "lugar":
            self.open_overlay("mapa")
            self.overlay.update(aba=e["alvo"][1], sel=e["alvo"][2])
        self.refresh()

    def _draw_busca(self, x, y, w, bottom):
        c, ov = self.c, self.overlay
        box = self._search_entry()
        if self._search_var.get() != ov.get("query", ""):
            self._search_var.set(ov.get("query", ""))
        box.place(x=x, y=y - 4, width=min(w, 720))   # place: o redesenho do canvas não tira o foco do campo
        box.lift()
        res = ov.get("results") or []
        top = y + 84
        if not ov.get("query"):
            return self._note(x, top, w, "Comece a digitar: Leon, Nemesis, Raccoon, Code Veronica, G-Vírus...")
        if not res:
            return self._note(x, top, w, "Nada encontrado.")
        c.create_text(x, top - 10, anchor="sw", text=f"{len(res)} resultado(s)", fill=A.DIM, font=self.f["small"])
        row_h = 58
        fits = max(1, int((bottom - top) // row_h))
        scroll = max(0, min(ov["sel"] - fits + 1, len(res) - fits))
        for k, e in enumerate(res[scroll:scroll + fits]):
            i = scroll + k
            ry, on = top + k * row_h, i == ov["sel"]
            tag = f"srch_{i}"
            self._round_rect(x, ry, x + w, ry + row_h - 6, 8, fill=A.CHIP_HI if on else "#141210",
                             outline=self.accent if on else "#26221f", tags=(tag,))
            label = search.KIND_NAMES[e["tipo"]].upper()
            c.create_text(x + 16, ry + 26, anchor="w", text=label, fill=self.accent if on else A.DIM, font=self.f["tiny"],
                          tags=(tag,))
            c.create_text(x + 120, ry + 8, anchor="nw", text=self._elide(e["titulo"], self.f["btn"], w - 140), fill=A.WHITE,
                          font=self.f["btn"], tags=(tag,))
            if e.get("sub"):
                c.create_text(x + 120, ry + 29, anchor="nw", text=self._elide(e["sub"], self.f["small"], w - 140),
                              fill=A.MUTED, font=self.f["small"], tags=(tag,))
            self._clickable(tag, lambda e=e: self._search_open(e))
