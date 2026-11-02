"""O catálogo (games/) está coerente: cada versão aponta para um capítulo que existe, os ids batem e as listas
de lore só citam personagens e capítulos conhecidos."""
import json
import unittest
from collections import Counter

from rehub import catalog, emulators
from rehub.paths import GAMES_DIR


def load(name):
    return json.loads((GAMES_DIR / name).read_text(encoding="utf-8"))


class CatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        tl = load("_linha_do_tempo.json")
        cls.chapters = [c for v in tl.values() if isinstance(v, list) for c in v]
        cls.chapter_ids = {c["id"] for c in cls.chapters}
        cls.people = {p["id"] for p in load("_personagens.json")["personagens"]}

    def test_chapter_ids_unique(self):
        dup = [k for k, n in Counter(c["id"] for c in self.chapters).items() if n > 1]
        self.assertEqual(dup, [])

    def test_every_game_file(self):
        for f in sorted(GAMES_DIR.glob("*.json")):
            if f.name.startswith("_"):
                continue
            with self.subTest(arquivo=f.name):
                g = json.loads(f.read_text(encoding="utf-8"))
                self.assertIn("nome", g)
                self.assertEqual(g.get("id", f.stem), f.stem, "id diferente do nome do arquivo")
                self.assertIn(g.get("tipo"), ("steam", "local"))
                if g["tipo"] == "steam":
                    self.assertIsInstance(g.get("appid"), int)
                self.assertIn(g.get("capitulo", f.stem), self.chapter_ids, "capítulo não existe na linha do tempo")
                if g.get("emulador"):
                    self.assertIn(g["emulador"], emulators.EMULATORS)

    def test_games_load(self):
        games = catalog.load_games()
        self.assertTrue(games)
        canon = catalog.load_timeline(games, "canon")
        self.assertTrue(all(ch["versoes"] for ch in canon))

    def test_lore_references(self):
        for p in load("_personagens.json")["personagens"]:
            for a in p.get("aparicoes", []):
                self.assertIn(a, self.chapter_ids, f"{p['id']} aparece em {a}")
        for v in load("_virus.json")["itens"]:
            for pid in v.get("criadores", []) + v.get("infectados", []):
                self.assertIn(pid, self.people, f"{v['id']} cita {pid}")
        mapa = load("_mapa.json")
        for pl in mapa["mundo"] + mapa["cidade"]["locais"]:
            for c in pl.get("capitulos", []):
                self.assertIn(c, self.chapter_ids, f"{pl['nome']} cita {c}")
        for gr in load("_relacoes.json")["grupos"]:
            for m in gr["membros"]:
                self.assertIn(m, self.people, f"{gr['nome']} cita {m}")

    def test_marathon_hours(self):
        canon = {c["id"] for c in load("_linha_do_tempo.json")["capitulos"]}
        for cid, hours in load("_maratona.json")["horas"].items():
            self.assertIn(cid, canon)
            self.assertGreater(hours, 0)


if __name__ == "__main__":
    unittest.main()
