"""Cores, fontes e widgets reaproveitados pelas janelas."""
import threading
import tkinter as tk

BG, PANEL, PANEL_HI = "#0b0a09", "#171513", "#26221f"
RED, RED_DARK, TEXT, MUTED, GREEN = "#b3121b", "#7a0c12", "#ece6da", "#958c80", "#5fbf6f"
FONT = "Bahnschrift"
from ..franchise import FR, hex_rgb  # noqa: E402
RED = FR["cor"]
RED_DARK = "#%02x%02x%02x" % tuple(int(v * 0.65) for v in hex_rgb(RED))


def button(parent, text, cmd, primary=False):
    return tk.Button(parent, text=text, command=cmd, bd=0, cursor="hand2",
                     font=(FONT, 10, "bold" if primary else "normal"),
                     bg=RED if primary else PANEL_HI, fg=TEXT,
                     activebackground=RED_DARK, activeforeground=TEXT, padx=14, pady=6)


LINE = "#2c2723"
_logos = {}


def umbrella(size=22):
    """O simbolo da Umbrella (re_hub.png) no tamanho pedido, para cabecalhos de janelas e menus."""
    if size not in _logos:
        from PIL import Image, ImageTk
        from ..paths import ROOT
        try:
            img = Image.open(ROOT / "re_hub.png").convert("RGBA")
            img.thumbnail((size, size), Image.LANCZOS)
            _logos[size] = ImageTk.PhotoImage(img)
        except OSError:
            _logos[size] = None
    return _logos[size]


def brand_row(parent, bg, color, text=None):
    """Linha de marca: o simbolo da Umbrella e o nome do app (ou outro texto) em maiusculas."""
    row = tk.Frame(parent, bg=bg)
    logo = umbrella(20)
    if logo:
        tk.Label(row, image=logo, bg=bg).pack(side="left", padx=(0, 8))
    tk.Label(row, text=(text or FR["app"]).upper(), fg=color, bg=bg, font=(FONT, 9, "bold")).pack(side="left")
    return row
STYLES = {  # fundo, texto, borda, fundo com o mouse, fundo ao apertar
    "primary": (RED, "#ffffff", "#e0454c", "#e0353e", RED_DARK),
    "plain": ("#1d1a17", TEXT, "#3d3630", "#2b2622", "#141210"),
    "ghost": (PANEL, "#c4bcae", PANEL, "#221f1c", "#141210"),
    "danger": ("#241312", "#ff9a8a", "#5c2622", "#3d1a1a", "#1a0d0d"),
    "alert": ("#b8322a", "#ffffff", "#e05a4c", "#d4433a", "#7e221c"),   # confirmar algo que apaga ou tira
}


def mix(a, b, k):
    """Cor entre a e b (k de 0 a 1), para as transições suaves."""
    ra, rb = hex_rgb(a), hex_rgb(b)
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * k) for x, y in zip(ra, rb))


def fade(widget, option, start, end, steps=6, ms=16):
    """Troca a cor de um widget aos poucos (~100 ms) em vez de pular de uma vez."""
    job = getattr(widget, "_fade_job", None)
    if job:
        widget.after_cancel(job)

    def step(k):
        try:
            widget.config(**{option: mix(start, end, k / steps)})
        except tk.TclError:   # o widget fechou no meio
            return
        widget._fade_job = widget.after(ms, step, k + 1) if k < steps else None
    step(1)


