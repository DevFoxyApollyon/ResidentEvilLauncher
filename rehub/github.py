"""Baixa releases do GitHub e extrai .zip com segurança."""
import fnmatch
import json
import os
import subprocess
import shutil
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

HEADERS = {"User-Agent": "RE-Hub"}

# Pastas que pertencem à raiz do jogo: um zip com só uma delas não é "desembrulhado".
ROOT_FOLDERS = {"natives", "reframework", "nativepc", "data", "usa", "jpn", "dc", "save", "bin"}


def _open(url, timeout=30):
    return urllib.request.urlopen(urllib.request.Request(url, headers=HEADERS), timeout=timeout)


def copy_progress(r, f, progress=None, cancelled=lambda: False):
    """Copia a resposta para f em blocos e chama progress(feito, total, bytes/s, segundos restantes) ~4x por segundo."""
    total = int(r.headers.get("Content-Length") or 0)
    done, start, last = 0, time.monotonic(), 0.0
    while True:
        if cancelled():
            raise RuntimeError("Download cancelado.")
        chunk = r.read(1 << 20)
        if not chunk:
            break
        f.write(chunk)
        done += len(chunk)
        now = time.monotonic()
        if progress and (now - last >= 0.25 or done == total):
            last = now
            speed = done / max(now - start, 1e-6)
            progress(done, total, speed, (total - done) / speed if total and speed else None)


def latest_release(repo):
    """A release estavel mais nova; projetos que so publicam pre-releases (alfas) usam a mais nova delas."""
    import urllib.error
    try:
        with _open(f"https://api.github.com/repos/{repo}/releases/latest") as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code != 404:
            raise
    with _open(f"https://api.github.com/repos/{repo}/releases?per_page=5") as r:
        releases = [x for x in json.load(r) if not x.get("draft")]
    if not releases:
        raise RuntimeError(f"{repo} ainda nao tem nenhuma release para baixar.")
    return releases[0]


def download_release(repo, pattern, dest, merge=False, progress=None, cancelled=lambda: False):
    """Baixa o asset da última release que casa com `pattern` (ex.: '*windows*.zip').

    merge=False: dest vira exatamente o conteúdo do zip.
    merge=True: copia por cima de dest, sem apagar o que já existe (saves, assets do usuário).
    Retorna a tag da release.
    """
    release = latest_release(repo)
    pattern = (pattern or "*.zip").lower()
    asset = next((a for a in release.get("assets", []) if fnmatch.fnmatch(a["name"].lower(), pattern)), None)
    if not asset:
        raise RuntimeError(f"Nenhum arquivo '{pattern}' na última release de {repo}.")
    if not asset["name"].lower().endswith(".zip"):
        raise RuntimeError(f"{asset['name']} não é .zip; baixe manualmente pelo GitHub.")

    with tempfile.TemporaryDirectory() as tmp:
        zip_path = Path(tmp) / asset["name"]
        with _open(asset["browser_download_url"], timeout=300) as r, open(zip_path, "wb") as f:
            copy_progress(r, f, progress, cancelled)
        if merge:
            staged = Path(tmp) / "staged"
            extract_zip(zip_path, staged)
            shutil.copytree(staged, dest, dirs_exist_ok=True)
        else:
            extract_zip(zip_path, dest)
    return release.get("tag_name", "?")


def download_asset(repo, pattern, dest_dir, progress=None, cancelled=lambda: False):
    """Baixa so o arquivo da release (ex.: o instalador .exe de um projeto) para dest_dir. Devolve (tag, caminho)."""
    release = latest_release(repo)
    asset = next((a for a in release.get("assets", []) if fnmatch.fnmatch(a["name"].lower(), pattern.lower())), None)
    if not asset:
        raise RuntimeError(f"Nenhum arquivo '{pattern}' na ultima release de {repo}.")
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    path = dest_dir / asset["name"]
    with _open(asset["browser_download_url"], timeout=600) as r, open(path, "wb") as f:
        copy_progress(r, f, progress, cancelled)
    return release.get("tag_name", "?"), path


