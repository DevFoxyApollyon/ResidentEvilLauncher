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
STYLES = {  # fundo, texto, borda, fundo com o mouse
    "primary": (RED, TEXT, RED, "#d0343c"),
    "plain": (PANEL, TEXT, "#4a423a", PANEL_HI),
    "danger": ("#2a1414", "#ff9a8a", "#6b2a24", "#4a1d22"),
}


def flat_button(parent, text, cmd, style="plain"):
    """Botao reto no visual do app (maiusculas, borda fina, clareia com o mouse)."""
    bg, fg, border, hover = STYLES.get(style, STYLES["plain"])
    b = tk.Label(parent, text=text.upper(), bg=bg, fg=fg, font=(FONT, 9, "bold"), padx=16, pady=8, cursor="hand2",
                 highlightthickness=1, highlightbackground=border)
    b.bind("<Button-1>", lambda e: cmd())
    b.bind("<Enter>", lambda e: b.config(bg=hover))
    b.bind("<Leave>", lambda e: b.config(bg=bg))
    return b


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
    tk.Label(body, text=FR["app"].upper(), fg=accent, bg=PANEL, font=(FONT, 9, "bold"), anchor="w").pack(fill="x")
    tk.Label(body, text=title, fg=TEXT, bg=PANEL, font=(FONT, 17, "bold"), anchor="w", justify="left",
             wraplength=440).pack(fill="x", pady=(4, 0))
    tk.Label(body, text=message, fg="#c4bcae", bg=PANEL, font=(FONT, 11), anchor="w", justify="left",
             wraplength=440).pack(fill="x", pady=(8, 0))
    for d in details:
        tk.Label(body, text="—  " + d, fg=MUTED, bg=PANEL, font=(FONT, 10), anchor="w", justify="left",
                 wraplength=440).pack(fill="x", pady=(3, 0))
    bar = tk.Frame(card, bg=PANEL)
    bar.pack(fill="x", padx=30, pady=(18, 24))
    styles = {"primary": (accent, TEXT, accent), "danger": ("#c0392b", TEXT, "#c0392b"), "plain": (PANEL, TEXT, "#4a423a")}
    for text, value, style in reversed(buttons):
        bg, fg, border = styles.get(style, styles["plain"])
        hover = "#e04a3c" if style == "danger" else ("#d0343c" if style == "primary" else PANEL_HI)
        b = tk.Label(bar, text=text.upper(), bg=bg, fg=fg, font=(FONT, 10, "bold"), padx=22, pady=9, cursor="hand2",
                     highlightthickness=1, highlightbackground=border)
        b.pack(side="right", padx=(10, 0))
        b.bind("<Button-1>", lambda e, v=value: close(v))
        b.bind("<Enter>", lambda e, w=b, h=hover: w.config(bg=h))
        b.bind("<Leave>", lambda e, w=b, c=bg: w.config(bg=c))
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
    return bool(_dialog(parent, title, message, details, (("Cancelar", False, "plain"), (ok, True, "danger" if danger else "primary")),
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
