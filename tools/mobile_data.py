"""Gera mobile/www/data.json (o catálogo para o app Android) e os ícones do app a partir de re_hub.png.

Uso: python tools/mobile_data.py   (rode de novo depois de mudar o catálogo em games/ e gere o APK de novo)
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402

from rehub import catalog, sources  # noqa: E402
from rehub.franchise import FR  # noqa: E402

WWW = ROOT / "mobile" / "www"
RES = ROOT / "mobile" / "android" / "app" / "src" / "main" / "res"
STEAM = "https://cdn.akamai.steamstatic.com/steam/apps/{a}/{f}"
SECTIONS = (("canon", "Linha do tempo"), ("spinoff", "Não canônicos"))


def first(v):
    return (v[0] if v else None) if isinstance(v, list) else v


def art(g):
    if g.get("arte"):
        return first(g["arte"].get("capa")), first(g["arte"].get("fundo"))
    if g.get("tipo") == "steam" and g.get("appid"):
        a = g["appid"]
        return STEAM.format(a=a, f="library_600x900_2x.jpg"), STEAM.format(a=a, f="library_hero.jpg")
    return None, None


def where(g):
    """Onde e como jogar esta versão, visto do celular."""
    if g.get("mobile"):
        return {"tipo": g["mobile"], "rotulo": g.get("acao", "Abrir"), "url": g["url"]}
    if g.get("andamento"):
        return {"tipo": "andamento", "rotulo": "Acompanhar", "url": g["andamento"]["url"]}
    if g.get("tipo") == "steam" and g.get("appid"):
        return {"tipo": "pc", "rotulo": "Ver na Steam", "url": f"https://store.steampowered.com/app/{g['appid']}"}
    src = sources.sources(g)
    return {"tipo": "pc", "rotulo": "Ver projeto", "url": src[0][1]} if src else {"tipo": "pc", "rotulo": "", "url": ""}


def version(g):
    capa, fundo = art(g)
    return {"id": g["id"], "nome": g["nome"], "versao": g.get("versao") or g["nome"], "capa": capa, "fundo": fundo,
            "dica": g.get("dica", ""), "status": (g.get("andamento") or {}).get("status", ""), "jogar": where(g)}


def main():
    games = catalog.load_games()
    out = {"app": FR["app"], "cor": FR["cor"], "noticias": FR["noticias"], "secoes": []}
    for key, label in SECTIONS:
        chapters = []
        for ch in catalog.load_timeline(games, key):
            vs = [version(v) for v in ch.get("versoes", []) if v.get("tipo") != "info"]
            if not vs:
                continue
            capa, fundo = next(((v["capa"], v["fundo"]) for v in vs if v["capa"]), (None, None))
            chapters.append({"id": ch["id"], "titulo": ch["titulo"], "quando": ch.get("quando", ""), "onde": ch.get("onde", ""),
                             "ano": ch.get("lancamento", ""), "sinopse": ch.get("sinopse", ""), "capa": capa, "fundo": fundo,
                             "versoes": vs})
        out["secoes"].append({"id": key, "nome": label, "capitulos": chapters})
    WWW.mkdir(parents=True, exist_ok=True)
    (WWW / "data.json").write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    for name in ("re_hub.png", "re_logo.png"):
        Image.open(ROOT / name).save(WWW / name)
    n = sum(len(s["capitulos"]) for s in out["secoes"])
    print(f"data.json: {n} capítulos")
    if RES.is_dir():   # ícone do app em todas as densidades (o símbolo sem fundo sobre preto)
        sym = Image.open(ROOT / "re_hub.png").convert("RGBA")
        for folder, px in (("mdpi", 48), ("hdpi", 72), ("xhdpi", 96), ("xxhdpi", 144), ("xxxhdpi", 192)):
            d = RES / f"mipmap-{folder}"
            d.mkdir(parents=True, exist_ok=True)
            icon = Image.new("RGBA", (px, px), (11, 10, 9, 255))
            s = int(px * 0.82)
            icon.alpha_composite(sym.resize((s, s), Image.LANCZOS), ((px - s) // 2, (px - s) // 2))
            icon.save(d / "ic_launcher.png")
            icon.save(d / "ic_launcher_round.png")
            fg = Image.new("RGBA", (px * 9 // 4, px * 9 // 4), (0, 0, 0, 0))   # ícone adaptável: 108dp, área segura 72dp
            s = int(fg.width * 0.56)
            fg.alpha_composite(sym.resize((s, s), Image.LANCZOS), ((fg.width - s) // 2, (fg.width - s) // 2))
            fg.save(d / "ic_launcher_foreground.png")
        print("ícones do app gerados")


if __name__ == "__main__":
    main()
