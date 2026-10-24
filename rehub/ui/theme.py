"""Cores, fontes e widgets reaproveitados pelas janelas."""
import threading
import tkinter as tk

BG, PANEL, PANEL_HI = "#0b0a09", "#171513", "#26221f"
RED, RED_DARK, TEXT, MUTED, GREEN = "#b3121b", "#7a0c12", "#ece6da", "#958c80", "#5fbf6f"
FONT = "Bahnschrift"
from ..franchise import FR, hex_rgb  # noqa: E402
RED = FR["cor"]
RED_DARK = "#%02x%02x%02x" % tuple(int(v * 0.65) for v in hex_rgb(RED))


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
def mix(a, b, k):
    """Cor entre a e b (k de 0 a 1), para as transições suaves."""
    ra, rb = hex_rgb(a), hex_rgb(b)
    return "#%02x%02x%02x" % tuple(int(x + (y - x) * k) for x, y in zip(ra, rb))


ICONS = {"REMOVER": "trash", "DESINSTALAR": "trash", "EXCLUIR": "trash", "EDITAR": "edit", "ABRIR": "link",
         "ADICIONAR": "plus", "BAIXAR": "down", "INSTALAR": "down", "SITE": "link", "PROCURAR .EXE": "folder",
         "JOGAR": "play", "ATUALIZAR": "refresh", "CONFIGURAR": "gear"}


def flat_button(parent, text, cmd, style="plain", icon=None, accent=None, height=36, size=10):
    """Botao desenhado (cantos suaves, gradiente, brilho no hover, afunda ao apertar). O icone sai do texto
    quando nao e dado (Remover = lixeira, Editar = lapis...); '+' vira o icone de mais."""
    from . import skin
    icon = {"+": "plus", "✕": "x", "▶": "play"}.get(icon, icon) or ICONS.get(text.upper())
    try:
        bg = parent.cget("bg")
    except tk.TclError:
        bg = PANEL
    opts = dict(style=style, accent=accent or RED, icon=icon, height=height, size=size, glow=4)
    imgs = {st: skin.button_photo(text, state=st, **opts) for st in ("normal", "hover", "press")}
    b = tk.Label(parent, image=imgs["normal"], bg=bg, bd=0, cursor="hand2", takefocus=0)
    b._imgs = imgs
    state = {"in": False}

    def enter(e):
        state["in"] = True
        b.config(image=imgs["hover"])

    def leave(e):
        state["in"] = False
        b.config(image=imgs["normal"])

    def up(e):
        b.config(image=imgs["hover"] if state["in"] else imgs["normal"])
        if state["in"]:
            cmd()
    b.bind("<Enter>", enter)
    b.bind("<Leave>", leave)
    b.bind("<ButtonPress-1>", lambda e: b.config(image=imgs["press"]))
    b.bind("<ButtonRelease-1>", up)
    return b


def section_title(parent, text, bg=PANEL, color=None):
    """Titulo de grupo: ponto e texto pequeno em maiusculas com um filete que vai ate a borda."""
    row = tk.Frame(parent, bg=bg)
    c = color or MUTED
    dot = tk.Canvas(row, width=6, height=6, bg=bg, highlightthickness=0)
    dot.create_oval(0, 0, 5, 5, fill=c, outline="")
    dot.pack(side="left", padx=(0, 7))
    tk.Label(row, text=" ".join(text.upper()) if len(text) < 14 else text.upper(), fg=c, bg=bg,
             font=(FONT, 8, "bold")).pack(side="left")
    tk.Frame(row, bg=LINE, height=1).pack(side="left", fill="x", expand=True, padx=(10, 0), pady=(2, 0))
    return row


def entry(parent, var, width=52, bg=PANEL):
    """Campo de texto escuro com moldura que acende na cor da franquia quando esta em uso."""
    box = tk.Frame(parent, bg="#3b342d", padx=1, pady=1)
    e = tk.Entry(box, textvariable=var, bg="#100e0d", fg=TEXT, insertbackground=TEXT, relief="flat", font=(FONT, 11),
                 highlightthickness=0, width=width, selectbackground=RED, selectforeground="#ffffff")
    e.pack(fill="both", expand=True, ipadx=10, ipady=7)
    e.bind("<FocusIn>", lambda ev: box.config(bg=RED))
    e.bind("<FocusOut>", lambda ev: box.config(bg="#3b342d"))
    box.focus_set = e.focus_set
    return box


