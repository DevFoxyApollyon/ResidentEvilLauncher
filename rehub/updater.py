"""Atualização do próprio launcher pelas releases do GitHub (franquia.json > "repositorio").

Uma vez por dia o hub compara a versão instalada com a última release. Se houver uma nova, baixa o instalador,
confere o SHA-256 publicado pelo GitHub e abre o instalador em modo automático: ele fecha o launcher, troca os
arquivos (data/ fica) e abre a versão nova.
"""
import fnmatch
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from . import github
from .franchise import FR
from .paths import ROOT

ASSET = "*Instalar*.exe"   # o instalador na release ("RE.Launcher.-.Instalar.exe")
REG = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\REHub"


def parse(version):
    """'v1.8.4' -> (1, 8, 4). Partes que não são número viram 0 (comparação segura)."""
    return tuple(int(p) if p.isdigit() else 0 for p in re.findall(r"\d+|[a-z]+", str(version).lower().lstrip("v")))


def newer(remote, local):
    return parse(remote) > parse(local)


def current():
    """Versão instalada: o arquivo VERSION ao lado do .exe (o instalador grava) ou o registro do Windows.
    None rodando pelo código (não há o que atualizar)."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        return (ROOT / "VERSION").read_text(encoding="utf-8").strip() or None
    except OSError:
        pass
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG) as k:
            return winreg.QueryValueEx(k, "DisplayVersion")[0]
    except OSError:
        return None


def check():
    """{"versao", "notas", "url", "digest", "nome", "pagina"} da última release se for mais nova que a instalada,
    senão None. Levanta erro sem internet."""
    local = current()
    rel = github.latest_release(FR["repositorio"])
    tag = rel.get("tag_name", "")
    if not local or not newer(tag, local):
        return None
    asset = next((a for a in rel.get("assets", []) if fnmatch.fnmatch(a["name"], ASSET)), None)
    if not asset:
        return None
    return {"versao": tag.lstrip("v"), "notas": (rel.get("body") or "").strip(), "url": asset["browser_download_url"],
            "digest": asset.get("digest"), "nome": asset["name"], "pagina": rel.get("html_url", "")}


def download(info, progress=None, cancelled=lambda: False):
    """Baixa o instalador para a pasta temporária e confere o hash. Devolve o caminho."""
    folder = Path(tempfile.gettempdir()) / "re_launcher_update"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / info["nome"]
    with github._open(info["url"], timeout=600) as r, open(path, "wb") as f:
        github.copy_progress(r, f, progress, cancelled)
    if not github.check_digest(path, info.get("digest")):
        raise RuntimeError("A release não informa o SHA-256 do instalador: baixe pela página do GitHub.")
    return path


def run_installer(path):
    """Abre o instalador em modo automático na pasta atual (ele fecha o launcher e abre o novo quando terminar)."""
    subprocess.Popen([str(path), "--auto", "--dir", str(ROOT)], cwd=str(Path(path).parent),
                     creationflags=getattr(subprocess, "DETACHED_PROCESS", 0))
