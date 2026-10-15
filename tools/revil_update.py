"""Adiciona ao catálogo o que falta em relação a residentevil.com.br/jogos/ e separa as HQs.

Uso: python tools/revil_update.py   (pode rodar de novo: não duplica nada)
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TL = ROOT / "games" / "_linha_do_tempo.json"
d = json.loads(TL.read_text(encoding="utf-8"))

REVIL = "https://residentevil.com.br/wp-content/uploads/"
WIKI = "https://static.wikia.nocookie.net/residentevil/images/"
F_REVIL = "capa: REVIL (residentevil.com.br)"
F_WIKI = "imagem: Resident Evil Wiki (fãs)"


def revil(path):
    return REVIL + path


def link_revil(path):
    return {"nome": "Ver no REVIL", "url": "https://residentevil.com.br/" + path}


# ---------- perdidos: banners do REVIL como capa + o que faltava da seção Betas ----------
by_id = {c["id"]: c for c in d["perdidos"]}
extra_art = {
    "re1_5": ("2015/06/BetaRE1meio0D3.jpg", "betas/resident-evil-1-5"),
    "re0_n64": ("2023/05/Beta_RE0-360x300.jpg", "betas/resident-evil-0-beta"),
    "re4_perdidos": ("2015/06/BetaRE4-D3.jpg", "artigos/versoes-beta-de-resident-evil-4"),
}
for cid, (img, page) in extra_art.items():
    c = by_id[cid]
    old = [u for u in c.get("arte", {}).get("capa", []) if REVIL not in u]
    c["arte"] = {"capa": [revil(img)] + old, "fonte": F_REVIL}
    c["links"] = [link_revil(page)] + [lk for lk in c.get("links", []) if "residentevil.com.br" not in lk["url"]]
for cid, page in (("re_gbc", "Resident_Evil_(Game_Boy_Color)"), ("re_portable", "Resident_Evil_Portable")):
    by_id[cid].setdefault("links", [{"nome": "Resident Evil Wiki", "url": "https://residentevil.fandom.com/wiki/" + page}])

new_lost = [
    {
        "id": "re_dash", "titulo": "Resident Evil Dash", "quando": "1996", "onde": "Sequência do RE1 para Saturn",
        "lancamento": 1996, "formato": "Jogo cancelado · Sega Saturn",
        "poster": {"titulo": "RESIDENT EVIL DASH", "subtitulo": "SATURN · 1996", "carimbo": "CANCELADO"},
        "sinopse": "Citado uma única vez, numa entrevista de Yoshiki Okamoto em 1996. Três anos depois do RE1, plantas "
                   "infectadas atacariam Raccoon City e dois personagens novos voltariam à mansão Spencer, agora "
                   "envelhecida. Foi cancelado para não atrasar o RE2; parte das ideias foi para o RE1 de Saturn, "
                   "as Ivies do RE2 e o cenário Flashback do Outbreak File #2.",
        "lancamentos": [{"nome": "Conceito anunciado", "ano": 1996, "plataformas": "Sega Saturn",
                         "onde": "Nunca saiu build: só existe a entrevista"}],
        "arte": {"capa": [revil("2015/06/BetaDash-D3.jpg")], "fonte": F_REVIL},
        "links": [link_revil("betas/resident-evil-dash")],
    },
    {
        "id": "re2_trial", "titulo": "Resident Evil 2 Trial", "quando": "Setembro de 1997", "onde": "Demo do RE2",
        "lancamento": 1997, "formato": "Demo oficial · PlayStation",
        "sinopse": "Disco extra do Director's Cut com uma versão quase final do RE2: tela de título diferente, texto no "
                   "lugar da abertura, sem vozes e itens em lugares que mudaram depois. Leon segue por um caminho mais "
                   "curto nas ruas de Raccoon.",
        "lancamentos": [{"nome": "Resident Evil 2 Trial Edition", "ano": 1997, "plataformas": "PlayStation",
                         "onde": "Disco bônus do Resident Evil Director's Cut: emulador com o seu disco"}],
        "arte": {"capa": [revil("2015/06/BetaRE2-D3.jpg")], "fonte": F_REVIL},
        "links": [link_revil("betas/resident-evil-2-trial")],
    },
    {
        "id": "re5_beta", "titulo": "Resident Evil 5 Beta", "quando": "2005 – 2007", "onde": "Primeiros trailers do RE5",
        "lancamento": 2005, "formato": "Conceito · PS3 / Xbox 360",
        "sinopse": "O primeiro vídeo do RE5, de 2005, mostrava Chris com outras roupas, inimigos rápidos parecidos com "
                   "zumbis e um sistema de calor: Chris precisaria beber e comer para não perder velocidade. Do conceito, "
                   "só a cegueira ao passar do escuro para o claro chegou ao jogo final.",
        "lancamentos": [{"nome": "Trailers de 2005 e 2007", "ano": 2005, "plataformas": "PS3, Xbox 360",
                         "onde": "Só vídeos: nada jogável vazou"}],
        "arte": {"capa": [revil("2023/05/Beta_RE5-360x300.jpg")], "fonte": F_REVIL},
        "links": [link_revil("betas/resident-evil-5-beta")],
    },
]
d["perdidos"] = sorted(d["perdidos"] + [c for c in new_lost if c["id"] not in by_id], key=lambda c: c["lancamento"])

# ---------- não canônicos que faltavam (Re:Verse, Survival Unit, outros jogos) ----------
new_spin = [
    {
        "id": "reverse", "titulo": "Resident Evil Re:Verse", "quando": "Fora da história", "onde": "Multiplayer online",
        "lancamento": 2022, "formato": "Multiplayer · grátis com Village",
        "sinopse": "Mata-mata online para seis jogadores com heróis e vilões da série. Quem morre volta como arma "
                   "biológica para se vingar. Saiu em outubro de 2022, grátis para quem tinha Resident Evil Village.",
        "lancamentos": [{"nome": "Resident Evil Re:Verse", "ano": 2022, "plataformas": "PC, PS4, Xbox One",
                         "onde": "Junto com Resident Evil Village (Steam e consoles)"}],
        "arte": {"capa": [revil("2023/05/REverse-D3-360x300.jpg")], "fonte": F_REVIL},
        "links": [link_revil("resident-evil-reverse")],
    },
    {
        "id": "survival_unit", "titulo": "Resident Evil Survival Unit", "quando": "Mundo paralelo",
        "onde": "Hospital da Umbrella", "lancamento": 2025, "formato": "Estratégia · celular",
        "sinopse": "Estratégia em tempo real para celular. O protagonista acorda num hospital depois de servir de cobaia "
                   "da Umbrella e, tentando fugir, encontra personagens da série num mundo paralelo. Feito pela JOYCITY "
                   "e lançado no mundo todo em 17 de novembro de 2025, com legendas em português.",
        "lancamentos": [{"nome": "Resident Evil Survival Unit", "ano": 2025, "plataformas": "iOS, Android",
                         "onde": "App Store e Google Play (grátis)"}],
        "arte": {"capa": [revil("2025/11/Survival-Unit-D3.jpg")], "fonte": F_REVIL},
        "links": [link_revil("resident-evil-survival-unit")],
    },
    {
        "id": "outros_jogos", "titulo": "Celular, pachinko e tabuleiro", "quando": "Fora da história",
        "onde": "Jogos fora dos consoles", "lancamento": 2000, "formato": "Outros jogos",
        "sinopse": "Resident Evil também saiu em celulares antigos, iPhone e iPad, no Zeebo, em máquinas pachinko "
                   "japonesas, num jogo de cartas e em jogos de tabuleiro. A maior parte dos jogos de celular saiu do ar.",
        "lancamentos": [
            {"nome": "Assault Nightmare", "ano": 2000, "plataformas": "Celular (Japão)", "onde": "Fora do ar"},
            {"nome": "Confidential Report", "ano": 2004, "plataformas": "Celular", "onde": "Fora do ar"},
            {"nome": "Genesis", "ano": 2008, "plataformas": "Celular", "onde": "Fora do ar"},
            {"nome": "Degeneration", "ano": 2008, "plataformas": "Celular", "onde": "Fora do ar"},
            {"nome": "RE4 Mobile, iPad e Zeebo", "ano": 2009, "plataformas": "Celular, iPad, Zeebo", "onde": "Fora do ar"},
            {"nome": "Mercenaries VS", "ano": 2011, "plataformas": "iPhone", "onde": "Fora do ar"},
            {"nome": "Outbreak Survive", "ano": 2012, "plataformas": "Celular (Japão)", "onde": "Fora do ar"},
            {"nome": "Clan Master", "ano": 2016, "plataformas": "Celular (Japão)", "onde": "Fora do ar"},
            {"nome": "Personagens em TEPPEN", "ano": 2020, "plataformas": "Celular", "onde": "App Store e Google Play"},
            {"nome": "Deck Building Game", "ano": 2010, "plataformas": "Jogo de cartas", "onde": "Lojas de jogos de mesa"},
            {"nome": "Pachinko e pachislot", "ano": 2008, "plataformas": "Máquinas japonesas", "onde": "Casas de pachinko no Japão"},
            {"nome": "The Board Game", "ano": 2019, "plataformas": "Tabuleiro", "onde": "Lojas de jogos de mesa"},
        ],
        "arte": {"capa": [revil("2016/05/Outros-D3.jpg")], "fonte": F_REVIL},
        "links": [link_revil("outros-jogos/")],
    },
]
have = {c["id"] for c in d["nao_canonicos"]}
d["nao_canonicos"] = sorted(d["nao_canonicos"] + [c for c in new_spin if c["id"] not in have],
                          key=lambda c: c.get("lancamento", 9999))


# ---------- HQs e livros: seção própria, uma capa por série ----------
def comic(cid, titulo, ano, formato, onde, sinopse, img, wiki, quando=None):
    return {
        "id": cid, "titulo": titulo, "quando": quando or str(ano), "onde": formato, "lancamento": ano,
        "formato": formato, "sinopse": sinopse,
        "lancamentos": [{"nome": titulo, "ano": ano, "plataformas": formato, "onde": onde}],
        "arte": {"capa": [WIKI + img], "fonte": F_WIKI},
        "links": [{"nome": "Resident Evil Wiki", "url": "https://residentevil.fandom.com/wiki/" + wiki}],
    }


if "hqs" not in d:
    midia = {c["id"]: c for c in d["midia"]}
    moved = [midia.pop(k) for k in ("marhawa", "heavenly_island") if k in midia]
    midia.pop("hqs", None)
    livros = midia.pop("livros", None)
    hqs = [
        comic("hq_magazine", "The Official Comic Magazine", 1998, "Revista em quadrinhos (Image / WildStorm)",
              "Edições usadas", "Cinco revistas com histórias curtas dos S.T.A.R.S. e de Raccoon City, adaptações do "
              "RE1 e do RE2 e contos originais. Foi a primeira HQ ocidental da série.",
              "e/e6/RE_Magazine_1.jpg/revision/latest?cb=20090514234238", "Resident_Evil_Vol_1_Issue_1", "1998 – 1999"),
        comic("hq_bh2_manhua", "Bio Hazard 2 (manhua)", 1998, "Quadrinho de Hong Kong", "Edições importadas",
              "Adaptação longa e bem livre do RE2, publicada em Hong Kong, com Leon e Claire enfrentando criaturas "
              "que não estão no jogo.",
              "a/a8/BIO_HAZARD_2_comic_-_Volume_8.png/revision/latest?cb=20121102002158", "BIO_HAZARD_2_(manhua)"),
        comic("hq_bh3_manhua", "Biohazard 3 Last Escape (manhua)", 1999, "Quadrinho de Hong Kong",
              "Edições importadas", "A fuga de Jill de Raccoon City contada em quadrinhos de Hong Kong, com o "
              "Nemesis como perseguidor.",
              "9/9b/BIOHAZARD_3_LAST_ESCAPE_VOL.1_-_front_cover.jpg/revision/latest?cb=20131006222630",
              "BIOHAZARD_3_LAST_ESCAPE_(manhua)"),
        comic("hq_fire_ice", "Fire & Ice", 2000, "Minissérie (WildStorm)", "Edições usadas",
              "Quatro edições sobre a Charlie Team dos S.T.A.R.S., uma equipe que nunca aparece nos jogos, presa num "
              "surto da Umbrella.",
              "b/b5/Fire_and_Ice_issue_1.jpg/revision/latest?cb=20210422004425", "Resident_Evil:_Fire_and_Ice",
              "2000 – 2001"),
        comic("hq_veronica", "Code: Veronica (manhua)", 2001, "Quadrinho de Hong Kong · WildStorm em inglês",
              "Edições usadas ou importadas", "Adaptação de Code: Veronica em Hong Kong, depois traduzida pela "
              "WildStorm em quatro volumes. Segue a história do jogo com mais ação.",
              "a/a7/BIOHAZARD_CODE_Veronica_VOL.1_-_front_cover.jpg/revision/latest?cb=20130710024118",
              "BIOHAZARD_CODE:Veronica_(manhua)"),
        comic("hq_bh0_manhua", "Biohazard 0 (manhua)", 2003, "Quadrinho de Hong Kong", "Edições importadas",
              "Rebecca e Billy no trem Ecliptic Express e no centro de treinamento da Umbrella, em quadrinhos de "
              "Hong Kong.",
              "6/6e/Biohazard_0_VOL.1_-_front_cover.jpg/revision/latest?cb=20130709023501", "Biohazard_0_(manhua)"),
        comic("hq_wildstorm_2009", "Resident Evil (2009)", 2009, "Minissérie (WildStorm / DC)", "Edições usadas",
              "Seis edições que servem de prólogo do RE5: Mina Gere, agente da BSAA, investiga a morte dos pais na "
              "África, região onde o jogo se passa.",
              "2/26/Resident_Evil_Vol_2_Issue_1.jpg/revision/latest?cb=20140126054907", "Resident_Evil_Vol_2_Issue_1",
              "2009 – 2011"),
        comic("hq_death_island", "Death Island (mangá)", 2023, "Mangá", "Edições importadas",
              "Adaptação em mangá do filme em CG Death Island, que junta Leon, Chris, Jill, Claire e Rebecca em "
              "Alcatraz.",
              "6/62/BIOHAZARD_DEATH_ISLAND_manga_promo_2.jpg/revision/latest?cb=20230515142221",
              "BIOHAZARD_DEATH_ISLAND_(manga)"),
    ] + moved
    if livros:
        hqs.append(livros)
    d["midia"] = list(midia.values())
    d["hqs"] = sorted(hqs, key=lambda c: c["lancamento"])
    d["_comentario"] += " Seções extras: 'perdidos', 'midia' (filmes e séries), 'hqs' (HQs, mangás e livros) e 'fas'."

# ---------- Resident Evil Veronica (remake de 2027): o jogo da Steam já existe (games/veronica.json) ----------
ver = next(c for c in d["capitulos"] if c["id"] == "veronica")
if not any(x.get("ano") == 2027 for x in ver.get("lancamentos", [])):
    ver.setdefault("lancamentos", []).append({"nome": "Resident Evil Veronica (remake)", "ano": 2027,
                                              "plataformas": "PS5, Xbox Series X|S, Switch 2, PC",
                                              "onde": "Anunciado no Summer Game Fest 2026 · Steam e consoles"})
TL.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")

print("ok:", len(d["perdidos"]), "perdidos,", len(d["nao_canonicos"]), "não canônicos,", len(d["midia"]), "filmes,",
      len(d["hqs"]), "HQs/livros")