def dropdown(parent, var, options, accent=None):
    """Caixa de escolha no visual do app (no lugar do OptionMenu do Windows): abre um menu desenhado com rolagem."""
    from . import skin
    box = tk.Frame(parent, bg="#3b342d", padx=1, pady=1, cursor="hand2")
    inner = tk.Frame(box, bg="#100e0d")
    inner.pack(fill="both", expand=True)
    lab = tk.Label(inner, textvariable=var, bg="#100e0d", fg=TEXT, font=(FONT, 11), anchor="w", padx=10, pady=7)
    lab.pack(side="left", fill="x", expand=True)
    arrow = tk.Label(inner, image=skin.icon_photo("chevron", 14, MUTED), bg="#100e0d", padx=10)
    arrow.pack(side="right")

    def pick(v):
        var.set(v)

    def open_menu(e=None):
        sel = options.index(var.get()) if var.get() in options else 0
        box.config(bg=accent or RED)
        skin.Menu(parent.winfo_toplevel(), [(None, [(o, "", lambda o=o: pick(o), "dot") for o in options])],
                  box.winfo_rootx() - 14, box.winfo_rooty() + box.winfo_height() + 2, accent or RED,
                  width=max(260, box.winfo_width() + 28 - 28), max_height=360, selected=sel,
                  on_close=lambda: box.winfo_exists() and box.config(bg="#3b342d"))
    for w in (box, inner, lab, arrow):
        w.bind("<Button-1>", open_menu)
        w.bind("<Enter>", lambda e: box.config(bg="#6b6158") if box.cget("bg") == "#3b342d" else None)
        w.bind("<Leave>", lambda e: box.config(bg="#3b342d") if box.cget("bg") == "#6b6158" else None)
    return box


