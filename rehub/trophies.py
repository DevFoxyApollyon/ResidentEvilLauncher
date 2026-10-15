"""Troféus no estilo PlayStation a partir das conquistas da Steam.

Lê a página pública de conquistas do seu perfil (sem senha nem chave de API) e a
raridade global de cada conquista. Platina = 100%; ouro/prata/bronze vêm da raridade.
"""
import html
import json
import re
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime

from . import steam
from .paths import DATA

CACHE = DATA / "trofeus"
TTL = 6 * 3600  # segundos até buscar de novo
TIERS = ("platina", "ouro", "prata", "bronze")


class TrophyError(Exception):
    pass


def steam_user():
    """(steamid64, nome) da conta usada por último nesta Steam, ou (None, None)."""
    root = steam.steam_path()
    vdf = root / "config" / "loginusers.vdf" if root else None
    if not vdf or not vdf.exists():
        return None, None
    users = re.findall(r'"(7656\d{13})"\s*\{([^}]*)\}', vdf.read_text(encoding="utf-8", errors="ignore"))
    if not users:
        return None, None
    sid, block = next(((s, b) for s, b in users if re.search(r'"MostRecent"\s+"1"', b)), users[0])
    name = re.search(r'"PersonaName"\s+"([^"]*)"', block)
    return sid, name.group(1) if name else None


def tier(percent):
    """Raridade -> tipo do troféu. Sem raridade conhecida, conta como bronze."""
    if percent is not None and percent < 10:
        return "ouro"
    if percent is not None and percent < 35:
        return "prata"
    return "bronze"


