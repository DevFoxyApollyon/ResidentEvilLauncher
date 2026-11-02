"""Partes sem interface: downloads seguros, versões, argumentos de emulador, links de ISO, cache, saves, busca e quiz."""
import hashlib
import json
import os
import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from rehub import cache, catalog, emulators, github, isodl, launcher, quiz, saves, search, updater


class DownloadsTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def test_zip_outside_folder_is_refused(self):
        z = self.tmp / "mau.zip"
        with zipfile.ZipFile(z, "w") as f:
            f.writestr("../fora.txt", "x")
        with self.assertRaises(RuntimeError):
            github.extract_zip(z, self.tmp / "out")
        self.assertFalse((self.tmp / "fora.txt").exists())

    def test_zip_single_folder_is_unwrapped(self):
        z = self.tmp / "mod.zip"
        with zipfile.ZipFile(z, "w") as f:
            f.writestr("MeuMod-v2/arquivo.txt", "x")
        github.extract_zip(z, self.tmp / "out")
        self.assertTrue((self.tmp / "out" / "arquivo.txt").exists())

    def test_digest(self):
        f = self.tmp / "a.bin"
        f.write_bytes(b"resident evil")
        good = "sha256:" + hashlib.sha256(b"resident evil").hexdigest()
        self.assertTrue(github.check_digest(f, good))
        self.assertFalse(github.check_digest(f, None))   # sem hash publicado: não confere
        with self.assertRaises(RuntimeError):
            github.check_digest(f, "sha256:" + "0" * 64)
        self.assertFalse(f.exists(), "arquivo com hash errado deve ser apagado")


class VersionTest(unittest.TestCase):
    def test_newer(self):
        self.assertTrue(updater.newer("v1.9.0", "1.8.4"))
        self.assertTrue(updater.newer("v1.10.0", "1.9.9"))
        self.assertFalse(updater.newer("v1.8.4", "1.8.4"))
        self.assertFalse(updater.newer("1.8.3", "1.8.4"))
        self.assertTrue(updater.newer("2026.11.02", "2026.10.25"))

    def test_not_frozen_has_no_version(self):
        self.assertIsNone(updater.current())


class EmulatorArgsTest(unittest.TestCase):
    def test_default_args(self):
        self.assertEqual(emulators.args_for({"emulador": "pcsx2"}), emulators.EMULATORS["pcsx2"]["args"])
        self.assertIsNone(emulators.args_for({}))

    def test_profiles(self):
        a = emulators.args_for({"emulador": "pcsx2"}, {"tela_cheia": False})
        self.assertIn("-nofullscreen", a)
        a = emulators.args_for({"emulador": "dolphin"}, {"tela_cheia": True, "escala": 3, "widescreen": True, "extra": "-d"})
        for part in ("Dolphin.Display.Fullscreen=True", "GFX.Settings.InternalResolution=3",
                     "GFX.Settings.wideScreenHack=True", "-d ", '-e "{iso}"'):
            self.assertIn(part, a)

    def test_split_args_keeps_iso_with_spaces(self):
        argv = launcher.split_args('-b -e "{iso}"', {"iso": r"C:\Meus Jogos\re.iso"})
        self.assertEqual(argv, ["-b", "-e", r"C:\Meus Jogos\re.iso"])


class IsoLinksTest(unittest.TestCase):
    def test_variants_and_hash(self):
        self.assertEqual(isodl._variants(" http://a "), {"Normal": "http://a"})
        self.assertEqual(isodl._variants({"Normal": {"link": "http://b", "sha256": "ab"}, "Dublada": ""}),
                         {"Normal": "http://b"})
        isodl.LINKS.parent.mkdir(parents=True, exist_ok=True)
        isodl.LINKS.write_text(json.dumps({"x": {"Normal": {"link": "http://b", "sha256": "ab"}}}), encoding="utf-8")
        g = {"id": "x", "capitulo": "y"}
        self.assertEqual(isodl.link_for(g), {"Normal": "http://b"})
        self.assertEqual(isodl.hash_for(g, "Normal"), "ab")
        self.assertIsNone(isodl.hash_for(g, "Dublada"))


