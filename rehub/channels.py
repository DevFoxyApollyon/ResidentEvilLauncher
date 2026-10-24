"""Aba Canais: vídeos novos do YouTube e transmissões ao vivo (YouTube e Twitch) dos canais da franquia.

Sem chave de API: os vídeos vêm do feed Atom que todo canal do YouTube publica; "ao vivo" do YouTube sai da
página /live do canal; o da Twitch, do decapi.me (serviço aberto que lê a API da Twitch).
Os canais ficam em data/canais.json (Opções > Canais), o último resultado em data/canais_estado.json.
"""
import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime

from .franchise import FR
from .paths import DATA

CONFIG = DATA / "canais.json"
STATE = DATA / "canais_estado.json"
MAX_AGE = 3 * 60            # confere ao vivo e vídeos novos a cada 3 minutos
NEW_FOR = 7 * 24 * 3600     # vídeo mais velho que isso não vira aviso de "novo"
MAX_VIDEOS = 24
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) RE-Hub/1.0"
NS = {"a": "http://www.w3.org/2005/Atom", "yt": "http://www.youtube.com/xml/schemas/2015",
      "m": "http://search.yahoo.com/mrss/"}
TWITCH = "https://decapi.me/twitch/"
MONTHS = ("jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez")


def _get(url, timeout=15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.5"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


# ---------- canais escolhidos ----------
def config():
    """{"youtube": [{"id", "nome", "handle"}], "twitch": ["login"]}. Na primeira vez vem do franquia.json."""
    try:
        data = json.loads(CONFIG.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = None
    if data is None:
        seed = FR.get("canais", {})
        data = {"youtube": [{"handle": h.lstrip("@")} for h in seed.get("youtube", [])],
                "twitch": [l.lower() for l in seed.get("twitch", [])]}
    data.setdefault("youtube", [])
    data.setdefault("twitch", [])
    return data


def save_config(data):
    DATA.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def resolve_youtube(ref):
    """Aceita @nome, link do canal ou o código UC...; devolve {"id", "nome", "handle"}. ValueError se não achar."""
    ref = ref.strip()
    m = re.search(r"(UC[\w-]{22})", ref)
    handle = None
    if m:
        url = f"https://www.youtube.com/channel/{m.group(1)}"
    else:
        h = re.search(r"@([\w.\-]+)", ref) or re.fullmatch(r"([\w.\-]+)", ref)
        if not h:
            raise ValueError("Use o @ do canal (ex.: @ResidentEvil) ou o link dele.")
        handle = h.group(1)
        url = f"https://www.youtube.com/@{handle}"
    try:
        page = _get(url)
    except OSError:
        raise ValueError("Não consegui abrir o canal. Confira o nome e a internet.")
    cid = re.search(r'rel="canonical" href="https://www\.youtube\.com/channel/(UC[\w-]{22})"', page)
    if not cid:
        raise ValueError("Canal do YouTube não encontrado.")
    name = re.search(r'<meta property="og:title" content="([^"]*)"', page)
    return {"id": cid.group(1), "handle": handle or "", "nome": html.unescape(name.group(1)) if name else (handle or cid.group(1))}


def clean_twitch(ref):
    login = re.sub(r"^(https?://)?(www\.)?twitch\.tv/", "", ref.strip().lower()).strip("/@ ")
    if not re.fullmatch(r"\w{3,25}", login):
        raise ValueError("Use o nome do canal da Twitch (ex.: gaules) ou o link dele.")
    return login


def add_youtube(ref):
    ch = resolve_youtube(ref)
    data = config()
    if any(c.get("id") == ch["id"] for c in data["youtube"]):
        raise ValueError(f"{ch['nome']} já está na lista.")
    # troca a entrada que só tinha o @ (ainda sem código) pela completa
    data["youtube"] = [c for c in data["youtube"] if not (ch["handle"] and c.get("handle", "").lower() == ch["handle"].lower())] + [ch]
    save_config(data)
    return ch["nome"]


def add_twitch(ref):
    login = clean_twitch(ref)
    data = config()
    if login in data["twitch"]:
        raise ValueError(f"{login} já está na lista.")
    data["twitch"].append(login)
    save_config(data)
    return login


def remove(kind, key):
    data = config()
    if kind == "youtube":
        data["youtube"] = [c for c in data["youtube"] if (c.get("id") or c.get("handle")) != key]
    else:
        data["twitch"] = [l for l in data["twitch"] if l != key]
    save_config(data)


# ---------- YouTube ----------
def _ago(iso):
    try:
        dt = datetime.fromisoformat(iso)
    except (TypeError, ValueError):
        return 0, "", ""
    local = dt.astimezone()
    return dt.timestamp(), f"{local.day} {MONTHS[local.month - 1]} {local.year} · {local:%H:%M}", f"{local.day:02d}/{local.month:02d}"


def youtube_videos(ch):
    root = ET.fromstring(_get(f"https://www.youtube.com/feeds/videos.xml?channel_id={ch['id']}"))
    author = root.findtext("a:author/a:name", "", NS) or ch.get("nome", "")
    out = []
    for e in root.findall("a:entry", NS):
        vid = e.findtext("yt:videoId", "", NS)
        ts, when, short = _ago(e.findtext("a:published", "", NS))
        stats = e.find("m:group/m:community/m:statistics", NS)
        out.append({
            "plataforma": "youtube", "id": vid, "titulo": html.unescape(e.findtext("a:title", "", NS)),
            "canal": author, "link": f"https://www.youtube.com/watch?v={vid}", "canal_link": f"https://www.youtube.com/channel/{ch['id']}",
            "ts": ts, "quando": when, "data": short,
            "imagem": f"https://i.ytimg.com/vi/{vid}/hqdefault.jpg",
            "views": int(stats.get("views", 0)) if stats is not None else 0,
            "resumo": re.sub(r"\s+", " ", e.findtext("m:group/m:description", "", NS) or "").strip()[:400],
        })
    return out


def youtube_live(ch):
    """A transmissão ao vivo do canal agora, ou None. Lê a página /live: só os dados do vídeo principal
    (videoDetails) dizem se é ao vivo ou reprise; o resto da página lista outras lives recomendadas."""
    page = _get(f"https://www.youtube.com/channel/{ch['id']}/live")
    i = page.find('"videoDetails":{')
    if i < 0 or '"isLive":true' not in page[i:i + 6000]:
        return None
    vid = re.search(r'"videoId":"([\w-]{11})"', page[i:i + 6000])
    if not vid:
        return None
    title = re.search(r'<meta name="title" content="([^"]*)"', page)
    watching = re.search(r'"text":"([\d.,]+)"\},\{"text":" (?:watching|assistindo)', page)
    return {"plataforma": "youtube", "id": vid.group(1), "canal_id": ch["id"], "canal": ch.get("nome", ""),
            "titulo": html.unescape(title.group(1)) if title else "Transmissão ao vivo",
            "link": f"https://www.youtube.com/watch?v={vid.group(1)}", "canal_link": f"https://www.youtube.com/channel/{ch['id']}",
            "imagem": f"https://i.ytimg.com/vi/{vid.group(1)}/maxresdefault_live.jpg",
            "espectadores": watching.group(1) if watching else "", "desde": 0, "categoria": ""}


# ---------- Twitch ----------
def _uptime_pt(text):
    """'1 day, 28 minutes, 34 seconds' (decapi.me) vira '1 d 28 min'."""
    parts = {u: int(n) for n, u in re.findall(r"(\d+) (day|hour|minute|second)", text)}
    out = [f"{parts[u]} {s}" for u, s in (("day", "d"), ("hour", "h"), ("minute", "min")) if parts.get(u)]
    return " ".join(out[:2]) or "instantes"


def twitch_live(login):
    """Info do canal se estiver ao vivo, senão None. decapi.me responde 'X is offline' ou o tempo no ar."""
    up = _get(TWITCH + f"uptime/{login}").strip()
    if not up or "offline" in up.lower() or "not found" in up.lower() or "error" in up.lower():
        return None
    title = _get(TWITCH + f"title/{login}").strip()
    game = _get(TWITCH + f"game/{login}").strip()
    try:
        viewers = _get(TWITCH + f"viewercount/{login}").strip()
    except OSError:
        viewers = ""
    return {"plataforma": "twitch", "id": login, "canal": login, "titulo": title or "Ao vivo na Twitch",
            "link": f"https://www.twitch.tv/{login}", "canal_link": f"https://www.twitch.tv/{login}",
            "imagem": f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{login}-640x360.jpg",
            "espectadores": viewers if viewers.isdigit() else "", "desde": 0, "categoria": game, "no_ar": _uptime_pt(up)}


# ---------- estado e atualização ----------
_memo = {"mtime": None, "data": None}


def cached():
    """O último resultado (lido do disco só quando o arquivo muda: a tela pergunta a cada quadro)."""
    try:
        m = STATE.stat().st_mtime
        if _memo["mtime"] != m:
            _memo["data"], _memo["mtime"] = json.loads(STATE.read_text(encoding="utf-8")), m
        return _memo["data"]
    except (OSError, ValueError):
        return {"quando": 0, "videos": [], "lives": [], "vistos": None, "avisadas": []}


def _live_key(l):
    return f"{l['plataforma']}:{l['id']}"


def refresh(force=False):
    """Busca vídeos e lives. Devolve (videos_novos, lives_novas) para o app avisar, ou None se ainda está fresco.
    Na primeira vez nada é 'novo' (senão o app abriria com um aviso para cada vídeo antigo)."""
    old = cached()
    if not force and time.time() - old.get("quando", 0) < MAX_AGE - 5:
        return None
    cfg = config()
    jobs = [("v", c) for c in cfg["youtube"]] + [("y", c) for c in cfg["youtube"]] + [("t", l) for l in cfg["twitch"]]

    def run(job):
        kind, c = job
        try:
            if kind == "v":
                if not c.get("id"):
                    c.update(resolve_youtube(c["handle"]))
                return kind, youtube_videos(c)
            if kind == "y":
                if not c.get("id"):
                    return kind, None
                return kind, youtube_live(c)
            return kind, twitch_live(c)
        except (OSError, ValueError, ET.ParseError):
            return kind, "erro"
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(run, jobs))
    if any(c.get("id") for c in cfg["youtube"]):
        save_config(cfg)   # guarda os códigos que acabaram de ser descobertos pelos @
    videos, lives, failed = [], [], False
    for kind, res in results:
        if res == "erro":
            failed = True
        elif kind == "v":
            videos += res
        elif res:
            lives.append(res)
    if failed and not videos and not lives and old.get("videos"):
        return None   # sem internet: fica com o que já tinha
    videos.sort(key=lambda v: -v["ts"])
    videos = videos[:MAX_VIDEOS]
    now = time.time()
    seen = old.get("vistos")
    first = seen is None
    seen = set(seen or [])
    new_videos = [v for v in videos if v["id"] not in seen and now - v["ts"] < NEW_FOR] if not first else []
    told = set(old.get("avisadas", []))
    new_lives = [l for l in lives if _live_key(l) not in told] if not first else []
    DATA.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({
        "quando": now, "videos": videos, "lives": lives,
        "vistos": sorted(seen | {v["id"] for v in videos}), "avisadas": [_live_key(l) for l in lives],
    }, ensure_ascii=False, indent=1), encoding="utf-8")
    return new_videos, new_lives