def cached(appid):
    """Último resultado salvo, sem acessar a internet."""
    try:
        return json.loads((CACHE / f"{appid}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def is_fresh(result):
    # resultado sem raridade (a Steam falhou no meio) é buscado de novo logo
    ttl = TTL if result.get("completo", True) else 120
    return time.time() - result.get("buscado_em", 0) < ttl


def load(appid, steamid, force=False):
    old = cached(appid)
    if old and not force and is_fresh(old):
        return old
    result = _fetch(appid, steamid)
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{appid}.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
    return result


def _get(url):
    """GET com novas tentativas quando a Steam limita as consultas (HTTP 429)."""
    req = urllib.request.Request(url, headers={"User-Agent": "RE-Hub"})
    for wait in (5, 15, None):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code != 429 or wait is None:
                if e.code == 429:
                    raise TrophyError("A Steam limitou as consultas por agora. Clique em Atualizar daqui a alguns minutos.")
                raise
            time.sleep(wait)


PRIVATE = "Seu perfil está privado. Em Steam > Perfil > Privacidade, deixe 'Detalhes dos jogos' como Público."


def _fetch(appid, steamid):
    base = f"https://steamcommunity.com/profiles/{steamid}/stats/{appid}/achievements/"
    raw = _get(base + "?xml=1&l=brazilian")
    # alguns jogos antigos (Revelations, RE6...) só têm a página HTML, sem a versão XML
    items = _from_xml(raw, appid) if raw.lstrip().startswith(b"<?xml") else _from_html(_get(base + "?l=english"), appid)
    for i in items:
        i["tier"] = tier(i["raridade"])
    return _summary(appid, items)


def _from_xml(raw, appid):
    root = ET.fromstring(raw)
    if root.find("error") is not None:
        raise TrophyError(root.findtext("error"))
    if root.findtext("privacyState") not in (None, "public"):
        raise TrophyError(PRIVATE)
    try:
        data = json.loads(_get("https://api.steampowered.com/ISteamUserStats/"
                               f"GetGlobalAchievementPercentagesForApp/v0002/?gameid={appid}&format=json"))
        # o XML da Steam traz o código em minúsculas e a API em maiúsculas
        rarity = {a["name"].lower(): float(a["percent"]) for a in data["achievementpercentages"]["achievements"]}
    except (OSError, ValueError, KeyError, TrophyError):
        rarity = {}
    backup = {} if rarity else _global_rarity_html(appid)  # API falhou: usa a página pública
    items = []
    for a in root.iter("achievement"):
        icon, name = a.findtext("iconClosed") or "", (a.findtext("name") or "").strip()
        pct = rarity.get((a.findtext("apiname") or "").lower())
        items.append({
            "nome": name,
            "descricao": (a.findtext("description") or "").strip(),
            "icone": icon,
            "conquistado": a.get("closed") == "1",
            "quando": int(a.findtext("unlockTimestamp") or 0),
            "raridade": pct if pct is not None else backup.get(icon, backup.get(name)),
        })
    return items


def _global_rarity_html(appid):
    """{ícone ou nome: % de jogadores} da página pública de conquistas do jogo."""
    try:
        page = _get(f"https://steamcommunity.com/stats/{appid}/achievements/?l=english").decode("utf-8", "ignore")
    except (OSError, TrophyError):
        return {}
    rarity = {}
    for icon, name, _, chunk in _html_rows(page):
        pct = re.search(r'achievePercent">([\d.]+)%', chunk)
        if pct:
            rarity[icon] = rarity[name] = float(pct.group(1))
    return rarity


def _html_rows(page):
    """Cada conquista de uma página HTML da Steam: (ícone, nome, descrição, trecho completo)."""
    rows = []
    for chunk in page.split('class="achieveRow')[1:]:
        icon = re.search(r'<img src="([^"]+)"', chunk)
        name = re.search(r"<h3[^>]*>(.*?)</h3>", chunk, re.S)
        desc = re.search(r"<h5[^>]*>(.*?)</h5>", chunk, re.S)
        rows.append((icon.group(1) if icon else "", html.unescape(name.group(1).strip()) if name else "",
                     html.unescape(desc.group(1).strip()) if desc else "", chunk))
    return rows


def _from_html(raw, appid):
    page = raw.decode("utf-8", "ignore")
    if 'class="achieveRow' not in page:
        if "profile_private_info" in page or "This profile is private" in page:
            raise TrophyError(PRIVATE)
        return []  # jogo sem conquistas (ou ainda não lançado)
    rarity = _global_rarity_html(appid)  # casamos pelo ícone, que é igual nas duas páginas
    items = []
    for icon, name, desc, chunk in _html_rows(page):
        when = re.search(r'achieveUnlockTime">\s*Unlocked (.*?)<', chunk, re.S)
        items.append({"nome": name, "descricao": desc, "icone": icon, "conquistado": bool(when),
                      "quando": _parse_unlock(when.group(1)) if when else 0,
                      "raridade": rarity.get(icon, rarity.get(name))})
    return items


def _parse_unlock(text):
    """'27 Jun @ 2:09pm' ou '3 Mar, 2015 @ 10:01am' -> timestamp."""
    text = " ".join(text.split())
    for fmt in ("%d %b, %Y @ %I:%M%p", "%d %b @ %I:%M%p", "%b %d, %Y @ %I:%M%p", "%b %d @ %I:%M%p"):
        try:
            d = datetime.strptime(text, fmt)
            if "%Y" not in fmt:
                d = d.replace(year=datetime.now().year)
            return int(d.timestamp())
        except ValueError:
            continue
    return 1  # conquistado, mas sem data legível


def _summary(appid, items):
    total, got = len(items), sum(i["conquistado"] for i in items)
    per_tier = {t: [sum(1 for i in items if i["tier"] == t and i["conquistado"]),
                    sum(1 for i in items if i["tier"] == t)] for t in TIERS[1:]}
    per_tier["platina"] = [int(total > 0 and got == total), int(total > 0)]
    return {
        "appid": appid,
        "buscado_em": time.time(),
        "total": total,
        "conquistados": got,
        "progresso": round(100 * got / total) if total else 0,
        "platina": total > 0 and got == total,
        "completo": all(i["raridade"] is not None for i in items),
        "por_tier": per_tier,
        "recentes": sorted((i for i in items if i["conquistado"]), key=lambda i: -i["quando"])[:4],
        "proximos": sorted((i for i in items if not i["conquistado"]), key=lambda i: -(i["raridade"] or 0))[:4],
    }
