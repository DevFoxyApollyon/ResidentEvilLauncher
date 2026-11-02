"""Quiz da franquia: perguntas de múltipla escolha montadas com o que o hub já tem (linha do tempo, fichas de
personagens, vírus). Nada é baixado: as respostas saem do catálogo (games/)."""
import random
import re

from . import catalog, characters, lore


def _year(text):
    m = re.search(r"\d{4}", text or "")
    return m.group(0) if m else None


def _options(rng, right, pool, n=4):
    """A certa e mais n-1 erradas diferentes dela; devolve (opções embaralhadas, índice da certa) ou None."""
    wrong = sorted({p for p in pool if p and p != right})
    if len(wrong) < n - 1:
        return None
    opts = rng.sample(wrong, n - 1) + [right]
    rng.shuffle(opts)
    return opts, opts.index(right)


def _q(text, got, why="", chapter=None):
    if not got:
        return None
    opts, right = got
    return {"pergunta": text, "opcoes": opts, "certa": right, "explicacao": why, "capitulo": chapter}


def _chapters(games):
    canon = catalog.load_timeline(games, "canon")
    spin = catalog.load_timeline(games, "spinoff")
    return canon, spin


def _makers(games, rng):
    canon, spin = _chapters(games)
    chapters = [c for c in canon + spin if c.get("titulo") and any(v.get("tipo") != "info" for v in c["versoes"])]
    titles = {c["id"]: c["titulo"] for c in chapters + catalog.load_timeline(games, "midia")}
    people = [p for p in characters.curated() if p.get("nome")]
    names = {p["id"]: p["nome"] for p in people}
    viruses = lore.load("virus").get("itens", [])

    def year_story():
        c = rng.choice([c for c in canon if _year(c.get("quando"))])
        return _q(f"Em que ano se passa {c['titulo']}?",
                  _options(rng, _year(c["quando"]), [_year(o.get("quando")) for o in canon]),
                  f"{c['titulo']}: {c['quando']}.", c["id"])

    def year_release():
        c = rng.choice([c for c in chapters if c.get("lancamento")])
        return _q(f"Em que ano {c['titulo']} foi lançado?",
                  _options(rng, str(c["lancamento"]), [str(o.get("lancamento", "")) for o in chapters]),
                  f"Lançado em {c['lancamento']}.", c["id"])

    def where():
        c = rng.choice([c for c in canon if c.get("onde")])
        return _q(f"Onde se passa {c['titulo']}?", _options(rng, c["onde"], [o.get("onde") for o in canon]),
                  f"{c['titulo']}: {c['onde']}.", c["id"])

    def first():
        picks = rng.sample(canon, 4)
        order = {c["id"]: i for i, c in enumerate(canon)}
        right = min(picks, key=lambda c: order[c["id"]])
        opts = [c["titulo"] for c in picks]
        return _q("Qual destes acontece primeiro na história?", (opts, opts.index(right["titulo"])),
                  f"{right['titulo']} vem antes ({right.get('quando', '')}).", right["id"])

    def appears():
        p = rng.choice([p for p in people if any(a in titles for a in p.get("aparicoes", []))])
        inside = [titles[a] for a in p["aparicoes"] if a in titles]
        right = rng.choice(inside)
        pool = [t for t in titles.values() if t not in inside]
        return _q(f"Em qual destes {p['nome']} aparece?", _options(rng, right, pool),
                  f"{p['nome']} aparece em: " + ", ".join(inside[:5]) + ".")

    def role():
        p = rng.choice([p for p in people if p.get("papel")])
        same = [o["nome"] for o in people if o.get("tipo") == p.get("tipo")]
        return _q(f"Quem é \"{p['papel']}\"?", _options(rng, p["nome"], same), p.get("descricao", ""))

    def creator():
        v = rng.choice([v for v in viruses if any(c in names for c in v.get("criadores", []))])
        right = names[next(c for c in v["criadores"] if c in names)]
        pool = [o["nome"] for o in people if o.get("tipo") in ("vilao", "heroi") and o["id"] not in v["criadores"]]
        return _q(f"Quem criou o {v['nome']}?", _options(rng, right, pool), v.get("origem", ""))

    makers = [year_story, year_release, where, appears, role]
    if len(canon) >= 4:
        makers.append(first)
    if any(any(c in names for c in v.get("criadores", [])) for v in viruses):
        makers.append(creator)
    return makers


def generate(games, n=10, seed=None):
    """n perguntas sem repetir o enunciado."""
    rng = random.Random(seed)
    makers = _makers(games, rng)
    out, seen = [], set()
    for _ in range(n * 20):
        if len(out) >= n:
            break
        try:
            q = rng.choice(makers)()
        except (IndexError, ValueError, StopIteration):   # um tipo sem dados suficientes: tenta outro
            continue
        if q and q["pergunta"] not in seen:
            seen.add(q["pergunta"])
            out.append(q)
    return out
