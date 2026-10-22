"""Gera o instalador do RE Hub: build/installer/RE Hub - Instalar.exe (um arquivo so).

    python tools/build_installer.py [--version 1.2.0]

1. gera o app (PyInstaller, como no LEIA-ME) em build/dist/RE Hub;
2. junta num zip o app, o catalogo (games/, franquia.json, modelos/) e as fontes livres
   (data/fontes, licenca OFL). Nao entra nada pessoal nem de terceiros: configuracoes, jogos
   baixados, mods, capas e trailers em cache, musicas e sons que voce colocou;
3. empacota installer/installer.py com esse zip num .exe so (PyInstaller --onefile).
"""
import argparse
import datetime
import os
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
APP = BUILD / "dist" / "RE Hub"
OUT = BUILD / "installer"
CATALOG = ["games", "modelos", "franquia.json", "re_hub.ico", "re_hub.png", "LEIA-ME.md"]
FREE_DATA = ["data/fontes"]


def pyinstaller(*args):
    subprocess.run([sys.executable, "-m", "PyInstaller", "--noconfirm", *args], cwd=ROOT, check=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--version", default=datetime.date.today().strftime("%Y.%m.%d"))
    ap.add_argument("--skip-app", action="store_true", help="usa o app ja gerado em build/dist")
    a = ap.parse_args()
    icon = str(ROOT / "re_hub.ico")
    if not a.skip_app:
        pyinstaller("--noconsole", "--onedir", "--contents-directory", "_internal", "--icon", icon,
                    "--name", "RE Hub", "--distpath", str(BUILD / "dist"), "--workpath", str(BUILD),
                    "--specpath", str(BUILD), str(ROOT / "main.py"))
    OUT.mkdir(parents=True, exist_ok=True)
    zpath = OUT / "payload.zip"
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        z.writestr("VERSION", a.version)
        for f in APP.rglob("*"):
            if f.is_file():
                z.write(f, f.relative_to(APP).as_posix())
        for name in CATALOG + FREE_DATA:
            p = ROOT / name
            for f in ([p] if p.is_file() else p.rglob("*")):
                if f.is_file() and "__pycache__" not in f.parts:
                    z.write(f, f.relative_to(ROOT).as_posix())
    print("payload", zpath, zpath.stat().st_size // (1 << 20), "MB")
    sep = ";" if os.name == "nt" else ":"
    pyinstaller("--noconsole", "--onefile", "--icon", icon, "--name", "RE Hub - Instalar",
                "--add-data", f"{zpath}{sep}.", "--add-data", f"{icon}{sep}.",
                "--distpath", str(OUT), "--workpath", str(OUT / "work"), "--specpath", str(OUT / "work"),
                str(ROOT / "installer" / "installer.py"))
    exe = OUT / "RE Hub - Instalar.exe"
    print(exe, exe.stat().st_size // (1 << 20), "MB")


if __name__ == "__main__":
    main()
