"""O que a Steam e o Windows já guardam no PC sobre os seus jogos: horas jogadas, última vez que jogou,
prints (F12 da Steam), gravações (Xbox Game Bar, Radeon, NVIDIA) e quando o jogo foi atualizado."""
import re
from datetime import date
from pathlib import Path

from . import steam

STEAM_ID_BASE = 76561197960265728
IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
VIDEO_EXTS = {".mp4", ".mkv", ".mov", ".webm"}


def parse_vdf(text):
    """Lê um .vdf/.acf da Steam (texto com chaves e aspas) para dicionários."""
    root, stack, key = {}, [], None
    cur = root
    for s, brace in re.findall(r'"((?:[^"\\]|\\.)*)"|([{}])', text):
        if brace == "{":
            new = {}
            cur[key or ""] = new
            stack.append(cur)
            cur, key = new, None
        elif brace == "}":
            cur, key = (stack.pop() if stack else root), None
        elif key is None:
            key = s
        else:
            cur[key] = s.replace("\\\\", "\\")
            key = None
    return root


def _get(d, *path):
    """Caminho dentro do vdf sem ligar para maiúsculas ("apps" e "Apps" aparecem nos dois jeitos)."""
    for k in path:
        if not isinstance(d, dict):
            return {}
        d = next((v for kk, v in d.items() if kk.lower() == k.lower()), {})
    return d


def account_dir(steamid):
    root = steam.steam_path()
    if not root or not steamid:
        return None
    d = root / "userdata" / str(int(steamid) - STEAM_ID_BASE)
    return d if d.is_dir() else None


_play = {"file": None, "mtime": None, "data": {}}


def playtimes(steamid):
    """{appid: {"minutos": horas jogadas em minutos, "ultima": timestamp}} lidos do localconfig.vdf da conta.
    Só relê o arquivo quando a Steam o muda."""
    d = account_dir(steamid)
    f = d / "config" / "localconfig.vdf" if d else None
    if not f or not f.exists():
        return {}
    m = f.stat().st_mtime
    if _play["file"] != f or _play["mtime"] != m:
        try:
            vdf = parse_vdf(f.read_text(encoding="utf-8", errors="ignore"))
        except OSError:
            return _play["data"]
        out = {}
        for appid, info in _get(vdf, "UserLocalConfigStore", "Software", "Valve", "Steam", "apps").items():
            if appid.isdigit() and isinstance(info, dict):
                out[int(appid)] = {"minutos": int(info.get("Playtime") or 0), "ultima": int(info.get("LastPlayed") or 0)}
        _play.update(file=f, mtime=m, data=out)
    return _play["data"]


def manifest(appid):
    """Dados do appmanifest_<appid>.acf (nome, última atualização, build) do jogo instalado; {} se não estiver."""
    root = steam.steam_path()
    if not root:
        return {}
    for lib in steam.library_folders(root):
        f = lib / "steamapps" / f"appmanifest_{appid}.acf"
        if f.exists():
            try:
                st = _get(parse_vdf(f.read_text(encoding="utf-8", errors="ignore")), "AppState")
            except OSError:
                return {}
            return {"nome": st.get("name", ""), "atualizado": int(st.get("LastUpdated") or 0),
                    "build": st.get("buildid", ""), "jogado": int(st.get("LastPlayed") or 0),
                    "precisa_atualizar": bool(int(st.get("StateFlags") or 0) & 2)}
    return {}


# ---------- prints e gravações ----------
def steam_screens_dir(steamid, appid):
    """Pasta onde a Steam guarda as prints do jogo (F12)."""
    d = account_dir(steamid)
    return d / "760" / "remote" / str(appid) / "screenshots" if d else None


