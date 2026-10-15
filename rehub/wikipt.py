"""Resident Evil Wiki em português (residentevil.fandom.com/pt-br): a fonte das informações do hub.

Daqui vêm a lista de personagens, vilões e armas biológicas (pelas categorias da wiki), os textos de cada ficha,
as imagens e versões, os vírus, os textos dos jogos (aba Wiki) e dos lugares do mapa. Tudo fica guardado em
data/cache/wiki_pt e só é buscado de novo depois de alguns dias.

A wiki em português não tem os documentos dos jogos (diários, relatórios): esses continuam vindo da wiki em inglês,
traduzidos (rehub/lore.py).
"""
import hashlib
import html
import json
import re
import time
import unicodedata
import urllib.parse
import urllib.request

from .franchise import FR
from .paths import DATA

CACHE = DATA / "cache" / "wiki_pt"
UA = {"User-Agent": "RE-Hub/1.0 (launcher pessoal)"}
BASE = FR.get("wiki_pt", "").rstrip("/")

# categorias que formam a lista de personagens, e o tipo de cada uma
PEOPLE_CATS = (("Personagens", "heroi"), ("Vilões", "vilao"), ("Armas Bio Orgânicas", "criatura"), ("Criaturas", "criatura"),
               ("Zumbis", "criatura"))
VIRUS_CATS = ("Vírus", "Parasitas")
SKIP = {"Arma Bio-Orgânica", "B.O.W.", "Ganados", "Parasita", "Locais", "Tyrant Series", "NE-α"}

# página da wiki de cada versão do catálogo (games/*.json) e dos filmes (capítulos)
GAME_PAGES = {"re0": "Resident Evil Zero", "re1": "Resident Evil Remake", "re1_decomp": "Resident Evil",
              "re2": "Resident Evil 2 (2019)", "re2_classic": "Resident Evil 2", "re3": "Resident Evil 3 (2020)",
              "re3_classic": "Resident Evil 3: Nemesis", "re4": "Resident Evil 4 (2023)", "re4_2005": "Resident Evil 4",
              "re5": "Resident Evil 5", "re6": "Resident Evil 6", "re7": "Resident Evil 7: Biohazard",
              "village": "Resident Evil:Village", "requiem": "Resident Evil Requiem", "cvx": "Resident Evil CODE: Veronica X",
              "veronica": "Resident Evil Veronica", "outbreak": "Resident Evil Outbreak", "survivor": "Resident Evil Survivor",
              "survivor2": "Resident Evil Survivor 2 CODE: Veronica", "gaiden": "Resident Evil Gaiden",
              "dead_aim": "Resident Evil:Dead Aim", "mercenaries3d": "Resident Evil Mercenaries 3D", "umbrella_corps": "Umbrella Corps"}
CHAPTER_PAGES = {"degeneration": "Resident Evil:Degeneration", "damnation": "Resident Evil:Condenação",
                 "vendetta": "Resident Evil:Vendetta", "infinite_darkness": "Resident Evil:Infinite Darkness",
                 "death_island": "Resident Evil:Death Island", "resident_evil_2002": "Resident Evil - O Hóspede Maldito",
                 "apocalypse": "Resident Evil 2 - Apocalipse", "extinction": "Resident Evil 3 - A Extinção",
                 "afterlife": "Resident Evil 4 - Recomeço", "retribution": "Resident Evil 5 - Retribuição",
                 "final_chapter": "Resident Evil 6 - O Capítulo Final", "executer": "BIOHAZARD 4D-EXECUTER",
                 "veronica": "Resident Evil CODE:Veronica"}
