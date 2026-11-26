#!/usr/bin/env python3
"""Rigenera Chiaroscuro.qxw da rig.json (codice in chiaroscuro/generator.py). Con QLC+ chiuso, o lascia fare all'app."""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from chiaroscuro import generator, paths  # noqa: E402
from chiaroscuro._shared import qxf  # noqa: E402

if __name__ == "__main__":
    qxf.set_dirs(*paths.fixture_dirs())
    generator.build()
