"""Baixa a ISO de um jogo pelos links que a pessoa guardou em data/isos.json (so no PC dela).

O arquivo fica em data/, que o instalador do hub nao leva: os links nunca saem deste PC. Cada chave e o id
da versao (ex.: "cvx_enhanced") ou do capitulo (ex.: "veronica", vale para todas as versoes dele); o valor e
um link direto, do MediaFire ou do Google Drive. Se o link for um .zip/.rar/.7z, o hub extrai e acha a imagem.
"""
import base64
import json
import re
import shutil
import urllib.parse
from pathlib import Path

from . import github, isofind
from .paths import DATA

LINKS = DATA / "isos.json"
DEST = DATA / "isos"
HELP = ("Um link por jogo. Chave = id da versao (games/<id>.json) ou do capitulo. Aceita link direto, MediaFire "
        "e Google Drive (MEGA nao: os arquivos de la vem criptografados). Use so copias suas.")
PREFER = [".cue", ".iso", ".chd", ".gdi", ".cdi", ".rvz", ".wbfs", ".cso", ".pbp"]


def needs_iso(game):
    return "{iso}" in game.get("args", "") or bool(game.get("emulador"))


def links():
    try:
        data = json.loads(LINKS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: v.strip() for k, v in data.items() if not k.startswith("_") and isinstance(v, str) and v.strip()}


def link_for(game):
    ls = links()
    return ls.get(game["id"]) or ls.get(game.get("capitulo", ""))


def ensure_file(games):
    """Cria/completa data/isos.json com uma linha vazia para cada jogo que usa ISO (nunca apaga o que ja tem)."""
    try:
        data = json.loads(LINKS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data["_leia"] = HELP
    for g in games:
        if needs_iso(g) and g["tipo"] != "steam":
            data.setdefault(g["id"], "")
    LINKS.parent.mkdir(parents=True, exist_ok=True)
    LINKS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return LINKS


def resolve(url):
    """Transforma o link da pagina (MediaFire, Drive) no link do arquivo."""
    host = urllib.parse.urlparse(url).netloc.lower()
    if "mega.nz" in host or "mega.co.nz" in host:
        raise RuntimeError("Links do MEGA vem criptografados e o hub nao consegue baixar. Use um link direto, "
                           "do MediaFire ou do Google Drive em data/isos.json.")
    if "mediafire.com" in host and not host.startswith("download"):
        with github._open(url) as r:
            page = r.read().decode("utf-8", "ignore")
        m = re.search(r'data-scrambled-url="([^"]+)"', page)
        if m:
            return base64.b64decode(m.group(1)).decode()
        m = re.search(r'href="(https?://download\d*\.mediafire\.com/[^"]+)"', page)
        if not m:
            raise RuntimeError("Nao achei o botao de download nessa pagina do MediaFire (o arquivo pode ter saido do ar).")
        return m.group(1)
    m = re.search(r"drive\.google\.com/(?:file/d/|open\?id=|uc\?(?:.*&)?id=)([\w-]+)", url)
    if m:
        return f"https://drive.usercontent.google.com/download?id={m.group(1)}&export=download&confirm=t"
    return url


def _filename(r, url, fallback):
    cd = r.headers.get("Content-Disposition", "")
    m = re.search(r"filename\*=UTF-8''([^;]+)", cd, re.I) or re.search(r'filename="?([^";]+)"?', cd, re.I)
    name = urllib.parse.unquote(m.group(1)) if m else urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
    name = re.sub(r'[\\/:*?"<>|]', "_", name).strip()
    return name or fallback


def _pick_image(folder):
    files = [p for p in Path(folder).rglob("*") if p.is_file() and p.suffix.lower() in isofind.EXTS]
    if not files:
        raise RuntimeError("O arquivo baixado nao tem nenhuma ISO/imagem dentro.")
    return sorted(files, key=lambda p: (PREFER.index(p.suffix.lower()) if p.suffix.lower() in PREFER else 99,
                                        -p.stat().st_size))[0]


def download(game, progress=None, cancelled=lambda: False):
    """Baixa (e extrai, se vier compactada) a ISO do jogo para data/isos/<id>/. Devolve o caminho da imagem."""
    url = link_for(game)
    if not url:
        raise RuntimeError(f"Sem link para {game['nome']} em {LINKS}.")
    url = resolve(url)
    folder = DEST / game["id"]
    tmp = folder / "_baixando"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with github._open(url, timeout=60) as r:
        if "text/html" in r.headers.get("Content-Type", ""):
            raise RuntimeError("O link abriu uma pagina, nao um arquivo. Use o link direto de download.")
        name = _filename(r, r.geturl(), game["id"] + ".iso")
        part = tmp / name
        with open(part, "wb") as f:
            github.copy_progress(r, f, progress, cancelled)
    if part.suffix.lower() in github.ARCHIVES:
        out = folder / "jogo"
        github.extract_archive(part, out)
        shutil.rmtree(tmp, ignore_errors=True)
        return _pick_image(out)
    final = folder / name
    final.unlink(missing_ok=True)
    part.replace(final)
    shutil.rmtree(tmp, ignore_errors=True)
    return final


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


def clock(s):
    s = int(s)
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}:{s % 60:02d}"



