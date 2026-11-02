"""Limite do cache: cards montados, prints, páginas da wiki, imagens pequenas e trailers são refeitos ou baixados de
novo quando faltam, então podem ser apagados. Ao passar do limite, saem os arquivos usados há mais tempo."""
import os
import shutil

from .paths import DATA

FOLDERS = [DATA / "cache", DATA / "imagens", DATA / "trailers"]   # tudo aqui o app sabe refazer
LIMITS = (1, 2, 5, 10)          # GB que dá para escolher em Opções
DEFAULT = 2


def _files():
    for folder in FOLDERS:
        if not folder.is_dir():
            continue
        for root, _dirs, names in os.walk(folder):
            for n in names:
                p = os.path.join(root, n)
                try:
                    st = os.stat(p)
                except OSError:
                    continue
                yield p, st.st_size, max(st.st_atime, st.st_mtime)


def size():
    """Tamanho do cache em bytes."""
    return sum(s for _p, s, _t in _files())


def prune(limit_gb, keep=0.8):
    """Se o cache passou de limit_gb, apaga os arquivos usados há mais tempo até ficar em keep*limite.
    Devolve (bytes apagados, arquivos apagados)."""
    limit = int(limit_gb * (1 << 30))
    files = list(_files())
    total = sum(s for _p, s, _t in files)
    if total <= limit:
        return 0, 0
    freed = count = 0
    for p, s, _t in sorted(files, key=lambda f: f[2]):
        if total - freed <= limit * keep:
            break
        try:
            os.remove(p)
        except OSError:
            continue
        freed += s
        count += 1
    return freed, count


def clear():
    """Apaga o cache inteiro (Opções > Limpar cache). Devolve os bytes liberados."""
    total = size()
    for folder in FOLDERS:
        shutil.rmtree(folder, ignore_errors=True)
    return total


def human(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit in ("B", "KB") else f"{n:.1f} {unit}"
        n /= 1024