def flat_button(parent, text, cmd, style="plain", icon=None):
    """Botao reto no visual do app: maiusculas espacadas, borda fina, acende aos poucos com o mouse e afunda ao
    apertar. icon: um simbolo curto antes do texto (ex.: '+', '✕', '▶')."""
    bg, fg, border, hover, press = STYLES.get(style, STYLES["plain"])
    label_text = text.upper()
    if icon:
        label_text = f"{icon}   {label_text}"
    b = tk.Label(parent, text=label_text, bg=bg, fg=fg, font=(FONT, 9, "bold"), padx=18, pady=8, cursor="hand2",
                 highlightthickness=1, highlightbackground=border, highlightcolor=border)
    state = {"in": False}

    def enter(e):
        state["in"] = True
        fade(b, "bg", b.cget("bg"), hover)
        b.config(highlightbackground=mix(border, "#ffffff", 0.25))

    def leave(e):
        state["in"] = False
        fade(b, "bg", b.cget("bg"), bg)
        b.config(highlightbackground=border)

    def down(e):
        b.config(bg=press)

    def up(e):
        b.config(bg=hover if state["in"] else bg)
        if state["in"]:
            cmd()
    b.bind("<Enter>", enter)
    b.bind("<Leave>", leave)
    b.bind("<ButtonPress-1>", down)
    b.bind("<ButtonRelease-1>", up)
    return b


def section_title(parent, text, bg=PANEL, color=None):
    """Titulo de grupo: texto pequeno em maiusculas com um filete que vai ate a borda."""
    row = tk.Frame(parent, bg=bg)
    tk.Label(row, text=text.upper(), fg=color or MUTED, bg=bg, font=(FONT, 8, "bold")).pack(side="left")
    tk.Frame(row, bg=LINE, height=1).pack(side="left", fill="x", expand=True, padx=(10, 0), pady=(2, 0))
    return row


def entry(parent, var, width=52, bg=PANEL):
    """Campo de texto escuro com filete que acende na cor da franquia quando esta em uso."""
    e = tk.Entry(parent, textvariable=var, bg="#0f0d0c", fg=TEXT, insertbackground=TEXT, relief="flat", font=(FONT, 11),
                 highlightthickness=1, highlightbackground="#3b342d", highlightcolor=RED, width=width)
    return e