# ---------- importar uma lista de links ----------
def _game_from_text(text, games):
    """O jogo que um nome (chave do arquivo ou nome do arquivo no link) indica: id, capitulo ou palavras da busca."""
    key = text.strip().lower()
    for g in games:
        if key in (g["id"].lower(), g.get("capitulo", "").lower()):
            return g
    best, top = None, 0
    probe = Path(re.sub(r'[\\/:*?"<>|]', " ", key) + ".zip")   # .zip: nao filtra pelo tipo de imagem
    for g in games:
        s = _score(probe, {**g, "iso_busca": g.get("iso_busca", []) + [g["nome"]]})
        if s > top:
            best, top = g, s
    return best


def import_links(path, games):
    """Le uma lista de links (.json igual ao isos.json, ou .txt com 'jogo = link', 'jogo: link' ou so o link, um por
    linha) e junta em data/isos.json. Devolve ({id: link} do que entrou, [linhas que nao deu para ligar a um jogo])."""
    games = [g for g in games if needs_iso(g) and g["tipo"] != "steam"]
    text = Path(path).read_text(encoding="utf-8-sig", errors="ignore")
    pairs = []
    try:
        data = json.loads(text)
        pairs = [(k, v) for k, v in data.items() if not k.startswith("_") and isinstance(v, str) and v.strip()]
    except ValueError:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.search(r"https?://\S+", line)
            if not m:
                continue
            name = line[:m.start()].strip(" \t=:-|;,")
            pairs.append((name, m.group(0)))
    found, missed = {}, []
    for name, url in pairs:
        if not name:   # so o link: o nome do arquivo dentro dele diz o jogo
            name = urllib.parse.unquote(re.sub(r"/file/?$", "", urllib.parse.urlparse(url).path)).replace("/", " ")
        g = _game_from_text(name, games)
        if g:
            found[g["id"]] = url.strip()
        else:
            missed.append(f"{name}  {url}".strip())
    if found:
        ensure_file(games)
        data = json.loads(LINKS.read_text(encoding="utf-8"))
        data.update(found)
        LINKS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return found, missed


# ---------- organizar uma pasta de ISOs ja baixadas ----------
GENERIC = ("resident evil", "biohazard")   # nome da serie: casa com qualquer jogo, vale pouco


def _candidates(folder):
    files = [p for p in Path(folder).rglob("*") if p.is_file() and DEST not in p.parents]
    tracks = {t for p in files if p.suffix.lower() == ".cue" for t in _cue_tracks(p)}   # o .cue leva os .bin junto
    for p in files:
        ext = p.suffix.lower()
        if p not in tracks and (ext in isofind.EXTS or ext in github.ARCHIVES):
            yield p


def _score(f, g):
    from .emulators import IMAGE_TYPES
    kinds = IMAGE_TYPES.get(g.get("emulador"))
    ext = f.suffix.lower()
    if kinds and ext not in github.ARCHIVES and f"*{ext}" not in kinds.split():
        return 0   # imagem de outro sistema (ex.: .iso nao e de Game Boy)
    s = isofind.score(f, g["iso_busca"], g.get("iso_serial"))
    name = isofind._norm(f.stem + " " + f.parent.name)
    s -= 2 * sum(1 for w in g["iso_busca"] if isofind._norm(w) in GENERIC and isofind._norm(w) in name)
    return max(s, 0)


def scan_folder(folder, games, cfg):
    """Liga cada arquivo da pasta ao(s) jogo(s) dele. Devolve [(arquivo, [jogos])], so de jogos ainda sem ISO."""
    games = [g for g in games if needs_iso(g) and g["tipo"] != "steam" and g.get("iso_busca")
             and not Path(cfg.get(g["id"]).get("iso") or "?").is_file()]
    files = list(_candidates(folder))
    sc = {(f, g["id"]): _score(f, g) for f in files for g in games}
    owners = {}
    for f in files:
        top = max((sc[f, g["id"]] for g in games), default=0)
        if top:
            owners[f] = [g for g in games if sc[f, g["id"]] == top]
    taken = {g["id"] for gs in owners.values() for g in gs}
    for g in games:   # versoes do mesmo capitulo (ex.: Outbreak e o servidor fan) usam a mesma ISO
        if g["id"] in taken:
            continue
        opts = [f for f, gs in owners.items() if sc[f, g["id"]] and any(o.get("capitulo") == g.get("capitulo") for o in gs)]
        opts.sort(key=lambda f: (any(g["id"].startswith(o["id"]) for o in owners[f]), sc[f, g["id"]]), reverse=True)
        if opts:
            owners[opts[0]].append(g)
    return sorted(owners.items(), key=lambda x: x[1][0]["nome"])


def _cue_tracks(cue):
    try:
        names = re.findall(r'FILE\s+"([^"]+)"', cue.read_text(errors="ignore"), re.I)
    except OSError:
        return []
    return [cue.parent / n for n in names if (cue.parent / n).is_file()]


def organize(matches, progress=None):
    """Move cada imagem para data/isos/<id>/ (o .cue leva os .bin; um .zip/.rar/.7z e extraido e o original
    fica onde estava). Devolve {id do jogo: caminho da imagem}."""
    out = {}
    for k, (f, gs) in enumerate(matches):
        if progress:
            progress(k, len(matches), gs[0]["nome"])
        folder = DEST / gs[0]["id"]
        if f.suffix.lower() in github.ARCHIVES:
            image = _pick_image((github.extract_archive(f, folder / "jogo"), folder / "jogo")[1])
        else:
            folder.mkdir(parents=True, exist_ok=True)
            for extra in (_cue_tracks(f) if f.suffix.lower() == ".cue" else []):
                shutil.move(str(extra), str(folder / extra.name))
            image = folder / f.name
            shutil.move(str(f), str(image))
        for g in gs:
            out[g["id"]] = image
    return out
