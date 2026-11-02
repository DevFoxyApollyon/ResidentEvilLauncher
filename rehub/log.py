"""Registro de erros em data/logs/launcher.log (até 3 arquivos de 1 MB): o que deu errado fica anotado em vez de
sumir num 'except: pass'. Opções > Sistema > Abrir log mostra o arquivo."""
import logging
import logging.handlers
import sys
import threading

from .paths import DATA

FOLDER = DATA / "logs"
FILE = FOLDER / "launcher.log"
log = logging.getLogger("rehub")


def setup():
    """Liga o arquivo de log e anota as exceções que escaparem (da interface, das threads ou do processo)."""
    if log.handlers:
        return log
    log.setLevel(logging.INFO)
    try:
        FOLDER.mkdir(parents=True, exist_ok=True)
        h = logging.handlers.RotatingFileHandler(FILE, maxBytes=1 << 20, backupCount=2, encoding="utf-8", delay=True)
    except OSError:   # pasta sem permissão: segue sem log em arquivo
        h = logging.NullHandler()
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s", "%Y-%m-%d %H:%M:%S"))
    log.addHandler(h)
    sys.excepthook = lambda t, v, tb: log.critical("erro não tratado", exc_info=(t, v, tb))
    threading.excepthook = lambda a: a.exc_type is not SystemExit and log.error(
        "erro na thread %s", a.thread.name if a.thread else "?", exc_info=(a.exc_type, a.exc_value, a.exc_traceback))
    return log


def error(msg, *args):
    """Anota um erro com o traceback da exceção que está sendo tratada."""
    log.error(msg, *args, exc_info=True)


def info(msg, *args):
    log.info(msg, *args)
