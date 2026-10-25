"""Instalador do RE Launcher: um .exe so (tools/build_installer.py) que traz o app inteiro.

Instala em %LOCALAPPDATA%\\Programs\\RE Launcher (ou na pasta escolhida), cria os atalhos na area de
trabalho e no menu Iniciar e registra o desinstalador em "Adicionar ou remover programas"
(so para este usuario: nada pede administrador). A pasta data/ de uma instalacao anterior
(configuracoes, jogos baixados, mods, musicas suas) nunca e apagada nem sobrescrita.

    "RE Launcher - Instalar.exe"          instala (janela)
    "RE Launcher - Instalar.exe" --uninstall   desinstala (o atalho do Windows chama assim)
"""
import os
import shutil
import subprocess
import sys
import threading
import tkinter as tk
import winreg
import zipfile
from pathlib import Path
from tkinter import filedialog

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageTk

APP = "RE Launcher"
EXE = "RE Launcher.exe"
UNINSTALLER = "Desinstalar RE Launcher.exe"
REG = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\REHub"
DEFAULT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / APP
BG, PANEL, LINE, TEXT, MUTED = "#0b0a09", "#151311", "#2c2723", "#ece6da", "#958c80"
RED, RED_HI, GREEN = "#c4111a", "#e02a33", "#5fbf6f"
FONT = "Bahnschrift"


def payload():
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / "payload.zip"


def version():
    try:
        with zipfile.ZipFile(payload()) as z:
            return z.read("VERSION").decode().strip()
    except (KeyError, OSError):
        return "?"


def shortcut(lnk, target, workdir, icon):
    ps = ("$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:L);"
          "$s.TargetPath=$env:T;$s.WorkingDirectory=$env:W;$s.IconLocation=$env:I;$s.Save()")
    env = dict(os.environ, L=str(lnk), T=str(target), W=str(workdir), I=str(icon))
    subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", ps], env=env,
                   check=True, capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)


def places():
    desk = Path(os.path.join(os.environ["USERPROFILE"], "Desktop"))
    try:  # a area de trabalho pode estar no OneDrive
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            desk = Path(os.path.expandvars(winreg.QueryValueEx(k, "Desktop")[0]))
    except OSError:
        pass
    menu = Path(os.environ["APPDATA"]) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
    return desk / f"{APP}.lnk", menu / f"{APP}.lnk"


def close_running():
    """Fecha o launcher (e o antigo RE Hub) se estiver aberto: com ele rodando, os arquivos de _internal ficam
    presos e a atualização parava em "Acesso negado"."""
    for exe in (EXE, "RE Hub.exe"):
        subprocess.run(["taskkill", "/IM", exe, "/F"], capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
    import time
    time.sleep(1.0)


def _rmtree(path, tries=6):
    import time
    for k in range(tries):   # o Windows solta os arquivos um instante depois de fechar o programa
        try:
            shutil.rmtree(path)
            return
        except FileNotFoundError:
            return
        except PermissionError:
            if k == tries - 1:
                raise
            time.sleep(0.8)


def install(dest, progress, desktop=True):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    close_running()
    with zipfile.ZipFile(payload()) as z:
        names = [n for n in z.namelist() if n != "VERSION"]
        old = dest / "_internal"
        if old.exists():  # a biblioteca do app e trocada inteira (arquivos de versoes antigas saem)
            _rmtree(old)
        for i, n in enumerate(names):
            target = dest / n
            if n.startswith("data/") and target.exists():
                continue  # dados do usuario: nunca sobrescreve
            z.extract(n, dest)
            if i % 40 == 0:
                progress(i / len(names))
    shutil.copy2(sys.executable, dest / UNINSTALLER)
    exe, icon = dest / EXE, dest / "re_hub.ico"
    desk, menu = places()
    for lnk in ([desk] if desktop else []) + [menu]:
        lnk.parent.mkdir(parents=True, exist_ok=True)
        shortcut(lnk, exe, dest, icon if icon.exists() else exe)
    if not desktop and desk.exists():   # desmarcou: tira o atalho que uma instalacao anterior criou
        desk.unlink()
    size = sum(f.stat().st_size for f in dest.rglob("*") if f.is_file() and "data" not in f.parts) // 1024
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG) as k:
        for name, value in (("DisplayName", APP), ("DisplayVersion", version()), ("Publisher", "DevFoxyApollyon"),
                            ("InstallLocation", str(dest)), ("DisplayIcon", str(icon if icon.exists() else exe)),
                            ("UninstallString", f'"{dest / UNINSTALLER}" --uninstall')):
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, value)
        winreg.SetValueEx(k, "EstimatedSize", 0, winreg.REG_DWORD, size)
        winreg.SetValueEx(k, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(k, "NoRepair", 0, winreg.REG_DWORD, 1)
    progress(1.0)


def installed_at():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
            return Path(winreg.QueryValueEx(k, "InstallLocation")[0])
    except OSError:
        return None


def asset(name):
    return Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent)) / name


