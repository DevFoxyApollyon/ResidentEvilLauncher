"""Fichas de personagens (games/_personagens.json) e os retratos, baixados da wiki da franquia."""
import json
import subprocess
import urllib.parse
import urllib.request

from .franchise import FR
from .paths import COVERS, GAMES_DIR


def load():
    try:
        return json.loads((GAMES_DIR / "_personagens.json").read_text(encoding="utf-8")).get("personagens", [])
    except (OSError, ValueError):
        return []


def portrait_path(ch):
    p = COVERS / f"_pers_{ch['id']}.png"
    return p if p.exists() else None


def _api(params):
    url = FR["wiki_referer"].rstrip("/") + "/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": "RE-Hub/1.0 (launcher pessoal)"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _thumb(data):
    pages = (data.get("query") or {}).get("pages") or {}
    best = sorted(pages.values(), key=lambda p: p.get("index", 0))
    return next((p["thumbnail"]["source"] for p in best if p.get("thumbnail")), None)


def download_portrait(ch):
    """Imagem principal da página do personagem na wiki (pelo título; se não achar, pela busca)."""
    name = ch.get("busca") or ch["nome"]
    try:
        url = ch.get("retrato") or _thumb(_api({"action": "query", "titles": name, "redirects": 1, "prop": "pageimages", "pithumbsize": 600}))
        if not url:
            url = _thumb(_api({"action": "query", "generator": "search", "gsrsearch": name, "gsrlimit": 1,
                               "prop": "pageimages", "pithumbsize": 600}))
    except (OSError, ValueError):
        return False
    if not url:
        return False
    COVERS.mkdir(parents=True, exist_ok=True)
    out = COVERS / f"_pers_{ch['id']}.png"
    try:  # a Wiki recusa o Python nas imagens (403); o curl do Windows, com Referer, passa
        subprocess.run(["curl", "-sfL", "--max-time", "25", "-e", FR["wiki_referer"], "-o", str(out), url],
                       check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except (OSError, subprocess.CalledProcessError):
        out.unlink(missing_ok=True)
        return False
