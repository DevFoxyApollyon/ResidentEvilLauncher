"""Controle (XInput: Xbox e qualquer controle que o Windows/Steam apresente como um) e atalho global de teclado.

Tudo pelo próprio Windows (ctypes), sem instalar nada. O controle é lido pela interface a cada 50 ms;
o atalho de teclado fica numa thread com a fila de mensagens do Windows.
"""
import ctypes
import threading
import time
from ctypes import wintypes

BUTTONS = {0x0001: "up", 0x0002: "down", 0x0004: "left", 0x0008: "right", 0x0010: "start", 0x0020: "back",
           0x0100: "lb", 0x0200: "rb", 0x0400: "guide", 0x1000: "a", 0x2000: "b", 0x4000: "x", 0x8000: "y"}
REPEAT = {"up", "down", "left", "right", "rs_up", "rs_down"}  # segurar repete (como segurar a seta do teclado)
DEAD = 16000
TRIGGER = 120


class _State(ctypes.Structure):
    _fields_ = [("packet", wintypes.DWORD), ("buttons", wintypes.WORD), ("lt", ctypes.c_ubyte), ("rt", ctypes.c_ubyte),
                ("lx", ctypes.c_short), ("ly", ctypes.c_short), ("rx", ctypes.c_short), ("ry", ctypes.c_short)]


def _load():
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            dll = ctypes.WinDLL(name)
        except OSError:
            continue
        try:  # a função sem nome (ordinal 100) também lê o botão Guide/Xbox
            fn = dll[100]
        except (AttributeError, OSError):
            fn = dll.XInputGetState
        fn.argtypes, fn.restype = [wintypes.DWORD, ctypes.POINTER(_State)], wintypes.DWORD
        return fn
    return None


class Pad:
    """poll() devolve os botões que acabaram de ser apertados (e as repetições de quem está segurado)."""

    def __init__(self):
        self._get = _load()
        self._user, self._next_scan = None, 0.0
        self._held = {}   # botão -> (apertado em, próxima repetição)
        self.guide_since = None

    def _read(self):
        if not self._get:
            return None
        s = _State()
        if self._user is not None:
            if self._get(self._user, ctypes.byref(s)) == 0:
                return s
            self._user = None
        now = time.time()
        if now < self._next_scan:  # procurar controle desconectado é lento: só a cada 2 segundos
            return None
        self._next_scan = now + 2
        for u in range(4):
            if self._get(u, ctypes.byref(s)) == 0:
                self._user = u
                return s
        return None

    @property
    def connected(self):
        return self._user is not None

    def poll(self):
        s = self._read()
        down = set()
        if s is not None:
            down = {name for bit, name in BUTTONS.items() if s.buttons & bit}
            if s.lx < -DEAD:
                down.add("left")
            elif s.lx > DEAD:
                down.add("right")
            if s.ly > DEAD:
                down.add("up")
            elif s.ly < -DEAD:
                down.add("down")
            if s.ry > DEAD:
                down.add("rs_up")
            elif s.ry < -DEAD:
                down.add("rs_down")
            if s.lt > TRIGGER:
                down.add("lt")
            if s.rt > TRIGGER:
                down.add("rt")
        now, events = time.time(), []
        for name in down:
            if name not in self._held:
                self._held[name] = (now, now + 0.4)
                events.append(name)
            elif name in REPEAT and now >= self._held[name][1]:
                self._held[name] = (self._held[name][0], now + 0.11)
                events.append(name)
        for name in list(self._held):
            if name not in down:
                del self._held[name]
        self.guide_since = self._held["guide"][0] if "guide" in self._held else None
        return events


# ---------- atalho global ----------
MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 0x1, 0x2, 0x4000
WM_HOTKEY = 0x0312


def global_hotkey(callback, key="H", mods=MOD_CONTROL | MOD_ALT):
    """Ctrl+Alt+H (padrão) de qualquer lugar do Windows chama callback() (numa thread: use after() lá dentro).
    Retorna False se outro programa já usa a combinação."""
    ok = threading.Event()
    result = {}

    def loop():
        user32 = ctypes.windll.user32
        result["ok"] = bool(user32.RegisterHotKey(None, 1, mods | MOD_NOREPEAT, ord(key)))
        ok.set()
        if not result["ok"]:
            return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY:
                try:
                    callback()
                except Exception:
                    pass
    threading.Thread(target=loop, daemon=True).start()
    ok.wait(2)
    return result.get("ok", False)
