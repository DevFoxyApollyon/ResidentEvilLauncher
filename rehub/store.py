"""Dados da loja da Steam: arte oficial (capa vertical e fundo) e DLCs de cada jogo."""
import json
import subprocess
import time
import urllib.parse
import urllib.request

from .franchise import FR
from .paths import COVERS, DATA

CACHE = DATA / "loja"
ASSET_BASE = "https://shared.akamai.steamstatic.com/store_item_assets/"
OLD_CDN = "https://cdn.cloudflare.steamstatic.com/steam/apps/{appid}/{file}"
ART = {"capa": ("library_capsule_2x", "library_capsule", "library_600x900.jpg"),
       "fundo": ("library_hero", "page_background", "library_hero.jpg")}


def _get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "RE-Hub"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.load(r)


def _cached(name, max_age):
    p = CACHE / name
    try:
        if time.time() - p.stat().st_mtime < max_age:
            return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return None


def _save(name, data):
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / name).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def items(appids):
    """{appid: {"assets": {...}, "lancamento": timestamp}} de vários jogos numa consulta só."""
    data = _cached("itens.json", 7 * 86400) or {}
    missing = [a for a in appids if str(a) not in data or "precisao" not in data[str(a)]]
    if missing:
        req = {"ids": [{"appid": a} for a in missing],
               "context": {"language": "brazilian", "country_code": "BR"},
               "data_request": {"include_assets": True, "include_release": True}}
        url = "https://api.steampowered.com/IStoreBrowseService/GetItems/v1?input_json=" + urllib.parse.quote(json.dumps(req))
        for it in _get_json(url).get("response", {}).get("store_items", []):
            rel = it.get("release") or {}
            # precisao: "date_full" (dia certo), "date_month", "date_quarter", "date_year" ou "" (já saiu / sem data)
            data[str(it["appid"])] = {"assets": it.get("assets", {}), "lancamento": rel.get("steam_release_date"),
                                      "precisao": rel.get("coming_soon_display", "") if rel.get("is_coming_soon") else ""}
        _save("itens.json", data)
    return {int(k): v for k, v in data.items()}


def art_key(game):
    """Nome do arquivo de arte da versão: arte própria (ex.: GOG), appid da Steam, ou None (pôster gerado)."""
    if game.get("arte"):
        return game["id"]
    if game["tipo"] == "steam":
        return str(game["appid"])
    return None


def art_path(key, kind):
    """kind: "capa", "fundo" ou "logo" (png com transparência)."""
    p = COVERS / f"{key}_{kind}.{'png' if kind == 'logo' else 'jpg'}"
    return p if key and p.exists() else None


def art_urls(game, kind, info):
    """Links a tentar, em ordem. 'arte' do catálogo pode ter um link ou uma lista."""
    if game.get("arte"):
        own = game["arte"].get(kind) or []
        return [own] if isinstance(own, str) else list(own)
    if game["tipo"] != "steam":
        return []
    if kind == "logo":  # jogos novos não têm logo no endereço antigo: o catálogo pode indicar outro (logo_url)
        return [u for u in (game.get("logo_url"), OLD_CDN.format(appid=game["appid"], file="logo.png")) if u]
    assets = (info or {}).get("assets", {})
    fmt = assets.get("asset_url_format", "")
    urls = [ASSET_BASE + fmt.replace("${FILENAME}", assets[k]) for k in ART[kind][:2] if fmt and assets.get(k)]
    return urls + [OLD_CDN.format(appid=game["appid"], file=ART[kind][2])]


def download_art(game, kind, info=None):
    """Baixa capa, fundo ou logo da versão. Retorna True se conseguiu."""
    COVERS.mkdir(parents=True, exist_ok=True)
    ext = "png" if kind == "logo" else "jpg"
    for url in art_urls(game, kind, info):
        try:
            out = COVERS / f"{art_key(game)}_{kind}.{ext}"
            if "wikia.nocookie.net" in url:  # a Wiki recusa o Python (403); o curl do Windows, com Referer, passa
                subprocess.run(["curl", "-sfL", "--max-time", "20", "-e", FR["wiki_referer"],
                                "-o", str(out), url], check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                return True
            req = urllib.request.Request(url, headers={"User-Agent": "RE-Hub/1.0 (launcher pessoal)"})
            with urllib.request.urlopen(req, timeout=20) as r:
                out.write_bytes(r.read())
            return True
        except (OSError, subprocess.CalledProcessError):
            continue
    return False


SERIES_LOGO = FR["logo_url"]


def download_series_logo():
    """Logo da série (Wikimedia Commons) para o topo do app. Retorna True se baixou agora."""
    dest = COVERS / "_serie_logo.png"
    if dest.exists():
        return False
    try:
        req = urllib.request.Request(SERIES_LOGO, headers={"User-Agent": "RE-Hub/1.0 (launcher pessoal)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            COVERS.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(r.read())
        return True
    except OSError:
        return False


def dlcs(appid):
    """Lista de DLCs: [{id, nome, imagem, preco, lancamento}] (cache de 1 dia)."""
    name = f"dlc_{appid}.json"
    cached = _cached(name, 86400)
    if cached is not None:
        return cached
    data = _get_json(f"https://store.steampowered.com/api/dlcforapp/?appid={appid}&l=brazilian&cc=br")
    out = []
    for d in data.get("dlc", []):
        price = d.get("price_overview") or {}
        if price.get("final") is not None:
            preco = "Grátis" if price["final"] == 0 else f"R$ {price['final'] / 100:.2f}".replace(".", ",")
            if price.get("discount_percent"):
                preco += f"  (-{price['discount_percent']}%)"
        else:
            preco = "Grátis" if d.get("is_free") else ""
        out.append({"id": d["id"], "nome": d.get("name", ""), "imagem": d.get("header_image", ""),
                    "preco": preco, "lancamento": int((d.get("release_date") or {}).get("steam") or 0)})
    out.sort(key=lambda d: -d["lancamento"])
    _save(name, out)
    return out
