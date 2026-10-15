"""Adiciona curtas e jogos feitos por fãs à seção "Feito por fãs". Pode rodar de novo: não duplica nada.

Uso: python tools/fan_update.py
Itens sem imagem ganham, no app, uma arte aleatória da série como capa.
"""
import json
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TL = ROOT / "games" / "_linha_do_tempo.json"
d = json.loads(TL.read_text(encoding="utf-8"))


def yt(q):
    return {"nome": "Procurar no YouTube", "url": "https://www.youtube.com/results?search_query=" + urllib.parse.quote_plus(q)}


def item(cid, titulo, categoria, sinopse, onde, links, ano=None, quando=None, formato=None):
    c = {"id": cid, "titulo": titulo, "categoria": categoria, "quando": quando or (str(ano) if ano else categoria),
         "onde": formato or categoria, "formato": formato or categoria, "sinopse": sinopse,
         "lancamentos": [{"nome": titulo, "ano": ano or "—", "plataformas": formato or categoria, "onde": onde}],
         "links": links}
    if ano:
        c["lancamento"] = ano
    return c


games = [
    item("fan_re1_remake", "Resident Evil (fan remake em Unity)", "Fan remake",
         "Remake do primeiro jogo feito por fãs na Unity, com modo clássico de câmeras fixas. A demo saiu em outubro de "
         "2022, e o projeto foi encerrado em dezembro do mesmo ano depois que a Capcom pediu para parar.",
         "Cancelado a pedido da Capcom; a demo saiu do ar", [
             {"nome": "Notícia (Game Developer)",
              "url": "https://www.gamedeveloper.com/business/capcom-shuts-down-fan-remakes-of-resident-evil-games"}],
         ano=2022, formato="Fan remake · cancelado"),
    item("fan_cv_remake", "Code: Veronica (fan remake em Unity)", "Fan remake",
         "Remake de Code: Veronica feito pela mesma equipe, com modos Remake (câmera no ombro) e Classic (câmeras "
         "fixas). Teve demo, mas foi cancelado em dezembro de 2022 a pedido da Capcom, pouco antes de sair completo.",
         "Cancelado a pedido da Capcom", [
             {"nome": "Notícia (TheGamer)",
              "url": "https://www.thegamer.com/resident-evil-code-veronica-fan-remake-shut-down-capcom/"}],
         ano=2022, formato="Fan remake · cancelado"),
    item("fan_re3_classic", "Resident Evil 3 Classic Remake (UE5)", "Fan remake",
         "Projeto de fãs que refaz o RE3 na Unreal Engine 5 com câmeras fixas, como o original, usando cenários do "
         "remake de 2020 e a Jill com a roupa clássica. Mostrado em 2021; não há notícia de versão final.",
         "Só vídeos de demonstração", [
             {"nome": "Notícia (DSOGaming)",
              "url": "https://www.dsogaming.com/videotrailer-news/fans-working-on-a-classic-remake-of-resident-evil-3-in-unreal-engine-5/"}],
         ano=2021, formato="Fan remake · em vídeo"),
    item("fan_obsrv", "Outbreak Server Resurrection", "Servidor de fãs",
         "Os servidores oficiais do Outbreak fecharam em 2007 (EUA) e 2011 (Japão). Desde 1º de janeiro de 2014, "
         "fãs mantêm servidores alternativos para as versões japonesas, com placares e listas de banimento.",
         "Online de novo com a versão japonesa (PS2 ou emulador)", [
             {"nome": "Grupo na Steam", "url": "https://steamcommunity.com/groups/outbreakserver"},
             {"nome": "Notícia (Kotaku)",
              "url": "https://kotaku.com/ten-years-later-fans-bring-resident-evil-outbreak-back-1494567563"}],
         ano=2014, formato="Servidor online de fãs"),
]
films = [
    item("fan_red_falls", "Resident Evil: Red Falls", "Fan film",
         "Filme de fãs de quase uma hora, roteirizado por Jordan Page. Um capitão interroga um homem ligado a "
         "bioterroristas que mantêm agentes da BSAA reféns, enquanto a equipe Foxtrot entra na cidade infestada de "
         "Red Falls.", "Grátis no YouTube", [yt("Resident Evil Red Falls fan film")], ano=2013, formato="Fan film · 53 min"),
    item("fan_biohazard_riggs", "Biohazard (Chandler Riggs)", "Fan film",
         "Curta de 19 minutos baseado no RE7, escrito, dirigido e estrelado por Chandler Riggs (o Carl de The Walking "
         "Dead) como Ethan Winters. Recria o jantar da família Baker e a luta com Jack na garagem.",
         "Grátis no YouTube", [yt("Biohazard Chandler Riggs Resident Evil 7 fan film")], ano=2026,
         formato="Fan film · 19 min"),
    item("fan_leaving_rc", "Leaving Raccoon City", "Fan film",
         "Curta de Beau Preiser sobre a fuga de Raccoon City.", "Grátis no YouTube",
         [yt("Leaving Raccoon City Resident Evil Fan Film")], ano=2025, formato="Fan film · 7 min"),
    item("fan_invasion", "Resident Evil: Invasion", "Fan film", "Curta de fãs de seis minutos.", "Grátis no YouTube",
         [yt("Resident Evil Invasion fan film")], ano=2023, formato="Fan film · 6 min"),
    item("fan_downfall", "Downfall RC", "Fan film", "Curta de Jose Angel Salazar sobre a queda de Raccoon City.",
         "Grátis no YouTube", [yt("DOWNFALL RC A Resident Evil Fan-Film")], formato="Fan film · 14 min"),
    item("fan_falling_stars", "Resident Evil: Falling Stars", "Fan film",
         "Média-metragem de fãs dirigido por Mariano Caterinozzi.", "Grátis no YouTube",
         [yt("Resident Evil Falling Stars fan made short movie")], formato="Fan film · 38 min"),
    item("fan_breakout", "Resident Evil: Breakout", "Fan film", "Curta de Ryan Brewer (Brewed Images).",
         "Grátis no YouTube", [yt("Resident Evil Breakout Brewed Images")], formato="Fan film · 13 min"),
    item("fan_village_short", "Village (curta de fãs)", "Fan film",
         "Curta de quatro minutos inspirado em Resident Evil Village, gravado com uma GoPro por cineastas estreantes.",
         "Grátis no YouTube", [yt("Resident Evil Village fan film Dimitrescu short")], formato="Fan film · 4 min"),
    item("fan_stars_serie", "S.T.A.R.S. (websérie)", "Fan série",
         "Websérie de comédia de humor ácido sobre a equipe S.T.A.R.S., dois anos antes do primeiro jogo.",
         "Grátis no YouTube", [yt("S.T.A.R.S. Resident Evil fan series")], formato="Websérie de fãs"),
]

