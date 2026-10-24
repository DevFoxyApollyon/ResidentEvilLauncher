"""Canais do YouTube e da Twitch no hub: a aba Canais, o aviso animado quando sai vídeo novo ou alguém entra ao
vivo, o selo AO VIVO pulsando no topo e a janela para escolher os canais. O Hub herda daqui (mixin)."""
import io
import math
import threading
import time
import tkinter as tk
import urllib.request
import webbrowser

from PIL import Image, ImageTk

from .. import catalog, channels, store
from . import theme as t

YT_RED, TWITCH = "#ff2b3b", "#9d6bff"
BANNER_W, BANNER_H = 440, 104
WHITE, MUTED, DIM = "#ece6da", "#a8a094", "#6b645b"


def _ease(k):
    return 1 - (1 - k) ** 3


class ChannelsUI:
    # ---------- busca em segundo plano ----------
    def _fetch_channels(self):
        """Confere vídeos novos e lives a cada 3 minutos enquanto o app estiver aberto."""
        while True:
            try:
                got = channels.refresh()
                if got is not None:
                    for ch in catalog.load_timeline(self.games, "canais"):
                        g = ch["versoes"][0]
                        if g.get("arte") and not store.art_path(store.art_key(g), "capa"):
                            store.download_art(g, "capa")
                    self.after(0, lambda got=got: self._channels_arrived(*got))
            except Exception:  # sem internet: fica com o que já tinha
                pass
            time.sleep(channels.MAX_AGE)

    def _channels_arrived(self, new_videos, new_lives):
        if self.section == "canais":
            cid = self.chapter["id"] if self.chapter else None
            self._build_chapters()
            self.sel = next((i for i, ch in enumerate(self.chapters) if ch["id"] == cid), 0)
        for l in new_lives:
            self.banner("live", l)
        for v in new_videos[:3]:   # muitos de uma vez (voltou a internet): só os 3 mais novos
            self.banner("video", v)
        self.refresh()

    def open_channel_item(self, item):
        """Clique no aviso: vai para a aba Canais com o vídeo/live escolhido."""
        self.overlay = None
        self.set_section("canais")
        key = item["id"]
        self.sel = next((i for i, ch in enumerate(self.chapters) if key in ch["id"]), 0)
        self.refresh()

    # ---------- aviso animado (desliza da direita, como as notificações da PS5) ----------
    def banner(self, kind, item):
        if not hasattr(self, "_banners"):
            self._banners, self._banner_on = [], False
        self._banners.append((kind, item))
        threading.Thread(target=self._banner_thumb, args=(item,), daemon=True).start()
        if not self._banner_on:
            self.after(400, self._next_banner)

    def _banner_thumb(self, item):
        if "_pil_thumb" in item:
            return
        try:
            req = urllib.request.Request(item["imagem"], headers={"User-Agent": channels.UA})
            with urllib.request.urlopen(req, timeout=10) as r:
                img = Image.open(io.BytesIO(r.read())).convert("RGB")
            w, h = 150, 84   # 16:9 cortado do centro (as do YouTube vêm com faixas pretas)
            k = max(w / img.width, h / img.height)
            img = img.resize((int(img.width * k) + 1, int(img.height * k) + 1), Image.LANCZOS)
            item["_pil_thumb"] = img.crop(((img.width - w) // 2, (img.height - h) // 2, (img.width - w) // 2 + w, (img.height - h) // 2 + h))
        except (OSError, ValueError):
            item["_pil_thumb"] = None

    def _next_banner(self):
        if not self._banners:
            self._banner_on = False
            return
        self._banner_on = True
        kind, item = self._banners.pop(0)
        live = kind == "live"
        color = TWITCH if item.get("plataforma") == "twitch" else YT_RED
        W = self.winfo_width()
        cv = tk.Canvas(self, width=BANNER_W, height=BANNER_H, bg="#151311", highlightthickness=1,
                       highlightbackground="#3b342d", cursor="hand2")
        cv.create_rectangle(0, 0, 4, BANNER_H, fill=color, outline="")
        thumb = item.get("_pil_thumb")
        tx = 16
        if thumb is not None:
            cv._img = ImageTk.PhotoImage(thumb)
            cv.create_image(tx, 10, image=cv._img, anchor="nw")
            if not live:   # botão de play sobre a miniatura
                cx, cy = tx + 75, 52
                cv.create_oval(cx - 16, cy - 12, cx + 16, cy + 12, fill=color, outline="")
                cv.create_polygon(cx - 5, cy - 6, cx - 5, cy + 6, cx + 7, cy, fill="#ffffff", outline="")
            tx += 150 + 14
        plat = "TWITCH" if item.get("plataforma") == "twitch" else "YOUTUBE"
        head = f"AO VIVO  ·  {plat}" if live else f"NOVO VÍDEO  ·  {plat}"
        dot = cv.create_oval(tx, 16, tx + 9, 25, fill=color, outline="")
        cv.create_text(tx + 15, 20, anchor="w", text=head, fill=color, font=(t.FONT, 9, "bold"))
        tw = BANNER_W - tx - 16
        title = item.get("titulo", "")
        f = self.f["btn"]
        lines, cur = [], ""
        for word in title.split():
            if f.measure((cur + " " + word).strip()) > tw and cur:
                lines.append(cur)
                cur = word
            else:
                cur = (cur + " " + word).strip()
        lines.append(cur)
        if len(lines) > 2:   # duas linhas no máximo
            lines = [lines[0], self._elide(" ".join(lines[1:]), f, tw)]
        cv.create_text(tx, 32, anchor="nw", text="\n".join(lines), fill=WHITE, font=f)
        sub = item.get("canal", "")
        if live and item.get("espectadores"):
            sub += f"  ·  {item['espectadores']} assistindo"
        cv.create_text(tx, BANNER_H - 14, anchor="w", text=self._elide(sub, self.f["small"], tw), fill=MUTED, font=self.f["small"])
        bar = cv.create_rectangle(4, BANNER_H - 2, BANNER_W, BANNER_H, fill=color, outline="")
        close = cv.create_text(BANNER_W - 10, 10, anchor="ne", text="✕", fill=DIM, font=(t.FONT, 9))
        y = 74
        hold, start = 9.0, time.time()
        state = {"phase": "in", "t0": start, "gone": False}
        x_in, x_out = W - 56 - BANNER_W, W + 10

        def finish():
            if state["gone"]:
                return
            state["gone"] = True
            cv.destroy()
            self.after(250, self._next_banner)

        def out(e=None):
            if state["phase"] != "out":
                state["phase"], state["t0"] = "out", time.time()

        def click(e):
            if cv.find_closest(e.x, e.y)[0] == close or e.x > BANNER_W - 26 and e.y < 24:
                return out()
            out()
            self.open_channel_item(item)
        cv.bind("<Button-1>", click)
        cv.bind("<Enter>", lambda e: (cv.config(highlightbackground=color), state.update(paused=True)))
        cv.bind("<Leave>", lambda e: (cv.config(highlightbackground="#3b342d"), state.update(paused=False)))

        def frame():
            if state["gone"] or not cv.winfo_exists():
                return
            now = time.time()
            if state["phase"] == "in":
                k = min(1, (now - state["t0"]) / 0.45)
                cv.place(x=x_out + (x_in - x_out) * _ease(k), y=y)
                if k >= 1:
                    state["phase"], state["t0"] = "hold", now
            elif state["phase"] == "hold":
                if state.get("paused"):   # mouse em cima: o tempo para
                    state["t0"] += now - state.get("last", now)
                k = min(1, (now - state["t0"]) / hold)
                cv.coords(bar, 4, BANNER_H - 2, 4 + (BANNER_W - 4) * (1 - k), BANNER_H)
                if k >= 1:
                    out()
            else:
                k = min(1, (now - state["t0"]) / 0.35)
                cv.place(x=x_in + (x_out - x_in) * (k * k), y=y)
                if k >= 1:
                    return finish()
            state["last"] = now
            pulse = (math.sin(now * (6 if live else 3)) + 1) / 2   # o ponto respira
            cv.itemconfigure(dot, fill=t.mix("#151311", color, 0.35 + 0.65 * pulse))
            tk.Misc.lift(cv)   # Canvas.lift sobe itens, nao o widget
            self.after(33, frame)
        cv.place(x=x_out, y=y)
        self._sound("trophy")
        frame()

    # ---------- selo AO VIVO no topo, ao lado das seções ----------
    def _live_pill_show(self, x, y):
        n = channels.live_count()
        pill = getattr(self, "_pill", None)
        if not n or self.overlay:
            if pill:
                pill.place_forget()
            return
        if pill is None or not pill.winfo_exists():
            pill = self._pill = tk.Canvas(self, height=24, bg=t.BG, highlightthickness=0, cursor="hand2")
            pill.bind("<Button-1>", lambda e: (self.set_section("canais"), self.refresh()))
            self._pill_pulse()
        text = f"AO VIVO  {n}" if n > 1 else "AO VIVO"
        w = self.f["tiny"].measure(text) + 34
        if getattr(pill, "_text", None) != text:
            pill.delete("all")
            pill.config(width=w)
            pill.create_rectangle(0, 0, w - 1, 23, fill="#2a0f12", outline=YT_RED)
            pill._dot = pill.create_oval(10, 8, 18, 16, fill=YT_RED, outline="")
            pill.create_text(24, 12, anchor="w", text=text, fill="#ffd9dc", font=self.f["tiny"])
            pill._text = text
        pill.place(x=x, y=y - 12)

    def _live_pill_hide(self):
        if getattr(self, "_pill", None):
            self._pill.place_forget()

    def _pill_pulse(self):
        pill = getattr(self, "_pill", None)
        if not pill or not pill.winfo_exists():
            return
        if pill.winfo_ismapped():
            k = (math.sin(time.time() * 5) + 1) / 2
            pill.itemconfigure(pill._dot, fill=t.mix("#4a1015", YT_RED, k))
        self.after(50, self._pill_pulse)

    # ---------- janela de canais ----------
    def channels_menu(self):
        """Opções > Canais: quais canais do YouTube e da Twitch o hub acompanha."""
        top, body, bar, close = t.modal(self, "Canais do YouTube e Twitch",
                                        "O hub avisa quando sai vídeo novo ou quando um destes canais entra ao vivo, e mostra "
                                        "tudo na aba Canais. No YouTube use o @ do canal; na Twitch, o nome.", width=640)
        listf = tk.Frame(body, bg=t.PANEL)
        listf.pack(fill="x")
        msg = tk.Label(body, text="", fg="#e0857f", bg=t.PANEL, font=(t.FONT, 10), anchor="w")

        def draw():
            for w in listf.winfo_children():
                w.destroy()
            cfg = channels.config()
            lives = {(l["plataforma"], l.get("canal_id", l["id"])) for l in channels.cached().get("lives", [])}
            for kind, label, color, items in (("youtube", "YouTube", YT_RED, cfg["youtube"]), ("twitch", "Twitch", TWITCH, cfg["twitch"])):
                t.section_title(listf, label, color=color).pack(fill="x", pady=(6, 6))
                if not items:
                    tk.Label(listf, text="Nenhum canal.", fg=DIM, bg=t.PANEL, font=(t.FONT, 10), anchor="w").pack(fill="x", pady=(0, 6))
                for it in items:
                    key = it if kind == "twitch" else (it.get("id") or it.get("handle"))
                    name = it if kind == "twitch" else (it.get("nome") or "@" + it.get("handle", ""))
                    sub = f"twitch.tv/{it}" if kind == "twitch" else ("@" + it["handle"] if it.get("handle") else it.get("id", ""))
                    on_air = (kind, it if kind == "twitch" else it.get("id")) in lives
                    row = tk.Frame(listf, bg="#141210", highlightthickness=1, highlightbackground="#2c2723")
                    row.pack(fill="x", pady=(0, 6))
                    tk.Frame(row, bg=color, width=3).pack(side="left", fill="y")
                    info = tk.Frame(row, bg="#141210")
                    info.pack(side="left", fill="x", expand=True, padx=12, pady=7)
                    top_line = tk.Frame(info, bg="#141210")
                    top_line.pack(fill="x")
                    tk.Label(top_line, text=name, fg=WHITE, bg="#141210", font=(t.FONT, 11, "bold"), anchor="w").pack(side="left")
                    if on_air:
                        tk.Label(top_line, text="  ● AO VIVO", fg=YT_RED, bg="#141210", font=(t.FONT, 8, "bold")).pack(side="left")
                    tk.Label(info, text=sub, fg=MUTED, bg="#141210", font=(t.FONT, 9), anchor="w").pack(fill="x")
                    link = f"https://www.twitch.tv/{it}" if kind == "twitch" else (
                        f"https://www.youtube.com/channel/{it['id']}" if it.get("id") else f"https://www.youtube.com/@{it.get('handle')}")
                    btns = tk.Frame(row, bg="#141210")
                    btns.pack(side="right", padx=10)
                    t.flat_button(btns, "Remover", lambda k=kind, v=key: (channels.remove(k, v), draw(), refetch()), "danger").pack(side="right", padx=(6, 0))
                    t.flat_button(btns, "Abrir", lambda u=link: webbrowser.open(u)).pack(side="right")
            top.place_again()

        t.section_title(body, "Adicionar canal").pack(fill="x", pady=(14, 6))
        row = tk.Frame(body, bg=t.PANEL)
        row.pack(fill="x")
        ref = tk.StringVar()
        e = t.entry(row, ref, width=30)
        e.pack(side="left", fill="x", expand=True, ipady=7)

        def add(kind):
            v = ref.get().strip()
            if not v:
                return msg.config(text="Digite o @ do canal do YouTube ou o nome na Twitch.", fg="#e0857f")
            msg.config(text="Procurando o canal...", fg=MUTED)

            def work():
                return channels.add_youtube(v) if kind == "youtube" else channels.add_twitch(v)

            def done(name):
                if not top.winfo_exists():
                    return
                ref.set("")
                msg.config(text=f"{name} adicionado. Os vídeos aparecem em instantes.", fg="#7ad18a")
                draw()
                refetch()

            def fail(m):
                if top.winfo_exists():
                    msg.config(text=m, fg="#e0857f")
            t.in_background(self, work, done, fail)
        t.flat_button(row, "YouTube", lambda: add("youtube"), "plain", icon="+").pack(side="left", padx=(8, 0))
        t.flat_button(row, "Twitch", lambda: add("twitch"), "plain", icon="+").pack(side="left", padx=(6, 0))
        msg.pack(fill="x", pady=(8, 0))

        def refetch():
            def work():
                return channels.refresh(force=True)
            t.in_background(self, work, lambda got: got and self._channels_arrived(*got) or self._channels_arrived([], []),
                            lambda m: None)
        draw()
        t.flat_button(bar, "Ver aba Canais", lambda: (close(), self.set_section("canais"), self.refresh()), "primary").pack(side="right")
        t.flat_button(bar, "Fechar", close, "ghost").pack(side="right", padx=(0, 8))
        top.after(60, e.focus_set)
