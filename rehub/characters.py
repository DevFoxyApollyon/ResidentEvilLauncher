"""Fichas de personagens (games/_personagens.json) e os retratos, baixados da wiki da franquia.

Além do retrato principal, cada personagem tem as suas versões (uma imagem por jogo/filme): vêm da galeria do
quadro de informações da página dele na wiki (e da página "/remake", na wiki de RE) ou de "versoes" na ficha.
"""
import json
import re
import subprocess
import urllib.parse
import urllib.request

from .franchise import FR
from .paths import COVERS, GAMES_DIR

VERSIONS = COVERS / "_versoes"
CACHE_VERSION = 2

# rótulos da wiki -> (nome em português, ano) para ordenar do mais antigo ao mais novo
LABELS = {
    "RE1 (1996)": ("Resident Evil (1996)", 1996), "RE (1996)": ("Resident Evil (1996)", 1996),
    "RE2 (1998)": ("Resident Evil 2 (1998)", 1998), "RE3 (1999)": ("Resident Evil 3 (1999)", 1999),
    "RE3": ("Resident Evil 3 (1999)", 1999), "CV": ("Code: Veronica", 2000), "CVX": ("Code: Veronica X", 2001),
    "RE0": ("Resident Evil 0", 2002), "RE1 (2002)": ("REmake (2002)", 2002), "RE (2002)": ("REmake (2002)", 2002),
    "OB": ("Outbreak", 2003), "RE4 (2005)": ("Resident Evil 4 (2005)", 2005), "UC": ("Umbrella Chronicles", 2007),
    "DEG": ("Degeneration", 2008), "DEGE": ("Degeneration", 2008), "RE5": ("Resident Evil 5", 2009),
    "DC": ("Darkside Chronicles", 2009), "LIN": ("RE5: Lost in Nightmares", 2010), "MERC3D": ("Mercenaries 3D", 2011),
    "REV": ("Revelations", 2012), "RE6": ("Resident Evil 6", 2012), "DAM": ("Damnation", 2012),
    "ORC": ("Operation Raccoon City", 2012), "REV2": ("Revelations 2", 2015), "VEN": ("Vendetta", 2017),
    "RE7": ("Resident Evil 7", 2017), "2R": ("Resident Evil 2 (Remake)", 2019), "RE2 (2019)": ("Resident Evil 2 (Remake)", 2019),
    "RE:2": ("Resident Evil 2 (Remake)", 2019), "RE3 (2020)": ("Resident Evil 3 (Remake)", 2020),
    "RESISTANCE": ("Resistance", 2020), "ID": ("Infinite Darkness", 2021), "ID-TB": ("Infinite Darkness (extra)", 2021),
    "VIL": ("Village", 2021), "4R": ("Resident Evil 4 (Remake)", 2023), "RE4 (2023)": ("Resident Evil 4 (Remake)", 2023),
    "RE:4": ("Resident Evil 4 (Remake)", 2023), "DI": ("Death Island", 2023), "HI": ("Heavenly Island", 2015),
    "REQ": ("Requiem", 2026), "STAGE": ("Biohazard: The Stage", 2016), "PACHISLOT": ("Pachislot", 2000),
    "PACHI-SLOT": ("Pachislot", 2000), "HUMAN": ("Humano", None), "MUTATED": ("Mutado", None),
    "SWAMP MAN": ("Homem do pântano", None), "TEEN": ("Adolescente", None), "BABY": ("Bebê", None),
    "ADULT": ("Adulto", None),
}
# na página "/remake" os rótulos curtos querem dizer o remake
REMAKE_LABELS = {"RE2": "2R", "RE4": "4R", "RE3": "RE3 (2020)"}
LABELS["RE:V"] = ("Re:Verse", 2022)
REMAKES = {"2": ("Resident Evil 2 (Remake)", 2019), "3": ("Resident Evil 3 (Remake)", 2020),
           "4": ("Resident Evil 4 (Remake)", 2023)}


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