MODDB = "https://www.moddb.com/mods/"
classic_mods = [
    item("fan_revisited", "Resident Evil REvisited", "Mod clássico",
         "Mod para o RE2 de PC que vira um prólogo do primeiro jogo, baseado nos livros de S. D. Perry. Você joga como "
         "Trent (Victor Darius) nas Montanhas Arklay e na mansão Spencer no começo do surto, com câmeras fixas, salas "
         "inspiradas no remake de GameCube e um motel tirado de um cenário cortado do Outbreak.",
         "Em produção (demo anunciada)", [
             {"nome": "Notícia (GameRevolution)", "url": "https://www.gamerevolution.com/news/699940-resident-evil-revisited-mod-re1-prequel"},
             {"nome": "Notícia (MegaVisions)", "url": "https://megavisions.net/this-new-resident-evil-2-mod-is-inspired-by-s-d-perrys-novels"}],
         formato="Mod do RE2 clássico (PC)"),
    item("fan_re2_rearranged", "RE2: Classic Re-arranged", "Mod clássico",
         "Muda a posição de inimigos, itens e caminhos do RE2 para deixar o jogo mais difícil sem mexer em vida, dano ou "
         "armas. Precisa do Classic REbirth.", "ModDB (grátis)", [{"nome": "Abrir no ModDB", "url": MODDB + "resident-evil-2-classic-re-arranged"}],
         ano=2026, formato="Mod do RE2 clássico · v1.22"),
    item("fan_reenhance", "RE:Enhance", "Mod clássico",
         "Refaz os cenários pré-renderizados dos clássicos em resolução bem maior, de SonicB00M. Tem versões para RE1, "
         "RE2 e RE3.", "ModDB e fóruns (grátis)", [{"nome": "Discussão (ResetEra)",
                                                    "url": "https://www.resetera.com/threads/the-definitive-way-to-play-classic-resident-evil-2-3-today-re-enhance-mod.1382446/"}],
         formato="Mod visual · RE1, RE2, RE3"),
    item("fan_re3_definitive", "RE3: Definitive Edition", "Mod clássico",
         "Pacote para o RE3 de 1999 que junta Classic REbirth, o HD Mod da TeamX, modelos novos dos personagens e ReShade.",
         "ModDB (grátis)", [{"nome": "Abrir no ModDB", "url": MODDB + "resident-evil-3-definitive-edition"}],
         formato="Mod do RE3 clássico"),
    item("fan_re3_necropolis", "RE3: Lord of the Necropolis", "Mod clássico",
         "Overhaul do RE3 de 1999 (versão SourceNext) pensado como um \"Director's Cut\" do jogo.",
         "ModDB (grátis)", [{"nome": "Mods do RE3 no ModDB", "url": "https://www.moddb.com/games/resident-evil-3/mods"}],
         formato="Mod do RE3 clássico"),
    item("fan_re3_restoration", "RE3: Restoration Project", "Mod clássico",
         "Patch acumulado para o RE3 de PC: vídeos em tela cheia, som sem perda, correções de bugs e outras melhorias. "
         "Não precisa do Classic REbirth.", "ModDB (grátis)", [{"nome": "Abrir no ModDB", "url": MODDB + "resident-evil-3-restoration-project"}],
         formato="Mod do RE3 clássico"),
    item("fan_re2_hd_teamx", "RE2 e RE3 HD Mod (TeamX)", "Mod clássico",
         "Texturas e fundos em HD para o RE2 e o RE3 clássicos, muito usado junto com o Classic REbirth.",
         "ModDB (grátis)", [{"nome": "RE3 HD Mod no ModDB", "url": MODDB + "resident-evil-3-hd-mod"}],
         formato="Mod de texturas · RE2, RE3"),
]

