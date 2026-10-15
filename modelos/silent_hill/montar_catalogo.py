"""Monta o catálogo do SH Hub (games/_linha_do_tempo.json e games/*.json) numa pasta criada por tools/nova_franquia.py.

Uso: python modelos/silent_hill/montar_catalogo.py "C:/Users/<você>/Documents/SH Hub"

Fontes conferidas em out/2026: Steam (appids e datas), Wikipedia (anos e plataformas), Silent Hill Wiki (capas),
libretro-thumbnails (capas de caixa dos clássicos). Pode rodar de novo: reescreve o catálogo inteiro.
"""
import json
import sys
import urllib.parse
from pathlib import Path

LIB = "https://raw.githubusercontent.com/libretro-thumbnails/"
WIKI = "https://static.wikia.nocookie.net/silent/images/"
F_LIB, F_WIKI = "capa: libretro-thumbnails", "imagem: Silent Hill Wiki (fãs)"


def lib(system, name, kind="Named_Boxarts"):
    return f"{LIB}{system}/master/{kind}/{urllib.parse.quote(name)}.png"


def wiki(path):
    return WIKI + path


def page(title):
    return {"nome": "Silent Hill Wiki", "url": "https://silenthill.fandom.com/wiki/" + urllib.parse.quote(title.replace(" ", "_"))}


