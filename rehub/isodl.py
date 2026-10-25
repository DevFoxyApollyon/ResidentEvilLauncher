"""ISOs dos jogos: links da pessoa (data/isos.json, só neste PC), download, conversão e organização.

O arquivo fica em data/, que o instalador e o repositório não levam: os links nunca saem deste PC. Cada chave é o id
da versão (ex.: "cvx_enhanced") ou do capítulo (ex.: "veronica", vale para todas as versões dele). O valor é um link
ou, para ter mais de uma opção, {"Normal": link, "Português": link, "Dublada": link}. Aceita link direto, MediaFire e
Google Drive; se vier .zip/.rar/.7z, o hub extrai e acha a imagem. Se a imagem for de um formato que a versão não abre
(ex.: .chd num port que só lê .iso), o hub converte com o chdman do MAME.
"""
import base64
import fnmatch
import json
import re
import shutil
import subprocess
import tempfile
import urllib.parse
from pathlib import Path

from . import github, isofind
from .paths import DATA

LINKS = DATA / "isos.json"
DEST = DATA / "isos"
CHDMAN = DATA / "ferramentas" / "chdman.exe"
VARIANTS = ("Normal", "Português", "Dublada")
HELP = ('Um jogo por chave (id da versão em games/<id>.json, ou do capítulo). Valor: {"Normal": link, "Português": link, '
        '"Dublada": link} (deixe vazio o que não tiver). Aceita link direto, MediaFire e Google Drive (MEGA não: os '
        "arquivos de lá vêm criptografados). Use só cópias suas.")
PREFER = [".cue", ".iso", ".chd", ".gdi", ".cdi", ".rvz", ".wbfs", ".cso", ".pbp"]
PARTIAL = (".crdownload", ".part", ".partial", ".download", ".tmp", ".opdownload")
NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def image_types(game):
    """Tipos de imagem que a versão abre ("*.iso *.chd ..."): os do emulador dela; um port nativo (sem emulador)
    lê só .iso (ex.: o recvx-enhanced-port do Code Veronica não abre .chd)."""
    from .emulators import IMAGE_TYPES
    return game.get("iso_tipos") or IMAGE_TYPES.get(game.get("emulador"), "*.iso")


def accepts(game, path):
    return f"*{Path(path).suffix.lower()}" in image_types(game).split()


def convertible(game, path):
    """True se a imagem não é do formato da versão, mas o hub sabe converter (.chd -> .iso)."""
    return Path(path).suffix.lower() == ".chd" and not accepts(game, path) and "*.iso" in image_types(game).split()


def bad_image(path, game=None):
    """Mensagem se o arquivo não serve como imagem do jogo (download que não terminou, vazio, formato que a versão
    não abre); None se estiver ok."""
    p = Path(path)
    if p.suffix.lower() in PARTIAL or p.name.lower().startswith("não confirmado"):
        return (f"{p.name} é um download que ainda não terminou (ou foi cancelado).\n\n"
                "Espere o navegador terminar de baixar e escolha o arquivo final (.iso, .chd, .cue...).")
    if game is not None and not accepts(game, p):
        kinds = image_types(game).replace("*", "")
        extra = " O hub pode converter para .iso." if convertible(game, p) else ""
        return f"{game['nome']} só abre {kinds}; {p.name} é {p.suffix.lower()}.{extra}"
    try:
        if p.stat().st_size < 64 * 1024:   # ROM de Game Boy tem poucos MB; menos que isso não é jogo
            return f"{p.name} é pequeno demais para ser a imagem do jogo."
    except OSError:
        return f"Não encontrei {p.name}."
    disc_9660 = game is not None and game.get("emulador") in (None, "pcsx2", "duckstation")   # Wii/GameCube não é
    if p.suffix.lower() == ".iso" and disc_9660 and not is_iso9660(p):
        return f"{p.name} não é uma imagem de disco válida (pode ter sido convertida errado ou estar incompleta)."
    return None


def needs_iso(game):
    return "{iso}" in game.get("args", "") or bool(game.get("emulador"))


# ---------- links (com opções: Normal, Português, Dublada) ----------
def _variants(value):
    """O valor do isos.json como {opção: link}, só com os links preenchidos (um texto sozinho é a opção Normal)."""
    if isinstance(value, str):
        return {"Normal": value.strip()} if value.strip() else {}
    if isinstance(value, dict):
        return {k: v.strip() for k, v in value.items() if isinstance(v, str) and v.strip()}
    return {}


