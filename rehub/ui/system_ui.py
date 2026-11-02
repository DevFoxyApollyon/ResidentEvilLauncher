"""Tarefas do próprio launcher: atualização pelo GitHub, limite do cache, modo sofá, backup automático dos saves,
horas dos jogos fora da Steam e o log. Mixin do Hub (rehub/ui/app.py)."""
import os
import threading
import time

from .. import cache, launcher, log as logmod, saves, sofa, updater
from ..franchise import FR
from ..log import log
from . import theme as t
from .progress import Progress

UPDATE_EVERY = 20 * 3600      # procura versão nova do launcher no máximo uma vez a cada 20 horas
SAVES_EVERY = 24 * 3600       # backup automático ao jogar: no máximo um por dia por jogo


class SystemActions:
    def _system_start(self):
        """Ao abrir: limpa o cache acima do limite, procura atualização e, no modo sofá, vai para o último jogo."""
        if os.environ.get("REHUB_TESTE"):
            return
        self.after(20000, lambda: threading.Thread(target=self._prune_cache, daemon=True).start())
        if time.time() - self.cfg.get("_update").get("buscado_em", 0) > UPDATE_EVERY:
            self.after(12000, lambda: self.check_update(quiet=True))

    # ---------- atualização do launcher ----------
    def check_update(self, quiet=False):
        """Compara com a última release. quiet: só avisa se houver versão nova (é o que roda ao abrir)."""
        if updater.current() is None and not quiet:
            return t.notice(self, "Atualização", "Rodando pelo código: atualize com git pull.")

        def done(info):
            self.cfg.set("_update", buscado_em=int(time.time()))
            if info:
                self.toast(f"{FR['app']} {info['versao']} disponível", "Clique para atualizar", lambda: self._ask_update(info), 12)
            elif not quiet:
                t.notice(self, "Atualização", f"Você já está na versão mais nova ({updater.current()}).")

        def fail(msg):
            if not quiet:
                t.notice(self, "Não consegui procurar atualização", msg, error=True)
        t.in_background(self, updater.check, done, fail)

    def _ask_update(self, info):
        notes = [ln for ln in info["notas"].splitlines() if ln.strip()][:10]
        if not t.confirm(self, f"Atualizar para a versão {info['versao']}?",
                         f"O {FR['app']} baixa o instalador, confere o SHA-256 e reabre já atualizado. Seus dados ficam.",
                         notes, ok="Atualizar"):
            return
        prog = Progress(self, f"Atualizando para a versão {info['versao']}", "Depois de baixar, o launcher fecha e reabre.")

        def done(path):
            prog.close()
            log.info("atualizando para %s", info["versao"])
            updater.run_installer(path)
            self.quit_app()

        def fail(msg):
            prog.close()
            t.notice(self, "A atualização falhou", msg, error=True)
        t.in_background(self, lambda: updater.download(info, prog.step("Baixando o instalador"), prog.cancelled), done, fail)

    # ---------- cache ----------
    def cache_limit(self):
        return self.prefs.get("cache_gb", cache.DEFAULT)

    def _prune_cache(self):
        try:
            freed, n = cache.prune(self.cache_limit())
            if n:
                log.info("cache: %s arquivos apagados (%s)", n, cache.human(freed))
        except OSError:
            log.exception("falhou: limpar o cache")

    def cycle_cache_limit(self):
        opts = cache.LIMITS
        cur = self.cache_limit()
        nxt = opts[(opts.index(cur) + 1) % len(opts)] if cur in opts else cache.DEFAULT
        self._save_prefs(cache_gb=nxt)
        self.notify(f"Limite do cache: {nxt} GB (o que passar disso sai, começando pelo usado há mais tempo).")
        threading.Thread(target=self._prune_cache, daemon=True).start()

    def clear_cache(self):
        if not t.confirm(self, "Limpar o cache?", "Cards montados, prints, páginas da wiki e trailers são refeitos ou "
                         "baixados de novo quando precisar.", [f"Ocupando agora: {cache.human(cache.size())}"], ok="Limpar"):
            return
        freed = cache.clear()
        self._tiles.clear()
        self._tile_base.clear()
        self._remote.clear()
        self.notify(f"Cache limpo: {cache.human(freed)} liberados.")
        self.refresh()

    # ---------- modo sofá ----------
    def toggle_sofa(self):
        on = not sofa.enabled()
        try:
            sofa.set_enabled(on)
        except OSError as e:
            return t.notice(self, "Não deu certo", str(e), error=True)
        self.notify("Modo sofá ligado: o launcher abre com o Windows e, com o controle ligado, vai para o último jogo."
                    if on else "Modo sofá desligado.", 6)

    def _sofa_go(self):
        """Aberto pelo Windows com o controle ligado: conta 5 s e abre o último jogo (qualquer botão cancela)."""
        target = self.continue_target()
        if not target:
            return
        _sec, ch, g = target
        self.goto_chapter(ch["id"], g["id"])
        self._sofa_cancel = False
        self.toast(f"Modo sofá: abrindo {g['nome']}", "Em 5 segundos. Qualquer botão cancela.", seconds=5)

        def go():
            if not self._sofa_cancel and self.game and self.game["id"] == g["id"]:
                self.play(g)
        self.after(5000, go)

    # ---------- saves ----------
    def save_paths(self, g):
        return saves.locations(g, self.cfg, self.installed, self.steamid)

    def backup_saves(self, g, reason, done=None, quiet=True):
        """Backup dos saves numa thread. quiet: erro só vai para o log (backups automáticos)."""
        paths = self.save_paths(g)
        if not paths:
            return done and done(None)

        def ok(path):
            if path:
                self.cfg.set(g["id"], ultimo_backup=int(time.time()))
                log.info("backup dos saves de %s (%s): %s", g["id"], reason, path.name)
            if done:
                done(path)

        def fail(msg):
            log.error("backup dos saves de %s falhou: %s", g["id"], msg)
            if not quiet:
                t.notice(self, "O backup falhou", msg, error=True)
            if done:
                done(None)
        t.in_background(self, lambda: saves.backup(g["id"], paths, reason), ok, fail)

    def _auto_backup(self, g):
        if time.time() - self.cfg.get(g["id"]).get("ultimo_backup", 0) > SAVES_EVERY:
            self.backup_saves(g, "antes de jogar")

    # ---------- horas fora da Steam ----------
    def _played(self, g, seconds):
        """Um jogo fora da Steam fechou: soma o tempo (sessões de menos de 1 minuto não contam)."""
        if seconds < 60:
            return
        mins = self.cfg.get(g["id"]).get("minutos", 0) + round(seconds / 60)
        self.cfg.set(g["id"], minutos=mins, ultima=int(time.time()))
        log.info("%s: %d min (total %d)", g["id"], round(seconds / 60), mins)
        self.after(300, self.check_achievements)
        self.refresh()

    def local_minutes(self):
        """Minutos jogados em tudo que não é da Steam (contados pelo hub)."""
        return sum(self.cfg.get(g["id"]).get("minutos", 0) for g in self.games if g.get("tipo") not in ("steam", "info"))

    def launch(self, g):
        """launcher.play com o tempo de jogo contado e um backup dos saves (uma vez por dia)."""
        self._auto_backup(g)
        return launcher.play(g, self.cfg, on_exit=lambda s: self.after(0, lambda: self._played(g, s)))

    def open_log(self):
        logmod.FOLDER.mkdir(parents=True, exist_ok=True)
        os.startfile(logmod.FILE if logmod.FILE.exists() else logmod.FOLDER)
