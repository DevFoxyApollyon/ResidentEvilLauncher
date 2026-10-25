"""Progresso de download e conversão: barra, quanto já foi, velocidade e tempo restante de cada etapa (port, ISO...).

Os downloads rodam numa thread; ela só grava o estado. Task aparece embaixo do jogo na tela principal (o jeito
usado pelo hub); Progress é a janela por cima, para telas sem lugar para isso. Cancelar para o download.
"""
import tkinter as tk

from ..isodl import clock, human
from . import theme as t

W = 460


def describe(s):
    """Texto do estado: '45%  ·  1.2 GB de 3.4 GB  ·  12 MB/s  ·  faltam 3:10'."""
    if s["total"]:
        pct = 100 * s["done"] / s["total"]
        text = (f"{pct:.0f}%" if s.get("items") == "pct" else f"{s['done']} de {s['total']}" if s.get("items") else
                f"{pct:.0f}%  ·  {human(s['done'])} de {human(s['total'])}")
    else:
        text = "Começando..." if s.get("items") else human(s["done"]) if s["done"] else "Conectando..."
    if s["speed"]:
        text += f"  ·  {human(s['speed'])}/s"
    if s["eta"] is not None:
        text += f"  ·  faltam {clock(s['eta'])}"
    return text


class Task:
    """O mesmo progresso, mas sem janela: aparece embaixo do jogo na tela principal (o hub desenha), com Cancelar.
    gid: o id da versão (ou do capítulo) embaixo da qual ele aparece; muda em lotes (várias ISOs)."""

    def __init__(self, hub, gid, title=""):
        self.hub, self.gid, self.title = hub, gid, title
        self.cancel_flag = False
        self.state = {"step": title or "Preparando...", "done": 0, "total": 0, "speed": 0, "eta": None}
        hub.tasks.append(self)
        hub._tasks_tick()

    def step(self, name, items=False, gid=None):
        self.state.update(step=name, done=0, total=0, speed=0, eta=None, items=items)
        if gid:
            self.gid = gid

        def progress(done, total, speed, eta):
            self.state.update(done=done, total=total, speed=speed, eta=eta)
        return progress

    def cancelled(self):
        return self.cancel_flag

    def cancel(self):
        self.cancel_flag = True

    def frac(self):
        s = self.state
        return s["done"] / s["total"] if s["total"] else 0.0

    def line(self):
        return f"{self.state['step']}  ·  {describe(self.state)}"

    def close(self):
        if self in self.hub.tasks:
            self.hub.tasks.remove(self)
        self.hub.refresh()


class Progress:
    def __init__(self, parent, title, subtitle=""):
        self.top, body, bar, self.close = t.modal(parent, title, subtitle, width=W + 60)
        self.step_lbl = t.label(body, "Preparando...", 11, bold=True)
        self.step_lbl.pack(fill="x")
        self.canvas = tk.Canvas(body, width=W, height=10, bg=t.LINE, highlightthickness=0)
        self.canvas.pack(fill="x", pady=(10, 6))
        self.fill = self.canvas.create_rectangle(0, 0, 0, 10, fill=t.RED, outline="")
        self.info = t.label(body, "", 10, fg=t.MUTED)
        self.info.pack(fill="x")
        self.cancel_flag = False
        self.state = {"step": "Preparando...", "done": 0, "total": 0, "speed": 0, "eta": None}
        t.flat_button(bar, "Cancelar", self._cancel, "danger").pack(side="right")
        t.flat_button(bar, "Esconder", self.close, "ghost").pack(side="right", padx=(0, 8))
        self._tick()

    def step(self, name, items=False):
        """Comeca uma etapa e devolve o callback de progresso dela (chamado pela thread do download).
        items=True: conta arquivos (3 de 5) em vez de bytes; items="pct": só a porcentagem (conversão)."""
        self.state.update(step=name, done=0, total=0, speed=0, eta=None, items=items)

        def progress(done, total, speed, eta):
            self.state.update(done=done, total=total, speed=speed, eta=eta)
        return progress

    def cancelled(self):
        return self.cancel_flag

    def _cancel(self):
        self.cancel_flag = True
        self.close()

    def _tick(self):
        if not self.top.winfo_exists():
            return
        s = self.state
        self.step_lbl.config(text=s["step"])
        w = self.canvas.winfo_width() or W
        self.canvas.coords(self.fill, 0, 0, w * s["done"] / s["total"] if s["total"] else 0, 10)
        self.info.config(text=describe(s))
        self.top.after(200, self._tick)