def _videos_dir():
    """Pasta Vídeos de verdade (pode ter sido movida para outro disco)."""
    import ctypes
    import uuid
    try:
        buf = ctypes.c_wchar_p()
        guid = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("18989B1D-99B5-455B-841C-AB7C74E4DDFC").bytes_le)
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(buf)) == 0:
            path = Path(buf.value)
            ctypes.windll.ole32.CoTaskMemFree(buf)
            return path
    except (OSError, AttributeError, ValueError):
        pass
    return Path.home() / "Videos"


def pictures_dir():
    """Pasta Imagens de verdade (onde a foto do card é salva)."""
    import ctypes
    import uuid
    try:
        buf = ctypes.c_wchar_p()
        guid = (ctypes.c_byte * 16).from_buffer_copy(uuid.UUID("33E28130-4E1E-4676-835A-98395C3BC3BB").bytes_le)
        if ctypes.windll.shell32.SHGetKnownFolderPath(ctypes.byref(guid), 0, None, ctypes.byref(buf)) == 0:
            path = Path(buf.value)
            ctypes.windll.ole32.CoTaskMemFree(buf)
            return path
    except (OSError, AttributeError, ValueError):
        pass
    return Path.home() / "Pictures"


def norm(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


# "RESIDENT EVIL 2 2026-10-15 18-00-00.png" (Game Bar) / "Resident Evil 2 10_15_2026 ..." (outros)
_STAMP = re.compile(r"^(.*?)[\s_]+(?:\d{4}[-_.]\d{1,2}[-_.]\d{1,2}|\d{1,2}[-_.]\d{1,2}[-_.]\d{4})")


def captures(names):
    """Gravações e capturas do Windows/placa de vídeo cujo título bate com um dos nomes do jogo.
    Game Bar: Vídeos/Captures/<título da janela> <data>.mp4|png. Radeon/NVIDIA: uma pasta com o nome do jogo."""
    wanted = {norm(n) for n in names if n and norm(n)}
    if not wanted:
        return []
    videos = _videos_dir()
    out = []
    gamebar = videos / "Captures"
    if gamebar.is_dir():
        for p in gamebar.iterdir():
            m = _STAMP.match(p.stem)
            if m and norm(m.group(1)) in wanted and p.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS:
                out.append(p)
    for vendor in ("Radeon ReLive", "NVIDIA", "AMD"):
        base = videos / vendor
        if not base.is_dir():
            continue
        for sub in base.iterdir():
            if sub.is_dir() and norm(sub.name) in wanted:
                out += [p for p in sub.rglob("*") if p.suffix.lower() in IMAGE_EXTS | VIDEO_EXTS]
    return out


def media_for(steamid, appid, names):
    """Prints e vídeos do jogo, mais novos primeiro: [{"path", "video", "quando"}]."""
    files = []
    d = steam_screens_dir(steamid, appid) if appid else None
    if d and d.is_dir():
        files += [p for p in d.iterdir() if p.suffix.lower() in IMAGE_EXTS]
    files += captures(names)
    out, seen = [], set()
    for p in files:
        if p in seen:
            continue
        seen.add(p)
        try:
            when = p.stat().st_mtime
        except OSError:
            continue
        out.append({"path": p, "video": p.suffix.lower() in VIDEO_EXTS, "quando": when})
    out.sort(key=lambda m: -m["quando"])
    return out


def ago(ts):
    """'hoje', 'ontem', 'há 3 dias', 'há 2 meses'..."""
    if not ts:
        return ""
    days = (date.today() - date.fromtimestamp(ts)).days  # pelo calendário: ontem à noite é "ontem"
    if days <= 0:
        return "hoje"
    if days == 1:
        return "ontem"
    if days < 30:
        return f"há {days} dias"
    if days < 365:
        m = days // 30
        return f"há {m} {'mês' if m == 1 else 'meses'}"
    y = days // 365
    return f"há {y} {'ano' if y == 1 else 'anos'}"


def hours(minutes):
    if not minutes:
        return ""
    if minutes < 60:
        return f"{minutes} min"
    h = minutes / 60
    return f"{h:.1f} h".replace(".", ",") if h < 10 else f"{round(h)} h"
