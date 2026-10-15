"""Cores, fontes e widgets reaproveitados pelas janelas."""
import threading
import tkinter as tk

BG, PANEL, PANEL_HI = "#0b0e14", "#161b25", "#232a37"
RED, RED_DARK, TEXT, MUTED, GREEN = "#b3121b", "#7a0c12", "#e8e1e1", "#8f8585", "#5fbf6f"
FONT = "Segoe UI"
from ..franchise import FR, hex_rgb  # noqa: E402
RED = FR["cor"]
RED_DARK = "#%02x%02x%02x" % tuple(int(v * 0.65) for v in hex_rgb(RED))


def button(parent, text, cmd, primary=False):
    return tk.Button(parent, text=text, command=cmd, bd=0, cursor="hand2",
                     font=(FONT, 10, "bold" if primary else "normal"),
                     bg=RED if primary else PANEL_HI, fg=TEXT,
                     activebackground=RED_DARK, activeforeground=TEXT, padx=14, pady=6)


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
        sb = tk.Scrollbar(self, command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
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
    """Janela escura modal. buttons: (texto, valor devolvido, estilo 'primary'|'danger'|'plain'). Devolve o valor."""
    top = tk.Toplevel(parent)
    top.withdraw()
    top.title(FR["app"])
    top.configure(bg=PANEL)
    top.resizable(False, False)
    top.transient(parent.winfo_toplevel())
    result = {"v": None}

    def close(v):
        result["v"] = v
        top.destroy()

    tk.Frame(top, bg=accent, height=3).pack(fill="x")
    body = tk.Frame(top, bg=PANEL)
    body.pack(fill="both", padx=26, pady=(20, 10))
    ic = tk.Canvas(body, width=44, height=44, bg=PANEL, highlightthickness=0)
    ic.create_oval(2, 2, 42, 42, fill=accent, outline="")
    ic.create_text(22, 22, text=icon, fill="white", font=(FONT, 18, "bold"))
    ic.pack(side="left", anchor="n", padx=(0, 16))
    txt = tk.Frame(body, bg=PANEL)
    txt.pack(side="left", fill="both")
    label(txt, title, 13, bold=True, wraplength=380).pack(fill="x")
    label(txt, message, 10, fg="#c9c1c1", wraplength=380).pack(fill="x", pady=(6, 0))
    for d in details:
        label(txt, "•  " + d, 9, fg=MUTED, wraplength=380).pack(fill="x", pady=(3, 0))
    bar = tk.Frame(top, bg=BG)
    bar.pack(fill="x", side="bottom")
    for text, value, style in reversed(buttons):
        bg = {"primary": RED, "danger": "#c0392b"}.get(style, PANEL_HI)
        tk.Button(bar, text=text, command=lambda v=value: close(v), bd=0, cursor="hand2", padx=18, pady=7,
                  font=(FONT, 10, "bold" if style != "plain" else "normal"), bg=bg, fg=TEXT,
                  activebackground=RED_DARK, activeforeground=TEXT).pack(side="right", padx=(0, 10), pady=12)
    top.bind("<Escape>", lambda e: close(None))
    top.protocol("WM_DELETE_WINDOW", lambda: close(None))
    top.update_idletasks()
    p = parent.winfo_toplevel()
    x = p.winfo_rootx() + (p.winfo_width() - top.winfo_reqwidth()) // 2
    y = p.winfo_rooty() + (p.winfo_height() - top.winfo_reqheight()) // 3
    top.geometry(f"+{max(0, x)}+{max(0, y)}")
    top.deiconify()
    top.attributes("-topmost", True)  # sempre na frente, inclusive da tela cheia (atrás dela o app parecia travado)
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
        fill = GREEN if self.on else "#3a4150"
        self.create_oval(1, 1, 23, 23, fill=fill, outline="")
        self.create_oval(23, 1, 45, 23, fill=fill, outline="")
        self.create_rectangle(12, 1, 34, 23, fill=fill, outline="")
        kx = 25 if self.on else 3
        self.create_oval(kx, 3, kx + 18, 21, fill="white", outline="")