def font(size, bold=False):
    for name in ("bahnschrift.ttf",):
        try:
            f = ImageFont.truetype(name, size)
            f.set_variation_by_name("Bold" if bold else "SemiBold")
            return f
        except (OSError, ValueError):
            pass
    return ImageFont.truetype("segoeuib.ttf" if bold else "segoeui.ttf", size)


def rgb(c):
    c = c.lstrip("#")
    return tuple(int(c[i:i + 2], 16) for i in (0, 2, 4))


def button_image(text, style, state, w=None, h=42, ss=3):
    """Botão desenhado (cantos suaves): primary = vermelho cheio; plain = vidro escuro com fio claro."""
    f = font(12 * ss, bold=True)
    label = text.upper()
    track = 1.4 * ss
    tw = sum(f.getlength(ch) + track for ch in label) - track
    W = int(w * ss) if w else int(tw + 46 * ss)
    H = h * ss
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    hot, down = state == "hover", state == "press"
    if style == "primary":
        base = rgb(RED_HI) if hot else rgb("#8f0e15") if down else rgb(RED)
        d.rounded_rectangle((0, 0, W - 1, H - 1), 6 * ss, fill=base + (255,))
        fg = (255, 255, 255, 255)
    elif style == "ghost":
        if hot or down:
            d.rounded_rectangle((0, 0, W - 1, H - 1), 6 * ss, fill=(255, 255, 255, 22))
        fg = (255, 255, 255, 255) if hot else rgb(MUTED) + (255,)
    else:
        fill = (52, 47, 42, 255) if hot else (24, 22, 20, 255)
        d.rounded_rectangle((0, 0, W - 1, H - 1), 6 * ss, fill=fill, outline=(255, 255, 255, 70 if hot else 34),
                            width=ss)
        fg = (255, 255, 255, 255) if hot else rgb(TEXT) + (255,)
    x = (W - tw) / 2
    for ch in label:
        d.text((x, H / 2), ch, font=f, fill=fg, anchor="lm")
        x += f.getlength(ch) + track
    return img.resize((W // ss, H // ss), Image.LANCZOS)


class Button(tk.Label):
    def __init__(self, parent, text, cmd, style="plain", w=None, bg=BG):
        self.imgs = {s: ImageTk.PhotoImage(button_image(text, style, s, w)) for s in ("normal", "hover", "press")}
        super().__init__(parent, image=self.imgs["normal"], bg=bg, bd=0, cursor="hand2")
        self.cmd, self.enabled, self._in = cmd, True, False
        self.bind("<Enter>", lambda e: self._set("hover", True))
        self.bind("<Leave>", lambda e: self._set("normal", False))
        self.bind("<ButtonPress-1>", lambda e: self.enabled and self.config(image=self.imgs["press"]))
        self.bind("<ButtonRelease-1>", self._release)

    def _set(self, state, inside):
        self._in = inside
        if self.enabled:
            self.config(image=self.imgs[state])

    def _release(self, e):
        if self.enabled:
            self.config(image=self.imgs["hover" if self._in else "normal"])
            if self._in:
                self.cmd()

    def set_enabled(self, on):
        self.enabled = on
        self.config(cursor="hand2" if on else "")


class Switch(tk.Canvas):
    """Interruptor liga/desliga com o texto ao lado (no lugar da caixinha do Windows)."""

    def __init__(self, parent, text, var, bg=BG):
        super().__init__(parent, height=30, bg=bg, highlightthickness=0, cursor="hand2")
        self.var, self.text = var, text
        self.bind("<Button-1>", lambda e: (var.set(not var.get()), self._draw()))
        self.bind("<Configure>", lambda e: self._draw())

    def _draw(self):
        self.delete("all")
        on = self.var.get()
        fill = RED if on else "#3a342f"
        self.create_oval(0, 5, 20, 25, fill=fill, outline="")
        self.create_oval(20, 5, 40, 25, fill=fill, outline="")
        self.create_rectangle(10, 5, 30, 25, fill=fill, outline="")
        kx = 22 if on else 2
        self.create_oval(kx, 7, kx + 16, 23, fill="white", outline="")
        self.create_text(54, 15, anchor="w", text=self.text, fill=TEXT, font=(FONT, 11))


def banner(w, h, subtitle):
    """Faixa do topo: brilho vermelho, o símbolo da Umbrella e o logo RESIDENT EVIL com LAUNCHER embaixo."""
    img = Image.new("RGB", (w, h), rgb(BG))
    glow = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(glow).ellipse((-60, -120, 300, 240), fill=rgb(RED) + (110,))
    img.paste(glow.filter(ImageFilter.GaussianBlur(70)), (0, 0), glow.filter(ImageFilter.GaussianBlur(70)))
    try:
        sym = Image.open(asset("re_hub.png")).convert("RGBA").resize((86, 86), Image.LANCZOS)
        img.paste(sym, (30, (h - 86) // 2 - 4), sym)
    except OSError:
        pass
    x = 134
    try:
        logo = Image.open(asset("re_logo.png")).convert("RGBA")
        logo = logo.resize((int(logo.width * 34 / logo.height), 34), Image.LANCZOS)
        img.paste(logo, (x, 42), logo)
    except OSError:
        ImageDraw.Draw(img).text((x, 42), "RESIDENT EVIL", font=font(30, True), fill=rgb(TEXT))
    d = ImageDraw.Draw(img)
    f = font(15, True)
    tx = x
    for ch in "LAUNCHER":
        d.text((tx, 88), ch, font=f, fill=rgb(TEXT))
        tx += f.getlength(ch) + 5
    d.text((x, 114), subtitle.upper(), font=font(11), fill=rgb(MUTED))
    d.line((0, h - 1, w, h - 1), fill=rgb(LINE))
    return img


class Window(tk.Tk):
    W = 600

    def __init__(self, uninstall):
        super().__init__()
        self.title(f"{APP} - {'Desinstalar' if uninstall else 'Instalar'}")
        self.configure(bg=BG, highlightthickness=1, highlightbackground="#3a342f")
        self.resizable(False, False)
        self.overrideredirect(True)   # sem a barra do Windows: X desenhado e arrasta pela faixa do topo
        ico = asset("re_hub.ico")
        if ico.exists():
            self.iconbitmap(default=str(ico))
        tk.Frame(self, bg=RED, height=3).pack(fill="x")
        sub = "Desinstalar" if uninstall else f"Instalar  ·  versão {version()}"
        self._banner = ImageTk.PhotoImage(banner(self.W, 150, sub))
        top = tk.Canvas(self, width=self.W, height=150, bg=BG, highlightthickness=0)
        top.pack(fill="x")
        top.create_image(0, 0, image=self._banner, anchor="nw")
        x_btn = top.create_text(self.W - 24, 22, text="✕", fill=MUTED, font=(FONT, 13), tags=("x",))
        top.tag_bind("x", "<Button-1>", lambda e: self.destroy())
        top.tag_bind("x", "<Enter>", lambda e: top.itemconfigure(x_btn, fill=TEXT))
        top.tag_bind("x", "<Leave>", lambda e: top.itemconfigure(x_btn, fill=MUTED))
        top.bind("<ButtonPress-1>", self._grab)
        top.bind("<B1-Motion>", self._drag)
        self.bind("<Escape>", lambda e: self.destroy())
        body = tk.Frame(self, bg=BG, padx=34, pady=22)
        body.pack(fill="both")
        self.body, self.uninstall = body, uninstall
        (self._uninstall_ui if uninstall else self._install_ui)()
        self.update_idletasks()
        w, h = self.W, self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth() - w) // 2}+{(self.winfo_screenheight() - h) // 3}")
        self.after(10, self._taskbar)

    def _taskbar(self):
        """Sem moldura a janela some da barra de tarefas; isto a põe de volta (com o ícone)."""
        try:
            import ctypes
            hwnd = ctypes.windll.user32.GetParent(self.winfo_id())
            style = ctypes.windll.user32.GetWindowLongW(hwnd, -20)
            ctypes.windll.user32.SetWindowLongW(hwnd, -20, (style & ~0x80) | 0x40000)   # sem TOOLWINDOW, com APPWINDOW
            self.withdraw()
            self.after(10, self.deiconify)
        except (AttributeError, OSError):
            pass

    def _grab(self, e):
        self._dx, self._dy = e.x_root - self.winfo_x(), e.y_root - self.winfo_y()

    def _drag(self, e):
        self.geometry(f"+{e.x_root - self._dx}+{e.y_root - self._dy}")

    def _label(self, text, size=10, fg=MUTED, bold=False, **kw):
        return tk.Label(self.body, text=text, fg=fg, bg=BG, font=(FONT, size, "bold" if bold else "normal"), anchor="w",
                        justify="left", **kw)

    def _status_bar(self):
        self.bar = tk.Canvas(self.body, height=6, bg=BG, highlightthickness=0)
        self.bar.pack(fill="x", pady=(18, 6))
        self.bar.bind("<Configure>", lambda e: self._progress_draw(getattr(self, "_frac", 0)))
        self.status = self._label("", 10)
        self.status.pack(fill="x")

    def _progress_draw(self, f):
        self._frac = f
        w = self.bar.winfo_width()
        self.bar.delete("all")
        self.bar.create_rectangle(0, 2, w, 5, fill="#2a2522", outline="")
        if f > 0:
            self.bar.create_rectangle(0, 2, w * f, 5, fill=RED, outline="")

    def _install_ui(self):
        prev = installed_at()
        self._label("PASTA DE INSTALAÇÃO", 9, bold=True).pack(fill="x")
        box = tk.Frame(self.body, bg="#3a342f", padx=1, pady=1)
        box.pack(fill="x", pady=(6, 8))
        inner = tk.Frame(box, bg="#141210")
        inner.pack(fill="x")
        self.path = tk.StringVar(value=str(prev or DEFAULT))
        e = tk.Entry(inner, textvariable=self.path, bg="#141210", fg=TEXT, insertbackground=TEXT, relief="flat",
                     font=(FONT, 11), highlightthickness=0, selectbackground=RED)
        e.pack(side="left", fill="x", expand=True, ipady=9, padx=(12, 6))
        Button(inner, "Alterar", self._browse, "ghost", bg="#141210").pack(side="right", padx=4, pady=3)
        e.bind("<FocusIn>", lambda ev: box.config(bg=RED))
        e.bind("<FocusOut>", lambda ev: box.config(bg="#3a342f"))
        note = tk.Frame(self.body, bg=BG)
        note.pack(fill="x", pady=(0, 16))
        dot = tk.Canvas(note, width=10, height=10, bg=BG, highlightthickness=0)
        dot.create_oval(1, 1, 9, 9, fill=GREEN if prev else MUTED, outline="")
        dot.pack(side="left", padx=(2, 8))
        tk.Label(note, text=("Já instalado aqui: atualiza (fecha o launcher se estiver aberto) e mantém seus dados." if prev else
                             "Atalho no menu Iniciar. Não precisa de administrador."),
                 fg=GREEN if prev else MUTED, bg=BG, font=(FONT, 10), anchor="w").pack(side="left")
        self.desktop = tk.BooleanVar(value=True)
        self.open_after = tk.BooleanVar(value=True)
        Switch(self.body, "Criar atalho na área de trabalho", self.desktop).pack(fill="x", pady=3)
        Switch(self.body, f"Abrir o {APP} quando terminar", self.open_after).pack(fill="x", pady=3)
        self._status_bar()
        bar = tk.Frame(self.body, bg=BG)
        bar.pack(fill="x", pady=(14, 0))
        self.go = Button(bar, "Instalar" if not prev else "Atualizar", self._start, "primary", w=160)
        self.go.pack(side="right")
        Button(bar, "Cancelar", self.destroy, "ghost").pack(side="right", padx=(0, 10))

    def _browse(self):
        d = filedialog.askdirectory(parent=self, initialdir=self.path.get())
        if d:
            p = Path(d)
            self.path.set(str(p if p.name.lower() in ("re hub", "re launcher") else p / APP))

    def _progress(self, f):
        self.after(0, lambda: (self._progress_draw(f), self.status.config(text=f"Instalando...  {f * 100:.0f}%")))

    def _start(self):
        self.go.set_enabled(False)
        self.status.config(text="Instalando...", fg=MUTED)
        dest, desktop = self.path.get(), self.desktop.get()

        def work():
            try:
                install(dest, self._progress, desktop)
                self.after(0, lambda: self._done(dest))
            except Exception as e:  # mostra o erro em vez de fechar calado
                msg = str(e)
                self.after(0, lambda: (self.status.config(text="Erro: " + msg, fg="#e0857f"), self.go.set_enabled(True)))
        threading.Thread(target=work, daemon=True).start()

    def _done(self, dest):
        self.status.config(text=f"Pronto. O {APP} está instalado.", fg=GREEN)
        if self.open_after.get():
            subprocess.Popen([str(Path(dest) / EXE)], cwd=dest)
            self.after(700, self.destroy)
        else:
            self.go.pack_forget()
            self.go = Button(self.go.master, "Fechar", self.destroy, "primary", w=160)
            self.go.pack(side="right")

    def _uninstall_ui(self):
        where = installed_at() or Path(sys.executable).parent
        self.where = where
        self._label(f"Remove o app de {where}, os atalhos e a entrada em Adicionar ou remover programas.", 11, fg=TEXT,
                    wraplength=500).pack(fill="x")
        self.keep = tk.BooleanVar(value=True)
        Switch(self.body, "Manter meus dados (ISOs, configurações, mods, músicas)", self.keep).pack(
            fill="x", pady=(14, 0))
        self.status = self._label("", 10)
        self.status.pack(fill="x", pady=(10, 0))
        bar = tk.Frame(self.body, bg=BG)
        bar.pack(fill="x", pady=(14, 0))
        Button(bar, "Desinstalar", self._remove, "primary", w=160).pack(side="right")
        Button(bar, "Cancelar", self.destroy, "ghost").pack(side="right", padx=(0, 10))

    def _remove(self):
        where = self.where
        for lnk in places():
            lnk.unlink(missing_ok=True)
        try:
            winreg.DeleteKey(winreg.HKEY_CURRENT_USER, REG)
        except OSError:
            pass
        for item in where.iterdir() if where.exists() else ():
            if item.name == UNINSTALLER or (item.name == "data" and self.keep.get()):
                continue
            shutil.rmtree(item, ignore_errors=True) if item.is_dir() else item.unlink(missing_ok=True)
        # o proprio desinstalador sai depois que este processo fechar
        rest = "" if self.keep.get() else f' & rmdir /s /q "{where}"'
        subprocess.Popen(f'cmd /c ping 127.0.0.1 -n 3 >nul & del /f /q "{where / UNINSTALLER}"{rest}',
                         creationflags=subprocess.CREATE_NO_WINDOW)
        self.status.config(text=f"{APP} removido.", fg=TEXT)
        self.after(900, self.destroy)


if __name__ == "__main__":
    Window("--uninstall" in sys.argv).mainloop()
