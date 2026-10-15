"""Gerenciador de mods.

Cada mod fica guardado em data/mods/<jogo>/<mod>/files/ com a mesma estrutura da pasta do jogo.
Ativar copia os arquivos para a pasta do jogo e guarda backup do que foi sobrescrito;
desativar apaga o que foi copiado e devolve os originais. Assim nada se perde.
"""
import json
import re
import shutil
import time
from pathlib import Path

from . import github
from .paths import MODS


class ModConflict(Exception):
    pass


# categoria: palavras no nome ou nos arquivos do mod que indicam o que ele altera
CATEGORIES = {
    "Base": ("reframework", "dinput8", "fluffy", "modmanager", "loader", "asi", "classic rebirth", "ddraw"),
    "Idioma": ("pt-br", "ptbr", "portugu", "tradu", "translat", "idioma", "language", "dublag", "legenda", "subtitle"),
    "Personagem": ("outfit", "costume", "roupa", "skin", "leon", "ada", "jill", "claire", "ashley", "chris", "wesker",
                   "rebecca", "ethan", "mia", "dimitrescu", "luis", "krauser", "player", "character", "personagem"),
    "Textura": ("texture", "textura", "retex", "4k", "8k", "hd ", " hd", "upscale", "ai upscale"),
    "Gráficos": ("reshade", "light", "luz", "graphic", "fov", "sharp", "dlss", "fsr", "ray", "shadow", "fog", "enhance"),
    "Áudio": ("sound", "audio", "music", "musica", "voice", "voz", "ost"),
    "Interface": ("ui", "hud", "menu", "font", "crosshair", "mira", "icon", "prompt"),
    "Gameplay": ("weapon", "arma", "gun", "ammo", "difficulty", "dificuldade", "inventory", "inventario", "cheat",
                 "trainer", "infinite", "enemy", "inimigo", "randomizer", "rebalance", "camera", "dodge", "vr"),
}
CATEGORY_ORDER = list(CATEGORIES) + ["Outros"]


def pretty_version(tag):
    """'nightly-01432-d052e8f...' vira 'nightly 01432'; o resto fica como está."""
    tag = tag or ""
    if tag.startswith("nightly-"):
        return "nightly " + tag.split("-")[1]
    return tag


def guess_category(name, files=()):
    """Adivinha pelo nome do mod e, se não der, pelos nomes dos arquivos."""
    for text in (name.lower(), " ".join(files).lower()):
        for cat, words in CATEGORIES.items():
            if any(w in text for w in words):
                return cat
    return "Outros"


# mods que dá para reconhecer na pasta do jogo mesmo instalados fora do app
KNOWN = {"reframework": {"nome": "REFramework", "arquivos": ("dinput8.dll",), "pasta": "reframework",
                         "versao": "reframework_revision.txt"}}