# nome do jogo nas categorias ("Personagens de ...") -> capítulo
CATEGORY_CHAPTERS = {
    "residentevil": "re1", "residentevilremake": "re1", "residentevil0": "re0", "residentevilzero": "re0",
    "residentevil15": "re1_5", "residentevil2": "re2", "residentevil2remake": "re2", "residentevil3": "re3",
    "residentevil3nemesis": "re3", "residentevil3remake": "re3", "residentevilcodeveronica": "veronica",
    "residentevilcodeveronicax": "veronica", "residentevil4": "re4", "residentevil4remake": "re4", "residentevil5": "re5",
    "residentevil6": "re6", "residentevil7": "re7", "residentevilvillage": "village", "residentevilrequiem": "requiem",
    "residentevilooutbreak": "outbreak", "residenteviloutbreak": "outbreak", "dooutbreak": "outbreak",
    "residentevilrevelations": "rev1", "residentevilrevelations2": "rev2", "residenteviltheumbrellachronicles": "umbrella_chronicles",
    "umbrellachronicles": "umbrella_chronicles", "residentevilthedarksidechronicles": "darkside_chronicles",
    "residentevilsurvivor": "survivor", "residentevilgaiden": "gaiden", "residentevilorc": "orc",
    "residentevilthemercenaries3d": "mercenaries3d", "residentevilresistance": "resistance",
    "residentevilsurvivalunit": "survival_unit", "residentevildegeneration": "degeneration",
    "residentevildamnation": "damnation", "residentevilvendetta": "vendetta", "residentevilinfinitedarkness": "infinite_darkness",
    "residentevildeathisland": "death_island", "residentevililhadamorte": "death_island", "residentevilveronica": "veronica",
    "residentevil7biohazard": "re7", "residentevildeadaim": "dead_aim", "residentevilavinganca": "vendetta",
    "residentevildegeneracao": "degeneration", "heavenlyisland": "heavenly_island", "residentevilreverse": "reverse",
    "marhawadesire": "marhawa", "residentevilsurvivor2codeveronica": "survivor2", "residentevilmercenaries3d": "mercenaries3d",
}


def available():
    return bool(BASE)


