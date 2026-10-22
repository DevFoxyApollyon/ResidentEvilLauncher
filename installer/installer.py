"""Instalador do RE Hub: um .exe so (tools/build_installer.py) que traz o app inteiro.

Instala em %LOCALAPPDATA%\\Programs\\RE Hub (ou na pasta escolhida), cria os atalhos na area de
trabalho e no menu Iniciar e registra o desinstalador em "Adicionar ou remover programas"
(so para este usuario: nada pede administrador). A pasta data/ de uma instalacao anterior
(configuracoes, jogos baixados, mods, musicas suas) nunca e apagada nem sobrescrita.

    "RE Hub - Instalar.exe"               instala (janela)
    "RE Hub - Instalar.exe" --uninstall   desinstala (o atalho do Windows chama assim)
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

APP = "RE Hub"
EXE = "RE Hub.exe"
UNINSTALLER = "Desinstalar RE Hub.exe"
REG = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\REHub"
DEFAULT = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "Programs" / APP
BG, PANEL, LINE, TEXT, MUTED, RED = "#0b0a09", "#151311", "#2c2723", "#ece6da", "#958c80", "#b3121b"
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


def install(dest, progress):
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(payload()) as z:
        names = [n for n in z.namelist() if n != "VERSION"]
        old = dest / "_internal"
        if old.exists():  # a biblioteca do app e trocada inteira (arquivos de versoes antigas saem)
            shutil.rmtree(old)
        for i, n in enumerate(names):
            target = dest / n
            if n.startswith("data/") and target.exists():
                continue  # dados do usuario: nunca sobrescreve
            z.extract(n, dest)
            if i % 40 == 0:
                progress(i / len(names))
    shutil.copy2(sys.executable, dest / UNINSTALLER)
    exe, icon = dest / EXE, dest / "re_hub.ico"
    for lnk in places():
        lnk.parent.mkdir(parents=True, exist_ok=True)
        shortcut(lnk, exe, dest, icon if icon.exists() else exe)
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


class Window(tk.Tk):
    def __init__(self, uninstall):
        super().__init__()
        self.title(f"{APP} - {'Desinstalar' if uninstall else 'Instalar'}")
        self.configure(bg=BG)
        self.resizable(False, False)
        ico = Path(getattr(sys, "_MEIPASS", ".")) / "re_hub.ico"
        if ico.exists():
            self.iconbitmap(default=str(ico))
        tk.Frame(self, bg=RED, height=3).pack(fill="x")
        body = tk.Frame(self, bg=BG, padx=34, pady=26)
        body.pack(fill="both")
        tk.Label(body, text="RE HUB", fg=TEXT, bg=BG, font=(FONT, 26, "bold"), anchor="w").pack(fill="x")
        sub = "Desinstalar" if uninstall else f"Instalar versao {version()}"
        tk.Label(body, text=sub.upper(), fg=MUTED, bg=BG, font=(FONT, 10), anchor="w").pack(fill="x", pady=(0, 18))
        self.body, self.uninstall = body, uninstall
        (self._uninstall_ui if uninstall else self._install_ui)()
        self.update_idletasks()
        w, h = 560, self.winfo_reqheight()
        self.geometry(f"{w}x{h}+{(self.winfo_screenwidth() - w) // 2}+{(self.winfo_screenheight() - h) // 3}")

    def _button(self, parent, text, cmd, primary=True):
        b = tk.Button(parent, text=text.upper(), command=cmd, bd=0, cursor="hand2", font=(FONT, 11, "bold"),
                      bg=RED if primary else PANEL, fg=TEXT, activebackground="#d0343c" if primary else LINE,
                      activeforeground=TEXT, padx=22, pady=9, highlightthickness=1 if not primary else 0,
                      highlightbackground=LINE)
        return b

    def _install_ui(self):
        b = self.body
        prev = installed_at()
        tk.Label(b, text="PASTA", fg=MUTED, bg=BG, font=(FONT, 9), anchor="w").pack(fill="x")
        row = tk.Frame(b, bg=BG)
        row.pack(fill="x", pady=(4, 6))
        self.path = tk.StringVar(value=str(prev or DEFAULT))
        e = tk.Entry(row, textvariable=self.path, bg=PANEL, fg=TEXT, insertbackground=TEXT, relief="flat",
                     font=(FONT, 11), highlightthickness=1, highlightbackground=LINE, highlightcolor=MUTED)
        e.pack(side="left", fill="x", expand=True, ipady=7)
        self._button(row, "Escolher", self._browse, primary=False).pack(side="left", padx=(8, 0))
        note = ("Ja instalado aqui: atualiza o app e mantem seus dados (data/)." if prev else
                "Atalhos na area de trabalho e no menu Iniciar. Nao precisa de administrador.")
        tk.Label(b, text=note, fg=MUTED, bg=BG, font=(FONT, 10), anchor="w", wraplength=490,
                 justify="left").pack(fill="x", pady=(2, 16))
        self.open_after = tk.BooleanVar(value=True)
        tk.Checkbutton(b, text="Abrir o RE Hub no fim", variable=self.open_after, bg=BG, fg=TEXT,
                       selectcolor=PANEL, activebackground=BG, activeforeground=TEXT, font=(FONT, 10),
                       anchor="w").pack(fill="x")
        self.bar = tk.Canvas(b, height=4, bg=PANEL, highlightthickness=0)
        self.bar.pack(fill="x", pady=(18, 4))
        self.status = tk.Label(b, text="", fg=MUTED, bg=BG, font=(FONT, 10), anchor="w")
        self.status.pack(fill="x")
        bar = tk.Frame(b, bg=BG)
        bar.pack(fill="x", pady=(14, 0))
        self.go = self._button(bar, "Instalar", self._start)
        self.go.pack(side="right")
        self._button(bar, "Cancelar", self.destroy, primary=False).pack(side="right", padx=(0, 8))

    def _browse(self):
        d = filedialog.askdirectory(parent=self, initialdir=self.path.get())
        if d:
            p = Path(d)
            self.path.set(str(p if p.name.lower() == "re hub" else p / APP))

    def _progress(self, f):
        def draw():
            self.bar.delete("all")
            self.bar.create_rectangle(0, 0, self.bar.winfo_width() * f, 4, fill=RED, outline="")
        self.after(0, draw)

    def _start(self):
        self.go.config(state="disabled")
        self.status.config(text="Instalando...")
        dest = self.path.get()

        def work():
            try:
                install(dest, self._progress)
                self.after(0, lambda: self._done(dest))
            except Exception as e:  # mostra o erro em vez de fechar calado
                msg = str(e)
                self.after(0, lambda: (self.status.config(text="Erro: " + msg, fg="#e0857f"),
                                       self.go.config(state="normal")))
        threading.Thread(target=work, daemon=True).start()

    def _done(self, dest):
        self.status.config(text="Pronto. O RE Hub esta instalado.", fg=TEXT)
        if self.open_after.get():
            subprocess.Popen([str(Path(dest) / EXE)], cwd=dest)
            self.after(600, self.destroy)
        else:
            self.go.config(text="FECHAR", state="normal", command=self.destroy)

    def _uninstall_ui(self):
        b = self.body
        where = installed_at() or Path(sys.executable).parent
        self.where = where
        tk.Label(b, text=f"Remove o app de {where}, os atalhos e o registro em Adicionar ou remover programas.",
                 fg=TEXT, bg=BG, font=(FONT, 11), anchor="w", wraplength=490, justify="left").pack(fill="x")
        self.keep = tk.BooleanVar(value=True)
        tk.Checkbutton(b, text="Manter meus dados (configuracoes, jogos baixados, mods, musicas)",
                       variable=self.keep, bg=BG, fg=TEXT, selectcolor=PANEL, activebackground=BG,
                       activeforeground=TEXT, font=(FONT, 10), anchor="w").pack(fill="x", pady=(14, 0))
        self.status = tk.Label(b, text="", fg=MUTED, bg=BG, font=(FONT, 10), anchor="w")
        self.status.pack(fill="x", pady=(10, 0))
        bar = tk.Frame(b, bg=BG)
        bar.pack(fill="x", pady=(14, 0))
        self._button(bar, "Desinstalar", self._remove).pack(side="right")
        self._button(bar, "Cancelar", self.destroy, primary=False).pack(side="right", padx=(0, 8))

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
        self.status.config(text="RE Hub removido.", fg=TEXT)
        self.after(900, self.destroy)


if __name__ == "__main__":
    Window("--uninstall" in sys.argv).mainloop()
