"""Testes do RE Launcher: python -m unittest (sem dependências além das do app).

Cada execução usa uma pasta de dados temporária (REHUB_DATA), então nunca mexe nos dados de verdade.
"""
import os
import tempfile

os.environ.setdefault("REHUB_DATA", tempfile.mkdtemp(prefix="rehub_testes_"))
