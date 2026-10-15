"""Detecta a Steam e os jogos instalados lendo os arquivos .vdf/.acf."""
import os
import re
import winreg
from pathlib import Path


def steam_path():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Valve\Steam") as k:
            return Path(winreg.QueryValueEx(k, "SteamPath")[0])
    except OSError:
        default = Path(r"C:\Program Files (x86)\Steam")
        return default if default.exists() else None


def library_folders(root):
    """Todas as bibliotecas Steam (pode haver uma em cada disco)."""
    folders = [root]
    vdf = root / "steamapps" / "libraryfolders.vdf"
    if vdf.exists():
        text = vdf.read_text(encoding="utf-8", errors="ignore")
        for p in re.findall(r'"path"\s+"([^"]+)"', text):
            p = Path(p.replace("\\\\", "\\"))
            if p not in folders:
                folders.append(p)
    return folders


def installed_apps():
    """{appid: pasta_do_jogo} de tudo que está instalado."""
    root = steam_path()
    if not root:
        return {}
    apps = {}
    for lib in library_folders(root):
        for acf in (lib / "steamapps").glob("appmanifest_*.acf"):
            text = acf.read_text(encoding="utf-8", errors="ignore")
            appid = re.search(r'"appid"\s+"(\d+)"', text)
            folder = re.search(r'"installdir"\s+"([^"]+)"', text)
            if appid:
                apps[int(appid.group(1))] = lib / "steamapps" / "common" / (folder.group(1) if folder else "")
    return apps


def run(appid):
    os.startfile(f"steam://rungameid/{appid}")


def install(appid):
    os.startfile(f"steam://install/{appid}")


def uninstall(appid):
    """Abre a confirmação de desinstalar da própria Steam."""
    os.startfile(f"steam://uninstall/{appid}")


def store(appid):
    os.startfile(f"steam://store/{appid}")
