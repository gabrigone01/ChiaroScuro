#!/usr/bin/env python3
"""Ponte Chiaroscuro da terminale (senza finestra). Il codice è nel pacchetto chiaroscuro (chiaroscuro/bridge.py).
    python3 Chiaroscuro/scripts/piano_luci.py [--non-aprire] [--qlc finestra] [--sorgente roland] [--lista] ...
Per la finestra dell'app:  python3 -m chiaroscuro  (dalla cartella Chiaroscuro) oppure avvia.command."""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from chiaroscuro.bridge import main  # noqa: E402

if __name__ == "__main__":
    main(sys.argv[1:])
