"""Gera VERSOES.md: todas as versoes do catalogo, de onde vem cada uma e como instalar (para o GitHub).

    python tools/versoes_md.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from rehub import catalog, sources  # noqa: E402


def main():
    games = catalog.load_games()
    games = games if isinstance(games, list) else list(games.values())
    titles, order = {}, []
    for sec in ("canon", "spinoff"):
        for ch in catalog.load_timeline(games, sec):
            if ch["id"] not in titles:
                titles[ch["id"]] = ch.get("titulo", ch["id"])
                order.append(ch["id"])
    by_ch = {}
    for g in games:
        if g.get("tipo") in ("steam", "local"):
            by_ch.setdefault(g.get("capitulo", g["id"]), []).append(g)
    out = ["# Versões jogáveis no RE Launcher", "",
           "Todas as versões que o hub instala ou abre, de onde vem cada uma e como instalar. O hub nunca baixa o jogo:",
           "versões da Steam e da GOG você compra (as demos são grátis); ports e emuladores precisam da SUA cópia/ISO.",
           "Gerado por `tools/versoes_md.py` a partir do catálogo (`games/`).", ""]
    for ch, gs in sorted(by_ch.items(), key=lambda kv: order.index(kv[0]) if kv[0] in order else 999):
        out += [f"## {titles.get(ch, gs[0]['nome'])}", ""]
        for g in sorted(gs, key=lambda g: g.get("ordem", 999)):
            src = sources.sources(g)
            where = ", ".join(f"[{n}]({u})" for n, u, _ in src) or "seu arquivo"
            out.append(f"### {g.get('versao') or g['nome']}")
            out.append(f"- **Onde:** {where}")
            for k, s in enumerate(sources.steps(g), 1):
                out.append(f"  {k}. {s}")
            out.append("")
    (ROOT / "VERSOES.md").write_text("\n".join(out), encoding="utf-8")
    print("VERSOES.md", sum(len(v) for v in by_ch.values()), "versões")


if __name__ == "__main__":
    main()