def yt(q):
    return {"nome": "Procurar no YouTube", "url": "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q)}


def lanc(nome, ano, plat, onde):
    return {"nome": nome, "ano": ano, "plataformas": plat, "onde": onde}


# ---------- capítulos da história (ordem aproximada da história; os jogos de outras cidades vêm no fim) ----------
capitulos = [
    {"id": "origins", "titulo": "Silent Hill: Origins", "quando": "Prólogo · 7 anos antes do primeiro jogo",
     "onde": "Silent Hill", "lancamento": 2007,
     "sinopse": "O caminhoneiro Travis Grady pega um atalho por Silent Hill, tira uma menina de uma casa em chamas e "
                "acaba preso na cidade. É o começo da história de Alessa e do culto que move a série.",
     "lancamentos": [lanc("Silent Hill: Origins", 2007, "PSP", "Emulador (PPSSPP)"),
                     lanc("Silent Hill: Origins (PS2)", 2008, "PlayStation 2", "Emulador (PCSX2)")],
     "trilha_busca": ["silent hill origins"]},
    {"id": "sh1", "titulo": "Silent Hill", "quando": "Início · a primeira visita de Harry",
     "onde": "Silent Hill", "lancamento": 1999,
     "sinopse": "Harry Mason sofre um acidente de carro na entrada de Silent Hill e acorda sem a filha Cheryl. "
                "Procurando por ela numa cidade coberta de névoa, ele descobre um culto e um mundo que vira pesadelo "
                "quando a sirene toca.",
     "lancamentos": [lanc("Silent Hill", 1999, "PlayStation", "Emulador (DuckStation)"),
                     lanc("Silent Hill (PSN)", 2009, "PS3, PSP", "PlayStation Store da época (fora de venda)"),
                     lanc("Play Novel: Silent Hill", 2001, "Game Boy Advance (só no Japão)", "Emulador (mGBA)"),
                     lanc("Silent Hill: Shattered Memories (reimaginação)", 2009, "Wii · PS2 e PSP em 2010",
                          "Emulador (Dolphin, PCSX2 ou PPSSPP)"),
                     lanc("Silent Hill (remake, Bloober Team)", "—", "Anunciado em 2025", "Ainda sem data")],
     "trilha_busca": ["silent hill"]},
    {"id": "sh2", "titulo": "Silent Hill 2", "quando": "Depois · a carta de Mary",
     "onde": "Silent Hill, Toluca Lake", "lancamento": 2001,
     "sinopse": "James Sunderland recebe uma carta da esposa Mary, morta há três anos, chamando-o para o \"lugar "
                "especial\" deles em Silent Hill. A cidade que ele encontra parece feita da própria culpa.",
     "lancamentos": [lanc("Silent Hill 2", 2001, "PlayStation 2", "Emulador (PCSX2)"),
                     lanc("Restless Dreams", 2001, "Xbox", "Emulador (xemu)"),
                     lanc("Director's Cut (PC)", 2003, "PC", "Cópia original + Enhanced Edition (fãs)"),
                     lanc("Silent Hill HD Collection", 2012, "PS3, Xbox 360", "Consoles da época"),
                     lanc("Silent Hill 2 (remake)", 2024, "PS5, PC", "Steam, PS Store")],
     "trilha_busca": ["silent hill 2"]},
    {"id": "sh3", "titulo": "Silent Hill 3", "quando": "Retorno · 17 anos depois do primeiro jogo",
     "onde": "Shopping, Silent Hill", "lancamento": 2003,
     "sinopse": "Heather Mason, uma adolescente comum, vê o shopping em que está se transformar num pesadelo. "
                "Perseguida pelo culto, ela descobre que seu passado está ligado à cidade e ao primeiro jogo.",
     "lancamentos": [lanc("Silent Hill 3", 2003, "PlayStation 2", "Emulador (PCSX2)"),
                     lanc("Silent Hill 3 (PC)", 2003, "PC", "Cópia original"),
                     lanc("Silent Hill HD Collection", 2012, "PS3, Xbox 360", "Consoles da época")],
     "trilha_busca": ["silent hill 3"]},
    {"id": "sh4", "titulo": "Silent Hill 4: The Room", "quando": "Apartamento 302 · South Ashfield",
     "onde": "South Ashfield", "lancamento": 2004,
     "sinopse": "Henry Townshend acorda trancado no próprio apartamento, com correntes na porta por dentro. O único "
                "jeito de sair é um buraco no banheiro que leva a mundos ligados a um assassino em série.",
     "lancamentos": [lanc("Silent Hill 4: The Room", 2004, "PS2, Xbox, PC", "Emulador (PCSX2) ou PC"),
                     lanc("Silent Hill 4 (GOG)", 2020, "PC", "GOG")],
     "trilha_busca": ["silent hill 4"]},
    {"id": "homecoming", "titulo": "Silent Hill: Homecoming", "quando": "Volta para casa · Shepherd's Glen",
     "onde": "Shepherd's Glen e Silent Hill", "lancamento": 2008,
     "sinopse": "O soldado Alex Shepherd volta para a cidade natal para procurar o irmão desaparecido e encontra "
                "Shepherd's Glen vazia, envolvida pela mesma névoa de Silent Hill.",
     "lancamentos": [lanc("Silent Hill: Homecoming", 2008, "PS3, Xbox 360", "Consoles da época"),
                     lanc("Silent Hill: Homecoming (PC)", 2009, "PC", "Steam")],
     "trilha_busca": ["silent hill homecoming"]},
    {"id": "downpour", "titulo": "Silent Hill: Downpour", "quando": "Transferência de presos · chuva",
     "onde": "Arredores de Silent Hill", "lancamento": 2012,
     "sinopse": "O ônibus que leva o presidiário Murphy Pendleton sai da estrada perto de Silent Hill. Livre, ele "
                "atravessa a cidade enquanto a chuva traz o Outro Mundo e o passado que o levou à prisão.",
     "lancamentos": [lanc("Silent Hill: Downpour", 2012, "PS3, Xbox 360", "Consoles da época")],
     "trilha_busca": ["silent hill downpour"]},
    {"id": "short_message", "titulo": "Silent Hill: The Short Message", "quando": "Agora · Kettenstadt",
     "onde": "Kettenstadt, Alemanha", "lancamento": 2024,
     "sinopse": "Jogo curto e gratuito em primeira pessoa: a jovem Anita recebe uma mensagem da amiga Maya, artista de "
                "rua, e vai até um prédio abandonado em Kettenstadt, na Alemanha.",
     "lancamentos": [lanc("Silent Hill: The Short Message", 2024, "PS5", "PS Store (grátis)")],
     "trilha_busca": ["short message"]},
    {"id": "f", "titulo": "Silent Hill f", "quando": "Japão · anos 1960",
     "onde": "Ebisugaoka, Japão", "lancamento": 2025,
     "sinopse": "Uma névoa envolve a cidade natal de Hinako, levando-a a lutar contra monstros e resolver "
                "quebra-cabeças sinistros. Primeiro Silent Hill no Japão, com roteiro de Ryukishi07.",
     "lancamentos": [lanc("Silent Hill f", 2025, "PC, PS5, Xbox Series X|S", "Steam, PS Store, Xbox")],
     "trilha_busca": ["silent hill f"]},
    {"id": "townfall", "titulo": "Silent Hill: Townfall", "quando": "1996 · ilha de St. Amelia",
     "onde": "St. Amelia, ilha fictícia da Escócia", "lancamento": 2026,
     "sinopse": "Simon Ordell é chamado de volta à ilha de St. Amelia para \"acertar as coisas\" e encontra uma cidade "
                "quieta sob a névoa. Em primeira pessoa, com uma TV de bolso (CRTV) que sintoniza sinais instáveis. "
                "Feito pela Screen Burn, de Glasgow, com a Annapurna.",
     "lancamentos": [lanc("Silent Hill: Townfall", 2026, "PC, PS5", "Steam, PS Store")],
     "trilha_busca": ["townfall"]},
]

nao_canonicos = [
    {"id": "arcade", "titulo": "Silent Hill: The Arcade", "quando": "Fora da história", "onde": "Fliperamas",
     "lancamento": 2007, "formato": "Arcade · tiro com pistola de luz",
     "sinopse": "Jogo de tiro sobre trilhos para dois jogadores, feito para fliperamas e lançado só nas máquinas.",
     "lancamentos": [lanc("Silent Hill: The Arcade", 2007, "Arcade", "Só nas máquinas (nunca saiu em casa)")],
     "arte": {"capa": [wiki("b/b4/Arcade_title.png/revision/latest?cb=20140218071224")], "fonte": F_WIKI},
     "links": [page("Silent Hill: The Arcade")]},
    {"id": "book_of_memories", "titulo": "Silent Hill: Book of Memories", "quando": "Fora da história",
     "onde": "Um livro que reescreve o passado", "lancamento": 2012, "formato": "Ação em masmorras · PS Vita",
     "sinopse": "Spin-off com visão de cima, cooperativo, em que o jogador recebe um livro capaz de mudar a própria "
                "vida e enfrenta fases inspiradas nos jogos anteriores. Feito pela WayForward.",
     "lancamentos": [lanc("Silent Hill: Book of Memories", 2012, "PS Vita", "Emulador (Vita3K) ou console")],
     "arte": {"capa": [wiki("3/33/Bookofmemories.png/revision/latest?cb=20140809055320")], "fonte": F_WIKI},
     "links": [page("Silent Hill: Book of Memories")]},
    {"id": "shattered", "titulo": "Silent Hill: Shattered Memories", "quando": "Reimaginação do primeiro jogo",
     "onde": "Silent Hill gelada", "lancamento": 2009, "formato": "Wii · PS2 e PSP em 2010",
     "sinopse": "Releitura do primeiro jogo com sessões de terapia que mudam a história conforme suas respostas. "
                "Harry procura Cheryl numa Silent Hill coberta de gelo, sem armas: só fugir.",
     "lancamentos": [lanc("Shattered Memories", 2009, "Wii", "Emulador (Dolphin)"),
                     lanc("Shattered Memories (PS2, PSP)", 2010, "PS2, PSP", "Emulador (PCSX2, PPSSPP)")],
     "arte": {"capa": [lib("Nintendo_-_Wii", "Silent Hill - Shattered Memories (USA) (En,Fr,Es)"),
                       wiki("c/cc/SHSMboxart.PNG/revision/latest?cb=20140810070219")], "fonte": F_LIB},
     "links": [page("Silent Hill: Shattered Memories")]},
    {"id": "play_novel", "titulo": "Play Novel: Silent Hill", "quando": "Recontagem do primeiro jogo",
     "onde": "Silent Hill", "lancamento": 2001, "formato": "Romance interativo · GBA (Japão)",
     "sinopse": "Versão em texto do primeiro jogo para Game Boy Advance, lançada só no Japão, com um cenário extra. "
                "Fãs traduziram para o inglês.",
     "lancamentos": [lanc("Play Novel: Silent Hill", 2001, "Game Boy Advance", "Emulador (mGBA) · tradução de fãs")],
     "arte": {"capa": [lib("Nintendo_-_Game_Boy_Advance", "Play Novel - Silent Hill (Japan)")], "fonte": F_LIB},
     "links": [page("Play Novel: Silent Hill")]},
    {"id": "celular", "titulo": "Jogos de celular", "quando": "Fora da história", "onde": "Celulares antigos",
     "lancamento": 2006, "formato": "Celular",
     "sinopse": "A série teve vários jogos para celulares da época, como a trilogia Orphan e The Escape (que chegou "
                "ao iPhone em 2009). Hoje estão todos fora do ar.",
     "lancamentos": [lanc("Silent Hill (celular)", 2006, "FOMA, Java", "Fora do ar"),
                     lanc("Silent Hill: Orphan", 2007, "Celular", "Fora do ar"),
                     lanc("Silent Hill: The Escape", 2007, "FOMA · iOS em 2009", "Fora do ar"),
                     lanc("Silent Hill: Orphan 2", 2008, "Celular", "Fora do ar"),
                     lanc("Silent Hill: Orphan 3", 2010, "Celular", "Fora do ar")],
     "arte": {"capa": [wiki("2/27/Sh_orphan.jpg/revision/latest?cb=20080929002828")], "fonte": F_WIKI},
     "links": [page("Silent Hill: Orphan")]},
]

perdidos = [
    {"id": "comx_hq", "titulo": "HQ da Com.X", "quando": "1999", "onde": "Quadrinho nunca publicado",
     "lancamento": 1999, "formato": "Graphic novel inédita",
     "poster": {"titulo": "A HQ PERDIDA", "subtitulo": "COM.X · 1999", "carimbo": "INÉDITA"},
     "sinopse": "Uma graphic novel de Silent Hill foi concluída pela editora Com.X em 1999, mas nunca chegou a ser "
                "publicada.", "lancamentos": [lanc("Graphic novel", 1999, "Quadrinho", "Nunca publicada")],
     "links": [{"nome": "Wikipedia", "url": "https://en.wikipedia.org/wiki/Silent_Hill_(comics)"}]},
    {"id": "broken_covenant", "titulo": "Silent Hill: Broken Covenant", "quando": "2006", "onde": "Coyote Flats, Arizona",
     "lancamento": 2006, "formato": "Proposta cancelada · PS3",
     "poster": {"titulo": "BROKEN COVENANT", "subtitulo": "PS3 · 2006", "carimbo": "CANCELADO"},
     "sinopse": "Proposta da Climax Los Angeles para o PS3: o padre Hector Santos numa cidade corrompida pelas "
                "memórias de Silent Hill. A Konami recusou duas vezes e o projeto foi abandonado; vídeos do jogo "
                "apareceram em 2016.",
     "lancamentos": [lanc("Protótipo", 2006, "PlayStation 3", "Só vídeos que vazaram em 2016")],
     "links": [page("Broken Covenant")]},
    {"id": "silent_hills", "titulo": "Silent Hills e P.T.", "quando": "2014 – 2015", "onde": "Um corredor de casa",
     "lancamento": 2014, "formato": "Jogo cancelado · PS4",
     "sinopse": "P.T. era o \"teaser jogável\" de Silent Hills, de Hideo Kojima e Guillermo del Toro, com Norman "
                "Reedus. A Konami cancelou o jogo em abril de 2015 e tirou P.T. da PlayStation Store, nem quem já "
                "tinha baixado pôde baixar de novo.",
     "lancamentos": [lanc("P.T.", 2014, "PS4", "Removido em 2015: só em consoles que ainda têm instalado"),
                     lanc("Silent Hills", 2015, "PS4", "Cancelado")],
     "arte": {"capa": [wiki("d/d9/PT_Title_Card.jpg/revision/latest?cb=20140817043109"),
                       "https://upload.wikimedia.org/wikipedia/commons/d/dc/Silent_Hills_logo.png"], "fonte": F_WIKI},
     "links": [page("Silent Hills"), page("P.T.")]},
]

midia = [
    {"id": "filme_2006", "titulo": "Terror em Silent Hill (2006)", "quando": "2006", "onde": "Filme · baseado no primeiro jogo",
     "lancamento": 2006, "formato": "Filme · Christophe Gans",
     "sinopse": "Rose leva a filha adotiva Sharon, que vive tendo pesadelos com Silent Hill, até a cidade abandonada "
                "e a perde depois de um acidente na estrada.",
     "lancamentos": [lanc("Terror em Silent Hill", 2006, "Cinema", "Streaming e mídia física")],
     "arte": {"capa": [wiki("a/ad/Silent_hill_xlg.png/revision/latest?cb=20140812040646")], "fonte": F_WIKI},
     "links": [page("Silent Hill (film)")]},
    {"id": "revelation", "titulo": "Silent Hill: Revelação (2012)", "quando": "2012", "onde": "Filme · baseado no Silent Hill 3",
     "lancamento": 2012, "formato": "Filme · M. J. Bassett",
     "sinopse": "Continuação do filme de 2006: Heather Mason, prestes a fazer 18 anos, é atraída de volta a Silent "
                "Hill quando o pai desaparece.",
     "lancamentos": [lanc("Silent Hill: Revelação", 2012, "Cinema (3D)", "Streaming e mídia física")],
     "arte": {"capa": [wiki("e/e0/Revelationposter.png/revision/latest?cb=20140812040932")], "fonte": F_WIKI},
     "links": [page("Silent Hill: Revelation")]},
    {"id": "ascension", "titulo": "Silent Hill: Ascension", "quando": "2023", "onde": "Série interativa",
     "lancamento": 2023, "formato": "Série interativa ao vivo",
     "sinopse": "Série animada transmitida pela internet em que o público votava nas decisões dos personagens. Feita "
                "pela Genvid com Bad Robot Games e Behaviour Interactive.",
     "lancamentos": [lanc("Silent Hill: Ascension", 2023, "Navegador, PC, celular", "App e site oficiais da série")],
     "arte": {"capa": [wiki("f/f0/SHAscension_Final_Poster.png/revision/latest?cb=20240606040859")], "fonte": F_WIKI},
     "links": [page("Silent Hill: Ascension")]},
    {"id": "return_2026", "titulo": "Return to Silent Hill (2026)", "quando": "2026", "onde": "Filme · baseado no Silent Hill 2",
     "lancamento": 2026, "formato": "Filme · Christophe Gans",
     "sinopse": "Christophe Gans volta à série adaptando Silent Hill 2: James volta à cidade atrás do amor perdido.",
     "lancamentos": [lanc("Return to Silent Hill", 2026, "Cinema (janeiro de 2026)", "Cinema, depois streaming")],
     "arte": {"capa": [wiki("c/c4/Return_To_Silent_Hill_%28Poster%29.webp/revision/latest?cb=20221020160104")], "fonte": F_WIKI},
     "links": [page("Return to Silent Hill")]},
]


def hq(cid, titulo, quando, ano, formato, sinopse, img=None, wiki_title=None):
    c = {"id": cid, "titulo": titulo, "quando": quando, "onde": formato, "formato": formato, "sinopse": sinopse,
         "lancamentos": [lanc(titulo, ano or "—", formato, "Edições usadas ou digitais")],
         "links": [page(wiki_title or titulo)]}
    if ano:
        c["lancamento"] = ano
    if img:
        c["arte"] = {"capa": [wiki(img)], "fonte": F_WIKI}
    return c


hqs = [
    hq("hq_dying_inside", "Dying Inside", "2004", 2004, "Minissérie IDW · 5 edições",
       "Um médico tenta curar os delírios de uma paciente e acaba preso numa cidade feita dos próprios medos. "
       "Roteiro de Scott Ciencin, arte de Ben Templesmith e Aadi Salman.",
       "c/cf/Dying_inside_tpb.jpg/revision/latest?cb=20150117044338", "Silent Hill: Dying Inside"),
    hq("hq_among_damned", "Among the Damned", "2004", 2004, "Edição única IDW",
       "História curta de Scott Ciencin com arte de Shaun Thomas.",
       "a/a9/ATD.jpg/revision/latest?cb=20150116081113"),
    hq("hq_paint_black", "Paint It Black", "2005", 2005, "Edição única IDW",
       "Os quadros de um artista sem-teto o levam a outros lugares, até que líderes de torcida o sacrificam para "
       "fugir da cidade.", "e/e2/PIBcover.jpg/revision/latest?cb=20090613210323"),
    hq("hq_grinning_man", "The Grinning Man", "2005", 2005, "Edição única IDW",
       "O último dia de um policial rodoviário vira um pesadelo quando uma brincadeira encontra um caçador sorridente.",
       "1/1a/TGMcover.jpg/revision/latest?cb=20150116081146"),
    hq("hq_dead_alive", "Dead/Alive", "2005 – 2006", 2005, "Minissérie IDW · 5 edições",
       "Uma menina demoníaca faz um pacto com uma bruxa para trazer o Inferno à Terra por meio de duas pessoas.",
       "e/e1/Silent_Hill_-_Dead-Alive_logo.png/revision/latest?cb=20181002032331", "Silent Hill: Dead/Alive"),
    hq("hq_hunger", "Hunger", "2006", 2006, "HQ digital (UMD Silent Hill Experience)",
       "Um repórter desacreditado investiga um assassinato em Silent Hill enquanto procura a noiva desaparecida.",
       None, "Silent Hill: Hunger"),
    hq("hq_sinners_reward", "Sinner's Reward", "2008", 2008, "Minissérie IDW · 4 edições",
       "Um matador de aluguel e a amante pegam o caminho errado e não conseguem sair de Silent Hill.",
       "3/37/Sinner%27s_reward_tpb.jpg/revision/latest?cb=20090511165656"),
    hq("hq_past_life", "Past Life", "2010 – 2011", 2010, "Minissérie IDW · 4 edições",
       "Um pistoleiro e a esposa, morando em Silent Hill em 1867, são assombrados pelo passado.",
       "a/af/PLCover.jpg/revision/latest?cb=20150924234741"),
    hq("hq_annes_story", "Downpour: Anne's Story", "2014", 2014, "Minissérie IDW · 4 edições",
       "A policial Anne Cunningham, do jogo Downpour, persegue o homem que culpa pela morte do pai.",
       "1/1d/AScover.jpg/revision/latest?cb=20150116081733", "Anne's Story"),
    hq("hq_cage_cradle", "Cage of Cradle", "Mangá digital", None, "Mangá",
       "Mangá digital ligado à história de Silent Hill 3.",
       "d/dc/9607580.jpg/revision/latest?cb=20180918234252", "Silent Hill: Cage of Cradle"),
    hq("livros_yamashita", "Romances de Sadamu Yamashita", "Romances", None, "Livros (Japão)",
       "Romances que recontam Silent Hill, Silent Hill 2 e Silent Hill 3, lançados no Japão.",
       "2/2d/Silent_Hill_novel_-_Slip_cover.jpg/revision/latest?cb=20170905204409", "Silent Hill (novel)"),
]


def fan(cid, titulo, categoria, sinopse, onde, links, ano=None, formato=None, img=None):
    c = {"id": cid, "titulo": titulo, "categoria": categoria, "quando": str(ano) if ano else categoria,
         "onde": formato or categoria, "formato": formato or categoria, "sinopse": sinopse,
         "lancamentos": [lanc(titulo, ano or "—", formato or categoria, onde)], "links": links}
    if ano:
        c["lancamento"] = ano
    if img:
        c["arte"] = {"capa": [img], "fonte": F_WIKI}
    return c


fas = [
    fan("fan_sh2ee", "Silent Hill 2: Enhanced Edition", "Patch",
        "Patch de fãs que moderniza o Silent Hill 2 de PC: imagem em HD, fontes novas, sombras e efeitos restaurados, "
        "widescreen e mais quadros por segundo. Depois de quase sete anos, a 10ª e última atualização saiu em 2024. "
        "Precisa da sua cópia do Director's Cut de PC (americana ou europeia).",
        "Site oficial do projeto (grátis)", [{"nome": "Site do projeto", "url": "https://enhanced.townofsilenthill.com/SH2/"},
                                            {"nome": "Notícia (Boss Rush)",
                                             "url": "https://bossrush.net/2024/08/31/silent-hill-2-enhanced-edition-a-fan-made-patch-updating-the-game-is-officially-complete"}],
        ano=2024, formato="Patch de fãs · PC"),
    fan("fan_alchemilla", "Silent Hill: Alchemilla", "Jogo de fãs",
        "Jogo de fãs feito na Source Engine, num hospital: sem armas nem monstros para lutar, só exploração, bilhetes, "
        "chaves e quebra-cabeças. Precisa do Source SDK Base 2013 Singleplayer (grátis na Steam).",
        "ModDB (grátis)", [{"nome": "Notícia (Indie Retro News)",
                           "url": "https://indieretronews.com/2015/01/alchemilla-silent-hill-style-source.html"}],
        ano=2015, formato="Jogo de fãs · Source Engine"),
    fan("fan_play_novel_tr", "Play Novel traduzido", "Tradução",
        "Fãs traduziram para o inglês o Play Novel: Silent Hill, que só saiu no Japão.",
        "Patch de tradução", [{"nome": "Notícia (Bloody Disgusting)",
                              "url": "https://bloody-disgusting.com/news/3216280/some-extremely-dedicated-fans-have-translated-the-japan-exclusive-silent-hill-play-novel/"}],
        formato="Tradução de fãs · GBA"),
    fan("fan_road_of_guilt", "Silent Hill: Road of Guilt", "Fan film",
        "Curta de Leigh Thorne e Ruben Abreu feito sem orçamento na pandemia, para os 20 anos do Silent Hill 2: James "
        "recupera gravações antigas de sessões de terapia com o Dr. Finch.",
        "Grátis no YouTube", [{"nome": "Notícia (TheGamer)",
                              "url": "https://www.thegamer.com/fan-short-silent-hill-road-of-guilt-release-20th-anniversary-silent-hill-2/"},
                             yt("Silent Hill Road of Guilt")], ano=2021, formato="Fan film · 18 min"),
    fan("fan_no_escape", "Silent Hill: No Escape", "Fan CG",
        "Filme em computação gráfica de Nick Greenlee, dividido em seis episódios.",
        "Grátis no YouTube", [{"nome": "FilmAffinity", "url": "https://www.filmaffinity.com/en/film892141.html"},
                             yt("Silent Hill No Escape Nick Greenlee")], ano=2005, formato="Fan film em CG · 6 episódios"),
    fan("fan_the_room_short", "The Room (curta de Nick Merola)", "Fan film",
        "Curta inspirado no Silent Hill 4, filmado em um dia no próprio apartamento do diretor.",
        "Grátis no YouTube", [{"nome": "Notícia (Bloody Disgusting)",
                              "url": "https://bloody-disgusting.com/movie/3811274/director-nick-merola-releases-short-film-inspired-by-silent-hill-4-the-room-video/"},
                             yt("Nick Merola Silent Hill 4 The Room short film")], formato="Fan film"),
    fan("fan_letter_to_james", "A Letter to James", "Fan film",
        "Curta baseado no Silent Hill 2 anunciado em janeiro de 2025 pelo estúdio Rebel Monkey.",
        "Teaser no YouTube", [{"nome": "Notícia (Mezha)",
                              "url": "https://mezha.ua/en/2025/01/21/ukrainian-american-studio-rebel-monkey-creates-a-short-film-based-on-silent-hill-2/"}],
        formato="Fan film · anunciado"),
]

# ---------- versões jogáveis (games/*.json) ----------
games = [
    {"id": "origins_psp", "ordem": 10, "nome": "Silent Hill: Origins", "capitulo": "origins", "versao": "PSP (emulador)",
     "tipo": "local", "args": "\"{iso}\"", "dica": "Aponte um emulador de PSP (por exemplo, o PPSSPP) e a SUA própria ISO.",
     "arte": {"capa": [lib("Sony_-_PlayStation_Portable", "Silent Hill - Origins (USA) (En,Fr,De,Es,It)")], "fonte": F_LIB}},
    {"id": "origins_ps2", "ordem": 11, "nome": "Silent Hill: Origins (PS2)", "capitulo": "origins", "versao": "PS2 (emulador)",
     "tipo": "local", "args": "\"{iso}\"", "dica": "Aponte o PCSX2 e a SUA própria ISO.",
     "arte": {"capa": [lib("Sony_-_PlayStation_2", "Silent Hill Origins (USA) (En,Fr,De,Es,It)")], "fonte": F_LIB}},
    {"id": "sh1_ps1", "ordem": 20, "nome": "Silent Hill (1999)", "capitulo": "sh1", "versao": "PS1 (emulador)",
     "tipo": "local", "args": "\"{iso}\"", "dica": "Aponte um emulador de PS1 (por exemplo, o DuckStation) e o SEU disco.",
     "arte": {"capa": [lib("Sony_-_PlayStation", "Silent Hill (USA)")],
              "fundo": [lib("Sony_-_PlayStation", "Silent Hill (USA)", "Named_Titles")], "fonte": F_LIB}},
    {"id": "sh2_remake", "ordem": 30, "nome": "Silent Hill 2 (Remake)", "capitulo": "sh2", "versao": "Remake",
     "tipo": "steam", "appid": 2124490},
    {"id": "sh2_classic", "ordem": 31, "nome": "Silent Hill 2 (2001, clássico)", "capitulo": "sh2", "versao": "Clássico",
     "tipo": "local", "args": "\"{iso}\"",
     "dica": "PC: aponte o sh2pc.exe do Director's Cut (com o Enhanced Edition dos fãs). PS2: aponte o PCSX2 e a SUA ISO.",
     "arte": {"capa": [lib("Sony_-_PlayStation_2", "Silent Hill 2 (USA) (En,Ja,Fr,De,Es,It) (v2.01)"),
                       lib("Microsoft_-_Xbox", "Silent Hill 2 - Restless Dreams (USA)")], "fonte": F_LIB},
     "sugestoes": [{"nome": "Silent Hill 2: Enhanced Edition", "tipo": "mod", "url": "https://enhanced.townofsilenthill.com/SH2/",
                    "descricao": "Patch de fãs com HD, widescreen, sombras e efeitos restaurados. Precisa do Director's Cut de PC."}]},
    {"id": "sh3", "ordem": 40, "nome": "Silent Hill 3", "capitulo": "sh3", "versao": "PS2 ou PC",
     "tipo": "local", "args": "\"{iso}\"", "dica": "PC: aponte o sh3.exe. PS2: aponte o PCSX2 e a SUA ISO.",
     "arte": {"capa": [lib("Sony_-_PlayStation_2", "Silent Hill 3 (USA) (En,Ja,Fr,De,Es,It,Ko)")], "fonte": F_LIB}},
    {"id": "sh4", "ordem": 50, "nome": "Silent Hill 4: The Room", "capitulo": "sh4", "versao": "PC (GOG) ou PS2",
     "tipo": "local", "dica": "A versão da GOG é a mais fácil de achar hoje. Aponte o executável do jogo.",
     "arte": {"capa": [lib("Sony_-_PlayStation_2", "Silent Hill 4 - The Room (USA) (En,Ja)"),
                       lib("Microsoft_-_Xbox", "Silent Hill 4 - The Room (USA)")], "fonte": F_LIB}},
    {"id": "homecoming", "ordem": 60, "nome": "Silent Hill: Homecoming", "capitulo": "homecoming", "versao": "PC",
     "tipo": "steam", "appid": 19000},
    {"id": "downpour", "ordem": 70, "nome": "Silent Hill: Downpour", "capitulo": "downpour", "versao": "PS3 ou Xbox 360",
     "tipo": "local", "args": "\"{iso}\"", "dica": "Aponte um emulador (RPCS3 para PS3, Xenia para Xbox 360) e a SUA cópia.",
     "arte": {"capa": [wiki("4/4d/Downpour_boxart.png/revision/latest?cb=20140809064206"),
                       lib("Sony_-_PlayStation_3", "Silent Hill Downpour (Japan)")], "fonte": F_WIKI}},
    {"id": "short_message", "ordem": 80, "nome": "Silent Hill: The Short Message", "capitulo": "short_message",
     "versao": "PS5 · grátis", "tipo": "info",
     "arte": {"capa": [wiki("4/4e/Silent_Hill-_The_Short_Message_banner.jpg/revision/latest?cb=20240131235421")], "fonte": F_WIKI},
     "links": [page("Silent Hill: The Short Message")]},
    {"id": "f", "ordem": 90, "nome": "Silent Hill f", "capitulo": "f", "versao": "PC", "tipo": "steam", "appid": 2947440},
    {"id": "townfall", "ordem": 100, "nome": "Silent Hill: Townfall", "capitulo": "townfall", "versao": "PC",
     "tipo": "steam", "appid": 1636440},
]


def main(dest):
    gdir = Path(dest) / "games"
    if not gdir.exists():
        sys.exit(f"{gdir} não existe. Rode antes tools/nova_franquia.py.")
    for old in gdir.glob("*.json"):
        if not old.name.startswith("_"):
            old.unlink()
    tl = {"_comentario": "Capítulos em ordem aproximada da história ('capitulos'; os jogos em outras cidades vêm no fim), "
                         "spin-offs ('nao_canonicos'), perdidos, mídia, HQs e fãs. Cada jogo em games/*.json aponta para um "
                         "capítulo pelo campo 'capitulo'.",
          "capitulos": capitulos, "nao_canonicos": sorted(nao_canonicos, key=lambda c: c["lancamento"]), "perdidos": perdidos, "midia": midia, "hqs": hqs, "fas": fas}
    (gdir / "_linha_do_tempo.json").write_text(json.dumps(tl, ensure_ascii=False, indent=2), encoding="utf-8")
    for g in games:
        (gdir / f"{g['id']}.json").write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"ok: {len(capitulos)} capítulos, {len(games)} versões, {len(nao_canonicos)} spin-offs, {len(perdidos)} perdidos, "
          f"{len(midia)} filmes/séries, {len(hqs)} HQs/livros, {len(fas)} de fãs")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
