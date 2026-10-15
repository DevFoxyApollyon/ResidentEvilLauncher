"""Monta um hub de outra franquia (ex.: Silent Hill) numa pasta nova, usando o mesmo .exe.

Uso: python tools/nova_franquia.py silent_hill "C:/Users/voce/Documents/SH Hub"

Copia: o .exe, o franquia.json de modelos/<franquia>/, as ferramentas (ffmpeg), as fontes e os sons do PS5.
Cria um catálogo vazio (games/_linha_do_tempo.json) pronto para receber os jogos.
Nada desta pasta é alterado.
"""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EMPTY = {"_comentario": "Capítulos em ordem da história ('capitulos'), spin-offs ('nao_canonicos'), perdidos, mídia, "
                        "HQs e fãs. Cada jogo em games/*.json aponta para um capítulo pelo campo 'capitulo'.",
         "capitulos": [], "nao_canonicos": [], "perdidos": [], "midia": [], "hqs": [], "fas": []}


def main(franquia, dest):
    model = ROOT / "modelos" / franquia / "franquia.json"
    if not model.exists():
        sys.exit(f"Não achei {model}")
    dest = Path(dest)
    if (dest / "games").exists():
        sys.exit(f"{dest} já tem um catálogo; escolha outra pasta.")
    cfg = json.loads(model.read_text(encoding="utf-8"))
    (dest / "games").mkdir(parents=True)
    (dest / "games" / "_linha_do_tempo.json").write_text(json.dumps(EMPTY, ensure_ascii=False, indent=2), encoding="utf-8")
    shutil.copy2(model, dest / "franquia.json")
    for item in ("RE Hub.exe", "_internal"):  # o mesmo programa; o nome do arquivo não importa
        src = ROOT / item
        if src.is_dir():
            shutil.copytree(src, dest / item, dirs_exist_ok=True)
        elif src.exists():
            shutil.copy2(src, dest / f"{cfg['app']}.exe")
    for sub in ("ferramentas", "fontes", "sons/ps5"):
        if (ROOT / "data" / sub).exists():
            shutil.copytree(ROOT / "data" / sub, dest / "data" / sub, dirs_exist_ok=True)
    for ext in ("ico", "png"):  # ícone: use um próprio se houver em modelos/<franquia>/
        own = ROOT / "modelos" / franquia / f"{cfg['icone']}.{ext}"
        if own.exists():
            shutil.copy2(own, dest / own.name)
    print(f"{cfg['app']} criado em {dest}. Agora é só preencher games/ com os jogos.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