have = {c["id"] for c in d["fas"]}
first_film = next((i for i, c in enumerate(d["fas"]) if c.get("categoria", "").startswith("Fan film")), len(d["fas"]))
d["fas"][first_film:first_film] = [c for c in games if c["id"] not in have]
d["fas"][first_film + len([c for c in games if c["id"] not in have]):first_film + len([c for c in games if c["id"] not in have])] =     [c for c in classic_mods if c["id"] not in have]
d["fas"] += [c for c in films if c["id"] not in have]

# os mesmos mods como "Recomendados" nos clássicos (botão Abrir página na tela Gerenciar)
LINKS = {
    "re2_classic": [("Classic REbirth (RE2)", "https://classicrebirth.com/index.php/downloads/resident-evil-2-classic-rebirth/",
                     "Patch que faz o RE2 de PC rodar bem no Windows atual. Base para quase todos os outros mods."),
                    ("RE2: Classic Re-arranged", MODDB + "resident-evil-2-classic-re-arranged",
                     "Inimigos, itens e caminhos remontados para mais desafio. Precisa do Classic REbirth."),
                    ("Resident Evil REvisited", "https://www.gamerevolution.com/news/699940-resident-evil-revisited-mod-re1-prequel",
                     "Prólogo do RE1 feito como mod do RE2 (em produção)."),
                    ("Mods do RE2 no ModDB", "https://www.moddb.com/games/resident-evil-2/mods", "Lista completa de mods do RE2 clássico.")],
    "re3_classic": [("RE3: Definitive Edition", MODDB + "resident-evil-3-definitive-edition",
                     "Classic REbirth + HD Mod + personagens novos + ReShade num pacote só."),
                    ("RE3: Restoration Project", MODDB + "resident-evil-3-restoration-project",
                     "Vídeos em tela cheia, som sem perda e correções."),
                    ("RE3 HD Mod (TeamX)", MODDB + "resident-evil-3-hd-mod", "Texturas e fundos em HD."),
                    ("Mods do RE3 no ModDB", "https://www.moddb.com/games/resident-evil-3/mods", "Lista completa de mods do RE3 clássico.")],
}
for gid, links in LINKS.items():
    gf = ROOT / "games" / f"{gid}.json"
    g = json.loads(gf.read_text(encoding="utf-8"))
    names = {x["nome"] for x in g.get("sugestoes", [])}
    g.setdefault("sugestoes", []).extend({"nome": n, "tipo": "mod", "url": u, "descricao": desc}
                                         for n, u, desc in links if n not in names)
    gf.write_text(json.dumps(g, ensure_ascii=False, indent=2), encoding="utf-8")
TL.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
print("ok:", len(d["fas"]), "itens feitos por fãs")
