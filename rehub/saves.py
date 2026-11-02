"""Backup dos saves de cada jogo em data/backups/saves/<jogo>/<data>.zip.

Onde ficam os saves:
- Steam: a pasta da conta para o jogo (userdata/<conta>/<appid>), onde a Steam guarda o save e a nuvem.
- Emulador baixado pelo hub: os cartões de memória / saves dele (valem para todos os jogos do emulador).
- Port de PC: o campo "saves" do catálogo (lista de caminhos; {jogo} = pasta do jogo, %APPDATA% e ~ funcionam)
  ou, sem ele, as pastas e arquivos com "save" no nome dentro da pasta do jogo.
Cada .zip leva um manifesto com o caminho original de cada pasta, para restaurar no mesmo lugar.
"""
import glob
import json
import os
import re
import time
import zipfile
from pathlib import Path

from . import emulators, launcher, library
from .paths import DATA

ROOT = DATA / "backups" / "saves"
KEEP = 15                 # backups guardados por jogo (os mais velhos saem)
MAX_BYTES = 1 << 30       # pastas maiores que 1 GB não entram (provavelmente não são só saves)


def documents():
    """Documentos do Windows (pode estar no OneDrive)."""
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as k:
            return Path(os.path.expandvars(winreg.QueryValueEx(k, "Personal")[0]))
    except OSError:
        return Path.home() / "Documents"


def _emulator_paths(game, cfg):
    key = game.get("emulador")
    exe = emulators.find(key) if key else None
    emu = exe.parent if exe else None
    portable = bool(emu and any((emu / n).exists() for n in ("portable.txt", "portable.ini")))
    docs, appdata = documents(), Path(os.environ.get("APPDATA", ""))
    if key == "pcsx2":
        return [emu / "memcards"] if portable else [docs / "PCSX2" / "memcards"]
    if key == "duckstation":
        return [emu / "memcards"] if portable else [docs / "DuckStation" / "memcards"]
    if key == "dolphin":
        base = emu / "User" if portable else docs / "Dolphin Emulator"
        return [base / "GC", base / "Wii" / "title"]
    if key == "azahar":
        return [emu / "user" / "sdmc"] if emu and (emu / "user").is_dir() else [appdata / "Azahar" / "sdmc"]
    if key == "mgba":   # o save fica ao lado da ROM, com o mesmo nome
        rom = cfg.get(game["id"]).get("iso")
        return [Path(rom).with_suffix(".sav")] if rom else []
    return []


def _expand(pattern, gdir):
    text = os.path.expanduser(os.path.expandvars(pattern.replace("{jogo}", str(gdir or ""))))
    if "{jogo}" in pattern and not gdir:
        return []
    if any(ch in text for ch in "*?["):
        return [Path(p) for p in sorted(glob.glob(text))]
    return [Path(text)]


def locations(game, cfg, installed, steamid):
    """Pastas/arquivos de save do jogo que existem neste PC."""
    if game.get("tipo") == "steam":
        acc = library.account_dir(steamid)
        paths = [acc / str(game["appid"])] if acc else []
    elif game.get("emulador"):
        paths = _emulator_paths(game, cfg)
    else:
        gdir = launcher.game_dir(game, cfg, installed)
        if game.get("saves"):
            paths = [p for pat in game["saves"] for p in _expand(pat, gdir)]
        elif gdir and gdir.is_dir():   # sem caminho no catálogo: o que tiver "save" no nome, até 2 níveis
            paths = [p for p in list(gdir.glob("*")) + list(gdir.glob("*/*")) if re.search(r"save", p.name, re.I)]
            paths = [p for p in paths if not any(q in p.parents for q in paths)]
        else:
            paths = []
    return [p for p in paths if p.exists()]


def _walk(p):
    if p.is_file():
        yield p, p.name
        return
    for f in sorted(p.rglob("*")):
        if f.is_file():
            yield f, f.relative_to(p).as_posix()


def folder(game_id):
    return ROOT / game_id


def backup(game_id, paths, reason=""):
    """Zipa os saves. Devolve o caminho do .zip (None se não há nada para guardar)."""
    paths = [Path(p) for p in paths if Path(p).exists()]
    files = [(k, f, rel) for k, p in enumerate(paths) for f, rel in _walk(p)]
    if not files:
        return None
    total = sum(f.stat().st_size for _k, f, _r in files)
    if total > MAX_BYTES:
        raise RuntimeError(f"Os saves somam {total / (1 << 30):.1f} GB: grande demais para o backup automático.")
    out = folder(game_id)
    out.mkdir(parents=True, exist_ok=True)
    tag = re.sub(r"[^\w-]+", "_", reason).strip("_")
    path = out / (time.strftime("%Y-%m-%d_%H-%M-%S") + (f"_{tag}" if tag else "") + ".zip")
    manifest = {"jogo": game_id, "quando": int(time.time()), "motivo": reason,
                "pastas": [{"origem": str(p), "arquivo": p.is_file()} for p in paths]}
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifesto.json", json.dumps(manifest, ensure_ascii=False, indent=2))
        for k, f, rel in files:
            z.write(f, f"{k}/{rel}")
    prune(game_id)
    return path


def prune(game_id, keep=KEEP):
    for old in backups(game_id)[keep:]:
        old.unlink(missing_ok=True)


def backups(game_id):
    """Backups do jogo, do mais novo para o mais velho."""
    d = folder(game_id)
    return sorted(d.glob("*.zip"), key=lambda p: p.name, reverse=True) if d.is_dir() else []


def describe(path):
    """'25/10/2026 14:03 · antes de instalar mod' para mostrar na lista."""
    try:
        with zipfile.ZipFile(path) as z:
            m = json.loads(z.read("manifesto.json"))
    except (OSError, KeyError, ValueError, zipfile.BadZipFile):
        return path.stem
    when = time.strftime("%d/%m/%Y %H:%M", time.localtime(m.get("quando", 0)))
    return when + (f"  ·  {m['motivo']}" if m.get("motivo") else "")


def restore(path):
    """Devolve os saves do .zip para os lugares de origem (por cima do que estiver lá). Devolve quantos arquivos."""
    count = 0
    with zipfile.ZipFile(path) as z:
        m = json.loads(z.read("manifesto.json"))
        targets = m["pastas"]
        for name in z.namelist():
            if name == "manifesto.json" or name.endswith("/"):
                continue
            k, _, rel = name.partition("/")
            t = targets[int(k)]
            base = Path(t["origem"])
            dest = base if t.get("arquivo") else base / rel
            root = base.parent if t.get("arquivo") else base
            if not dest.resolve().is_relative_to(root.resolve()):
                raise RuntimeError(f"Caminho suspeito no backup: {name}")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with z.open(name) as src, open(dest, "wb") as out:
                out.write(src.read())
            count += 1
    return count