class ModManager:
    def __init__(self, game_id, game_dir):
        self.base = MODS / game_id
        self.game_dir = Path(game_dir) if game_dir else None
        self.state_file = self.base / "state.json"
        try:
            self.state = json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            self.state = {"ativos": {}}

    # ---------- biblioteca ----------
    def mods(self):
        out = []
        if self.base.exists():
            for d in sorted(self.base.iterdir()):
                meta = d / "mod.json"
                if d.is_dir() and meta.exists():
                    info = json.loads(meta.read_text(encoding="utf-8"))
                    info["id"] = d.name
                    info["ativo"] = d.name in self.state["ativos"]
                    files = self._files(d.name)
                    info["arquivos"] = len(files)
                    info.setdefault("categoria", guess_category(info.get("nome", d.name), files))
                    out.append(info)
        return out

    def add_archive(self, path):
        """Adiciona um mod em .zip, .rar ou .7z."""
        p = Path(path)
        return self._store(p.stem, str(p), lambda d: github.extract_archive(p, d))

    add_zip = add_archive

    def add_folder(self, folder):
        p = Path(folder)

        def fill(d):
            shutil.copytree(p, d)
            github.unwrap(d)
        return self._store(p.name, str(p), fill)

    def add_github(self, nome, repo, asset, mod_id):
        """Baixa (ou atualiza) um mod de uma release do GitHub."""
        return self._store(nome, f"github.com/{repo}",
                           lambda d: github.download_release(repo, asset, d), mod_id=mod_id)

    def set_category(self, mod_id, categoria):
        meta = self.base / mod_id / "mod.json"
        info = json.loads(meta.read_text(encoding="utf-8"))
        info["categoria"] = categoria
        meta.write_text(json.dumps(info, indent=2, ensure_ascii=False), encoding="utf-8")

    def folder(self, mod_id):
        """Onde o mod está: no jogo (se ativo e tiver pasta própria) ou na biblioteca."""
        k = KNOWN.get(mod_id)
        if mod_id in self.state["ativos"] and k and self.game_dir and (self.game_dir / k["pasta"]).is_dir():
            return self.game_dir / k["pasta"]
        return self.base / mod_id / "files"

    # ---------- mods instalados fora do app ----------
    def external(self):
        """Mods conhecidos (ex.: REFramework) que estão na pasta do jogo mas não foram ativados pelo app."""
        out = []
        if not self.game_dir or not self.game_dir.is_dir():
            return out
        for mod_id, k in KNOWN.items():
            if mod_id in self.state["ativos"]:
                continue
            if all((self.game_dir / f).exists() for f in k["arquivos"]):
                rev = self.game_dir / k["versao"]
                out.append({"id": mod_id, "nome": k["nome"], "fora": True,
                            "revisao": rev.read_text(errors="ignore").strip()[:12] if rev.exists() else ""})
        return out

    def uninstall_external(self, mod_id):
        """Tira da pasta do jogo um mod instalado fora do app. Guarda os arquivos em _removidos (dá para voltar)
        e mantém a pasta de configurações (ex.: reframework/), que não atrapalha o jogo."""
        k = KNOWN[mod_id]
        keep = self.base / "_removidos" / f"{mod_id}-{time.strftime('%Y%m%d-%H%M%S')}"
        keep.mkdir(parents=True, exist_ok=True)
        for f in (*k["arquivos"], k["versao"]):
            src = self.game_dir / f
            if src.exists():
                shutil.move(str(src), str(keep / f))
        return keep

    def revision(self, mod_id):
        """Revisão do mod guardado na biblioteca (para comparar com o que está no jogo)."""
        k = KNOWN.get(mod_id)
        rev = self.base / mod_id / "files" / k["versao"] if k else None
        return rev.read_text(errors="ignore").strip()[:12] if rev and rev.exists() else ""

    def remove(self, mod_id):
        self.disable(mod_id)
        shutil.rmtree(self.base / mod_id, ignore_errors=True)

    def _store(self, nome, origem, fill, mod_id=None):
        """fill(pasta) preenche os arquivos do mod e pode devolver a versão."""
        mod_id = mod_id or self._free_id(nome)
        was_active = mod_id in self.state["ativos"]
        if was_active:
            self.disable(mod_id)
        slot = self.base / mod_id
        try:  # atualizando: mantém a categoria que o usuário escolheu
            old_cat = json.loads((slot / "mod.json").read_text(encoding="utf-8")).get("categoria")
        except (OSError, ValueError):
            old_cat = None
        shutil.rmtree(slot, ignore_errors=True)
        slot.mkdir(parents=True)
        try:
            versao = fill(slot / "files") or ""
        except Exception:
            shutil.rmtree(slot, ignore_errors=True)
            raise
        meta = {"nome": nome, "origem": origem, "versao": versao,
                "categoria": old_cat or guess_category(nome, self._files(mod_id))}
        (slot / "mod.json").write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        if was_active:
            self.enable(mod_id)
        return mod_id

    def _free_id(self, nome):
        slug = re.sub(r"[^a-z0-9]+", "-", nome.lower()).strip("-") or "mod"
        mod_id, n = slug, 2
        while (self.base / mod_id).exists():
            mod_id, n = f"{slug}-{n}", n + 1
        return mod_id

    def _files(self, mod_id):
        root = self.base / mod_id / "files"
        return [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file()] if root.exists() else []

    # ---------- ativar / desativar ----------
    def enable(self, mod_id):
        if mod_id in self.state["ativos"]:
            return
        if not self.game_dir or not self.game_dir.is_dir():
            raise RuntimeError("A pasta do jogo não foi encontrada. Instale ou configure o jogo antes de ativar mods.")

        files = self._files(mod_id)
        owners = {f.lower(): mid for mid, info in self.state["ativos"].items() for f in info["arquivos"]}
        clash = sorted({owners[f.lower()] for f in files if f.lower() in owners})
        if clash:
            raise ModConflict("Esse mod mexe nos mesmos arquivos de: " + ", ".join(clash) + ".\nDesative-os primeiro.")

        src, backup = self.base / mod_id / "files", self._backup_dir(mod_id)
        copied, backups, created = [], [], []
        try:
            for rel in files:
                dest = self.game_dir / rel
                if dest.exists():
                    (backup / rel).parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(dest, backup / rel)
                    backups.append(rel)
                created += self._make_dirs(dest.parent)
                shutil.copy2(src / rel, dest)
                copied.append(rel)
        except OSError:
            self._undo(mod_id, copied, backups, created)  # deixa o jogo como estava
            raise
        self.state["ativos"][mod_id] = {"arquivos": copied, "backups": backups, "pastas": created}
        self._save()

    def disable(self, mod_id):
        info = self.state["ativos"].pop(mod_id, None)
        if info:
            self._undo(mod_id, info["arquivos"], info["backups"], info.get("pastas", []))
            self._save()

    def _make_dirs(self, folder):
        """Cria a pasta e devolve (relativas ao jogo) as que não existiam antes."""
        missing = []
        while not folder.exists():
            missing.append(folder.relative_to(self.game_dir).as_posix())
            folder = folder.parent
        if missing:
            (self.game_dir / missing[0]).mkdir(parents=True)
        return missing

    def _undo(self, mod_id, files, backups, created):
        if self.game_dir:
            for rel in files:
                (self.game_dir / rel).unlink(missing_ok=True)
            backup = self._backup_dir(mod_id)
            for rel in backups:
                shutil.copy2(backup / rel, self.game_dir / rel)
            # só apaga pastas que o próprio mod criou, das mais fundas para as de cima, e se ficaram vazias
            for rel in sorted(created, key=lambda p: -p.count("/")):
                d = self.game_dir / rel
                if d.is_dir() and not any(d.iterdir()):
                    d.rmdir()
        shutil.rmtree(self._backup_dir(mod_id), ignore_errors=True)

    def _backup_dir(self, mod_id):
        return self.base / "_backup" / mod_id

    def _save(self):
        self.base.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(self.state, indent=2, ensure_ascii=False), encoding="utf-8")
