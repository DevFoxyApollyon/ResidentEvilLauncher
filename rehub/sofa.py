"""Modo sofá: o launcher abre junto com o Windows e, se houver um controle ligado, já vai para o último jogo.

Liga e desliga um valor em HKCU\\...\\Run (só deste usuário, sem administrador) que abre o launcher com --sofa.
Sem controle ligado nos primeiros segundos, o launcher não aparece (o PC foi ligado para outra coisa).
"""
import sys
import winreg
from pathlib import Path

from .franchise import FR
from .paths import ROOT

RUN = r"Software\Microsoft\Windows\CurrentVersion\Run"
FLAG = "--sofa"


def _name():
    return FR["app"]


def command():
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}" {FLAG}'
    pyw = Path(sys.executable).with_name("pythonw.exe")   # rodando pelo código: sem janela de console
    return f'"{pyw if pyw.exists() else sys.executable}" "{ROOT / "main.py"}" {FLAG}'


def enabled():
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN) as k:
            return FLAG in winreg.QueryValueEx(k, _name())[0]
    except OSError:
        return False


def set_enabled(on):
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, RUN) as k:
        if on:
            winreg.SetValueEx(k, _name(), 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(k, _name())
            except FileNotFoundError:
                pass


def started_by_windows():
    return FLAG in sys.argv
