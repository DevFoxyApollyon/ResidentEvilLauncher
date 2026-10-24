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
    if game.get("emulador"):
        from .emulators import EMULATORS as EMU
        e = EMU[game["emulador"]]
        out.append((f"Emulador: {e['nome']}", e["site"], f"{e['sistema']}: o hub baixa sozinho, voce so precisa da ISO"))
    if game.get("tipo") == "steam" and game.get("appid"):
        out.append(("Steam", f"https://store.steampowered.com/app/{game['appid']}", "versao oficial de PC"))
    if game["id"] in GOG:
        out.append(("GOG", GOG[game["id"]], "versao oficial de PC, sem DRM"))
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
