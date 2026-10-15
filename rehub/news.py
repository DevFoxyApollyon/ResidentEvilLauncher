"""Aba Notícias: as últimas notícias da franquia pelo feed RSS de um site de fãs (no RE, o REVIL).

Guarda em data/noticias.json e busca de novo a cada 30 minutos (o site atualiza de hora em hora).
"""
import hashlib
import html
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime

from .franchise import FR
from .paths import DATA

FEED = FR["noticias"]["feed"]
SOURCE, SITE = FR["noticias"].get("fonte", ""), FR["noticias"].get("site", "")
CACHE = DATA / "noticias.json"
MAX_AGE = 30 * 60
NS = {"content": "http://purl.org/rss/1.0/modules/content/", "dc": "http://purl.org/dc/elements/1.1/"}
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _text(fragment):
    t = re.sub(r"<p>O post .*?</p>", "", fragment or "", flags=re.S)  # rodapé automático do WordPress
    t = html.unescape(re.sub(r"<[^>]+>", " ", t))
    return re.sub(r"\s+", " ", t).replace("[…]", "…").strip()


def _parse(xml_bytes):
    items = []
    for it in ET.fromstring(xml_bytes).iter("item"):
        content = it.findtext("content:encoded", "", NS)
        img = re.search(r'<img[^>]+src="([^"]+)"', content)
        guid = re.search(r"[?&]p=(\d+)", it.findtext("guid", ""))  # WordPress (REVIL); outros feeds: hash do link
        uid = guid.group(1) if guid else hashlib.sha1((it.findtext("guid", "") or it.findtext("link", "")).encode()).hexdigest()[:12]
        title = html.unescape(it.findtext("title", ""))
        source = it.findtext("source", "")  # Google Notícias: "Título - Site" e o site também em <source>
        if source and title.endswith(" - " + source):
            title = title[: -len(source) - 3]
        try:
            dt = parsedate_to_datetime(it.findtext("pubDate", ""))
            when, short = f"{dt.day} {MONTHS[dt.month - 1]} {dt.year} · {dt:%H:%M}", f"{dt.day:02d}/{dt.month:02d}"
        except (TypeError, ValueError):
            when, short = "", ""
        items.append({
            "id": f"noticia_{uid}",
            "titulo": title,
            "link": it.findtext("link", ""),
            "quando": when, "data": short,
            "autor": it.findtext("dc:creator", "", NS) or source,
            "categorias": [c.text for c in it.findall("category") if c.text and c.text != "Notícias"],
            "resumo": _text(it.findtext("description", "")),
            "imagem": img.group(1) if img else None,
        })
    return items


def cached():
    try:
        return json.loads(CACHE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"quando": 0, "itens": []}


def refresh(force=False):
    """Busca o feed se o cache estiver velho. Devolve True se trouxe algo novo."""
    old = cached()
    if not force and time.time() - old.get("quando", 0) < MAX_AGE:
        return False
    items = []
    for url in (FEED, FEED + "?paged=2"):  # duas páginas: as 20 notícias mais recentes
        req = urllib.request.Request(url, headers={"User-Agent": "RE-Hub/1.0 (launcher pessoal)"})
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                items += [i for i in _parse(r.read()) if i["id"] not in {x["id"] for x in items}]
        except OSError:
            if not items:
                raise
            break
    items = items[:20]  # alguns feeds (ex.: Google Notícias) mandam 100
    DATA.mkdir(exist_ok=True)
    CACHE.write_text(json.dumps({"quando": time.time(), "itens": items}, ensure_ascii=False, indent=1), encoding="utf-8")
    return [i["id"] for i in items] != [i["id"] for i in old.get("itens", [])]


def chapters():
    """Cada notícia vira um "capítulo" da aba, no formato que a tela já sabe mostrar."""
    out = []
    for n in cached().get("itens", []):
        out.append({
            "id": n["id"], "titulo": n["titulo"], "quando": n["quando"], "onde": SOURCE,
            "formato": "Notícia · " + (", ".join(n["categorias"][:2]) or FR["nome"]),
            "categoria": n["data"], "sinopse": n["resumo"],
            "lancamentos": [{"nome": n["titulo"], "ano": n["data"], "plataformas": "por " + (n["autor"] or SOURCE),
                             "onde": ", ".join(n["categorias"]) or SITE}],
            "arte": {"capa": [n["imagem"]], "fonte": "imagem: " + SOURCE} if n["imagem"] else None,
            "links": [{"nome": "Ler notícia", "url": n["link"]}],
        })
    return out
