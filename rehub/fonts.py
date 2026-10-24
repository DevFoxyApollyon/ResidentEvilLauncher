"""Fonte do título de cada jogo, parecida com a do logo da capa.

As fontes dos logos são da Capcom e não existem para baixar; aqui vão fontes livres (Google Fonts, licença OFL/Apache)
que lembram cada uma. Ficam em data/fontes e são carregadas só para o app (não instala nada no Windows).
Para trocar a de um capítulo, ponha "fonte_titulo": "<chave>" nele em games/_linha_do_tempo.json.
"""
import ctypes
import urllib.request

from PIL import ImageFont

from .franchise import FR
from .paths import DATA

FONTS = DATA / "fontes"
BASE = "https://raw.githubusercontent.com/google/fonts/main/"
FILES = {  # chave: (caminho no repositório google/fonts, como lembra o logo)
    "trajan": ("ofl/cinzel/Cinzel%5Bwght%5D.ttf", "serifa clássica dos logos de RE"),
    "gotica": ("ofl/cinzeldecorative/CinzelDecorative-Bold.ttf", "Village e Shadows of Rose"),
    "fraktur": ("ofl/unifrakturmaguntia/UnifrakturMaguntia-Book.ttf", "letra gótica"),
    "maquina": ("apache/specialelite/SpecialElite-Regular.ttf", "máquina de escrever riscada (RE7, Outbreak)"),
    "militar": ("ofl/blackopsone/BlackOpsOne-Regular.ttf", "estêncil militar (Mercenaries, ORC, Umbrella Corps)"),
    "condensada": ("ofl/oswald/Oswald%5Bwght%5D.ttf", "sem serifa forte (RE5, RE6, Resistance)"),
    "elegante": ("ofl/marcellus/Marcellus-Regular.ttf", "serifa fina (Revelations)"),
    "requiem": ("ofl/cormorantgaramond/CormorantGaramond%5Bwght%5D.ttf", "serifa alta e fina (Requiem)"),
    "script": ("ofl/pinyonscript/PinyonScript-Regular.ttf", "letra cursiva (Code: Veronica)"),
    "pixel": ("ofl/pressstart2p/PressStart2P-Regular.ttf", "pixel (Game Boy, celular)"),
    "cartaz": ("ofl/bebasneue/BebasNeue-Regular.ttf", "cartaz de cinema"),
    "bloco": ("ofl/bungee/Bungee-Regular.ttf", "letras em bloco (Re:Verse)"),
    "gibi": ("ofl/bangers/Bangers-Regular.ttf", "letra de gibi (HQs)"),
    "terror": ("ofl/creepster/Creepster-Regular.ttf", "letra escorrendo (fãs)"),
}
CHAPTERS = {
    "re0": "trajan", "re1": "trajan", "re2": "trajan", "re3": "trajan", "re4": "trajan",
    "outbreak": "maquina", "veronica": "script", "darkside_chronicles": "trajan", "umbrella_chronicles": "trajan",
    "rev1": "elegante", "rev2": "elegante", "re5": "condensada", "re6": "condensada", "re7": "maquina",
    "village": "gotica", "shadows_of_rose": "gotica", "requiem": "requiem",
    "survivor": "cartaz", "survivor2": "script", "gaiden": "pixel", "dead_aim": "cartaz", "mercenaries3d": "militar",
    "orc": "militar", "umbrella_corps": "militar", "resistance": "condensada", "reverse": "bloco",
    "survival_unit": "condensada", "outros_jogos": "pixel", "re_gbc": "pixel", "re_dash": "maquina",
}
SECTIONS = {"perdidos": "maquina", "midia": "cartaz", "hqs": "gibi", "fas": "terror", "noticias": "condensada", "canais": "condensada"}
FR_PRIVATE = 0x10
_loaded = {}  # chave: (arquivo, nome da família) ou None


def key_for(chapter):
    return chapter.get("fonte_titulo") or FR["fontes"].get(chapter["id"]) or CHAPTERS.get(chapter["id"]) or SECTIONS.get(chapter.get("secao"))


def ensure(key):
    """Baixa (uma vez) e registra a fonte. Devolve (arquivo, família) ou None se não der."""
    if key in _loaded:
        return _loaded[key]
    _loaded[key] = None
    if key not in FILES:
        return None
    path = FONTS / FILES[key][0].rsplit("/", 1)[1].replace("%5B", "[").replace("%5D", "]")
    try:
        if not path.exists():
            FONTS.mkdir(parents=True, exist_ok=True)
            req = urllib.request.Request(BASE + FILES[key][0], headers={"User-Agent": "RE-Hub"})
            data = urllib.request.urlopen(req, timeout=15).read()
            path.write_bytes(data)
        family = ImageFont.truetype(str(path), 20).getname()[0]
        ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0)
        _loaded[key] = (str(path), family)
    except (OSError, ValueError, AttributeError):
        pass
    return _loaded[key]


def ensure_all():
    for k in FILES:
        ensure(k)
