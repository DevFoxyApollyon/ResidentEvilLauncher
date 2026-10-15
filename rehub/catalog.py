"""Catálogo de jogos: lê games/*.json e guarda as escolhas do usuário."""
import json

from . import news
from .paths import CONFIG, DATA, GAMES_DIR


def load_games():
    games = []
    for f in GAMES_DIR.glob("*.json"):
        if f.name.startswith("_"):
            continue
        g = json.loads(f.read_text(encoding="utf-8"))
        g.setdefault("id", f.stem)
        games.append(g)
    return sorted(games, key=lambda g: (g.get("ordem", 999), g["nome"]))


SECTIONS = {"canon": "capitulos", "spinoff": "nao_canonicos", "perdidos": "perdidos", "midia": "midia", "hqs": "hqs", "fas": "fas"}


def _info_item(c):
    """Filmes, HQs e jogos perdidos não têm executável: viram um item só de informação."""
    return {"id": c["id"], "nome": c["titulo"], "tipo": "info", "versao": c.get("formato", ""),
            "arte": c.get("arte"), "poster": c.get("poster"), "links": c.get("links", [])}


_cache = {"mtime": None, "data": None}


def _timeline_data():
    """O catálogo da linha do tempo, lido do disco só quando o arquivo muda."""
    f = GAMES_DIR / "_linha_do_tempo.json"
    m = f.stat().st_mtime
    if _cache["mtime"] != m:
        _cache["data"], _cache["mtime"] = json.loads(f.read_text(encoding="utf-8")), m
    return _cache["data"]


def load_timeline(games, section="canon"):
    """Capítulos de uma seção ('canon' = história oficial, 'spinoff' = não canônicos),
    cada um com a lista 'versoes' (os jogos dele).

    Jogo sem capítulo conhecido vira um capítulo próprio no fim da história oficial, para nada sumir.
    """
    if section == "noticias":  # vem do feed do REVIL, não do catálogo
        return [dict(c, versoes=[_info_item(c)], secao=section) for c in news.chapters()]
    data = _timeline_data()
    known = {c["id"] for key in SECTIONS.values() for c in data.get(key, [])}
    chapters = {c["id"]: dict(c, versoes=[], secao=section) for c in data.get(SECTIONS[section], [])}
    order = list(chapters)
    for g in games:
        cid = g.get("capitulo") or g["id"]
        if cid not in chapters:
            if section != "canon" or cid in known:
                continue
            chapters[cid] = {"id": cid, "titulo": g["nome"], "quando": "", "onde": "", "versoes": [], "secao": section}
            order.append(cid)
        chapters[cid]["versoes"].append(g)
    for c in chapters.values():
        if not c["versoes"] and section != "canon":  # sem executável: item só de informação
            c["versoes"].append(_info_item(c))
    return [chapters[c] for c in order if chapters[c]["versoes"]]


class Config:
    """config.json: {id_do_jogo: {"exe": ..., "iso": ...}}"""

    def __init__(self):
        try:
            self.data = json.loads(CONFIG.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.data = {}

    def get(self, game_id):
        return self.data.get(game_id, {})

    def clear(self, game_id):
        """Esquece o que o usuário configurou para o jogo (executável, ISO, pasta)."""
        if self.data.pop(game_id, None) is not None:
            CONFIG.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")

    def set(self, game_id, **values):
        self.data.setdefault(game_id, {}).update(values)
        DATA.mkdir(exist_ok=True)
        CONFIG.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