def _norm(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()  # "Degeneração" -> "Degeneracao"
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _norm_keep(s):
    """Sem acentos e em minúsculas, mas com espaços (para nomes de arquivo)."""
    return unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()


def _api(params, timeout=25):
    url = BASE + "/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout) as r:
        return json.load(r)


def _path(kind, key):
    return CACHE / kind / (hashlib.sha1(key.encode()).hexdigest()[:16] + ".json")


def _cached(p, max_age):
    try:
        if time.time() - p.stat().st_mtime < max_age:
            return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return None


def _save(p, data):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def _members(cat):
    out, cont = [], {}
    while True:
        d = _api({"action": "query", "list": "categorymembers", "cmtitle": "Categoria:" + cat, "cmlimit": 500,
                  "cmtype": "page", **cont})
        out += [m["title"] for m in d.get("query", {}).get("categorymembers", [])]
        if "continue" not in d:
            return out
        cont = {"cmcontinue": d["continue"]["cmcontinue"]}


def chapter_of_category(cat):
    cat = cat[len("Categoria:"):] if cat.startswith("Categoria:") else cat
    m = re.match(r"(?:Personagens|Perosnagens|Criaturas|Locais) d[eo]s? (.*)", cat)
    if not m:
        return None
    return CATEGORY_CHAPTERS.get(_norm(m.group(1)))


# ---------- índice: quem existe na wiki e em quais jogos aparece ----------
def index(max_age=7 * 86400):
    """{"pessoas": {título: {"tipo", "cats", "capitulos"}}, "virus": [títulos], "redirecionar": {nome: título}}."""
    p = CACHE / "indice.json"
    got = _cached(p, max_age)
    if got is not None:
        return got
    people, member = {}, {}
    for cat, _ in PEOPLE_CATS:
        for t in _members(cat):
            if t in SKIP or "/" in t or "(Anderson)" in t:
                continue
            member.setdefault(t, set()).add(cat)
    for t, cats in member.items():  # vilão > criatura > personagem; quem só é "zumbi" e também personagem é personagem
        if "Vilões" in cats:
            tipo = "vilao"
        elif cats & {"Armas Bio Orgânicas", "Criaturas"} or cats == {"Zumbis"}:
            tipo = "criatura"
        else:
            tipo = "heroi"
        people[t] = {"tipo": tipo}
    virus = [t for cat in VIRUS_CATS for t in _members(cat) if t not in SKIP]
    titles = list(people)
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        cont = {}
        while True:
            d = _api({"action": "query", "titles": "|".join(chunk), "prop": "categories", "cllimit": 500, **cont})
            for pg in d.get("query", {}).get("pages", {}).values():
                if pg.get("title") in people:
                    people[pg["title"]].setdefault("cats", []).extend(c["title"].split(":", 1)[-1] for c in pg.get("categories", []))
            if "continue" not in d:
                break
            cont = {k: v for k, v in d["continue"].items() if k != "continue"}
    for t, e in list(people.items()):
        cats = e.get("cats", [])
        if any("Anderson" in c or "Filmes" in c for c in cats) and not any(c.startswith(("Personagens de", "Criaturas de")) for c in cats):
            del people[t]  # personagens só dos filmes da Alice
            continue
        e["capitulos"] = sorted({c for c in map(chapter_of_category, cats) if c})
    result = {"pessoas": people, "virus": list(dict.fromkeys(virus)), "buscado_em": time.time()}
    _save(p, result)
    return result


def cached_index():
    """O índice guardado (mesmo que antigo), sem ir à internet; None se ainda não existe."""
    return _cached(CACHE / "indice.json", 10 ** 9)


def cached_names():
    return _cached(CACHE / "nomes.json", 10 ** 9) or {}


def prepare(names, force=False):
    """Em segundo plano: monta o índice e acha a página de cada nome da lista do hub. True se mudou algo."""
    before = (cached_index() or {}).get("buscado_em")
    idx = index(0 if force else 7 * 86400)
    resolve(names)
    return idx.get("buscado_em") != before or bool(set(names) - set(cached_names()))


def resolve(names):
    """{nome: título canônico na wiki pt-br} (segue redirecionamentos). Nomes que não existem ficam de fora."""
    p = CACHE / "nomes.json"
    known = _cached(p, 30 * 86400) or {}
    missing = [n for n in dict.fromkeys(names) if n and n not in known]
    for i in range(0, len(missing), 50):
        chunk = missing[i:i + 50]
        d = _api({"action": "query", "titles": "|".join(chunk), "redirects": 1})
        q = d.get("query", {})
        norm = {x["from"]: x["to"] for x in q.get("normalized", [])}
        red = {x["from"]: x["to"] for x in q.get("redirects", [])}
        exist = {pg["title"] for pg in q.get("pages", {}).values() if "missing" not in pg and "invalid" not in pg}
        for n in chunk:
            t = red.get(norm.get(n, n), norm.get(n, n))
            known[n] = t if t in exist else ""
    if missing:
        _save(p, known)
    return {n: known.get(n, "") for n in names if known.get(n)}


# ---------- textos ----------
def _plain(t):
    t = re.sub(r"<gallery.*?</gallery>", "", t, flags=re.S | re.I)
    t = re.sub(r"\[\[(?:File|Image|Arquivo|Imagem|Ficheiro|Categoria|Category):[^\]]*\]\]", "", t, flags=re.I)
    t = re.sub(r"\[\[[a-z]{2}(?:-[a-z]+)?:[^\]]*\]\]", "", t)  # links para a wiki em outras línguas
    for _ in range(4):
        t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"\{\|.*?\|\}", "", t, flags=re.S)  # tabelas
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"\[https?://\S+ ([^\]]*)\]", r"\1", t)
    t = re.sub(r"<ref[^>]*/>|<ref[^>]*>.*?</ref>", "", t, flags=re.S)
    t = re.sub(r"<br\s*/?>", "\n", t, flags=re.I)
    t = re.sub(r"<[^>]+>", "", t)
    t = re.sub(r"'''?", "", t)
    t = re.sub(r"^[:;*#]+\s?", "• ", t, flags=re.M)
    t = re.sub(r"__\w+__", "", t)
    t = html.unescape(t)
    t = re.sub(r"[ \t]+\n", "\n", t)
    return re.sub(r"\n{3,}", "\n\n", t).strip()


def _infobox_field(text, *names):
    for n in names:
        m = re.search(rf"\|\s*{n}\s*=\s*(.*?)(?=\|\s*[\w ]+\s*=|\}}\}})", text, re.S | re.I)
        if m:
            v = _plain(m.group(1)).replace("• ", "").strip()
            if v:
                return v.split("\n")[0].strip()
    return ""


