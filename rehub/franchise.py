"""Identidade da franquia: tudo que muda de um hub para outro (Resident Evil, Silent Hill...).

Fica em franquia.json, ao lado do .exe. O código é o mesmo para todas: um hub novo é uma pasta com o .exe,
um franquia.json, o catálogo (games/) e os dados (data/). Veja tools/nova_franquia.py.
"""
import json

from .paths import ROOT

DEFAULTS = {
    "id": "resident_evil",
    "nome": "Resident Evil",
    "app": "RE Hub",
    "cor": "#d1121b",                 # cor de destaque padrão (botões, carimbos, barra de progresso)
    "logo_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/0/0a/The_Resident_Evil_logo.svg/"
                "960px-The_Resident_Evil_logo.svg.png",
    "logo_cor": [214, 20, 30],        # o logo da série é pintado nessa cor no topo
    "simbolo": "umbrella",            # desenho da tela de carregamento: "umbrella", "halo" ou um .png ao lado do .exe
    "icone": "re_hub",                # re_hub.ico / re_hub.png ao lado do .exe
    "prefixo_titulo": "Resident Evil",  # tirado do nome nas capas geradas ("Resident Evil 2" vira "2")
    "wiki_referer": "https://residentevil.fandom.com/",
    "mensagens": ["Iniciando sistema Umbrella...", "Carregando arquivos dos S.T.A.R.S....",
                  "Lendo a biblioteca da Steam...", "Preparando a linha do tempo...", "Abrindo a mansão Spencer..."],
    "noticias": {"feed": "https://residentevil.com.br/feed/", "fonte": "REVIL", "site": "residentevil.com.br"},
    "fontes": {},                     # capítulo -> fonte do título (chaves em rehub/fonts.py)
    "temas": {},                      # clima do tema composto -> lista de capítulos (rehub/compose.py)
    "rotulo_criaturas": "Armas biológicas",  # nome do filtro de criaturas na tela Personagens
}


def load():
    try:
        data = json.loads((ROOT / "franquia.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        data = {}
    return {**DEFAULTS, **data}


FR = load()


def hex_rgb(color):
    color = color.lstrip("#")
    return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))
