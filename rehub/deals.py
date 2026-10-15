"""Preços, promoções e lista de desejos da Steam (APIs públicas, sem senha nem chave)."""
import json
import time
import urllib.request

from .paths import DATA

CACHE = DATA / "loja"
TTL = 6 * 3600


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "RE-Hub"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _load(name):
    try:
        return json.loads((CACHE / name).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _save(name, data):
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def cached():
    """Último resultado guardado (sem internet): {"precos": {...}, "desejos": [...], "buscado_em": ts} ou None."""
    return _load("ofertas.json")


def wishlist(steamid):
    """appids na lista de desejos da Steam (perfil público)."""
    data = _get_json(f"https://api.steampowered.com/IWishlistService/GetWishlist/v1/?steamid={steamid}")
    return [it["appid"] for it in data.get("response", {}).get("items", [])]


def prices(appids):
    """{appid: {"final", "inicial", "desconto", "texto", "texto_inicial"}} em reais. Grátis/sem preço ficam de fora."""
    out = {}
    appids = list(dict.fromkeys(appids))
    for i in range(0, len(appids), 40):  # o filtro de preço aceita vários jogos numa consulta só
        chunk = ",".join(str(a) for a in appids[i:i + 40])
        data = _get_json(f"https://store.steampowered.com/api/appdetails?appids={chunk}&cc=br&filters=price_overview")
        for appid, d in data.items():
            p = (d or {}).get("data") or {}
            p = p.get("price_overview") if isinstance(p, dict) else None
            if p:
                out[int(appid)] = {"final": p["final"], "inicial": p["initial"], "desconto": p.get("discount_percent", 0),
                                   "texto": p.get("final_formatted") or f"R$ {p['final'] / 100:.2f}".replace(".", ","),
                                   "texto_inicial": p.get("initial_formatted", "")}
        time.sleep(0.5)
    return out


def refresh(steamid, appids, force=False):
    """Preços dos jogos da franquia e a lista de desejos, com cache de 6 horas."""
    old = cached()
    if old and not force and time.time() - old.get("buscado_em", 0) < TTL and \
            set(map(str, appids)) <= set(old.get("precos", {})) | set(map(str, old.get("sem_preco", []))):
        return old
    try:
        wl = wishlist(steamid) if steamid else []
    except (OSError, ValueError):
        wl = (old or {}).get("desejos", [])
    p = prices(appids)
    result = {"buscado_em": time.time(), "precos": {str(k): v for k, v in p.items()}, "desejos": wl,
              "sem_preco": [a for a in appids if a not in p]}
    _save("ofertas.json", result)
    return result
