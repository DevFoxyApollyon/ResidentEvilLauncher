"""De onde vem cada versao do catalogo: loja (Steam, GOG), GitHub do port ou o emulador indicado.

sources(game) -> [(rotulo, url, detalhe)], a fonte principal primeiro.
"""

# paginas da GOG das versoes que tambem sao vendidas la (sem DRM)
GOG = {
    "re1_classic": "https://www.gog.com/en/game/resident_evil",
    "re2_classic": "https://www.gog.com/en/game/resident_evil_2",
    "re3_classic": "https://www.gog.com/en/game/resident_evil_3",
    "re0": "https://www.gog.com/en/game/resident_evil_0",
    "re1": "https://www.gog.com/en/game/resident_evil_hd_remaster",
}
EMULATORS = ("PCSX2", "DuckStation", "Dolphin", "Azahar", "mGBA")


def sources(game):
    out = []
    if game.get("andamento"):
        a = game["andamento"]
        return [("Em andamento", a["url"], f"{a['nome']}: {a['status']}")]
    if game.get("meu"):
        return [("Adicionado por você", game.get("url") or game.get("exe_fixo", ""), "site" if game.get("url") else "executável")]
    if game.get("emulador"):
        from .emulators import EMULATORS as EMU
        e = EMU[game["emulador"]]
        out.append((f"Emulador: {e['nome']}", e["site"], f"{e['sistema']}: o hub baixa sozinho, você só precisa da ISO"))
    if game.get("tipo") == "steam" and game.get("appid"):
        out.append(("Steam", f"https://store.steampowered.com/app/{game['appid']}", "versão oficial de PC"))
    if game["id"] in GOG:
        out.append(("GOG", GOG[game["id"]], "versão oficial de PC, sem DRM"))
    if game.get("github"):
        out.append(("GitHub", f"https://github.com/{game['github']}/releases/latest", "port de PC, baixa pelo hub"))
    for p in game.get("projetos", []):
        url = p["url"]
        if game.get("github") and url.rstrip("/").endswith(game["github"]):
            continue
        kind = "Emulador" if p["nome"].split(" (")[0] in EMULATORS else "Projeto"
        if kind == "Emulador" and game.get("emulador"):
            continue   # o emulador do jogo ja esta na lista (baixado pelo hub)
        out.append((f"{kind}: {p['nome'].split(' (')[0]}", url, p.get("status", "")))
    return out


def label(game):
    """Rotulo curto da fonte principal, para listas."""
    s = sources(game)
    return " / ".join(x[0].split(":")[0] for x in s[:2]) if s else "Seu arquivo"


def steps(game):
    """Como instalar e jogar esta versão, passo a passo, no caminho qué ela usa."""
    if game.get("mobile") == "ios":
        return ["Esta versão é jogada no iPhone, iPad ou Mac: clique em Abrir na App Store e baixe pelo aparelho.",
                "Precisa de iPhone 15 Pro ou mais novo, ou iPad/Mac com chip Apple M1 ou mais novo.",
                "O download é grátis e tem um trecho para testar; o jogo completo é comprado dentro do app."]
    if game.get("mobile") == "android":
        return ["Clique em Baixar APK e baixe o .apk da última release no celular Android (64 bits).",
                "Instale o .apk (o Android pede para permitir apps de fora da Play Store).",
                "Abra o jogo e escolha a SUA ROM americana (.gbc)."]
    if game.get("meu"):
        return ["Versão que você adicionou em Opções > Adicionar jogo ou site.",
                "Clique em Jogar: abre " + ("o site no navegador." if game.get("url") else "o executável que você escolheu."),
                "Para tirar, use Remover."]
    if game.get("andamento"):
        a = game["andamento"]
        return [f"Ainda não dá para jogar esta versão no PC. {a['status']}",
                "Clique em Acompanhar para ver o projeto; quando sair uma versão jogável, ela entra aqui."]
    if game.get("tipo") == "steam":
        free = "demo" in game.get("versão", "").lower() or "grátis" in game.get("versão", "").lower()
        out = ["Clique em Instalar: a Steam abre e baixa o jogo" + (" (é de graça)." if free else " (o jogo precisa estar na sua conta Steam).")]
        if game["id"] in GOG:
            out.append("Comprou na GOG? Instale pelo GOG Galaxy e use Configurar para apontar o .exe.")
        return out + ["Quando terminar, o botão vira Jogar."]
    if game.get("emulador"):
        from .emulators import EMULATORS as EMU
        e = EMU[game["emulador"]]
        return [f"Clique em Instalar: o hub baixa o {e['nome']} ({e['sistema']}) sozinho, uma vez para todos os jogos dele.",
                "O hub procura a SUA ISO no PC e pergunta se é ela; se não achar, você escolhe o arquivo.",
                "Clique em Jogar: o jogo abre direto no emulador, em tela cheia."] + game.get("passos_extra", [])
    if game.get("instalador"):
        return ["Clique em Instalar: o hub baixa o instalador oficial do projeto e abre.",
                "Termine a instalação (escolha a pasta que quiser).",
                f"No hub, clique em Configurar e escolha o {game.get('exe', '.exe')} instalado.",
                (game.get("depois_de_baixar") or "clique em Jogar.")[0].upper() + (game.get("depois_de_baixar") or "clique em Jogar.")[1:]]
    if game.get("github"):
        out = ["Clique em Instalar: o hub baixa a versão mais nova do GitHub e ja configura o executável."]
        if "{iso}" in game.get("args", ""):
            out.append("O hub procura a SUA ISO no PC e pergunta se é ela; se não achar, você escolhe o arquivo.")
        if game.get("depois_de_baixar"):
            out.append(game["depois_de_baixar"][0].upper() + game["depois_de_baixar"][1:])
        return out + ["Clique em Jogar."]
    return ["Clique em Configurar e escolha o executável do jogo."]