def page(title, max_age=14 * 86400):
    """{"titulo", "intro", "secoes": [(nome, texto)], "papel", "link"} de uma página (cache de 14 dias)."""
    p = _path("paginas", title)
    got = _cached(p, max_age)
    if got is not None:
        return got
    d = _api({"action": "parse", "page": title, "prop": "wikitext", "redirects": 1})
    if "parse" not in d:
        result = {"titulo": title, "intro": "", "secoes": [], "papel": "", "link": ""}
        _save(p, result)
        return result
    real = d["parse"]["title"]
    text = d["parse"]["wikitext"]["*"]
    parts = re.split(r"^==\s*([^=].*?)\s*==\s*$", text, flags=re.M)
    lead = parts[0]
    lead = re.sub(r"\{\{\s*quote.*?\}\}", "", lead, flags=re.S | re.I)
    papel = _infobox_field(lead, "ocupação", "ocupacao", "afiliação", "tipo", "classificação")
    secoes = []
    for k in range(1, len(parts) - 1, 2):
        body = _plain(parts[k + 1])
        if body and parts[k].strip().lower() not in ("galeria", "referências", "notas", "curiosidades", "vídeos", "links externos"):
            secoes.append((_plain(parts[k]), body))
    intro = "\n".join(ln for ln in _plain(lead).split("\n") if not ln.startswith(("Se você está procurando", "Se você procura",
                                                                                   "Para outros usos")))
    result = {"titulo": real, "intro": intro.strip(), "secoes": secoes, "papel": papel,
              "link": BASE + "/wiki/" + urllib.parse.quote(real.replace(" ", "_"))}
    _save(p, result)
    return result


def game_page(chapter, game):
    """Página da wiki do jogo/filme selecionado (pela versão; se não houver, pelo capítulo)."""
    return GAME_PAGES.get(game["id"]) if game else None or CHAPTER_PAGES.get(chapter["id"])


# ---------- imagens ----------
def thumb(title, size=600):
    """Imagem principal da página."""
    d = _api({"action": "query", "titles": title, "redirects": 1, "prop": "pageimages", "pithumbsize": size})
    for pg in d.get("query", {}).get("pages", {}).values():
        if pg.get("thumbnail"):
            return pg["thumbnail"]["source"]
    return None


def gallery(title):
    """[(arquivo, rótulo)] da galeria do quadro de informações (image1 = <gallery> ...)."""
    d = _api({"action": "parse", "page": title, "prop": "wikitext", "section": 0, "redirects": 1})
    text = d.get("parse", {}).get("wikitext", {}).get("*", "")
    m = re.search(r"\|\s*image\d*\s*=\s*(.*?)(?=\n\s*\|[a-z_ ]+=|\}\})", text, re.S | re.I)
    if not m:
        return []
    body = m.group(1)
    items = re.findall(r"^\s*([^|\n<>]+?\.(?:png|jpe?g|webp|gif))\s*\|([^\n]*)$", body, re.M | re.I)
    if not items:
        one = re.findall(r"([^|\n<>=\[\]]+?\.(?:png|jpe?g|webp|gif))", body, re.I)
        items = [(one[0], "")] if one else []
    return [(re.sub(r"^(?:File|Image|Arquivo|Imagem):", "", f.strip(), flags=re.I).replace("_", " "), lab.strip())
            for f, lab in items]


def file_urls(files, width=600):
    out = {}
    for i in range(0, len(files), 40):
        chunk = files[i:i + 40]
        d = _api({"action": "query", "titles": "|".join("Arquivo:" + f for f in chunk), "prop": "imageinfo",
                  "iiprop": "url", "iiurlwidth": width})
        q = d.get("query", {})
        names = {n["to"]: n["from"] for n in q.get("normalized", [])}
        for pg in q.get("pages", {}).values():
            info = (pg.get("imageinfo") or [{}])[0]
            url = info.get("thumburl") or info.get("url")
            if url:
                out[names.get(pg["title"], pg["title"]).split(":", 1)[1].replace("_", " ")] = url
    return out