class BrowserDownloadTest(unittest.TestCase):
    def test_waits_for_partial_then_takes_file(self):
        import threading
        folder = Path(tempfile.mkdtemp())
        g = {"id": "outbreak_teste", "nome": "Outbreak", "emulador": "pcsx2", "iso_busca": ["outbreak"]}
        since = time.time()
        (folder / "outro.txt").write_text("x")

        def browser():
            part = folder / "Não confirmado 1.crdownload"
            part.write_bytes(b"x" * 10)
            time.sleep(0.5)
            part.rename(folder / "Biohazard - Outbreak #1.iso")
        threading.Thread(target=browser).start()
        path = isodl.wait_browser_download(g, since, folder=folder, timeout=10, tick=0.2)
        self.assertEqual(path.name, "Biohazard - Outbreak #1.iso")
        image = isodl.take_download(g, path, "Português")
        self.assertTrue(image.exists() and not path.exists())
        self.assertIn("outbreak_teste", str(image))

    def test_needs_browser(self):
        self.assertTrue(isodl.needs_browser("https://www.mediafire.com/file/abc/x.iso/file"))
        self.assertFalse(isodl.needs_browser("https://drive.google.com/file/d/abc/view"))


class CacheTest(unittest.TestCase):
    def test_prune_removes_oldest_first(self):
        folder = cache.FOLDERS[0] / "teste"
        folder.mkdir(parents=True, exist_ok=True)
        now = time.time()
        for k in range(10):
            p = folder / f"{k}.bin"
            p.write_bytes(b"x" * 1000)
            os.utime(p, (now - 1000 + k, now - 1000 + k))
        freed, n = cache.prune(5000 / (1 << 30), keep=0.5)   # limite de 5000 bytes: fica com 2500
        self.assertEqual(n, 8)
        self.assertEqual(sorted(p.name for p in folder.iterdir()), ["8.bin", "9.bin"])
        cache.clear()
        self.assertEqual(cache.size(), 0)


class SavesTest(unittest.TestCase):
    def test_backup_and_restore(self):
        src = Path(tempfile.mkdtemp()) / "saves"
        (src / "slot").mkdir(parents=True)
        (src / "slot" / "save1.dat").write_bytes(b"original")
        single = src.parent / "config.sav"
        single.write_bytes(b"cfg")
        z = saves.backup("teste_jogo", [src, single], "teste")
        self.assertTrue(z and z.exists())
        (src / "slot" / "save1.dat").write_bytes(b"estragado")
        single.unlink()
        self.assertEqual(saves.restore(z), 2)
        self.assertEqual((src / "slot" / "save1.dat").read_bytes(), b"original")
        self.assertEqual(single.read_bytes(), b"cfg")
        self.assertIn("teste", saves.describe(z))

    def test_keeps_last_backups(self):
        src = Path(tempfile.mkdtemp())
        (src / "s.dat").write_bytes(b"1")
        for k in range(3):
            saves.backup("teste_poda", [src], f"n{k}")
            time.sleep(1.05)   # o nome do backup tem a hora em segundos
        saves.prune("teste_poda", keep=2)
        self.assertEqual(len(saves.backups("teste_poda")), 2)

    def test_nothing_to_save(self):
        self.assertIsNone(saves.backup("vazio", [Path(tempfile.mkdtemp()) / "nao_existe"]))


class SearchQuizTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.games = catalog.load_games()

    def test_search(self):
        ix = search.index(self.games)
        self.assertEqual(search.find(ix, "LEON")[0]["titulo"], "Leon S. Kennedy")
        self.assertTrue(search.find(ix, "veronica"))
        self.assertTrue(search.find(ix, "vírus g") or search.find(ix, "g-virus"))
        self.assertEqual(search.find(ix, "   "), [])

    def test_quiz(self):
        qs = quiz.generate(self.games, 20, seed=7)
        self.assertEqual(len(qs), 20)
        self.assertEqual(len({q["pergunta"] for q in qs}), 20)
        for q in qs:
            self.assertEqual(len(q["opcoes"]), 4)
            self.assertEqual(len(set(q["opcoes"])), 4)
            self.assertIn(q["certa"], range(4))


if __name__ == "__main__":
    unittest.main()
