"""Avvio: `python3 -m chiaroscuro` (finestra) oppure `python3 -m chiaroscuro --cli [opzioni]` (solo terminale)."""
import os
import sys


def _redirect_output():
    """App senza console (Windows/macOS impacchettata): stampe in un file di log nella cartella dati."""
    if sys.stdout is None or sys.stderr is None or getattr(sys, "frozen", False):
        from . import paths
        os.makedirs(paths.DATA_DIR, exist_ok=True)
        log = open(os.path.join(paths.DATA_DIR, "chiaroscuro.log"), "w", encoding="utf-8", buffering=1)
        sys.stdout = sys.stderr = log


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("-psn_")]   # macOS aggiunge -psn_… alle app
    if args:
        from . import bridge
        bridge.main(args)
    else:
        _redirect_output()
        from . import gui
        gui.main()


if __name__ == "__main__":
    main()
