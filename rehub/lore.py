"""Conteúdo extra das telas: mapa, vírus, relações (games/_*.json), arquivos dos jogos (lidos da wiki da franquia)
e recordes de speedrun (speedrun.com). Tudo guardado em data/cache para abrir sem internet depois."""
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request

from .franchise import FR
from .paths import DATA, GAMES_DIR

CACHE = DATA / "cache"
UA = {"User-Agent": "RE-Hub/1.0 (launcher pessoal)"}

# arquivos (documentos, diários) de cada capítulo: categorias da wiki, com o rótulo de cada versão
FILE_CATEGORIES = {
    # Resident Evil
    "re0": [("Resident Evil 0", "Resident Evil 0 files")],
    "re1": [("Resident Evil", "Resident Evil files")],
    "outbreak": [("Outbreak", "Resident Evil Outbreak files"), ("Outbreak File #2", "Outbreak 2 files")],
    "re3": [("Resident Evil 3 (1999)", "Resident Evil 3: Nemesis files"), ("Resident Evil 3 (Remake)", "Resident Evil 3 remake files")],
    "re2": [("Resident Evil 2 (1998)", "Resident Evil 2 files"), ("Resident Evil 2 (Remake)", "Resident Evil 2 remake files")],
    "veronica": [("Code: Veronica", "Resident Evil CODE:Veronica files")],
    "darkside_chronicles": [("Darkside Chronicles", "Resident Evil: The Darkside Chronicles files")],
    "umbrella_chronicles": [("Umbrella Chronicles", "Resident Evil: The Umbrella Chronicles files")],
    "re4": [("Resident Evil 4 (2005)", "Resident Evil 4 files"), ("Resident Evil 4 (Remake)", "Resident Evil 4 remake files")],
    "rev1": [("Revelations", "Resident Evil: Revelations files")],
    "re5": [("Resident Evil 5", "Resident Evil 5 files")],
    "rev2": [("Revelations 2", "Resident Evil: Revelations 2 files")],
    "re6": [("Resident Evil 6", "Resident Evil 6 files")],
    "re7": [("Resident Evil 7", "Resident Evil 7: Biohazard files")],
    "village": [("Village", "Resident Evil Village files")],
    "requiem": [("Requiem", "Resident Evil Requiem files")],
    "survivor": [("Survivor", "Resident Evil Survivor files")],
    "survivor2": [("Survivor 2", "Resident Evil Survivor 2 CODE:Veronica files")],
    "gaiden": [("Gaiden", "Resident Evil Gaiden files")],
    "dead_aim": [("Dead Aim", "Resident Evil: Dead Aim files")],
    "survival_unit": [("Survival Unit", "Resident Evil Survival Unit files")],
    "degeneration": [("Degeneration", "Resident Evil: Degeneration files")],
    # Silent Hill
    "origins": [("Origins", "Silent Hill: Origins Memos")],
    "sh1": [("Silent Hill", "Silent Hill Memos")],
    "sh2": [("Silent Hill 2 (2001)", "Silent Hill 2 Memos"), ("Silent Hill 2 (2024)", "Silent Hill 2 (2024 video game) Memos")],
    "sh3": [("Silent Hill 3", "Silent Hill 3 Memos")],
    "sh4": [("Silent Hill 4", "Silent Hill 4: The Room Memos")],
    "homecoming": [("Homecoming", "Silent Hill: Homecoming Memos")],
    "downpour": [("Downpour", "Silent Hill: Downpour Memos")],
    "short_message": [("The Short Message", "Silent Hill: The Short Message Memos")],
    "f": [("Silent Hill f", "Silent Hill ƒ Memos")],
    "shattered": [("Shattered Memories", "Silent Hill: Shattered Memories Memos")],
    "book_of_memories": [("Book of Memories", "Silent Hill: Book of Memories Memos")],
}