def modal(parent, title, subtitle="", width=560, accent=None, badge=None):
    """Janela por cima no visual do app: o hub escurece atras e um cartao de cantos arredondados (desenhado) aparece
    com um leve deslize. badge: (icone, cor) num circulo ao lado do titulo. Devolve (top, body, bar, close)."""
    from PIL import ImageTk
    from . import skin
    accent = accent or RED
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
    top.configure(bg=skin.KEY)
    top.attributes("-topmost", True)
    try:
        top.attributes("-transparentcolor", skin.KEY)
    except tk.TclError:
        pass
    c = tk.Canvas(top, bg=skin.KEY, highlightthickness=0)
    c.pack(fill="both", expand=True)
    inner = tk.Frame(c, bg=PANEL)
    body = tk.Frame(inner, bg=PANEL)
    body.pack(fill="both", expand=True)
    tk.Frame(inner, bg=LINE, height=1).pack(fill="x", pady=(20, 0))
    bar = tk.Frame(inner, bg=PANEL)
    bar.pack(fill="x", pady=(14, 0))
    closed = {"v": False}
    PADX, PADB = 30, 22

    def close(e=None):
        if closed["v"]:
            return
        closed["v"] = True
        top.destroy()
        shade.destroy()
    top.close = close
    win = c.create_window(PADX, 0, window=inner, anchor="nw")

    def place():
        if not top.winfo_exists():
            return
        inner.update_idletasks()
        W = max(width, inner.winfo_reqwidth() + 2 * PADX)
        c.delete("head")
        x = PADX
        logo = umbrella(18)
        if logo:
            c.create_image(x, 32, image=logo, anchor="w", tags=("head",))
        c.create_text(x + (26 if logo else 0), 32, anchor="w", text=FR["app"].upper(), fill=accent, font=(FONT, 9, "bold"), tags=("head",))
        xb = c.create_image(W - PADX + 6, 32, image=skin.icon_photo("x", 16, MUTED), anchor="e", tags=("head", "xbtn"))
        c.tag_bind("xbtn", "<Button-1>", close)
        c.tag_bind("xbtn", "<Enter>", lambda e: (c.itemconfigure(xb, image=skin.icon_photo("x", 16, TEXT)), c.config(cursor="hand2")))
        c.tag_bind("xbtn", "<Leave>", lambda e: (c.itemconfigure(xb, image=skin.icon_photo("x", 16, MUTED)), c.config(cursor="")))
        tx, y = x, 56
        if badge:
            c.create_image(x, y + 2, image=skin.badge_photo(badge[0], badge[1], 44), anchor="nw", tags=("head",))
            tx += 58
        t1 = c.create_text(tx, y, anchor="nw", text=title, fill=TEXT, font=(FONT, 18, "bold"), width=W - tx - PADX, tags=("head",))
        y = c.bbox(t1)[3] + 4
        if subtitle:
            t2 = c.create_text(tx, y, anchor="nw", text=subtitle, fill="#b3aa9d", font=(FONT, 10), width=W - tx - PADX, tags=("head",))
            y = c.bbox(t2)[3]
        if badge:
            y = max(y, 56 + 50)
        y += 18
        c.coords(win, PADX, y)
        c.itemconfigure(win, width=W - 2 * PADX)
        inner.update_idletasks()
        H = y + inner.winfo_reqheight() + PADB
        top._bg = ImageTk.PhotoImage(skin.panel_image(W, H, accent, radius=14, header=y))
        c.delete("bg")
        c.create_image(0, 0, image=top._bg, anchor="nw", tags=("bg",))
        c.tag_lower("bg")
        c.config(width=W, height=H)
        X = p.winfo_rootx() + (p.winfo_width() - W) // 2
        Y = p.winfo_rooty() + max(20, (p.winfo_height() - H) // 3)
        top._xy = (max(0, X), max(0, Y))
        top.geometry(f"{W}x{H}+{top._xy[0]}+{top._xy[1]}")

    def show():   # o fundo escurece e o cartao sobe um pouco enquanto aparece
        place()
        top.deiconify()
        top.lift()
        top.grab_set()
        top.focus_force()
        for k in range(1, 8):
            e = 1 - (1 - k / 7) ** 3
            top.after(k * 16, lambda a=e: shade.winfo_exists() and shade.attributes("-alpha", 0.6 * a))
            top.after(k * 16, lambda a=e: top.winfo_exists() and (top.attributes("-alpha", a),
                                                                  top.geometry(f"+{top._xy[0]}+{int(top._xy[1] + 10 * (1 - a))}")))
    top.attributes("-alpha", 0.0)
    top.bind("<Escape>", close)
    top.after(1, show)
    top.place_again = place
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
def _dialog(parent, title, message, details=(), buttons=(("OK", True, "primary"),), icon="alert", accent=RED):
    """Aviso no visual do app (cartao desenhado com icone num circulo). buttons: (texto, valor devolvido, estilo).
    Enter = ultimo botao, Esc = fechar."""
    result = {"v": None}
    top, body, bar, close = modal(parent, title, message, width=520, accent=accent, badge=(icon, accent))
    for d in details:
        row = tk.Frame(body, bg=PANEL)
        row.pack(fill="x", pady=(0, 5))
        tk.Frame(row, bg=accent, width=2).pack(side="left", fill="y", padx=(58, 10))
        tk.Label(row, text=d, fg=MUTED, bg=PANEL, font=(FONT, 10), anchor="w", justify="left", wraplength=400).pack(side="left", fill="x")
    if not details:
        body.config(height=1)

    def done(v):
        result["v"] = v
        close()
    for text, value, style in reversed(buttons):
        flat_button(bar, text, lambda v=value: done(v), style, height=38, size=10).pack(side="right", padx=(8, 0))
    top.bind("<Return>", lambda e: done(buttons[-1][1]))
    top.protocol("WM_DELETE_WINDOW", close)
    parent.wait_window(top)
    return result["v"]


def confirm(parent, title, message, details=(), ok="Confirmar", danger=False):
    return bool(_dialog(parent, title, message, details, (("Cancelar", False, "ghost"), (ok, True, "alert" if danger else "primary")),
                        icon="trash" if danger and ok.lower() in ("remover", "excluir", "desinstalar") else ("alert" if danger else "question"),
                        accent="#d63a30" if danger else RED))


def notice(parent, title, message, details=(), error=False):
    _dialog(parent, title, message, details, (("OK", True, "primary"),), icon="alert" if error else "check",
            accent="#d63a30" if error else GREEN)


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