def _curl(url, out):
    """A Wiki recusa o Python nas imagens (403); o curl do Windows, com Referer, passa."""
    try:
        subprocess.run(["curl", "-sfL", "--max-time", "25", "-e", FR["wiki_referer"], "-o", str(out), url],
                       check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        return True
    except (OSError, subprocess.CalledProcessError):
        out.unlink(missing_ok=True)
        return False


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
    return _curl(url, COVERS / f"_pers_{ch['id']}.png")


# ---------- versões (uma imagem por jogo) ----------
def _gallery(page):
    """(título da página, [(arquivo, rótulo)], texto) do campo image do quadro de informações."""
    try:
        d = _api({"action": "parse", "page": page, "prop": "wikitext", "section": 0, "redirects": 1})
    except (OSError, ValueError):
        return None, [], ""
    if "parse" not in d:
        return None, [], ""
    text = d["parse"]["wikitext"]["*"]
    m = re.search(r"\|\s*image\s*=\s*(.*?)\n\s*\|", text, re.S | re.I)
    if not m:
        return d["parse"]["title"], [], text
    body = m.group(1)
    items = re.findall(r"^\s*([^|\n<>]+?\.(?:png|jpe?g|webp|gif))\s*\|([^\n]*)$", body, re.M | re.I)
    if not items:  # uma imagem só, sem galeria
        one = re.findall(r"([^|\n<>=\[\]]+?\.(?:png|jpe?g|webp|gif))", body, re.I)
        items = [(one[0].strip(), "")] if one else []
    clean = [(re.sub(r"^(?:File|Image|Arquivo):", "", f.strip(), flags=re.I).strip(), lab.strip().strip('"'))
             for f, lab in items]
    return d["parse"]["title"], clean, text


def _label(raw, remake=None):
    """Rótulo da wiki -> (nome, ano). remake: (nome, ano) do jogo da página "/remake" (None na página principal).
    Siglas que não conhecemos (ex.: "MD-2012") voltam None e a imagem fica de fora."""
    raw = raw.strip()
    key = raw.upper()
    if remake:
        key = REMAKE_LABELS.get(key, key)
        if key in LABELS:
            return LABELS[key]
        return (f"{remake[0]} · {raw}" if raw else remake[0]), remake[1]
    if key in LABELS:
        return LABELS[key]
    if not raw:
        return "Original", None
    if re.fullmatch(r"[A-Z0-9:\-]+", raw):
        return None
    return raw, None


def _urls(files):
    """{arquivo: link da imagem em até 600 px de largura}."""
    out = {}
    for i in range(0, len(files), 40):
        chunk = files[i:i + 40]
        d = _api({"action": "query", "titles": "|".join("File:" + f for f in chunk), "prop": "imageinfo",
                  "iiprop": "url", "iiurlwidth": 600})
        q = d.get("query") or {}
        names = {n["to"]: n["from"] for n in q.get("normalized", [])}
        for p in (q.get("pages") or {}).values():
            info = (p.get("imageinfo") or [{}])[0]
            url = info.get("thumburl") or info.get("url")
            if url:
                title = names.get(p["title"], p["title"])
                out[title.split(":", 1)[1]] = url
    return out


def versions(ch):
    """Versões já baixadas: [{"rotulo", "ano", "arquivo"}] (do mais antigo ao mais novo), ou None se ainda não buscou."""
    try:
        data = json.loads((VERSIONS / f"{ch['id']}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if data.get("v") != CACHE_VERSION:
        return None
    return [v for v in data["versoes"] if (VERSIONS / v["arquivo"]).exists()]


def version_path(v):
    return VERSIONS / v["arquivo"]


def download_versions(ch):
    """Busca na wiki uma imagem por jogo/filme do personagem e guarda em data/covers/_versoes."""
    entries = []  # (arquivo da wiki, rótulo, ano)
    for v in ch.get("versoes", []):  # versões escritas à mão na ficha
        entries.append((v["arquivo"], v["rotulo"], v.get("ano")))
    if not entries:
        title, items, _ = _gallery(ch.get("busca") or ch["nome"])
        for f, lab in reversed(items):  # a wiki lista do mais novo para o mais antigo
            got = _label(lab)
            if got:
                entries.append((f, *got))
        if title and FR["id"] == "resident_evil":  # só a wiki de RE separa os remakes em "/remake"
            _, more, text = _gallery(title + "/remake")
            m = re.search(r"Resident Evil ([234])\W{0,12}(?:<small>)?\s*\((?:2019|2020|2023)", text)
            remake = REMAKES.get(m.group(1)) if m else ("Remake", None)
            for f, lab in more:
                got = _label(lab, remake=remake)
                if got:
                    entries.append((f, *got))
    if not entries:
        return False
    # ano desconhecido: o do vizinho anterior (mantém a ordem da wiki)
    last, fixed = 0, []
    for f, lab, year in entries:
        last = year if year else last
        fixed.append((f, lab, year or last))
    fixed.sort(key=lambda e: e[2])
    try:
        urls = _urls([f for f, _, _ in fixed])
    except (OSError, ValueError):
        return False
    VERSIONS.mkdir(parents=True, exist_ok=True)
    out, seen = [], set()
    for k, (f, lab, year) in enumerate(fixed):
        url = urls.get(f) or urls.get(f.replace("_", " "))
        if not url or f in seen:
            continue
        seen.add(f)
        name = f"{ch['id']}_{k:02d}{'.png' if f.lower().endswith('.png') else '.jpg'}"
        if (VERSIONS / name).exists() or _curl(url, VERSIONS / name):
            out.append({"rotulo": lab, "ano": year or None, "arquivo": name})
    (VERSIONS / f"{ch['id']}.json").write_text(json.dumps({"v": CACHE_VERSION, "versoes": out}, ensure_ascii=False),
                                               encoding="utf-8")
    return bool(out)
