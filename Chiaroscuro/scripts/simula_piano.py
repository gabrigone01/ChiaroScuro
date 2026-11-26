#!/usr/bin/env python3
"""Pianista simulato da terminale. Nell'app c'è "Play simulazione" (impostazioni) che suona dentro l'app.
    python3 Chiaroscuro/scripts/simula_piano.py --offline [--seed N]     verifica l'analisi in un attimo
    python3 Chiaroscuro/scripts/simula_piano.py dolce tempesta -d 15     (solo macOS) sorgente MIDI virtuale "Piano simulato"
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")))
from chiaroscuro import simulator  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scenari", nargs="*", default=simulator.TUTTI)
    ap.add_argument("-d", "--durata", type=float, default=25.0)
    ap.add_argument("--offline", action="store_true", help="verifica l'analisi senza MIDI né QLC+")
    ap.add_argument("--seed", type=int, default=1)
    a = ap.parse_args()
    if a.offline:
        rows, ok, n = simulator.offline_check(a.seed, a.durata, a.scenari)
        print("\n".join(rows))
        print(f"{ok}/{n} scenari riconosciuti")
        return
    import signal
    from chiaroscuro._shared import midi_in  # noqa: F401  (aggiunge _tools al percorso)
    import coremidi
    v = coremidi.VirtualSource("Piano simulato")
    print("Sorgente MIDI 'Piano simulato' pronta.")
    time.sleep(2.5)
    p = simulator.Player(lambda s, d1, d2: v.send([s, d1, d2]), a.scenari, a.durata, seed=a.seed)
    signal.signal(signal.SIGTERM, lambda *_: p.stop())
    last = None
    try:
        while p.info["on"]:
            if p.info["scenario"] != last:
                last = p.info["scenario"]
                print(f"[{p.info['n']}/{p.info['tot']}] {last}")
            time.sleep(0.2)
    except KeyboardInterrupt:
        p.stop()
        time.sleep(0.3)
    v.close()


if __name__ == "__main__":
    main()