def links():
    try:
        data = json.loads(LINKS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return {k: _variants(v) for k, v in data.items() if not k.startswith("_") and _variants(v)}


def link_for(game):
    """{opção: link} da versão (as do capítulo valem também, as da versão por cima); {} se não houver."""
    ls = links()
    return {**ls.get(game.get("capitulo", ""), {}), **ls.get(game["id"], {})}


def default_variant(game):
    opts = link_for(game)
    return next((v for v in VARIANTS if v in opts), next(iter(opts), None))


def ensure_file(games):
    """Cria/completa data/isos.json com as opções vazias para cada jogo que usa ISO (nunca apaga o que já tem)."""
    try:
        data = json.loads(LINKS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    data["_leia"] = HELP
    for g in games:
        if needs_iso(g) and g["tipo"] != "steam":
            cur = data.get(g["id"])
            if isinstance(cur, str):   # formato antigo (um link só): vira a opção Normal
                cur = {"Normal": cur}
            data[g["id"]] = {**{v: "" for v in VARIANTS}, **(cur or {})}
    LINKS.parent.mkdir(parents=True, exist_ok=True)
    LINKS.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return LINKS


def resolve(url):
    """Transforma o link da página (MediaFire, Drive) no link do arquivo."""
    host = urllib.parse.urlparse(url).netloc.lower()
    if "mega.nz" in host or "mega.co.nz" in host:
        raise RuntimeError("Links do MEGA vêm criptografados e o hub não consegue baixar. Use um link direto, "
                           "do MediaFire ou do Google Drive em data/isos.json.")
    if "mediafire.com" in host and not host.startswith("download"):
        with github._open(url) as r:
            page = r.read().decode("utf-8", "ignore")
        m = re.search(r'data-scrambled-url="([^"]+)"', page)
        if m:
            return base64.b64decode(m.group(1)).decode()
        m = re.search(r'href="(https?://download\d*\.mediafire\.com/[^"]+)"', page)
        if not m:
            raise RuntimeError("Não achei o botão de download nessa página do MediaFire (o arquivo pode ter saído do ar).")
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
        raise RuntimeError("O arquivo baixado não tem nenhuma ISO/imagem dentro.")
    return sorted(files, key=lambda p: (PREFER.index(p.suffix.lower()) if p.suffix.lower() in PREFER else 99,
                                        -p.stat().st_size))[0]


def _folder(game, variant=None):
    """data/isos/<id>/ (a opção Normal) ou data/isos/<id>/<opção>/ (Português, Dublada)."""
    base = DEST / game["id"]
    return base if not variant or variant == "Normal" else base / re.sub(r"[^\w-]+", "_", variant)


def download(game, progress=None, cancelled=lambda: False, variant=None, convert_progress=None):
    """Baixa (e extrai, se vier compactada) a ISO do jogo na opção pedida (ou na padrão). Se ela vier num formato
    que a versão não abre, converte. Devolve o caminho da imagem."""
    opts = link_for(game)
    variant = variant if variant in opts else default_variant(game)
    if not variant:
        raise RuntimeError(f"Sem link para {game['nome']} em {LINKS}.")
    url = resolve(opts[variant])
    folder = _folder(game, variant)
    tmp = folder / "_baixando"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    with github._open(url, timeout=60) as r:
        if "text/html" in r.headers.get("Content-Type", ""):
            raise RuntimeError("O link abriu uma página, não um arquivo. Use o link direto de download.")
        name = _filename(r, r.geturl(), game["id"] + ".iso")
        part = tmp / name
        with open(part, "wb") as f:
            github.copy_progress(r, f, progress, cancelled)
    if part.suffix.lower() in github.ARCHIVES:
        out = folder / "jogo"
        github.extract_archive(part, out)
        shutil.rmtree(tmp, ignore_errors=True)
        image = _pick_image(out)
    else:
        image = folder / name
        image.unlink(missing_ok=True)
        part.replace(image)
        shutil.rmtree(tmp, ignore_errors=True)
    if convertible(game, image):
        image = convert(game, image, convert_progress or progress, cancelled, keep=False)
    return image


# ---------- conversão (.chd -> .iso) pelo chdman do MAME ----------
def ensure_chdman(progress=None, cancelled=lambda: False):
    """Baixa o MAME oficial (GitHub mamedev/mame) uma vez e tira dele só o chdman.exe."""
    if CHDMAN.exists():
        return CHDMAN
    release = github.latest_release("mamedev/mame")
    asset = next((a for a in release.get("assets", []) if fnmatch.fnmatch(a["name"].lower(), "mame*64bit.exe")
                  or fnmatch.fnmatch(a["name"].lower(), "mame*x64.exe")), None)
    if not asset:
        raise RuntimeError("Não achei o MAME para Windows na última release do mamedev/mame.")
    with tempfile.TemporaryDirectory() as tmp:
        sfx = Path(tmp) / asset["name"]
        with github._open(asset["browser_download_url"], timeout=600) as r, open(sfx, "wb") as f:
            github.copy_progress(r, f, progress, cancelled)
        out = Path(tmp) / "x"
        out.mkdir()
        for cmd in github._extractors(sfx, out):   # o .exe do MAME é um 7-Zip autoextraível
            try:
                subprocess.run(cmd + (["chdman.exe"] if Path(cmd[0]).name.lower() == "tar.exe" else []),
                               capture_output=True, stdin=subprocess.DEVNULL, timeout=600, creationflags=NO_WINDOW)
            except (OSError, subprocess.TimeoutExpired):
                continue
            found = next(out.rglob("chdman.exe"), None)
            if found:
                CHDMAN.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(found, CHDMAN)
                return CHDMAN
    raise RuntimeError("Não consegui tirar o chdman.exe do MAME. Instale o 7-Zip e tente de novo.")


def is_iso9660(path):
    """True se o arquivo é uma imagem de disco de verdade (o descritor 'CD001' no setor 16)."""
    try:
        with open(path, "rb") as f:
            f.seek(16 * 2048)
            return f.read(6)[1:6] == b"CD001"
    except OSError:
        return False


def _chd_kind(chdman, src):
    """"cd" ou "dvd": um .chd feito de .bin/.cue (createcd) guarda setores crus de CD, não dá para extrair como DVD."""
    r = subprocess.run([str(chdman), "info", "-i", str(src)], capture_output=True, text=True, errors="ignore",
                       stdin=subprocess.DEVNULL, creationflags=NO_WINDOW)
    return "cd" if re.search(r"Tag='(CHT2|CHTR|CHCD)'|cdlz|cdzl|cdfl", r.stdout) else "dvd"


def _run_chdman(cmd, progress, cancelled, part, parts, cleanup):
    """Roda o chdman e passa a porcentagem dele (a etapa `part` de `parts`) para progress."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                            creationflags=NO_WINDOW)
    buf, log = "", ""
    while True:
        ch = proc.stdout.read(1)
        if not ch:
            break
        if cancelled():
            proc.kill()
            proc.wait()
            cleanup()
            raise RuntimeError("Conversão cancelada.")
        c = ch.decode("latin-1")
        if c in "\r\n":
            m = re.search(r"([\d.]+)% complete", buf)
            if m and progress:
                progress(int((part + float(m.group(1)) / 100) / parts * 1000), 1000, 0, None)
            log, buf = (log + buf + "\n")[-2000:], ""
        else:
            buf += c
    if proc.wait() != 0:
        cleanup()
        raise RuntimeError("O chdman não conseguiu converter.\n" + log[-300:])


def _bin_to_iso(cue, out, progress, cancelled, part, parts):
    """Tira os 2048 bytes de dados de cada setor de 2352 da faixa de dados (MODE1 a partir do byte 16, MODE2 do 24)."""
    text = cue.read_text(errors="ignore")
    m = re.search(r'FILE\s+"([^"]+)".*?TRACK\s+\d+\s+(MODE[12])/(2352|2048)', text, re.S | re.I)
    if not m:
        raise RuntimeError("A faixa de dados do CD não é MODE1/MODE2 (2048 ou 2352 bytes); não sei converter.")
    binf = cue.parent / m.group(1)
    if m.group(3) == "2048":   # setores já só com os dados (MODE1/2048): o .bin já é a ISO
        binf.replace(out)
        return
    offset = 16 if m.group(2).upper() == "MODE1" else 24
    total = binf.stat().st_size // 2352
    with open(binf, "rb") as fi, open(out, "wb") as fo:
        for k in range(total):
            sector = fi.read(2352)
            if len(sector) < 2352:
                break
            fo.write(sector[offset:offset + 2048])
            if k % 4096 == 0:
                if cancelled():
                    raise RuntimeError("Conversão cancelada.")
                if progress:
                    progress(int((part + k / total) / parts * 1000), 1000, 0, None)


def convert(game, path, progress=None, cancelled=lambda: False, keep=True):
    """Converte o .chd para .iso em data/isos/<id>/ (o original fica, a não ser que keep=False).
    .chd de DVD: chdman extractdvd. .chd de CD (feito de .bin/.cue): chdman extractcd e depois tira os dados de cada
    setor. No fim confere se o .iso é uma imagem de disco de verdade.
    progress(feito, total, 0, None) recebe a porcentagem em milésimos."""
    src = Path(path)
    chdman = ensure_chdman()
    folder = src.parent if DEST in src.parents else _folder(game)
    folder.mkdir(parents=True, exist_ok=True)
    out = folder / (src.stem + ".iso")
    if _chd_kind(chdman, src) == "dvd":
        _run_chdman([str(chdman), "extractdvd", "-i", str(src), "-o", str(out), "-f"], progress, cancelled, 0, 1,
                    lambda: out.unlink(missing_ok=True))
    else:
        tmp = folder / "_convertendo"
        shutil.rmtree(tmp, ignore_errors=True)
        tmp.mkdir()
        try:
            cue = tmp / "disco.cue"
            _run_chdman([str(chdman), "extractcd", "-i", str(src), "-o", str(cue), "-ob", str(tmp / "disco.bin"), "-f"],
                        progress, cancelled, 0, 2, lambda: None)
            _bin_to_iso(cue, out, progress, cancelled, 1, 2)
        except BaseException:
            out.unlink(missing_ok=True)
            raise
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
    if not is_iso9660(out):
        out.unlink(missing_ok=True)
        raise RuntimeError(f"A conversão de {src.name} não gerou uma imagem de disco válida.")
    if progress:
        progress(1000, 1000, 0, None)
    if not keep:
        src.unlink(missing_ok=True)
    return out


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024


def clock(s):
    s = int(s)
    return f"{s // 3600}h{s % 3600 // 60:02d}m" if s >= 3600 else f"{s // 60}:{s % 60:02d}"


# ---------- importar uma lista de links ----------
def _variant_in(name):
    """A opção escrita junto do nome na lista ("code veronica dublada = link"): devolve (opção, nome sem ela)."""
    low = name.lower()
    for word, variant in (("dublad", "Dublada"), ("pt-br", "Português"), ("ptbr", "Português"), ("portugu", "Português"),
                          ("traduz", "Português"), ("normal", "Normal"), ("original", "Normal")):
        if word in low:
            return variant, re.sub(rf"[\[(|/-]?\s*\w*{word}\w*\s*[\])]?", " ", name, flags=re.I).strip()
    return "Normal", name


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
    """Lê uma lista de links (.json igual ao isos.json, ou .txt com 'jogo = link', 'jogo dublada: link' ou só o link,
    um por linha) e junta em data/isos.json. A opção (Normal, Português, Dublada) vem de uma palavra junto do nome.
    Devolve ({id: {opção: link}} do que entrou, [linhas que não deu para ligar a um jogo])."""
    games = [g for g in games if needs_iso(g) and g["tipo"] != "steam"]
    text = Path(path).read_text(encoding="utf-8-sig", errors="ignore")
    pairs = []
    try:
        data = json.loads(text)
        for k, v in data.items():
            if not k.startswith("_"):
                pairs += [(k, var, url) for var, url in _variants(v).items()]
    except ValueError:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            m = re.search(r"https?://\S+", line)
            if not m:
                continue
            var, name = _variant_in(line[:m.start()].strip(" \t=:-|;,"))
            pairs.append((name, var, m.group(0)))
    found, missed = {}, []
    for name, var, url in pairs:
        if not name:   # só o link: o nome do arquivo dentro dele diz o jogo (e a opção, se tiver "dublado" etc.)
            name = urllib.parse.unquote(re.sub(r"/file/?$", "", urllib.parse.urlparse(url).path)).replace("/", " ")
            var, name = _variant_in(name)
        g = _game_from_text(name, games)
        if g:
            found.setdefault(g["id"], {})[var] = url.strip()
        else:
            missed.append(f"{name}  {url}".strip())
    if found:
        ensure_file(games)
        data = json.loads(LINKS.read_text(encoding="utf-8"))
        for gid, opts in found.items():
            data[gid] = {**_variants(data.get(gid)), **opts} if isinstance(data.get(gid), (dict, str)) else opts
            data[gid] = {**{v: "" for v in VARIANTS}, **data[gid]}
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
    ext = f.suffix.lower()
    if ext not in github.ARCHIVES and f"*{ext}" not in image_types(g).split():
        return 0   # formato que a versão não abre (ex.: .iso não é de Game Boy; port nativo não lê .chd)
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


def adopt(game, path):
    """Move a imagem escolhida pela pessoa para data/isos/<id do jogo>/, com o mesmo nome (o .cue leva os .bin).
    Se ela já estiver lá, não mexe. Devolve o caminho novo."""
    src = Path(path)
    folder = DEST / game["id"]
    if folder.resolve() in src.resolve().parents:
        return src
    folder.mkdir(parents=True, exist_ok=True)
    for extra in (_cue_tracks(src) if src.suffix.lower() == ".cue" else []):
        shutil.move(str(extra), str(folder / extra.name))
    dest = folder / src.name
    if dest.exists():
        dest.unlink()
    shutil.move(str(src), str(dest))
    return dest


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