def modal(parent, title, subtitle="", width=560, accent=None):
    """Janela por cima no visual do app (sem a moldura do Windows): o hub escurece atras, cartao reto com filete
    na cor da franquia, titulo, subtitulo e uma barra de botoes embaixo. Devolve (top, body, bar, close)."""
    p = parent.winfo_toplevel()
    shade = tk.Toplevel(p)
    shade.overrideredirect(True)
    shade.configure(bg="#000000")
    shade.geometry(f"{p.winfo_width()}x{p.winfo_height()}+{p.winfo_rootx()}+{p.winfo_rooty()}")
    shade.attributes("-alpha", 0.0)
    shade.attributes("-topmost", True)
    top = tk.Toplevel(p)
    top.withdraw()
    top.overrideredirect(True)
    top.configure(bg="#3b342d")
    top.attributes("-topmost", True)
    card = tk.Frame(top, bg=PANEL)
    card.pack(fill="both", expand=True, padx=1, pady=1)
    tk.Frame(card, bg=accent or RED, height=3).pack(fill="x")
    head = tk.Frame(card, bg=PANEL)
    head.pack(fill="x", padx=30, pady=(22, 0))
    brand_row(head, PANEL, accent or RED).pack(side="left")
    closed = {"v": False}

    def close(e=None):
        if closed["v"]:
            return
        closed["v"] = True
        top.destroy()
        shade.destroy()
    x_btn = tk.Label(head, text="✕", fg=MUTED, bg=PANEL, font=(FONT, 12), cursor="hand2", padx=4)
    x_btn.pack(side="right")
    x_btn.bind("<Button-1>", close)
    x_btn.bind("<Enter>", lambda e: x_btn.config(fg=TEXT))
    x_btn.bind("<Leave>", lambda e: x_btn.config(fg=MUTED))
    tk.Label(card, text=title, fg=TEXT, bg=PANEL, font=(FONT, 18, "bold"), anchor="w").pack(fill="x", padx=30, pady=(6, 0))
    if subtitle:
        tk.Label(card, text=subtitle, fg=MUTED, bg=PANEL, font=(FONT, 10), anchor="w", justify="left",
                 wraplength=width - 60).pack(fill="x", padx=30, pady=(4, 0))
    body = tk.Frame(card, bg=PANEL)
    body.pack(fill="both", expand=True, padx=30, pady=(16, 0))
    tk.Frame(card, bg=LINE, height=1).pack(fill="x", padx=30, pady=(18, 0))
    bar = tk.Frame(card, bg=PANEL)
    bar.pack(fill="x", padx=30, pady=(14, 22))
    top.bind("<Escape>", close)

    def place():
        top.update_idletasks()
        w, h = max(width, top.winfo_reqwidth()), top.winfo_reqheight()
        x = p.winfo_rootx() + (p.winfo_width() - w) // 2
        y = p.winfo_rooty() + max(20, (p.winfo_height() - h) // 3)
        top.geometry(f"{w}x{h}+{max(0, x)}+{max(0, y)}")

    def show():   # o fundo escurece aos poucos e o cartao aparece
        place()
        top.deiconify()
        top.lift()
        top.grab_set()
        top.focus_force()
        for k in range(1, 7):
            top.after(k * 18, lambda a=k * 0.09: shade.winfo_exists() and shade.attributes("-alpha", a))
    top.after(1, show)
    top.place_again = place   # quando o conteudo muda de tamanho
    return top, body, bar, close


def label(parent, text, size=10, bold=False, fg=TEXT, bg=PANEL, **kw):
    return tk.Label(parent, text=text, fg=fg, bg=bg, font=(FONT, size, "bold" if bold else "normal"),
                    anchor="w", justify="left", **kw)


def in_background(widget, work, done, fail):
    """Roda work() numa thread e chama done(resultado) ou fail(mensagem) de volta na interface."""
    def runner():
        try:
            result = work()
            widget.after(0, lambda: done(result))
        except Exception as e:  # mostra qualquer erro ao usuário em vez de travar
            msg = str(e)
            widget.after(0, lambda: fail(msg))
    threading.Thread(target=runner, daemon=True).start()


class ScrollFrame(tk.Frame):
    """Frame com barra de rolagem; coloque os widgets em .inner."""

    def __init__(self, parent, bg=BG):
        super().__init__(parent, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        sb = tk.Canvas(self, width=6, bg=bg, highlightthickness=0)   # barra fina no lugar da do Windows
        sb.pack(side="right", fill="y", padx=(6, 0))
        thumb = sb.create_rectangle(0, 0, 6, 0, fill="#4a423a", outline="")

        def moved(first, last):
            h = sb.winfo_height()
            f, l = float(first), float(last)
            sb.coords(thumb, 0, f * h, 6, l * h)
            sb.itemconfigure(thumb, state="hidden" if f <= 0 and l >= 1 else "normal")
        self.canvas.configure(yscrollcommand=moved)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(win, width=e.width))
        # rola só a janela que está sob o mouse
        self.canvas.bind("<Enter>", lambda e: self.canvas.bind_all("<MouseWheel>", self._wheel))
        self.canvas.bind("<Leave>", lambda e: self.canvas.unbind_all("<MouseWheel>"))

    def _wheel(self, e):
        self.canvas.yview_scroll(-e.delta // 120, "units")

    def clear(self):
        for w in self.inner.winfo_children():
            w.destroy()
        self.canvas.yview_moveto(0)


# ---------- caixas de diálogo e interruptor no visual do app (no lugar das caixas brancas do Windows) ----------
def _dialog(parent, title, message, details=(), buttons=(("OK", True, "primary"),), icon="!", accent=RED):
    """Janela modal no visual do app: a tela escurece atras, um cartao reto com filete na cor do aviso.
    buttons: (texto, valor devolvido, estilo 'primary'|'danger'|'plain'). Enter = ultimo botao, Esc = fechar."""
    p = parent.winfo_toplevel()
    shade = tk.Toplevel(p)   # escurece o hub atras do aviso
    shade.overrideredirect(True)
    shade.configure(bg="#000000")
    shade.geometry(f"{p.winfo_width()}x{p.winfo_height()}+{p.winfo_rootx()}+{p.winfo_rooty()}")
    shade.attributes("-alpha", 0.55)
    shade.attributes("-topmost", True)
    top = tk.Toplevel(p)
    top.withdraw()
    top.overrideredirect(True)
    top.title(FR["app"])
    top.configure(bg="#3b342d")   # a borda de 1 px
    result = {"v": None}

    def close(v):
        result["v"] = v
        top.destroy()
        shade.destroy()

    card = tk.Frame(top, bg=PANEL)
    card.pack(fill="both", expand=True, padx=1, pady=1)
    tk.Frame(card, bg=accent, height=3).pack(fill="x")
    body = tk.Frame(card, bg=PANEL)
    body.pack(fill="both", padx=30, pady=(22, 6))
    brand_row(body, PANEL, accent).pack(fill="x")
    tk.Label(body, text=title, fg=TEXT, bg=PANEL, font=(FONT, 17, "bold"), anchor="w", justify="left",
             wraplength=440).pack(fill="x", pady=(4, 0))
    tk.Label(body, text=message, fg="#c4bcae", bg=PANEL, font=(FONT, 11), anchor="w", justify="left",
             wraplength=440).pack(fill="x", pady=(8, 0))
    for d in details:
        tk.Label(body, text="—  " + d, fg=MUTED, bg=PANEL, font=(FONT, 10), anchor="w", justify="left",
                 wraplength=440).pack(fill="x", pady=(3, 0))
    bar = tk.Frame(card, bg=PANEL)
    bar.pack(fill="x", padx=30, pady=(18, 24))
    for text, value, style in reversed(buttons):
        b = flat_button(bar, text, lambda v=value: close(v), style)
        b.config(font=(FONT, 10, "bold"), padx=22, pady=9)
        b.pack(side="right", padx=(10, 0))
    top.bind("<Escape>", lambda e: close(None))
    top.bind("<Return>", lambda e: close(buttons[-1][1]))
    top.protocol("WM_DELETE_WINDOW", lambda: close(None))
    top.update_idletasks()
    w = max(top.winfo_reqwidth(), 500)
    x = p.winfo_rootx() + (p.winfo_width() - w) // 2
    y = p.winfo_rooty() + (p.winfo_height() - top.winfo_reqheight()) // 3
    top.geometry(f"{w}x{top.winfo_reqheight()}+{max(0, x)}+{max(0, y)}")
    top.deiconify()
    top.attributes("-topmost", True)  # sempre na frente, inclusive da tela cheia (atras dela o app parecia travado)
    top.lift()
    top.grab_set()
    top.focus_force()
    parent.wait_window(top)
    return result["v"]


def confirm(parent, title, message, details=(), ok="Confirmar", danger=False):
    return bool(_dialog(parent, title, message, details, (("Cancelar", False, "plain"), (ok, True, "alert" if danger else "primary")),
                        icon="?" if not danger else "!", accent="#c0392b" if danger else RED))


def notice(parent, title, message, details=(), error=False):
    _dialog(parent, title, message, details, (("OK", True, "primary"),), icon="!" if error else "✓",
            accent="#c0392b" if error else GREEN)


class Switch(tk.Canvas):
    """Interruptor liga/desliga (estilo PS5)."""

    def __init__(self, parent, on, command, bg=PANEL):
        super().__init__(parent, width=46, height=24, bg=bg, highlightthickness=0, cursor="hand2")
        self.on, self.command = on, command
        self._draw()
        self.bind("<Button-1>", lambda e: self.command(not self.on))

    def _draw(self):
        self.delete("all")
        fill = GREEN if self.on else "#3f3830"
        self.create_oval(1, 1, 23, 23, fill=fill, outline="")
        self.create_oval(23, 1, 45, 23, fill=fill, outline="")
        self.create_rectangle(12, 1, 34, 23, fill=fill, outline="")
        kx = 25 if self.on else 3
        self.create_oval(kx, 3, kx + 18, 21, fill="white", outline="")