def extract_zip(zip_path, dest):
    """Extrai em dest (recriando a pasta) e recusa zips que tentam escrever fora dela."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    root = dest.resolve()
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            if not (root / member).resolve().is_relative_to(root):
                raise RuntimeError(f"Arquivo suspeito no zip: {member}")
        z.extractall(dest)
    unwrap(dest)


ARCHIVES = (".zip", ".rar", ".7z")
FILETYPES = [("Mods (.zip, .rar, .7z)", "*.zip *.rar *.7z"), ("Todos os arquivos", "*.*")]


def _extractors(archive, out):
    """Comandos para abrir .rar/.7z, em ordem: o tar do próprio Windows 10/11 (libarchive, abre RAR5 e 7z),
    depois WinRAR e 7-Zip se estiverem instalados."""
    windir = os.environ.get("SystemRoot", r"C:\Windows")
    yield [str(Path(windir) / "System32" / "tar.exe"), "-xf", str(archive), "-C", str(out)]
    for base in (os.environ.get("ProgramFiles", r"C:\Program Files"), os.environ.get("ProgramFiles(x86)", "")):
        if not base:
            continue
        unrar, sevenz = Path(base) / "WinRAR" / "UnRAR.exe", Path(base) / "7-Zip" / "7z.exe"
        if unrar.exists():
            yield [str(unrar), "x", "-o+", "-y", "-p-", str(archive), str(out) + os.sep]  # -p-: nunca pedir senha
        if sevenz.exists():
            yield [str(sevenz), "x", "-y", f"-o{out}", str(archive)]


def extract_archive(path, dest):
    """Extrai .zip, .rar ou .7z em dest (recriando a pasta), recusando arquivos que caiam fora dela."""
    path = Path(path)
    if path.suffix.lower() == ".zip":
        return extract_zip(path, dest)
    if path.suffix.lower() not in ARCHIVES:
        raise RuntimeError(f"{path.name}: use .zip, .rar ou .7z.")
    dest = Path(dest)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "x"
        errors = []
        for cmd in _extractors(path, out):
            shutil.rmtree(out, ignore_errors=True)
            out.mkdir()
            try:  # stdin fechado e tempo limite: nada fica esperando resposta escondido
                r = subprocess.run(cmd, capture_output=True, stdin=subprocess.DEVNULL, timeout=600,
                                   creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            except (OSError, subprocess.TimeoutExpired) as e:
                errors.append(str(e)[:200])
                continue
            if r.returncode == 0 and any(out.iterdir()):
                break
            errors.append((r.stderr or r.stdout or b"").decode(errors="ignore").strip()[:200])
        else:
            raise RuntimeError(f"Não consegui abrir {path.name}. Se for um .rar protegido por senha ou de versão "
                               "muito nova, extraia com o WinRAR e use + Pasta.\n" + (errors[-1] if errors else ""))
        root = out.resolve()
        for p in out.rglob("*"):  # nada de links ou caminhos que escapem da pasta
            if p.is_symlink() or not p.resolve().is_relative_to(root):
                raise RuntimeError(f"Arquivo suspeito em {path.name}: {p.name}")
        if dest.exists():
            shutil.rmtree(dest)
        shutil.move(str(out), str(dest))
    unwrap(dest)


def unwrap(folder):
    """Se tudo estiver dentro de uma única subpasta (ex.: MeuMod-v2/), sobe o conteúdo um nível."""
    folder = Path(folder)
    items = list(folder.iterdir())
    if len(items) == 1 and items[0].is_dir() and items[0].name.lower() not in ROOT_FOLDERS:
        tmp = folder.with_name(folder.name + "__unwrap")
        items[0].rename(tmp)
        folder.rmdir()
        tmp.rename(folder)
