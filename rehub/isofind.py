"""Procura a ISO/imagem do jogo no PC da pessoa, para ela nao precisar escolher o arquivo.

Olha as pastas onde as imagens costumam ficar (Downloads, Documentos, Area de trabalho, Jogos e as
raizes dos discos), sem entrar em Windows, Arquivos de Programas e pastas de sistema, ate uma
profundidade limitada. Um arquivo conta quando a extensao e de imagem do sistema do jogo e o nome
tem uma das palavras do jogo ("iso_busca" no catalogo) ou o codigo do disco (ex.: SLUS-20765).
"""
import os
import re
import string
from pathlib import Path

SKIP = {"windows", "program files", "program files (x86)", "programdata", "$recycle.bin", "system volume information",
        "appdata", "node_modules", ".git", "steamapps", "_internal", "recomps", "msys64", "python314"}
EXTS = {".iso", ".bin", ".cue", ".chd", ".cso", ".wbfs", ".rvz", ".gcm", ".ciso", ".3ds", ".cci", ".cxi", ".gbc", ".gb", ".pbp"}


def _roots():
    home = Path.home()
    seen, out = set(), []
    for p in [home / "Downloads", home / "Documents", home / "Desktop", home / "Pictures", home / "Videos",
              home / "OneDrive", home / "Games", home / "Jogos", home] +[Path(f"{d}:\\") for d in string.ascii_uppercase if os.path.exists(f"{d}:\\")]:
        if p.exists() and str(p).lower() not in seen:
            seen.add(str(p).lower())
            out.append(p)
    return out


def _walk(root, depth):
    try:
        with os.scandir(root) as it:
            for e in it:
                name = e.name.lower()
                if e.is_dir(follow_symlinks=False):
                    if depth > 0 and name not in SKIP and not name.startswith("."):
                        yield from _walk(e.path, depth - 1)
                elif os.path.splitext(name)[1] in EXTS:
                    yield e.path
    except OSError:
        return


def _norm(s):
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def score(path, words, serial=None):
    """0 = nao e do jogo; quanto maior, melhor (codigo do disco vale mais que palavras do nome)."""
    name = _norm(Path(path).stem + " " + Path(path).parent.name)
    pts = 0
    if serial and _norm(serial).replace(" ", "") in name.replace(" ", ""):
        pts += 10
    for w in words:
        if _norm(w) and _norm(w) in name:   # palavra so com simbolos (ex.: japones) vira vazia e casaria com tudo
            pts += 3
    if pts and Path(path).suffix.lower() == ".bin" and Path(path).with_suffix(".cue").exists():
        pts -= 1   # com .cue ao lado, o .cue e o arquivo certo
    return pts


def find(words, exts=None, serial=None, limit=5, extra=()):
    """As melhores imagens candidatas, a mais provavel primeiro. extra: pastas a mais (ex.: data/isos do hub)."""
    exts = {e.lower() for e in exts} if exts else EXTS
    hits = {}
    for root in [Path(e) for e in extra if Path(e).is_dir()] + _roots():
        depth = 2 if len(root.parts) == 1 else 4   # raiz do disco: so dois niveis
        for p in _walk(root, depth):
            if os.path.splitext(p)[1].lower() not in exts:
                continue
            s = score(p, words, serial)
            if s > 0:
                hits[os.path.normcase(p)] = (s, p)
    return [p for s, p in sorted(hits.values(), key=lambda x: -x[0])][:limit]