def load(name):
    """games/_<name>.json, ou {} se não existir (a tela correspondente some)."""
    try:
        return json.loads((GAMES_DIR / f"_{name}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _get_json(url, timeout=20):
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def _cached(path, max_age):
    try:
        if time.time() - path.stat().st_mtime < max_age:
            return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return None


def _save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _wiki(params):
    url = FR["wiki_referer"].rstrip("/") + "/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    return _get_json(url)


# ---------- arquivos dos jogos ----------
def file_groups(chapter_id):
    """[(rótulo da versão, [títulos dos arquivos])] do capítulo (cache de 7 dias)."""
    out = []
    for label, cat in FILE_CATEGORIES.get(chapter_id, []):
        p = CACHE / "arquivos" / (hashlib.sha1(cat.encode()).hexdigest()[:16] + ".json")
        titles = _cached(p, 7 * 86400)
        if titles is None:
            titles, cont = [], {}
            while True:
                d = _wiki({"action": "query", "list": "categorymembers", "cmtitle": "Category:" + cat, "cmlimit": 500,
                           "cmtype": "page", **cont})
                titles += [m["title"] for m in d.get("query", {}).get("categorymembers", [])
                           if not m["title"].startswith(("Template:", "Category:"))]
                if "continue" not in d:
                    break
                cont = {"cmcontinue": d["continue"]["cmcontinue"]}
            titles.sort(key=str.lower)
            _save(p, titles)
        if titles:
            out.append((label, titles))
    return out


def has_files(chapter_id):
    return chapter_id in FILE_CATEGORIES


def _plain(wikitext):
    """Wikitexto -> texto corrido para ler (sem links, modelos, tags nem imagens)."""
    t = wikitext
    t = re.sub(r"<tabber>\s*", "", t)
    t = re.split(r"\n\|-\|", t)[0]  # abas da wiki: fica com a primeira (a tradução oficial)
    t = re.sub(r"^[^=\n<]{1,40}=(?=<poem>|\s*\n)", "", t, flags=re.M)  # rótulo da aba ("Official localisation=")
    t = re.sub(r"\[\[(?:File|Image|Arquivo):[^\]]*\]\]", "", t, flags=re.I)
    for _ in range(3):
        t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+ ([^\]]*)\]", r"\1", t)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"'''?", "", t)
    t = re.sub(r"^[:;*#]+\s?", "", t, flags=re.M)
    t = re.sub(r"^=+\s*(.*?)\s*=+\s*$", r"\n\1\n", t, flags=re.M)
    t = html.unescape(t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def read_file(title):
    """Texto do documento: a seção Transcript da página (se não houver, o começo da página). Cache de 30 dias."""
    p = CACHE / "arquivos" / "textos" / (hashlib.sha1(title.encode()).hexdigest()[:16] + ".json")
    got = _cached(p, 30 * 86400)
    if got:
        return got
    d = _wiki({"action": "parse", "page": title, "prop": "wikitext", "redirects": 1})
    text = d.get("parse", {}).get("wikitext", {}).get("*", "")
    m = re.search(r"^==\s*(?:Transcript|Transcription|Contents?|Text)\s*==\s*$(.*?)(?=^==[^=]|\Z)", text, re.M | re.S | re.I)
    body = m.group(1) if m else text
    result = {"titulo": title, "texto": _plain(body) or "(A wiki não tem o texto deste arquivo.)",
              "link": FR["wiki_referer"].rstrip("/") + "/wiki/" + urllib.parse.quote(title.replace(" ", "_"))}
    _save(p, result)
    return result


def translate(text, target="pt"):
    """Tradução automática (Google Tradutor, sem chave), em pedaços de até ~1800 caracteres sem quebrar parágrafos.
    Nomes próprios da série ficam protegidos ("Resident Evil" não vira "Residente Mal")."""
    names = sorted({FR["nome"], FR["prefixo_titulo"], "Umbrella", "S.T.A.R.S.", "Silent Hill", "Resident Evil"} - {""},
                   key=len, reverse=True)
    for k, n in enumerate(names):
        text = text.replace(n, f"QZX{k}Q")
    chunks, cur = [], ""
    for para in text.split("\n"):
        if cur and len(cur) + len(para) > 1800:
            chunks.append(cur)
            cur = ""
        cur += para + "\n"
    if cur:
        chunks.append(cur)
    out = []
    for chunk in chunks:
        data = urllib.parse.urlencode({"client": "gtx", "sl": "auto", "tl": target, "dt": "t", "q": chunk}).encode()
        req = urllib.request.Request("https://translate.googleapis.com/translate_a/single", data=data, headers=UA)
        with urllib.request.urlopen(req, timeout=20) as r:
            parts = json.load(r)[0]
        out.append("".join(p[0] for p in parts if p and p[0]))
    result = "".join(out).strip()
    for k, n in enumerate(names):
        result = re.sub(rf"QZX\s*{k}\s*Q(?=[^\W_])", n + " ", result, flags=re.I)  # o tradutor come o espaço antes do número
        result = re.sub(rf"QZX\s*{k}\s*Q", n, result, flags=re.I)
    return result


def read_file_pt(title):
    """O documento traduzido para o português (guardado junto com o original)."""
    doc = read_file(title)
    if doc.get("texto_pt"):
        return doc
    doc["texto_pt"] = translate(doc["texto"])
    _save(CACHE / "arquivos" / "textos" / (hashlib.sha1(title.encode()).hexdigest()[:16] + ".json"), doc)
    return doc


# ---------- speedrun ----------
def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


# abreviação no speedrun.com de cada versão do catálogo (onde a busca pelo nome erraria)
SPEEDRUN = {"re0": "re0", "re1": "remake_hd", "re1_decomp": "residentevil", "re1_classic": "residentevil",
            "re2": "re2remake", "re2_classic": "re2",
            "re3": "re3r", "re3_classic": "re3", "re4": "re4r", "re4_2005": "re4steam", "re5": "re5steam", "re6": "re6",
            "re7": "re7", "village": "re8", "requiem": "RE9", "rev1": "rerev", "rev2": "rev2", "outbreak": "reobf1",
            "outbreak2": "reobf2"}


def speedrun(game):
    """Melhores tempos de cada categoria no speedrun.com: {"jogo", "link", "recordes": [...]}. Cache de 1 dia.
    O nome é procurado no site; "speedrun": "<abreviação>" no .json do jogo escolhe à mão."""
    p = CACHE / "speedrun" / f"{game['id']}.json"
    got = _cached(p, 86400)
    if got is not None:
        return got
    base = "https://www.speedrun.com/api/v1/"
    abbr = game.get("speedrun") or (SPEEDRUN.get(game["id"]) if FR["id"] == "resident_evil" else None)
    if abbr:
        g = _get_json(base + "games/" + urllib.parse.quote(abbr))["data"]
    else:
        name = re.sub(r"\s+[—-]\s.*$", "", game["nome"])
        name = re.sub(r"\s*\((?!remake)[^)]*\)", "", name, flags=re.I).strip()
        remake = "remake" in name.lower()
        query = re.sub(r"\(remake\)", "", name, flags=re.I).strip()
        found = _get_json(base + "games?max=20&name=" + urllib.parse.quote(query))["data"]
        if not found:
            result = {"jogo": None, "recordes": []}
            _save(p, result)
            return result
        want = _norm(query)

        def score(x):
            n = _norm(x["names"]["international"])
            s = 0 if n == want else 1 if n.startswith(want) else 2
            if remake:  # o remake costuma ser o mesmo nome com o ano
                s = 0 if n.startswith(want) and re.search(r"\(20\d\d\)", x["names"]["international"]) else s + 1
            return s, len(n)
        g = sorted(found, key=score)[0]
    recs = _get_json(base + f"games/{g['id']}/records?top=1&scope=full-game&skip-empty=true&embed=players,category&max=40")
    out = []
    for c in recs.get("data", []):
        if not c.get("runs"):
            continue
        run = c["runs"][0]["run"]
        players = c.get("players", {}).get("data", [])
        who = ", ".join((pl.get("names") or {}).get("international") or pl.get("name", "?") for pl in players) or "?"
        out.append({"categoria": c["category"]["data"]["name"], "tempo": run["times"]["primary_t"], "jogador": who,
                    "data": run.get("date") or "", "link": run.get("weblink", "")})
    result = {"jogo": g["names"]["international"], "link": g.get("weblink", ""), "recordes": out}
    _save(p, result)
    return result


def fmt_time(seconds):
    s = float(seconds)
    h, rest = divmod(int(s), 3600)
    m, sec = divmod(rest, 60)
    ms = int(round((s - int(s)) * 1000))
    txt = f"{h}:{m:02d}:{sec:02d}" if h else f"{m}:{sec:02d}"
    return txt + (f".{ms:03d}" if ms else "")


# ---------- mapa do mundo ----------
MAP_URL = "https://upload.wikimedia.org/wikipedia/commons/thumb/5/51/BlankMap-Equirectangular.svg/1920px-BlankMap-Equirectangular.svg.png"


def world_map():
    """Mapa-múndi em branco (Wikimedia Commons, domínio público), baixado uma vez. Caminho do png ou None."""
    p = CACHE / "mapa_mundo.png"
    if p.exists():
        return p
    try:
        with urllib.request.urlopen(urllib.request.Request(MAP_URL, headers=UA), timeout=30) as r:
            data = r.read()
        if not data.startswith(b"\x89PNG"):
            return None
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return p
    except OSError:
        return None