def _count(n):
    n = int(n)
    return f"{n / 1000:.1f} mil".replace(".", ",").replace(",0", "") if n >= 10000 else (f"{n:,}".replace(",", ".") if n else "0")


def _duration(seconds):
    m = int(seconds // 60)
    return f"{m // 60}h{m % 60:02d}" if m >= 60 else f"{m} min"


def chapters():
    """Lives primeiro e depois os vídeos mais novos, no formato de "capítulo" que a tela já sabe mostrar."""
    out, st, now = [], cached(), time.time()
    for l in st.get("lives", []):
        plat = "Twitch" if l["plataforma"] == "twitch" else "YouTube"
        bits = [plat, l["canal"]]
        if l.get("espectadores"):
            bits.append(f"{l['espectadores']} assistindo")
        if l.get("desde"):
            bits.append(f"no ar há {_duration(now - l['desde'])}")
        elif l.get("no_ar"):
            bits.append(f"no ar há {l['no_ar']}")
        out.append({
            "id": f"live_{l['plataforma']}_{l['id']}_{int(st.get('quando', 0) // 600)}", "titulo": l["titulo"],
            "quando": "AO VIVO AGORA", "onde": " · ".join(bits[1:]),
            "formato": f"Ao vivo · {plat}", "categoria": "AO VIVO", "ao_vivo": True, "plataforma": l["plataforma"],
            "sinopse": l.get("categoria") and f"Jogando / categoria: {l['categoria']}" or f"{l['canal']} está transmitindo agora no {plat}.",
            "lancamentos": [{"nome": l["titulo"], "ano": "AO VIVO", "plataformas": f"{plat} · {l['canal']}",
                             "onde": (f"{l['espectadores']} espectadores" if l.get("espectadores") else "transmissão em andamento")}],
            "arte": {"capa": [l["imagem"]], "fonte": "imagem: " + plat},
            "links": [{"nome": "Assistir ao vivo", "url": l["link"]}, {"nome": "Canal", "url": l["canal_link"]}],
        })
    for v in st.get("videos", []):
        out.append({
            "id": f"yt_{v['id']}", "titulo": v["titulo"], "quando": v["quando"], "onde": v["canal"],
            "formato": "Vídeo · YouTube", "categoria": v["data"], "plataforma": "youtube",
            "sinopse": v["resumo"],
            "lancamentos": [{"nome": v["titulo"], "ano": v["data"], "plataformas": f"{v['canal']} · {_count(v['views'])} visualizações",
                             "onde": "youtube.com"}],
            "arte": {"capa": [v["imagem"]], "fonte": "imagem: YouTube"},
            "links": [{"nome": "Assistir no YouTube", "url": v["link"]}, {"nome": "Canal", "url": v["canal_link"]}],
        })
    return out


def live_count():
    return len(cached().get("lives", []))
