"""Busca global (Ctrl+F): jogos e versões de todas as seções, personagens, vírus e lugares do mapa num lugar só.
Ignora acentos e maiúsculas; cada resultado diz para onde ir ao abrir."""
import unicodedata

from . import catalog, characters, lore

SECTIONS = ("canon", "spinoff", "perdidos", "midia", "hqs", "fas")
KIND_NAMES = {"capitulo": "Jogo", "versao": "Versão", "personagem": "Personagem", "virus": "Vírus", "lugar": "Lugar"}


def norm(text):
    text = unicodedata.normalize("NFKD", str(text or "")).lower()
    return "".join(ch for ch in text if not unicodedata.combining(ch))


def index(games):
    """[{tipo, titulo, sub, alvo, texto}]: alvo diz o que abrir (ver Hub._search_open)."""
    out = []
    for sec in SECTIONS:
        for ch in catalog.load_timeline(games, sec):
            out.append({"tipo": "capitulo", "titulo": ch["titulo"], "sub": " · ".join(p for p in (ch.get("quando"), ch.get("onde")) if p),
                        "alvo": ("capitulo", ch["id"], None), "texto": " ".join((ch["titulo"], ch.get("sinopse", "")))})
            if len(ch["versoes"]) > 1:
                for v in ch["versoes"]:
                    if v.get("tipo") != "info":
                        out.append({"tipo": "versao", "titulo": v["nome"], "sub": f"{ch['titulo']} · {v.get('versao', '')}",
                                    "alvo": ("capitulo", ch["id"], v["id"]), "texto": v["nome"]})
    for p in characters.load():
        out.append({"tipo": "personagem", "titulo": p["nome"], "sub": p.get("papel", ""), "alvo": ("personagem", p["id"]),
                    "texto": " ".join((p["nome"], p.get("busca", ""), p.get("papel", ""))), "auto": p.get("automatica")})
    for i, v in enumerate(lore.load("virus").get("itens", [])):
        out.append({"tipo": "virus", "titulo": v["nome"], "sub": v.get("efeito", ""), "alvo": ("virus", i),
                    "texto": " ".join((v["nome"], v.get("busca", "")))})
    mapa = lore.load("mapa")
    for aba, places in (("mundo", mapa.get("mundo", [])), ("cidade", mapa.get("cidade", {}).get("locais", []))):
        for i, pl in enumerate(places):
            out.append({"tipo": "lugar", "titulo": pl["nome"], "sub": pl.get("regiao", ""), "alvo": ("lugar", aba, i),
                        "texto": pl["nome"]})
    for e in out:
        e["_t"], e["_x"] = norm(e["titulo"]), norm(e["texto"])
    return out


def find(entries, query, limit=40):
    """Resultados em ordem: começa com o texto > palavra que começa com ele > contém no título > contém no resto.
    Várias palavras: todas precisam aparecer."""
    words = norm(query).split()
    if not words:
        return []
    q = " ".join(words)
    scored = []
    for e in entries:
        if not all(w in e["_x"] or w in e["_t"] for w in words):
            continue
        t, tw = e["_t"], e["_t"].split()
        score = (0 if t == q else 1 if t.startswith(q + " ") else 2 if t.startswith(q) else 3 if q in tw
                 else 4 if any(w.startswith(q) for w in tw) else 5 if q in t else 6)
        scored.append((score, e["tipo"] != "capitulo", bool(e.get("auto")), len(t), e))
    scored.sort(key=lambda s: s[:4])
    return [s[4] for s in scored[:limit]]
